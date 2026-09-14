"""scripts/test_kis.py 의 각 단계가 mock 응답으로 끝까지 도는지 확인.

실제 KIS 키 없이도 검증 스크립트의 로직 오류를 잡기 위한 테스트다.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from tests.conftest import FakeResponse, ok
from tests.test_kis_api import FakeSession
from trading.kis_api import KisApi
from trading.kis_auth import TokenManager

KST = ZoneInfo("Asia/Seoul")


def _load_script():
    path = Path(__file__).resolve().parent.parent / "scripts" / "test_kis.py"
    spec = importlib.util.spec_from_file_location("kis_smoke_script", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["kis_smoke_script"] = module
    spec.loader.exec_module(module)
    return module


script = _load_script()


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(script.time, "sleep", lambda *_: None)


def _price_payload():
    return ok(
        {
            "hts_kor_isnm": "삼성전자", "stck_prpr": "71300", "prdy_ctrt": "1.28", "prdy_vrss": "900",
            "stck_oprc": "70500", "stck_hgpr": "71500", "stck_lwpr": "70300", "acml_vol": "1234",
            "hts_avls": "4256000", "per": "13.5", "pbr": "1.2",
        }
    )


def _daily_payload(n: int = 60):
    rows = [
        {
            "stck_bsop_date": f"2026{(7 + i // 30):02d}{(i % 28) + 1:02d}",
            "stck_oprc": "70000", "stck_hgpr": "71000", "stck_lwpr": "69000",
            "stck_clpr": str(70000 + i), "acml_vol": "1000",
        }
        for i in range(n)
    ]
    return ok(output2=rows)


def _orderbook_payload():
    out = {f"askp{i}": str(71000 + i * 100) for i in range(1, 6)}
    out.update({f"bidp{i}": str(70900 - i * 100) for i in range(1, 6)})
    out.update({f"askp_rsqn{i}": "10" for i in range(1, 6)})
    out.update({f"bidp_rsqn{i}": "20" for i in range(1, 6)})
    out.update({"total_askp_rsqn": "50", "total_bidp_rsqn": "100"})
    return ok(output1=out)


def test_check_quotes_and_balance(auth):
    session = FakeSession(
        [
            FakeResponse(_price_payload()),
            FakeResponse(_daily_payload()),
            FakeResponse(_orderbook_payload()),
            FakeResponse(
                {
                    "rt_cd": "0",
                    "output1": [
                        {"pdno": "005930", "prdt_name": "삼성전자", "hldg_qty": "1", "ord_psbl_qty": "1",
                         "pchs_avg_pric": "70000", "prpr": "71300", "evlu_amt": "71300",
                         "evlu_pfls_amt": "1300", "evlu_pfls_rt": "1.86"}
                    ],
                    "output2": [{"dnca_tot_amt": "1000000", "prvs_rcdl_excc_amt": "1000000",
                                 "nass_amt": "1071300", "scts_evlu_amt": "71300"}],
                }
            ),
        ]
    )
    api = KisApi(auth.env, auth, rate_limit=1000, session=session)
    assert script.check_quotes(api, "005930") is True
    assert script.check_balance(api) is True


def test_check_order_roundtrip_buy_then_sell(auth, monkeypatch):
    monkeypatch.setattr(TokenManager, "get_hashkey", lambda self, body: "HASH")
    filled_buy = {
        "rt_cd": "0",
        "output1": [{"odno": "0000000001", "pdno": "005930", "prdt_name": "삼성전자", "ord_qty": "1",
                     "tot_ccld_qty": "1", "rmn_qty": "0", "avg_prvs": "71300", "tot_ccld_amt": "71300",
                     "sll_buy_dvsn_cd_name": "현금매수", "ccld_dvsn_name": "체결"}],
    }
    filled_sell = {
        "rt_cd": "0",
        "output1": [{"odno": "0000000002", "pdno": "005930", "prdt_name": "삼성전자", "ord_qty": "1",
                     "tot_ccld_qty": "1", "rmn_qty": "0", "avg_prvs": "71400", "tot_ccld_amt": "71400",
                     "sll_buy_dvsn_cd_name": "현금매도", "ccld_dvsn_name": "체결"}],
    }
    session = FakeSession(
        [
            FakeResponse(ok({"ODNO": "0000000001", "KRX_FWDG_ORD_ORGNO": "91252", "ORD_TMD": "100000"})),
            FakeResponse(filled_buy),
            FakeResponse(ok({"ODNO": "0000000002", "KRX_FWDG_ORD_ORGNO": "91252", "ORD_TMD": "100010"})),
            FakeResponse(filled_sell),
        ]
    )
    api = KisApi(auth.env, auth, rate_limit=1000, session=session)
    assert script.check_order_roundtrip(api, "005930") is True

    buy_body = session.requests[0]["body"]
    sell_headers = session.requests[2]["headers"]
    assert buy_body["ORD_DVSN"] == "01"
    assert sell_headers["tr_id"] == "VTTC0801U"


def test_check_order_roundtrip_stops_when_buy_not_filled(auth, monkeypatch):
    monkeypatch.setattr(TokenManager, "get_hashkey", lambda self, body: "HASH")
    unfilled = {
        "rt_cd": "0",
        "output1": [{"odno": "0000000001", "pdno": "005930", "prdt_name": "삼성전자", "ord_qty": "1",
                     "tot_ccld_qty": "0", "rmn_qty": "1", "avg_prvs": "0", "tot_ccld_amt": "0",
                     "sll_buy_dvsn_cd_name": "현금매수", "ccld_dvsn_name": "미체결"}],
    }
    session = FakeSession(
        [FakeResponse(ok({"ODNO": "0000000001", "KRX_FWDG_ORD_ORGNO": "9", "ORD_TMD": "1"}))]
        + [FakeResponse(unfilled) for _ in range(6)]
    )
    api = KisApi(auth.env, auth, rate_limit=1000, session=session)
    assert script.check_order_roundtrip(api, "005930") is False
    # 매수 미체결이면 매도 주문을 내지 않는다.
    assert sum(1 for r in session.requests if r["method"] == "POST") == 1


def test_check_token_detects_cache_reuse(env, tmp_path, monkeypatch):
    import requests

    token_file = tmp_path / "token.json"
    expiry = datetime.now(KST) + timedelta(hours=12)
    calls = []

    def fake_post(url, **kwargs):
        calls.append(url)
        return FakeResponse(
            {
                "access_token": "TOKEN-A",
                "access_token_token_expired": expiry.strftime("%Y-%m-%d %H:%M:%S"),
                "expires_in": 43200,
            }
        )

    monkeypatch.setattr(requests, "post", fake_post)
    auth = TokenManager(env, token_file)
    assert script.check_token(auth) is True
    assert len(calls) == 1, "2차 호출에서 재발급되면 안 됩니다"
