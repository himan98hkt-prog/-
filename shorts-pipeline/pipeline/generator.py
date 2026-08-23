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


def fold_negative(prompt: str, negative: str) -> str:
    """네거티브를 안 받는 모델을 위해 금지 사항을 긍정 프롬프트에 녹인다.

    버리는 것보다 낫다. 대부분의 영상 모델이 "Avoid: ..." 는 알아듣는다.
    """
    words = " ".join((negative or "").split()).strip(" ,.")
    if not words:
        return prompt
    return f"{prompt.rstrip('. ')}. Avoid: {words}."


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
    # 네거티브를 안 받는 모델(hailuo 등)이면 **버리지 말고** 긍정 프롬프트에
    # 녹여 넣는다. 예전에는 그냥 버렸다. kling -> hailuo 로 바꾼 순간
    # "morphing architecture / distorted geometry" 같은 왜곡 방지 지시가
    # 통째로 사라졌고, 사용자가 곧바로 "애니메이션이 이상하다" 고 신고했다.
    req = GenerationRequest(
        image=image,
        prompt=(prompt if model.supports_negative
                else fold_negative(prompt, cfg.negative_prompt)),
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
    out = shrink_to_output(out, cfg, run, index=index)
    run.log("upscale.done", index=index, path=str(out))
    return out


def shrink_to_output(frame: Path, cfg: Config, run: Run, *, index: int) -> Path:
    """업스케일한 프레임을 다시 출력 해상도로 줄인다.

    esrgan 은 1080x1920 을 4배(4320x7680)로 키운다. 그걸 그대로 다음 클립의
    입력으로 보내면 fal 에 **40~80MB 짜리 data URI** 를 올리게 된다.
    requests 의 timeout 은 소켓이 조용할 때만 도는 값이라, 업로드가 느리게
    이어지는 동안에는 영영 만료되지 않는다. 실제로 클립 2에서 43분을 멈춰
    있다가 아무 오류도 못 낸 사례가 나왔다.

    모델은 어차피 출력 해상도로 만든다. 큰 그림을 보낼 이유가 없다.
    업스케일의 이점(압축 잡티 제거)은 줄이고 나서도 남는다 — 슈퍼샘플링이다.
    """
    from PIL import Image

    want = (int(cfg.output["width"]), int(cfg.output["height"]))
    try:
        with Image.open(frame) as img:
            if img.size[0] <= want[0] and img.size[1] <= want[1]:
                return frame
            before = img.size
            small = img.convert("RGB").resize(want, Image.LANCZOS)
        small.save(frame, "PNG", optimize=True)
    except OSError as exc:
        run.log("upscale.shrink_failed", index=index, error=str(exc))
        return frame
    mb = frame.stat().st_size / 1e6
    print(f"    업스케일 프레임을 {before[0]}x{before[1]} -> "
          f"{want[0]}x{want[1]} 로 줄였습니다 ({mb:.1f}MB)")
    run.log("upscale.shrunk", index=index, before=list(before), after=list(want),
            size_mb=round(mb, 2))
    return frame
