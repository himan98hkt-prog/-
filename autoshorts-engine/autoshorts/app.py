"""선택 UI — Gradio 기반 간이 대시보드.

``pip install gradio`` 후 ``autoshorts ui`` 로 실행한다. 설치돼 있지 않으면
CLI 사용법을 안내하고 종료한다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import REFRAME_MODES, Settings, SubtitleStyle, load_dotenv
from .utils import get_logger, human_duration, setup_logging

LOG = get_logger("app")

DESCRIPTION = """
# 🎬 AutoShorts-Engine

유튜브 URL 이나 로컬 영상 파일을 넣으면 AI 가 하이라이트를 골라
자막이 박힌 9:16 쇼츠로 만들어 드립니다.

- 전사는 로컬 `faster-whisper` (무과금)
- 하이라이트 선정은 Gemini 무료 티어, 키가 없으면 오프라인 휴리스틱으로 자동 대체
"""


def _run_job(
    url: str,
    uploaded: Any,
    mode: str,
    whisper_model: str,
    min_seconds: float,
    max_seconds: float,
    max_clips: int,
    burn_subtitles: bool,
    api_key: str,
    output_dir: str,
    progress: Any = None,
):
    """UI 폼 입력을 파이프라인 설정으로 옮겨 실행한다."""
    from .pipeline import run_pipeline

    source = (url or "").strip()
    if not source and uploaded:
        source = uploaded if isinstance(uploaded, str) else getattr(uploaded, "name", "")
    if not source:
        raise ValueError("유튜브 URL 을 입력하거나 영상 파일을 업로드하세요.")

    settings = Settings(
        source=source,
        output_dir=Path(output_dir or "output"),
        whisper_model=whisper_model,
        min_clip_seconds=float(min_seconds),
        max_clip_seconds=float(max_seconds),
        max_clips=int(max_clips),
        min_clips=min(3, int(max_clips)),
        reframe_mode=mode,
        burn_subtitles=bool(burn_subtitles),
        gemini_api_key=(api_key or "").strip() or None,
        subtitle_style=SubtitleStyle(),
    )

    def on_progress(stage: str, fraction: float, message: str) -> None:
        if progress is not None:
            try:
                progress(fraction, desc=f"[{stage}] {message}")
            except Exception:
                pass

    result = run_pipeline(settings, on_progress=on_progress)

    rows = [
        [
            clip.index,
            f"{clip.start:.1f}s ~ {clip.end:.1f}s",
            human_duration(clip.duration),
            clip.title,
            clip.score,
            clip.reason,
        ]
        for clip in result.clips
    ]
    videos = [str(path) for path in result.output_paths]
    note = (
        f"쇼츠 {len(videos)}개 생성 · {human_duration(result.elapsed_seconds)} 소요"
        + ("\n\n⚠️ Gemini 키가 없어 오프라인 휴리스틱으로 구간을 골랐습니다." if result.used_offline_analysis else "")
    )
    return rows, videos, note


def build_interface():
    """Gradio Blocks 인터페이스를 만든다 (실행은 하지 않는다)."""
    import gradio as gr

    with gr.Blocks(title="AutoShorts-Engine", theme=gr.themes.Soft()) as demo:
        gr.Markdown(DESCRIPTION)
        with gr.Row():
            with gr.Column(scale=3):
                url = gr.Textbox(label="유튜브 URL", placeholder="https://www.youtube.com/watch?v=...")
                uploaded = gr.File(label="또는 로컬 영상 파일", file_types=["video"], type="filepath")
                with gr.Row():
                    mode = gr.Radio(list(REFRAME_MODES), value="blur", label="9:16 변환 방식")
                    whisper_model = gr.Dropdown(
                        ["tiny", "base", "small", "medium"], value="base", label="Whisper 모델"
                    )
                with gr.Row():
                    min_seconds = gr.Slider(10, 90, value=30, step=5, label="클립 최소 길이(초)")
                    max_seconds = gr.Slider(20, 120, value=60, step=5, label="클립 최대 길이(초)")
                with gr.Row():
                    max_clips = gr.Slider(1, 10, value=5, step=1, label="최대 클립 수")
                    burn_subtitles = gr.Checkbox(value=True, label="자막 번인")
                api_key = gr.Textbox(label="Gemini API 키 (선택)", type="password",
                                     placeholder="비우면 GEMINI_API_KEY 환경변수 또는 오프라인 분석")
                output_dir = gr.Textbox(label="저장 폴더", value="output")
                start = gr.Button("쇼츠 만들기", variant="primary")
            with gr.Column(scale=4):
                note = gr.Markdown()
                table = gr.Dataframe(
                    headers=["#", "구간", "길이", "후킹 제목", "점수", "선정 이유"],
                    label="선정된 하이라이트",
                    wrap=True,
                )
                gallery = gr.Files(label="생성된 쇼츠")

        start.click(
            fn=lambda *args, progress=gr.Progress(): _run_job(*args, progress=progress),
            inputs=[url, uploaded, mode, whisper_model, min_seconds, max_seconds,
                    max_clips, burn_subtitles, api_key, output_dir],
            outputs=[table, gallery, note],
        )
    return demo


def launch(host: str = "127.0.0.1", port: int = 7860, share: bool = False) -> None:
    load_dotenv()
    setup_logging()
    try:
        import gradio  # noqa: F401
    except ImportError:
        print(
            "Gradio 가 설치돼 있지 않습니다.\n"
            "  pip install gradio\n"
            "설치 없이 쓰려면 CLI 를 사용하세요:\n"
            '  autoshorts run "https://youtu.be/..."'
        )
        return
    build_interface().launch(server_name=host, server_port=port, share=share)


if __name__ == "__main__":
    launch()
