"""음원 내보내기 — 소리가 실제로 그 음높이로 나는지까지 본다.

"파일이 만들어졌다" 는 검사는 아무것도 지켜 주지 못한다. 무음 파일도 통과한다.
그래서 스펙트럼을 열어 **정말 그 음이 울리는지**, 손 분리가 되는지, 셈여림이
크기 차이로 나타나는지를 본다.
"""

from __future__ import annotations

import numpy as np
from app.export.audio import (
    SAMPLE_RATE,
    pcm_to_wav,
    render_audio,
    render_pcm,
    wav_duration_seconds,
)
from app.generation.assemble import measures_to_note_events
from app.schemas.music import Measure, ScoreEvent, Voice


def _one_measure(rh: list[str], lh: list[str], dynamics: str | None = None) -> Measure:
    return Measure(
        number=1,
        rh=[Voice(events=[ScoreEvent(dur=4.0, pitches=rh)])],
        lh=[Voice(events=[ScoreEvent(dur=4.0, pitches=lh)])],
        dynamics=dynamics,  # type: ignore[arg-type]
    )


def _peak_hz(pcm: np.ndarray, seconds: float = 1.0) -> float:
    mono = pcm[: int(seconds * SAMPLE_RATE), 0] + pcm[: int(seconds * SAMPLE_RATE), 1]
    spectrum = np.abs(np.fft.rfft(mono))
    freqs = np.fft.rfftfreq(len(mono), 1.0 / SAMPLE_RATE)
    return float(freqs[int(np.argmax(spectrum))])


def test_rendered_audio_actually_sounds_the_written_pitch() -> None:
    """A4 를 치면 440Hz 근처가 가장 세게 울려야 한다."""
    events = measures_to_note_events([_one_measure(["A4"], [])], 60, "4/4")
    pcm = render_pcm(events, reverb=0.0)
    assert 435 < _peak_hz(pcm) < 445


def test_hands_can_be_exported_separately() -> None:
    """오른손만 뽑으면 왼손 음역이 사라져야 한다 — 손 분리 연습 음원의 전제."""
    events = measures_to_note_events([_one_measure(["C5"], ["C3"])], 60, "4/4")
    assert 515 < _peak_hz(render_pcm(events, hands="rh", reverb=0.0)) < 535
    assert 125 < _peak_hz(render_pcm(events, hands="lh", reverb=0.0)) < 136


def test_dynamics_become_real_loudness_differences() -> None:
    """한 곡 안에서 pp 마디가 ff 마디보다 조용해야 한다.

    렌더는 곡 전체를 한 번 정규화하므로, pp 만 따로 뽑아 재는 것은 의미가 없다.
    같은 파일 안에서 두 마디를 비교해야 다이내믹이 진짜인지 알 수 있다.
    """
    quiet = Measure(number=1, rh=[Voice(events=[ScoreEvent(dur=4.0, pitches=["C4"])])], dynamics="pp")
    loud = Measure(number=2, rh=[Voice(events=[ScoreEvent(dur=4.0, pitches=["C4"])])], dynamics="ff")
    pcm = render_pcm(measures_to_note_events([quiet, loud], 60, "4/4"), reverb=0.0)
    # 60bpm 4/4 → 한 마디 4초. 각 마디의 앞 2초만 재 잔향 섞임을 피한다.
    first = float(np.sqrt((pcm[: 2 * SAMPLE_RATE] ** 2).mean()))
    second = float(np.sqrt((pcm[4 * SAMPLE_RATE : 6 * SAMPLE_RATE] ** 2).mean()))
    assert second > first * 1.8, f"pp {first:.4f} vs ff {second:.4f}"


def test_asking_for_an_absent_hand_yields_silence_not_a_crash() -> None:
    """왼손이 없는 곡에서 '왼손만' 을 눌러도 조용한 파일이 나와야 한다."""
    events = measures_to_note_events([_one_measure(["C4"], [])], 60, "4/4")
    pcm = render_pcm(events, hands="lh")
    assert pcm.shape[1] == 2
    assert float(np.max(np.abs(pcm))) == 0.0


def test_dense_chords_do_not_clip() -> None:
    """열 손가락이 한꺼번에 울려도 -1..1 을 넘지 않아야 한다."""
    events = measures_to_note_events(
        [_one_measure(["C5", "E5", "G5", "C6"], ["C2", "G2", "C3", "E3"], "fff")], 60, "4/4"
    )
    pcm = render_pcm(events)
    assert float(np.max(np.abs(pcm))) <= 1.0


def test_wav_is_a_real_playable_file() -> None:
    events = measures_to_note_events([_one_measure(["C4"], ["C3"])], 60, "4/4")
    wav = pcm_to_wav(render_pcm(events))
    assert wav[:4] == b"RIFF" and wav[8:12] == b"WAVE"
    # 4분음표 4개 = 4초 + 잔향 꼬리
    assert 6.0 < wav_duration_seconds(wav) < 9.0


def test_render_audio_never_returns_empty_handed() -> None:
    """인코더가 있든 없든 빈손으로 보내지 않는다 — mp3 아니면 wav."""
    events = measures_to_note_events([_one_measure(["C4"], ["C3"])], 60, "4/4")
    data, ext = render_audio(events)
    assert ext in {"mp3", "wav"}
    assert len(data) > 4096
