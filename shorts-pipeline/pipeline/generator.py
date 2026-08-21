"""provider 위에 재시도와 로깅을 얹은 생성 래퍼."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from .config import Config
from .providers import GenerationRequest, ProviderError, VideoProvider, build_provider
from .runlog import Run

MAX_ATTEMPTS = 3  # 최초 1회 + 재시도 2회 (지시서 4.2)


@dataclass
class GenerationStats:
    """실제 과금 대상 호출 수. 사후 비용 계산에 쓴다."""

    clip_calls: int = 0
    upscale_calls: int = 0


def make_provider(cfg: Config, run: Run) -> VideoProvider:
    """config 와 run 을 엮어 provider 를 만든다. 모든 호출이 log.jsonl 에 남는다."""
    return build_provider(
        cfg.provider,
        endpoint=cfg.model.endpoint,
        base_url=cfg.provider_cfg.get("endpoint_base"),
        on_log=lambda event, payload: run.log(event, **payload),
    )


def generate_clip(
    provider: VideoProvider,
    cfg: Config,
    run: Run,
    stats: GenerationStats,
    *,
    index: int,
    image: Path,
    prompt: str,
    end_image: Path | None = None,
) -> Path:
    """클립 하나를 만든다. 실패하면 동일 파라미터로 최대 2회 더 시도한다."""
    dest = run.clip(index)
    model = cfg.model
    req = GenerationRequest(
        image=image,
        prompt=prompt,
        duration=cfg.clip_duration,
        negative_prompt=cfg.negative_prompt if model.supports_negative else "",
        end_image=end_image if model.supports_end_image else None,
    )

    last: ProviderError | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            result = provider.generate(req, dest)
        except ProviderError as exc:
            last = exc
            run.log("clip.attempt_failed", index=index, attempt=attempt,
                    error=str(exc), retryable=exc.retryable)
            # 과금됐을 수도 있는 실패는 보수적으로 비용에 넣는다.
            stats.clip_calls += 1
            if not exc.retryable or attempt == MAX_ATTEMPTS:
                break
            backoff = 2 ** attempt
            print(f"    재시도 {attempt}/{MAX_ATTEMPTS - 1} — {backoff}초 후 ({exc})")
            time.sleep(backoff)
            continue

        stats.clip_calls += 1
        run.log("clip.done", index=index, job_id=result.job_id,
                elapsed=round(result.elapsed_seconds, 1), path=str(dest))
        return dest

    raise ProviderError(
        f"클립 {index} 를 {MAX_ATTEMPTS}회 시도했지만 실패했습니다.\n마지막 오류: {last}",
        retryable=False,
    )


def upscale_frame(
    provider: VideoProvider,
    cfg: Config,
    run: Run,
    stats: GenerationStats,
    *,
    index: int,
    frame: Path,
) -> Path:
    """프레임을 업스케일한다. 실패하면 원본 프레임을 그대로 쓴다.

    업스케일은 품질 보정일 뿐이라, 여기서 파이프라인 전체를 멈출 이유가 없다.
    """
    spec = cfg.upscaler
    if spec is None:
        return frame
    dest = run.frame(index, upscaled=True)
    try:
        out = provider.upscale(frame, dest, spec.endpoint)
    except ProviderError as exc:
        stats.upscale_calls += 1
        run.log("upscale.failed", index=index, error=str(exc))
        print(f"    ⚠ 업스케일 실패, 원본 프레임으로 계속합니다 ({exc})")
        return frame
    stats.upscale_calls += 1
    run.log("upscale.done", index=index, path=str(out))
    return out
