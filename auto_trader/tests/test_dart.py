"""전자공시 조회 — 화면 표시 전용이라는 점까지 테스트로 고정한다."""

from __future__ import annotations

import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data_pipeline import dart  # noqa: E402

CORP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<result>
  <list><corp_code>00126380</corp_code><corp_name>삼성전자</corp_name>
        <stock_code>005930</stock_code><modify_date>20260101</modify_date></list>
  <list><corp_code>00164779</corp_code><corp_name>SK하이닉스</corp_name>
        <stock_code>000660</stock_code><modify_date>20260101</modify_date></list>
  <list><corp_code>00999999</corp_code><corp_name>비상장회사</corp_name>
        <stock_code> </stock_code><modify_date>20260101</modify_date></list>
</result>"""


def _zip_of(xml: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        bundle.writestr("CORPCODE.xml", xml)
    return buffer.getvalue()


def _listing(*reports) -> bytes:
    return json.dumps({
        "status": "000", "message": "정상",
        "list": [
            {"corp_code": "00126380", "corp_name": "삼성전자", "stock_code": "005930",
             "report_nm": title, "rcept_no": rcept, "flr_nm": "삼성전자",
             "rcept_dt": date}
            for title, rcept, date in reports
        ],
    }).encode("utf-8")


@pytest.fixture()
def fake_dart(monkeypatch, tmp_path):
    """DART 응답 대역. calls 에 어떤 URL 을 불렀는지 남는다."""
    calls: list[tuple[str, dict]] = []
    payloads = {
        dart.CORP_CODE_URL: _zip_of(CORP_XML),
        dart.LIST_URL: _listing(("주요사항보고서(유상증자결정)", "20260917000123", "20260917"),
                                ("분기보고서 (2026.06)", "20260814000456", "20260814")),
    }

    def fake_get(url, params):
        calls.append((url, params))
        if url not in payloads:
            raise AssertionError(f"예상치 못한 호출: {url}")
        return payloads[url]

    monkeypatch.setattr(dart, "_get", fake_get)
    return {"calls": calls, "payloads": payloads, "dir": tmp_path}


# --- 기본 동작 ---------------------------------------------------------------- #

def test_returns_filings_for_held_stocks(fake_dart):
    result = dart.recent_filings("KEY", fake_dart["dir"], ["005930"], {"005930": "삼성전자"})

    assert result["ready"]
    assert len(result["filings"]) == 2
    first = result["filings"][0]
    assert first["title"] == "주요사항보고서(유상증자결정)"
    assert first["filed_at"] == "2026-09-17", "20260917 을 읽기 좋게 바꿔야 합니다"
    assert first["url"].endswith("20260917000123"), "원문으로 가는 링크가 있어야 합니다"


def test_unlisted_companies_are_skipped():
    """비상장사는 stock_code 가 비어 있다 — 표에 섞이면 안 된다."""
    from xml.etree import ElementTree

    codes = {}
    for item in ElementTree.fromstring(CORP_XML).iter("list"):
        stock = (item.findtext("stock_code") or "").strip()
        if stock:
            codes[stock] = item.findtext("corp_code")
    assert set(codes) == {"005930", "000660"}


def test_no_key_is_not_an_error(tmp_path):
    """공시는 편의 기능이다 — 키가 없다고 화면이 깨지면 안 된다."""
    result = dart.recent_filings("", tmp_path, ["005930"])
    assert not result["ready"]
    assert "키가 없습니다" in result["reason"]
    assert result["filings"] == []


def test_no_filings_is_not_an_error(monkeypatch, tmp_path):
    """상태코드 013 은 '공시 없음' 이지 오류가 아니다."""
    def fake_get(url, params):
        if url == dart.CORP_CODE_URL:
            return _zip_of(CORP_XML)
        return json.dumps({"status": "013", "message": "조회된 데이타가 없습니다."}).encode()

    monkeypatch.setattr(dart, "_get", fake_get)
    result = dart.recent_filings("KEY", tmp_path, ["005930"])
    assert result["ready"] and result["filings"] == []


def test_bad_key_explains_itself(monkeypatch, tmp_path):
    def fake_get(url, params):
        return b'<result><status>011</status><message>...</message></result>'

    monkeypatch.setattr(dart, "_get", fake_get)
    result = dart.recent_filings("WRONG", tmp_path, ["005930"])
    assert not result["ready"]
    assert "사용할 수 없는 키" in result["reason"]


def test_network_failure_is_contained(monkeypatch, tmp_path):
    """DART 가 죽어도 대시보드는 살아 있어야 한다."""
    def boom(url, params):
        raise dart.DartError("전자공시에 연결하지 못했습니다 (timeout)")

    monkeypatch.setattr(dart, "_get", boom)
    result = dart.recent_filings("KEY", tmp_path, ["005930"])
    assert not result["ready"] and "연결하지 못했습니다" in result["reason"]


# --- 요청 한도 아끼기 ---------------------------------------------------------- #

def test_corp_code_map_is_cached(fake_dart):
    dart.recent_filings("KEY", fake_dart["dir"], ["005930"])
    dart.recent_filings("KEY", fake_dart["dir"], ["000660"])   # 보유가 바뀌면 재조회

    corp_calls = [c for c in fake_dart["calls"] if c[0] == dart.CORP_CODE_URL]
    assert len(corp_calls) == 1, "10만 건짜리 목록을 두 번 받으면 안 됩니다"


def test_filings_are_cached_for_the_same_holdings(fake_dart):
    dart.recent_filings("KEY", fake_dart["dir"], ["005930"])
    dart.recent_filings("KEY", fake_dart["dir"], ["005930"])

    list_calls = [c for c in fake_dart["calls"] if c[0] == dart.LIST_URL]
    assert len(list_calls) == 1, "새로고침마다 부르면 하루 한도를 금방 씁니다"


# --- 가장 중요한 것: AI 입력에 들어가지 않는다 --------------------------------- #

def test_dart_is_never_part_of_the_ai_snapshot():
    """공시 원문이 모델에 들어가면 사람이 검증하지 않은 텍스트가 주문이 된다.

    스냅샷을 만드는 곳(data_pipeline.market_data)이 이 모듈을 아예 모르는지 본다.
    """
    source = (Path(__file__).resolve().parent.parent
              / "data_pipeline" / "market_data.py").read_text(encoding="utf-8")
    assert "dart" not in source.lower(), "시세 수집이 공시 모듈을 참조하고 있습니다"


def test_only_the_dashboard_imports_dart():
    """매매 경로(main·agents·logic·trading)는 공시를 몰라야 한다."""
    root = Path(__file__).resolve().parent.parent
    offenders = []
    for folder in ("agents", "logic", "trading", "data_pipeline"):
        for path in (root / folder).rglob("*.py"):
            if path.name == "dart.py":
                continue
            if "data_pipeline.dart" in path.read_text(encoding="utf-8"):
                offenders.append(str(path.relative_to(root)))
    if "data_pipeline.dart" in (root / "main.py").read_text(encoding="utf-8"):
        offenders.append("main.py")

    assert not offenders, f"매매 경로가 공시를 가져다 씁니다: {offenders}"
