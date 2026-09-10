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
import os
import re
import shlex
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


def _add_trend_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--youtube-api-key", default=None,
                        help="YouTube Data API 키 (기본: YOUTUBE_API_KEY 환경변수)")
    parser.add_argument("--channel", action="store_true",
                        help="입력을 채널로 강제 해석 (기본: @핸들·채널 URL·UC아이디면 자동 판별)")
    parser.add_argument("--days", type=float, default=14.0, help="최근 며칠 안의 업로드만 볼지")
    parser.add_argument("--top", type=int, default=10, help="상위 몇 개를 남길지")
    parser.add_argument("--max-candidates", type=int, default=50, help="검사할 후보 영상 수")
    parser.add_argument("--min-vs", type=float, default=1.0,
                        help="최소 V/S 비율 (구독자 대비 조회수). 1.0 이면 구독자 수만큼은 봐야 통과")
    parser.add_argument("--min-subscribers", type=int, default=1000,
                        help="최소 구독자 수. 극소 채널은 V/S 가 무의미하게 커져 기본값으로 걸러낸다")
    parser.add_argument("--min-views", type=int, default=1000, help="최소 조회수")
    parser.add_argument("--min-duration", type=float, default=180.0,
                        help="원본 최소 길이(초). 기본 3분 — 이보다 짧으면 하이라이트를 뽑기 어렵다")
    parser.add_argument("--max-duration", type=float, default=None, help="원본 최대 길이(초)")
    parser.add_argument("--region", default=None, help="지역 코드 (예: KR)")
    parser.add_argument("--lang", default=None, help="관련 언어 코드 (예: ko)")
    parser.add_argument("--json", dest="json_out", default=None, help="결과를 JSON 파일로 저장")


def _add_upload_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--upload", action="store_true", help="제작한 쇼츠를 YouTube 에 업로드")
    parser.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"],
                        help="공개 범위. 기본은 비공개 — 검토 후 직접 공개하시길 권합니다")
    parser.add_argument("--publish-at", default=None,
                        help="예약 공개 시각 (예: 2026-09-15T09:00:00+09:00). 지정하면 비공개로 올라가 그 시각에 공개됩니다")
    parser.add_argument("--publish-in", default=None,
                        help="지금부터 얼마 뒤에 공개할지 (예: 6h, 2d, 90m)")
    parser.add_argument("--upload-count", type=int, default=None,
                        help="몇 개까지 올릴지 (기본: 만들어진 전부, 하루 한도 내에서)")
    parser.add_argument("--tags", default=None, help="쉼표로 구분한 태그 (예: 재테크,부업)")
    parser.add_argument("--category-id", default="22", help="YouTube 카테고리 id (기본 22=인물/블로그)")
    parser.add_argument("--made-for-kids", action="store_true", help="아동용 콘텐츠로 표시")
    parser.add_argument("--token-path", default=None, help="OAuth 토큰 경로 (기본: ~/.autoshorts/youtube_token.json)")
    parser.add_argument("--dry-run-upload", action="store_true",
                        help="쇼츠는 실제로 만들되 업로드 직전에 멈춥니다 (예약 설정 점검용)")


def _parse_publish_moment(args: argparse.Namespace):
    """--publish-at / --publish-in 을 datetime 으로 바꾼다."""
    from datetime import datetime, timedelta, timezone

    raw_at = getattr(args, "publish_at", None)
    raw_in = getattr(args, "publish_in", None)
    if raw_at and raw_in:
        raise ValueError("--publish-at 과 --publish-in 은 함께 쓸 수 없습니다.")

    if raw_at:
        text = str(raw_at).strip().replace("Z", "+00:00")
        moment = datetime.fromisoformat(text)
        return moment if moment.tzinfo else moment.astimezone()

    if raw_in:
        text = str(raw_in).strip().lower()
        units = {"m": 1, "h": 60, "d": 1440}
        unit = text[-1]
        if unit not in units:
            raise ValueError(f"--publish-in 형식은 90m / 6h / 2d 입니다: {raw_in!r}")
        try:
            amount = float(text[:-1])
        except ValueError:
            raise ValueError(f"--publish-in 형식은 90m / 6h / 2d 입니다: {raw_in!r}") from None
        return datetime.now(timezone.utc) + timedelta(minutes=amount * units[unit])
    return None


