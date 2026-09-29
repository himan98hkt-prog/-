"""LTX API (Lightricks 클라우드) 로 클립을 만든다.

**LTX Desktop 이 8GB 그래픽카드에서 영상을 만드는 방법이 바로 이것이다.**
그 앱은 VRAM 15GB 미만이면 내 PC 생성을 끄고, 설정에 넣어 둔 LTX API 키로
이 API 를 부른다. 앱에서 만들어 마음에 들었던 영상과 같은 모델 · 같은 경로다.
다른 점은 앱을 켜 두지 않아도 아침 예약이 혼자 돈다는 것뿐이다.

호출 순서는 LTX Desktop 의 services/ltx_api_client 를 그대로 따른다.

  1. POST /v1/upload            -> 서명된 업로드 주소와 storage_uri
  2. PUT  <upload_url>          -> 입력 이미지
  3. POST /v1/image-to-video    -> 영상 (본문이 영상이거나, video_url 이 온다)

**돈이 든다.** 초당 과금이다 (2026-09, LTX-2.5 Fast 720p $0.09 · 1080p $0.13).
"""

from __future__ import annotations

import mimetypes
import os
import shutil
import time
from pathlib import Path
from typing import Any

import requests

from .base import GenerationRequest, GenerationResult, ProviderError, VideoProvider

_DEFAULT_BASE = "https://api.ltx.video"

# 세로(9:16) 크기. LTX Desktop 의 _API_PIXELS_16_9 를 뒤집은 것이다.
RESOLUTIONS = {"720p": "720x1280", "1080p": "1080x1920"}

# 모델별로 받는 길이(초). LTX Desktop 의 api_model_specs.py 와 같다.
# Fast 는 720p/1080p 에서 20초까지, Pro 2.5 는 10초까지.
_TO_10 = (2, 3, 4, 5, 6, 8, 10)
_TO_20 = _TO_10 + (12, 14, 16, 18, 20)
DURATIONS = {"ltx-2-5-fast": _TO_20, "ltx-2-5-pro": _TO_10}
FPS = {"ltx-2-5-fast": (24, 25), "ltx-2-5-pro": (24, 25, 50)}

# config.yaml 에 providers.ltx 가 없을 때 쓰는 기본값 (업데이트는 사용자
# config 를 덮어쓰지 않으므로 대부분 없다).
DEFAULTS: dict[str, Any] = {
    "endpoint_base": _DEFAULT_BASE,
    "fps": 24,
    "models": {
        "ltx_25_fast_1080p": {"endpoint": "ltx-2-5-fast/1080p", "price_per_second": 0.13,
                              "max_duration": 20, "supports_end_image": True,
                              "supports_negative": False},
        "ltx_25_fast_720p": {"endpoint": "ltx-2-5-fast/720p", "price_per_second": 0.09,
                             "max_duration": 20, "supports_end_image": True,
                             "supports_negative": False},
        "ltx_25_pro_1080p": {"endpoint": "ltx-2-5-pro/1080p", "price_per_second": 0.17,
                             "max_duration": 10, "supports_end_image": True,
                             "supports_negative": False},
        "ltx_25_pro_720p": {"endpoint": "ltx-2-5-pro/720p", "price_per_second": 0.12,
                            "max_duration": 10, "supports_end_image": True,
                            "supports_negative": False},
    },
    "upscalers": {
        # 클립 사이 프레임. Real-ESRGAN 이 있으면 쓰고, 없으면 그대로 넘긴다.
        "local": {"endpoint": "realesrgan", "price_per_image": 0},
    },
}
DEFAULT_MODEL = "ltx_25_fast_1080p"


def settings_with_defaults(cfg: dict | None) -> dict:
    import copy

    out = copy.deepcopy(DEFAULTS)
    for key, value in (cfg or {}).items():
        if key in ("models", "upscalers") and isinstance(value, dict):
            out[key].update(value)
        elif value not in (None, ""):
            out[key] = value
    return out


def parse_endpoint(endpoint: str) -> tuple[str, str]:
    """'ltx-2-5-fast/1080p' -> ('ltx-2-5-fast', '1080x1920')."""
    model, _, res = (endpoint or "").partition("/")
    if model not in DURATIONS:
        raise ProviderError(f"알 수 없는 LTX 모델: {endpoint}", retryable=False, billed=False)
    if (res or "1080p") not in RESOLUTIONS:
        raise ProviderError(f"LTX 해상도는 720p 또는 1080p 입니다 (지금 {res})",
                            retryable=False, billed=False)
    return model, RESOLUTIONS[res or "1080p"]


