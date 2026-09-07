"""KIS 인증·API 래퍼 테스트 (외부 호출은 전부 mock)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
import requests

from tests.conftest import FakeResponse, fail, make_env, ok
from trading.kis_api import (
    KisApi,
    KisApiError,
    RateLimiter,
    RetryableKisError,
    _to_float,
    _to_int,
)
from trading.kis_auth import TR_IDS, TokenManager

KST = ZoneInfo("Asia/Seoul")


# --------------------------------------------------------------------------- #
# TokenManager — 캐시가 핵심(발급 횟수 제한)
# --------------------------------------------------------------------------- #


def _token_payload(hours: int = 24) -> dict:
    expiry = datetime.now(KST) + timedelta(hours=hours)
    return {
        "access_token": "ISSUED-TOKEN",
        "access_token_token_expired": expiry.strftime("%Y-%m-%d %H:%M:%S"),
        "expires_in": hours * 3600,
        "token_type": "Bearer",
    }


def test_token_issued_once_and_cached(env, token_path, monkeypatch):
    calls: list[str] = []

    def fake_post(url, **kwargs):
        calls.append(url)
        return FakeResponse(_token_payload())

    monkeypatch.setattr(requests, "post", fake_post)

    first = TokenManager(env, token_path).get_access_token()
    # 새 프로세스처럼 매니저를 새로 만들어도 캐시 파일을 재사용해야 한다.
    second = TokenManager(env, token_path).get_access_token()

    assert first == second == "ISSUED-TOKEN"
    assert len(calls) == 1, "캐시가 유효한데도 토큰을 재발급했습니다"
    assert json.loads(token_path.read_text())["kis_env"] == "VTS"


def test_token_reissued_when_near_expiry(env, token_path, monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(requests, "post", lambda url, **kw: (calls.append(url), FakeResponse(_token_payload()))[1])

    manager = TokenManager(env, token_path)
    manager.get_access_token()
    # 만료 10분 전 상황을 캐시 파일에 직접 심는다.
    cached = json.loads(token_path.read_text())
    cached["expires_at"] = (datetime.now(KST) + timedelta(minutes=5)).isoformat()
    token_path.write_text(json.dumps(cached))

    TokenManager(env, token_path).get_access_token()
    assert len(calls) == 2


def test_token_not_reused_across_environments(env, token_path, monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(requests, "post", lambda url, **kw: (calls.append(url), FakeResponse(_token_payload()))[1])

    TokenManager(env, token_path).get_access_token()
    TokenManager(make_env(kis_env="REAL"), token_path).get_access_token()
    assert len(calls) == 2, "모의/실전 토큰을 서로 재사용하면 안 됩니다"


def test_tr_id_prefix_by_environment(env, token_path):
    vts = TokenManager(env, token_path)
    real = TokenManager(make_env(kis_env="REAL"), token_path)
    assert vts.tr_id("order_buy") == "VTTC0802U"
    assert real.tr_id("order_buy") == "TTTC0802U"
    assert vts.tr_id("order_sell") == "VTTC0801U"
    assert real.tr_id("order_sell") == "TTTC0801U"
    assert vts.tr_id("price") == real.tr_id("price") == "FHKST01010100"


def test_build_headers_contains_required_fields(auth):
    headers = auth.build_headers("VTTC0802U", hashkey="HASH123")
    assert headers["authorization"] == "Bearer TEST-ACCESS-TOKEN"
    assert headers["tr_id"] == "VTTC0802U"
    assert headers["custtype"] == "P"
    assert headers["hashkey"] == "HASH123"


def test_mask_headers_hides_secrets(auth):
    from trading.kis_auth import mask_headers

    masked = mask_headers(auth.build_headers("VTTC0802U"))
    assert "TEST-ACCESS-TOKEN" not in masked["authorization"]
    assert masked["appsecret"] != "APPSECRET-TEST-0001"
    assert masked["tr_id"] == "VTTC0802U"


# --------------------------------------------------------------------------- #
# Rate limiter
# --------------------------------------------------------------------------- #


def test_rate_limiter_blocks_over_quota():
    limiter = RateLimiter(max_calls_per_sec=2, window=0.3)
    import time as _time

    start = _time.monotonic()
    for _ in range(4):
        limiter.acquire()
    elapsed = _time.monotonic() - start
    assert elapsed >= 0.3, "초당 호출 제한이 지켜지지 않았습니다"


# --------------------------------------------------------------------------- #
# 값 파싱
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "raw,expected",
    [("1,234", 1234), ("", 0), ("-", 0), (None, 0), ("71300", 71300), ("-2.5", -2)],
)
def test_to_int_handles_kis_quirks(raw, expected):
    assert _to_int(raw) == expected


def test_to_float_handles_empty():
    assert _to_float("") == 0.0
    assert _to_float("-1.23") == pytest.approx(-1.23)


# --------------------------------------------------------------------------- #
# API 호출
# --------------------------------------------------------------------------- #


class FakeSession:
    """요청을 기록하고 미리 정한 응답을 돌려주는 requests.Session 대역."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests: list[dict] = []

    def request(self, method, url, headers=None, params=None, json=None, timeout=None):
        self.requests.append(
            {"method": method, "url": url, "headers": headers, "params": params, "body": json}
        )
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def make_api(auth, responses, *, rate_limit: float = 1000) -> tuple[KisApi, FakeSession]:
    session = FakeSession(responses)
    return KisApi(auth.env, auth, rate_limit=rate_limit, session=session), session


