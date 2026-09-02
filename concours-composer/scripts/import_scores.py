#!/usr/bin/env python3
"""`data/reference_scores/` 의 참고 악보를 코퍼스에 적재한다.

원장이 폴더에 악보를 넣어 두기만 하면 되도록 만든다 — 업로드 화면을 거치지 않는다.
같은 파일을 두 번 읽지 않게 내용 해시로 기록을 남긴다.

저작권 표시가 없으면 **copyrighted 로 간주**한다(안전한 쪽). 저작권곡은 통계만 쓰고
음표열을 보관하지 않는다(CLAUDE.md 절대 규칙 3).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

# 참고 악보도 만든 곡과 같은 자리에 둔다 — **프로그램 폴더 바깥**.
# 프로그램 폴더 안에 두면 새 판을 받으려고 폴더를 지울 때 함께 사라진다.
# 원장이 모아 둔 악보를 그렇게 잃게 할 수는 없다.
from app.config import resolve_data_dir  # noqa: E402

DATA = resolve_data_dir()
SCORE_DIR = DATA / "reference_scores"
LEDGER = DATA / "reference_scores.imported.json"
SUFFIXES = {".musicxml", ".xml", ".mxl", ".mid", ".midi"}


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _sidecar(path: Path) -> dict[str, Any]:
    side = path.with_suffix(".json")
    if not side.exists():
        return {}
    try:
        data = json.loads(side.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"  ! {side.name} 을 읽을 수 없다 ({e}) — 저작권곡으로 취급한다")
        return {}
    return data if isinstance(data, dict) else {}


def _tags(path: Path) -> list[str]:
    """하위 폴더 이름을 부문 태그로."""
    rel = path.relative_to(SCORE_DIR).parent
    return [p for p in rel.parts if p not in (".", "")]


def scan() -> list[Path]:
    if not SCORE_DIR.exists():
        return []
    return sorted(p for p in SCORE_DIR.rglob("*") if p.suffix.lower() in SUFFIXES)


def load_ledger() -> dict[str, str]:
    if not LEDGER.exists():
        return {}
    try:
        data = json.loads(LEDGER.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def sync(corpus: Any, *, force: bool = False, quiet: bool = False) -> dict[str, int]:
    """폴더를 훑어 새 악보만 적재한다. 돌려주는 값은 {added, skipped, failed}."""
    from app.ingest.parse import UnsupportedScore

    ledger = {} if force else load_ledger()
    added = skipped = failed = 0
    for path in scan():
        key = str(path.relative_to(SCORE_DIR))
        digest = _digest(path)
        if ledger.get(key) == digest:
            skipped += 1
            continue
        meta = _sidecar(path)
        tags = list(dict.fromkeys([*_tags(path), *meta.get("division_tags", [])]))
        try:
            score = corpus.add_file(
                path,
                score_id=f"ref-{digest}",
                title=meta.get("title") or path.stem,
                composer=meta.get("composer", ""),
                # 표시가 없으면 저작권곡이다 — 음표열을 보관하지 않는 쪽이 안전하다.
                copyright_status=meta.get("copyright_status", "copyrighted"),
                era=meta.get("era", ""),
                source=meta.get("source", str(path.relative_to(ROOT))),
                division_tags=tags,
                teacher_difficulty=meta.get("teacher_difficulty"),
            )
        except (UnsupportedScore, ValueError, OSError) as e:
            failed += 1
            if not quiet:
                print(f"  ! {key}: {type(e).__name__}: {e}")
            continue
        ledger[key] = digest
        added += 1
        if not quiet:
            keep = "음표열 보관" if score.measures is not None else "통계만"
            print(f"  + {key} — {score.title} · {score.copyright_status} ({keep})")
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"added": added, "skipped": skipped, "failed": failed}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="이미 읽은 파일도 다시 읽는다")
    args = ap.parse_args()

    from app.api.corpus import get_corpus

    if not SCORE_DIR.exists():
        print(f"{SCORE_DIR.relative_to(ROOT)} 가 없다 — 만들고 악보를 넣어라")
        return 1
    print(f"{SCORE_DIR.relative_to(ROOT)} 를 훑는다")
    r = sync(get_corpus(), force=args.all)
    print(f"새로 적재 {r['added']} · 건너뜀 {r['skipped']} · 실패 {r['failed']}")
    return 0 if r["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
