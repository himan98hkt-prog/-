"""AutoShorts-Engine — 롱폼 영상을 AI 로 분석해 9:16 쇼츠를 자동 생성한다.

무거운 의존성(yt-dlp, faster-whisper, Gemini SDK, Gradio)은 실제로 쓰이는
시점에 지연 임포트하므로, 이 패키지를 임포트하는 것만으로는 아무것도
설치돼 있지 않아도 된다.
"""

from __future__ import annotations

__version__ = "0.1.0"

from .config import Settings, SubtitleStyle
from .models import Clip, Segment, Transcript, Word

__all__ = [
    "__version__",
    "Settings",
    "SubtitleStyle",
    "Clip",
    "Segment",
    "Transcript",
    "Word",
    "run_pipeline",
]


def run_pipeline(settings: "Settings", **kwargs):
    """:func:`autoshorts.pipeline.run_pipeline` 지연 로딩 래퍼."""
    from .pipeline import run_pipeline as _run

    return _run(settings, **kwargs)
