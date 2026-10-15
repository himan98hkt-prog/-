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

# `raw: True` 는 **굽지 않고 그대로 내보내는** 형식이다. MIDI 가 그렇다 —
# 이미 만들어 둔 것을 복사하면 되고, 그래서 fluidsynth·ffmpeg 가 없어도 나간다.
# MIDI 하나만 달라고 하면 이 함수는 소리를 아예 안 만든다.
FORMATS = {
    'midi':     {'ext': '.mid', 'bitrate': None,   'label': 'MIDI', 'raw': True,
                 'desc': '악보 편집기·시퀀서에서 열어 고칠 수 있는 원본'},
    'practice': {'ext': '.mp3', 'bitrate': '192k', 'label': '연습용',
                 'desc': '카톡으로 보낼 수 있는 크기'},
    'stage':    {'ext': '.mp3', 'bitrate': '320k', 'label': '무대용',
                 'desc': '발표회장 스피커로 트는 것'},
    'master':   {'ext': '.wav', 'bitrate': None,   'label': '영상편집용',
                 'desc': '무압축. 영상에 붙일 때'},
}

# 무엇을 소리로 낼 것인가.
#
# **MR 은 반주만이다.** 피아노는 아이가 친다. 원곡 피아노가 음원에 들어 있으면
# 아이는 자기 연주와 녹음된 피아노를 겹쳐 치게 되고, 그건 MR 이 아니라 감상용
# 데모다. 그래서 기본값이 `mr` 이다.
MIXES = {
    'mr':    {'label': '반주만 (MR)', 'keep': 'accomp',
              'desc': '아이가 피아노를 친다. 기본값이자 실제로 파는 것'},
    'full':  {'label': '피아노 + 반주', 'keep': 'all',
              'desc': '화성이 맞는지 확인하거나, 아이에게 곡을 들려줄 때'},
    'piano': {'label': '피아노만', 'keep': 'piano',
              'desc': '원곡만. 반주 없이 곡을 확인할 때'},
}
DEFAULT_MIX = 'mr'


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


def filter_channels(src_path: str, out_path: str, keep) -> str:
    """채널을 골라 남긴 MIDI 를 만든다. 템포·박자 메타 트랙은 항상 남긴다.

    합쳐 둔 MIDI 에서 골라내기 때문에 어떤 mix 를 고르든 **타이밍이 완전히 같다.**
    반주만 따로 만들고 피아노만 따로 만들면 둘이 어긋날 여지가 생긴다.
    """
    src = MidiFile(src_path)
    mf = MidiFile(ticks_per_beat=src.ticks_per_beat)
    keep = None if keep is None else set(keep)
    for tr in src.tracks:
        if not any(m.type == 'note_on' for m in tr):
            mf.tracks.append(tr)                 # 메타(템포·박자·끝) 트랙
            continue
        if keep is None:
            mf.tracks.append(tr)
            continue
        chans = {getattr(m, 'channel', None) for m in tr if not m.is_meta}
        if chans & keep:
            mf.tracks.append(tr)
    mf.save(out_path)
    return out_path


def mix_channels(mix: str):
    """mix 이름 -> 남길 채널 집합 (None 이면 전부)."""
    if mix == 'full':
        return None
    if mix == 'piano':
        return {orch.PIANO_CHANNEL}
    if mix == 'mr':
        return set(orch.CHANNEL.values())        # 피아노(0번)만 뺀다
    raise ValueError(f"모르는 mix 입니다: {mix} (가능: {', '.join(MIXES)})")


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

def render(src, style: str = 'strings', level: str = arranger.DEFAULT_LEVEL,
           bpm: float = 120.0, curve: str = arranger.DEFAULT_CURVE,
           tag: str = 'out', out_dir: str = '.',
           formats: Sequence[str] = ('practice',), stems: bool = False,
           keep_midi: bool = False, count_in: int = 0, transpose: int = 0,
           harmony_override=None, outfile: Optional[str] = None,
           mix: str = DEFAULT_MIX) -> RenderResult:
    """악보 -> 음원. 기본값은 **반주만(MR)** 이다 — 피아노는 아이가 친다."""
    if mix not in MIXES:
        raise ValueError(f"모르는 mix 입니다: {mix} (가능: {', '.join(MIXES)})")
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
        res.info['mix'] = mix

        # 길이는 **항상 합쳐 둔 MIDI 기준**이다. 반주만 낼 때도 곡 전체 길이만큼
        # 나와야 한다 — 마지막 마디의 반주가 먼저 끝나도 음원이 잘리면 안 된다.
        seconds = midi_seconds(cm)

        play = cm
        if mix != 'full':
            # --keep-midi 로 남길 때도 **요청한 mix 그대로** 남아야 한다.
            # 합쳐 둔 MIDI 를 주면 "MR 을 달라"고 했는데 피아노가 든 파일이 나온다.
            dest = out_dir if keep_midi else work
            play = filter_channels(cm, os.path.join(dest, f'{tag}_{mix}.mid'),
                                   mix_channels(mix))
            if keep_midi:
                res.info['mix_midi'] = play

        if outfile and os.path.splitext(outfile)[1].lower() in ('.mid', '.midi'):
            os.makedirs(os.path.dirname(os.path.abspath(outfile)) or '.', exist_ok=True)
            shutil.copyfile(play, outfile)
            res.files['midi'] = outfile
            res.info['files'] = dict(res.files)
            return res

        # 소리를 만들 일이 있을 때만 만든다. MIDI 만 달라고 했으면 fluidsynth 도
        # ffmpeg 도 안 부른다 — 그 둘이 안 깔린 기계에서도 MIDI 는 나가야 한다.
        wav = ''
        if stems or any(not FORMATS[f].get('raw') for f in formats):
            wav = os.path.join(work, f'{tag}.wav')
            midi_to_wav(play, wav)

        for i, f in enumerate(formats):
            spec = FORMATS[f]
            if outfile and i == 0:
                path = outfile
                os.makedirs(os.path.dirname(os.path.abspath(path)) or '.', exist_ok=True)
            else:
                path = os.path.join(out_dir, f'{tag}_{f}{spec["ext"]}')
            if spec.get('raw'):
                # 이미 `mix` 가 반영된 MIDI 다. 「반주만」을 달라고 했으면
                # 피아노가 빠진 그 파일이 그대로 나간다.
                shutil.copyfile(play, path)
            else:
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
         curve: str = 'build', level: str = 'rich', out_dir: str = '.',
         mix: str = 'full') -> dict:
    """프로토타입 `render.full` 호환 서명 — 이름 그대로 피아노+반주를 낸다.

    새로 쓰는 코드는 `render()` 를 쓸 것. 기본값이 반주만(MR)이다.
    """
    res = render(src, style=style, level=level, bpm=bpm, curve=curve, tag=tag,
                 out_dir=out_dir, formats=('practice',), mix=mix)
    info = dict(res.info)
    info['file'] = res.files.get('practice')
    return info
