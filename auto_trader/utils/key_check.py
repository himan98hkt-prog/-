"""발급받은 키가 실제로 동작하는지 항목별로 확인한다.

`scripts/check_keys.py`(CLI)와 대시보드 설정 화면이 같은 로직을 쓴다.
각 검사는 **독립적**이어서 일부 키만 채운 상태에서도 돌아간다.
"""

from __future__ import annotations

from dataclasses import dataclass

OK, FAIL, SKIP = "ok", "fail", "skip"
ICONS = {OK: "✅", FAIL: "❌", SKIP: "⏭️"}


@dataclass
class Result:
    name: str
    status: str
    detail: str

    @property
    def icon(self) -> str:
        return ICONS.get(self.status, "•")

    @property
    def optional(self) -> bool:
        return "선택" in self.name

    def line(self) -> str:
        return f"{self.icon} {self.name:<22} {self.detail}"


def check_kis(env: dict[str, str | None]) -> list[Result]:
    """토큰 발급을 실제로 시도해 APP KEY/SECRET 과 도메인 일치를 확인한다."""
    key, secret = env.get("KIS_APP_KEY"), env.get("KIS_APP_SECRET")
    account = (env.get("KIS_ACCOUNT_NO") or "").strip()
    mode = (env.get("KIS_ENV") or "VTS").upper()
    results: list[Result] = []

    if not (key and secret):
        return [Result("KIS 인증", SKIP, "KIS_APP_KEY / KIS_APP_SECRET 미입력")]

    if not (account.isdigit() and len(account) == 8):
        results.append(Result("KIS 계좌번호", FAIL,
                              f"숫자 8자리여야 합니다 (현재: {account!r}) — 앞 8자리만, 뒤 2자리는 PRODUCT_CD"))
    else:
        results.append(Result("KIS 계좌번호", OK, f"{account[:2]}****{account[-2:]} ({mode})"))

    import requests

    base = ("https://openapivts.koreainvestment.com:29443" if mode == "VTS"
            else "https://openapi.koreainvestment.com:9443")
    try:
        response = requests.post(
            f"{base}/oauth2/tokenP",
            json={"grant_type": "client_credentials", "appkey": key, "appsecret": secret},
            timeout=15,
        )
    except requests.RequestException as exc:
        results.append(Result("KIS 인증", FAIL, f"접속 실패: {exc}"))
        return results

    if response.status_code == 200 and response.json().get("access_token"):
        results.append(Result("KIS 인증", OK, f"{mode} 토큰 발급 성공"))
    else:
        body = (response.text or "")[:180].replace("\n", " ")
        hint = ""
        if "EGW00133" in body:
            hint = " (1분 내 재발급 제한 — 잠시 후 다시 시도하세요)"
        elif response.status_code in (401, 403):
            hint = f" (모의용 키를 {mode} 도메인에 쓰고 있는지 확인하세요)"
        results.append(Result("KIS 인증", FAIL, f"HTTP {response.status_code}: {body}{hint}"))
    return results


def check_anthropic(env: dict[str, str | None]) -> Result:
    api_key = env.get("ANTHROPIC_API_KEY")
    model = env.get("CLAUDE_MODEL") or "claude-sonnet-5"
    if not api_key:
        return Result("Anthropic (Claude)", SKIP, "ANTHROPIC_API_KEY 미입력")
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key, timeout=30.0, max_retries=0)
        client.messages.create(model=model, max_tokens=16,
                               messages=[{"role": "user", "content": "ping"}])
    except Exception as exc:  # SDK 예외 종류가 많아 통째로 잡아 원문을 보여준다
        detail = str(exc)[:200]
        if "credit" in detail.lower() or "billing" in detail.lower():
            detail += " → 콘솔 Billing 에서 크레딧을 충전하세요"
        elif "not_found" in detail or "model" in detail.lower():
            detail += f" → CLAUDE_MODEL={model} 이 유효한지 확인하세요"
        return Result("Anthropic (Claude)", FAIL, detail)
    return Result("Anthropic (Claude)", OK, f"{model} 호출 성공")


def check_gemini(env: dict[str, str | None]) -> Result:
    api_key = env.get("GEMINI_API_KEY")
    model = env.get("GEMINI_MODEL") or "gemini-2.5-pro"
    if not api_key:
        return Result("Google (Gemini)", SKIP, "GEMINI_API_KEY 미입력")
    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        client.models.generate_content(model=model, contents="ping")
    except Exception as exc:
        detail = str(exc)[:200]
        if "quota" in detail.lower() or "429" in detail:
            detail += " → 무료 티어 한도일 수 있습니다"
        return Result("Google (Gemini)", FAIL, detail)
    return Result("Google (Gemini)", OK, f"{model} 호출 성공")