def _auto_options_from_args(args: argparse.Namespace):
    from .automation import AutoOptions

    tags = [t.strip() for t in str(getattr(args, "tags", "") or "").split(",") if t.strip()]
    return AutoOptions(
        upload=getattr(args, "upload", False),
        privacy=getattr(args, "privacy", "private"),
        publish_at=_parse_publish_moment(args),
        upload_count=getattr(args, "upload_count", None),
        tags=tags,
        category_id=getattr(args, "category_id", "22"),
        made_for_kids=getattr(args, "made_for_kids", False),
        skip_processed=not getattr(args, "allow_reprocess", False),
        trend_days=getattr(args, "days", 14.0),
        trend_min_vs=getattr(args, "min_vs", 1.0),
        trend_min_subscribers=getattr(args, "min_subscribers", 1000),
        trend_min_duration=getattr(args, "min_duration", 180.0),
        as_channel=True if getattr(args, "channel", False) else None,
        # --dry-run 은 렌더까지 건너뛰고, --dry-run-upload 는 렌더는 하되 업로드만 멈춘다
        dry_run_upload=getattr(args, "dry_run_upload", False) or getattr(args, "dry_run", False),
    )


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

    td_parser = subparsers.add_parser(
        "trend", help="키워드/채널에서 구독자 대비 조회수가 높은 급상승 영상 찾기")
    td_parser.add_argument("target", help="검색 키워드, 또는 채널(@핸들 · 채널 URL · UC아이디)")
    td_parser.add_argument("--run", action="store_true",
                           help="1위 영상을 그대로 쇼츠 파이프라인에 넘겨 원클릭으로 제작")
    _add_common_arguments(td_parser)
    _add_trend_arguments(td_parser)
    _add_transcribe_arguments(td_parser)
    _add_analyze_arguments(td_parser)
    _add_render_arguments(td_parser)

    auto_parser = subparsers.add_parser(
        "auto", help="탐색→제작→업로드를 한 번에 (예약 실행용)")
    auto_parser.add_argument("target", help="검색 키워드, 채널, 영상 URL, 또는 로컬 파일")
    auto_parser.add_argument("--allow-reprocess", action="store_true",
                             help="이미 처리한 원본도 다시 처리")
    _add_common_arguments(auto_parser)
    _add_trend_arguments(auto_parser)
    _add_upload_arguments(auto_parser)
    _add_transcribe_arguments(auto_parser)
    _add_analyze_arguments(auto_parser)
    _add_render_arguments(auto_parser)

    up_parser = subparsers.add_parser("upload", help="이미 만든 영상 파일을 업로드")
    up_parser.add_argument("video", nargs="+", help="업로드할 MP4 경로 (여러 개 가능)")
    up_parser.add_argument("--title", default=None, help="제목 (기본: 파일명에서 유추)")
    up_parser.add_argument("--description", default="", help="설명")
    _add_common_arguments(up_parser)
    _add_upload_arguments(up_parser)

    login_parser = subparsers.add_parser("login", help="YouTube 업로드용 OAuth 로그인 (최초 1회)")
    login_parser.add_argument("--client-secret", default=None,
                              help="OAuth 클라이언트 JSON 경로 (기본: ~/.autoshorts/client_secret.json)")
    login_parser.add_argument("--token-path", default=None, help="토큰 저장 경로")
    login_parser.add_argument("--port", type=int, default=0, help="로그인 콜백 포트 (기본: 임의)")
    _add_common_arguments(login_parser)

    setup_parser = subparsers.add_parser("setup", help="API 키를 입력해 .env 를 만드는 설치 마법사")
    setup_parser.add_argument("--env-path", default=".env", help=".env 저장 위치")
    setup_parser.add_argument("--non-interactive", action="store_true",
                              help="입력 없이 현재 상태만 점검")
    _add_common_arguments(setup_parser)

    doctor_parser = subparsers.add_parser("doctor", help="설치 상태 점검 (FFmpeg·의존성·키·인증)")
    _add_common_arguments(doctor_parser)

    sch_parser = subparsers.add_parser("schedule", help="집 PC 에 정기 실행 예약 등록/해제")
    sch_parser.add_argument("action", choices=["add", "remove", "show"], help="등록 / 해제 / 확인")
    sch_parser.add_argument("target", nargs="?", default=None, help="예약 실행할 대상 (키워드·채널·URL)")
    sch_parser.add_argument("--at", default="09:00", help="실행 시각 (예: 09:00)")
    sch_parser.add_argument("--weekday", default=None, help="특정 요일만 (mon~sun 또는 월~일). 생략하면 매일")
    sch_parser.add_argument("--every-hours", type=int, default=None, help="N시간마다 실행 (--at 무시)")
    sch_parser.add_argument("--log", default=None, help="실행 로그를 남길 파일 경로")
    sch_parser.add_argument("--dry-run", action="store_true", help="등록하지 않고 등록될 내용만 출력")
    sch_parser.add_argument(
        "--auto-args", default="",
        help='auto 에 넘길 추가 인자. 값이 -로 시작하면 등호를 쓰세요: --auto-args="--upload"')
    _add_common_arguments(sch_parser)

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
        youtube_api_key=getattr(args, "youtube_api_key", None),
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


