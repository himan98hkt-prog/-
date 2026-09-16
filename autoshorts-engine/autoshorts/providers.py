"""Provider adapter 경계.

외부 의존(STT 모델, LLM, FFmpeg)을 **교체 가능한 어댑터**로 감싼다. 목적은 두 가지다.

1. SaaS 에서 provider 를 workspace 단위로 바꿔 끼울 수 있게 한다.
2. Phase 4 의 multimodal signal provider 가 붙을 자리를 지금 만들어 둔다.

여기서는 **인터페이스와 기존 구현 위임**만 한다. 고급 분석은 Phase 4 범위이며
:class:`SignalProvider` 는 자리만 잡아 두고 구현하지 않는다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Protocol, Sequence

from .contracts import CostEvent, JobSpec
from .models import Clip, Transcript
from .utils import get_logger

__all__ = [
    "TranscriptionProvider",
    "HighlightProvider",
    "RenderProvider",
    "SignalProvider",
    "SignalSample",
    "FasterWhisperProvider",
    "GeminiHighlightProvider",
    "FFmpegRenderProvider",
    "ProviderRegistry",
    "default_registry",
]

LOG = get_logger("providers")


class TranscriptionProvider(ABC):
    """음성 → 타임스탬프 텍스트."""

    name: str = "base"

    @abstractmethod
    def transcribe(self, audio_path: str | Path, spec: JobSpec, **kwargs: Any) -> Transcript:
        ...

    def estimate_cost(self, seconds: float) -> CostEvent:
        return CostEvent(kind="transcription", provider=self.name,
                         units=round(seconds, 2), unit_name="seconds")


class HighlightProvider(ABC):
    """전사본 → 하이라이트 후보."""

    name: str = "base"

    @abstractmethod
    def select(self, transcript: Transcript, spec: JobSpec, **kwargs: Any) -> list[Clip]:
        ...

    def estimate_cost(self, transcript: Transcript) -> CostEvent:
        return CostEvent(kind="highlight", provider=self.name,
                         units=len(transcript.text), unit_name="chars")


class RenderProvider(ABC):
    """클립 → 세로 영상 파일."""

    name: str = "base"

    @abstractmethod
    def render(self, video_path: str | Path, clips: Sequence[Clip],
               transcript: Transcript | None, spec: JobSpec, **kwargs: Any) -> list[Any]:
        ...


class SignalSample(Protocol):
    """Phase 4 가 다룰 신호 한 점의 모양.

    구현은 Phase 4 범위다. 여기서는 candidate ranking 이 어떤 모양의 신호를
    받게 될지만 고정해 둔다.
    """

    start: float
    end: float
    value: float


class SignalProvider(ABC):
    """Phase 4 multimodal signal provider 자리.

    ``audio energy`` / ``scene change`` / ``face presence`` / ``motion`` 같은
    신호를 구간별로 돌려준다. **Phase 1 에서는 구현하지 않는다.**

    fallback 규약: 이 provider 가 없거나 실패하면 highlight 선정은 기존
    transcript-only 경로로 정상 동작해야 한다.
    """

    name: str = "base"
    signal_kind: str = "unknown"

    @abstractmethod
    def sample(self, media_path: str | Path, spec: JobSpec) -> list[SignalSample]:
        ...

    @property
    def available(self) -> bool:
        """이 provider 를 쓸 수 있는지. False 면 호출부는 조용히 건너뛴다."""
        return False


# ── 기존 구현 위임 ─────────────────────────────────────────


class FasterWhisperProvider(TranscriptionProvider):
    """기존 :mod:`autoshorts.transcriber` 위임."""

    name = "faster-whisper"

    def __init__(self, model_size: str = "base", device: str = "auto",
                 compute_type: str = "auto", beam_size: int = 5, vad_filter: bool = True) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.beam_size = beam_size
        self.vad_filter = vad_filter

    def transcribe(self, audio_path: str | Path, spec: JobSpec, **kwargs: Any) -> Transcript:
        from . import transcriber

        return transcriber.transcribe(
            audio_path,
            model_size=self.model_size,
            device=self.device,
            compute_type=self.compute_type,
            language=spec.language,
            beam_size=self.beam_size,
            vad_filter=self.vad_filter,
            **kwargs,
        )


class GeminiHighlightProvider(HighlightProvider):
    """기존 :mod:`autoshorts.ai_analyzer` 위임. 키가 없으면 오프라인 대체."""

    name = "gemini"

    def __init__(self, api_key: str | None = None, model: str = "gemini-2.0-flash",
                 allow_offline_fallback: bool = True) -> None:
        self.api_key = api_key
        self.model = model
        self.allow_offline_fallback = allow_offline_fallback

    def select(self, transcript: Transcript, spec: JobSpec, **kwargs: Any) -> list[Clip]:
        from . import ai_analyzer

        options = spec.clip_options
        return ai_analyzer.analyze(
            transcript,
            api_key=self.api_key,
            model=self.model,
            min_seconds=options.min_seconds,
            max_seconds=options.max_seconds,
            min_clips=options.min_clips,
            max_clips=options.max_clips,
            allow_offline_fallback=self.allow_offline_fallback,
            **kwargs,
        )

    @property
    def uses_offline_fallback(self) -> bool:
        return not self.api_key


class FFmpegRenderProvider(RenderProvider):
    """기존 :mod:`autoshorts.video_renderer` 위임."""

    name = "ffmpeg"

    def render(self, video_path, clips, transcript, spec, **kwargs):
        from . import video_renderer

        return video_renderer.render_clips(video_path, clips, transcript, **kwargs)


class ProviderRegistry:
    """이름 → provider 해석."""

    def __init__(self) -> None:
        self._transcription: dict[str, Any] = {}
        self._highlight: dict[str, Any] = {}
        self._render: dict[str, Any] = {}
        self._signals: list[SignalProvider] = []

    def register_transcription(self, name: str, factory) -> None:
        self._transcription[name] = factory

    def register_highlight(self, name: str, factory) -> None:
        self._highlight[name] = factory

    def register_render(self, name: str, factory) -> None:
        self._render[name] = factory

    def register_signal(self, provider: SignalProvider) -> None:
        """Phase 4 가 신호 provider 를 붙일 지점."""
        self._signals.append(provider)

    def signal_providers(self) -> list[SignalProvider]:
        """사용 가능한 신호 provider 만. 없으면 빈 목록(= transcript-only fallback)."""
        return [p for p in self._signals if p.available]

    def transcription(self, name: str, **kwargs) -> TranscriptionProvider:
        factory = self._transcription.get(name)
        if factory is None:
            raise KeyError(f"등록되지 않은 전사 provider: {name!r}")
        return factory(**kwargs)

    def highlight(self, name: str, **kwargs) -> HighlightProvider:
        factory = self._highlight.get(name)
        if factory is None:
            raise KeyError(f"등록되지 않은 분석 provider: {name!r}")
        return factory(**kwargs)

    def render(self, name: str, **kwargs) -> RenderProvider:
        factory = self._render.get(name)
        if factory is None:
            raise KeyError(f"등록되지 않은 렌더 provider: {name!r}")
        return factory(**kwargs)

    def known(self) -> dict[str, list[str]]:
        return {
            "transcription": sorted(self._transcription),
            "highlight": sorted(self._highlight),
            "render": sorted(self._render),
            "signal": [p.name for p in self._signals],
        }


def default_registry() -> ProviderRegistry:
    """기본 provider 가 등록된 레지스트리."""
    registry = ProviderRegistry()
    registry.register_transcription("faster-whisper", FasterWhisperProvider)
    registry.register_highlight("gemini", GeminiHighlightProvider)
    registry.register_render("ffmpeg", FFmpegRenderProvider)
    return registry
