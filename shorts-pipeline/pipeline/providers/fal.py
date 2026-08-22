"""fal.ai queue API 기반 provider.

제출(POST) → status 폴링 → 결과 조회 순서로 동작한다.
모델 엔드포인트는 config.yaml 에서 오므로 여기에 하드코딩하지 않는다.
"""

from __future__ import annotations

import base64
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

_DEFAULT_BASE = "https://queue.fal.run"
# 이 상태 코드는 다시 걸어볼 가치가 있다.
_RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}


# 이 크기를 넘으면 JPEG 로 다시 인코딩한다. 업로드가 길어지면 requests 의
# timeout 이 안 돈다 — 소켓이 계속 살아 있어서 만료 타이머가 매번 초기화된다.
# 4배 업스케일한 PNG(40~80MB)를 그대로 올리다 43분을 멈춘 사례가 있었다.
# 1080x1920 실사 프레임은 보통 1.5~3MB 다. 8MB 를 넘는다는 것은 업스케일
# 결과가 그대로 들어왔다는 뜻이다. 기준을 4MB 로 잡았더니 디테일이 아주
# 많은 정상 프레임까지 JPEG 로 바뀌어서 8MB 로 올렸다.
MAX_INLINE_MB = 8.0


def _data_uri(path: Path) -> str:
    """fal 은 공개 URL 또는 data URI 를 받는다. 로컬 파일은 data URI 로 올린다.

    너무 크면 JPEG 로 줄여서 보낸다. 화질보다 **끝나는 것**이 먼저다.
    """
    size_mb = path.stat().st_size / 1e6
    if size_mb > MAX_INLINE_MB:
        shrunk = _to_jpeg(path)
        if shrunk is not None:
            data, mime, new_mb = shrunk
            print(f"    입력 이미지가 커서 JPEG 로 줄여 보냅니다 "
                  f"({size_mb:.1f}MB -> {new_mb:.1f}MB)", flush=True)
            return f"data:{mime};base64," + base64.b64encode(data).decode()

    suffix = path.suffix.lower().lstrip(".")
    mime = "image/jpeg" if suffix in ("jpg", "jpeg") else f"image/{suffix or 'png'}"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def _to_jpeg(path: Path) -> tuple[bytes, str, float] | None:
    """JPEG 로 다시 인코딩한 바이트. 실패하면 None (원본을 그대로 쓴다)."""
    import io

    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        with Image.open(path) as img:
            rgb = img.convert("RGB")
            buf = io.BytesIO()
            rgb.save(buf, "JPEG", quality=92, optimize=True)
    except OSError:
        return None
    data = buf.getvalue()
    return data, "image/jpeg", len(data) / 1e6


