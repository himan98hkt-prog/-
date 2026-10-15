"""Higgsfield provider.

레퍼런스로 삼은 @cyborg.digitalart 이 실제로 쓰는 스택이다 (프로필 bio 기준:
Adobe | Openart | Higgsfield | hailuo | kling | wery ai | pixverse).

구독 크레딧으로 과금되므로 클립당 실효 단가가 fal 종량제보다 낮다.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import requests

from .base import (
    GenerationRequest,
    GenerationResult,
    ProviderError,
    VideoProvider,
)

_DEFAULT_BASE = "https://platform.higgsfield.ai/v1"
_RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}
_TERMINAL_OK = {"completed", "succeeded", "success"}
_TERMINAL_BAD = {"failed", "cancelled", "canceled", "error", "nsfw"}


class HiggsfieldProvider(VideoProvider):
    name = "higgsfield"

    def __init__(self, endpoint: str, *, base_url: str | None = None, **kwargs):
        super().__init__(endpoint, base_url=base_url or _DEFAULT_BASE, **kwargs)
        key = os.getenv("HIGGSFIELD_API_KEY")
        secret = os.getenv("HIGGSFIELD_API_SECRET")
        if not key or not secret:
            raise ProviderError(
                "HIGGSFIELD_API_KEY / HIGGSFIELD_API_SECRET 이 설정되지 않았습니다.\n"
                "  발급: https://cloud.higgsfield.ai/ → API keys",
                retryable=False,
            )
        self._headers = {
            "hf-api-key": key,
            "hf-secret": secret,
            "Content-Type": "application/json",
        }

    def generate(self, req: GenerationRequest, dest: Path) -> GenerationResult:
        started = time.time()
        params: dict = {
            "model": self.endpoint,
            "prompt": req.prompt,
            "duration": req.duration,
            "aspect_ratio": "9:16",
            "input_images": [{"type": "image_url", "image_url": _upload(req.image)}],
        }
        if req.negative_prompt:
            params["negative_prompt"] = req.negative_prompt
        if req.end_image is not None:
            params["end_image"] = {"type": "image_url", "image_url": _upload(req.end_image)}
        params.update(req.extra)

        self.log("higgsfield.submit", model=self.endpoint, duration=req.duration)
        submit = self._request("POST", f"{self.base_url}/text2video", json={"params": params})
        job_id = submit.get("id") or submit.get("job_id")
        if not job_id:
            raise ProviderError(f"higgsfield 응답에 작업 ID 가 없습니다: {submit}")
        self.log("higgsfield.queued", job_id=job_id)

        def check() -> tuple[bool, dict]:
            body = self._request("GET", f"{self.base_url}/jobs/{job_id}")
            status = str(body.get("status", "")).lower()
            if status in _TERMINAL_OK:
                return True, body
            if status in _TERMINAL_BAD:
                raise ProviderError(f"higgsfield 작업 실패 ({status}): {body}")
            return False, body

        result = self._poll(check, label=f"higgsfield 작업 {job_id}")
        self.log("higgsfield.completed", job_id=job_id)

        url = _find_media_url(result, (".mp4", ".webm", ".mov"))
        if not url:
            raise ProviderError(f"higgsfield 결과에 영상 URL 이 없습니다: {str(result)[:600]}")
        self._download(url, dest)
        return GenerationResult(dest, str(job_id), result, time.time() - started)

    def upscale(self, image: Path, dest: Path, endpoint: str) -> Path:
        payload = {"params": {
            "model": endpoint,
            "input_images": [{"type": "image_url", "image_url": _upload(image)}],
        }}
        submit = self._request("POST", f"{self.base_url}/image2image", json=payload)
        job_id = submit.get("id") or submit.get("job_id")

        def check() -> tuple[bool, dict]:
            body = self._request("GET", f"{self.base_url}/jobs/{job_id}")
            status = str(body.get("status", "")).lower()
            if status in _TERMINAL_OK:
                return True, body
            if status in _TERMINAL_BAD:
                raise ProviderError(f"higgsfield 업스케일 실패: {body}")
            return False, body

        result = self._poll(check, label=f"higgsfield 업스케일 {job_id}")
        url = _find_media_url(result, (".png", ".jpg", ".jpeg", ".webp"))
        if not url:
            raise ProviderError(f"업스케일 결과에 이미지 URL 이 없습니다: {str(result)[:400]}")
        return self._download(url, dest)

    def _request(self, method: str, url: str, **kwargs) -> dict:
        try:
            resp = requests.request(
                method, url, headers=self._headers, timeout=180, **kwargs
            )
        except requests.RequestException as exc:
            raise ProviderError(f"higgsfield 요청 실패 ({method} {url}): {exc}") from exc
        if resp.status_code >= 400:
            hint = ""
            if resp.status_code in (401, 403):
                hint = "\n  HIGGSFIELD_API_KEY / SECRET 을 확인하세요."
            elif resp.status_code == 402:
                hint = "\n  크레딧이 부족합니다."
            raise ProviderError(
                f"higgsfield HTTP {resp.status_code}: {resp.text[:400]}{hint}",
                retryable=resp.status_code in _RETRYABLE_STATUS,
            )
        return resp.json() if resp.content else {}


def _upload(path: Path) -> str:
    """로컬 이미지를 공개 URL 로 만든다.

    Higgsfield 는 data URI 를 받지 않으므로 임시 호스팅이 필요하다.
    PUBLIC_MEDIA_BASE_URL 이 있으면 그 아래 경로로 노출됐다고 가정한다.
    """
    base = os.getenv("PUBLIC_MEDIA_BASE_URL", "").rstrip("/")
    if not base:
        raise ProviderError(
            "higgsfield provider 는 이미지를 공개 URL 로 받습니다.\n"
            "  .env 의 PUBLIC_MEDIA_BASE_URL 을 설정하고 runs/ 를 정적 서빙하거나,\n"
            "  provider: fal 로 바꿔 쓰세요 (fal 은 로컬 파일을 data URI 로 올립니다).",
            retryable=False,
        )
    return f"{base}/{path.name}"


def _find_media_url(node, extensions: tuple[str, ...]) -> str | None:
    if isinstance(node, str):
        low = node.split("?")[0].lower()
        return node if node.startswith("http") and low.endswith(extensions) else None
    if isinstance(node, dict):
        for key in ("url", "output_url", "result_url", "video_url", "image_url"):
            val = node.get(key)
            if isinstance(val, str) and val.startswith("http"):
                low = val.split("?")[0].lower()
                if low.endswith(extensions):
                    return val
        for value in node.values():
            found = _find_media_url(value, extensions)
            if found:
                return found
        return None
    if isinstance(node, list):
        for item in node:
            found = _find_media_url(item, extensions)
            if found:
                return found
    return None
