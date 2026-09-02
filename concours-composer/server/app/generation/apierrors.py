"""Claude 호출이 실패했을 때 **원장이 읽고 다음 행동을 알 수 있는 말**로 바꾼다.

원장님 PC에서 "26초쯤 만들어지다가 확 없어지고 `{}` 만 떴다" 는 사고의 정체가 이것이었다.
Anthropic SDK 가 던지는 예외(`AuthenticationError`, `BadRequestError` …)가 아무 데서도
잡히지 않고 그대로 올라가면, 서버는 본문이 없는 500 을 돌려주고 화면에는 `{}` 만 남는다.
정작 진짜 원인 — 키가 거절됐다, 크레딧이 없다, 인터넷이 끊겼다 — 은 아무 데도 안 보인다.

그래서 **모든 Claude 호출은 이 파일을 거쳐 나간다**. 여기서 SDK 예외를
`ClaudeUnavailable` 하나로 모으고, 그 안에 세 가지를 담는다.

    message     — 무슨 일이 일어났는가 (한 줄)
    what_to_do  — 원장이 지금 무엇을 하면 되는가 (이게 핵심이다)
    issues      — 화면 아래에 접어 둘 기술적 근거

'다시 시도하십시오' 같은 말은 쓰지 않는다. 키가 틀렸는데 다시 눌러 봐야 또 틀린다.
"""
from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)


class ClaudeUnavailable(RuntimeError):
    """Claude 를 부르지 못했다. 이유와 다음 행동을 함께 들고 다닌다."""

    def __init__(self, message: str, what_to_do: str, issues: list[str] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.what_to_do = what_to_do
        self.issues = issues or []

    def as_detail(self) -> dict[str, Any]:
        """FastAPI `HTTPException(detail=...)` 에 그대로 넣는 모양."""
        return {"message": self.message, "what_to_do": self.what_to_do, "issues": self.issues}


# 계정에 돈이 없을 때 Anthropic 은 400 으로 답한다. 400 은 '내 요청이 잘못됐다' 는
# 뜻이라 그대로 읽으면 프로그램 잘못처럼 보인다 — 본문을 봐야 구분된다.
_CREDIT_MARKS = ("credit balance", "insufficient", "billing", "quota")


def _body_text(exc: BaseException) -> str:
    """SDK 예외에서 사람이 읽을 수 있는 본문을 최대한 끌어낸다."""
    parts: list[str] = [str(exc)]
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict) and err.get("message"):
            parts.append(str(err["message"]))
    return " ".join(parts).lower()


def _status_of(exc: BaseException) -> int | None:
    code = getattr(exc, "status_code", None)
    return code if isinstance(code, int) else None