def test_get_current_price_parses_output(auth):
    payload = ok(
        {
            "hts_kor_isnm": "삼성전자",
            "stck_prpr": "71300",
            "prdy_ctrt": "1.28",
            "prdy_vrss": "900",
            "stck_oprc": "70500",
            "stck_hgpr": "71500",
            "stck_lwpr": "70300",
            "acml_vol": "12,345,678",
            "hts_avls": "4256000",
            "per": "13.5",
            "pbr": "1.2",
        }
    )
    api, session = make_api(auth, [FakeResponse(payload)])
    quote = api.get_current_price("005930")

    assert quote["name"] == "삼성전자"
    assert quote["current"] == 71300
    assert quote["volume"] == 12345678
    assert quote["market_cap"] == 4256000 * 100_000_000
    assert quote["per"] == pytest.approx(13.5)
    assert session.requests[0]["params"]["FID_INPUT_ISCD"] == "005930"
    assert session.requests[0]["headers"]["tr_id"] == "FHKST01010100"


def test_rt_cd_error_becomes_kis_api_error(auth):
    api, _ = make_api(auth, [FakeResponse(fail("40580000", "잘못된 종목코드입니다"))])
    with pytest.raises(KisApiError) as exc_info:
        api.get_current_price("999999")
    assert exc_info.value.msg_cd == "40580000"
    assert "잘못된 종목코드" in str(exc_info.value)


def test_http_error_becomes_kis_api_error(auth):
    api, _ = make_api(auth, [FakeResponse(None, status_code=403, text="forbidden")])
    with pytest.raises(KisApiError) as exc_info:
        api.get_current_price("005930")
    assert exc_info.value.http_status == 403


def test_expired_token_is_invalidated_and_retried(auth, monkeypatch):
    """EGW00123(토큰 만료)이면 캐시를 버리고 재시도해 성공해야 한다."""
    monkeypatch.setattr("utils.retry.time.sleep", lambda *_: None)
    monkeypatch.setattr(
        TokenManager, "get_access_token", lambda self, force=False: "REFRESHED-TOKEN"
    )
    responses = [
        FakeResponse({"rt_cd": "1", "msg_cd": "EGW00123", "msg1": "token expired"}),
        FakeResponse(ok({"stck_prpr": "100", "hts_kor_isnm": "테스트"})),
    ]
    api, session = make_api(auth, responses)
    quote = api.get_current_price("005930")
    assert quote["current"] == 100
    assert len(session.requests) == 2


def test_retryable_error_gives_up_after_max_attempts(auth, monkeypatch):
    monkeypatch.setattr("utils.retry.time.sleep", lambda *_: None)
    responses = [FakeResponse(None, status_code=502, text="bad gateway") for _ in range(3)]
    api, session = make_api(auth, responses)
    with pytest.raises(KisApiError):
        api.get_current_price("005930")
    assert len(session.requests) == 3, "재시도는 3회까지"


def test_daily_ohlcv_returns_sorted_dataframe(auth):
    rows = [
        {"stck_bsop_date": "20260904", "stck_oprc": "70000", "stck_hgpr": "71000",
         "stck_lwpr": "69500", "stck_clpr": "70800", "acml_vol": "1000"},
        {"stck_bsop_date": "20260903", "stck_oprc": "69000", "stck_hgpr": "70200",
         "stck_lwpr": "68800", "stck_clpr": "69900", "acml_vol": "900"},
    ]
    api, _ = make_api(auth, [FakeResponse(ok(output2=rows))])
    df = api.get_daily_ohlcv("005930", days=2)

    assert list(df.columns) == ["date", "open", "high", "low", "close", "volume"]
    assert len(df) == 2
    assert df.iloc[0]["date"] < df.iloc[1]["date"], "날짜 오름차순이어야 합니다"
    assert df.iloc[-1]["close"] == 70800


