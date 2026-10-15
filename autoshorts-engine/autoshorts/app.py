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
- **급상승 탐색** 탭에서 키워드·채널로 '떡상 영상'을 찾아 바로 쇼츠로 만들 수 있습니다
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
    do_upload: bool = False,
    privacy: str = "private",
    publish_in_hours: float = 0.0,
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

    upload_lines: list[str] = []
    if do_upload and result.renders:
        from datetime import datetime, timedelta, timezone

        from . import uploader
        from .automation import AutoOptions, build_upload_request

        publish_at = None
        if publish_in_hours and float(publish_in_hours) > 0:
            publish_at = datetime.now(timezone.utc) + timedelta(hours=float(publish_in_hours))

        options = AutoOptions(upload=True, privacy=privacy, publish_at=publish_at)
        for index, render in enumerate(result.renders):
            request = build_upload_request(
                render, options=options, source_title=result.title, source_url=result.source
            )
            if publish_at is not None:
                request.publish_at = publish_at + timedelta(hours=24 * index)
                request.privacy = "private"
            try:
                uploaded_result = upload_fn_for_ui()(request)
                upload_lines.append(f"- [{uploaded_result.title}]({uploaded_result.shorts_url}) · {uploaded_result.privacy}")
            except Exception as exc:
                upload_lines.append(f"- ⚠️ {render.output_path.name}: {exc}")

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
    if upload_lines:
        note += "\n\n**업로드**\n" + "\n".join(upload_lines)
    return rows, videos, note


def upload_fn_for_ui():
    """업로드 함수를 지연 조회한다(테스트에서 교체하기 쉽도록)."""
    from . import uploader

    return uploader.upload_video


def _find_trending(target, is_channel, days, top, min_vs, min_subscribers, min_duration, api_key):
    """급상승 탐색 탭: 표와 1위 URL 을 돌려준다."""
    from . import trend_finder

    target = (target or "").strip()
    if not target:
        raise ValueError("키워드나 채널(@핸들 · 채널 URL)을 입력하세요.")

    key = (api_key or "").strip() or Settings(source="x").youtube_api_key
    videos, quota = trend_finder.find_trending(
        target,
        api_key=key,
        days=float(days),
        limit=int(top),
        min_vs_ratio=float(min_vs),
        min_subscribers=int(min_subscribers),
        min_duration=float(min_duration),
        as_channel=True if is_channel else None,
    )
    rows = [
        [v.rank, round(v.vs_ratio, 2), f"{v.view_count:,}", f"{v.subscriber_count:,}",
         f"{v.age_hours:.0f}시간 전", human_duration(v.duration_seconds), v.title, v.url]
        for v in videos
    ]
    if not videos:
        return rows, "", "조건에 맞는 영상이 없습니다. 기간을 늘리거나 V/S 기준을 낮춰 보세요."
    note = (
        f"**{len(videos)}개 발견** · 할당량 {quota} 유닛 사용 (무료 한도 하루 10,000)\n\n"
        f"1위: [{videos[0].title}]({videos[0].url}) — V/S {videos[0].vs_ratio:.2f}"
    )
    return rows, videos[0].url, note