class LtxApiProvider(VideoProvider):
    name = "ltx"

    def __init__(self, endpoint: str, *, base_url: str | None = None, **kwargs):
        settings = kwargs.pop("settings", None)
        super().__init__(endpoint, base_url=base_url or _DEFAULT_BASE, **kwargs)
        self.settings = settings_with_defaults(settings)
        key = (os.getenv("LTX_API_KEY") or "").strip()
        if not key:
            raise ProviderError(
                "LTX_API_KEY 가 설정되지 않았습니다.\n"
                "  LTX Desktop 에 넣어 둔 키를 쓰면 됩니다 — 앱의 설정(Settings)에서 복사하거나\n"
                "  https://console.ltx.video 에서 새로 만들어 작업실 [설정] 탭에 붙여넣으세요.",
                retryable=False, billed=False)
        self._key = key

    # ── 요청 ─────────────────────────────────────────────────────────
    def payload(self, req: GenerationRequest, image_uri: str,
                last_uri: str | None) -> dict[str, Any]:
        model, resolution = parse_endpoint(self.endpoint)
        seconds = int(req.duration)
        if seconds not in DURATIONS[model]:
            allowed = ", ".join(str(d) for d in DURATIONS[model])
            raise ProviderError(
                f"{model} 은(는) {seconds}초를 못 만듭니다. 되는 길이: {allowed}초",
                retryable=False, billed=False)
        fps = int(self.settings.get("fps") or 24)
        if fps not in FPS[model]:
            fps = FPS[model][0]
        body: dict[str, Any] = {
            "prompt": req.prompt,
            "image_uri": image_uri,
            "model": model,
            "resolution": resolution,
            "duration": float(seconds),
            "fps": float(fps),
            # 소리는 우리가 음악으로 깐다. 켜도 값은 같지만 받을 필요가 없다.
            "generate_audio": False,
        }
        if last_uri:
            body["last_frame_uri"] = last_uri
        return body

    def generate(self, req: GenerationRequest, dest: Path) -> GenerationResult:
        started = time.time()
        image_uri = self.upload(req.image)
        last_uri = self.upload(req.end_image) if req.end_image else None
        body = self.payload(req, image_uri, last_uri)
        self.log("ltx_api.submit", model=body["model"], resolution=body["resolution"],
                 duration=body["duration"])
        print(f"      LTX 클라우드에서 만드는 중… ({body['model']} {body['resolution']} "
              f"{int(body['duration'])}초, 1~3분)", flush=True)

        try:
            # 동기식이다. LTX Desktop 도 20분(1200초)까지 기다린다.
            resp = requests.post(f"{self.base_url}/v1/image-to-video", json=body,
                                 headers=self._headers(json=True),
                                 timeout=max(1200, int(self.timeout)))
        except requests.Timeout as exc:
            # 저쪽에서는 이미 만들고 있다. 다시 보내면 값을 두 번 낸다.
            raise ProviderError(
                "LTX 가 20분 안에 영상을 돌려주지 않았습니다. 이미 과금됐을 수 있어 "
                "다시 보내지 않습니다. https://console.ltx.video 에서 확인하세요.",
                retryable=False, billed=True) from exc
        except requests.RequestException as exc:
            raise ProviderError(f"LTX 에 연결하지 못했습니다: {exc}",
                                retryable=True, billed=None) from exc

        data = self._video_bytes(resp)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        elapsed = time.time() - started
        self.log("ltx_api.done", path=str(dest), seconds=round(elapsed, 1),
                 request_id=resp.headers.get("x-request-id", ""))
        return GenerationResult(video_path=dest,
                                job_id=resp.headers.get("x-request-id", f"ltx-{int(started)}"),
                                raw_response={"status": resp.status_code},
                                elapsed_seconds=elapsed)

    def upload(self, path: Path) -> str:
        """이미지를 올리고 storage_uri 를 돌려준다. 여기서 실패하면 돈은 안 나갔다."""
        try:
            init = requests.post(f"{self.base_url}/v1/upload", headers=self._headers(),
                                 timeout=60)
        except requests.RequestException as exc:
            raise ProviderError(f"LTX 업로드 준비 실패: {exc}",
                                retryable=True, billed=False) from exc
        if init.status_code != 200:
            raise self._http_error(init, stage="업로드 준비", billed=False)
        try:
            info = init.json()
            upload_url, storage_uri = str(info["upload_url"]), str(info["storage_uri"])
            extra = dict(info.get("required_headers") or {})
        except (ValueError, KeyError, TypeError) as exc:
            raise ProviderError("LTX 업로드 응답을 읽지 못했습니다.",
                                retryable=True, billed=False) from exc

        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        try:
            with path.open("rb") as fh:
                put = requests.put(upload_url, data=fh,
                                   headers={"Content-Type": mime, **extra}, timeout=300)
        except requests.RequestException as exc:
            raise ProviderError(f"LTX 이미지 업로드 실패: {exc}",
                                retryable=True, billed=False) from exc
        if put.status_code not in (200, 201):
            raise ProviderError(f"LTX 이미지 업로드 실패 ({put.status_code})",
                                retryable=True, billed=False)
        return storage_uri

    # ── 응답 ─────────────────────────────────────────────────────────
    def _video_bytes(self, resp: requests.Response) -> bytes:
        if resp.status_code != 200:
            raise self._http_error(resp, stage="생성", billed=None)
        ctype = (resp.headers.get("Content-Type") or "").lower()
        if "video" in ctype or "octet-stream" in ctype:
            if not resp.content:
                raise ProviderError("LTX 가 빈 영상을 돌려줬습니다.", retryable=False, billed=True)
            return resp.content
        try:
            payload = resp.json()
        except ValueError as exc:
            raise ProviderError("LTX 응답을 읽지 못했습니다.", retryable=False,
                                billed=True) from exc
        url = (payload.get("video_url") or payload.get("output_video")
               or (payload.get("result") or {}).get("video_url"))
        if not url:
            raise ProviderError(f"LTX 응답에 영상 주소가 없습니다: {str(payload)[:300]}",
                                retryable=False, billed=True)
        try:
            dl = requests.get(url, headers=self._headers(), timeout=300)
        except requests.RequestException as exc:
            raise ProviderError(f"만든 영상을 받지 못했습니다: {exc}",
                                retryable=False, billed=True) from exc
        if dl.status_code != 200 or not dl.content:
            raise ProviderError(f"만든 영상을 받지 못했습니다 ({dl.status_code})",
                                retryable=False, billed=True)
        return dl.content

    def _http_error(self, resp: requests.Response, *, stage: str,
                    billed: bool | None) -> ProviderError:
        code = resp.status_code
        text = (resp.text or "")[:300]
        if code == 401:
            return ProviderError("LTX_API_KEY 가 틀렸습니다. LTX Desktop 설정의 키를 다시 "
                                 "복사해 넣으세요.", retryable=False, billed=False)
        if code == 402:
            return ProviderError(
                "LTX 크레딧이 모자랍니다. https://console.ltx.video 에서 충전하세요.",
                retryable=False, billed=False)
        if code in (400, 404, 422):
            return ProviderError(f"LTX 가 요청을 거절했습니다 ({code}): {text}",
                                 retryable=False, billed=False)
        if code == 429:
            return ProviderError("LTX 가 잠시 요청이 많다고 합니다 (429).",
                                 retryable=True, billed=False)
        return ProviderError(f"LTX {stage} 실패 ({code}): {text}",
                             retryable=code >= 500, billed=billed)

    def _headers(self, json: bool = False) -> dict[str, str]:
        h = {"Authorization": f"Bearer {self._key}"}
        if json:
            h["Content-Type"] = "application/json"
        return h

    # ── 클립 사이 프레임 ─────────────────────────────────────────────
    def upscale(self, image: Path, dest: Path, endpoint: str) -> Path:
        """LTX API 에는 이미지 업스케일이 없다. Real-ESRGAN 이 있으면 쓰고, 없으면 그대로."""
        from pipeline import upscale

        dest.parent.mkdir(parents=True, exist_ok=True)
        exe = upscale.find_realesrgan()
        if exe is None:
            shutil.copyfile(image, dest)
            return dest
        try:
            return upscale.upscale_image(image, dest, exe=exe,
                                         model="realesr-animevideov3", scale=2)
        except Exception as exc:                        # noqa: BLE001
            raise ProviderError(f"프레임 업스케일 실패: {exc}",
                                retryable=False, billed=False) from exc
