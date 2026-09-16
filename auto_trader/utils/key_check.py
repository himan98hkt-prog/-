"""발급받은 키가 실제로 동작하는지 항목별로 확인한다.

`scripts/check_keys.py`(CLI)와 대시보드 설정 화면이 같은 로직을 쓴다.
각 검사는 **독립적**이어서 일부 키만 채운 상태에서도 돌아간다.
"""

from __future__ import annotations

from dataclasses import dataclass

import time

OK, FAIL, SKIP = "ok", "fail", "skip"

# KIS 토큰 서버가 느릴 때를 견디기 위한 값
KIS_TOKEN_TIMEOUT_SEC = 30
KIS_TOKEN_ATTEMPTS = 3
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


# --------------------------------------------------------------------------- #
# 값 위생 검사 — "키가 맞는데 왜 안 되지" 의 대부분은 눈에 안 보이는 문자 때문이다
# --------------------------------------------------------------------------- #

# 서비스를 서로 바꿔 넣은 경우만 잡는다.
#
# "이 키는 반드시 이렇게 시작한다" 는 식의 검사는 하지 않는다 — 제공사가 키 형식을
# 바꾸면 멀쩡한 키를 틀렸다고 막아 세운다(실제로 Gemini 키가 AIza 로 시작하지 않는
# 사례가 있었다). 대신 **다른 서비스의 키가 분명한 경우**만 짚는다.
FOREIGN_PREFIX = {
    "ANTHROPIC_API_KEY": (("AIza", "Gemini"),),
    "GEMINI_API_KEY": (("sk-ant-", "Anthropic"), ("sk-proj-", "OpenAI")),
    "OPENAI_API_KEY": (("sk-ant-", "Anthropic"), ("AIza", "Gemini")),
}

# 눈에 보이지 않거나 붙여넣기 사고로 섞이는 문자들
INVISIBLE = {
    "\u200b": "제로폭 공백", "\u200c": "제로폭 비접합", "\u200d": "제로폭 접합",
    "\ufeff": "BOM", "\u00a0": "줄바꿈 없는 공백", "\u3000": "전각 공백",
}


def _describe_bad_chars(value: str) -> list[str]:
    """값에 섞인 문제 문자를 사람이 읽을 수 있게 설명한다 (값 자체는 노출하지 않는다)."""
    problems: list[str] = []
    if value != value.strip():
        problems.append("앞뒤 공백")
    if "\n" in value or "\r" in value:
        problems.append("줄바꿈")
    if "\t" in value:
        problems.append("탭")
    # 공백을 걷어낸 뒤에 본다 — ` "키" ` 처럼 공백에 감싸인 따옴표도 잡아야 한다.
    trimmed = value.strip()
    if trimmed[:1] in ("'", '"') or trimmed[-1:] in ("'", '"'):
        problems.append("따옴표")
    for char, label in INVISIBLE.items():
        if char in value:
            problems.append(label)
    # 한글 IME 를 켜 둔 채 입력하면 한글이나 전각 문자가 섞인다.
    hangul = [c for c in value if "\uac00" <= c <= "\ud7a3" or "\u3131" <= c <= "\u318e"]
    if hangul:
        problems.append(f"한글 {len(hangul)}자 (입력기가 켜져 있었을 수 있습니다)")
    else:
        other = [c for c in value if ord(c) > 127]
        if other:
            problems.append(f"영문·숫자가 아닌 문자 {len(other)}자")
    return problems


