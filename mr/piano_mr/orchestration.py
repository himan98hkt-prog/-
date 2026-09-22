# -*- coding: utf-8 -*-
"""모듈 ③ 편성 엔진 — 역할(role)에 악기와 세기를 매핑한다.

설계 제1원칙(지시서 1장): "따라오는 반주"가 아니라 **"용서하는 반주"**.
아이가 빨라지거나 멈춰도 티가 안 나야 한다. 그래서

  * `pad`(지속 화음)가 항상 켜져 있고 소리의 70% 를 담당한다.
  * 드럼킷·스타카토 현악·빠른 리듬 패턴은 기본값이 아니다.
    `perc` 는 `march`/`pop` 스타일 + `rich` 레벨에서만 켜진다.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

# General MIDI 음색표
GM = {
    'strings_soft': 49, 'strings': 48, 'violin': 40, 'viola': 41, 'cello': 42,
    'contrabass': 43, 'pizz': 45, 'harp': 46, 'timpani': 47, 'choir': 52,
    'flute': 73, 'oboe': 68, 'clarinet': 71, 'bassoon': 70, 'horn': 60,
    'trumpet': 56, 'trombone': 57, 'celesta': 8, 'glocken': 9, 'vibes': 11,
    'music_box': 10, 'epiano': 4, 'jazz_bass': 32, 'guitar_nylon': 24,
    'organ': 19, 'accordion': 21, 'warm_pad': 89,
}

GM_LABEL = {
    'strings_soft': '현악 앙상블', 'strings': '현악 합주', 'violin': '바이올린',
    'viola': '비올라', 'cello': '첼로', 'contrabass': '콘트라베이스',
    'pizz': '피치카토 현악', 'harp': '하프', 'timpani': '팀파니', 'choir': '합창',
    'flute': '플루트', 'oboe': '오보에', 'clarinet': '클라리넷', 'bassoon': '바순',
    'horn': '호른', 'trumpet': '트럼펫', 'trombone': '트롬본', 'celesta': '첼레스타',
    'glocken': '글로켄슈필', 'vibes': '비브라폰', 'music_box': '오르골',
    'epiano': '일렉트릭 피아노', 'jazz_bass': '어쿠스틱 베이스',
    'guitar_nylon': '나일론 기타', 'organ': '오르간', 'accordion': '아코디언',
    'warm_pad': '따뜻한 패드', 'drums': '리듬 악기',
}

# 역할(role):
#   pad     지속 화음 (반주의 뼈대) — 박자를 흐리게, 실수를 덮어줌. 항상 ON
#   bass    저음 근음. 항상 ON
#   color   아르페지오·분산화음 (프레이즈 시작점 장식)
#   counter 대선율 (반복부에서만)
#   accent  클라이맥스 포인트 (곡당 1~2회)
#   perc    리듬 악기 (march/pop + rich 에서만)
ROLES = ('pad', 'bass', 'color', 'counter', 'accent', 'perc')
ROLE_LABEL = {'pad': '지속 화음', 'bass': '저음', 'color': '분산화음',
              'counter': '대선율', 'accent': '강조', 'perc': '리듬'}

STYLES: Dict[str, dict] = {
    'strings': {
        'label': '현악 앙상블',
        'desc': '가장 안전한 기본값. 어떤 곡에도 무난하고 아이 실수를 가장 잘 덮어준다.',
        'pad': ('strings_soft', 52), 'bass': ('cello', 58),
        'color': ('harp', 46), 'counter': ('violin', 54), 'accent': None,
    },
    'chamber': {
        'label': '실내악',
        'desc': '현악 + 목관. 바흐·소나티네 등 고전 곡에 어울린다.',
        'pad': ('strings_soft', 50), 'bass': ('cello', 58),
        'color': ('harp', 44), 'counter': ('flute', 56), 'accent': ('oboe', 52),
    },
    'orchestra': {
        'label': '풀 오케스트라',
        'desc': '발표회 마지막 곡, 클라이맥스용. 소리가 가장 두껍다.',
        'pad': ('strings_soft', 56), 'bass': ('contrabass', 62),
        'color': ('harp', 48), 'counter': ('horn', 54), 'accent': ('timpani', 50),
    },
    'fairytale': {
        'label': '동화풍',
        'desc': '오르골·첼레스타·피치카토. 저학년 소품과 동요에 잘 맞는다.',
        'pad': ('warm_pad', 44), 'bass': ('pizz', 52),
        'color': ('celesta', 54), 'counter': ('music_box', 50), 'accent': ('glocken', 48),
    },
    'warm': {
        'label': '따뜻한 소편성',
        'desc': '합창 패드 + 첼로 + 하프. 조용하고 서정적인 곡 전용.',
        'pad': ('choir', 40), 'bass': ('cello', 54),
        'color': ('harp', 50), 'counter': ('flute', 50), 'accent': None,
    },
    'march': {
        'label': '행진곡풍',
        'desc': '금관 + 팀파니. 체르니·하농 등 리듬 연습곡을 재미있게 만든다.',
        'pad': ('horn', 48), 'bass': ('trombone', 56),
        'color': ('trumpet', 46), 'counter': ('clarinet', 50), 'accent': ('timpani', 54),
        'perc': True,
    },
    'pop': {
        'label': '팝·재즈풍',
        'desc': '일렉피아노 + 어쿠스틱 베이스. 지루한 연습곡에 생기를 준다.',
        'pad': ('epiano', 46), 'bass': ('jazz_bass', 58),
        'color': ('vibes', 46), 'counter': ('guitar_nylon', 48), 'accent': None,
        'perc': True,
    },
}

DEFAULT_STYLE = 'strings'

# 레벨: 어떤 역할까지 켤지. UI 문구는 "간단 / 보통 / 풍성"
LEVELS = {
    'simple': ['pad', 'bass'],
    'normal': ['pad', 'bass', 'color'],
    'rich':   ['pad', 'bass', 'color', 'counter', 'accent'],
}
LEVEL_LABEL = {'off': '반주 없음', 'simple': '간단', 'normal': '보통', 'rich': '풍성'}
LEVEL_ORDER = ['off', 'simple', 'normal', 'rich']

# 채널 배정 (9번은 GM 드럼 전용, 0번은 피아노 원곡 전용)
CHANNEL = {'pad': 1, 'bass': 2, 'color': 3, 'counter': 4, 'accent': 5, 'perc': 9}
PIANO_CHANNEL = 0

# 스템(파트별 분리) 묶음 — 지시서 모듈 ④ "영상편집용"
STEMS = {
    'piano': [PIANO_CHANNEL],
    'strings': [CHANNEL['pad'], CHANNEL['color'], CHANNEL['counter'], CHANNEL['accent']],
    'bass': [CHANNEL['bass'], CHANNEL['perc']],
}


class UnknownStyleError(ValueError):
    pass


class UnknownLevelError(ValueError):
    pass


def check_style(name: str) -> str:
    if name not in STYLES:
        raise UnknownStyleError(
            f"모르는 스타일입니다: {name!r} (가능: {', '.join(STYLES)})")
    return name


def check_level(name: str) -> str:
    if name not in LEVELS:
        raise UnknownLevelError(
            f"모르는 레벨입니다: {name!r} (가능: {', '.join(LEVELS)})")
    return name


def resolve(style_name: str, level: str = 'normal') -> Dict[str, dict]:
    """스타일+레벨 -> {역할: {program, velocity, channel, instrument}}"""
    st = STYLES[check_style(style_name)]
    out: Dict[str, dict] = {}
    for r in LEVELS[check_level(level)]:
        spec = st.get(r)
        if not spec:
            continue
        name, vel = spec
        out[r] = {'program': GM[name], 'velocity': vel,
                  'channel': CHANNEL[r], 'instrument': name,
                  'label': GM_LABEL.get(name, name)}
    # 리듬 악기는 march/pop + rich 에서만 (지시서 1장 금지 항목)
    if st.get('perc') and level == 'rich':
        out['perc'] = {'program': 0, 'velocity': 44, 'channel': CHANNEL['perc'],
                       'instrument': 'drums', 'label': GM_LABEL['drums']}
    return out


def list_styles() -> List[Tuple[str, str, str]]:
    return [(k, v['label'], v['desc']) for k, v in STYLES.items()]


def describe(style_name: str, level: str = 'normal') -> str:
    st = STYLES[check_style(style_name)]
    roles = resolve(style_name, level)
    parts = [f"{ROLE_LABEL[r]}={v['label']}" for r, v in roles.items()]
    return f"{st['label']}({style_name}) · {LEVEL_LABEL[level]} · " + ', '.join(parts)
