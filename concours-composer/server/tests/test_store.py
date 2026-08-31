"""SQLite 스냅샷 저장소 — 재시작해도 곡이 남는가."""
from __future__ import annotations

from pathlib import Path

from app.api.deps import Store, get_store
from app.main import app
from app.schemas.music import Measure, ScoreEvent, Voice
from app.store.persistence import decode, encode
from app.validate.validator import ValidationReport
from fastapi.testclient import TestClient


def _measure() -> Measure:
    return Measure(
        number=1,
        rh=[Voice(events=[ScoreEvent(dur=4.0, pitches=["C5"])])],
        lh=[Voice(events=[ScoreEvent(dur=4.0, pitches=["C3"])])],
        dynamics="mf",
    )


def test_encode_decode_pydantic_roundtrip() -> None:
    m = _measure()
    back = decode(encode(m))
    assert isinstance(back, Measure)
    assert back == m


def test_encode_decode_dataclass_roundtrip() -> None:
    rep = ValidationReport()
    rep.add("parallels", "soft", "병행 5도", [3, 4])
    back = decode(encode(rep))
    assert isinstance(back, ValidationReport)
    assert back.warnings[0].measures == [3, 4]
    assert back.summary() == rep.summary()


def test_decode_refuses_foreign_module() -> None:
    """파일에 적힌 임의의 모듈을 import 하지 않는다."""
    payload = {"__model__": "os:system", "data": {}}
    try:
        decode(payload)
    except ValueError as e:
        assert "허용되지 않은" in str(e)
    else:                                   # pragma: no cover
        raise AssertionError("외부 모듈을 그대로 불러왔다")


def test_store_survives_restart(tmp_path: Path) -> None:
    db = tmp_path / "store.sqlite3"
    a = Store()
    a.attach(db)
    a.students["s1"] = {"id": "s1", "name": "김민준"}
    a.compositions["c1"] = {"measures": [_measure()]}
    a.save()

    b = Store()
    b.attach(db)
    assert b.students["s1"]["name"] == "김민준"
    assert isinstance(b.compositions["c1"]["measures"][0], Measure)


def test_api_write_is_persisted(tmp_path: Path) -> None:
    """POST 한 번이면 파일에 남고, 새 저장소가 그것을 읽는다."""
    store = get_store()
    before = dict(store.students)
    store.attach(tmp_path / "api.sqlite3")
    try:
        with TestClient(app) as c:
            r = c.post("/api/students", json={
                "id": "s-persist", "name": "이서연", "grade": "초4", "level": 4,
                "hand_span": {"max_interval": 8}, "tempo_comfort_max_bpm": 108,
            })
            assert r.status_code in (200, 201), r.text
            sid = r.json()["id"]

        fresh = Store()
        fresh.attach(tmp_path / "api.sqlite3")
        assert sid in fresh.students
    finally:
        store.persistence = None
        store.students.clear()
        store.students.update(before)