def build_interface():
    """Gradio Blocks 인터페이스를 만든다 (실행은 하지 않는다)."""
    import gradio as gr

    # 테마 인자는 Gradio 버전마다 위치가 달라(6.0 에서 launch 로 이동) 지정하지 않는다
    with gr.Blocks(title="AutoShorts-Engine") as demo:
        gr.Markdown(DESCRIPTION)

        with gr.Tab("급상승 탐색"):
            gr.Markdown("키워드나 채널에서 **구독자 대비 조회수(V/S)** 가 높은 최근 영상을 찾습니다.")
            with gr.Row():
                with gr.Column(scale=3):
                    trend_target = gr.Textbox(
                        label="키워드 또는 채널",
                        placeholder="재테크  ·  @채널핸들  ·  https://www.youtube.com/channel/UC...")
                    trend_is_channel = gr.Checkbox(value=False, label="채널로 강제 해석 (할당량 100배 절약)")
                    with gr.Row():
                        trend_days = gr.Slider(1, 90, value=14, step=1, label="최근 며칠")
                        trend_top = gr.Slider(1, 25, value=10, step=1, label="상위 몇 개")
                    with gr.Row():
                        trend_min_vs = gr.Slider(0.1, 20, value=1.0, step=0.1, label="최소 V/S 비율")
                        trend_min_subs = gr.Number(value=1000, label="최소 구독자 수", precision=0)
                    trend_min_duration = gr.Slider(60, 1800, value=180, step=30,
                                                   label="원본 최소 길이(초) — 쇼츠 제외")
                    trend_key = gr.Textbox(label="YouTube Data API 키 (선택)", type="password",
                                           placeholder="비우면 YOUTUBE_API_KEY 환경변수 사용")
                    trend_search = gr.Button("급상승 영상 찾기", variant="primary")
                with gr.Column(scale=4):
                    trend_note = gr.Markdown()
                    trend_table = gr.Dataframe(
                        headers=["#", "V/S", "조회수", "구독자", "업로드", "길이", "제목", "URL"],
                        label="급상승 후보", wrap=True,
                    )
                    trend_top_url = gr.Textbox(label="1위 영상 URL", interactive=False)
                    trend_make = gr.Button("이 영상으로 쇼츠 만들기 →", variant="secondary")

        with gr.Tab("쇼츠 제작"):
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
                    with gr.Accordion("YouTube 자동 업로드 (선택)", open=False):
                        gr.Markdown(
                            "업로드하려면 터미널에서 `autoshorts login` 을 한 번 실행해 두세요.\n\n"
                            "⚠️ 남의 영상을 재편집한 것이라면 저작권 신고 대상이 될 수 있습니다. "
                            "기본값은 **비공개**이니 확인 후 직접 공개하시길 권합니다."
                        )
                        do_upload = gr.Checkbox(value=False, label="만들고 나서 YouTube 에 업로드")
                        privacy = gr.Radio(["private", "unlisted", "public"], value="private",
                                           label="공개 범위")
                        publish_in_hours = gr.Slider(
                            0, 168, value=0, step=1,
                            label="예약 공개 (몇 시간 뒤 · 0이면 예약 없음, 여러 개면 24시간 간격)")
                    start = gr.Button("쇼츠 만들기", variant="primary")
                with gr.Column(scale=4):
                    note = gr.Markdown()
                    table = gr.Dataframe(
                        headers=["#", "구간", "길이", "후킹 제목", "점수", "선정 이유"],
                        label="선정된 하이라이트",
                        wrap=True,
                    )
                    gallery = gr.Files(label="생성된 쇼츠")

        trend_search.click(
            fn=_find_trending,
            inputs=[trend_target, trend_is_channel, trend_days, trend_top,
                    trend_min_vs, trend_min_subs, trend_min_duration, trend_key],
            outputs=[trend_table, trend_top_url, trend_note],
        )
        # 1위 URL 을 제작 탭으로 넘겨 그대로 실행 — 원클릭 연동
        trend_make.click(fn=lambda value: value, inputs=[trend_top_url], outputs=[url]).then(
            fn=lambda *args, progress=gr.Progress(): _run_job(*args, progress=progress),
            inputs=[url, uploaded, mode, whisper_model, min_seconds, max_seconds,
                    max_clips, burn_subtitles, api_key, output_dir,
                    do_upload, privacy, publish_in_hours],
            outputs=[table, gallery, note],
        )

        start.click(
            fn=lambda *args, progress=gr.Progress(): _run_job(*args, progress=progress),
            inputs=[url, uploaded, mode, whisper_model, min_seconds, max_seconds,
                    max_clips, burn_subtitles, api_key, output_dir,
                    do_upload, privacy, publish_in_hours],
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
