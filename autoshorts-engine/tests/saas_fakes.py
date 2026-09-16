"""Phase 2 테스트용 가짜 파이프라인.

엔진 자체는 Phase 0/1 테스트가 검증한다. 여기서 확인하려는 것은 **엔진 바깥**
(큐·워커·격리·정산)이므로, 실제 렌더 대신 같은 모양의 결과를 즉시 돌려준다.
실제 엔진을 태우는 E2E 는 별도 스크립트(`scripts/phase2_e2e.py`)로 돌린다.
"""

from __future__ import annotations

import time
from pathlib import Path

from autoshorts.models import Clip
from autoshorts.pipeline import PipelineResult
from autoshorts.video_renderer import RenderResult


def fake_pipeline(
    *, clips: int = 2, delay: float = 0.0, fail_with: BaseException | None = None
):
    """``run_pipeline`` 과 같은 서명을 가진 대역을 만든다."""

    def run(settings, *, on_progress=None, clips_override=None):
        def notify(stage, fraction, message):
            if on_progress:
                on_progress(stage, fraction, message)

        notify("ingest", 0.5, "소스를 준비합니다.")
        notify("transcribe", 0.5, "전사합니다.")
        if delay:
            time.sleep(delay)
        notify("analyze", 0.5, "구간을 고릅니다.")
        if fail_with is not None:
            raise fail_with

        output_dir = Path(settings.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        renders = []
        for index in range(clips):
            path = output_dir / f"output_{index + 1}_테스트클립.mp4"
            path.write_bytes(b"\x00" * 2048)
            clip = Clip(
                index=index + 1,
                start=float(index * 60),
                end=float(index * 60 + 40),
                title=f"테스트 클립 {index + 1}",
                score=8.0 - index,
                reason="테스트",
            )
            renders.append(
                RenderResult(clip=clip, output_path=path, duration=40.0, size_bytes=2048)
            )
        notify("render", 1.0, "렌더를 마쳤습니다.")

        transcript_path = output_dir / "transcription.json"
        transcript_path.write_text("{}", encoding="utf-8")
        return PipelineResult(
            source=settings.source,
            transcript_path=transcript_path,
            clips=[r.clip for r in renders],
            renders=renders,
            used_offline_analysis=True,
        )

    return run
