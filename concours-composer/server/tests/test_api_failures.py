"""Claude 호출이 실패했을 때 화면이 `{}` 가 되지 않는지.

원장님 PC에서 실제로 일어난 사고를 그대로 재현한다 — 곡이 만들어지다가 26초쯤에
확 사라지고 `{}` 만 남고 아무 버튼도 안 눌리던 것. 원인은 Anthropic SDK 예외가
아무 데서도 잡히지 않아 서버가 본문 없는 500 을 돌려준 것이었다.

여기서 보는 것은 하나다: **원인마다 다른 한국어 안내가 나오는가.**
'다시 시도하십시오' 는 답이 아니다. 키가 틀렸으면 키를 고쳐야 하고, 잔액이 없으면
충전해야 하고, 인터넷이 끊겼으면 그것부터 봐야 한다.
"""

from __future__ import annotations

import httpx
import pytest
from app.generation.apierrors import ClaudeUnavailable, translate
from fastapi.testclient import TestClient
from pydantic import BaseModel


def _resp(status: int, body: dict | None = None) -> httpx.Response:
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return httpx.Response(status, json=body or {}, request=req)


def _status_error(status: int, message: str) -> Exception:
    import anthropic

    body = {"type": "error", "error": {"type": "invalid_request_error", "message": message}}
    return anthropic.APIStatusError(message, response=_resp(status, body), body=body)


def test_wrong_key_says_to_fix_the_key_not_to_retry() -> None:
    friendly = translate(_status_error(401, "invalid x-api-key"))
    assert friendly is not None
    assert "API 키" in friendly.message
    assert ".env" in friendly.what_to_do
    assert "다시 시도" not in friendly.what_to_do


def test_empty_wallet_is_not_reported_as_a_program_bug() -> None:
    """잔액 부족은 HTTP 400 으로 온다. 그대로 읽으면 프로그램 잘못처럼 보인다."""
    friendly = translate(
        _status_error(400, "Your credit balance is too low to access the Anthropic API")
    )
    assert friendly is not None
    assert "잔액" in friendly.message
    assert "충전" in friendly.what_to_do or "Billing" in friendly.what_to_do


def test_no_internet_points_at_the_network_not_at_the_key() -> None:
    import anthropic

    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    friendly = translate(anthropic.APIConnectionError(request=req))
    assert friendly is not None
    assert "인터넷" in friendly.message
    assert "키" not in friendly.message


@pytest.mark.parametrize(
    ("status", "must_contain"),
    [(403, "모델"), (404, "모델"), (429, "잠시"), (529, "혼잡"), (500, "혼잡")],
)
def test_every_status_gets_its_own_korean_sentence(status: int, must_contain: str) -> None:
    friendly = translate(_status_error(status, "boom"))
    assert friendly is not None, f"HTTP {status} 가 번역되지 않았다"
    assert must_contain in friendly.message + friendly.what_to_do
    assert friendly.what_to_do.strip(), "할 일이 비어 있으면 화면에서 막다른 길이 된다"


def test_a_plain_python_error_is_left_alone() -> None:
    """SDK 예외가 아닌 것까지 가로채면 진짜 결함이 숨는다."""
    assert translate(ValueError("우리 쪽 버그")) is None


def test_the_screen_gets_json_not_a_blank_500() -> None:
    """`{}` 사고의 재현 — 이제는 읽을 수 있는 본문이 온다."""
    from app.main import app

    @app.get("/__test_claude_down")
    def _boom() -> None:
        raise ClaudeUnavailable("키가 거절되었습니다", "키를 다시 넣어 주십시오", ["401"])

    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/__test_claude_down")

    assert r.status_code == 502
    detail = r.json()["detail"]
    assert detail["message"] == "키가 거절되었습니다"
    assert detail["what_to_do"] == "키를 다시 넣어 주십시오"


def test_key_check_costs_nothing_and_speaks_korean_when_there_is_no_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    """키가 없을 때 점검 버튼이 오류가 아니라 안내를 준다."""
    import app.api.apikey as mod
    from app.main import app

    monkeypatch.setattr(mod, "read_api_key_from_env_file", lambda: "")
    with TestClient(app) as c:
        r = c.post("/api/api-key/check")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["what_to_do"]


def test_the_whole_way_from_a_rejected_key_to_the_screen() -> None:
    """실제 경로 그대로: Claude 가 401 을 주면 화면에 무엇이 닿는가.

    조각으로만 확인하면 배선이 빠져도 모른다 — `{}` 사고가 바로 그랬다.
    SDK 예외를 진짜 호출 자리에서 일으켜 화면까지 따라간다.
    """
    import anthropic
    from app.config import Settings
    from app.generation.client import ClaudeClient

    class Rejecting:
        class messages:  # noqa: N801
            @staticmethod
            def parse(**_: object) -> object:
                raise _status_error(401, "invalid x-api-key")

    c = ClaudeClient(settings=Settings(anthropic_api_key="sk-ant-" + "x" * 30))
    c._client = Rejecting()

    with pytest.raises(ClaudeUnavailable) as caught:
        c.parse(stage="motif", system="s", user="u", output_model=_Tiny)

    assert "API 키" in caught.value.message
    assert ".env" in caught.value.what_to_do
    # 원래 예외도 잃지 않는다 — 오류기록.txt 에 남아야 원인을 찾을 수 있다.
    assert isinstance(caught.value.__cause__, anthropic.AnthropicError)


class _Tiny(BaseModel):
    ok: bool = True


def test_the_screen_shows_what_broke_not_a_web_address() -> None:
    """오류 화면이 **쓸모 있는 줄**을 보여 주는가.

    원장님 화면에 실제로 이것만 떴다:

        For further information visit https://errors.pydantic.dev/2.13/v/json_invalid

    traceback 의 마지막 줄을 그대로 보여 주고 있었는데, 그것이 하필 주소였다.
    어디가 왜 깨졌는지 알 수가 없어서 원인을 짚는 데 한참 걸렸다.
    필요한 것은 둘이다 — 무엇이 잘못됐는가, 그리고 우리 코드 어디인가.
    """
    from app.main import app
    from app.schemas.music import CompositionPlan

    @app.post("/__test_pydantic_json")
    def _boom() -> None:
        CompositionPlan.model_validate_json("{깨진 JSON")

    with TestClient(app, raise_server_exceptions=False) as c:
        issues = c.post("/__test_pydantic_json").json()["detail"]["issues"]

    joined = " | ".join(issues)
    assert "ValidationError" in joined, f"무엇이 잘못됐는지 안 나온다: {joined}"
    assert "Invalid JSON" in joined, f"왜 거절됐는지 안 나온다: {joined}"
    assert any("우리 코드" in x for x in issues), f"어느 자리인지 안 나온다: {joined}"


def test_the_real_cause_is_found_inside_the_wrapper() -> None:
    """Starlette 는 예외를 다시 던지고 묶어서 올린다 — 뿌리까지 따라가야 한다."""
    from app.main import _useful_lines

    try:
        try:
            raise ValueError("진짜 원인")
        except ValueError as inner:
            raise RuntimeError("껍데기") from inner
    except RuntimeError as outer:
        lines = _useful_lines(outer)

    assert any("진짜 원인" in x for x in lines), f"껍데기만 보고 있다: {lines}"
