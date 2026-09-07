"""KIS REST API 래퍼 (시세·잔고·주문).

- HTTP 오류와 `rt_cd != "0"` 은 모두 `KisApiError`로 변환한다.
- 초당 호출 제한(모의 2건/초, 실전 20건/초)을 내장 rate limiter로 지킨다.
- 조회 API는 재시도하지만 **주문 API는 재시도하지 않는다**(중복 주문 방지).
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Literal

import pandas as pd
import requests

from config.loader import EnvConfig
from trading.kis_auth import VTS_UNSUPPORTED, KisAuthError, TokenManager
from utils.logger import get_logger
from utils.retry import RetryExhausted, retry

logger = get_logger("kis_api")

HTTP_TIMEOUT = 15
MAX_ROWS_PER_DAILY_CALL = 100  # KIS 기간별 시세 1회 최대 100건

# 초당 호출 제한 (여유분 1건씩 뺀 보수적 값)
RATE_LIMITS: dict[str, float] = {"VTS": 2, "REAL": 19}

# 재시도해도 되는 KIS 오류 코드
RETRYABLE_MSG_CODES = {
    "EGW00201",  # 초당 거래건수 초과
    "EGW00202",  # 초당 거래건수 초과(계좌)
}
TOKEN_EXPIRED_MSG_CODES = {"EGW00123", "EGW00121"}

Side = Literal["BUY", "SELL"]
OrderType = Literal["market", "limit"]

ORD_DVSN = {"market": "01", "limit": "00"}


class KisApiError(Exception):
    """KIS API 호출 실패 (HTTP 오류 또는 rt_cd != '0')."""

    def __init__(
        self,
        message: str,
        *,
        rt_cd: str | None = None,
        msg_cd: str | None = None,
        msg1: str | None = None,
        http_status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.rt_cd = rt_cd
        self.msg_cd = msg_cd
        self.msg1 = msg1
        self.http_status = http_status

    @property
    def is_token_expired(self) -> bool:
        return self.msg_cd in TOKEN_EXPIRED_MSG_CODES


class RetryableKisError(KisApiError):
    """일시적 오류 — `utils.retry`가 다시 시도한다."""


# --------------------------------------------------------------------------- #
# 반환 모델
# --------------------------------------------------------------------------- #


@dataclass
class Holding:
    code: str
    name: str
    qty: int
    orderable_qty: int
    avg_price: float
    current_price: float
    eval_amount: float
    pnl_amount: float
    pnl_pct: float


@dataclass
class Balance:
    holdings: list[Holding] = field(default_factory=list)
    deposit: float = 0.0  # 예수금 총금액
    orderable_cash: float = 0.0  # D+2 예수금 기준 주문가능현금
    total_eval_amount: float = 0.0  # 유가증권 평가금액
    net_asset: float = 0.0  # 순자산
    total_pnl_amount: float = 0.0

    def by_code(self, code: str) -> Holding | None:
        return next((h for h in self.holdings if h.code == code), None)


@dataclass
class OrderResult:
    order_no: str
    org_no: str
    order_time: str
    code: str
    side: Side
    qty: int
    price: int
    order_type: OrderType


@dataclass
class OrderStatus:
    order_no: str
    code: str
    name: str
    side: Side | None
    order_qty: int
    filled_qty: int
    remain_qty: int
    filled_price: float
    filled_amount: float
    status: str  # 원문 상태 문자열
    org_no: str = ""

    @property
    def is_filled(self) -> bool:
        return self.order_qty > 0 and self.filled_qty >= self.order_qty

    @property
    def is_partially_filled(self) -> bool:
        return 0 < self.filled_qty < self.order_qty


# --------------------------------------------------------------------------- #
# Rate limiter
# --------------------------------------------------------------------------- #


class RateLimiter:
    """초당 최대 호출 수를 지키는 슬라이딩 윈도우 리미터 (스레드 안전)."""

    def __init__(self, max_calls_per_sec: float, window: float = 1.0) -> None:
        self.max_calls = max_calls_per_sec
        self.window = window
        self._calls: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                while self._calls and now - self._calls[0] >= self.window:
                    self._calls.popleft()
                if len(self._calls) < self.max_calls:
                    self._calls.append(now)
                    return
                sleep_for = self.window - (now - self._calls[0])
            time.sleep(max(sleep_for, 0.01))


# --------------------------------------------------------------------------- #
# 값 파싱 헬퍼
# --------------------------------------------------------------------------- #


def _to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    text = str(value).strip().replace(",", "")
    if not text or text in ("-", "."):
        return default
    try:
        return float(text)
    except ValueError:
        return default


def _to_int(value: Any, default: int = 0) -> int:
    return int(_to_float(value, default))


# --------------------------------------------------------------------------- #
# API 래퍼
# --------------------------------------------------------------------------- #


class KisApi:
    """KIS 국내주식 REST API 래퍼."""

    def __init__(
        self,
        env: EnvConfig,
        auth: TokenManager,
        *,
        rate_limit: float | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.env = env
        self.auth = auth
        self.limiter = RateLimiter(rate_limit or RATE_LIMITS[env.kis_env])
        self.session = session or requests.Session()

    # -- 내부 호출 --------------------------------------------------------- #

    def _execute(
        self,
        name: str,
        tr_name: str,
        *,
        method: str = "GET",
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        use_hashkey: bool = False,
        tr_cont: str = "",
    ) -> tuple[dict[str, Any], str]:
        """단일 HTTP 호출. 반환: (응답 JSON, 연속조회 키 tr_cont)."""
        if not self.env.is_real and tr_name in VTS_UNSUPPORTED:
            raise KisApiError(f"'{tr_name}' 은(는) 모의투자(VTS) 도메인에서 지원되지 않습니다")

        url = self.auth.url(name)
        hashkey = self.auth.get_hashkey(body) if (use_hashkey and body) else None
        headers = self.auth.build_headers(self.auth.tr_id(tr_name), hashkey)
        if tr_cont:
            headers["tr_cont"] = tr_cont

        self.limiter.acquire()
        try:
            response = self.session.request(
                method, url, headers=headers, params=params, json=body, timeout=HTTP_TIMEOUT
            )
        except requests.RequestException as exc:
            raise RetryableKisError(f"{tr_name} 요청 실패: {exc}") from exc

        if response.status_code >= 500:
            raise RetryableKisError(
                f"{tr_name} 서버 오류 (HTTP {response.status_code})", http_status=response.status_code
            )
        if response.status_code != 200:
            raise KisApiError(
                f"{tr_name} 실패 (HTTP {response.status_code}): {(response.text or '')[:200]}",
                http_status=response.status_code,
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise KisApiError(f"{tr_name} 응답 파싱 실패: {(response.text or '')[:200]}") from exc

        rt_cd = str(data.get("rt_cd", "")).strip()
        if rt_cd and rt_cd != "0":
            msg_cd = str(data.get("msg_cd", "")).strip()
            msg1 = str(data.get("msg1", "")).strip()
            message = f"{tr_name} 실패 [{msg_cd}] {msg1}"
            if msg_cd in TOKEN_EXPIRED_MSG_CODES:
                self.auth.invalidate()
                raise RetryableKisError(message, rt_cd=rt_cd, msg_cd=msg_cd, msg1=msg1)
            if msg_cd in RETRYABLE_MSG_CODES:
                raise RetryableKisError(message, rt_cd=rt_cd, msg_cd=msg_cd, msg1=msg1)
            raise KisApiError(message, rt_cd=rt_cd, msg_cd=msg_cd, msg1=msg1)

        return data, response.headers.get("tr_cont", "")

    @retry(
        max_attempts=3,
        backoff=2.0,
        exceptions=(RetryableKisError,),
        give_up_on=(KisAuthError,),
    )
    def _execute_retrying(self, *args: Any, **kwargs: Any) -> tuple[dict[str, Any], str]:
        return self._execute(*args, **kwargs)

    def _call(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """조회용 호출 (재시도 포함)."""
        try:
            data, _ = self._execute_retrying(*args, **kwargs)
        except RetryExhausted as exc:
            last = exc.last_error
            raise (last if isinstance(last, KisApiError) else KisApiError(str(last))) from last
        return data

    # -- 시세 -------------------------------------------------------------- #

    def get_current_price(self, code: str) -> dict[str, Any]:
        """주식현재가 시세 (FHKST01010100)."""
        data = self._call(
            "price",
            "price",
            params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code},
        )
        out = data.get("output") or {}
        if not out:
            raise KisApiError(f"현재가 응답이 비어 있습니다: {code}")
        return {
            "code": code,
            "name": (out.get("hts_kor_isnm") or "").strip(),
            "current": _to_int(out.get("stck_prpr")),
            "change_pct": _to_float(out.get("prdy_ctrt")),
            "change": _to_int(out.get("prdy_vrss")),
            "open": _to_int(out.get("stck_oprc")),
            "high": _to_int(out.get("stck_hgpr")),
            "low": _to_int(out.get("stck_lwpr")),
            "volume": _to_int(out.get("acml_vol")),
            "trade_amount": _to_int(out.get("acml_tr_pbmn")),
            "market_cap": _to_int(out.get("hts_avls")) * 100_000_000,  # 억원 → 원
            "per": _to_float(out.get("per")),
            "pbr": _to_float(out.get("pbr")),
            "upper_limit": _to_int(out.get("stck_mxpr")),
            "lower_limit": _to_int(out.get("stck_llam")),
        }

    def get_daily_ohlcv(self, code: str, days: int = 60) -> pd.DataFrame:
        """국내주식 기간별 시세(일봉). 100건 초과 시 나눠서 조회 후 합친다."""
        frames: list[pd.DataFrame] = []
        end_date = datetime.now().date()
        remaining = days

        while remaining > 0:
            # 휴장일을 감안해 넉넉히(영업일 ≈ 달력일 × 0.7) 거슬러 올라간다.
            span = min(remaining, MAX_ROWS_PER_DAILY_CALL)
            start_date = end_date - timedelta(days=int(span * 1.6) + 10)
            data = self._call(
                "daily_ohlcv",
                "daily_ohlcv",
                params={
                    "FID_COND_MRKT_DIV_CODE": "J",
                    "FID_INPUT_ISCD": code,
                    "FID_INPUT_DATE_1": start_date.strftime("%Y%m%d"),
                    "FID_INPUT_DATE_2": end_date.strftime("%Y%m%d"),
                    "FID_PERIOD_DIV_CODE": "D",
                    "FID_ORG_ADJ_PRC": "0",  # 0: 수정주가 반영
                },
            )
            rows = [row for row in (data.get("output2") or []) if row and row.get("stck_bsop_date")]
            if not rows:
                break
            frames.append(
                pd.DataFrame(
                    {
                        "date": [row["stck_bsop_date"] for row in rows],
                        "open": [_to_int(row.get("stck_oprc")) for row in rows],
                        "high": [_to_int(row.get("stck_hgpr")) for row in rows],
                        "low": [_to_int(row.get("stck_lwpr")) for row in rows],
                        "close": [_to_int(row.get("stck_clpr")) for row in rows],
                        "volume": [_to_int(row.get("acml_vol")) for row in rows],
                    }
                )
            )
            remaining -= len(rows)
            oldest = min(row["stck_bsop_date"] for row in rows)
            end_date = datetime.strptime(oldest, "%Y%m%d").date() - timedelta(days=1)
            if len(rows) < span:  # 상장 이후 데이터가 모두 소진됨
                break

        if not frames:
            raise KisApiError(f"일봉 데이터가 없습니다: {code}")

        df = pd.concat(frames, ignore_index=True)
        df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")
        df = df.drop_duplicates(subset="date").sort_values("date").reset_index(drop=True)
        return df.tail(days).reset_index(drop=True)

    def get_orderbook(self, code: str) -> dict[str, Any]:
        """주식현재가 호가 (FHKST01010200). 매수/매도 1~5호가."""
        data = self._call(
            "orderbook",
            "orderbook",
            params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code},
        )
        out = (data.get("output1") or {}) if isinstance(data.get("output1"), dict) else {}
        if not out:
            raise KisApiError(f"호가 응답이 비어 있습니다: {code}")

        asks = [
            {"price": _to_int(out.get(f"askp{i}")), "qty": _to_int(out.get(f"askp_rsqn{i}"))}
            for i in range(1, 6)
        ]
        bids = [
            {"price": _to_int(out.get(f"bidp{i}")), "qty": _to_int(out.get(f"bidp_rsqn{i}"))}
            for i in range(1, 6)
        ]
        best_ask = asks[0]["price"]
        best_bid = bids[0]["price"]
        mid = (best_ask + best_bid) / 2 if best_ask and best_bid else 0
        return {
            "code": code,
            "asks": asks,
            "bids": bids,
            "ask_total": _to_int(out.get("total_askp_rsqn")),
            "bid_total": _to_int(out.get("total_bidp_rsqn")),
            "best_ask": best_ask,
            "best_bid": best_bid,
            "spread_pct": round((best_ask - best_bid) / mid * 100, 4) if mid else 0.0,
        }

    def get_volume_rank(self, top_n: int = 20) -> list[dict[str, Any]]:
        """거래량 순위 (FHPST01710000). 모의투자 도메인에서는 지원되지 않는다."""
        data = self._call(
            "volume_rank",
            "volume_rank",
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_COND_SCR_DIV_CODE": "20171",
                "FID_INPUT_ISCD": "0000",  # 0000: 전체
                "FID_DIV_CLS_CODE": "0",
                "FID_BLNG_CLS_CODE": "0",  # 0: 평균거래량
                "FID_TRGT_CLS_CODE": "111111111",
                "FID_TRGT_EXLS_CLS_CODE": "000000",
                "FID_INPUT_PRICE_1": "",
                "FID_INPUT_PRICE_2": "",
                "FID_VOL_CNT": "",
                "FID_INPUT_DATE_1": "",
            },
        )
        rows = data.get("output") or []
        result = []
        for row in rows[:top_n]:
            result.append(
                {
                    "code": (row.get("mksc_shrn_iscd") or "").strip(),
                    "name": (row.get("hts_kor_isnm") or "").strip(),
                    "price": _to_int(row.get("stck_prpr")),
                    "change_pct": _to_float(row.get("prdy_ctrt")),
                    "volume": _to_int(row.get("acml_vol")),
                    "rank": _to_int(row.get("data_rank")),
                }
            )
        return result

    # -- 계좌 -------------------------------------------------------------- #

    def get_balance(self) -> Balance:
        """주식잔고조회. 보유 종목이 많으면 연속조회로 전부 모은다."""
        holdings: list[Holding] = []
        summary: dict[str, Any] = {}
        ctx_fk = ctx_nk = ""
        tr_cont = ""

        for _ in range(20):  # 무한 루프 방지
            params = {
                "CANO": self.env.kis_account_no,
                "ACNT_PRDT_CD": self.env.kis_account_product_cd,
                "AFHR_FLPR_YN": "N",
                "OFL_YN": "",
                "INQR_DVSN": "02",  # 종목별
                "UNPR_DVSN": "01",
                "FUND_STTL_ICLD_YN": "N",
                "FNCG_AMT_AUTO_RDPT_YN": "N",
                "PRCS_DVSN": "00",
                "CTX_AREA_FK100": ctx_fk,
                "CTX_AREA_NK100": ctx_nk,
            }
            try:
                data, tr_cont = self._execute_retrying("balance", "balance", params=params, tr_cont=tr_cont)
            except RetryExhausted as exc:
                last = exc.last_error
                raise (last if isinstance(last, KisApiError) else KisApiError(str(last))) from last

            for row in data.get("output1") or []:
                qty = _to_int(row.get("hldg_qty"))
                if qty <= 0:
                    continue
                holdings.append(
                    Holding(
                        code=(row.get("pdno") or "").strip(),
                        name=(row.get("prdt_name") or "").strip(),
                        qty=qty,
                        orderable_qty=_to_int(row.get("ord_psbl_qty"), qty),
                        avg_price=_to_float(row.get("pchs_avg_pric")),
                        current_price=_to_float(row.get("prpr")),
                        eval_amount=_to_float(row.get("evlu_amt")),
                        pnl_amount=_to_float(row.get("evlu_pfls_amt")),
                        pnl_pct=_to_float(row.get("evlu_pfls_rt")),
                    )
                )
            out2 = data.get("output2") or []
            if out2:
                summary = out2[0]

            if tr_cont not in ("F", "M"):  # F/M = 다음 페이지 있음
                break
            ctx_fk = (data.get("ctx_area_fk100") or "").strip()
            ctx_nk = (data.get("ctx_area_nk100") or "").strip()
            tr_cont = "N"

        return Balance(
            holdings=holdings,
            deposit=_to_float(summary.get("dnca_tot_amt")),
            orderable_cash=_to_float(summary.get("prvs_rcdl_excc_amt")),  # D+2 예수금
            total_eval_amount=_to_float(summary.get("scts_evlu_amt")),
            net_asset=_to_float(summary.get("nass_amt")),
            total_pnl_amount=_to_float(summary.get("evlu_pfls_smtl_amt")),
        )

    def get_orderable_cash(self, code: str, price: int = 0) -> float:
        """매수가능 조회. 시장가는 price=0으로 조회한다."""
        data = self._call(
            "orderable_cash",
            "orderable_cash",
            params={
                "CANO": self.env.kis_account_no,
                "ACNT_PRDT_CD": self.env.kis_account_product_cd,
                "PDNO": code,
                "ORD_UNPR": str(price),
                "ORD_DVSN": ORD_DVSN["limit"] if price else ORD_DVSN["market"],
                "CMA_EVLU_AMT_ICLD_YN": "N",
                "OVRS_ICLD_YN": "N",
            },
        )
        out = data.get("output") or {}
        return _to_float(out.get("ord_psbl_cash"))

    # -- 주문 -------------------------------------------------------------- #

    def place_order(
        self,
        code: str,
        qty: int,
        side: Side,
        price: int = 0,
        order_type: OrderType = "market",
    ) -> OrderResult:
        """주식주문(현금). **재시도하지 않는다** — 실패 시 체결조회로 상태를 확인할 것."""
        if qty <= 0:
            raise KisApiError(f"주문 수량이 0 이하입니다: {qty}")
        if order_type not in ORD_DVSN:
            raise KisApiError(f"알 수 없는 주문 유형: {order_type}")
        if order_type == "limit" and price <= 0:
            raise KisApiError("지정가 주문에는 가격이 필요합니다")

        body = {
            "CANO": self.env.kis_account_no,
            "ACNT_PRDT_CD": self.env.kis_account_product_cd,
            "PDNO": code,
            "ORD_DVSN": ORD_DVSN[order_type],
            "ORD_QTY": str(int(qty)),
            "ORD_UNPR": str(int(price) if order_type == "limit" else 0),
        }
        tr_name = "order_buy" if side == "BUY" else "order_sell"
        logger.info("주문 전송: %s %s %d주 (%s, %s원)", code, side, qty, order_type, price)

        data, _ = self._execute(  # 재시도 금지 경로
            "order_cash", tr_name, method="POST", body=body, use_hashkey=True
        )
        out = data.get("output") or {}
        result = OrderResult(
            order_no=(out.get("ODNO") or "").strip(),
            org_no=(out.get("KRX_FWDG_ORD_ORGNO") or "").strip(),
            order_time=(out.get("ORD_TMD") or "").strip(),
            code=code,
            side=side,
            qty=int(qty),
            price=int(price),
            order_type=order_type,
        )
        if not result.order_no:
            raise KisApiError(f"주문 응답에 주문번호(ODNO)가 없습니다: {data.get('msg1')}")
        logger.info("주문 접수 완료: 주문번호 %s", result.order_no)
        return result

    def cancel_order(self, order_no: str, code: str, qty: int, org_no: str = "") -> bool:
        """주식주문 정정취소(전량 취소). 재시도하지 않는다."""
        if not org_no:
            status = self.get_order_status(order_no)
            org_no = status.org_no if status else ""
        body = {
            "CANO": self.env.kis_account_no,
            "ACNT_PRDT_CD": self.env.kis_account_product_cd,
            "KRX_FWDG_ORD_ORGNO": org_no,
            "ORGN_ODNO": order_no,
            "ORD_DVSN": ORD_DVSN["limit"],
            "RVSE_CNCL_DVSN_CD": "02",  # 02: 취소
            "ORD_QTY": str(int(qty)),
            "ORD_UNPR": "0",
            "QTY_ALL_ORD_YN": "Y",
        }
        logger.info("주문 취소 요청: %s (%s %d주)", order_no, code, qty)
        data, _ = self._execute("order_cancel", "order_cancel", method="POST", body=body, use_hashkey=True)
        return str(data.get("rt_cd", "0")) == "0"

    def get_order_status(self, order_no: str, date: str | None = None) -> OrderStatus | None:
        """주식 일별주문체결조회에서 해당 주문번호를 찾아 체결 상태를 반환."""
        day = date or datetime.now().strftime("%Y%m%d")
        ctx_fk = ctx_nk = ""
        tr_cont = ""

        for _ in range(20):
            params = {
                "CANO": self.env.kis_account_no,
                "ACNT_PRDT_CD": self.env.kis_account_product_cd,
                "INQR_STRT_DT": day,
                "INQR_END_DT": day,
                "SLL_BUY_DVSN_CD": "00",  # 전체
                "INQR_DVSN": "00",  # 역순
                "PDNO": "",
                "CCLD_DVSN": "00",  # 전체
                "ORD_GNO_BRNO": "",
                "ODNO": "",
                "INQR_DVSN_3": "00",
                "INQR_DVSN_1": "",
                "CTX_AREA_FK100": ctx_fk,
                "CTX_AREA_NK100": ctx_nk,
            }
            try:
                data, tr_cont = self._execute_retrying("daily_ccld", "daily_ccld", params=params, tr_cont=tr_cont)
            except RetryExhausted as exc:
                last = exc.last_error
                raise (last if isinstance(last, KisApiError) else KisApiError(str(last))) from last

            for row in data.get("output1") or []:
                if (row.get("odno") or "").strip().lstrip("0") != order_no.strip().lstrip("0"):
                    continue
                order_qty = _to_int(row.get("ord_qty"))
                filled_qty = _to_int(row.get("tot_ccld_qty"))
                side_name = (row.get("sll_buy_dvsn_cd_name") or "").strip()
                side: Side | None = "SELL" if "매도" in side_name else ("BUY" if "매수" in side_name else None)
                return OrderStatus(
                    order_no=order_no,
                    code=(row.get("pdno") or "").strip(),
                    name=(row.get("prdt_name") or "").strip(),
                    side=side,
                    order_qty=order_qty,
                    filled_qty=filled_qty,
                    remain_qty=_to_int(row.get("rmn_qty"), max(order_qty - filled_qty, 0)),
                    filled_price=_to_float(row.get("avg_prvs")),
                    filled_amount=_to_float(row.get("tot_ccld_amt")),
                    status=(row.get("ccld_dvsn_name") or row.get("ord_dvsn_name") or "").strip(),
                    org_no=(row.get("ord_gno_brno") or "").strip(),
                )

            if tr_cont not in ("F", "M"):
                break
            ctx_fk = (data.get("ctx_area_fk100") or "").strip()
            ctx_nk = (data.get("ctx_area_nk100") or "").strip()
            tr_cont = "N"

        logger.warning("주문번호 %s 를 체결내역에서 찾지 못했습니다 (%s)", order_no, day)
        return None
