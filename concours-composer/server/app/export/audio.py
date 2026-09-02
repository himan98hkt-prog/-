"""음원 내보내기 — 곡을 소리 파일로 만든다.

원장이 곡을 판단하고 **학생·학부모에게 들려주려면** 파일 하나가 필요하다.
MIDI 는 재생기를 가려서 학부모 휴대폰에서 그냥 열리지 않는다.

외부 프로그램(fluidsynth·사운드폰트·ffmpeg)에 기대지 않는다. 학원 PC 에
그런 것을 깔게 하면 아무도 못 쓴다. 그래서 **numpy 만으로 직접 합성**한다 —
피아노는 배음 하나하나가 서로 다른 속도로 잦아드는 악기라, 배음별 감쇠만
제대로 주면 삼각파와는 비교가 안 되는 소리가 나온다.

MP3 는 ffmpeg·lame 이 있을 때만 만든다. 없으면 WAV 를 준다 — 어디서나 열린다.
"""

from __future__ import annotations

import io
import math
import shutil
import subprocess
import wave
from typing import Literal

import numpy as np

from app.schemas.music import NoteEvents

try:  # 울림(리버브) 합성용. 없으면 마른 소리로 낸다 — 소리는 나야 한다.
    from scipy.signal import oaconvolve as _oaconvolve
except ImportError:  # pragma: no cover - scipy 는 requirements 에 있다
    _oaconvolve = None  # type: ignore[assignment]

SAMPLE_RATE = 44100
Hands = Literal["both", "rh", "lh"]

# 배음 개수. 피아노는 20개 넘게 울리지만, 12개면 귀로 구분이 어렵고 계산은 절반이다.
_PARTIALS = 12
# 어느 배음까지를 '어두운 소리' 로 볼 것인가. 여린 타건은 이쪽만 울린다.
_DARK_PARTIALS = 4

# 음 하나를 미리 만들어 두는 길이(초). 낮은음은 오래 울린다.
_BANK_SECONDS = ((59, 5.0), (79, 3.0), (108, 2.0))

# (음높이) → (어두운 파형, 밝은 파형). 요청마다 다시 만들지 않는다.
_BANK: dict[int, tuple[np.ndarray, np.ndarray]] = {}
_REVERB: dict[int, np.ndarray] = {}


def _bank_seconds(pitch: int) -> float:
    for upper, sec in _BANK_SECONDS:
        if pitch <= upper:
            return sec
    return 2.0


def _decay_seconds(f0: float) -> float:
    """기본 배음이 잦아드는 시간. 낮은 음일수록 길다 — 실제 피아노가 그렇다."""
    return min(6.0, max(0.7, 0.55 + 260.0 / f0))


def _one_note(pitch: int, sample_rate: int) -> tuple[np.ndarray, np.ndarray]:
    """세기 1.0 으로 친 음 하나. (어두운 소리, 밝은 소리) 두 벌을 만든다.

    두 벌을 섞어 타건 세기에 따른 음색 변화를 낸다 — 여리게 치면 배음이 덜 실린다.
    필터를 음마다 돌리는 것보다 훨씬 싸고, 결과는 결정적이다.
    """
    f0 = 440.0 * (2.0 ** ((pitch - 69) / 12.0))
    n = int(_bank_seconds(pitch) * sample_rate)
    t = np.arange(n, dtype=np.float32) / sample_rate
    tau0 = _decay_seconds(f0)
    # 현의 뻣뻣함 때문에 배음은 정확한 정수배보다 살짝 높다(inharmonicity).
    stiffness = 0.0004 + 0.0009 * max(0.0, (pitch - 60) / 48.0)

    dark = np.zeros(n, dtype=np.float32)
    bright = np.zeros(n, dtype=np.float32)
    nyquist = sample_rate * 0.5
    for k in range(1, _PARTIALS + 1):
        freq = f0 * k * math.sqrt(1.0 + stiffness * k * k)
        if freq >= nyquist * 0.95:
            break
        # 배음 세기: 높을수록 약하다. cos 항은 배음마다 조금씩 다르게 해 '통' 을 만든다.
        amp = (1.0 / k**1.35) * (1.0 + 0.28 * math.cos(k * 1.7))
        # 높은 배음일수록 빨리 잦아든다 — 이것이 피아노 소리의 핵심이다.
        tau = tau0 / (1.0 + 0.42 * (k - 1))
        wave_k = amp * np.exp(-t / tau, dtype=np.float32) * np.sin(2.0 * math.pi * freq * t, dtype=np.float32)
        bright += wave_k
        if k <= _DARK_PARTIALS:
            dark += wave_k

    # 타건음(해머가 현을 때리는 순간의 잡음). 씨앗을 음높이로 고정해 결정적으로.
    rng = np.random.default_rng(pitch)
    thump_n = min(n, int(0.012 * sample_rate))
    thump = rng.standard_normal(thump_n).astype(np.float32)
    thump *= np.exp(-np.arange(thump_n, dtype=np.float32) / (0.0025 * sample_rate))
    thump *= 0.09
    bright[:thump_n] += thump
    dark[:thump_n] += thump * 0.5

    # 어택. 없으면 딸깍거린다.
    attack = 1.0 - np.exp(-t / 0.0035, dtype=np.float32)
    bright *= attack
    dark *= attack

    peak = float(np.max(np.abs(bright))) or 1.0
    return dark / peak, bright / peak