def test_orderbook_computes_spread(auth):
    out = {f"askp{i}": str(71000 + i * 100) for i in range(1, 6)}
    out.update({f"bidp{i}": str(70900 - i * 100) for i in range(1, 6)})
    out.update({f"askp_rsqn{i}": "10" for i in range(1, 6)})
    out.update({f"bidp_rsqn{i}": "20" for i in range(1, 6)})
    out.update({"total_askp_rsqn": "50", "total_bidp_rsqn": "100"})
    api, _ = make_api(auth, [FakeResponse(ok(output1=out))])

    book = api.get_orderbook("005930")
    assert book["best_ask"] == 71100
    assert book["best_bid"] == 70800
    assert book["ask_total"] == 50
    assert book["spread_pct"] > 0


def test_volume_rank_unsupported_on_vts(auth):
    api, session = make_api(auth, [])
    with pytest.raises(KisApiError) as exc_info:
        api.get_volume_rank(10)
    assert "모의투자" in str(exc_info.value)
    assert session.requests == [], "지원되지 않는 API는 호출조차 하지 않아야 합니다"


def test_volume_rank_on_real(real_env, token_path):
    manager = TokenManager(real_env, token_path)
    manager._token = "T"
    manager._expires_at = datetime.now(KST) + timedelta(hours=1)
    rows = [
        {"mksc_shrn_iscd": "005930", "hts_kor_isnm": "삼성전자", "stck_prpr": "71300",
         "acml_vol": "1000", "data_rank": "1", "prdy_ctrt": "1.2"},
        {"mksc_shrn_iscd": "000660", "hts_kor_isnm": "SK하이닉스", "stck_prpr": "170000",
         "acml_vol": "900", "data_rank": "2", "prdy_ctrt": "-0.5"},
    ]
    api = KisApi(real_env, manager, rate_limit=1000, session=FakeSession([FakeResponse(ok(rows))]))
    ranked = api.get_volume_rank(top_n=1)
    assert len(ranked) == 1
    assert ranked[0]["code"] == "005930"


def test_get_balance_parses_holdings_and_cash(auth):
    payload = {
        "rt_cd": "0",
        "output1": [
            {"pdno": "005930", "prdt_name": "삼성전자", "hldg_qty": "12", "ord_psbl_qty": "12",
             "pchs_avg_pric": "70000", "prpr": "71300", "evlu_amt": "855600",
             "evlu_pfls_amt": "15600", "evlu_pfls_rt": "1.86"},
            {"pdno": "000660", "prdt_name": "SK하이닉스", "hldg_qty": "0", "ord_psbl_qty": "0",
             "pchs_avg_pric": "0", "prpr": "0", "evlu_amt": "0",
             "evlu_pfls_amt": "0", "evlu_pfls_rt": "0"},
        ],
        "output2": [{"dnca_tot_amt": "4000000", "prvs_rcdl_excc_amt": "3800000",
                     "scts_evlu_amt": "855600", "nass_amt": "4855600", "evlu_pfls_smtl_amt": "15600"}],
    }
    api, _ = make_api(auth, [FakeResponse(payload)])
    balance = api.get_balance()

    assert len(balance.holdings) == 1, "수량 0 종목은 제외해야 합니다"
    assert balance.holdings[0].code == "005930"
    assert balance.deposit == 4000000
    assert balance.orderable_cash == 3800000
    assert balance.by_code("005930").qty == 12
    assert balance.by_code("035420") is None


def test_get_balance_follows_pagination(auth):
    page1 = {
        "rt_cd": "0",
        "output1": [{"pdno": "005930", "prdt_name": "삼성전자", "hldg_qty": "1", "ord_psbl_qty": "1",
                     "pchs_avg_pric": "70000", "prpr": "71300", "evlu_amt": "71300",
                     "evlu_pfls_amt": "1300", "evlu_pfls_rt": "1.86"}],
        "output2": [{"dnca_tot_amt": "100"}],
        "ctx_area_fk100": "FK", "ctx_area_nk100": "NK",
    }
    page2 = {
        "rt_cd": "0",
        "output1": [{"pdno": "000660", "prdt_name": "SK하이닉스", "hldg_qty": "2", "ord_psbl_qty": "2",
                     "pchs_avg_pric": "170000", "prpr": "171000", "evlu_amt": "342000",
                     "evlu_pfls_amt": "2000", "evlu_pfls_rt": "0.59"}],
        "output2": [{"dnca_tot_amt": "100"}],
    }
    api, session = make_api(
        auth,
        [FakeResponse(page1, headers={"tr_cont": "M"}), FakeResponse(page2, headers={"tr_cont": "D"})],
    )
    balance = api.get_balance()
    assert [h.code for h in balance.holdings] == ["005930", "000660"]
    assert session.requests[1]["params"]["CTX_AREA_FK100"] == "FK"


