"""전자공시(OpenDART) 조회 — **화면에 보여주기 전용**.

여기서 가져온 내용은 **AI 판단에 넣지 않는다.** 공시 원문을 모델에 먹이면
사람이 검증하지 않은 텍스트가 곧바로 주문으로 이어진다. 이 모듈의 결과는
대시보드 표시 외에는 쓰이지 않으며, 그 사실을 테스트로 고정해 두었다.

키가 없으면 조용히 비활성이다 — 공시는 편의 기능이고, 없다고 매매가 막히면 안 된다.

API: https://opendart.fss.or.kr (금융감독원, 무료·공개)
  · 공시검색      GET /api/list.json
  · 고유번호 목록  GET /api/corpCode.xml   (ZIP 안에 CORPCODE.xml)

DART 는 종목코드가 아니라 **자체 고유번호(corp_code)** 로 조회한다. 그래서
종목코드→고유번호 표를 한 번 받아 캐시해 두고 쓴다.
"""

from __future__ import annotations

import io
import json
import time
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

from utils.logger import get_logger

KST = ZoneInfo("Asia/Seoul")
logger = get_logger("dart")

LIST_URL = "https://opendart.fss.or.kr/api/list.json"
CORP_CODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml"
VIEWER_URL = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"

TIMEOUT_SEC = 15
CORP_MAP_TTL_DAYS = 7      # 상장사 목록은 자주 바뀌지 않는다
FILINGS_TTL_SEC = 1800     # 30분 — 사이클마다 부르지 않게
LOOKBACK_DAYS = 30
PER_STOCK = 5

# DART 응답 상태코드. 정상 외에는 화면에 이유를 적고 넘어간다.
STATUS_MESSAGES = {
    "013": "",                                  # 조회된 공시 없음 — 오류가 아니다
    "011": "사용할 수 없는 키입니다",
    "012": "접근할 수 없는 IP 입니다",
    "020": "오늘 요청 한도를 넘었습니다",
    "100": "요청 값이 잘못됐습니다",
    "800": "DART 가 점검 중입니다",
    "900": "정의되지 않은 오류입니다",
    "901": "사용자 계정이 정지됐습니다",
}


class DartError(RuntimeError):
    """조회 실패. 화면에 사유만 적고 나머지는 그대로 돈다."""


@dataclass
class Filing:
    code: str
    name: str
    title: str
    filed_at: str
    filer: str
    url: str


def _get(url: str, params: dict[str, str]) -> bytes:
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(f"{url}?{query}",
                                     headers={"User-Agent": "auto-trader-dashboard"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SEC) as response:
            return response.read()
    except Exception as exc:  # noqa: BLE001 — 네트워크 실패가 화면을 막으면 안 된다
        raise DartError(f"전자공시에 연결하지 못했습니다 ({exc})") from exc


# --- 종목코드 → 고유번호 ------------------------------------------------------ #

def _corp_map_path(data_dir: Path | str) -> Path:
    return Path(data_dir) / "dart_corp_codes.json"


def corp_code_map(api_key: str, data_dir: Path | str, *,
                  max_age_days: int = CORP_MAP_TTL_DAYS) -> dict[str, str]:
    """상장 종목코드 → DART 고유번호. 파일로 캐시한다(약 3,500개).

    전체 목록은 10만 건이 넘는 ZIP 이라 매번 받을 것이 못 된다.
    """
    path = _corp_map_path(data_dir)
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
        fetched = datetime.fromisoformat(cached["fetched_at"])
        if datetime.now(KST) - fetched < timedelta(days=max_age_days):
            return cached["codes"]
    except (OSError, ValueError, KeyError):
        pass

    payload = _get(CORP_CODE_URL, {"crtfc_key": api_key})
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as bundle:
            name = next(n for n in bundle.namelist() if n.lower().endswith(".xml"))
            raw = bundle.read(name)
    except (zipfile.BadZipFile, StopIteration) as exc:
        # 키가 틀리면 ZIP 대신 XML 오류 문서가 온다.
        raise DartError(_explain_status(payload.decode("utf-8", "replace"))) from exc

    codes: dict[str, str] = {}
    for item in ElementTree.fromstring(raw).iter("list"):
        stock = (item.findtext("stock_code") or "").strip()
        corp = (item.findtext("corp_code") or "").strip()
        if stock and corp:          # 비상장사는 stock_code 가 비어 있다
            codes[stock] = corp

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(
        {"fetched_at": datetime.now(KST).isoformat(timespec="seconds"), "codes": codes},
        ensure_ascii=False), encoding="utf-8")
    logger.info("DART 고유번호 %d개를 받았습니다", len(codes))
    return codes