def _print_trend_table(videos, quota_used: int) -> None:
    print()
    print(f"{'순위':>4}  {'V/S':>6}  {'조회수':>10}  {'구독자':>10}  {'경과':>7}  {'길이':>7}  제목")
    print("-" * 100)
    for video in videos:
        print(
            f"{video.rank:>4}  {video.vs_ratio:>6.2f}  {video.view_count:>10,}  "
            f"{video.subscriber_count:>10,}  {video.age_hours:>6.0f}h  "
            f"{human_duration(video.duration_seconds):>7}  {video.title[:44]}"
        )
        print(f"{'':>4}  {video.url}  · {video.channel_title}")
    print(f"\n할당량 {quota_used} 유닛 사용 (무료 한도 하루 10,000)")


def _cmd_trend(args: argparse.Namespace) -> int:
    from . import trend_finder

    settings = settings_from_args(args)
    videos, quota_used = trend_finder.find_trending(
        args.target,
        api_key=settings.youtube_api_key,
        days=args.days,
        limit=args.top,
        max_candidates=args.max_candidates,
        min_vs_ratio=args.min_vs,
        min_subscribers=args.min_subscribers,
        min_views=args.min_views,
        min_duration=args.min_duration,
        max_duration=args.max_duration,
        as_channel=True if args.channel else None,
        region_code=args.region,
        relevance_language=args.lang,
    )

    if not videos:
        print("조건에 맞는 급상승 영상을 찾지 못했습니다.", file=sys.stderr)
        print("  --days 를 늘리거나 --min-vs / --min-subscribers 를 낮춰 보세요.", file=sys.stderr)
        return 1

    _print_trend_table(videos, quota_used)

    if args.json_out:
        destination = Path(args.json_out)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps([v.to_dict() for v in videos], ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n결과 저장: {destination}")

    if not args.run:
        print("\n1위 영상으로 바로 쇼츠를 만들려면 --run 을 붙이세요.")
        return 0

    from .pipeline import run_pipeline

    top = videos[0]
    print(f"\n▶ 1위 영상으로 쇼츠 제작을 시작합니다: {top.title}")
    print(f"  {top.url}\n")
    settings.source = top.url
    result = run_pipeline(settings)
    if not result.renders:
        print("생성된 쇼츠가 없습니다. 로그를 확인하세요.", file=sys.stderr)
        return 1
    _print_summary(result)
    return 0


def _print_auto_result(result) -> int:
    if result.skipped_reason:
        print(f"\n건너뜀: {result.skipped_reason}")
        return 0
    if not result.renders:
        print("생성된 쇼츠가 없습니다.", file=sys.stderr)
        return 1

    print(f"\n✅ 원본: {result.title}")
    print(f"   {result.source_url}")
    for render in result.renders:
        print(f"   · {render.output_path}")
    for uploaded in result.uploads:
        when = f" · {uploaded.publish_at:%Y-%m-%d %H:%M} 공개 예약" if uploaded.publish_at else ""
        print(f"   ⬆ {uploaded.shorts_url}  ({uploaded.privacy}{when})")
    for error in result.upload_errors:
        print(f"   ⚠ 업로드 실패 — {error}", file=sys.stderr)
    if result.quota_used:
        print(f"\n   API 할당량 {result.quota_used} 유닛 사용")
    return 1 if result.upload_errors and not result.uploads else 0


def _cmd_auto(args: argparse.Namespace) -> int:
    from .automation import run_auto

    settings = settings_from_args(args)
    options = _auto_options_from_args(args)

    if options.upload and options.privacy == "public":
        print("⚠️  공개(public)로 바로 올립니다. 남의 영상을 재편집한 것이라면 저작권 신고 대상이 될 수 있습니다.\n")

    result = run_auto(settings, args.target, options)
    return _print_auto_result(result)


def _cmd_upload(args: argparse.Namespace) -> int:
    from . import uploader
    from .uploader import UploadRequest

    publish_at = _parse_publish_moment(args)
    tags = [t.strip() for t in str(args.tags or "").split(",") if t.strip()]
    failures = 0

    for path_text in args.video:
        path = Path(path_text)
        if not path.exists():
            print(f"❌ 파일 없음: {path}", file=sys.stderr)
            failures += 1
            continue

        title = args.title or _title_from_filename(path)
        request = UploadRequest(
            video_path=path, title=title, description=args.description, tags=tags,
            category_id=args.category_id, privacy=args.privacy, publish_at=publish_at,
            made_for_kids=args.made_for_kids,
        )
        try:
            result = uploader.upload_video(request, token_path=args.token_path)
            when = f" · {result.publish_at:%Y-%m-%d %H:%M} 공개 예약" if result.publish_at else ""
            print(f"✅ {result.shorts_url}  ({result.privacy}{when})")
        except Exception as exc:
            print(f"❌ {path.name}: {exc}", file=sys.stderr)
            failures += 1
    return 1 if failures else 0


def _title_from_filename(path: Path) -> str:
    """``output_01_제목.mp4`` 에서 제목만 뽑아낸다."""
    stem = path.stem
    match = re.match(r"^output_\d+_(.+)$", stem)
    if match:
        stem = match.group(1)
    return stem.replace("_", " ").strip() or stem


def _cmd_login(args: argparse.Namespace) -> int:
    from . import uploader

    try:
        uploader.run_oauth_flow(args.client_secret, args.token_path, port=args.port)
    except Exception as exc:
        print(f"❌ 로그인 실패: {exc}", file=sys.stderr)
        return 1
    token = Path(args.token_path or uploader.default_token_path()).expanduser()
    print(f"✅ 로그인 완료. 토큰 저장: {token}")
    print("   이제 `autoshorts auto ... --upload` 가 브라우저 없이 동작합니다.")
    return 0


def _prompt_secret(label: str, current: str | None) -> str:
    """키를 입력받는다. 엔터만 치면 기존 값을 유지한다."""
    import getpass

    masked = f"(현재: ****{current[-4:]})" if current else "(미설정)"
    try:
        value = getpass.getpass(f"  {label} {masked}\n  > ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return current or ""
    return value or (current or "")


def _cmd_setup(args: argparse.Namespace) -> int:
    from .config import load_dotenv

    env_path = Path(args.env_path)
    load_dotenv(env_path)
    existing = {
        "GEMINI_API_KEY": os.environ.get("GEMINI_API_KEY", ""),
        "YOUTUBE_API_KEY": os.environ.get("YOUTUBE_API_KEY", ""),
    }

    print("\n=== AutoShorts-Engine 설치 마법사 ===\n")
    print("입력한 키는 이 컴퓨터의 .env 파일에만 저장되며 어디로도 전송되지 않습니다.")
    print("엔터만 치면 기존 값을 유지합니다. 비워 두어도 대부분의 기능은 동작합니다.\n")

    if args.non_interactive:
        return _cmd_doctor(args)

    print("① Gemini API 키 — 하이라이트 선정 품질을 높입니다 (없으면 오프라인 분석)")
    print("   발급: https://aistudio.google.com/apikey")
    gemini = _prompt_secret("GEMINI_API_KEY", existing["GEMINI_API_KEY"])

    print("\n② YouTube Data API 키 — 급상승 영상 탐색에 필요합니다 (조회 전용)")
    print("   발급: https://console.cloud.google.com → YouTube Data API v3 사용 설정")
    youtube = _prompt_secret("YOUTUBE_API_KEY", existing["YOUTUBE_API_KEY"])

    lines = [
        "# AutoShorts-Engine 설정 — 이 파일은 저장소에 올리지 마세요.",
        f"GEMINI_API_KEY={gemini}",
        "GEMINI_MODEL=gemini-2.0-flash",
        f"YOUTUBE_API_KEY={youtube}",
        "",
    ]
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text("\n".join(lines), encoding="utf-8")
    try:
        env_path.chmod(0o600)
    except OSError:
        pass
    print(f"\n✅ 저장 완료: {env_path.resolve()}")

    print("\n③ 업로드 인증 (선택) — 쇼츠를 자동 업로드하려면 필요합니다.")
    print("   Google Cloud Console 에서 '데스크톱 앱' OAuth 클라이언트 JSON 을 받아")
    print(f"   {uploader_default_secret()} 에 두고 `autoshorts login` 을 실행하세요.")
    print("\n다음 단계: autoshorts doctor  로 설치 상태를 점검하세요.")
    return 0


def uploader_default_secret() -> str:
    from .uploader import default_client_secret_path

    return str(default_client_secret_path())


def _check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"  {'✅' if ok else '❌'} {label}{(' — ' + detail) if detail else ''}")
    return ok


def _cmd_doctor(args: argparse.Namespace) -> int:
    from .config import Settings, load_dotenv
    from .utils import ToolNotFoundError, which_or_raise

    load_dotenv()
    print("\n=== 설치 상태 점검 ===\n")
    problems = 0

    print("필수")
    try:
        ffmpeg = which_or_raise("ffmpeg")
        _check("FFmpeg", True, ffmpeg)
    except ToolNotFoundError as exc:
        problems += 1
        _check("FFmpeg", False, str(exc))

    for module, label, hint in [
        ("yt_dlp", "yt-dlp (영상 다운로드)", "pip install yt-dlp"),
        ("faster_whisper", "faster-whisper (음성 인식)", "pip install faster-whisper"),
    ]:
        try:
            __import__(module)
            _check(label, True)
        except ImportError:
            problems += 1
            _check(label, False, hint)

    print("\n선택")
    settings = Settings(source="x")
    _check("GEMINI_API_KEY (하이라이트 선정)", settings.has_gemini,
           "" if settings.has_gemini else "없으면 오프라인 휴리스틱으로 동작합니다")
    _check("YOUTUBE_API_KEY (급상승 탐색)", settings.has_youtube_api,
           "" if settings.has_youtube_api else "trend 명령을 쓰려면 필요합니다")

    for module, label, hint in [
        ("googleapiclient", "google-api-python-client (업로드)", "pip install google-api-python-client"),
        ("google_auth_oauthlib", "google-auth-oauthlib (업로드 인증)", "pip install google-auth-oauthlib"),
        ("gradio", "gradio (웹 UI)", "pip install gradio"),
    ]:
        try:
            __import__(module)
            _check(label, True)
        except ImportError:
            _check(label, False, hint)

    from .uploader import default_token_path

    token = default_token_path()
    _check("YouTube 업로드 로그인", token.exists(),
           str(token) if token.exists() else "업로드하려면 `autoshorts login` 실행")

    print("\n예약")
    from . import scheduler

    try:
        current = scheduler.show_schedule()
    except Exception as exc:
        current = f"확인 실패: {exc}"
    print(f"  플랫폼: {scheduler.detect_platform()}")
    for line in str(current).splitlines()[:6]:
        print(f"  {line}")

    print()
    if problems:
        print(f"❌ 필수 항목 {problems}건이 빠졌습니다. 위 안내대로 설치하세요.")
        return 1
    print("✅ 필수 항목은 모두 준비됐습니다.")
    return 0


def _cmd_schedule(args: argparse.Namespace) -> int:
    from . import scheduler

    if args.action == "show":
        print(scheduler.show_schedule())
        return 0

    if args.action == "remove":
        removed = scheduler.remove_schedule()
        print("✅ 예약을 해제했습니다." if removed else "등록된 예약이 없습니다.")
        return 0

    if not args.target:
        print("등록하려면 대상을 지정하세요. 예: autoshorts schedule add \"재테크\" --at 09:00",
              file=sys.stderr)
        return 1

    try:
        if args.every_hours:
            schedule = scheduler.Schedule(every_hours=args.every_hours)
        else:
            hour, minute = scheduler.parse_time(args.at)
            schedule = scheduler.Schedule(
                hour=hour, minute=minute, weekday=scheduler.parse_weekday(args.weekday)
            )
    except ValueError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    extra = shlex.split(args.auto_args or "")
    extra += list(getattr(args, "passthrough", None) or [])
    command = scheduler.build_auto_command(args.target, extra_args=extra)

    try:
        registered = scheduler.install_schedule(
            schedule, command, log_path=args.log, dry_run=args.dry_run
        )
    except scheduler.ScheduleError as exc:
        print(f"❌ 예약 등록 실패: {exc}", file=sys.stderr)
        return 1

    print(f"\n{'등록될 내용 (dry-run)' if args.dry_run else '✅ 예약 등록 완료'}: {schedule.description}")
    print(f"\n{registered}\n")
    if not args.dry_run:
        print("확인: autoshorts schedule show   ·   해제: autoshorts schedule remove")
        if "--upload" in extra:
            print("\n업로드가 포함돼 있습니다. `autoshorts login` 을 미리 해 두어야 무인 실행이 됩니다.")
    return 0


def _cmd_ui(args: argparse.Namespace) -> int:
    from .app import launch

    launch(host=args.host, port=args.port, share=args.share)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv()
    parser = build_parser()
    argv = list(sys.argv[1:] if argv is None else argv)
    # 서브커맨드를 생략하면 run 으로 간주한다: `autoshorts <URL>`
    known = {"run", "transcribe", "analyze", "render", "trend", "auto", "upload",
             "login", "setup", "doctor", "schedule", "ui", "-h", "--help", "--version"}
    if argv and argv[0] not in known:
        argv.insert(0, "run")

    # `schedule add ... -- --upload --max-clips 2` 처럼 `--` 뒤에 온 인자는
    # auto 명령에 그대로 넘긴다. argparse 는 옵션 사이에 낀 위치 인자를 안정적으로
    # 다루지 못해 파싱 전에 직접 분리한다.
    passthrough: list[str] = []
    if "--" in argv:
        index = argv.index("--")
        passthrough = argv[index + 1:]
        argv = argv[:index]

    args = parser.parse_args(argv)
    if passthrough:
        args.passthrough = passthrough
    if not args.command:
        parser.print_help()
        return 0

    setup_logging(verbose=getattr(args, "verbose", False), quiet=getattr(args, "quiet", False))
    handlers = {
        "run": _cmd_run,
        "transcribe": _cmd_transcribe,
        "analyze": _cmd_analyze,
        "render": _cmd_render,
        "trend": _cmd_trend,
        "auto": _cmd_auto,
        "upload": _cmd_upload,
        "login": _cmd_login,
        "setup": _cmd_setup,
        "doctor": _cmd_doctor,
        "schedule": _cmd_schedule,
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