def translate(exc: BaseException) -> ClaudeUnavailable | None:
    """Anthropic SDK 예외면 한국어로 바꿔 돌려준다. 아니면 None."""
    try:
        import anthropic
    except ImportError:  # pragma: no cover - SDK 가 없으면 애초에 부를 일이 없다
        return None

    if not isinstance(exc, anthropic.AnthropicError):
        return None

    name = type(exc).__name__
    status = _status_of(exc)
    text = _body_text(exc)
    tech = [f"{name}" + (f" (HTTP {status})" if status else ""), str(exc)[:300]]

    # 인터넷이 끊겼거나 너무 느리다 — 키와 무관하다.
    if isinstance(exc, anthropic.APITimeoutError):
        return ClaudeUnavailable(
            "Claude 서버 응답이 너무 늦어 중간에 끊겼습니다",
            "인터넷 연결을 확인하고 다시 만들어 보십시오. 회사 네트워크나 방화벽이 막고 있을 수도 있습니다.",
            tech,
        )
    if isinstance(exc, anthropic.APIConnectionError):
        return ClaudeUnavailable(
            "인터넷으로 Claude 서버에 닿지 못했습니다",
            "인터넷이 되는지 확인해 주십시오. 회사 네트워크·백신·방화벽이 막는 경우가 많습니다. "
            "휴대폰 핫스팟으로 바꿔 보면 원인이 네트워크인지 바로 알 수 있습니다.",
            tech,
        )

    if isinstance(exc, anthropic.AuthenticationError) or status == 401:
        return ClaudeUnavailable(
            "API 키가 거절되었습니다",
            "프로그램 폴더의 .env 파일에 적힌 키를 다시 확인해 주십시오. "
            "sk-ant- 로 시작해야 하고, 앞뒤에 빈칸이나 따옴표가 붙으면 안 됩니다. "
            "키를 새로 만들었다면 옛 키는 즉시 거절됩니다.",
            tech,
        )
    if isinstance(exc, anthropic.PermissionDeniedError) or status == 403:
        return ClaudeUnavailable(
            "이 API 키로는 사용할 수 없는 모델입니다",
            "console.anthropic.com 에서 결제 수단이 등록되어 있는지, "
            "그 키에 모델 사용 권한이 있는지 확인해 주십시오.",
            tech,
        )
    if isinstance(exc, anthropic.NotFoundError) or status == 404:
        return ClaudeUnavailable(
            "지정한 Claude 모델을 찾지 못했습니다",
            "프로그램 폴더의 .env 에서 COMPOSER_MODEL / WRITER_MODEL 줄을 지우면 기본값으로 돌아갑니다. "
            "직접 적으셨다면 모델 이름의 오타를 확인해 주십시오.",
            tech,
        )
    if isinstance(exc, anthropic.RateLimitError) or status == 429:
        return ClaudeUnavailable(
            "짧은 시간에 너무 많이 요청해 Claude 가 잠시 막았습니다",
            "1~2분 뒤에 다시 눌러 주십시오. 여러 곡을 한꺼번에 만드는 중이었다면 곡 수를 줄여 보십시오.",
            tech,
        )
    if any(m in text for m in _CREDIT_MARKS):
        return ClaudeUnavailable(
            "Anthropic 계정의 잔액(크레딧)이 부족합니다",
            "console.anthropic.com → Billing 에서 결제 수단을 등록하거나 크레딧을 충전해 주십시오. "
            "충전 뒤에는 곧바로 다시 만들 수 있습니다.",
            tech,
        )
    if isinstance(exc, anthropic.RequestTooLargeError) or status == 413:
        return ClaudeUnavailable(
            "한 번에 보낸 내용이 너무 많아 거절되었습니다",
            "참고 악보 폴더에 아주 큰 파일이 들어 있지 않은지 확인해 주십시오. "
            "계속 같은 자리에서 막히면 참고 악보를 잠시 빼고 만들어 보십시오.",
            tech,
        )
    if status is not None and 500 <= status < 600:
        return ClaudeUnavailable(
            "Claude 서버가 지금 혼잡합니다 (원장님 잘못이 아닙니다)",
            "잠시 뒤에 다시 눌러 주십시오. 여기까지 쓴 비용은 청구되지 않습니다.",
            tech,
        )
    if status == 400:
        return ClaudeUnavailable(
            "Claude 가 요청을 거절했습니다",
            "다른 성격이나 다른 급수로 한 번 더 만들어 보십시오. "
            "계속 같은 자리에서 막히면 '오류기록.txt' 파일을 보내 주십시오.",
            tech,
        )

    return ClaudeUnavailable(
        "Claude 를 부르는 중에 문제가 생겼습니다",
        "잠시 뒤 다시 시도해 보시고, 계속 같은 자리에서 막히면 '오류기록.txt' 파일을 보내 주십시오.",
        tech,
    )


def reraise_friendly(exc: BaseException) -> None:
    """SDK 예외면 한국어 예외로 바꿔 던지고, 아니면 아무것도 하지 않는다."""
    friendly = translate(exc)
    if friendly is None:
        return
    log.warning("Claude 호출 실패 → %s", friendly.message)
    raise friendly from exc
