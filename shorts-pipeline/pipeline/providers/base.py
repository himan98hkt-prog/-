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
    """provider 호출 실패. 재시도 가능 여부와 **과금 여부**를 함께 들고 다닌다.

    `billed` 가 왜 필요한가. 예전에는 실패한 호출을 전부 "돈이 나갔다" 로
    셌다. 그런데 키가 틀렸거나(401) 파라미터가 안 맞아(422) **접수조차 안
    된** 요청은 한 푼도 안 나간다. 그걸 3회 재시도하면 화면의 누적 비용에
    없던 $1.47 이 찍힌다. 비용을 보고 판단하는 사람에게는 거짓말이다.

      True  — 작업이 접수됐다. 결과를 못 받았어도 과금됐다고 봐야 한다.
      False — 접수 전에 끊겼다. 과금 없음.
      None  — 알 수 없음. 보수적으로 과금으로 센다.
    """

    def __init__(self, message: str, *, retryable: bool = True,
                 billed: bool | None = None, job_id: str | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.billed = billed
        self.job_id = job_id


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

# 한 클립을 얼마나 기다려 줄 것인가.
#
# 예전 값은 600초(10분)였는데, **이게 돈이 새는 구멍이었다.** 10초짜리
# hailuo 클립은 fal 대기열이 붐비면 10분을 넘긴다. 그때 타임아웃이 나면
# 예전 코드는 '재시도 가능' 으로 보고 **같은 클립을 새로 제출**했다.
# 먼저 낸 작업은 취소되지 않고 그대로 만들어져서 그대로 과금된다.
# 3회 재시도면 영상 하나에 클립 값 3번이 나간다. 결과물은 없는데.
#
# 그래서 두 가지를 바꿨다. 넉넉히 기다리고(30분), 그래도 안 끝나면
# **재제출하지 않는다.**
DEFAULT_TIMEOUT = 1800.0


class VideoProvider(ABC):
    """image-to-video provider."""

    name: str = "base"

    def __init__(
        self,
        endpoint: str,
        *,
        base_url: str | None = None,
        poll_interval: float = 5.0,
        timeout: float = DEFAULT_TIMEOUT,
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
                # 재시도하지 않는다. 저쪽에서는 아직 만들고 있을 수 있고,
                # 그 작업은 이미 과금됐다. 새로 제출하면 값을 두 번 낸다.
                raise ProviderError(
                    f"{label} 이(가) {self.timeout / 60:.0f}분 안에 끝나지 않았습니다.\n"
                    "  이 작업은 아직 만들어지는 중일 수 있고, 이미 과금됐습니다.\n"
                    "  값을 두 번 내지 않으려고 자동 재시도는 하지 않습니다.\n"
                    "  공급사 대시보드에서 결과를 확인하거나, "
                    "config.yaml 의 poll_timeout_seconds 를 늘리세요.",
                    retryable=False,
                    billed=True,
                )
            if elapsed >= next_beat:
                left = max(0, int(self.timeout - elapsed))
                print(f"      기다리는 중… {int(elapsed)}초 경과 "
                      f"(최대 {int(self.timeout)}초, {left}초 남음)", flush=True)
                next_beat += HEARTBEAT_SECONDS
            time.sleep(self.poll_interval)