def check_value_hygiene(env: dict[str, str | None]) -> list[Result]:
    """붙여넣기 사고를 잡아낸다. API 를 부르기 전에 먼저 돌린다.

    실패한 키를 몇 번씩 다시 입력해도 같은 오류가 나올 때, 원인은 대개
    값 자체가 아니라 값에 딸려 들어간 공백·줄바꿈·따옴표·한글이다.
    """
    results: list[Result] = []
    for key in ("KIS_APP_KEY", "KIS_APP_SECRET", "ANTHROPIC_API_KEY", "GEMINI_API_KEY",
                "CLAUDE_MODEL", "GEMINI_MODEL", "OPENAI_API_KEY", "OPENAI_MODEL",
                "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        value = env.get(key)
        if not value:
            continue

        problems = _describe_bad_chars(value)
        for prefix, service in FOREIGN_PREFIX.get(key, ()):
            if value.strip().startswith(prefix):
                problems.append(f"{service} 키로 보입니다 (칸을 바꿔 넣으셨나요?)")


        if problems:
            results.append(Result(
                f"입력값 {key}", FAIL,
                f"{', '.join(problems)} — 길이 {len(value)}자. "
                "메모장에 한 번 붙여넣어 확인한 뒤 다시 입력하세요",
            ))
    return results


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
        if mode == "REAL":
            # 실전 계좌다. 초록색 체크로 지나가면 안 된다.
            results.append(Result(
                "KIS 계좌번호", FAIL,
                f"{account[:2]}****{account[-2:]} — ⚠️ REAL(실전) 계좌입니다. "
                "검증 전에는 KIS_ENV=VTS(모의투자)로 두세요. "
                "실전으로 운용하시려면 설정 화면에서 REAL 을 그대로 두고 이 경고를 무시하세요",
            ))
        else:
            results.append(Result("KIS 계좌번호", OK, f"{account[:2]}****{account[-2:]} (모의투자)"))

    import requests

    base = ("https://openapivts.koreainvestment.com:29443" if mode == "VTS"
            else "https://openapi.koreainvestment.com:9443")
    # KIS 토큰 서버는 느릴 때가 잦다. 짧은 타임아웃으로 한 번 실패했다고
    # "키가 틀렸다" 로 읽히면 멀쩡한 키를 계속 다시 만들게 된다.
    response = None
    last_error = None
    for attempt in range(KIS_TOKEN_ATTEMPTS):
        try:
            response = requests.post(
                f"{base}/oauth2/tokenP",
                json={"grant_type": "client_credentials", "appkey": key, "appsecret": secret},
                timeout=KIS_TOKEN_TIMEOUT_SEC,
            )
            break
        except requests.RequestException as exc:
            last_error = exc
            if attempt < KIS_TOKEN_ATTEMPTS - 1:
                time.sleep(2)

    if response is None:
        timed_out = "timed out" in str(last_error).lower()
        advice = (
            "키 문제가 아닙니다. 확인할 것: "
            f"① 백신·방화벽이 {base.rsplit(':', 1)[-1]}번 포트를 막고 있는지 "
            "(증권사 API 는 비표준 포트를 씁니다 — 회사망·공유기에서 자주 막힙니다) "
            "② 인터넷 연결 ③ 잠시 뒤 재시도"
        ) if timed_out else "키 문제가 아니라 네트워크·증권사 서버 쪽입니다"
        results.append(Result(
            "KIS 인증", FAIL,
            f"{KIS_TOKEN_ATTEMPTS}번 시도했지만 접속하지 못했습니다 ({last_error}). {advice}",
        ))
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
        elif "authentication_error" in detail or "401" in detail:
            # 키 문자열 자체가 잘못됐다는 뜻이다. 잔액 부족은 401 이 아니다.
            detail += (
                f" → 키를 다시 발급받아 넣으세요 (현재 {len(api_key)}자,"
                f" {api_key[:7]}…{api_key[-4:]}). 콘솔에서 삭제된 키이거나,"
                " 복사할 때 일부가 빠졌을 수 있습니다"
            )
        elif "not_found" in detail or "model" in detail.lower():
            detail += f" → CLAUDE_MODEL={model!r} 이 유효한지 확인하세요"
        return Result("Anthropic (Claude)", FAIL, detail)
    return Result("Anthropic (Claude)", OK, f"{model} 호출 성공")


def check_gemini(env: dict[str, str | None]) -> Result:
    api_key = env.get("GEMINI_API_KEY")
    model = env.get("GEMINI_MODEL") or "gemini-3.5-flash"
    if not api_key:
        return Result("Google (Gemini)", SKIP, "GEMINI_API_KEY 미입력")
    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        client.models.generate_content(model=model, contents="ping")
    except Exception as exc:
        detail = str(exc)[:200]
        if "no longer available" in detail or "404" in detail:
            detail += (
                " → 모델 이름을 바꾸세요. gemini-2.5-pro 는 신규 사용자에게 막혔습니다."
                " 설정 화면에서 gemini-3.1-pro-preview (유료) 또는"
                " gemini-3.5-flash (무료 한도) 로 저장하세요"
            )
        elif "unexpected model name format" in detail or "model name" in detail.lower():
            # 키가 아니라 모델 이름이 문제다 — 값을 그대로 보여줘야 원인이 보인다.
            detail += (
                f" → 키가 아니라 모델 이름 문제입니다. GEMINI_MODEL={model!r}"
                " (따옴표 안에 공백·줄바꿈이 보이면 그게 원인입니다)."
                " 설정 화면에서 gemini-3.1-pro-preview 로 다시 저장하세요"
            )
        elif "RESOURCE_EXHAUSTED" in detail or "429" in detail or "quota" in detail.lower():
            return Result(
                "Google (Gemini)", FAIL,
                f"키는 정상입니다 — {model} 이(가) 무료 한도를 벗어났습니다. "
                "설정 화면의 'Gemini 모델' 을 gemini-3.5-flash 로 바꾸면 무료 한도로 쓸 수 있습니다. "
                "지금 모델을 그대로 쓰시려면 aistudio.google.com 에서 결제를 등록하세요",
            )
        elif "API key" in detail or "401" in detail or "403" in detail:
            detail += f" → 키를 다시 확인하세요 (현재 {len(api_key)}자)"
        return Result("Google (Gemini)", FAIL, detail)
    return Result("Google (Gemini)", OK, f"{model} 호출 성공")


def check_openai(env: dict[str, str | None]) -> Result:
    """ChatGPT 는 선택 — 키가 없으면 건너뛴다(실패가 아니다)."""
    api_key = env.get("OPENAI_API_KEY")
    model = env.get("OPENAI_MODEL") or "gpt-5.1"
    if not api_key:
        return Result("ChatGPT (선택)", SKIP, "미입력 — Claude·Gemini 둘로만 판단합니다")
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, timeout=30.0, max_retries=0)
        client.chat.completions.create(
            model=model, max_completion_tokens=16,
            messages=[{"role": "user", "content": "ping"}],
        )
    except Exception as exc:
        detail = str(exc)[:200]
        if "insufficient_quota" in detail or "no credits" in detail.lower():
            # 키는 정상이다. 잔액만 없다.
            return Result(
                "ChatGPT (선택)", FAIL,
                "키는 정상입니다 — 잔액이 0 입니다. "
                "platform.openai.com/settings/organization/billing 에서 "
                "결제수단을 등록하고 $5 이상 충전하세요. "
                "ChatGPT Plus 구독과 API 잔액은 별개입니다. "
                "충전하지 않으시려면 ChatGPT API 키 칸을 비우면 됩니다 "
                "(Claude·Gemini 둘로 정상 동작합니다)",
            )
        if "model" in detail.lower() and "not" in detail.lower():
            detail += f" → OPENAI_MODEL={model!r} 이 계정에서 쓸 수 있는 모델인지 확인하세요"
        elif "quota" in detail.lower() or "billing" in detail.lower():
            detail += " → platform.openai.com/settings/organization/billing 에서 결제수단을 등록하세요"
        elif "401" in detail or "authentication" in detail.lower():
            detail += f" → 키를 다시 발급받으세요 (현재 {len(api_key)}자)"
        return Result("ChatGPT (선택)", FAIL, detail)
    return Result("ChatGPT (선택)", OK, f"{model} 호출 성공")


