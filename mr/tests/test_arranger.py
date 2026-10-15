# -*- coding: utf-8 -*-
"""반주 생성 — 지시서 12장의 "리팩터링 시 지킬 것" 중 보이싱 규칙."""
import pytest
from mido import MidiFile

from conftest import score
from piano_mr import arranger, harmony, orchestration as orch, score_loader


# --- 보이싱: 패드는 멜로디 최저음 아래 --------------------------------------

@pytest.mark.parametrize('ceiling', [60, 67, 72, 79, 84])
@pytest.mark.parametrize('root,qual', [(0, 'M'), (9, 'm'), (11, 'd'), (7, '7')])
def test_pad_stays_under_the_melody(root, qual, ceiling):
    tri = arranger.voice(root, qual, ceiling)
    assert len(tri) == 3
    assert min(tri) >= arranger.PAD_FLOOR
    assert max(tri) < ceiling or ceiling - 1 <= arranger.PAD_FLOOR + 12
    assert tri[0] % 12 == root


def test_voice_never_loops_forever_on_a_low_ceiling():
    assert arranger.voice(0, 'M', 36)          # 천장이 패드 바닥과 같아도 끝난다


def test_voice_quality_intervals():
    assert arranger.voice(0, 'M', 84)[1] - arranger.voice(0, 'M', 84)[0] == 4
    assert arranger.voice(0, 'm', 84)[1] - arranger.voice(0, 'm', 84)[0] == 3
    assert arranger.voice(0, 'd', 84)[2] - arranger.voice(0, 'd', 84)[0] == 6


# --- 연출 곡선 ---------------------------------------------------------------

def test_build_curve_is_four_quarters():
    """지시서 5장: 곡을 4등분해서 off -> simple -> normal -> rich."""
    plan = arranger.stage_plan(list(range(1, 17)), 'build', 'rich')
    assert [plan[b] for b in range(1, 17)] == (
        ['off'] * 4 + ['simple'] * 4 + ['normal'] * 4 + ['rich'] * 4)


def test_build_curve_respects_the_level_ceiling():
    plan = arranger.stage_plan(list(range(1, 9)), 'build', 'normal')
    assert set(plan.values()) <= {'off', 'simple', 'normal'}
    assert plan[1] == 'off' and plan[8] == 'normal'


def test_flat_curve_is_constant():
    plan = arranger.stage_plan([1, 2, 3], 'flat', 'simple')
    assert set(plan.values()) == {'simple'}


def test_unknown_curve():
    with pytest.raises(ValueError, match='연출 곡선'):
        arranger.stage_plan([1], '없는곡선')


# --- 반주 MIDI ---------------------------------------------------------------

def test_accompaniment_midi_is_tiny(tmp_path):
    """지시서 2.4/6장: 카탈로그에는 오디오가 아니라 이 파일(2.4 KB)을 저장한다."""
    arr, _ls, _segs = arranger.arrange(score('p01_block_c'), style='chamber', bpm=96)
    out = tmp_path / 'a.mid'
    arr.save(str(out))
    assert out.stat().st_size < 10_000


def test_roles_land_on_their_own_channels(tmp_path):
    arr, _ls, _segs = arranger.arrange(score('p07_minuet_g'), style='chamber',
                                       level='rich', bpm=108)
    out = tmp_path / 'a.mid'
    arr.save(str(out))
    mf = MidiFile(str(out))
    seen = {}
    for tr in mf.tracks:
        names = [m.name for m in tr if m.type == 'track_name']
        chans = {m.channel for m in tr if m.type == 'note_on'}
        if names and chans:
            seen[names[0]] = chans
    for role, chans in seen.items():
        if role in orch.CHANNEL:
            assert chans == {orch.CHANNEL[role]}, role
    assert 'pad' in seen and 'bass' in seen


def test_build_curve_delays_the_entry(tmp_path):
    """감동은 반주가 들어오는 순간에서 나온다 — 처음부터 깔면 안 된다."""
    arr, ls, _segs = arranger.arrange(score('p01_block_c'), bpm=96, curve='build')
    out = tmp_path / 'a.mid'
    arr.save(str(out))
    mf = MidiFile(str(out))
    firsts = []
    for tr in mf.tracks:
        t = 0
        for m in tr:
            t += m.time
            if m.type == 'note_on':
                firsts.append(t / mf.ticks_per_beat)
                break
    assert firsts and min(firsts) > 0


def test_count_in_shifts_everything(tmp_path):
    arr, ls, _segs = arranger.arrange(score('p01_block_c'), bpm=96, count_in=2)
    assert arr.lead_ql == pytest.approx(8.0)          # 4/4 두 마디
    out = tmp_path / 'a.mid'
    arr.save(str(out))
    mf = MidiFile(str(out))
    clicks = [tr for tr in mf.tracks
              if any(m.type == 'note_on' and m.channel == 9 for m in tr)]
    assert clicks


def test_corrected_harmony_is_used(tmp_path):
    """화성 확인 화면에서 고친 값이 그대로 반주에 반영되어야 한다."""
    ls = score_loader.load(score('p01_block_c'))
    segs = harmony.analyze_segments(ls)
    for s in segs:
        s['root'], s['qual'], s['label'] = 5, 'M', 'F'
    arr, _ls, used = arranger.arrange(ls, harmony_override=segs, bpm=96)
    assert all(s['label'] == 'F' for s in used)
    assert arr.segments == len(segs)


def test_run_matches_the_prototype_signature(tmp_path):
    out = tmp_path / 'a.mid'
    info = arranger.run(score('p01_block_c'), str(out), 'strings', 'build', 96.0)
    assert out.exists()
    assert info['key'] == 'C major' and info['time'] == '4/4'
    assert 'pad' in info['instruments']
