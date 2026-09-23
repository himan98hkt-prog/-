# -*- coding: utf-8 -*-
"""콩쿨 레퍼토리 목록 — 무엇을 넣을 수 있고, 무엇을 넣으면 안 되는가.

지역 콩쿨 과제곡은 **거의 다 퍼블릭도메인**이다. 바이엘·체르니·부르크뮐러·
소나티네·바흐·쇼팽… 전부 작곡가가 죽은 지 백 년이 넘었다. 이 제품이 성립하는
이유가 그것이다.

그래도 사람 판단을 믿지 않는다. 목록의 곡마다 **작곡가 사망연도**를 적어 두고,
넣을 때 보호기간(사후 70년)을 **코드가 다시 계산한다.** 카발레프스키처럼 콩쿨에
자주 나오지만 아직 보호기간 안인 작곡가를 사람이 섞어 넣는 일을 막는다.

여기에 악보는 없다. 목록과 저작권 근거만 있다. MusicXML 은 사람이 확보해서
한 폴더에 넣고 `catalog_cli.py import --manifest` 로 한 번에 들인다.
"""
from __future__ import annotations

import datetime
import json
import os
from typing import List, Optional, Sequence, Tuple

from .catalog import CopyrightError

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PATH = os.path.join(os.path.dirname(HERE), 'repertoire', 'competition.json')
FORMAT = 'piano-mr-repertoire'

# 저작권 보호기간. 한국·EU·미국(1978년 이후 작) 모두 사후 70년이다.
TERM_YEARS = 70

# 악보 파일로 인정하는 확장자. 옛 MusicXML 은 .xml 로도 나온다.
SCORE_EXT = ('.musicxml', '.mxl', '.xml', '.krn')


def load(path: Optional[str] = None) -> dict:
    with open(path or DEFAULT_PATH, encoding='utf-8') as f:
        data = json.load(f)
    if data.get('format') != FORMAT:
        raise ValueError(f'레퍼토리 목록이 아닙니다: {data.get("format")!r}')
    return data


def expired(died: Optional[int], today: Optional[datetime.date] = None) -> bool:
    """보호기간이 끝났는가. 사망연도를 모르면(None) **끝났다고 보지 않는다.**"""
    if died is None:
        return False
    year = (today or datetime.date.today()).year
    # 사망한 **다음 해 1월 1일**부터 센다 (한국 저작권법 제44조).
    return year > died + TERM_YEARS


def check(work: dict, today: Optional[datetime.date] = None) -> None:
    """넣어도 되는 곡인가. 아니면 왜 안 되는지 말하고 막는다."""
    died = work.get('died')
    if expired(died, today):
        return
    who = f'{work.get("title", work.get("id"))} — {work.get("composer")}'
    if died is None:
        # 사망연도를 모르면 **끝났다고 보지 않는다.** 교재처럼 출판사가 권리를
        # 갖는 것도 여기로 온다 — 모르는 것을 넘겨주는 쪽이 위험하다.
        raise CopyrightError(
            f'{who} 는 저작권이 끝났는지 확인되지 않았습니다 (사망연도 미상). '
            '지시서 7장: 확인된 곡만 카탈로그에 넣습니다.')
    raise CopyrightError(
        f'{who} 는 아직 저작권 보호기간 안입니다 '
        f'(사망 {died}년 · {died + TERM_YEARS + 1}년에 만료). '
        '지시서 7장: 보호기간이 끝난 곡만 카탈로그에 넣습니다.')


def find_score(work: dict, scores_dir: str) -> Optional[str]:
    """목록의 한 곡에 맞는 악보 파일을 찾는다.

    `file` 이 적혀 있으면 그것을, 없으면 `<id>.<확장자>` 를 본다. 원장님이 파일
    이름을 목록의 id 로 맞춰 두면 아무것도 안 적어도 된다.
    """
    names = [work['file']] if work.get('file') else [work['id'] + e for e in SCORE_EXT]
    for name in names:
        path = os.path.join(scores_dir, name)
        if os.path.exists(path):
            return path
    return None


def survey(works: Sequence[dict], scores_dir: str,
           today: Optional[datetime.date] = None) -> Tuple[List[dict], List[dict], List[dict]]:
    """넣을 수 있는 것 / 악보가 없는 것 / 저작권에 걸리는 것으로 가른다."""
    ready: List[dict] = []
    missing: List[dict] = []
    blocked: List[dict] = []
    for w in works:
        try:
            check(w, today)
        except CopyrightError as e:
            blocked.append({**w, 'why': str(e)})
            continue
        path = find_score(w, scores_dir)
        (ready if path else missing).append({**w, 'path': path})
    return ready, missing, blocked
