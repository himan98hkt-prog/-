"""영상 생성 provider 의 공통 인터페이스.

새 provider 를 붙일 때는 이 클래스만 구현하면 파이프라인 나머지는 그대로 돈다.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import requests


class ProviderError(Exception):
    """provider 호출 실패. 재시도 가능 여부를 함께 들고 다닌다."""

    def __init__(self, message: str, *, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


@dataclass
class GenerationRequest:
    image: Path
    prompt: str
    duration: int
    negative_prompt: str = ""
    end_image: Path | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationResult:
    video_path: Path
    job_id: str
    raw_response: dict[str, Any]
    elapsed_seconds: float


# 기다리는 동안 이 간격으로 한 줄씩 찍는다. 화면에서 '살아 있음' 을 보여준다.
HEARTBEAT_SECONDS = 30.0


class VideoProvider(ABC):
    """image-to-video provider."""

    name: str = "base"

    def __init__(
        self,
        endpoint: str,
        *,
        base_url: str | None = None,
        poll_interval: float = 5.0,
        timeout: float = 600.0,
        on_log: Callable[[str, dict], None] | None = None,
    ):
        self.endpoint = endpoint
        self.base_url = (base_url or "").rstrip("/")
        self.poll_interval = poll_interval
        self.timeout = timeout
        self._on_log = on_log or (lambda event, payload: None)

    def log(self, event: str, **payload: Any) -> None:
        self._on_log(event, payload)

    @abstractmethod
    def generate(self, req: GenerationRequest, dest: Path) -> GenerationResult:
        """영상을 만들어 dest 에 저장하고 결과를 돌려준다."""

    @abstractmethod
    def upscale(self, image: Path, dest: Path, endpoint: str) -> Path:
        """이미지를 업스케일해 dest 에 저장한다."""

    # ── 공통 헬퍼 ──────────────────────────────────────────────────────
    def _download(self, url: str, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(url, stream=True, timeout=180) as resp:
            resp.raise_for_status()
            with dest.open("wb") as fh:
                for chunk in resp.iter_content(chunk_size=1 << 20):
                    fh.write(chunk)
        if dest.stat().st_size == 0:
            raise ProviderError(f"다운로드한 파일이 비어 있습니다: {url}")
        return dest

    def _poll(
        self,
        check: Callable[[], tuple[bool, dict]],
        *,
        label: str,
    ) -> dict:
        """완료될 때까지 폴링. (완료여부, payload) 를 주는 check 를 반복 호출한다.

        기다리는 동안 30초마다 한 줄씩 찍는다. 안 그러면 클립 하나에 몇 분씩
        아무 출력이 없어서, 작업실 화면만 보는 사람은 **멈춘 것과 구별할 수
        없다.** 실제로 "만들다가 중단되어 멈춰 있다" 는 문의가 나왔다.
        """
        started = time.time()
        next_beat = HEARTBEAT_SECONDS
        while True:
            done, payload = check()
            if done:
                return payload
            elapsed = time.time() - started
            if elapsed > self.timeout:
                raise ProviderError(
                    f"{label} 이(가) {self.timeout:.0f}초 안에 끝나지 않았습니다. "
                    "타임아웃을 늘리거나 더 짧은 클립으로 시도하세요."
                )
            if elapsed >= next_beat:
                left = max(0, int(self.timeout - elapsed))
                print(f"      기다리는 중… {int(elapsed)}초 경과 "
                      f"(최대 {int(self.timeout)}초, {left}초 남음)", flush=True)
                next_beat += HEARTBEAT_SECONDS
            time.sleep(self.poll_interval)
