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

import sys
from pathlib import Path
from typing import Optional

import typer

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
    result = stitch(
        clips, run.final,
        width=out["width"], height=out["height"], fps=out["fps"],
        crf=out.get("crf", 18),
        crossfade=crossfade, transition=transition,
        audio=out.get("audio", "silent"), audio_file=out.get("audio_file"),
    )
    spent = actual_cost(cfg, stats.clip_calls, stats.upscale_calls)
    run.save_state(
        final=str(result.path), duration=round(result.duration, 2),
        clip_calls=stats.clip_calls, upscale_calls=stats.upscale_calls,
        cost_usd=round(spent, 4),
    )
    run.log("run.finished", duration=result.duration, cost_usd=spent)

    typer.secho("\n✓ 완료", fg=typer.colors.GREEN, bold=True)
    typer.echo(f"  파일   : {result.path}")
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

    try:
        warnings = prepare_input(
            image, run.input_image, pad=pad,
            width=cfg.output["width"], height=cfg.output["height"],
        )
    except ValidationError as exc:
        _die(str(exc))
    for w in warnings:
        typer.secho(f"  {w}", fg=typer.colors.YELLOW)

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

    if youtube:
        from publish import youtube as yt
        yc = cfg.publish_cfg.get("youtube", {})
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
                dry_run=dry_run,
            )
        except yt.UploadError as exc:
            _die(str(exc))
        typer.secho(f"✓ YouTube: {res.url}", fg=typer.colors.GREEN)
        run.log("publish.youtube", video_id=res.video_id, url=res.url)

    if instagram:
        from publish import instagram as ig
        ic = cfg.publish_cfg.get("instagram", {})
        url, uploaded = _resolve_media_url(cfg, run, video_url, dry_run)
        try:
            res = ig.upload(
                url,
                caption=ic.get("caption_template", "{description}")
                          .format(description=description),
                share_to_feed=bool(ic.get("share_to_feed", True)),
                dry_run=dry_run,
            )
        except ig.UploadError as exc:
            _die(str(exc))
        typer.secho(f"✓ Instagram: {res.permalink or res.media_id}", fg=typer.colors.GREEN)
        run.log("publish.instagram", media_id=res.media_id, permalink=res.permalink)

        # 발행이 끝났으면 스토리지를 비워 비용을 아낀다.
        sc = cfg.publish_cfg.get("storage", {})
        if uploaded and sc.get("delete_after_publish") and not dry_run:
            from publish.storage import S3Storage
            S3Storage.from_env(sc).delete(uploaded.key)
            typer.echo(f"  S3 객체 삭제: {uploaded.key}")


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


if __name__ == "__main__":
    try:
        app()
    except KeyboardInterrupt:
        typer.secho("\n중단됨 (Ctrl-C)", fg=typer.colors.YELLOW)
        sys.exit(130)
