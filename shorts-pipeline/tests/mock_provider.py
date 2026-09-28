"""API 없이 파이프라인 전체를 돌리기 위한 가짜 provider.

실제 모델 대신 ffmpeg 로 합성 클립을 만든다. 체이닝 로직 · 프레임 추출 ·
합성 · resume 을 API 비용 0원으로 검증할 수 있다.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

from pipeline.providers import register
from pipeline.providers.base import (
    GenerationRequest,
    GenerationResult,
    ProviderError,
    VideoProvider,
)


class MockProvider(VideoProvider):
    name = "mock"
    counter = 0
    fail_on: set[int] = set()      # 이 회차에서 실패시킨다 (재시도 경로 검증)
    _attempts: dict[int, int] = {}

    # LTX-2 처럼 소리를 함께 만드는 모델을 흉내낸다. 기본은 꺼 둔다 —
    # 기존 검사들은 소리 없는 클립을 전제로 쓰여 있다.
    with_audio = False
    # 모델에 실제로 무엇이 전달됐는지 보기 위해 받은 요청을 남긴다.
    requests: list[GenerationRequest] = []

    def generate(self, req: GenerationRequest, dest: Path) -> GenerationResult:
        MockProvider.counter += 1
        n = MockProvider.counter
        idx = int(dest.stem.split("_")[1])
        MockProvider._attempts[idx] = MockProvider._attempts.get(idx, 0) + 1
        MockProvider.requests.append(req)

        if idx in MockProvider.fail_on and MockProvider._attempts[idx] < 2:
            raise ProviderError(f"mock 강제 실패 (clip {idx})", retryable=True)

        if not req.image.exists():
            raise ProviderError(f"입력 이미지가 없다: {req.image}", retryable=False)

        dest.parent.mkdir(parents=True, exist_ok=True)
        hue = (n * 47) % 360
        args = ["ffmpeg", "-v", "error", "-f", "lavfi",
                "-i", f"testsrc2=size=540x960:rate=30:duration={req.duration}"]
        if MockProvider.with_audio:
            args += ["-f", "lavfi",
                     "-i", f"sine=frequency={220 + hue}:duration={req.duration}",
                     "-c:a", "aac", "-shortest"]
        args += ["-vf", f"hue=h={hue}",
                 "-c:v", "libx264", "-pix_fmt", "yuv420p", "-y", str(dest)]
        subprocess.run(args, check=True, capture_output=True)
        return GenerationResult(dest, f"mock-{n}", {"mock": True}, 0.01)

    def upscale(self, image: Path, dest: Path, endpoint: str) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(image),
             "-vf", "scale=iw*2:ih*2:flags=lanczos", "-y", str(dest)],
            check=True, capture_output=True,
        )
        return dest


register("mock", MockProvider)
