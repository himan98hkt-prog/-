# -*- coding: utf-8 -*-
"""악보 **입력본**의 출처 — 곡이 만료된 것과, 팔 수 있는 것은 다른 문제다.

악보 한 장에는 권리가 세 겹으로 붙는다.

    ① **곡**     작곡가의 저작권.      부르크뮐러 1858년 사망 → 만료.
    ② **판본**   출판사의 편집(운지·페달). 헨레·피터스 판은 살아 있다.
    ③ **입력본** 그 악보를 컴퓨터에 쳐 넣은 사람의 것.

`repertoire.py` 가 보는 것은 ①뿐이다. 이 파일은 ③을 본다. ①만 보고 "만료된
곡이니 괜찮겠지" 하면 ③에서 걸린다 — **곡이 만료돼도 그 파일에 붙은 약정은
따로 돌아간다.**

**그런데 우리가 파는 것은 악보가 아니다.** 우리가 파는 것은 프로그램과, 만료된
곡에 우리 엔진이 붙인 **반주**다. 그 반주의 화성·편곡은 우리 것이다. 그래서
입력본만 깨끗하면 나머지는 전부 우리 것이 된다. 이 파일이 지키는 것이 그
"입력본만 깨끗하면" 이다.

## 왜 NC 가 특히 위험한가

`CC BY-NC-SA` 같은 라이선스는 **받는 것은 공짜지만 파는 것은 금지**다. 둘을
헷갈리기 쉽다. 게다가 `SA`(동일조건변경허락)는 더 곤란하다 — 그것으로 만든
결과물도 같은 조건으로 풀어야 해서, **반주 음원까지 딸려 나간다.**

`ND`(변경금지)는 상업적 사용을 허용해도 우리한테는 막힌 것이다. 반주를 붙이는
것 자체가 2차적 저작물이라서다. 그래서 `sellable` 은 `commercial` 과 다르다.

## 모르면 못 쓴다

기본값은 `unknown` 이고 **`unknown` 은 팔 수 없다.** 모르는 것을 넘겨주는 쪽이
위험하기 때문이다 — `repertoire.expired()` 가 사망연도를 모를 때 "끝났다고 보지
않는" 것과 같은 원칙이다.

예를 들어 music21 코퍼스는 자기 `license.txt` 에 이렇게 적어 두었다.

    Some encodings included in the corpus may not be used for commercial uses
    or have other restrictions

**어느 것인지는 알려 주지 않는다.** 그러니 코퍼스에서 온 악보는 전부 `unknown`
이다. 실제로 코퍼스의 쇼팽 마주르카(`chopin/mazurka06-2.krn`)는 `!!!ENC: Craig
Stuart Sapp` 이고, 같은 사람의 GitHub 저장소들은 전부 `CC BY-NC-SA` 다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


class ProvenanceError(RuntimeError):
    """이 악보로는 그 일을 할 수 없다."""


@dataclass(frozen=True)
class Term:
    key: str
    label: str
    commercial: bool           # 상업적 사용을 허용하는가
    noderiv: bool = False      # 2차적 저작물 금지 (= 반주를 붙일 수 없다)
    sharealike: bool = False   # 결과물도 같은 조건으로 풀어야 한다
    attribution: bool = False  # 출처를 표시해야 한다
    note: str = ''

    @property
    def sellable(self) -> bool:
        """이 악보로 만든 반주를 **팔 수 있는가.**

        `commercial` 과 다르다. `ND` 는 상업적 사용을 허용하면서도 2차적 저작물을
        금지하는데, 반주를 붙이는 것이 바로 그 2차적 저작물이다.
        """
        return self.commercial and not self.noderiv

    @property
    def caution(self) -> str:
        """팔 수는 있지만 조건이 붙는 경우, 그 조건."""
        if not self.sellable:
            return ''
        if self.sharealike:
            return ('동일조건변경허락 — 이 악보로 만든 반주도 같은 조건으로 '
                    '풀어야 합니다. 남이 그대로 재배포해도 막을 수 없습니다')
        if self.attribution:
            return '출처를 표시해야 합니다'
        return ''


def _t(key, label, commercial, **kw) -> Term:
    return Term(key=key, label=label, commercial=commercial, **kw)


# 키를 짧게 둔 이유: 카탈로그 JSON 에 그대로 들어가고 화면에도 그대로 나온다.
TERMS: Dict[str, Term] = {t.key: t for t in (
    # --- 우리 것 ---------------------------------------------------------
    _t('own', '자사 제작', True,
       note='우리가 직접 만든 악보. 악보까지 같이 팔 수 있다'),
    _t('omr', 'PDF 인식 결과', True,
       note='만료된 원판을 우리가 인식한 것. 인식 결과물은 인식한 쪽 것이라 '
            '남의 입력본이 끼지 않는다'),

    # --- 자유롭게 쓸 수 있는 것 -------------------------------------------
    _t('cc0', 'CC0 (권리 포기)', True,
       note='입력한 사람이 권리를 포기했다. 가장 깨끗하다'),
    _t('pd', '퍼블릭도메인 입력본', True,
       note='입력본까지 퍼블릭도메인으로 공표된 것'),
    _t('cc-by', 'CC BY (저작자표시)', True, attribution=True),
    _t('cc-by-sa', 'CC BY-SA (저작자표시·동일조건)', True,
       attribution=True, sharealike=True),

    # --- 팔 수 없는 것 ----------------------------------------------------
    _t('cc-by-nd', 'CC BY-ND (변경금지)', True, noderiv=True, attribution=True,
       note='상업적 사용은 되지만 2차적 저작물이 금지다. 반주를 붙이는 것이 '
            '2차적 저작물이라 우리한테는 막힌 것이다'),
    _t('cc-by-nc', 'CC BY-NC (비영리)', False, attribution=True),
    _t('cc-by-nc-sa', 'CC BY-NC-SA (비영리·동일조건)', False,
       attribution=True, sharealike=True,
       note='kernScores(craigsapp) 저장소들이 이것이다'),
    _t('cc-by-nc-nd', 'CC BY-NC-ND (비영리·변경금지)', False,
       noderiv=True, attribution=True),

    # --- 모르는 것 --------------------------------------------------------
    _t('unknown', '출처 확인 안 됨', False,
       note='기본값. 모르는 것은 못 판다 — 모르는 쪽이 위험하다'),
)}

DEFAULT = 'unknown'


def term(key: Optional[str]) -> Term:
    """라이선스 키를 해석한다. 빈 값·모르는 값은 전부 `unknown` 으로 본다.

    모르는 키에 예외를 던지지 않는 것은 일부러다. 옛 카탈로그 파일이나 사람이
    손으로 고친 값이 들어와도 **안전한 쪽으로** 떨어져야 한다.
    """
    return TERMS.get((key or '').strip().lower() or DEFAULT, TERMS[DEFAULT])


def sellable(key: Optional[str]) -> bool:
    return term(key).sellable


def known(key: Optional[str]) -> bool:
    """우리가 아는 키인가. CLI 에서 오타를 잡는 데 쓴다."""
    return (key or '').strip().lower() in TERMS


def check(key: Optional[str], what: str = '이 악보') -> None:
    """팔 수 있는 악보인가. 아니면 왜 안 되는지 말하고 막는다."""
    t = term(key)
    if t.sellable:
        return
    if t.key == DEFAULT:
        raise ProvenanceError(
            f'{what} 는 입력본 출처가 확인되지 않았습니다. '
            '어디서 받은 악보인지 정하고 넣어 주세요 '
            f'(가능: {", ".join(sorted(TERMS))}).')
    why = '2차적 저작물이 금지라 반주를 붙일 수 없습니다' if t.noderiv \
        else '비영리 조건이라 판매용에 넣을 수 없습니다'
    raise ProvenanceError(f'{what} 의 입력본은 {t.label} 입니다 — {why}.')


def split(songs: Iterable, key=lambda s: getattr(s, 'score_license', '')
          ) -> Tuple[List, List]:
    """팔 수 있는 것과 아닌 것으로 가른다."""
    ok: List = []
    no: List = []
    for s in songs:
        (ok if sellable(key(s)) else no).append(s)
    return ok, no


def summary(songs: Sequence, key=lambda s: getattr(s, 'score_license', '')
            ) -> List[dict]:
    """출처별로 몇 곡인지. 카탈로그 화면과 꾸러미 보고에 쓴다."""
    counts: Dict[str, int] = {}
    for s in songs:
        k = term(key(s)).key
        counts[k] = counts.get(k, 0) + 1
    out = [{'key': k, 'label': TERMS[k].label, 'count': n,
            'sellable': TERMS[k].sellable, 'caution': TERMS[k].caution}
           for k, n in counts.items()]
    # 팔 수 있는 것 먼저, 그 안에서는 많은 것 먼저
    out.sort(key=lambda r: (not r['sellable'], -r['count'], r['key']))
    return out
