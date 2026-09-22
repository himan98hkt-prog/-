# -*- coding: utf-8 -*-
"""모듈 ④ 렌더러 — 피아노 원곡 MIDI + 반주 MIDI 를 합쳐 음원으로.

전 과정이 로컬 연산이다. **API 호출 0회** (지시서 2.4/8.1).

출력 3종 (지시서 모듈 ④):
  * `연습용`     MP3 192k  — 카톡으로 보낼 수 있는 크기
  * `무대용`     MP3 320k
  * `영상편집용` WAV + 파트별 스템(피아노/현악/저음)

저장 원칙(6장): 오디오는 보관하지 않는다. 카탈로그에는 반주 MIDI(2.4 KB)만 남기고
필요할 때 다시 렌더한다.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Dict, Optional, Sequence

from mido import MidiFile, MidiTrack
from music21 import stream, tempo

from . import arranger, orchestration as orch, score_loader

TPB = arranger.TPB
DEFAULT_SF2 = '/usr/share/sounds/sf2/FluidR3_GM.sf2'
SF2_FALLBACKS = ('/usr/share/sounds/sf2/default-GM.sf2',
                 '/usr/share/sounds/sf2/TimGM6mb.sf2',
                 '/usr/share/soundfonts/default.sf2')
TAIL_SECONDS = 2.5
FADE_SECONDS = 1.5
LOUDNORM = 'loudnorm=I=-16:TP=-1.5'

FORMATS = {
    'practice': {'ext': '.mp3', 'bitrate': '192k', 'label': '연습용'},
    'stage':    {'ext': '.mp3', 'bitrate': '320k', 'label': '무대용'},
    'master':   {'ext': '.wav', 'bitrate': None,   'label': '영상편집용'},
}


class ToolMissingError(RuntimeError):
    pass


@dataclass
class RenderResult:
    files: Dict[str, str] = field(default_factory=dict)
    stems: Dict[str, str] = field(default_factory=dict)
    accomp_mid: str = ''
    combined_mid: str = ''
    info: dict = field(default_factory=dict)

    def first(self) -> Optional[str]:
        for v in self.files.values():
            return v
        return None


# --------------------------------------------------------------------------
# 외부 도구
# --------------------------------------------------------------------------

def soundfont() -> str:
    sf = os.environ.get('MR_SOUNDFONT')
    for cand in ([sf] if sf else []) + [DEFAULT_SF2] + list(SF2_FALLBACKS):
        if cand and os.path.exists(cand):
            return cand
    raise ToolMissingError(
        'SoundFont(.sf2)를 찾지 못했습니다. '
        '`apt-get install fluid-soundfont-gm` 로 설치하거나 '
        'MR_SOUNDFONT 환경변수로 경로를 지정하세요.')


def require_tools(*names: str) -> None:
    missing = [n for n in names if shutil.which(n) is None]
    if missing:
        raise ToolMissingError(
            f"{', '.join(missing)} 가 설치되어 있지 않습니다. "
            '`apt-get install fluidsynth ffmpeg` 로 설치하세요.')


def _run(cmd: Sequence[str]) -> None:
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        tail = p.stderr.decode('utf-8', 'replace').strip().splitlines()[-6:]
        raise RuntimeError(f"{cmd[0]} 실패:\n" + '\n'.join(tail))


# --------------------------------------------------------------------------
# MIDI 만들기 / 합치기
# --------------------------------------------------------------------------

def piano_midi(ls: score_loader.LoadedScore, bpm: float, out: str) -> str:
    """원곡 피아노를 채널 0 고정 MIDI 로."""
    s = stream.Score()
    for p in ls.score.parts:
        s.insert(0, p)
    if not s.parts:
        s.insert(0, ls.score)
    s.insert(0, tempo.MetronomeMark(number=bpm))
    s.write('midi', fp=out)
    mf = MidiFile(out)
    for tr in mf.tracks:
        for m in tr:
            if m.type in ('note_on', 'note_off', 'program_change', 'control_change',
                          'pitchwheel', 'aftertouch', 'polytouch'):
                m.channel = orch.PIANO_CHANNEL
    mf.save(out)
    return out


def combine(piano: str, accomp: str, out: str, tpb: int = TPB,
            lead_ql: float = 0.0) -> str:
    """두 MIDI 를 하나로. `ticks_per_beat` 를 통일해서 병합할 것 (지시서 모듈 ④).

    music21 과 mido 의 기본 tpb 가 달라서, 맞추지 않으면 반주가 2배 빨라진다.
    """
    a = MidiFile(accomp)
    p = MidiFile(piano)
    mf = MidiFile(ticks_per_beat=tpb)

    def rescale(src_mf: MidiFile, keep_meta: bool, shift: int = 0) -> None:
        f = tpb / src_mf.ticks_per_beat
        for tr in src_mf.tracks:
            nt = MidiTrack()
            shifted = shift
            for m in tr:
                if m.is_meta and m.type in ('set_tempo', 'time_signature') and not keep_meta:
                    continue
                t = int(round(m.time * f)) + shifted
                shifted = 0
                nt.append(m.copy(time=t))
            if any(x.type == 'note_on' for x in nt) or keep_meta:
                mf.tracks.append(nt)

    rescale(a, True)                                   # 반주 파일의 템포/박자 메타를 사용
    rescale(p, False, int(round(lead_ql * tpb)))       # 카운트인만큼 피아노를 뒤로 민다
    mf.save(out)
    return out


def split_stems(combined: str, out_dir: str, tag: str) -> Dict[str, str]:
    """채널 묶음별로 MIDI 를 쪼갠다 — 발표회 영상 편집용."""
    src = MidiFile(combined)
    made: Dict[str, str] = {}
    for name, channels in orch.STEMS.items():
        mf = MidiFile(ticks_per_beat=src.ticks_per_beat)
        chans = set(channels)
        kept = False
        for i, tr in enumerate(src.tracks):
            has_note = any(m.type == 'note_on' for m in tr)
            if not has_note:
                mf.tracks.append(tr)                   # 메타(템포·박자) 트랙은 항상
                continue
            if any(getattr(m, 'channel', None) in chans for m in tr if not m.is_meta):
                mf.tracks.append(tr)
                kept = True
        if not kept:
            continue
        path = os.path.join(out_dir, f'{tag}_{name}.mid')
        mf.save(path)
        made[name] = path
    return made


# --------------------------------------------------------------------------
# 오디오
# --------------------------------------------------------------------------

def midi_to_wav(mid: str, wav: str, gain: float = 0.95) -> str:
    require_tools('fluidsynth')
    _run(['fluidsynth', '-ni', '-g', str(gain), '-F', wav, '-r', '44100',
          soundfont(), mid])
    return wav


def encode(wav: str, out: str, seconds: float, bitrate: Optional[str] = '192k',
           fade: bool = True) -> str:
    require_tools('ffmpeg')
    af = [LOUDNORM]
    if fade and seconds > FADE_SECONDS:
        af.append(f'afade=t=out:st={seconds - FADE_SECONDS:.2f}:d={FADE_SECONDS}')
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-i', wav,
           '-t', f'{seconds:.2f}', '-af', ','.join(af)]
    if bitrate:
        cmd += ['-b:a', bitrate]
    cmd.append(out)
    _run(cmd)
    return out


def midi_seconds(mid: str, tail: float = TAIL_SECONDS) -> float:
    return MidiFile(mid).length + tail


# --------------------------------------------------------------------------
# 전 과정
# --------------------------------------------------------------------------

def render(src, style: str = 'strings', level: str = 'rich', bpm: float = 120.0,
           curve: str = 'build', tag: str = 'out', out_dir: str = '.',
           formats: Sequence[str] = ('practice',), stems: bool = False,
           keep_midi: bool = False, count_in: int = 0, transpose: int = 0,
           harmony_override=None, outfile: Optional[str] = None) -> RenderResult:
    """악보 -> 음원. 반환값에 만들어진 파일 경로가 다 들어 있다."""
    for f in formats:
        if f not in FORMATS:
            raise ValueError(f"모르는 출력 형식입니다: {f} (가능: {', '.join(FORMATS)})")
    os.makedirs(out_dir, exist_ok=True)

    arr, ls, segs = arranger.arrange(src, style=style, level=level, curve=curve,
                                     bpm=bpm, count_in=count_in, transpose=transpose,
                                     harmony_override=harmony_override)

    work = tempfile.mkdtemp(prefix='mr_')
    res = RenderResult(info=arr.info())
    res.info['segments_detail'] = len(segs)
    try:
        acc_mid = os.path.join(out_dir if keep_midi else work, f'{tag}_accomp.mid')
        arr.save(acc_mid)
        res.accomp_mid = acc_mid

        pm = os.path.join(work, f'{tag}_piano.mid')
        piano_midi(ls, bpm, pm)

        cm = os.path.join(out_dir if keep_midi else work, f'{tag}.mid')
        combine(pm, acc_mid, cm, lead_ql=arr.lead_ql)
        res.combined_mid = cm

        if outfile and os.path.splitext(outfile)[1].lower() in ('.mid', '.midi'):
            os.makedirs(os.path.dirname(os.path.abspath(outfile)) or '.', exist_ok=True)
            shutil.copyfile(cm, outfile)
            res.files['midi'] = outfile
            res.info['files'] = dict(res.files)
            return res

        seconds = midi_seconds(cm)
        wav = os.path.join(work, f'{tag}.wav')
        midi_to_wav(cm, wav)

        for i, f in enumerate(formats):
            spec = FORMATS[f]
            if outfile and i == 0:
                path = outfile
                os.makedirs(os.path.dirname(os.path.abspath(path)) or '.', exist_ok=True)
            else:
                path = os.path.join(out_dir, f'{tag}_{f}{spec["ext"]}')
            encode(wav, path, seconds, spec['bitrate'])
            res.files[f] = path

        if stems:
            for name, smid in split_stems(cm, work, tag).items():
                swav = os.path.join(work, f'{tag}_{name}.wav')
                midi_to_wav(smid, swav)
                spath = os.path.join(out_dir, f'{tag}_stem_{name}.wav')
                encode(swav, spath, seconds, None, fade=False)
                res.stems[name] = spath
        res.info['files'] = dict(res.files)
        res.info['stems'] = dict(res.stems)
        return res
    finally:
        shutil.rmtree(work, ignore_errors=True)


def full(src, style: str = 'strings', bpm: float = 120.0, tag: str = 'out',
         curve: str = 'build', level: str = 'rich', out_dir: str = '.') -> dict:
    """프로토타입 `render.full` 호환 서명. mp3 경로를 info['file'] 로 돌려준다."""
    res = render(src, style=style, level=level, bpm=bpm, curve=curve, tag=tag,
                 out_dir=out_dir, formats=('practice',))
    info = dict(res.info)
    info['file'] = res.files.get('practice')
    return info
