# -*- coding: utf-8 -*-
"""회귀 테스트 (지시서 9장 1단계 · 11장 검증 기준).

    "엔진을 고칠 때마다 정확도가 떨어지지 않는지 확인"

엔진을 건드린 뒤 이 파일이 빨개지면, 고친 게 아니라 망가뜨린 것이다.
자세한 표는 `python bench.py`.
"""
import pytest

from conftest import FIXTURES
from piano_mr import evaluate

GATE = 0.95          # 지시서 11장: 화성 정확도 95% 이상
PER_SONG_GATE = 0.80
SPEED_GATE = 5.0     # 지시서 11장: 1곡 5초 이내


@pytest.fixture(scope='module')
def suite():
    return evaluate.run_suite(FIXTURES)


def test_suite_has_twenty_songs(suite):
    assert len(suite.results) == 20


def test_overall_accuracy_meets_the_gate(suite):
    assert suite.accuracy >= GATE, (
        f'화성 정확도 {suite.accuracy * 100:.1f}% < {GATE * 100:.0f}%\n'
        + suite.table())


def test_no_song_falls_apart(suite):
    bad = [r for r in suite.results if r.accuracy < PER_SONG_GATE]
    assert not bad, '\n'.join(f'{r.song_id} {r.accuracy * 100:.1f}%' for r in bad)


def test_key_detection_is_reliable(suite):
    """지시서 2.2: 조성은 통계적 성질이라 음표를 틀려도 잘 버틴다.

    다만 8마디짜리 성긴 악보에서는 흔들릴 수 있어서 100% 를 요구하지 않는다.
    흔들릴 때를 위해 `--key` 로 직접 지정할 수 있다.
    """
    assert suite.key_accuracy >= 0.90, [
        (r.song_id, r.key_expected, r.key_found) for r in suite.results if not r.key_ok]


def test_given_the_key_every_song_is_near_perfect():
    """조성만 확정되면 화성 분석 자체는 거의 틀리지 않는다."""
    given = evaluate.run_suite(FIXTURES, use_truth_key=True)
    assert given.key_accuracy == 1.0
    assert given.accuracy >= 0.97, given.table()


def test_seventh_chords_are_identified(suite):
    """G 와 G7 구분까지 포함한 정확도."""
    assert suite.accuracy_strict >= 0.90, suite.table()


def test_analysis_is_fast(suite):
    slow = [r for r in suite.results if r.seconds > SPEED_GATE]
    assert not slow, [(r.song_id, r.seconds) for r in slow]


def test_every_stage_of_the_fix_earned_its_place():
    """1단계 보강이 실제로 올린 것인지 매번 확인한다.

    되돌렸을 때 정확도가 안 떨어지는 '보강'은 보강이 아니라 군더더기다.
    `python3 bench.py --stages` 가 같은 표를 출력한다.
    """
    proto = evaluate.run_suite(FIXTURES, split_mode='legacy', sevenths=False)
    with_7 = evaluate.run_suite(FIXTURES, split_mode='legacy')
    fixed = evaluate.run_suite(FIXTURES, split_mode='fixed')
    adaptive = evaluate.run_suite(FIXTURES, split_mode='adaptive')
    assert proto.accuracy < with_7.accuracy < fixed.accuracy < adaptive.accuracy
    assert proto.bars_wrong > fixed.bars_wrong > adaptive.bars_wrong


def test_unknown_split_mode():
    import pytest as _pytest
    from piano_mr import harmony, score_loader
    from conftest import score
    ls = score_loader.load(score('p01_block_c'))
    with _pytest.raises(ValueError, match='분할 방식'):
        harmony.analyze_segments(ls, split_mode='없는방식')


@pytest.mark.parametrize('group,ids', [
    ('3박자', ['p05_waltz_c', 'p06_waltz_fast_d', 'p07_minuet_g',
               'p08_three_eight', 'p12_minor_dm_waltz']),
    ('단조', ['p10_minor_am', 'p11_minor_em_alberti', 'p12_minor_dm_waltz',
              'p13_minor_gm_dim', 'p14_minor_bm_fast']),
    ('화성이 잦은 곡', ['p06_waltz_fast_d', 'p14_minor_bm_fast',
                        'p15_fast_harmony_c', 'p16_fast_harmony_bb']),
])
def test_weak_cases_from_the_spec(suite, group, ids):
    """지시서 9장이 "현 프로토타입의 검증 범위 밖"이라고 지목한 세 가지."""
    rows = [r for r in suite.results if r.song_id in ids]
    assert len(rows) == len(ids)
    samples = sum(r.samples for r in rows)
    matched = sum(r.matched for r in rows)
    acc = matched / samples
    assert acc >= GATE, f'{group}: {acc * 100:.1f}%\n' + '\n'.join(r.row() for r in rows)
