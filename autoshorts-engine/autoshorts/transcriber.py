"""Module B — Transcription Engine.

``faster-whisper`` 로 오디오를 전사한다. CPU 로컬 구동이 기본이며,
CUDA 가 잡히면 자동으로 GPU 를 쓴다. 결과는 단어 단위 타임스탬프까지
포함해 ``transcription.json`` 으로 저장한다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Iterable

from .models import Segment, Transcript, Word
from .utils import ensure_dir, get_logger

__all__ = [
    "transcribe",
    "TranscriptionError",
    "resolve_device",
    "segments_from_whisper",
    "MODEL_SIZES",
]

LOG = get_logger("transcriber")

MODEL_SIZES = ("tiny", "base", "small", "medium", "large-v3", "distil-large-v3")


class TranscriptionError(RuntimeError):
    """전사 실패."""


def resolve_device(device: str = "auto", compute_type: str = "auto") -> tuple[str, str]:
    """실행 장치와 연산 타입을 결정한다.

    CUDA 가 있으면 ``cuda/float16``, 없으면 ``cpu/int8`` 을 고른다.
    int8 은 CPU 에서 정확도 손실이 거의 없으면서 2~3배 빠르다.
    """
    resolved_device = device
    if device == "auto":
        resolved_device = "cpu"
        try:  # torch 는 선택적 의존성
            import torch  # type: ignore

            if torch.cuda.is_available():
                resolved_device = "cuda"
        except Exception:
            resolved_device = "cpu"

    resolved_compute = compute_type
    if compute_type == "auto":
        resolved_compute = "float16" if resolved_device == "cuda" else "int8"
    return resolved_device, resolved_compute


def _word_text(word: Any) -> str:
    text = getattr(word, "word", None)
    if text is None:
        text = getattr(word, "text", "")
    return str(text)


def segments_from_whisper(raw_segments: Iterable[Any]) -> list[Segment]:
    """faster-whisper 세그먼트 객체를 내부 모델로 변환.

    duck typing 으로 접근하므로 테스트에서 가짜 객체를 그대로 쓸 수 있다.
    """
    out: list[Segment] = []
    for raw in raw_segments:
        words: list[Word] = []
        for word in (getattr(raw, "words", None) or []):
            text = _word_text(word).strip()
            if not text:
                continue
            words.append(
                Word(
                    start=getattr(word, "start", raw.start) or 0.0,
                    end=getattr(word, "end", raw.end) or 0.0,
                    text=text,
                    probability=getattr(word, "probability", None),
                )
            )
        text = str(getattr(raw, "text", "") or "").strip()
        if not text and not words:
            continue
        out.append(
            Segment(
                start=float(getattr(raw, "start", 0.0) or 0.0),
                end=float(getattr(raw, "end", 0.0) or 0.0),
                text=text or " ".join(w.text for w in words),
                words=words,
            )
        )
    return out


def transcribe(
    audio_path: str | Path,
    *,
    model_size: str = "base",
    device: str = "auto",
    compute_type: str = "auto",
    language: str | None = None,
    beam_size: int = 5,
    vad_filter: bool = True,
    output_path: str | Path | None = None,
    progress: Callable[[float, str], None] | None = None,
) -> Transcript:
    """오디오를 전사해 :class:`Transcript` 를 돌려준다.

    ``output_path`` 를 주면 같은 내용을 JSON 으로도 저장한다.
    """
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise TranscriptionError(f"오디오 파일이 없습니다: {audio_path}")

    try:
        from faster_whisper import WhisperModel  # 지연 임포트 (설치가 무겁다)
    except ImportError as exc:  # pragma: no cover - 환경 의존
        raise TranscriptionError(
            "faster-whisper 가 설치돼 있지 않습니다. `pip install faster-whisper` 로 설치하세요."
        ) from exc

    resolved_device, resolved_compute = resolve_device(device, compute_type)
    LOG.info(
        "전사 시작: model=%s device=%s compute=%s file=%s",
        model_size, resolved_device, resolved_compute, audio_path.name,
    )

    try:
        model = WhisperModel(model_size, device=resolved_device, compute_type=resolved_compute)
    except Exception as exc:
        if resolved_device == "cuda":
            LOG.warning("GPU 초기화 실패, CPU 로 전환합니다: %s", exc)
            resolved_device, resolved_compute = "cpu", "int8"
            model = WhisperModel(model_size, device=resolved_device, compute_type=resolved_compute)
        else:
            raise TranscriptionError(f"Whisper 모델 로드 실패: {exc}") from exc

    raw_segments, info = model.transcribe(
        str(audio_path),
        language=language,
        beam_size=beam_size,
        vad_filter=vad_filter,
        vad_parameters={"min_silence_duration_ms": 500} if vad_filter else None,
        word_timestamps=True,
        condition_on_previous_text=False,  # 긴 영상에서 환각 반복 억제
    )

    total = float(getattr(info, "duration", 0.0) or 0.0)
    segments: list[Segment] = []
    for segment in segments_from_whisper(raw_segments):
        segments.append(segment)
        if progress and total:
            progress(min(segment.end / total, 1.0), segment.text)

    if not segments:
        raise TranscriptionError(
            "음성에서 텍스트를 추출하지 못했습니다. 오디오에 말소리가 있는지 확인하세요."
        )

    transcript = Transcript(
        segments=segments,
        language=getattr(info, "language", None) or language,
        duration=total or max(s.end for s in segments),
        source=str(audio_path),
        model=f"faster-whisper/{model_size}",
    )
    LOG.info(
        "전사 완료: %d개 세그먼트, 언어=%s, 길이=%.1fs",
        len(transcript), transcript.language, transcript.duration,
    )

    if output_path:
        output_path = Path(output_path)
        ensure_dir(output_path.parent)
        transcript.save(output_path)
        srt_path = output_path.with_suffix(".srt")
        srt_path.write_text(transcript.to_srt(), encoding="utf-8")
        LOG.info("전사 저장: %s / %s", output_path.name, srt_path.name)

    return transcript


def load_or_transcribe(audio_path: str | Path, cache_path: str | Path, **kwargs: Any) -> Transcript:
    """캐시가 있으면 재사용하고, 없으면 전사한다."""
    cache_path = Path(cache_path)
    if cache_path.exists():
        LOG.info("전사 캐시 재사용: %s", cache_path.name)
        return Transcript.load(cache_path)
    return transcribe(audio_path, output_path=cache_path, **kwargs)