# --------------------------------------------------------------------------- #
# 주문 — 재시도 금지가 핵심
# --------------------------------------------------------------------------- #


def test_place_order_uses_market_division_and_tr_id(auth, monkeypatch):
    monkeypatch.setattr(TokenManager, "get_hashkey", lambda self, body: "HASH")
    payload = ok({"ODNO": "0000117057", "KRX_FWDG_ORD_ORGNO": "91252", "ORD_TMD": "121052"})
    api, session = make_api(auth, [FakeResponse(payload)])

    result = api.place_order("005930", 1, "BUY")

    body = session.requests[0]["body"]
    assert body["ORD_DVSN"] == "01", "시장가는 ORD_DVSN=01"
    assert body["ORD_QTY"] == "1"
    assert body["ORD_UNPR"] == "0"
    assert body["CANO"] == "50123456"
    assert session.requests[0]["headers"]["tr_id"] == "VTTC0802U"
    assert session.requests[0]["headers"]["hashkey"] == "HASH"
    assert result.order_no == "0000117057"
    assert result.org_no == "91252"


def test_place_limit_sell_order(auth, monkeypatch):
    monkeypatch.setattr(TokenManager, "get_hashkey", lambda self, body: "HASH")
    api, session = make_api(auth, [FakeResponse(ok({"ODNO": "1", "KRX_FWDG_ORD_ORGNO": "9", "ORD_TMD": "1"}))])

    api.place_order("005930", 3, "SELL", price=71500, order_type="limit")

    body = session.requests[0]["body"]
    assert body["ORD_DVSN"] == "00", "지정가는 ORD_DVSN=00"
    assert body["ORD_UNPR"] == "71500"
    assert session.requests[0]["headers"]["tr_id"] == "VTTC0801U"


def test_order_is_never_retried(auth, monkeypatch):
    """주문 실패는 즉시 예외 — 중복 주문 방지를 위해 재시도하지 않는다."""
    monkeypatch.setattr(TokenManager, "get_hashkey", lambda self, body: "HASH")
    monkeypatch.setattr("utils.retry.time.sleep", lambda *_: None)
    api, session = make_api(auth, [FakeResponse(None, status_code=500, text="server error")])

    with pytest.raises(KisApiError):
        api.place_order("005930", 1, "BUY")
    assert len(session.requests) == 1, "주문은 절대 재시도하면 안 됩니다"


def test_place_order_rejects_bad_input(auth):
    api, session = make_api(auth, [])
    with pytest.raises(KisApiError):
        api.place_order("005930", 0, "BUY")
    with pytest.raises(KisApiError):
        api.place_order("005930", 1, "BUY", order_type="limit")  # 가격 없음
    assert session.requests == []


def test_get_order_status_finds_order(auth):
    payload = {
        "rt_cd": "0",
        "output1": [
            {"odno": "0000117050", "pdno": "000660", "prdt_name": "SK하이닉스", "ord_qty": "1",
             "tot_ccld_qty": "0", "rmn_qty": "1", "avg_prvs": "0", "tot_ccld_amt": "0",
             "sll_buy_dvsn_cd_name": "현금매수", "ccld_dvsn_name": "미체결", "ord_gno_brno": "91252"},
            {"odno": "0000117057", "pdno": "005930", "prdt_name": "삼성전자", "ord_qty": "1",
             "tot_ccld_qty": "1", "rmn_qty": "0", "avg_prvs": "71300", "tot_ccld_amt": "71300",
             "sll_buy_dvsn_cd_name": "현금매수", "ccld_dvsn_name": "체결", "ord_gno_brno": "91252"},
        ],
    }
    api, _ = make_api(auth, [FakeResponse(payload)])
    status = api.get_order_status("0000117057")

    assert status is not None
    assert status.is_filled
    assert status.side == "BUY"
    assert status.filled_price == 71300


def test_get_order_status_returns_none_when_missing(auth):
    api, _ = make_api(auth, [FakeResponse({"rt_cd": "0", "output1": []})])
    assert api.get_order_status("9999999999") is None