def find_telegram_chats(token: str) -> list[tuple[str, str]]:
    """봇이 받은 메시지에서 (채팅 ID, 보낸 사람) 목록을 뽑는다.

    텔레그램 봇은 **상대가 먼저 말을 걸어야** 그 채팅으로 보낼 수 있다.
    그래서 사용자가 봇에게 /start 를 보낸 뒤 이 함수를 부르면 채팅 ID 를
    직접 찾아 줄 수 있다 — 숫자를 손으로 알아내게 하지 않는다.
    """
    import requests

    try:
        data = requests.get(
            f"https://api.telegram.org/bot{token}/getUpdates", timeout=10).json()
    except (requests.RequestException, ValueError):
        return []
    if not data.get("ok"):
        return []

    found: dict[str, str] = {}
    for item in data.get("result") or []:
        message = item.get("message") or item.get("edited_message") or {}
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        if chat_id is None:
            continue
        name = (chat.get("title")
                or " ".join(filter(None, (chat.get("first_name"), chat.get("last_name"))))
                or chat.get("username") or "이름 없음")
        # 같은 채팅이 여러 번 나오면 더 자세한 이름을 남긴다
        # (어떤 메시지엔 성이 빠져 있기도 하다).
        key = str(chat_id)
        if len(name) > len(found.get(key, "")):
            found[key] = name
    return sorted(found.items())


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
        found = find_telegram_chats(token)
        if found:
            hint = ", ".join(f"{cid} ({name})" for cid, name in found)
            results.append(Result("텔레그램 CHAT_ID", FAIL, f"미입력 — 봇 대화에서 찾은 값: {hint}"))
        else:
            results.append(Result("텔레그램 CHAT_ID", FAIL,
                                  "미입력 — 텔레그램에서 봇에게 아무 메시지나 보낸 뒤 "
                                  "설정 화면의 '내 채팅 ID 찾기' 를 누르세요"))
        return results

    if send_test:
        sent = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": "✅ 자동매매 알림 연결 테스트"}, timeout=10,
        ).json()
        if sent.get("ok"):
            results.append(Result("텔레그램 발송", OK, "테스트 메시지를 확인하세요"))
        else:
            reason = sent.get("description") or ""
            if "chat not found" in reason.lower():
                found = find_telegram_chats(token)
                if found:
                    hint = ", ".join(f"{cid} ({name})" for cid, name in found)
                    detail = (f"채팅 ID {chat_id} 로는 보낼 수 없습니다. "
                              f"봇 대화에서 찾은 실제 값: {hint} — "
                              "설정 화면의 '내 채팅 ID 찾기' 를 누르면 자동으로 채워집니다")
                else:
                    detail = ("토큰은 정상입니다. 텔레그램에서 봇을 찾아 **먼저 말을 걸어야** 합니다 — "
                              "@{} 대화창을 열고 [시작] 또는 /start 를 보낸 뒤, "
                              "설정 화면의 '내 채팅 ID 찾기' 를 누르세요").format(
                                  me["result"].get("username"))
                results.append(Result("텔레그램 발송", FAIL, detail))
            else:
                results.append(Result("텔레그램 발송", FAIL, f"{reason} → 봇 설정을 확인하세요"))
    else:
        results.append(Result("텔레그램 CHAT_ID", OK, f"{chat_id} (--telegram-test 로 실제 발송 확인)"))
    return results


