# -*- coding: utf-8 -*-
"""모듈 ① 악보 파서."""
import pytest

from conftest import score
from piano_mr import score_loader


def test_loads_musicxml():
    ls = score_loader.load(score('p01_block_c'))
    assert len(ls.bars) == 8
    assert ls.time_signature.ratioString == '4/4'
    assert str(ls.key) == 'C major'
    assert ls.note_count > 0


def test_pickup_measure_keeps_its_real_length():
    """못갖춘마디를 한 마디 길이로 잡으면 분석 창이 옆 마디로 밀린다."""
    ls = score_loader.load(score('p17_two_four_pickup'))
    first = ls.bars[0]
    assert first.length == pytest.approx(1.0)
    assert first.bar_length == pytest.approx(2.0)
    assert ls.bars[1].length == pytest.approx(2.0)
    # 마디들이 빈틈없이 이어져야 한다
    for a, b in zip(ls.bars, ls.bars[1:]):
        assert a.offset + a.length == pytest.approx(b.offset)


def test_repeats_are_expanded():
    """지시서 모듈 ①: 반복기호는 전개한 뒤 분석한다."""
    plain = score_loader.load(score('p18_repeat_g'), expand_repeats=False)
    wide = score_loader.load(score('p18_repeat_g'), expand_repeats=True)
    assert wide.repeats_expanded
    assert len(wide.bars) > len(plain.bars)
    numbers = [b.number for b in wide.bars]
    assert len(numbers) != len(set(numbers))       # 같은 마디 번호가 두 번 나온다
    assert [b.idx for b in wide.bars] == list(range(1, len(wide.bars) + 1))


def test_melody_low_sits_above_the_bass():
    """패드를 놓을 천장이므로 왼손 저음이 섞이면 안 된다."""
    ls = score_loader.load(score('p02_alberti_c'))
    lows = [b.melody_low for b in ls.bars if b.melody_low]
    assert lows
    bass = min(p.midi for n in ls.score.recurse().notes for p in n.pitches)
    assert min(lows) > bass


def test_beat_length_follows_the_meter():
    assert score_loader.load(score('p05_waltz_c')).bars[0].beat_length == pytest.approx(1.0)
    assert score_loader.load(score('p09_six_eight')).bars[0].beat_length == pytest.approx(1.5)


def test_transpose():
    plain = score_loader.load(score('p01_block_c'))
    up = score_loader.load(score('p01_block_c'), transpose=2)
    assert str(plain.key) == 'C major'
    assert str(up.key) == 'D major'


def test_missing_file():
    with pytest.raises(FileNotFoundError):
        score_loader.load('없는파일.mxl')


def test_unsupported_suffix(tmp_path):
    p = tmp_path / 'x.pdf'
    p.write_bytes(b'%PDF-1.4')
    with pytest.raises(ValueError, match='지원하지 않는'):
        score_loader.load(str(p))


def test_legacy_signature_matches_the_spec():
    """지시서 5장 모듈 ① 서명 호환."""
    out = score_loader.load_legacy(score('p01_block_c'))
    assert len(out) == 7
    _sc, _k, _ts, segs, low, bar_len, total = out
    assert segs and isinstance(low, dict) and isinstance(bar_len, dict)
    assert total > 0