def _explain_status(text: str) -> str:
    """오류 문서에서 상태코드를 뽑아 사람 말로 바꾼다."""
    for status, message in STATUS_MESSAGES.items():
        if f"<status>{status}</status>" in text or f'"status":"{status}"' in text:
            return message or "조회된 공시가 없습니다"
    return "전자공시가 예상과 다른 응답을 보냈습니다"


# --- 공시 조회 ---------------------------------------------------------------- #

def _filings_for(api_key: str, corp_code: str, code: str, name: str,
                 *, days: int, limit: int) -> list[Filing]:
    today = datetime.now(KST)
    payload = _get(LIST_URL, {
        "crtfc_key": api_key,
        "corp_code": corp_code,
        "bgn_de": (today - timedelta(days=days)).strftime("%Y%m%d"),
        "end_de": today.strftime("%Y%m%d"),
        "page_count": str(limit),
        "page_no": "1",
    })
    try:
        data = json.loads(payload)
    except ValueError as exc:
        raise DartError("전자공시 응답을 읽지 못했습니다") from exc

    status = str(data.get("status", "")).strip()
    if status != "000":
        if status == "013":
            return []                       # 공시 없음 — 정상이다
        raise DartError(STATUS_MESSAGES.get(status) or f"전자공시 오류 ({status})")

    filings = []
    for row in data.get("list") or []:
        rcept = str(row.get("rcept_no") or "").strip()
        filings.append(Filing(
            code=code,
            name=str(row.get("corp_name") or name).strip(),
            title=str(row.get("report_nm") or "").strip(),
            filed_at=_pretty_date(str(row.get("rcept_dt") or "")),
            filer=str(row.get("flr_nm") or "").strip(),
            url=VIEWER_URL.format(rcept_no=rcept) if rcept else "",
        ))
    return filings


def _pretty_date(raw: str) -> str:
    """20260917 → 2026-09-17. 형식이 다르면 그대로 둔다."""
    digits = raw.strip()
    if len(digits) == 8 and digits.isdigit():
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:]}"
    return digits


def recent_filings(api_key: str, data_dir: Path | str, codes: list[str],
                   names: dict[str, str] | None = None, *,
                   days: int = LOOKBACK_DAYS, limit: int = PER_STOCK) -> dict:
    """보유 종목의 최근 공시. 실패해도 예외를 밖으로 내보내지 않는다.

    Returns:
        {"ready": bool, "reason": str, "filings": [Filing, ...]}
    """
    blank = {"ready": False, "reason": "", "filings": []}
    if not api_key:
        blank["reason"] = "전자공시 키가 없습니다 — 설정에서 넣으면 공시가 표시됩니다"
        return blank
    if not codes:
        blank["reason"] = "보유 종목이 없습니다"
        return blank

    cache = _cache_path(data_dir)
    fresh = _read_cache(cache, codes)
    if fresh is not None:
        return fresh

    names = names or {}
    try:
        mapping = corp_code_map(api_key, data_dir)
    except DartError as exc:
        blank["reason"] = str(exc)
        return blank

    filings: list[Filing] = []
    unknown: list[str] = []
    for code in codes:
        corp = mapping.get(code)
        if not corp:
            unknown.append(code)
            continue
        try:
            filings.extend(_filings_for(api_key, corp, code, names.get(code, code),
                                        days=days, limit=limit))
        except DartError as exc:
            blank["reason"] = str(exc)
            return blank

    filings.sort(key=lambda f: f.filed_at, reverse=True)
    result = {
        "ready": True,
        "reason": (f"고유번호를 찾지 못한 종목: {', '.join(unknown)}" if unknown else ""),
        "filings": [f.__dict__ for f in filings],
    }
    _write_cache(cache, codes, result)
    return result


# --- 캐시 (요청 한도를 아끼고 화면을 빠르게) ----------------------------------- #

def _cache_path(data_dir: Path | str) -> Path:
    return Path(data_dir) / "dart_filings.json"


def _read_cache(path: Path, codes: list[str]) -> dict | None:
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if cached.get("codes") != sorted(codes):
        return None                      # 보유 종목이 바뀌면 다시 받는다
    if time.time() - float(cached.get("at", 0)) > FILINGS_TTL_SEC:
        return None
    return cached.get("result")


def _write_cache(path: Path, codes: list[str], result: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(
            {"at": time.time(), "codes": sorted(codes), "result": result},
            ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass                             # 캐시를 못 써도 조회 자체는 됐다