def run_all(env: dict[str, str | None], *, telegram_test: bool = False) -> list[Result]:
    """모든 항목을 검사해 결과 목록을 돌려준다."""
    results: list[Result] = []
    # 값 위생을 먼저 본다 — 여기서 걸리면 API 오류 메시지가 원인을 가린다.
    results.extend(check_value_hygiene(env))
    results.extend(check_kis(env))
    results.append(check_anthropic(env))
    results.append(check_gemini(env))
    results.append(check_openai(env))
    results.extend(check_telegram(env, send_test=telegram_test))
    return results


def summarize(results: list[Result]) -> dict[str, int]:
    """항목별 집계.

    `blocking_fail` 과 `fail` 을 구분하는 이유: ChatGPT 처럼 **선택** 항목이
    실패해도 프로그램은 정상 동작한다. 선택 항목 하나 때문에 "아직 준비되지
    않았습니다" 를 띄워 사용자를 막아 세우면 안 된다.
    """
    return {
        "ok": sum(1 for r in results if r.status == OK),
        "fail": sum(1 for r in results if r.status == FAIL),
        "blocking_fail": sum(1 for r in results if r.status == FAIL and not r.optional),
        "optional_fail": sum(1 for r in results if r.status == FAIL and r.optional),
        "skip": sum(1 for r in results if r.status == SKIP),
        "required_missing": sum(1 for r in results if r.status == SKIP and not r.optional),
    }
