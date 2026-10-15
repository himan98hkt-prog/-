"""체이닝 오케스트레이션.

chain   : 클립 N 의 마지막 프레임이 클립 N+1 의 시작 이미지가 된다.
          레퍼런스 @odysseyml / @hellopersonality 의 '끊기지 않는 전진'.
montage : 장면마다 독립된 시드 이미지에서 출발하고, 마지막에 첫 장면으로 회귀한다.
          레퍼런스 @cyborg.digitalart 의 'Infinite peace part N'.
"""

from __future__ import annotations

import time
from pathlib import Path

from .config import Config
from .frame_extractor import extract_first_frame, extract_last_frame
from .generator import GenerationStats, generate_clip, make_provider, upscale_frame
from .providers import ProviderError
from .runlog import Run


class Aborted(Exception):
    """사용자가 --interactive 에서 중단을 선택했다."""


def _fmt_elapsed(started: float) -> str:
    secs = int(time.time() - started)
    return f"{secs // 60}분 {secs % 60}초"


def _report_source_size(clip: Path, cfg: Config, run: Run) -> None:
    """모델이 실제로 내준 해상도를 알려준다.

    "화질이 아쉽다" 의 원인은 대개 여기다. 최종 인코딩(crf 18)은 이미
    원본과 PSNR 50dB 이상이라 눈으로 구별되지 않는다. 모델이 720p 를
    주는데 1080p 로 늘리고 있으면 그게 진짜 병목이다.
    """
    from .ffmpeg_util import FFmpegError, dimensions_of

    want_w, want_h = int(cfg.output["width"]), int(cfg.output["height"])
    try:
        w, h = dimensions_of(clip)
    except (FFmpegError, OSError):
        return
    run.save_state(source_res=[w, h])
    if w >= want_w and h >= want_h:
        print(f"    모델 출력 {w}x{h} — 출력({want_w}x{want_h})보다 크거나 같습니다.")
        return
    short = round((1 - min(w / want_w, h / want_h)) * 100)
    print(f"    ⚠ 모델 출력이 {w}x{h} 입니다. {want_w}x{want_h} 로 "
          f"{short}% 늘려 씁니다 — 여기서 화질이 깎입니다.")
    print("      더 높은 해상도를 주는 모델로 바꾸면 개선됩니다 "
          "(config.yaml 의 model).")


def _progress(index: int, total: int, cfg: Config, started: float) -> None:
    accumulated = index * cfg.clip_duration
    print(
        f"  [{index}/{total}] 클립 생성 완료 "
        f"(누적 {accumulated}초, 소요 {_fmt_elapsed(started)})"
    )


def _checkpoint(frame: Path, index: int, interactive: bool) -> str:
    """품질 체크포인트. 4~5회차부터 풍경이 무너지는 일이 잦아 필수다."""
    print(f"    라스트 프레임: {frame}")
    if not interactive:
        return "continue"
    while True:
        choice = input(
            "    [c] 계속  [r] 새 이미지로 리셋  [s] 여기서 중단하고 합성  [a] 취소 > "
        ).strip().lower() or "c"
        if choice in ("c", "continue"):
            return "continue"
        if choice in ("r", "reset"):
            return "reset"
        if choice in ("s", "stop"):
            return "stop"
        if choice in ("a", "abort"):
            return "abort"
        print("    c / r / s / a 중에서 고르세요.")


def run_chain(
    cfg: Config,
    run: Run,
    *,
    interactive: bool = False,
    resume: bool = False,
) -> tuple[list[Path], GenerationStats]:
    """라스트 프레임 체이닝 루프."""
    provider = make_provider(cfg, run)
    stats = GenerationStats()
    started = time.time()

    done = run.completed_clips() if resume else []
    clips = [run.clip(n) for n in done]
    if done:
        print(f"  이어하기: 클립 {len(done)}개를 재사용합니다 ({done}).")

    # 다음 클립의 입력 이미지를 정한다.
    if done:
        last_index = done[-1]
        frame = run.frame(last_index, upscaled=True)
        if not frame.exists():
            frame = run.frame(last_index)
        if not frame.exists():
            frame = extract_last_frame(run.clip(last_index), run.frame(last_index))
        current_image = frame
    else:
        current_image = run.input_image

    total = cfg.num_clips
    for index in range(len(done) + 1, total + 1):
        print(f"  [{index}/{total}] 생성 중… (입력: {current_image.name})")
        generate_clip(
            provider, cfg, run, stats,
            index=index, image=current_image, prompt=cfg.motion_prompt,
        )
        clips.append(run.clip(index))
        _progress(index, total, cfg, started)
        if index == 1:
            _report_source_size(run.clip(index), cfg, run)
        run.save_state(mode="chain", clips_done=index, total=total)

        if index == total:
            break

        raw = extract_last_frame(run.clip(index), run.frame(index))
        action = _checkpoint(raw, index, interactive)
        if action == "abort":
            raise Aborted("사용자가 실행을 취소했습니다.")
        if action == "stop":
            print("  여기까지의 클립으로 합성합니다.")
            break
        if action == "reset":
            new_path = input("    새 시작 이미지 경로 > ").strip()
            if new_path and Path(new_path).exists():
                from .validator import prepare_input
                reset_dest = run.frames_dir / f"reset_{index:02d}.png"
                prepare_input(
                    new_path, reset_dest,
                    width=cfg.output["width"], height=cfg.output["height"],
                )
                run.log("chain.reset", index=index, source=new_path)
                current_image = reset_dest
                continue
            print("    경로를 찾지 못해 원래 프레임으로 계속합니다.")

        current_image = upscale_frame(provider, cfg, run, stats, index=index, frame=raw)

    if cfg.loop_back and len(clips) >= 2:
        clips.append(_generate_loop_clip(provider, cfg, run, stats, clips))

    return clips, stats