def test_partially_filled_status(auth):
    payload = {
        "rt_cd": "0",
        "output1": [
            {"odno": "111", "pdno": "005930", "prdt_name": "삼성전자", "ord_qty": "10",
             "tot_ccld_qty": "4", "rmn_qty": "6", "avg_prvs": "71300", "tot_ccld_amt": "285200",
             "sll_buy_dvsn_cd_name": "현금매도", "ccld_dvsn_name": "부분체결"},
        ],
    }
    api, _ = make_api(auth, [FakeResponse(payload)])
    status = api.get_order_status("111")
    assert status.is_partially_filled and not status.is_filled
    assert status.side == "SELL"


def test_all_tr_ids_have_both_environments():
    for name, (real, vts) in TR_IDS.items():
        assert real and vts, f"{name} TR_ID 누락"
        if real.startswith("TTTC"):
            assert vts.startswith("VTTC"), f"{name}: 모의 TR_ID 접두어가 V가 아닙니다"


def test_orderable_cash_zero_is_preserved(auth):
    """KIS 가 '0' 을 주면 0 그대로 — 예수금으로 대체하면 안 된다."""
    payload = {
        "rt_cd": "0", "output1": [],
        "output2": [{"dnca_tot_amt": "4000000", "prvs_rcdl_excc_amt": "0"}],
    }
    api, _ = make_api(auth, [FakeResponse(payload)])
    balance = api.get_balance()
    assert balance.deposit == 4_000_000 and balance.orderable_cash == 0


def test_orderable_cash_falls_back_only_when_field_missing(auth):
    payload = {"rt_cd": "0", "output1": [], "output2": [{"dnca_tot_amt": "4000000"}]}
    api, _ = make_api(auth, [FakeResponse(payload)])
    assert api.get_balance().orderable_cash == 4_000_000


def test_daily_ohlcv_uses_kst_date(auth, monkeypatch):
    """거래일 파라미터는 호스트 타임존이 아니라 KST 기준이어야 한다."""
    from datetime import datetime as real_datetime, timezone

    class FrozenDatetime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            # UTC 로 2026-09-08 22:00 = KST 2026-09-09 07:00
            utc = real_datetime(2026, 9, 8, 22, 0, tzinfo=timezone.utc)
            return utc.astimezone(tz) if tz else utc.replace(tzinfo=None)

    monkeypatch.setattr("trading.kis_api.datetime", FrozenDatetime)
    rows = [{"stck_bsop_date": "20260908", "stck_oprc": "1", "stck_hgpr": "1",
             "stck_lwpr": "1", "stck_clpr": "1", "acml_vol": "1"}]
    api, session = make_api(auth, [FakeResponse(ok(output2=rows))])
    api.get_daily_ohlcv("005930", days=1)

    assert session.requests[0]["params"]["FID_INPUT_DATE_2"] == "20260909", "KST 날짜여야 합니다"


def test_order_status_uses_kst_date(auth, monkeypatch):
    from datetime import datetime as real_datetime, timezone

    class FrozenDatetime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            utc = real_datetime(2026, 9, 8, 22, 0, tzinfo=timezone.utc)
            return utc.astimezone(tz) if tz else utc.replace(tzinfo=None)

    monkeypatch.setattr("trading.kis_api.datetime", FrozenDatetime)
    api, session = make_api(auth, [FakeResponse({"rt_cd": "0", "output1": []})])
    api.get_order_status("0000000001")

    params = session.requests[0]["params"]
    assert params["INQR_STRT_DT"] == params["INQR_END_DT"] == "20260909"


def test_hashkey_call_is_rate_limited(auth, monkeypatch):
    """hashkey 도 KIS 호출이므로 초당 제한에 포함되어야 한다 (VTS 2건/초)."""
    monkeypatch.setattr(TokenManager, "get_hashkey", lambda self, body: "HASH")
    acquired = []
    api, _ = make_api(auth, [FakeResponse(ok({"ODNO": "1", "KRX_FWDG_ORD_ORGNO": "9", "ORD_TMD": "1"}))])
    monkeypatch.setattr(api.limiter, "acquire", lambda: acquired.append(1))

    api.place_order("005930", 1, "BUY")
    assert len(acquired) == 2, "hashkey 1회 + 주문 1회 = 2회를 세야 합니다"


def test_query_without_hashkey_acquires_once(auth):
    api, _ = make_api(auth, [FakeResponse(ok({"stck_prpr": "100", "hts_kor_isnm": "테스트"}))])
    acquired = []
    api.limiter.acquire = lambda: acquired.append(1)

    api.get_current_price("005930")
    assert len(acquired) == 1
