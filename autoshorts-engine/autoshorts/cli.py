"""AutoShorts-Engine 커맨드라인 인터페이스.

    autoshorts run "https://youtu.be/..." --mode blur
    autoshorts transcribe input.mp4
    autoshorts analyze work/.../transcription.json
    autoshorts render input.mp4 --clips clips.json
    autoshorts ui
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from . import __version__
from .config import REFRAME_MODES, Settings, SubtitleStyle, load_dotenv
from .models import Clip, Transcript
from .utils import get_logger, human_duration, setup_logging

LOG = get_logger("cli")


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-o", "--output-dir", default="output", help="최종 쇼츠 저장 폴더 (기본: output)")
    parser.add_argument("-w", "--work-dir", default="work", help="중간 산출물 폴더 (기본: work)")
    parser.add_argument("-v", "--verbose", action="store_true", help="상세 로그")
    parser.add_argument("-q", "--quiet", action="store_true", help="경고 이상만 출력")


def _add_transcribe_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model", default="base", help="faster-whisper 모델 (tiny/base/small/medium/large-v3)")
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"], help="추론 장치")
    parser.add_argument("--compute-type", default="auto", help="연산 타입 (int8/float16/float32 등)")
    parser.add_argument("--language", default=None, help="언어 코드 강제 지정 (예: ko, en). 기본은 자동 감지")
    parser.add_argument("--beam-size", type=int, default=5, help="빔 서치 크기 (기본: 5)")
    parser.add_argument("--no-vad", action="store_true", help="무음 구간 제거(VAD) 비활성화")


def _add_analyze_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--gemini-model", default="gemini-2.0-flash", help="Gemini 모델명")
    parser.add_argument("--api-key", default=None, help="Gemini API 키 (기본: GEMINI_API_KEY 환경변수)")
    parser.add_argument("--min-seconds", type=float, default=30.0, help="클립 최소 길이 (기본: 30)")
    parser.add_argument("--max-seconds", type=float, default=60.0, help="클립 최대 길이 (기본: 60)")
    parser.add_argument("--min-clips", type=int, default=3, help="최소 클립 개수 (기본: 3)")
    parser.add_argument("--max-clips", type=int, default=5, help="최대 클립 개수 (기본: 5)")
    parser.add_argument(
        "--no-offline-fallback",
        action="store_true",
        help="API 키가 없거나 호출이 실패해도 오프라인 휴리스틱으로 대체하지 않고 중단",
    )


def _add_render_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--mode", default="blur", choices=list(REFRAME_MODES),
                        help="9:16 변환 방식 (blur=블러 배경, crop=중앙 크롭)")
    parser.add_argument("--width", type=int, default=1080, help="가로 해상도 (기본: 1080)")
    parser.add_argument("--height", type=int, default=1920, help="세로 해상도 (기본: 1920)")
    parser.add_argument("--fps", type=int, default=None, help="출력 프레임레이트 (기본: 원본 유지)")
    parser.add_argument("--crf", type=int, default=20, help="x264 CRF 품질값, 낮을수록 고화질 (기본: 20)")
    parser.add_argument("--preset", default="veryfast", help="x264 프리셋 (기본: veryfast)")
    parser.add_argument("--blur-sigma", type=float, default=22.0, help="배경 블러 강도 (기본: 22)")
    parser.add_argument("--no-subtitles", action="store_true", help="자막 번인 생략")
    parser.add_argument("--font", default="NanumGothic Bold", help="자막 폰트 이름")
    parser.add_argument("--font-size", type=int, default=78, help="자막 크기 (기본: 78)")
    parser.add_argument("--no-word-highlight", action="store_true", help="단어별 노란색 강조 끄기")
    parser.add_argument("--lossless-cut", action="store_true",
                        help="스트림 복사로 먼저 무손실 컷한 뒤 렌더 (긴 원본에서 빠름, 시작점은 키프레임 스냅)")
    parser.add_argument("--overwrite", action="store_true", help="같은 이름의 결과 파일을 덮어쓴다")
    parser.add_argument("--dry-run", action="store_true", help="FFmpeg 를 실행하지 않고 명령만 출력")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="autoshorts",
        description="롱폼 영상을 AI 로 분석해 9:16 쇼츠를 자동 생성합니다.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"AutoShorts-Engine {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="전체 파이프라인 실행 (기본 명령)")
    run_parser.add_argument("source", help="유튜브 URL 또는 로컬 영상 파일 경로")
    _add_common_arguments(run_parser)
    _add_transcribe_arguments(run_parser)
    _add_analyze_arguments(run_parser)
    _add_render_arguments(run_parser)
    run_parser.add_argument("--cookies-from-browser", default=None,
                            help="로그인이 필요한 영상용 (chrome/firefox/edge 등)")

    tr_parser = subparsers.add_parser("transcribe", help="전사만 수행해 transcription.json 생성")
    tr_parser.add_argument("source", help="영상/오디오 파일 경로 또는 URL")
    _add_common_arguments(tr_parser)
    _add_transcribe_arguments(tr_parser)

    an_parser = subparsers.add_parser("analyze", help="transcription.json 으로 하이라이트만 선정")
    an_parser.add_argument("transcript", help="transcription.json 경로")
    an_parser.add_argument("--clips-out", default=None, help="선정 결과 저장 경로 (기본: 전사본 옆 clips.json)")
    _add_common_arguments(an_parser)
    _add_analyze_arguments(an_parser)

    rd_parser = subparsers.add_parser("render", help="이미 선정된 클립으로 렌더링만 수행")
    rd_parser.add_argument("video", help="원본 영상 경로")
    rd_parser.add_argument("--clips", required=True, help="clips.json 경로")
    rd_parser.add_argument("--transcript", default=None, help="transcription.json 경로 (자막 번인용)")
    _add_common_arguments(rd_parser)
    _add_render_arguments(rd_parser)

    ui_parser = subparsers.add_parser("ui", help="Gradio 웹 대시보드 실행")
    ui_parser.add_argument("--host", default="127.0.0.1", help="바인딩 주소")
    ui_parser.add_argument("--port", type=int, default=7860, help="포트")
    ui_parser.add_argument("--share", action="store_true", help="Gradio 공유 링크 생성")
    _add_common_arguments(ui_parser)

    return parser


def settings_from_args(args: argparse.Namespace) -> Settings:
    """argparse 결과를 :class:`Settings` 로 변환한다."""
    style = SubtitleStyle(
        font_name=getattr(args, "font", "NanumGothic Bold"),
        font_size=getattr(args, "font_size", 78),
        highlight_active_word=not getattr(args, "no_word_highlight", False),
    )
    return Settings(
        source=getattr(args, "source", "") or "",
        work_dir=Path(getattr(args, "work_dir", "work")),
        output_dir=Path(getattr(args, "output_dir", "output")),
        whisper_model=getattr(args, "model", "base"),
        whisper_device=getattr(args, "device", "auto"),
        whisper_compute_type=getattr(args, "compute_type", "auto"),
        language=getattr(args, "language", None),
        beam_size=getattr(args, "beam_size", 5),
        vad_filter=not getattr(args, "no_vad", False),
        gemini_api_key=getattr(args, "api_key", None),
        gemini_model=getattr(args, "gemini_model", "gemini-2.0-flash"),
        min_clip_seconds=getattr(args, "min_seconds", 30.0),
        max_clip_seconds=getattr(args, "max_seconds", 60.0),
        min_clips=getattr(args, "min_clips", 3),
        max_clips=getattr(args, "max_clips", 5),
        allow_offline_fallback=not getattr(args, "no_offline_fallback", False),
        reframe_mode=getattr(args, "mode", "blur"),
        width=getattr(args, "width", 1080),
        height=getattr(args, "height", 1920),
        fps=getattr(args, "fps", None),
        blur_sigma=getattr(args, "blur_sigma", 22.0),
        crf=getattr(args, "crf", 20),
        preset=getattr(args, "preset", "veryfast"),
        burn_subtitles=not getattr(args, "no_subtitles", False),
        lossless_cut=getattr(args, "lossless_cut", False),
        overwrite=getattr(args, "overwrite", False),
        cookies_from_browser=getattr(args, "cookies_from_browser", None),
        dry_run=getattr(args, "dry_run", False),
        subtitle_style=style,
    )


def _print_summary(result) -> None:
    print()
    print(f"✅ 완료 — 쇼츠 {len(result.renders)}개 생성 ({human_duration(result.elapsed_seconds)} 소요)")
    for render in result.renders:
        clip = render.clip
        size = f"{render.size_bytes / 1_048_576:.1f}MB" if render.size_bytes else "-"
        print(
            f"  [{clip.index}] {clip.title}\n"
            f"      {clip.start:.1f}s ~ {clip.end:.1f}s ({human_duration(clip.duration)}) "
            f"· 점수 {clip.score:g} · {size}\n"
            f"      {render.output_path}"
        )
    if result.manifest_path:
        print(f"\n  요약: {result.manifest_path}")
    if result.used_offline_analysis:
        print("\n  ⚠️  GEMINI_API_KEY 가 없어 오프라인 휴리스틱으로 구간을 골랐습니다.")
        print("      더 좋은 결과를 원하면 .env 에 무료 티어 키를 넣고 다시 실행하세요.")


def _cmd_run(args: argparse.Namespace) -> int:
    from .pipeline import run_pipeline

    settings = settings_from_args(args)
    result = run_pipeline(settings)
    if not result.renders:
        print("생성된 쇼츠가 없습니다. 로그를 확인하세요.", file=sys.stderr)
        return 1
    _print_summary(result)
    return 0


def _cmd_transcribe(args: argparse.Namespace) -> int:
    from . import downloader, transcriber
    from .utils import ensure_dir

    settings = settings_from_args(args)
    work_dir = ensure_dir(settings.work_dir)
    ingested = downloader.ingest(args.source, work_dir)
    output = work_dir / "transcription.json"
    transcript = transcriber.transcribe(
        ingested.audio_path,
        model_size=settings.whisper_model,
        device=settings.whisper_device,
        compute_type=settings.whisper_compute_type,
        language=settings.language,
        beam_size=settings.beam_size,
        vad_filter=settings.vad_filter,
        output_path=output,
    )
    print(f"✅ 전사 완료: {len(transcript)}개 문장 → {output}")
    return 0


def _cmd_analyze(args: argparse.Namespace) -> int:
    from . import ai_analyzer

    settings = settings_from_args(args)
    transcript_path = Path(args.transcript)
    transcript = Transcript.load(transcript_path)
    clips = ai_analyzer.analyze(
        transcript,
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
        min_seconds=settings.min_clip_seconds,
        max_seconds=settings.max_clip_seconds,
        min_clips=settings.min_clips,
        max_clips=settings.max_clips,
        allow_offline_fallback=settings.allow_offline_fallback,
    )
    destination = Path(args.clips_out) if args.clips_out else transcript_path.with_name("clips.json")
    destination.write_text(
        json.dumps([c.to_dict() for c in clips], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for clip in clips:
        print(f"  [{clip.index}] {clip.start:7.1f}s ~ {clip.end:7.1f}s  {clip.title}  (점수 {clip.score:g})")
    print(f"\n✅ 하이라이트 {len(clips)}개 → {destination}")
    return 0


def _cmd_render(args: argparse.Namespace) -> int:
    from . import video_renderer

    settings = settings_from_args(args)
    settings.source = args.video
    clips = [Clip.from_dict(item) for item in json.loads(Path(args.clips).read_text(encoding="utf-8"))]
    for index, clip in enumerate(clips, start=1):
        clip.index = clip.index or index
    transcript = Transcript.load(args.transcript) if args.transcript else None
    if settings.burn_subtitles and transcript is None:
        LOG.warning("--transcript 가 없어 자막 없이 렌더링합니다.")
    results = video_renderer.render_clips(args.video, clips, transcript, settings)
    for render in results:
        print(f"  ✓ {render.output_path}")
    print(f"\n✅ {len(results)}개 렌더링 완료")
    return 0 if results else 1


def _cmd_ui(args: argparse.Namespace) -> int:
    from .app import launch

    launch(host=args.host, port=args.port, share=args.share)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv()
    parser = build_parser()
    argv = list(sys.argv[1:] if argv is None else argv)
    # 서브커맨드를 생략하면 run 으로 간주한다: `autoshorts <URL>`
    if argv and argv[0] not in {"run", "transcribe", "analyze", "render", "ui", "-h", "--help", "--version"}:
        argv.insert(0, "run")
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0

    setup_logging(verbose=getattr(args, "verbose", False), quiet=getattr(args, "quiet", False))
    handlers = {
        "run": _cmd_run,
        "transcribe": _cmd_transcribe,
        "analyze": _cmd_analyze,
        "render": _cmd_render,
        "ui": _cmd_ui,
    }
    try:
        return handlers[args.command](args)
    except KeyboardInterrupt:
        print("\n중단되었습니다.", file=sys.stderr)
        return 130
    except Exception as exc:
        LOG.error("%s", exc)
        if getattr(args, "verbose", False):
            raise
        print(f"\n❌ 오류: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