def _generate_loop_clip(provider, cfg, run, stats, clips: list[Path]) -> Path:
    """마지막 프레임 → 첫 프레임으로 돌아오는 클립. 무한 루프를 만든다."""
    index = len(clips) + 1
    print(f"  [루프] 첫 장면으로 돌아오는 클립을 만듭니다…")
    first = extract_first_frame(clips[0], run.frames_dir / "first.png")
    tail = run.frame(len(clips), upscaled=True)
    if not tail.exists():
        tail = extract_last_frame(clips[-1], run.frame(len(clips)))
    generate_clip(
        provider, cfg, run, stats,
        index=index, image=tail, prompt=cfg.motion_prompt, end_image=first,
    )
    return run.clip(index)


def run_montage(
    cfg: Config,
    run: Run,
    *,
    interactive: bool = False,
    resume: bool = False,
) -> tuple[list[Path], GenerationStats]:
    """장면 단위 몽타주.

    각 장면은 독립적이라 이전 장면의 화질 열화를 물려받지 않는다.
    시드 이미지는 frames/seed_NN.png 에 미리 넣어두거나, 없으면 입력 이미지를 쓴다.
    """
    provider = make_provider(cfg, run)
    stats = GenerationStats()
    started = time.time()

    prompts = cfg.scene_prompts or [cfg.motion_prompt] * cfg.num_clips
    if len(prompts) < cfg.num_clips:
        prompts = prompts + [prompts[-1]] * (cfg.num_clips - len(prompts))

    done = run.completed_clips() if resume else []
    clips = [run.clip(n) for n in done]
    if done:
        print(f"  이어하기: 장면 {len(done)}개를 재사용합니다 ({done}).")

    total = cfg.num_clips

    # 장면별 시드가 하나도 없으면 모든 클립이 같은 그림에서 출발한다.
    # 그러면 5초마다 처음 위치로 되돌아가는 영상이 나온다 — 원하는 결과가 아니다.
    if not any(run.seed(i).exists() for i in range(1, total + 1)):
        print(
            "\n  ⚠ 장면별 시드가 없어 모든 클립이 같은 이미지에서 시작합니다.\n"
            "     클립마다 처음 위치로 되돌아가는 영상이 나옵니다.\n"
            "     끊김 없이 이어지길 원하시면 --mode chain 을 쓰세요.\n"
            "     montage 를 쓰려면 --scenes 로 장면 이미지를 여러 장 지정하세요.\n"
        )

    for index in range(len(done) + 1, total + 1):
        seed = run.seed(index)
        if not seed.exists():
            seed = run.input_image
        print(f"  [{index}/{total}] 장면 생성 중… (시드: {seed.name})")
        generate_clip(
            provider, cfg, run, stats,
            index=index, image=seed, prompt=prompts[index - 1],
        )
        clips.append(run.clip(index))
        _progress(index, total, cfg, started)
        run.save_state(mode="montage", clips_done=index, total=total)

        if interactive and index < total:
            frame = extract_last_frame(run.clip(index), run.frame(index))
            if _checkpoint(frame, index, interactive) == "abort":
                raise Aborted("사용자가 실행을 취소했습니다.")

    return clips, stats


def orchestrate(cfg: Config, run: Run, **kwargs) -> tuple[list[Path], GenerationStats]:
    if cfg.mode == "chain":
        return run_chain(cfg, run, **kwargs)
    if cfg.mode == "montage":
        return run_montage(cfg, run, **kwargs)
    raise ProviderError(f"알 수 없는 mode: {cfg.mode}", retryable=False)
