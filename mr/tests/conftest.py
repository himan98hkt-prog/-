# -*- coding: utf-8 -*-
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

FIXTURES = os.path.join(ROOT, 'fixtures')
SCORES = os.path.join(FIXTURES, 'scores')


def score(name: str) -> str:
    return os.path.join(SCORES, name + '.musicxml')


# --- 관리노트와 대조하는 검사 -------------------------------------------------
# 반주는 관리노트와 **따로 파는 제품**이다 (`tools/standalone.py`). 떼어 내면
# 대조할 자바스크립트 원본이 따라오지 않는다 — 따라오면 그게 분리 실패다.
# 그래서 원본이 없으면 건너뛰되, 합본에서는 **반드시 돌아야** 한다. 그 못은
# 각 파일의 `..._does_not_vanish_in_the_combined_repo` 가 박는다.

REPO = os.path.dirname(ROOT)


def note_source(rel: str) -> str:
    """관리노트 쪽 파일의 절대경로 (합본일 때만 있다)."""
    return os.path.join(REPO, *rel.split('/'))


def is_combined() -> bool:
    """합본 저장소 안인가. 관리노트의 `package.json` 이 옆에 있으면 그렇다."""
    return os.path.exists(os.path.join(REPO, 'package.json'))


def needs_note_source(rel: str):
    import pytest
    return pytest.mark.skipif(
        not os.path.exists(note_source(rel)),
        reason=f'분리된 제품에는 관리노트의 {rel} 이(가) 없습니다')
