"""KIS 인증: 접근토큰 발급·캐시·갱신, hashkey, 공통 헤더, TR_ID 매핑.

KIS는 토큰 발급 횟수에 제한이 있으므로 **매 실행마다 발급하지 않는다.**
`data/token.json`에 캐시하고 만료 10분 전이 되어야 재발급한다.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests

from config.loader import TOKEN_PATH, EnvConfig
from utils.logger import get_logger, register_secret

KST = ZoneInfo("Asia/Seoul")
logger = get_logger("kis_auth")

TOKEN_PATH_DEFAULT = TOKEN_PATH
TOKEN_REFRESH_MARGIN = timedelta(minutes=10)  # 만료 10분 전부터 재발급
HTTP_TIMEOUT = 10

# --------------------------------------------------------------------------- #
# TR_ID 매핑 — 실전(T 접두)과 모의(V 접두)를 이 한 곳에서만 관리한다.
# 시세성 조회(FH*)는 실전/모의 구분이 없다.
# --------------------------------------------------------------------------- #
TR_IDS: dict[str, tuple[str, str]] = {
    #  논리명            (실전,        모의)
    "price": ("FHKST01010100", "FHKST01010100"),
    "daily_ohlcv": ("FHKST03010100", "FHKST03010100"),
    "orderbook": ("FHKST01010200", "FHKST01010200"),
    "volume_rank": ("FHPST01710000", "FHPST01710000"),
    "balance": ("TTTC8434R", "VTTC8434R"),
    "orderable_cash": ("TTTC8908R", "VTTC8908R"),
    "order_buy": ("TTTC0802U", "VTTC0802U"),
    "order_sell": ("TTTC0801U", "VTTC0801U"),
    "order_cancel": ("TTTC0803U", "VTTC0803U"),
    "daily_ccld": ("TTTC8001R", "VTTC8001R"),
}

# 모의투자 도메인에서 제공되지 않는 기능
VTS_UNSUPPORTED = {"volume_rank"}

PATHS: dict[str, str] = {
    "token": "/oauth2/tokenP",
    "revoke": "/oauth2/revokeP",
    "hashkey": "/uapi/hashkey",
    "price": "/uapi/domestic-stock/v1/quotations/inquire-price",
    "daily_ohlcv": "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
    "orderbook": "/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn",
    "volume_rank": "/uapi/domestic-stock/v1/quotations/volume-rank",
    "balance": "/uapi/domestic-stock/v1/trading/inquire-balance",
    "orderable_cash": "/uapi/domestic-stock/v1/trading/inquire-psbl-order",
    "order_cash": "/uapi/domestic-stock/v1/trading/order-cash",
    "order_cancel": "/uapi/domestic-stock/v1/trading/order-rvsecncl",
    "daily_ccld": "/uapi/domestic-stock/v1/trading/inquire-daily-ccld",
}


class KisAuthError(Exception):
    """토큰 발급·hashkey 실패."""


class TokenManager:
    """접근토큰 캐시 관리자. 스레드 안전."""

    def __init__(self, env: EnvConfig, token_path: Path | str = TOKEN_PATH_DEFAULT) -> None:
        self.env = env
        self.token_path = Path(token_path)
        self._lock = threading.RLock()
        self._token: str | None = None
        self._expires_at: datetime | None = None
        register_secret(env.kis_app_key, env.kis_app_secret)

    # -- 캐시 입출력 ------------------------------------------------------- #

    def _load_cache(self) -> bool:
        """캐시 파일을 읽어 유효하면 메모리에 올린다. 성공 여부 반환."""
        if not self.token_path.exists():
            return False
        try:
            cached = json.loads(self.token_path.read_text(encoding="utf-8"))
            # 다른 환경(모의↔실전)에서 발급한 토큰은 재사용할 수 없다.
            if cached.get("kis_env") != self.env.kis_env:
                logger.info("캐시된 토큰의 환경이 달라 재발급합니다 (%s → %s)", cached.get("kis_env"), self.env.kis_env)
                return False
            if cached.get("app_key_tail") != self.env.kis_app_key[-4:]:
                logger.info("캐시된 토큰의 APP KEY가 달라 재발급합니다")
                return False
            token = cached["access_token"]
            expires_at = datetime.fromisoformat(cached["expires_at"])
        except (json.JSONDecodeError, KeyError, ValueError, OSError) as exc:
            logger.warning("토큰 캐시를 읽지 못해 재발급합니다: %s", exc)
            return False

        if self._is_expiring(expires_at):
            logger.info("캐시된 토큰이 곧 만료되어 재발급합니다 (만료: %s)", expires_at)
            return False

        self._token = token
        self._expires_at = expires_at
        register_secret(token)
        logger.info("캐시된 토큰 재사용 (만료: %s)", expires_at.strftime("%Y-%m-%d %H:%M:%S"))
        return True

    def _save_cache(self, token: str, expires_at: datetime) -> None:
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "access_token": token,
            "expires_at": expires_at.isoformat(),
            "kis_env": self.env.kis_env,
            "app_key_tail": self.env.kis_app_key[-4:],
            "issued_at": datetime.now(KST).isoformat(timespec="seconds"),
        }
        self.token_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            self.token_path.chmod(0o600)
        except OSError:  # 파일시스템이 지원하지 않으면 무시
            pass

    @staticmethod
    def _is_expiring(expires_at: datetime) -> bool:
        return datetime.now(KST) >= expires_at - TOKEN_REFRESH_MARGIN

    # -- 공개 API ---------------------------------------------------------- #

    def get_access_token(self, *, force: bool = False) -> str:
        """유효한 접근토큰을 반환한다. 만료 10분 전이 아니면 재발급하지 않는다."""
        with self._lock:
            if not force:
                if self._token and self._expires_at and not self._is_expiring(self._expires_at):
                    return self._token
                if self._load_cache() and self._token:
                    return self._token
            return self._issue_token()

    def invalidate(self) -> None:
        """토큰 만료(EGW00123) 응답을 받았을 때 캐시를 버린다."""
        with self._lock:
            self._token = None
            self._expires_at = None
            self.token_path.unlink(missing_ok=True)
            logger.info("토큰 캐시를 폐기했습니다")

    def _issue_token(self) -> str:
        url = f"{self.env.base_url}{PATHS['token']}"
        body = {
            "grant_type": "client_credentials",
            "appkey": self.env.kis_app_key,
            "appsecret": self.env.kis_app_secret,
        }
        logger.info("접근토큰 발급 요청 (%s)", self.env.kis_env)
        try:
            response = requests.post(url, json=body, timeout=HTTP_TIMEOUT)
        except requests.RequestException as exc:
            raise KisAuthError(f"토큰 발급 요청 실패: {exc}") from exc

        if response.status_code != 200:
            raise KisAuthError(f"토큰 발급 실패 (HTTP {response.status_code}): {_safe_text(response)}")
        try:
            data = response.json()
        except ValueError as exc:
            raise KisAuthError(f"토큰 응답 파싱 실패: {_safe_text(response)}") from exc

        token = data.get("access_token")
        if not token:
            raise KisAuthError(f"토큰 응답에 access_token 이 없습니다: {data.get('msg1') or data}")

        expires_at = _parse_expiry(data)
        register_secret(token)
        self._token = token
        self._expires_at = expires_at
        self._save_cache(token, expires_at)
        logger.info("접근토큰 발급 완료 (만료: %s)", expires_at.strftime("%Y-%m-%d %H:%M:%S"))
        return token

    def get_hashkey(self, body: dict[str, Any]) -> str:
        """주문 API용 hashkey 생성."""
        url = f"{self.env.base_url}{PATHS['hashkey']}"
        headers = {
            "content-type": "application/json; charset=utf-8",
            "appkey": self.env.kis_app_key,
            "appsecret": self.env.kis_app_secret,
        }
        try:
            response = requests.post(url, headers=headers, json=body, timeout=HTTP_TIMEOUT)
        except requests.RequestException as exc:
            raise KisAuthError(f"hashkey 요청 실패: {exc}") from exc
        if response.status_code != 200:
            raise KisAuthError(f"hashkey 실패 (HTTP {response.status_code}): {_safe_text(response)}")
        hashed = response.json().get("HASH")
        if not hashed:
            raise KisAuthError("hashkey 응답에 HASH 가 없습니다")
        return hashed

    def build_headers(self, tr_id: str, hashkey: str | None = None) -> dict[str, str]:
        """공통 헤더. 비밀값이 담기므로 이 dict 자체를 로그로 찍지 않는다."""
        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self.get_access_token()}",
            "appkey": self.env.kis_app_key,
            "appsecret": self.env.kis_app_secret,
            "tr_id": tr_id,
            "custtype": "P",
        }
        if hashkey:
            headers["hashkey"] = hashkey
        return headers

    def tr_id(self, name: str) -> str:
        """논리명 → 환경에 맞는 TR_ID."""
        try:
            real, vts = TR_IDS[name]
        except KeyError as exc:
            raise KisAuthError(f"알 수 없는 TR 이름: {name}") from exc
        return real if self.env.is_real else vts

    def url(self, name: str) -> str:
        try:
            return f"{self.env.base_url}{PATHS[name]}"
        except KeyError as exc:
            raise KisAuthError(f"알 수 없는 엔드포인트: {name}") from exc


def mask_headers(headers: dict[str, str]) -> dict[str, str]:
    """로그용 헤더 마스킹 (비밀값 노출 금지)."""
    from config.loader import mask

    masked = dict(headers)
    for key in ("authorization", "appkey", "appsecret", "hashkey"):
        if key in masked:
            masked[key] = mask(masked[key])
    return masked


def _parse_expiry(data: dict[str, Any]) -> datetime:
    """`access_token_token_expired`(KST 문자열) 우선, 없으면 `expires_in`(초)."""
    raw = data.get("access_token_token_expired")
    if raw:
        try:
            return datetime.strptime(str(raw), "%Y-%m-%d %H:%M:%S").replace(tzinfo=KST)
        except ValueError:
            logger.warning("만료시각 파싱 실패(%r) — expires_in 으로 대체합니다", raw)
    seconds = int(data.get("expires_in", 86400))
    return datetime.now(KST) + timedelta(seconds=seconds)


def _safe_text(response: requests.Response, limit: int = 300) -> str:
    text = (response.text or "").strip().replace("\n", " ")
    return text[:limit]
