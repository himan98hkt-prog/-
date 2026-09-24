# -*- coding: utf-8 -*-
"""모듈 ② 화성 분석 — 지시서 12장이 "지키라"고 한 것들을 못 박는 테스트."""
import ast
import inspect

import pytest
from music21 import key as m21key

from conftest import score
from piano_mr import harmony, score_loader


# --- 지시서 12장: 점수식 상수는 실패를 거쳐 나온 값이다 ----------------------

def test_scoring_constants_unchanged():
    """이 값을 바꾸려면 먼저 bench.py 를 돌려 정확도가 떨어지지 않는지 볼 것."""
    assert harmony.W_MISS == 0.9
    assert harmony.W_BASS_ROOT == 0.30
    assert harmony.W_BASS_TONE == 0.10
    assert harmony.W_CONTINUITY == 0.06
    assert harmony.ONSET_BOOST == 1.5


def test_chordify_root_is_not_used():
    """`chordify().root()` 방식은 F장조를 A장조로 오판했다 (지시서 5장).

    주석으로 경고만 남기고 코드에서 다시 부르는 일이 없도록, 문자열이 아니라
    구문 트리에서 호출을 찾는다.
    """
    tree = ast.parse(inspect.getsource(harmony))
    called = {n.func.attr for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert 'chordify' not in called


def test_upper_voice_is_not_weighted():
    """상성부 가중은 오히려 해롭다 (지시서 5장). 가중은 베이스에만 붙는다."""
    w = {0: 1.0, 4: 1.0, 7: 1.0}
    cands = [(0, 'M'), (5, 'M')]
    lo = harmony.score_candidates(w, cands, None, 0)
    hi = harmony.score_candidates(w, cands, None, 7)
    assert lo[0][0] == (0, 'M')          # 베이스가 C면 C
    assert dict((c, s) for c, s, _ in lo) != dict((c, s) for c, s, _ in hi)


# --- 화음 이름 ---------------------------------------------------------------

@pytest.mark.parametrize('root,qual,text', [
    (0, 'M', 'C'), (9, 'm', 'Am'), (11, 'd', 'Bdim'), (7, '7', 'G7'),
    (10, 'M', 'Bb'), (6, 'd', 'F#dim'),
])
def test_label_roundtrip(root, qual, text):
    assert harmony.label(root, qual) == text
    assert harmony.parse_label(text) == (root, qual)


def test_label_of_nothing():
    assert harmony.label(None, None) == '—'
    assert harmony.parse_label('—') is None
    assert harmony.parse_label('없는화음') is None


@pytest.mark.parametrize('text,expected', [
    ('G#', (8, 'M')), ('Db', (1, 'M')), ('A#m', (10, 'm')), ('Cmaj', (0, 'M')),
])
def test_label_aliases(text, expected):
    assert harmony.parse_label(text) == expected


# --- 후보 화음 ---------------------------------------------------------------

def test_major_candidates_cover_diatonic_and_secondary():
    c = harmony.key_candidates(m21key.Key('C'))
    triads = {x for x in c if x[1] != '7'}
    for expected in [(0, 'M'), (2, 'm'), (4, 'm'), (5, 'M'), (7, 'M'), (9, 'm'), (11, 'd')]:
        assert expected in triads, harmony.label(*expected)
    for sec in [(2, 'M'), (9, 'M'), (4, 'M')]:        # V/V, V/ii, V/vi
        assert sec in triads, harmony.label(*sec)


def test_minor_candidates_include_harmonic_minor():
    c = harmony.key_candidates(m21key.Key('a'))
    triads = {x for x in c if x[1] != '7'}
    assert (9, 'm') in triads                 # i
    assert (4, 'M') in triads                 # V (화성단음계)
    assert (8, 'd') in triads                 # vii° = G#dim — 1단계 보강
    assert (0, 'M') in triads                 # III


def test_seventh_candidates_pair_every_major_triad():
    c = harmony.key_candidates(m21key.Key('C'))
    majors = {r for r, q in c if q == 'M'}
    sevenths = {r for r, q in c if q == '7'}
    assert majors == sevenths


def test_seventh_needs_both_tritone_notes():
    """b7 만 있고 3음이 없으면 7화음이 아니다 (유령 화음 방지)."""
    cands = [(7, 'M'), (7, '7')]
    with_third = {7: 1.0, 11: 1.0, 2: 1.0, 5: 1.0}       # G B D F
    got = harmony.score_candidates(with_third, cands, None, 7)
    assert got[0][0] == (7, '7')

    no_third = {7: 1.0, 2: 1.0, 5: 1.0}                  # G D F — B 없음
    got = harmony.score_candidates(no_third, cands, None, 7)
    assert all(q != '7' for (_r, q), _s, _p in got)


# --- 세그먼트 분할 -----------------------------------------------------------

@pytest.mark.parametrize('bar,beat,expected', [
    (4.0, 1.0, [1, 2, 4]),     # 4/4
    (3.0, 1.0, [1, 3]),        # 3/4 — 1.5박씩 잘리던 버그가 사라진 자리
    (3.0, 1.5, [1, 2]),        # 6/8 겹박자
    (2.0, 1.0, [1, 2]),        # 2/4
    (6.0, 1.5, [1, 2, 4]),     # 12/8
    (1.5, 1.5, [1]),           # 3/8
])
def test_split_options_are_beat_aligned(bar, beat, expected):
    assert harmony.split_options(bar, beat) == expected


@pytest.mark.parametrize('bar,beat,expected', [
    (4.0, 1.0, 2),    # 검증된 K.545 동작 — 2박마다
    (2.0, 1.0, 1),
    (3.0, 1.0, 1),    # 왈츠는 한 마디 한 화음에서 출발
    (3.0, 1.5, 2),    # 6/8 은 점4분음표 단위
])
def test_base_split_keeps_validated_behaviour(bar, beat, expected):
    assert harmony.base_split(bar, beat, 2.0) == expected


def test_three_four_never_splits_off_the_beat():
    """3박자 곡의 세그먼트 경계는 반드시 박 위에 있어야 한다."""
    ls = score_loader.load(score('p05_waltz_c'))
    for s in harmony.analyze_segments(ls):
        rel = s['off'] % 3.0
        assert abs(rel - round(rel)) < 1e-6, s


# --- 분석 결과 ---------------------------------------------------------------

def test_analyze_returns_confidence_and_alternatives():
    """지시서 10장: 2위 후보와 점수 차가 작은 구간을 노란색으로 강조한다."""
    ls = score_loader.load(score('p02_alberti_c'))
    segs = harmony.analyze_segments(ls)
    assert segs
    for s in segs:
        assert 0.0 <= s['conf'] <= 1.0
        assert isinstance(s['alts'], list)
        assert s['label'] == harmony.label(s['root'], s['qual'])
    assert isinstance(harmony.low_confidence(segs), list)


def test_silent_span_keeps_previous_chord():
    segs = [{'root': 0, 'qual': 'M'}, {'root': None, 'qual': None}]
    assert harmony.merge(segs) == [{'root': 0, 'qual': 'M'}]


def test_merge_joins_adjacent_identical_chords():
    segs = [{'root': 0, 'qual': 'M', 'off': 0.0, 'len': 2.0},
            {'root': 0, 'qual': 'M', 'off': 2.0, 'len': 2.0},
            {'root': 7, 'qual': 'M', 'off': 4.0, 'len': 2.0}]
    out = harmony.merge(segs)
    assert len(out) == 2
    assert out[0]['len'] == 4.0


def test_grid_renders_like_the_verification_screen():
    ls = score_loader.load(score('p01_block_c'))
    grid = harmony.to_grid(harmony.analyze_segments(ls))
    assert 'm1' in grid and '│' in grid


def test_key_can_be_overridden():
    ls = score_loader.load(score('p17_two_four_pickup'), key_name='C')
    assert str(ls.key) == 'C major'
    segs = harmony.analyze_segments(ls)
    assert segs[0]['label'] == 'G'
