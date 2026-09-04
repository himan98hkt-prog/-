"""프로세스 메모리 저장소를 SQLite 파일 하나로 내렸다 올린다.

지금까지는 서버를 재시작하면 올린 코퍼스와 만든 곡이 전부 사라졌다. 학원 PC 는
껐다 켜는 기계이므로 이것은 실사용에서 곧바로 문제가 된다.

**왜 스냅샷인가.** 라우터들이 `store.jobs.setdefault("guides", {})[cid] = guide` 처럼
버킷 **안쪽**을 직접 고친다. 쓰기를 가로채는 dict 로는 그런 변경이 보이지 않는다.
저장소 전체가 학원 하나 분량(수백 곡)이라 통째로 직렬화해도 부담이 없으므로,
쓰기가 일어난 요청 뒤에 전체를 한 번 저장한다.

**값의 형태.** 버킷에는 pydantic 모델·dataclass·원시값이 섞여 있다. 타입마다
코덱을 손으로 쓰면 새 필드가 생길 때마다 조용히 어긋나므로, 클래스 경로를 함께
적는 범용 인코더를 쓴다. 복원할 때는 `app.` 으로 시작하는 모듈만 import 한다 —
파일에 적힌 임의의 모듈을 불러오지 않는다.
"""
from __future__ import annotations

import importlib
import json
import logging
import sqlite3
import threading
from dataclasses import fields as dc_fields
from dataclasses import is_dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

log = logging.getLogger(__name__)

MODEL_TAG = "__model__"
DATACLASS_TAG = "__dataclass__"
ALLOWED_PREFIX = "app."


def _qualname(obj: object) -> str:
    t = type(obj)
    return f"{t.__module__}:{t.__qualname__}"


def encode(value: Any) -> Any:
    """pydantic 모델·dataclass·컨테이너를 JSON 으로 바꿀 수 있는 형태로."""
    if isinstance(value, BaseModel):
        return {MODEL_TAG: _qualname(value), "data": value.model_dump(mode="json")}
    if is_dataclass(value) and not isinstance(value, type):
        return {
            DATACLASS_TAG: _qualname(value),
            "data": {f.name: encode(getattr(value, f.name)) for f in dc_fields(value) if f.init},
        }
    if isinstance(value, dict):
        return {str(k): encode(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [encode(v) for v in value]
    if isinstance(value, set):
        return sorted(encode(v) for v in value)
    if isinstance(value, Path):
        return str(value)
    return value


def _resolve(path: str) -> type:
    module, _, qual = path.partition(":")
    if not module.startswith(ALLOWED_PREFIX):
        raise ValueError(f"허용되지 않은 모듈: {module}")
    obj: Any = importlib.import_module(module)
    for part in qual.split("."):
        obj = getattr(obj, part)
    if not isinstance(obj, type):
        raise ValueError(f"클래스가 아니다: {path}")
    return obj


def decode(value: Any) -> Any:
    if isinstance(value, dict):
        if MODEL_TAG in value:
            cls = _resolve(value[MODEL_TAG])
            return cls.model_validate(value["data"])          # type: ignore[attr-defined]
        if DATACLASS_TAG in value:
            cls = _resolve(value[DATACLASS_TAG])
            return cls(**{k: decode(v) for k, v in value["data"].items()})
        return {k: decode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [decode(v) for v in value]
    return value


class SqlitePersistence:
    """버킷 이름 → JSON 한 줄. 테이블 하나로 끝난다."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.execute("CREATE TABLE IF NOT EXISTS store (bucket TEXT PRIMARY KEY, payload TEXT NOT NULL)")

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path)
        con.execute("PRAGMA journal_mode=WAL")
        return con

    def save(self, buckets: dict[str, Any]) -> None:
        rows = []
        for name, value in buckets.items():
            try:
                rows.append((name, json.dumps(encode(value), ensure_ascii=False)))
            except (TypeError, ValueError) as e:
                # 한 버킷이 직렬화되지 않는다고 나머지까지 잃지 않는다.
                log.warning("버킷 %s 저장 실패, 건너뛴다: %s", name, e)
        with self._lock, self._connect() as con:
            con.executemany("INSERT OR REPLACE INTO store (bucket, payload) VALUES (?, ?)", rows)

    def load(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        with self._lock, self._connect() as con:
            for name, payload in con.execute("SELECT bucket, payload FROM store"):
                try:
                    out[name] = decode(json.loads(payload))
                except (ValueError, TypeError, AttributeError, ImportError) as e:
                    # 스키마가 바뀌어 못 읽는 버킷은 비우고 계속 뜬다.
                    log.warning("버킷 %s 복원 실패, 비운 채로 시작한다: %s", name, e)
        return out
