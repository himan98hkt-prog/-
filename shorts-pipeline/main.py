#!/usr/bin/env python3
"""이미지 → 연속 전진 영상 → YouTube/Instagram 자동 업로드.

  python main.py generate --image photo.png --clips 6 --interactive
  python main.py generate --image photo.png --model hailuo_23_pro --no-upscale
  python main.py resume   --run 20260821_1930
  python main.py stitch   --run 20260821_1930
  python main.py publish  --run 20260821_1930 --youtube --title "..."
  python main.py estimate --clips 12
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

import typer

# SHORTS_MOCK=1 로 실행하면 가짜 provider 를 붙여 API 비용 없이 화면을 둘러볼 수 있다.
if os.getenv("SHORTS_MOCK"):
    import tests.mock_provider  # noqa: F401

from pipeline import music
from pipeline.config import Config, ConfigError, load_config
from pipeline.content import Content, load_content
from pipeline.costs import actual_cost, estimate
from pipeline.ffmpeg_util import FFmpegError, ensure_ffmpeg
from pipeline.generator import GenerationStats
from pipeline.modes import Aborted, orchestrate
from pipeline.providers import ProviderError
from pipeline.runlog import Run
from pipeline.stitcher import stitch
from pipeline.validator import ValidationError, prepare_input

app = typer.Typer(add_completion=False, help=__doc__)
RUNS_DIR = Path(__file__).parent / "runs"


def _die(message: str) -> None:
    typer.secho(f"\n✗ {message}\n", fg=typer.colors.RED, err=True)
    raise typer.Exit(code=1)


def _load(config: str, **overrides) -> Config:
    try:
        return load_config(config, **overrides)
    except ConfigError as exc:
        _die(str(exc))
        raise  # 도달하지 않음. 타입 체커용.


def _confirm_cost(cfg: Config, assume_yes: bool) -> None:
    est = estimate(cfg)
    typer.echo(est.render())
    if est.over_cap:
        _die(
            f"예상 비용 ${est.expected:.2f} 가 상한 ${est.hard_cap:.2f} 를 넘습니다.\n"
            "  config.yaml 의 cost.hard_cap_usd 를 올리거나 클립 수를 줄이세요."
        )
    if not assume_yes and not typer.confirm("계속할까요?", default=False):
        raise typer.Exit(code=0)


def _now() -> str:
    from datetime import datetime
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _resolve_audio(cfg: Config, run: Run, out: dict):
    """output.audio 를 실제 ffmpeg 인자로 바꾼다.

    auto 면 시드의 테마에 맞는 곡을 music/ 에서 고른다. 곡이 하나도 없으면
    무음으로 간다 — 여기서 멈추면 하루치 영상이 통째로 날아간다.
    """
    from pipeline import music

    mode = str(out.get("audio", "silent") or "silent").lower()
    if mode != "auto":
        return mode, out.get("audio_file"), None

    seed = Path(run.state.get("seed_image") or "")
    theme = _theme_of_seed(seed)
    track = music.pick(theme, seed.stem or run.run_id,
                       Path(out.get("music_dir") or "music"))
    if track is None:
        typer.secho("  ⚠ music/ 에 곡이 없어 무음으로 만듭니다. "
                    "수노에서 만든 곡을 music/bright 같은 폴더에 넣으세요.",
                    fg=typer.colors.YELLOW)
        return "silent", None, None
    return "file", str(track.path), track


def _theme_of_seed(seed: Path) -> str:
    """시드 사이드카에 적힌 테마를 먼저 보고, 없으면 파일명으로 분류한다."""
    from pipeline.curate import classify
    from pipeline.intake import read_sidecar

    if not seed.name:
        return "misc"
    side = read_sidecar(seed)
    if side.get("theme"):
        return side["theme"]
    if side.get("source"):
        return classify(Path(side["source"]))
    return classify(seed)


def _finalize(cfg: Config, run: Run, clips: list[Path], stats: GenerationStats) -> None:
    """합성 + 결과 요약."""
    typer.echo(f"\n  클립 {len(clips)}개를 합성합니다…")
    out = cfg.output
    transition = (
        "fade" if cfg.mode == "chain" else cfg.montage_transition
    )
    crossfade = (
        cfg.crossfade_seconds if cfg.mode == "chain" else cfg.montage_transition_seconds
    )
    audio_mode, audio_file, track = _resolve_audio(cfg, run, out)
    if track:
        typer.echo(f"  음악   : {track.name}  ({music.MOOD_LABEL.get(track.mood, track.mood)})")
    result = stitch(
        clips, run.final,
        width=out["width"], height=out["height"], fps=out["fps"],
        crf=out.get("crf", 18),
        crossfade=crossfade, transition=transition,
        audio=audio_mode, audio_file=audio_file,
    )
    spent = actual_cost(cfg, stats.clip_calls, stats.upscale_calls)
    run.save_state(
        final=str(result.path), duration=round(result.duration, 2),
        clip_calls=stats.clip_calls, upscale_calls=stats.upscale_calls,
        cost_usd=round(spent, 4),
        # 어떤 곡이 들어갔는지 남긴다. 화면에서 "음악 있음/무음" 을 보여주고,
        # 소리가 안 들릴 때 무엇을 확인해야 하는지 바로 알 수 있게 한다.
        music=(track.name if track else None),
        final_res=[out["width"], out["height"]],
    )
    run.log("run.finished", duration=result.duration, cost_usd=spent)

    typer.secho("\n✓ 완료", fg=typer.colors.GREEN, bold=True)
    typer.echo(f"  파일   : {result.path}")
    typer.echo(f"  화질   : {out['width']}x{out['height']}"
               + (f"  (모델 출력 {src[0]}x{src[1]})"
                  if (src := run.state.get("source_res")) else ""))
    typer.echo(f"  길이   : {result.duration:.2f}초")
    typer.echo(f"  크기   : {result.size_mb:.1f} MB")
    typer.echo(
        f"  비용   : ${spent:.2f}  "
        f"(영상 {stats.clip_calls}회, 업스케일 {stats.upscale_calls}회)"
    )


# ══════════════════════════════════════════════════════════════════════
@app.command()
def generate(
    image: str = typer.Option(..., "--image", "-i", help="입력 이미지 (png/jpg)"),
    config: str = typer.Option("config.yaml", "--config", "-c"),
    clips: Optional[int] = typer.Option(None, "--clips", help="클립 수 (config 덮어쓰기)"),
    duration: Optional[int] = typer.Option(None, "--duration", help="클립당 초"),
    mode: Optional[str] = typer.Option(None, "--mode", help="chain | montage"),
    model: Optional[str] = typer.Option(None, "--model"),
    provider: Optional[str] = typer.Option(None, "--provider", help="fal | higgsfield"),
    upscale: Optional[bool] = typer.Option(
        None, "--upscale/--no-upscale", help="클립 사이 프레임 업스케일"
    ),
    pad: bool = typer.Option(False, "--pad", help="9:16 변환 시 크롭 대신 블러 패딩"),
    scenes: Optional[list[str]] = typer.Option(
        None, "--scenes", help="montage 모드에서 장면마다 쓸 이미지 (여러 번 지정)"),
    interactive: bool = typer.Option(False, "--interactive", help="회차마다 품질 확인"),
    assume_yes: bool = typer.Option(False, "--yes", "-y", help="비용 확인 생략"),
):
    """이미지 1장에서 연속 영상을 만든다."""
    cfg = _load(
        config, num_clips=clips, clip_duration=duration, mode=mode,
        model=model, provider=provider, upscale_between_clips=upscale,
    )
    try:
        ensure_ffmpeg()
    except FFmpegError as exc:
        _die(str(exc))

    _confirm_cost(cfg, assume_yes)

    run = Run.create(RUNS_DIR)
    typer.echo(f"\n▶ run {run.run_id}  (mode={cfg.mode}, {cfg.provider}/{cfg.model_key})")
    run.log("run.started", config=cfg.raw, image=str(image))
    # 배경음악을 고를 때 시드의 테마가 필요하다. resume 에서도 쓰므로 남긴다.
    run.save_state(seed_image=str(image))

    try:
        warnings = prepare_input(
            image, run.input_image, pad=pad,
            width=cfg.output["width"], height=cfg.output["height"],
        )
    except ValidationError as exc:
        _die(str(exc))
    for w in warnings:
        typer.secho(f"  {w}", fg=typer.colors.YELLOW)

    # montage 에서 장면별 이미지를 받았으면 frames/seed_NN.png 로 깔아둔다
    if scenes:
        for i, scene in enumerate(scenes, start=1):
            src = Path(scene)
            if not src.exists():
                _die(f"장면 이미지가 없습니다: {src}")
            try:
                prepare_input(src, run.seed(i), pad=pad,
                              width=cfg.output["width"], height=cfg.output["height"])
            except ValidationError as exc:
                _die(str(exc))
        typer.echo(f"  장면 이미지 {len(scenes)}장을 준비했습니다.")
        if cfg.mode == "montage" and len(scenes) < cfg.num_clips:
            typer.secho(
                f"  ⓘ 장면 {len(scenes)}장 < 클립 {cfg.num_clips}개 — "
                f"모자란 만큼은 입력 이미지를 씁니다. --clips {len(scenes)} 를 권합니다.",
                fg=typer.colors.YELLOW)

    # 시드 옆의 사이드카(.yaml/.txt)에서 이 영상의 제목·훅·프롬프트를 읽는다.
    content = load_content(Path(image))
    _apply_content(cfg, run, content)

    _execute(cfg, run, interactive=interactive, resume=False)


def _apply_content(cfg: Config, run: Run, content: Content) -> None:
    """사이드카 내용을 config 에 얹고 run 상태에 남긴다.

    여기서 저장해 둔 값을 publish 가 그대로 쓴다. 그래서 생성과 업로드를
    따로 실행해도 제목·설명이 이어진다.
    """
    if content.prompt:
        cfg.motion_prompt = content.prompt
    if content.scene_prompts:
        cfg.scene_prompts = content.scene_prompts

    run.save_state(content={
        "title": content.title,
        "hook": content.hook,
        "prompt": content.prompt,
        "scene_prompts": content.scene_prompts,
        "tags": content.tags,
    })
    where = content.source.name if content.source else "파일명"
    typer.echo(f"  제목: {content.title}  ({where})")
    if content.hook:
        typer.echo(f"  훅  : {content.hook}")
    if not content.source:
        typer.secho(
            "  ⓘ 사이드카가 없어 파일명을 제목으로 씁니다. "
            "seeds/{이름}.yaml 을 만들면 제목·설명을 지정할 수 있습니다.",
            fg=typer.colors.YELLOW)


@app.command()
def resume(
    run_id: str = typer.Option(..., "--run", help="이어서 진행할 run ID"),
    config: str = typer.Option("config.yaml", "--config", "-c"),
    interactive: bool = typer.Option(False, "--interactive"),
    assume_yes: bool = typer.Option(False, "--yes", "-y"),
):
    """중단된 실행을 이어서 완료한다."""
    cfg = _load(config)
    try:
        ensure_ffmpeg()
        run = Run.load(RUNS_DIR, run_id)
    except (FFmpegError, FileNotFoundError) as exc:
        _die(str(exc))

    done = run.completed_clips()
    remaining = max(0, cfg.num_clips - len(done))
    typer.echo(f"▶ run {run_id}: 완료 {len(done)}개, 남은 {remaining}개")
    if remaining == 0:
        typer.echo("  모든 클립이 이미 있습니다. 합성만 진행합니다.")
        _finalize(cfg, run, [run.clip(n) for n in done], GenerationStats())
        return
    if not assume_yes:
        _confirm_cost(cfg, assume_yes)

    _execute(cfg, run, interactive=interactive, resume=True)


def _execute(cfg: Config, run: Run, *, interactive: bool, resume: bool) -> None:
    try:
        clips, stats = orchestrate(cfg, run, interactive=interactive, resume=resume)
    except Aborted as exc:
        typer.secho(f"\n중단됨: {exc}", fg=typer.colors.YELLOW)
        raise typer.Exit(code=0)
    except ProviderError as exc:
        run.log("run.failed", error=str(exc))
        partial = run.completed_clips()
        if partial and typer.confirm(
            f"\n생성 실패했습니다. 지금까지 만든 {len(partial)}개로 합성할까요?",
            default=True,
        ):
            _finalize(cfg, run, [run.clip(n) for n in partial], GenerationStats())
            return
        _die(f"{exc}\n  이어하기: python main.py resume --run {run.run_id}")

    try:
        _finalize(cfg, run, clips, stats)
    except FFmpegError as exc:
        _die(f"{exc}\n  합성만 다시: python main.py stitch --run {run.run_id}")


@app.command("stitch")
def stitch_cmd(
    run_id: str = typer.Option(..., "--run"),
    config: str = typer.Option("config.yaml", "--config", "-c"),
):
    """이미 만들어진 클립으로 합성만 다시 실행한다."""
    cfg = _load(config)
    try:
        ensure_ffmpeg()
        run = Run.load(RUNS_DIR, run_id)
    except (FFmpegError, FileNotFoundError) as exc:
        _die(str(exc))
    done = run.completed_clips()
    if not done:
        _die(f"run {run_id} 에 합성할 클립이 없습니다.")
    _finalize(cfg, run, [run.clip(n) for n in done], GenerationStats())


@app.command("estimate")
def estimate_cmd(
    config: str = typer.Option("config.yaml", "--config", "-c"),
    clips: Optional[int] = typer.Option(None, "--clips"),
    duration: Optional[int] = typer.Option(None, "--duration"),
    model: Optional[str] = typer.Option(None, "--model"),
    provider: Optional[str] = typer.Option(None, "--provider"),
    compare: bool = typer.Option(False, "--compare", help="모든 모델 단가를 비교"),
):
    """API 를 부르지 않고 비용만 계산한다."""
    cfg = _load(config, num_clips=clips, clip_duration=duration,
                model=model, provider=provider)
    if not compare:
        typer.echo(estimate(cfg).render())
        return

    typer.echo(
        f"\n{cfg.num_clips}클립 x {cfg.clip_duration}초 "
        f"(= {cfg.num_clips * cfg.clip_duration}초) 기준 비교\n"
    )
    header = f"{'provider':<12} {'model':<22} {'클립당':>9} {'소계':>9} {'x재시도':>10}"
    typer.echo(header)
    typer.echo("─" * len(header))
    rows, skipped = [], []
    for pname, pcfg in cfg.raw["providers"].items():
        # 업스케일러 키는 provider 마다 다르다. 해당 provider 것으로 갈아끼운다.
        ups = list(pcfg.get("upscalers", {}))
        upscaler = ups[0] if ups else None
        for mname in pcfg.get("models", {}):
            try:
                sub = load_config(
                    config, num_clips=cfg.num_clips,
                    clip_duration=cfg.clip_duration,
                    provider=pname, model=mname,
                    upscaler=upscaler,
                    upscale_between_clips=cfg.upscale_between_clips and bool(upscaler),
                )
                est = estimate(sub)
            except ConfigError as exc:
                # 대개 clip_duration 이 모델 상한을 넘는 경우다.
                skipped.append(f"{pname}/{mname}: {exc}")
                continue
            rows.append((est.expected, pname, mname, est))
    for _, pname, mname, est in sorted(rows):
        typer.echo(
            f"{pname:<12} {mname:<22} ${est.cost_per_clip:>8.4f} "
            f"${est.subtotal:>8.2f} ${est.expected:>9.2f}"
        )
    for note in skipped:
        typer.secho(f"  (제외) {note}", fg=typer.colors.YELLOW)
    typer.echo("")


@app.command("publish")
def publish_cmd(
    run_id: str = typer.Option(..., "--run"),
    config: str = typer.Option("config.yaml", "--config", "-c"),
    title: str = typer.Option("", "--title"),
    description: str = typer.Option("", "--description"),
    youtube: bool = typer.Option(False, "--youtube"),
    instagram: bool = typer.Option(False, "--instagram"),
    video_url: str = typer.Option("", "--video-url", help="인스타그램용 공개 mp4 URL"),
    publish_at: str = typer.Option(
        "", "--publish-at",
        help="유튜브 공개 예약 시각 (예: 2026-08-25T21:00). "
             "지금 올리고 그 시각에 공개하므로 컴퓨터가 꺼져 있어도 됩니다."),
    dry_run: bool = typer.Option(False, "--dry-run"),
):
    """완성된 영상을 업로드한다."""
    cfg = _load(config)
    try:
        run = Run.load(RUNS_DIR, run_id)
    except FileNotFoundError as exc:
        _die(str(exc))
    if not run.final.exists():
        _die(f"최종 영상이 없습니다: {run.final}\n  먼저 stitch 를 실행하세요.")

    # --title 이 없으면 generate 때 저장해 둔 사이드카 내용을 쓴다.
    saved = run.state.get("content", {})
    title = title or saved.get("title") or f"AI DEOKHU {run.run_id}"
    description = description or saved.get("hook") or title

    if not youtube and not instagram:
        _die("--youtube 또는 --instagram 중 하나 이상을 지정하세요.")

    # 결과를 run 상태에 남긴다. 예전에는 log.jsonl 에만 적어서, 화면에서는
    # 무엇이 올라갔는지 확인할 방법이 없었다.
    done = dict(run.state.get("published") or {})
    failed = []

    def record(target: str, **fields) -> None:
        done[target] = {"at": _now(), "dry_run": dry_run, **fields}
        run.save_state(published=done)

    if youtube:
        from publish import youtube as yt
        yc = cfg.publish_cfg.get("youtube", {})
        typer.echo("\n  유튜브에 올리는 중…")
        try:
            res = yt.upload(
                run.final,
                title=yc.get("title_template", "{title}").format(title=title),
                description=yc.get("description_template", "{description}")
                            .format(description=description),
                tags=yc.get("tags", []),
                privacy=yc.get("privacy", "private"),
                category_id=str(yc.get("category_id", "24")),
                state_dir=RUNS_DIR,
                daily_cap=int(yc.get("daily_upload_cap", 90)),
                publish_at=publish_at or None,
                dry_run=dry_run,
            )
        except yt.UploadError as exc:
            # 여기서 죽으면 인스타는 시도조차 못 한다. 실제로 "둘 다" 를
            # 눌렀을 때 한쪽 실패가 다른 쪽까지 막고 있었다.
            typer.secho(f"✗ YouTube 실패: {exc}", fg=typer.colors.RED)
            record("youtube", ok=False, error=str(exc))
            failed.append(("유튜브", str(exc)))
        else:
            typer.secho(f"✓ YouTube: {res.url}", fg=typer.colors.GREEN)
            run.log("publish.youtube", video_id=res.video_id, url=res.url)
            record("youtube", ok=True, url=res.url, video_id=res.video_id,
                   publish_at=publish_at or None)
            if publish_at:
                typer.echo(f"    {publish_at} 에 공개됩니다 "
                           "(그때 컴퓨터가 꺼져 있어도 됩니다).")

    if instagram:
        from publish import instagram as ig
        ic = cfg.publish_cfg.get("instagram", {})
        typer.echo("\n  인스타그램에 올리는 중…")
        uploaded = None
        try:
            # _resolve_media_url 은 실패하면 _die -> typer.Exit 을 던진다.
            # typer.Exit 은 RuntimeError 를 상속하므로 넓게 잡으면 이유가
            # 빈 문자열로 기록되고, 안 잡으면 인스타 실패가 기록조차 안 된다.
            # (click.exceptions.Exit 을 잡아도 안 된다 — typer 는 자기 것을 쓴다.)
            try:
                url, uploaded = _resolve_media_url(cfg, run, video_url, dry_run)
            except typer.Exit as exc:
                raise ig.UploadError(
                    "인스타그램에 넘길 공개 URL 이 없습니다. "
                    "[설정] 탭에서 영상 보관함(R2)을 연결하세요."
                ) from exc
            res = ig.upload(
                url,
                caption=ic.get("caption_template", "{description}")
                          .format(description=description),
                share_to_feed=bool(ic.get("share_to_feed", True)),
                dry_run=dry_run,
            )
        except (ig.UploadError, OSError) as exc:
            typer.secho(f"✗ Instagram 실패: {exc}", fg=typer.colors.RED)
            record("instagram", ok=False, error=str(exc))
            failed.append(("인스타그램", str(exc)))
        else:
            typer.secho(f"✓ Instagram: {res.permalink or res.media_id}",
                        fg=typer.colors.GREEN)
            run.log("publish.instagram", media_id=res.media_id,
                    permalink=res.permalink)
            record("instagram", ok=True, url=res.permalink, media_id=res.media_id)

            # 발행이 끝났으면 스토리지를 비워 비용을 아낀다.
            sc = cfg.publish_cfg.get("storage", {})
            if uploaded and sc.get("delete_after_publish") and not dry_run:
                from publish.storage import S3Storage
                S3Storage.from_env(sc).delete(uploaded.key)
                typer.echo(f"  S3 객체 삭제: {uploaded.key}")

    if failed:
        names = " · ".join(n for n, _ in failed)
        _die(f"{names} 업로드에 실패했습니다.\n  "
             + "\n  ".join(f"{n}: {e}" for n, e in failed))


def _resolve_media_url(cfg: Config, run: Run, video_url: str, dry_run: bool):
    """인스타그램에 넘길 공개 URL 을 확보한다.

    --video-url 이 있으면 그대로 쓰고, 없으면 S3 에 올려서 만든다.
    반환값의 두 번째 요소는 업로드한 객체(정리용) 또는 None.
    """
    import os

    if video_url:
        return video_url, None

    sc = cfg.publish_cfg.get("storage", {})
    if sc.get("enabled", False):
        from publish.storage import S3Storage, StorageError
        try:
            storage = S3Storage.from_env(sc)
        except StorageError as exc:
            _die(str(exc))
        if dry_run:
            key = storage.key_for(run.final, run.run_id)
            typer.echo(f"  [dry-run] S3 업로드 생략: s3://{storage.bucket}/{key}")
            return f"https://example.invalid/{key}", None
        typer.echo(f"  S3 업로드 중… ({run.final.stat().st_size / 1048576:.1f} MB)")
        try:
            obj = storage.upload(run.final, run_id=run.run_id)
        except StorageError as exc:
            _die(str(exc))
        note = (
            f", {obj.expires_at:%H:%M UTC} 만료" if obj.is_temporary else ", 영구 공개"
        )
        typer.echo(f"  ✓ s3://{obj.bucket}/{obj.key} ({obj.size_mb:.1f} MB{note})")
        run.log("publish.storage", bucket=obj.bucket, key=obj.key,
                expires_at=obj.expires_at)
        return obj.url, obj

    # 스토리지가 꺼져 있으면 예전 방식대로 base URL 조합을 시도한다.
    base = os.getenv("PUBLIC_MEDIA_BASE_URL", "").rstrip("/")
    if base:
        return f"{base}/{run.run_id}/final.mp4", None

    _die(
        "인스타그램에 넘길 공개 URL 이 없습니다. 셋 중 하나를 하세요.\n"
        "  1) config.yaml 의 publish.storage.enabled 를 true 로 두고 S3_BUCKET 설정\n"
        "  2) --video-url 로 직접 URL 지정\n"
        "  3) .env 의 PUBLIC_MEDIA_BASE_URL 설정"
    )


@app.command("upload")
def upload_cmd(
    run_id: str = typer.Option("", "--run", help="업로드할 run ID"),
    file: str = typer.Option("", "--file", help="임의 파일 경로 (--run 대신)"),
    config: str = typer.Option("config.yaml", "--config", "-c"),
):
    """S3 에 올려 공개 URL 만 만든다. 자격증명 점검용으로도 쓴다."""
    cfg = _load(config)
    from publish.storage import S3Storage, StorageError

    if file:
        target, rid = Path(file), None
    elif run_id:
        try:
            run = Run.load(RUNS_DIR, run_id)
        except FileNotFoundError as exc:
            _die(str(exc))
        target, rid = run.final, run.run_id
    else:
        _die("--run 또는 --file 중 하나를 지정하세요.")

    if not target.exists():
        _die(f"파일이 없습니다: {target}")

    try:
        storage = S3Storage.from_env(cfg.publish_cfg.get("storage", {}))
        typer.echo(
            f"  대상 : s3://{storage.bucket}/{storage.key_for(target, rid)}"
            f"  ({storage.url_strategy})"
        )
        obj = storage.upload(target, run_id=rid)
    except StorageError as exc:
        _die(str(exc))

    typer.secho(f"\n✓ 업로드 완료 ({obj.size_mb:.1f} MB)", fg=typer.colors.GREEN, bold=True)
    if obj.is_temporary:
        typer.echo(f"  만료 : {obj.expires_at:%Y-%m-%d %H:%M UTC}")
    typer.echo(f"  URL  : {obj.url}")

    # 무료 티어 잔량. ListObjects 는 Class A 라 여기서만 부른다.
    try:
        typer.echo("")
        typer.echo(storage.usage().render())
    except StorageError as exc:
        typer.secho(f"  (사용량 조회 생략: {exc})", fg=typer.colors.YELLOW)


@app.command("doctor")
def doctor_cmd(config: str = typer.Option("config.yaml", "--config", "-c")):
    """무엇이 준비됐고 무엇이 남았는지 점검한다. 시작 전에 먼저 실행하세요."""
    from pipeline.doctor import run_all

    cfg = _load(config)
    root = Path(__file__).parent
    sections, can_generate = run_all(root, cfg)

    typer.echo("")
    for sec in sections:
        head = f"[{sec.title}]"
        if sec.required_for:
            head += f"  ({sec.required_for})"
        typer.secho(head, bold=True)
        for check in sec.checks:
            color = {"ok": typer.colors.GREEN, "warn": typer.colors.YELLOW,
                     "fail": typer.colors.RED}[check.status]
            typer.secho(check.render(), fg=color)
        typer.echo("")

    if can_generate:
        typer.secho("▶ 영상 제작 준비 완료.", fg=typer.colors.GREEN, bold=True)
        typer.echo("  python main.py generate --image seeds/{파일명} --mode montage")
    else:
        typer.secho("▶ 아직 영상을 만들 수 없습니다. 위의 ✗ 항목을 먼저 해결하세요.",
                    fg=typer.colors.RED, bold=True)

    for sec in sections[3:]:
        state = "준비됨" if sec.ready else "미설정"
        typer.echo(f"  {sec.title}: {state}")


@app.command("plan")
def plan_cmd(
    seeds: str = typer.Option("seeds", "--seeds"),
    overwrite: bool = typer.Option(False, "--overwrite", help="기존 사이드카도 덮어쓴다"),
):
    """시드 이미지마다 제목·설명을 적을 빈 양식(.yaml)을 만든다."""
    from pipeline.content import find_sidecar, write_template

    folder = Path(seeds)
    if not folder.is_dir():
        _die(f"시드 폴더가 없습니다: {folder}")

    exts = {".png", ".jpg", ".jpeg", ".webp"}
    images = [p for p in sorted(folder.iterdir())
              if p.is_file() and p.suffix.lower() in exts]
    if not images:
        _die(f"{folder} 에 이미지가 없습니다.")

    made = skipped = 0
    for img in images:
        if find_sidecar(img) and not overwrite:
            skipped += 1
            continue
        write_template(img)
        made += 1
        typer.echo(f"  + {img.with_suffix('.yaml').name}")

    typer.secho(f"\n✓ {made}개 생성, {skipped}개 건너뜀", fg=typer.colors.GREEN)
    if made:
        typer.echo("  각 .yaml 을 열어 title 과 hook 을 채우세요. "
                   "제목은 조회수에 직접 영향을 줍니다.")


@app.command("intake")
def intake_cmd(
    source: str = typer.Option(..., "--from", "-f",
                               help="새로 받은 이미지가 있는 폴더 (다운로드 폴더 등)"),
    seeds: str = typer.Option("seeds", "--seeds"),
    min_score: float = typer.Option(0.0, "--min-score", help="이 점수 미만은 제외"),
    limit: int = typer.Option(0, "--limit", help="한 번에 들여올 최대 장수 (0=제한 없음)"),
    move: bool = typer.Option(False, "--move", help="복사 대신 원본을 옮긴다"),
):
    """새로 받은 이미지 중 **아직 안 들여온 것만** seeds/ 에 넣는다.

    curate 와 달리 이미 있는 것을 건드리지 않는다. 계속 다운로드하면서
    같은 명령을 반복해도 안전하다.
    """
    from pipeline.intake import import_folder

    try:
        report = import_folder(Path(source), Path(seeds),
                               min_score=min_score, limit=limit, move=move)
    except NotADirectoryError as exc:
        _die(str(exc))

    typer.echo(f"\n{report.scanned}장을 살펴봤습니다.")
    for item in report.added:
        typer.echo(f"  + {item.name:<22} {item.title}  ({item.score:.0f}점)")

    reasons: dict[str, int] = {}
    for item in report.skipped:
        reasons[item.reason] = reasons.get(item.reason, 0) + 1
    for reason, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
        typer.echo(f"  - {n}장 건너뜀 — {reason}")

    if report.added:
        typer.secho(f"\n✓ {len(report.added)}장을 추가했습니다.", fg=typer.colors.GREEN)
    else:
        typer.secho("\n새로 들여올 이미지가 없습니다.", fg=typer.colors.YELLOW)


@app.command("reclassify")
def reclassify_cmd(
    seeds: str = typer.Option("seeds", "--seeds"),
    rewrite_copy: bool = typer.Option(False, "--rewrite-copy",
                                      help="제목·훅도 새로 짓는다 (직접 고친 것이 덮어써진다)"),
):
    """seeds/ 를 전부 다시 살펴 테마·사이드카를 지금 기준으로 맞춘다."""
    from pipeline.intake import reclassify

    try:
        report = reclassify(Path(seeds), rewrite_copy=rewrite_copy)
    except NotADirectoryError as exc:
        _die(str(exc))

    typer.echo(f"\n{report.scanned}장을 다시 살펴봤습니다.")
    for was, now in report.renamed:
        typer.echo(f"  ↻ {was}  ->  {now}")
    for name in report.fixed:
        typer.echo(f"  ✎ {name} 사이드카 정리")
    for item in report.skipped:
        typer.echo(f"  - {item.source} — {item.reason}")
    if not report.ok:
        typer.secho("\n고칠 것이 없습니다. 전부 정상입니다.", fg=typer.colors.GREEN)
    else:
        typer.secho(f"\n✓ 이름 {len(report.renamed)}개, "
                    f"사이드카 {len(report.fixed)}개를 맞췄습니다.",
                    fg=typer.colors.GREEN)


@app.command("curate")
def curate_cmd(
    source: str = typer.Option(..., "--from", "-f", help="미드저니 이미지가 있는 폴더"),
    seeds: str = typer.Option("seeds", "--seeds"),
    per_theme: int = typer.Option(3, "--per-theme", help="테마마다 남길 장수"),
    limit: int = typer.Option(0, "--limit", help="전체 상한 (0=제한 없음)"),
    min_score: float = typer.Option(45.0, "--min-score", help="이 점수 미만은 제외"),
    dedupe_threshold: int = typer.Option(24, "--dedupe", help="중복 판정 강도 (낮을수록 엄격)"),
    allow_crop: bool = typer.Option(False, "--allow-crop",
                                    help="세로가 아닌 이미지도 잘라서 쓴다"),
    dry_run: bool = typer.Option(False, "--dry-run", help="분석만 하고 복사하지 않는다"),
):
    """미드저니 이미지 수백 장을 테마별로 분류하고 쓸 만한 것만 골라 seeds/ 에 넣는다."""
    from pipeline.curate import (
        IMAGE_EXT, analyze, contact_sheet, dedupe as dedupe_groups,
        prompt_from_filename, safe_name, theme_label, write_sidecar,
    )
    import shutil as _shutil

    src = Path(source).expanduser()
    if not src.is_dir():
        _die(f"폴더를 찾을 수 없습니다: {src}")

    files = [p for p in sorted(src.rglob("*")) if p.is_file() and p.suffix.lower() in IMAGE_EXT]
    if not files:
        _die(f"{src} 에 이미지가 없습니다.")

    typer.echo(f"\n이미지 {len(files)}장을 분석합니다…")
    shots, broken = [], 0
    with typer.progressbar(files, label="  분석") as bar:
        for f in bar:
            shot = analyze(f)
            if shot is None:
                broken += 1
            else:
                shots.append(shot)
    if broken:
        typer.secho(f"  ⚠ {broken}장은 열지 못해 건너뜁니다.", fg=typer.colors.YELLOW)

    # 세로가 아니거나 해상도가 모자란 것은 점수와 무관하게 뺀다
    disqualified = [s for s in shots if s.disqualified]
    if disqualified and not allow_crop:
        shots = [s for s in shots if not s.disqualified]
        typer.echo(f"  규격 미달 {len(disqualified)}장을 제외했습니다 "
                   f"(--allow-crop 으로 포함 가능)")
    if not shots:
        _die("쓸 수 있는 이미지가 없습니다. 9:16 세로로 다시 뽑아주세요.")

    # ── 중복 묶기 ────────────────────────────────────────────────────
    groups = dedupe_groups(shots, threshold=dedupe_threshold)
    best = [g[0] for g in groups]
    dupes = len(shots) - len(best)
    typer.echo(f"  거의 같은 그림 {dupes}장을 묶어 {len(best)}장으로 줄였습니다.")

    # ── 테마별로 나눠 상위만 남긴다 ───────────────────────────────────
    by_theme: dict[str, list] = {}
    for shot in best:
        by_theme.setdefault(shot.theme, []).append(shot)

    picked, rejected = [], []
    for theme, items in by_theme.items():
        items.sort(key=lambda s: -s.score)
        keep = [s for s in items if s.score >= min_score][:per_theme]
        picked.extend(keep)
        rejected.extend([s for s in items if s not in keep])

    picked.sort(key=lambda s: -s.score)
    if limit:
        picked = picked[:limit]

    # ── 결과 표 ──────────────────────────────────────────────────────
    typer.echo("")
    header = f"{'테마':<16} {'후보':>5} {'선택':>5}  {'최고점':>6}"
    typer.secho(header, bold=True)
    typer.echo("─" * 42)
    for theme in sorted(by_theme, key=lambda t: -max(s.score for s in by_theme[t])):
        items = by_theme[theme]
        chosen = [s for s in picked if s.theme == theme]
        typer.echo(f"{theme_label(theme):<16} {len(items):>5} {len(chosen):>5}"
                   f"  {max(s.score for s in items):>6.1f}")
    typer.echo("─" * 42)
    typer.secho(f"{'합계':<16} {len(best):>5} {len(picked):>5}", bold=True)

    if not picked:
        _die(f"점수 {min_score} 이상인 이미지가 없습니다. --min-score 를 낮춰보세요.")

    # 왜 안 골랐는지 — 규격 미달과 '순위 밖'을 섞으면 오해를 부른다
    hard: dict[str, int] = {}
    for s in (disqualified if not allow_crop else []):
        for r in s.reasons:
            hard[r] = hard.get(r, 0) + 1
    if hard:
        typer.echo("\n규격 미달로 뺀 것:")
        for r, n in sorted(hard.items(), key=lambda kv: -kv[1])[:6]:
            typer.secho(f"  {n:>4}장  {r}", fg=typer.colors.RED)

    if rejected:
        typer.echo(f"\n{len(rejected)}장은 테마당 {per_theme}장 제한에 걸려 대기 중입니다."
                   " (문제가 있는 게 아닙니다)")
        typer.echo(f"  더 쓰려면: --per-theme {per_theme + 2}")
        soft: dict[str, int] = {}
        for s in rejected:
            for r in s.reasons:
                soft[r] = soft.get(r, 0) + 1
        low = {r: n for r, n in soft.items() if "밝음" in r or "밋밋" in r or "채도" in r}
        if low:
            typer.echo("  그중 품질이 아쉬운 것:")
            for r, n in sorted(low.items(), key=lambda kv: -kv[1])[:4]:
                typer.secho(f"    {n:>4}장  {r}", fg=typer.colors.YELLOW)

    if dry_run:
        typer.secho("\n[dry-run] 복사하지 않았습니다.", fg=typer.colors.YELLOW)
        return

    # ── 복사 + 사이드카 ──────────────────────────────────────────────
    seeds_dir = Path(seeds)
    seeds_dir.mkdir(parents=True, exist_ok=True)
    counters: dict[str, int] = {}
    typer.echo("")
    for shot in picked:
        counters[shot.theme] = counters.get(shot.theme, 0) + 1
        stem = safe_name(shot.theme, counters[shot.theme])
        dest = seeds_dir / f"{stem}{shot.path.suffix.lower()}"
        n = 1
        while dest.exists():
            n += 1
            dest = seeds_dir / f"{stem}_{n}{shot.path.suffix.lower()}"
        _shutil.copy2(shot.path, dest)
        write_sidecar(dest, shot.theme, prompt_from_filename(shot.path))
    typer.secho(f"✓ {len(picked)}장을 {seeds_dir}/ 에 복사하고 제목 양식을 만들었습니다.",
                fg=typer.colors.GREEN)

    # ── 눈으로 확인할 컨택트 시트 ─────────────────────────────────────
    review = seeds_dir / "_review"
    if review.exists():
        _shutil.rmtree(review, ignore_errors=True)
    made = []
    for theme in sorted({s.theme for s in picked}):
        items = [s for s in picked if s.theme == theme]
        out = review / f"{theme}.jpg"
        contact_sheet(items, out, title=f"{theme_label(theme)}  ({len(items)}장)")
        made.append(out)
    contact_sheet(picked[:36], review / "_all.jpg", title=f"전체 상위 {min(len(picked), 36)}장")

    typer.echo(f"\n확인용 시트: {review}")
    typer.echo("  _all.jpg 를 먼저 열어보세요. 마음에 안 드는 것은")
    typer.echo("  seeds/ 에서 이미지와 .yaml 을 함께 지우면 됩니다.")
    typer.echo("\n다음: python main.py doctor")


@app.command("connect-youtube")
def connect_youtube_cmd():
    """유튜브 계정을 연결한다. 브라우저가 열리면 로그인하고 권한을 허용하세요."""
    from publish.youtube import UploadError, _credentials, _require_libs

    secret = Path(os.getenv("YOUTUBE_CLIENT_SECRET_FILE", "secrets/client_secret.json"))
    if not secret.is_absolute():
        secret = Path(__file__).parent / secret
    if not secret.exists():
        _die("client_secret.json 이 없습니다.\n"
             f"  찾은 위치: {secret}\n"
             "  작업실 [설정] 탭에서 파일을 올리거나, secrets/ 폴더에 넣으세요.")

    typer.echo("브라우저가 열립니다. 유튜브 채널 계정으로 로그인하고 [허용] 을 누르세요.")
    typer.echo("  (창이 안 열리면 터미널에 뜬 주소를 직접 붙여넣으세요)\n")
    try:
        creds = _credentials()
    except UploadError as exc:
        _die(str(exc))
    except Exception as exc:                       # noqa: BLE001 - 원인을 그대로 보여준다
        _die(f"연결에 실패했습니다: {exc}")

    # 여기까지 왔으면 토큰이 저장된 것이고 업로드는 된다.
    # 채널 이름은 확인용 덤이다. 우리가 받은 권한은 업로드 전용(youtube.upload)이라
    # channels.list 는 403 이 난다 — 실패해도 연결은 성공이므로 넘어간다.
    name = ""
    try:
        _, _, _, build, _ = _require_libs()
        yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
        items = yt.channels().list(part="snippet", mine=True).execute().get("items") or []
        if items:
            name = items[0]["snippet"]["title"]
    except Exception:                              # noqa: BLE001 - 이름 확인은 부가 기능
        pass

    if name:
        typer.secho(f"\n연결 완료: {name}", fg=typer.colors.GREEN)
    else:
        typer.secho("\n연결 완료", fg=typer.colors.GREEN)
        typer.echo("  (업로드 전용 권한이라 채널 이름까지는 확인하지 않습니다)")

    # 매일 밤 자동 업로드는 사람 없이 토큰을 갱신해서 돌아간다.
    # 갱신용 토큰이 없으면 오늘은 되고 내일부터 조용히 실패한다 — 지금 잡아준다.
    if not getattr(creds, "refresh_token", None):
        typer.secho("\n! 갱신용 토큰을 못 받았습니다.", fg=typer.colors.YELLOW)
        typer.echo("  지금은 업로드되지만 몇 시간 뒤 만료되면 다시 로그인해야 합니다.")
        typer.echo("  secrets/youtube_token.json 을 지우고 다시 연결해 보세요.")

    # 작업실 화면이 채널 이름을 보여줄 수 있게 토큰 옆에 적어 둔다.
    token = Path(os.getenv("YOUTUBE_TOKEN_FILE", "secrets/youtube_token.json"))
    if not token.is_absolute():
        token = Path(__file__).parent / token
    if name:
        try:
            import json as _json
            data = _json.loads(token.read_text(encoding="utf-8"))
            data["_channel_title"] = name
            token.write_text(_json.dumps(data), encoding="utf-8")
        except (OSError, ValueError):
            pass                               # 이름 표시는 있으면 좋은 것일 뿐이다

    typer.echo(f"  토큰을 {token} 에 저장했습니다. 다음부터는 로그인이 필요 없습니다.")


@app.command("connect-instagram")
def connect_instagram_cmd():
    """인스타 토큰이 살아 있는지 확인한다. 계정 이름이 나오면 성공이다."""
    import json as _json
    import urllib.error
    import urllib.parse
    import urllib.request

    user_id = os.getenv("IG_USER_ID", "").strip()
    token = os.getenv("IG_ACCESS_TOKEN", "").strip()
    if not token:
        _die("IG_ACCESS_TOKEN 이 없습니다.\n"
             "  작업실 [설정] 탭에서 넣어주세요.")

    # 계정 ID 는 토큰만 있으면 우리가 찾을 수 있다. 사람이 그래프 API 탐색기에서
    # me/accounts 를 쳐서 숫자를 옮겨 적을 이유가 없다.
    if not user_id:
        typer.echo("IG_USER_ID 가 비어 있습니다. 토큰으로 직접 찾아봅니다…")
        found = _find_ig_user_id(token)
        if not found:
            _die("인스타 비즈니스 계정을 못 찾았습니다.\n"
                 "  토큰에 pages_show_list · instagram_basic 권한이 있는지,\n"
                 "  페이스북 페이지에 인스타 계정이 연결돼 있는지 확인하세요.")
        user_id, page_name = found
        typer.secho(f"  찾았습니다: {user_id}  (페이지: {page_name})",
                    fg=typer.colors.GREEN)
        from pipeline import envfile
        envfile.write({"IG_USER_ID": user_id})
        typer.echo("  .env 에 저장했습니다.")

    from publish.instagram import api_base

    qs = urllib.parse.urlencode({
        "fields": "username,followers_count,media_count",
        "access_token": token,
    })
    url = f"{api_base(token)}/{urllib.parse.quote(user_id)}?{qs}"
    try:
        with urllib.request.urlopen(url, timeout=20) as r:   # noqa: S310 - 고정 호스트
            data = _json.loads(r.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:400]
        _die(f"인스타 확인 실패 (HTTP {exc.code})\n  {detail}\n"
             "  토큰이 만료됐거나 IG_USER_ID 가 페이지에 연결돼 있지 않습니다.")
    except OSError as exc:
        _die(f"인스타에 연결하지 못했습니다: {exc}")

    typer.secho(f"\n연결 완료: @{data.get('username', '?')}", fg=typer.colors.GREEN)
    typer.echo(f"  게시물 {data.get('media_count', '?')}개 · "
               f"팔로워 {data.get('followers_count', '?')}명")

    # 토큰이 언제 죽는지 알려준다.
    # 탐색기에서 그냥 복사하면 1~2시간짜리 임시 토큰이 나온다. 지금은 통과하고
    # 밤에 조용히 실패하는 가장 흔한 함정이라 여기서 잡아준다.
    _report_ig_expiry(token)


def _find_ig_user_id(token: str) -> tuple[str, str] | None:
    """토큰으로 인스타 계정 ID 를 찾는다.

    발급 경로에 따라 찾는 방법이 다르다.
      인스타 로그인 토큰(IGAA...) : /me 가 곧 그 계정이다
      페이스북 토큰(EAA...)       : /me/accounts 의 페이지들에서 연결된 계정을 본다
    """
    import json as _json
    import urllib.error
    import urllib.parse
    import urllib.request

    from publish.instagram import GRAPH_IG, api_base

    if api_base(token) == GRAPH_IG:
        qs = urllib.parse.urlencode({"fields": "user_id,username",
                                     "access_token": token})
        try:
            with urllib.request.urlopen(      # noqa: S310 - 고정 호스트
                    f"{GRAPH_IG}/me?{qs}", timeout=20) as r:
                me = _json.loads(r.read().decode())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:300]
            typer.secho(f"  계정을 못 읽었습니다 (HTTP {exc.code})\n  {detail}",
                        fg=typer.colors.YELLOW)
            return None
        except (OSError, ValueError):
            return None
        gid = str(me.get("user_id") or me.get("id") or "")
        return (gid, f"@{me.get('username', '?')}") if gid else None

    qs = urllib.parse.urlencode({
        "fields": "name,instagram_business_account",
        "access_token": token,
    })
    try:
        with urllib.request.urlopen(          # noqa: S310 - 고정 호스트
                f"{api_base(token)}/me/accounts?{qs}", timeout=20) as r:
            pages = _json.loads(r.read().decode()).get("data", [])
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        typer.secho(f"  페이지 목록을 못 읽었습니다 (HTTP {exc.code})\n  {detail}",
                    fg=typer.colors.YELLOW)
        return None
    except (OSError, ValueError):
        return None

    linked = [(p["instagram_business_account"]["id"], p.get("name", "?"))
              for p in pages if p.get("instagram_business_account")]
    if not linked:
        if pages:
            names = ", ".join(p.get("name", "?") for p in pages[:5])
            typer.secho(f"  페이지는 보이는데({names}) 인스타가 연결돼 있지 않습니다.",
                        fg=typer.colors.YELLOW)
        return None
    if len(linked) > 1:
        typer.secho("  인스타 계정이 여러 개입니다. 첫 번째를 씁니다:", fg=typer.colors.YELLOW)
        for i, (gid, nm) in enumerate(linked):
            typer.echo(f"    {'->' if i == 0 else '  '} {gid}  ({nm})")
    return linked[0]


def _report_ig_expiry(token: str) -> None:
    import json as _json
    import time
    import urllib.error
    import urllib.parse
    import urllib.request

    from publish.instagram import GRAPH_IG, api_base

    if api_base(token) == GRAPH_IG:
        # debug_token 은 페이스북 쪽 기능이라 인스타 로그인 토큰에는 못 쓴다.
        # 만료를 정확히 읽을 방법이 없으니 통상값을 알려주고 넘어간다.
        typer.echo("  Instagram 로그인 토큰입니다. 보통 60일이며 만료일은 조회할 수 없습니다.")
        typer.echo("  두 달쯤 뒤 업로드가 실패하면 같은 자리에서 다시 발급하세요.")
        return

    qs = urllib.parse.urlencode({"input_token": token, "access_token": token})
    try:
        with urllib.request.urlopen(          # noqa: S310 - 고정 호스트
                f"https://graph.facebook.com/v21.0/debug_token?{qs}", timeout=20) as r:
            info = _json.loads(r.read().decode()).get("data", {})
    except (urllib.error.HTTPError, OSError, ValueError):
        return                                 # 확인 못 해도 연결 자체는 성공이다

    expires = info.get("expires_at")
    if expires == 0:                           # 0 은 '만료 없음' 이다 (시스템 사용자 토큰)
        typer.secho("  토큰 만료: 없음 — 다시 발급받을 필요가 없습니다.",
                    fg=typer.colors.GREEN)
        return
    if not expires:                            # 값을 안 주면 조용히 넘어간다
        return

    days = (expires - time.time()) / 86400
    if days < 1:
        hours = max(0, (expires - time.time()) / 3600)
        typer.secho(f"\n! 이 토큰은 약 {hours:.0f}시간 뒤 만료됩니다 — 임시 토큰입니다.",
                    fg=typer.colors.RED)
        typer.echo("  지금은 올라가지만 오늘 밤 자동 업로드부터 실패합니다.")
        typer.echo("  액세스 토큰 디버거에서 [확장 액세스 토큰] 을 눌러")
        typer.echo("  60일짜리로 바꾼 뒤 다시 넣으세요.")
        typer.echo("  https://developers.facebook.com/tools/debug/accesstoken/")
    elif days < 14:
        typer.secho(f"  ! 토큰이 {days:.0f}일 뒤 만료됩니다. 미리 재발급하세요.",
                    fg=typer.colors.YELLOW)
    else:
        typer.echo(f"  토큰 만료까지 약 {days:.0f}일 남았습니다.")


@app.command("connect-storage")
def connect_storage_cmd():
    """영상 보관함(R2/S3)이 실제로 되는지 왕복으로 확인한다.

    값이 채워졌는지만 보는 게 아니라, 인스타 업로드가 밟는 경로를 그대로 밟는다.
    올리기 -> 공개 URL 만들기 -> 그 URL 로 진짜 받아보기 -> 지우기.
    앞의 셋 중 하나만 막혀도 인스타는 실패하므로 전부 확인해야 의미가 있다.
    """
    import tempfile
    import urllib.error
    import urllib.request

    from publish.storage import S3Storage, StorageError

    bucket = os.getenv("S3_BUCKET", "").strip()
    if not bucket:
        _die("버킷 이름이 없습니다.\n"
             "  작업실 [설정] 탭 → 영상 보관함 을 채워주세요.")
    if not os.getenv("AWS_ACCESS_KEY_ID", "").strip():
        _die("액세스 키가 없습니다.\n"
             "  R2 → Manage API Tokens 에서 Object Read & Write 토큰을 만드세요.")

    try:
        store = S3Storage.from_env()
    except StorageError as exc:
        _die(str(exc))

    where = store.endpoint_url or f"AWS S3 ({store.region})"
    typer.echo(f"보관함: {bucket}  @ {where}")

    # 진짜 파일을 하나 올려본다. 몇 바이트라 무료 티어에 영향이 없다.
    tmp = Path(tempfile.gettempdir()) / "aideokhu_storage_check.txt"
    tmp.write_text("AI DEOKHU storage check\n", encoding="utf-8")
    key = None
    try:
        typer.echo("  1/4 올리는 중…")
        obj = store.upload(tmp, key=f"{store.prefix}/_check/connection-test.txt",
                           show_progress=False)
        key = obj.key
        typer.secho("      올라갔습니다.", fg=typer.colors.GREEN)

        typer.echo("  2/4 공개 URL 만드는 중…")
        if not obj.url:
            _die("URL 을 만들지 못했습니다. url_strategy 설정을 확인하세요.")
        typer.secho(f"      {obj.url[:70]}…", fg=typer.colors.GREEN)

        typer.echo("  3/4 그 URL 로 실제로 받아보는 중…")
        try:
            with urllib.request.urlopen(obj.url, timeout=30) as r:  # noqa: S310
                body = r.read()
            if b"AI DEOKHU" not in body:
                _die("URL 은 열리는데 내용이 다릅니다. 버킷/경로를 확인하세요.")
            typer.secho("      받았습니다. 인스타도 이 URL 로 영상을 가져갑니다.",
                        fg=typer.colors.GREEN)
        except urllib.error.HTTPError as exc:
            _die(f"URL 을 열 수 없습니다 (HTTP {exc.code}).\n"
                 "  presigned URL 이 막혔거나 공개 도메인 설정이 잘못됐습니다.\n"
                 "  인스타는 이 URL 로 영상을 가져가므로 이게 안 되면 업로드도 실패합니다.")
        except OSError as exc:
            _die(f"URL 에 연결하지 못했습니다: {exc}")
    except StorageError as exc:
        _die(str(exc))
    finally:
        tmp.unlink(missing_ok=True)
        if key:
            typer.echo("  4/4 시험 파일 지우는 중…")
            store.delete(key)

    typer.secho("\n보관함 연결 완료 — 인스타 업로드 준비됐습니다.", fg=typer.colors.GREEN)

    try:
        typer.echo(store.usage().render())
    except Exception:                          # noqa: BLE001 - 사용량 표시는 덤이다
        pass


@app.command("ui")
def ui_cmd(
    port: int = typer.Option(8765, "--port"),
    no_browser: bool = typer.Option(False, "--no-browser", help="브라우저를 자동으로 열지 않는다"),
):
    """브라우저 작업실을 연다. 클릭으로 영상을 만들고 올릴 수 있다."""
    from ui.server import serve

    serve(port=port, open_browser=not no_browser)


if __name__ == "__main__":
    try:
        app()
    except KeyboardInterrupt:
        typer.secho("\n중단됨 (Ctrl-C)", fg=typer.colors.YELLOW)
        sys.exit(130)
