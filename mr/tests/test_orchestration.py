# -*- coding: utf-8 -*-
"""모듈 ③ 편성 엔진."""
import pytest

from piano_mr import orchestration as orch


def test_seven_styles_exist():
    assert len(orch.STYLES) == 7
    assert set(orch.STYLES) == {'strings', 'chamber', 'orchestra', 'fairytale',
                                'warm', 'march', 'pop'}


def test_default_style_is_the_safest_one():
    assert orch.DEFAULT_STYLE == 'strings'


@pytest.mark.parametrize('name', sorted(orch.STYLES))
def test_pad_and_bass_are_always_on(name):
    """pad 는 소리의 70%, bass 는 무게감. 어떤 레벨에서도 빠지지 않는다."""
    for level in orch.LEVELS:
        roles = orch.resolve(name, level)
        assert 'pad' in roles and 'bass' in roles


@pytest.mark.parametrize('level,expected', [
    ('simple', {'pad', 'bass'}),
    ('normal', {'pad', 'bass', 'color'}),
])
def test_levels_gate_roles(level, expected):
    assert set(orch.resolve('chamber', level)) == expected


def test_rich_adds_counter_and_accent():
    roles = set(orch.resolve('chamber', 'rich'))
    assert {'counter', 'accent'} <= roles


def test_percussion_only_in_march_and_pop_at_rich():
    """지시서 1장 금지: 드럼킷을 기본값으로 쓰지 말 것."""
    for name in orch.STYLES:
        for level in orch.LEVELS:
            has = 'perc' in orch.resolve(name, level)
            assert has == (name in ('march', 'pop') and level == 'rich'), (name, level)


def test_channels_do_not_collide():
    chans = list(orch.CHANNEL.values())
    assert len(chans) == len(set(chans))
    assert orch.CHANNEL['perc'] == 9          # GM 드럼 고정
    assert orch.PIANO_CHANNEL == 0            # 피아노 원곡 전용
    assert 9 not in [v for k, v in orch.CHANNEL.items() if k != 'perc']
    assert 0 not in orch.CHANNEL.values()


def test_stems_cover_every_channel():
    covered = {c for chans in orch.STEMS.values() for c in chans}
    assert covered == set(orch.CHANNEL.values()) | {orch.PIANO_CHANNEL}


def test_unknown_style_and_level():
    with pytest.raises(orch.UnknownStyleError):
        orch.resolve('없는스타일')
    with pytest.raises(orch.UnknownLevelError):
        orch.resolve('strings', '없는레벨')


def test_describe_is_human_readable():
    text = orch.describe('chamber', 'normal')
    assert '실내악' in text and '보통' in text


def test_list_styles_has_labels_and_reasons():
    rows = orch.list_styles()
    assert len(rows) == 7
    assert all(len(r) == 3 and all(r) for r in rows)