def check_telegram(env: dict[str, str | None], *, send_test: bool) -> list[Result]:
    token = env.get("TELEGRAM_BOT_TOKEN")
    chat_id = env.get("TELEGRAM_CHAT_ID")
    if (env.get("NOTIFIER") or "telegram").lower() != "telegram":
        return [Result("텔레그램", SKIP, "NOTIFIER 가 telegram 이 아님")]
    if not token:
        return [Result("텔레그램 봇", SKIP, "TELEGRAM_BOT_TOKEN 미입력")]

    import requests

    results: list[Result] = []
    try:
        me = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10).json()
    except requests.RequestException as exc:
        return [Result("텔레그램 봇", FAIL, f"접속 실패: {exc}")]

    if not me.get("ok"):
        return [Result("텔레그램 봇", FAIL, f"토큰이 유효하지 않습니다: {me.get('description')}")]
    results.append(Result("텔레그램 봇", OK, f"@{me['result'].get('username')}"))

    if not chat_id:
        # 봇에게 보낸 메시지가 있으면 거기서 chat_id 를 찾아준다.
        updates = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=10).json()
        found = {
            str(item["message"]["chat"]["id"])
            for item in updates.get("result", [])
            if item.get("message", {}).get("chat", {}).get("id")
        }
        if found:
            results.append(Result("텔레그램 CHAT_ID", FAIL,
                                  f"미입력 — 봇 대화에서 찾은 값: {', '.join(sorted(found))}"))
        else:
            results.append(Result("텔레그램 CHAT_ID", FAIL,
                                  "미입력 — 텔레그램에서 봇에게 아무 메시지나 보낸 뒤 다시 실행하세요"))
        return results

    if send_test:
        sent = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": "✅ 자동매매 알림 연결 테스트"}, timeout=10,
        ).json()
        if sent.get("ok"):
            results.append(Result("텔레그램 발송", OK, "테스트 메시지를 확인하세요"))
        else:
            results.append(Result("텔레그램 발송", FAIL,
                                  f"{sent.get('description')} → 봇에게 먼저 /start 를 보냈는지 확인"))
    else:
        results.append(Result("텔레그램 CHAT_ID", OK, f"{chat_id} (--telegram-test 로 실제 발송 확인)"))
    return results


def check_naver(env: dict[str, str | None]) -> Result:
    client_id, secret = env.get("NAVER_CLIENT_ID"), env.get("NAVER_CLIENT_SECRET")
    if not (client_id or secret):
        return Result("네이버 뉴스 (선택)", SKIP, "미설정 — 뉴스 없이 동작합니다")
    if not (client_id and secret):
        return Result("네이버 뉴스 (선택)", FAIL, "ID 와 SECRET 을 둘 다 넣거나 둘 다 비워야 합니다")

    import requests

    try:
        response = requests.get(
            "https://openapi.naver.com/v1/search/news.json",
            headers={"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": secret},
            params={"query": "삼성전자", "display": 1}, timeout=10,
        )
    except requests.RequestException as exc:
        return Result("네이버 뉴스 (선택)", FAIL, f"접속 실패: {exc}")
    if response.status_code == 200:
        return Result("네이버 뉴스 (선택)", OK, "검색 API 호출 성공")
    return Result("네이버 뉴스 (선택)", FAIL, f"HTTP {response.status_code}: {(response.text or '')[:120]}")




def run_all(env: dict[str, str | None], *, telegram_test: bool = False) -> list[Result]:
    """모든 항목을 검사해 결과 목록을 돌려준다."""
    results: list[Result] = []
    results.extend(check_kis(env))
    results.append(check_anthropic(env))
    results.append(check_gemini(env))
    results.extend(check_telegram(env, send_test=telegram_test))
    results.append(check_naver(env))
    return results


def summarize(results: list[Result]) -> dict[str, int]:
    return {
        "ok": sum(1 for r in results if r.status == OK),
        "fail": sum(1 for r in results if r.status == FAIL),
        "skip": sum(1 for r in results if r.status == SKIP),
        "required_missing": sum(1 for r in results if r.status == SKIP and not r.optional),
    }
