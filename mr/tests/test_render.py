# -*- coding: utf-8 -*-
"""모듈 ④ 렌더러. fluidsynth/ffmpeg 가 없으면 건너뛴다."""
import os
import shutil
import subprocess

import pytest
from mido import MidiFile

from conftest import score
from piano_mr import arranger, orchestration as orch, render, score_loader

needs_audio = pytest.mark.skipif(
    shutil.which('fluidsynth') is None or shutil.which('ffmpeg') is None,
    reason='fluidsynth/ffmpeg 가 없습니다 (apt-get install fluidsynth ffmpeg)')


def probe(path, field):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', f'format={field}',
                          '-of', 'csv=p=0', path], capture_output=True, text=True)
    return out.stdout.strip()


# --- MIDI 병합 ---------------------------------------------------------------

def test_combine_unifies_ticks_per_beat(tmp_path):
    """music21 과 mido 의 기본 tpb 가 달라서, 맞추지 않으면 반주가 2배 빨라진다."""
    ls = score_loader.load(score('p01_block_c'))
    arr, _ls, _segs = arranger.arrange(ls, bpm=96)
    acc = str(tmp_path / 'a.mid')
    arr.save(acc)
    piano = render.piano_midi(ls, 96, str(tmp_path / 'p.mid'))
    assert MidiFile(piano).ticks_per_beat != 0
    out = render.combine(piano, acc, str(tmp_path / 'c.mid'))
    mf = MidiFile(out)
    assert mf.ticks_per_beat == render.TPB
    assert mf.length == pytest.approx(MidiFile(acc).length, abs=1.5)


def test_piano_is_pinned_to_channel_zero(tmp_path):
    ls = score_loader.load(score('p01_block_c'))
    p = render.piano_midi(ls, 96, str(tmp_path / 'p.mid'))
    chans = {m.channel for tr in MidiFile(p).tracks for m in tr if hasattr(m, 'channel')}
    assert chans == {orch.PIANO_CHANNEL}


def test_count_in_pushes_the_piano_back(tmp_path):
    ls = score_loader.load(score('p01_block_c'))
    arr, _ls, _segs = arranger.arrange(ls, bpm=96, count_in=1)
    acc = str(tmp_path / 'a.mid')
    arr.save(acc)
    piano = render.piano_midi(ls, 96, str(tmp_path / 'p.mid'))
    out = render.combine(piano, acc, str(tmp_path / 'c.mid'), lead_ql=arr.lead_ql)
    mf = MidiFile(out)
    firsts = {}
    for tr in mf.tracks:
        t = 0
        for m in tr:
            t += m.time
            if m.type == 'note_on':
                firsts.setdefault(m.channel, t / mf.ticks_per_beat)
                break
    assert firsts.get(orch.PIANO_CHANNEL) == pytest.approx(4.0, abs=0.1)
    assert firsts.get(9) == pytest.approx(0.0, abs=0.1)


def test_stems_split_by_channel_group(tmp_path):
    ls = score_loader.load(score('p07_minuet_g'))
    arr, _ls, _segs = arranger.arrange(ls, style='chamber', level='rich', bpm=108)
    acc = str(tmp_path / 'a.mid')
    arr.save(acc)
    piano = render.piano_midi(ls, 108, str(tmp_path / 'p.mid'))
    combined = render.combine(piano, acc, str(tmp_path / 'c.mid'))
    stems = render.split_stems(combined, str(tmp_path), 'x')
    assert set(stems) == {'piano', 'strings', 'bass'}
    for name, path in stems.items():
        chans = {m.channel for tr in MidiFile(path).tracks for m in tr
                 if m.type == 'note_on'}
        assert chans <= set(orch.STEMS[name]), (name, chans)


# --- 오디오 ------------------------------------------------------------------

@needs_audio
def test_practice_mp3_is_192k(tmp_path):
    res = render.render(score('p01_block_c'), style='strings', bpm=96,
                        tag='t', out_dir=str(tmp_path), formats=('practice',))
    path = res.files['practice']
    assert os.path.exists(path)
    assert 180_000 < int(probe(path, 'bit_rate')) < 205_000


@needs_audio
def test_three_output_formats(tmp_path):
    """지시서 모듈 ④: 연습용 192k / 무대용 320k / 영상편집용 WAV + 스템."""
    res = render.render(score('p01_block_c'), style='chamber', bpm=96, tag='t',
                        out_dir=str(tmp_path),
                        formats=('practice', 'stage', 'master'), stems=True)
    assert set(res.files) == {'practice', 'stage', 'master'}
    assert int(probe(res.files['stage'], 'bit_rate')) > 300_000
    assert res.files['master'].endswith('.wav')
    assert set(res.stems) == {'piano', 'strings', 'bass'}
    for p in list(res.files.values()) + list(res.stems.values()):
        assert os.path.getsize(p) > 1000


@needs_audio
def test_render_is_under_five_seconds(tmp_path):
    import time
    t0 = time.time()
    render.render(score('p07_minuet_g'), style='chamber', bpm=108, tag='t',
                  out_dir=str(tmp_path), formats=('practice',))
    assert time.time() - t0 < 5.0


@needs_audio
def test_full_matches_the_prototype_signature(tmp_path):
    info = render.full(score('p01_block_c'), 'strings', 96, 'proto',
                       out_dir=str(tmp_path))
    assert info['file'].endswith('.mp3') and os.path.exists(info['file'])
    assert info['key'] == 'C major'


def test_midi_output_needs_no_audio_tools(tmp_path):
    out = str(tmp_path / 'x.mid')
    res = render.render(score('p01_block_c'), bpm=96, tag='t',
                        out_dir=str(tmp_path), outfile=out)
    assert res.files['midi'] == out and os.path.exists(out)


def test_unknown_format(tmp_path):
    with pytest.raises(ValueError, match='출력 형식'):
        render.render(score('p01_block_c'), tag='t', out_dir=str(tmp_path),
                      formats=('없는형식',))


def test_missing_soundfont_says_how_to_fix(monkeypatch):
    monkeypatch.setenv('MR_SOUNDFONT', '/없는/경로.sf2')
    monkeypatch.setattr(render, 'DEFAULT_SF2', '/없는/경로2.sf2')
    monkeypatch.setattr(render, 'SF2_FALLBACKS', ())
    with pytest.raises(render.ToolMissingError, match='SoundFont'):
        render.soundfont()