def _bank(pitch: int, sample_rate: int) -> tuple[np.ndarray, np.ndarray]:
    key = pitch if sample_rate == SAMPLE_RATE else pitch + 1000 * sample_rate
    got = _BANK.get(key)
    if got is None:
        got = _one_note(pitch, sample_rate)
        _BANK[key] = got
    return got


def _reverb_ir(sample_rate: int) -> np.ndarray:
    """짧은 방 울림. 마른 소리로 두면 학원 스피커에서 얇게 들린다."""
    got = _REVERB.get(sample_rate)
    if got is not None:
        return got
    n = int(0.85 * sample_rate)
    rng = np.random.default_rng(20260902)
    ir = rng.standard_normal(n).astype(np.float32)
    ir *= np.exp(-np.arange(n, dtype=np.float32) / (0.22 * sample_rate))
    pre = int(0.018 * sample_rate)
    ir[:pre] = 0.0
    ir /= float(np.sum(np.abs(ir))) or 1.0
    _REVERB[sample_rate] = ir
    return ir


def _pedal_mask(events: NoteEvents, total: float) -> list[tuple[float, float]]:
    return [(p.onset, min(p.offset, total)) for p in events.pedal]


def render_pcm(
    events: NoteEvents,
    *,
    hands: Hands = "both",
    sample_rate: int = SAMPLE_RATE,
    reverb: float = 0.14,
) -> np.ndarray:
    """NoteEvents → 스테레오 float32 배열 (샘플, 2). 값 범위 -1..1."""
    by_hand: dict[str, set[str | None]] = {
        "both": {"L", "R", None},
        "rh": {"R"},
        "lh": {"L"},
    }
    keep = by_hand[hands]
    notes = [n for n in events.notes if n.hand in keep]
    if not notes:
        return np.zeros((sample_rate // 10, 2), dtype=np.float32)

    end = max(n.offset for n in notes)
    tail = 3.0  # 마지막 음이 잦아들 시간
    total_n = int((end + tail) * sample_rate) + 1
    left = np.zeros(total_n, dtype=np.float32)
    right = np.zeros(total_n, dtype=np.float32)

    pedals = _pedal_mask(events, end + tail)

    for note in notes:
        dark, bright = _bank(note.pitch, sample_rate)
        # 세기 → 크기와 밝기. 세게 칠수록 배음이 실린다.
        v = note.velocity / 127.0
        gain = v**1.55
        mix = 0.30 + 0.70 * v
        body = dark + mix * (bright - dark)

        start = int(note.onset * sample_rate)
        # 건반을 떼면 댐퍼가 현을 잡는다. 페달이 밟혀 있으면 그대로 울리게 둔다.
        held = any(a <= note.onset < b for a, b in pedals)
        ring = len(body) / sample_rate if held else (note.duration + 0.28)
        take = min(len(body), int(ring * sample_rate))
        if take <= 0:
            continue
        seg = body[:take] * gain

        if not held:
            # 건반을 뗀 뒤 0.22초에 걸쳐 잡는다.
            off = int(note.duration * sample_rate)
            if 0 <= off < take:
                fade_n = take - off
                fade = np.exp(-np.arange(fade_n, dtype=np.float32) / (0.055 * sample_rate))
                seg = seg.copy()
                seg[off:] *= fade

        stop = min(total_n, start + take)
        if stop <= start:
            continue
        piece = seg[: stop - start]
        # 낮은 음은 왼쪽, 높은 음은 오른쪽으로 살짝. 그랜드 피아노 앞에 앉은 자리다.
        pan = max(-0.65, min(0.65, (note.pitch - 60) / 42.0))
        angle = (pan + 1.0) * (math.pi / 4.0)
        left[start:stop] += piece * math.cos(angle)
        right[start:stop] += piece * math.sin(angle)

    if reverb > 0:
        ir = _reverb_ir(sample_rate)
        left = _convolve(left, ir, reverb)
        right = _convolve(right, ir, reverb)

    out = np.stack([left, right], axis=1)
    peak = float(np.max(np.abs(out)))
    if peak > 0:
        out *= 0.89 / peak  # -1 dBFS 근처. 클리핑 없이 충분히 크게.
    return out.astype(np.float32)


def _convolve(sig: np.ndarray, ir: np.ndarray, wet: float) -> np.ndarray:
    """마른 소리에 울림을 섞는다. 길이는 원본 그대로 유지한다.

    긴 신호에 짧은 응답을 겹치는 일이라 겹침-더하기(overlap-add)가 통짜 FFT 보다
    두세 배 빠르다 — 원장이 버튼을 누르고 기다리는 시간이 그만큼 준다.
    """
    if _oaconvolve is None:  # pragma: no cover
        return sig
    tail = _oaconvolve(sig, ir)[: len(sig)].astype(np.float32)
    return ((1.0 - wet) * sig + wet * tail).astype(np.float32)


def pcm_to_wav(pcm: np.ndarray, sample_rate: int = SAMPLE_RATE) -> bytes:
    """float32 (샘플, 2) → 16비트 WAV 바이트."""
    clipped = np.clip(pcm, -1.0, 1.0)
    ints = (clipped * 32767.0).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(ints.tobytes())
    return buf.getvalue()


def _ffmpeg_path() -> str | None:
    """ffmpeg 실행 파일. 시스템에 깔린 것 → pip 로 딸려온 것 순으로 찾는다.

    imageio-ffmpeg 는 윈도우·맥·리눅스용 ffmpeg 를 통째로 들고 오는 패키지라,
    원장이 따로 무엇을 설치하지 않아도 MP3 가 나온다.
    """
    system = shutil.which("ffmpeg")
    if system:
        return system
    try:
        import imageio_ffmpeg

        return str(imageio_ffmpeg.get_ffmpeg_exe())
    except (ImportError, RuntimeError, OSError):
        return None


def mp3_encoder() -> list[str] | None:
    """MP3 로 바꿔 줄 프로그램이 있으면 그 명령을, 없으면 None."""
    exe = _ffmpeg_path()
    if exe:
        return [
            exe,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            "pipe:0",
            "-codec:a",
            "libmp3lame",
            "-q:a",
            "2",
            "-f",
            "mp3",
            "pipe:1",
        ]
    if shutil.which("lame"):
        return ["lame", "--quiet", "-V", "2", "-", "-"]
    return None


def wav_to_mp3(wav: bytes) -> bytes | None:
    """WAV → MP3. 인코더가 없거나 실패하면 None (호출한 쪽이 WAV 를 준다)."""
    cmd = mp3_encoder()
    if cmd is None:
        return None
    try:
        proc = subprocess.run(cmd, input=wav, capture_output=True, timeout=180, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0 or len(proc.stdout) < 1024:
        return None
    return proc.stdout


def render_audio(
    events: NoteEvents,
    *,
    hands: Hands = "both",
    prefer_mp3: bool = True,
    sample_rate: int = SAMPLE_RATE,
) -> tuple[bytes, str]:
    """곡 → (파일 바이트, 확장자). MP3 가 안 되면 WAV 로 준다 — 빈손으로 보내지 않는다."""
    wav = pcm_to_wav(render_pcm(events, hands=hands, sample_rate=sample_rate), sample_rate)
    if prefer_mp3:
        mp3 = wav_to_mp3(wav)
        if mp3 is not None:
            return mp3, "mp3"
    return wav, "wav"


def wav_duration_seconds(wav: bytes) -> float:
    """WAV 헤더에서 길이를 읽는다 — 테스트와 화면 표시용."""
    with wave.open(io.BytesIO(wav), "rb") as w:
        return w.getnframes() / float(w.getframerate())


__all__ = [
    "SAMPLE_RATE",
    "mp3_encoder",
    "pcm_to_wav",
    "render_audio",
    "render_pcm",
    "wav_duration_seconds",
    "wav_to_mp3",
]