class FalProvider(VideoProvider):
    name = "fal"

    def __init__(self, endpoint: str, *, base_url: str | None = None, **kwargs):
        super().__init__(endpoint, base_url=base_url or _DEFAULT_BASE, **kwargs)
        key = os.getenv("FAL_API_KEY")
        if not key:
            raise ProviderError(
                "FAL_API_KEY 가 설정되지 않았습니다. .env 에 추가하세요.\n"
                "  키 발급: https://fal.ai/dashboard/keys",
                retryable=False,
            )
        self._headers = {
            "Authorization": f"Key {key}",
            "Content-Type": "application/json",
        }

    # ── 영상 생성 ──────────────────────────────────────────────────────
    def generate(self, req: GenerationRequest, dest: Path) -> GenerationResult:
        started = time.time()
        payload: dict = {
            "image_url": _data_uri(req.image),
            "prompt": req.prompt,
            "duration": req.duration,
        }
        if req.negative_prompt:
            payload["negative_prompt"] = req.negative_prompt
        if req.end_image is not None:
            payload["tail_image_url"] = _data_uri(req.end_image)
        payload.update(req.extra)

        # 로그에는 이미지 본문을 빼고 남긴다. data URI 는 수 MB 라 log 를 망친다.
        loggable = {k: v for k, v in payload.items() if not k.endswith("image_url")}
        self.log("fal.submit", endpoint=self.endpoint, payload=loggable)
        mb = sum(len(v) for k, v in payload.items()
                 if k.endswith("image_url") and isinstance(v, str)) / 1e6
        print(f"    fal 에 올리는 중… (이미지 {mb:.1f}MB)", flush=True)

        submit = self._request(
            "POST", f"{self.base_url}/{self.endpoint}", json=payload
        )
        job_id = submit.get("request_id")
        if not job_id:
            raise ProviderError(f"fal 응답에 request_id 가 없습니다: {submit}")
        self.log("fal.queued", job_id=job_id)

        status_url = submit.get("status_url") or (
            f"{self.base_url}/{self.endpoint}/requests/{job_id}/status"
        )
        response_url = submit.get("response_url") or (
            f"{self.base_url}/{self.endpoint}/requests/{job_id}"
        )

        def check() -> tuple[bool, dict]:
            body = self._request("GET", status_url)
            status = body.get("status")
            if status == "COMPLETED":
                return True, body
            if status in ("FAILED", "CANCELLED", "ERROR"):
                raise ProviderError(f"fal 작업 실패 ({status}): {body}")
            return False, body

        self._poll(check, label=f"fal 작업 {job_id}")
        result = self._request("GET", response_url)
        self.log("fal.completed", job_id=job_id, result=_trim(result))

        url = _find_video_url(result)
        if not url:
            raise ProviderError(f"fal 결과에서 영상 URL 을 찾지 못했습니다: {_trim(result)}")
        self._download(url, dest)
        return GenerationResult(dest, job_id, result, time.time() - started)

    # ── 업스케일 ──────────────────────────────────────────────────────
    def upscale(self, image: Path, dest: Path, endpoint: str) -> Path:
        payload = {"image_url": _data_uri(image)}
        self.log("fal.upscale.submit", endpoint=endpoint)
        submit = self._request("POST", f"{self.base_url}/{endpoint}", json=payload)
        job_id = submit.get("request_id")
        status_url = submit.get("status_url") or (
            f"{self.base_url}/{endpoint}/requests/{job_id}/status"
        )
        response_url = submit.get("response_url") or (
            f"{self.base_url}/{endpoint}/requests/{job_id}"
        )

        def check() -> tuple[bool, dict]:
            body = self._request("GET", status_url)
            if body.get("status") == "COMPLETED":
                return True, body
            if body.get("status") in ("FAILED", "CANCELLED", "ERROR"):
                raise ProviderError(f"fal 업스케일 실패: {body}")
            return False, body

        self._poll(check, label=f"fal 업스케일 {job_id}")
        result = self._request("GET", response_url)
        url = _find_image_url(result)
        if not url:
            raise ProviderError(f"업스케일 결과에서 이미지 URL 을 찾지 못했습니다: {_trim(result)}")
        return self._download(url, dest)

    # ── HTTP ─────────────────────────────────────────────────────────
    def _request(self, method: str, url: str, **kwargs) -> dict:
        try:
            resp = requests.request(
                method, url, headers=self._headers, timeout=180, **kwargs
            )
        except requests.RequestException as exc:
            raise ProviderError(f"fal 요청 실패 ({method} {url}): {exc}") from exc

        if resp.status_code >= 400:
            retryable = resp.status_code in _RETRYABLE_STATUS
            hint = ""
            if resp.status_code in (401, 403):
                hint = "\n  FAL_API_KEY 가 유효한지 확인하세요."
            elif resp.status_code == 402:
                hint = "\n  fal 잔액이 부족합니다."
            elif resp.status_code == 422:
                hint = "\n  모델이 받지 않는 파라미터일 수 있습니다. config 의 endpoint 를 확인하세요."
            raise ProviderError(
                f"fal HTTP {resp.status_code}: {resp.text[:400]}{hint}",
                retryable=retryable,
            )
        if not resp.content:
            return {}
        try:
            return resp.json()
        except ValueError as exc:
            raise ProviderError(f"fal 응답이 JSON 이 아닙니다: {resp.text[:300]}") from exc


def _find_video_url(payload: dict) -> str | None:
    """fal 모델마다 결과 스키마가 조금씩 달라 재귀로 찾는다."""
    return _find_url(payload, (".mp4", ".webm", ".mov"), ("video",))


def _find_image_url(payload: dict) -> str | None:
    return _find_url(payload, (".png", ".jpg", ".jpeg", ".webp"), ("image",))


def _find_url(node, extensions: tuple[str, ...], key_hints: tuple[str, ...]) -> str | None:
    if isinstance(node, str):
        low = node.split("?")[0].lower()
        if node.startswith("http") and low.endswith(extensions):
            return node
        return None
    if isinstance(node, dict):
        # url 키를 가진 dict 를 먼저 본다 ({"video": {"url": ...}} 형태).
        for hint in key_hints:
            sub = node.get(hint)
            if isinstance(sub, dict) and isinstance(sub.get("url"), str):
                return sub["url"]
        if isinstance(node.get("url"), str) and node["url"].startswith("http"):
            return node["url"]
        for value in node.values():
            found = _find_url(value, extensions, key_hints)
            if found:
                return found
        return None
    if isinstance(node, list):
        for item in node:
            found = _find_url(item, extensions, key_hints)
            if found:
                return found
    return None


def _trim(payload: dict, limit: int = 1500) -> dict | str:
    text = str(payload)
    return payload if len(text) <= limit else text[:limit] + "…"
