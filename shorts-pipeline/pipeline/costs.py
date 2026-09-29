"""실행 전 비용 견적. API 를 한 번도 부르기 전에 사용자에게 보여준다."""

from __future__ import annotations

from dataclasses import dataclass

from .config import Config


@dataclass
class CostEstimate:
    """한 번의 실행에 대한 견적."""

    provider: str
    model: str
    num_clips: int
    clip_duration: int
    video_clips_planned: int
    cost_per_clip: float
    video_subtotal: float
    upscale_images: int
    cost_per_upscale: float
    upscale_subtotal: float
    subtotal: float
    retry_multiplier: float
    expected: float
    hard_cap: float

    @property
    def output_seconds(self) -> float:
        return self.video_clips_planned * self.clip_duration

    @property
    def over_cap(self) -> bool:
        return self.expected > self.hard_cap

    def render(self) -> str:
        """콘솔에 그대로 찍을 수 있는 표."""
        lines = [
            "┌─ 예상 비용 ─────────────────────────────────────────────",
            f"│ provider / model : {self.provider} / {self.model}",
            f"│ 클립             : {self.video_clips_planned}개 x {self.clip_duration}초"
            f"  (원본 {self.output_seconds:.0f}초)",
            f"│ 영상 생성        : {self.video_clips_planned} x ${self.cost_per_clip:.4f}"
            f" = ${self.video_subtotal:.2f}",
        ]
        if self.upscale_images:
            lines.append(
                f"│ 업스케일         : {self.upscale_images} x ${self.cost_per_upscale:.4f}"
                f" = ${self.upscale_subtotal:.2f}"
            )
        lines += [
            f"│ 소계             : ${self.subtotal:.2f}",
            f"│ 재시도 계수      : x{self.retry_multiplier:.1f}"
            "  (실패·품질 리젝 반영)",
            f"│ ▶ 실질 예상      : ${self.expected:.2f}",
            f"│ 상한(hard cap)   : ${self.hard_cap:.2f}"
            + ("  ⚠ 초과!" if self.over_cap else ""),
            "└─────────────────────────────────────────────────────────",
        ]
        return "\n".join(lines)


def estimate(cfg: Config) -> CostEstimate:
    model = cfg.model
    usd_per_credit = cfg.usd_per_credit
    per_clip = model.cost_per_clip(cfg.clip_duration, usd_per_credit)

    # loop_back 은 첫 프레임으로 돌아오는 클립을 하나 더 만든다.
    planned = cfg.num_clips + (1 if cfg.loop_back else 0)
    video_subtotal = per_clip * planned

    # chain 모드는 클립 사이마다 프레임을 업스케일한다 (마지막 클립 뒤는 불필요).
    # montage 모드는 클립끼리 이어지지 않으므로 업스케일이 필요 없다.
    ups = cfg.upscaler
    if ups is not None and cfg.mode == "chain":
        n_ups = max(0, planned - 1)
        per_ups = ups.cost_per_image(usd_per_credit)
    else:
        n_ups, per_ups = 0, 0.0
    upscale_subtotal = n_ups * per_ups

    subtotal = video_subtotal + upscale_subtotal
    mult = float(cfg.cost_cfg.get("retry_multiplier", 1.0))
    return CostEstimate(
        provider=cfg.provider,
        model=model.key,
        num_clips=cfg.num_clips,
        clip_duration=cfg.clip_duration,
        video_clips_planned=planned,
        cost_per_clip=per_clip,
        video_subtotal=video_subtotal,
        upscale_images=n_ups,
        cost_per_upscale=per_ups,
        upscale_subtotal=upscale_subtotal,
        subtotal=subtotal,
        retry_multiplier=mult,
        expected=subtotal * mult,
        hard_cap=float(cfg.cost_cfg.get("hard_cap_usd", float("inf"))),
    )


def actual_cost(cfg: Config, clips_generated: int, upscales_done: int) -> float:
    """실제 호출 횟수로 계산한 사후 비용."""
    usd_per_credit = cfg.usd_per_credit
    total = cfg.model.cost_per_clip(cfg.clip_duration, usd_per_credit) * clips_generated
    ups = cfg.upscaler
    if ups is not None:
        total += ups.cost_per_image(usd_per_credit) * upscales_done
    return total
