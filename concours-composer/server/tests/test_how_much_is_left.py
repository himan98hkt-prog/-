"""남은 돈 — **모르는 것을 아는 척하지 않으면서** 아는 것은 정확히 센다.

원장님이 이렇게 물으셨다:

    "지금까지 얼마가 소진되었고 얼마가 남아 있는지도 확인할 수 있게 만들어줘."

여기서 지켜야 할 선이 하나 있다. **앤트로픽 계정의 진짜 잔액은 우리가 못 읽는다.**
그것을 읽는 창구(Admin API)는 `sk-ant-admin...` 관리자 키만 받고, 원장님이 넣으신
보통 키는 거절한다. 그러니 그럴듯한 잔액을 만들어 내면 그건 거짓말이고, 원장님은
그 거짓 숫자를 믿고 곡을 만들다 또 중간에 멈추신다. 이 파일은 그 거짓말을 막는다.

대신 아는 것은 정확히 센다 — 원장님이 적어 두신 충전액에서, 이 프로그램이 실제로
치른 값(성공한 곡이든 날린 시도든)을 뺀다.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app.api.deps import STORE
from app.main import app
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def client():
    STORE.jobs.clear()
    with TestClient(app) as c:
        yield c


def _spent(at: str, usd: float, ok: bool = True) -> dict:
    return {"at": at, "usd": usd, "ok": ok, "what": "중급 토카타"}


# ── 모르면 모른다고 한다 ───────────────────────────────────────────────────


def test_it_says_it_does_not_know_before_you_tell_it(client) -> None:
    """충전액을 안 적으셨으면 남은 돈을 **지어내지 않는다**."""
    w = client.get("/api/wallet").json()
    assert w["known"] is False
    assert w["charged_usd"] == 0
    assert w["remaining_usd"] == 0, "모르면서 0 이 아닌 숫자를 만들어 내면 안 된다"


def test_it_never_claims_to_read_the_real_account_balance(client) -> None:
    """계정 잔액을 읽는다고 말하면 안 된다 — 우리는 못 읽는다."""
    w = client.get("/api/wallet").json()
    assert "console.anthropic.com" in w["truth"], (
        "진짜 잔액을 어디서 보는지 알려 주지 않으면 원장님은 여기 숫자를 계정 잔액으로 믿으신다"
    )


def test_the_screen_admits_the_limit_in_plain_korean() -> None:
    """화면 글에도 못 읽는다는 사실이 적혀 있어야 한다."""
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    assert "console.anthropic.com" in html
    assert "읽을 수 없습니다" in html, "화면이 진짜 잔액을 아는 척하면 안 된다"


# ── 아는 것은 정확히 센다 ──────────────────────────────────────────────────


def test_it_subtracts_what_was_really_spent(client) -> None:
    r = client.post("/api/wallet/topup", json={"usd": 20, "note": "9월 카드"})
    assert r.status_code == 200
    STORE.jobs["spend_log"] = [
        _spent("2999-01-01T00:00:00+00:00", 0.42),
        _spent("2999-01-02T00:00:00+00:00", 0.18),
    ]
    w = client.get("/api/wallet").json()
    assert w["known"] is True
    assert w["charged_usd"] == 20
    assert w["spent_usd"] == pytest.approx(0.60)
    assert w["remaining_usd"] == pytest.approx(19.40)


def test_failed_attempts_count_against_the_money_too(client) -> None:
    """**곡을 못 얻은 시도에도 돈은 나갔다.** 그것을 빼지 않으면 남은 돈이 부풀려진다."""
    client.post("/api/wallet/topup", json={"usd": 5})
    STORE.jobs["spend_log"] = [_spent("2999-01-01T00:00:00+00:00", 1.25, ok=False)]
    w = client.get("/api/wallet").json()
    assert w["spent_usd"] == pytest.approx(1.25)
    assert w["remaining_usd"] == pytest.approx(3.75)


def test_money_spent_before_the_top_up_is_not_subtracted(client) -> None:
    """충전을 적기 **전에** 쓴 돈은 그 충전금에서 나간 돈이 아니다.

    이것을 빼면 방금 20 달러를 넣으신 원장님께 "남은 돈 3 달러" 라고 말하게 된다.
    """
    STORE.jobs["spend_log"] = [_spent("1999-01-01T00:00:00+00:00", 17.0)]
    w = client.post("/api/wallet/topup", json={"usd": 20}).json()
    assert w["remaining_usd"] == pytest.approx(20.0)
    # 그래도 여태 이 프로그램이 쓴 돈 전부는 따로 볼 수 있어야 한다.
    assert w["spent_all_usd"] == pytest.approx(17.0)


def test_topping_up_again_adds_to_what_is_left(client) -> None:
    client.post("/api/wallet/topup", json={"usd": 10})
    STORE.jobs["spend_log"] = [_spent("2999-01-01T00:00:00+00:00", 8.0)]
    client.post("/api/wallet/topup", json={"usd": 10})
    w = client.get("/api/wallet").json()
    assert w["charged_usd"] == 20
    assert w["remaining_usd"] == pytest.approx(12.0)


# ── 손이 미끄러졌을 때 ─────────────────────────────────────────────────────


def test_a_slip_of_the_zero_can_be_undone(client) -> None:
    """0 을 하나 더 붙이셨을 때 되돌릴 길이 없으면 숫자가 영영 틀린 채로 남는다."""
    client.post("/api/wallet/topup", json={"usd": 20})
    client.post("/api/wallet/topup", json={"usd": 200})
    w = client.post("/api/wallet/undo").json()
    assert w["charged_usd"] == 20


def test_undo_with_nothing_to_undo_is_a_plain_message_not_a_crash(client) -> None:
    r = client.post("/api/wallet/undo")
    assert r.status_code == 404
    assert "충전" in r.json()["detail"]


def test_absurd_amounts_are_refused(client) -> None:
    """100 달러를 넣으려다 0 을 세 개 더 붙이는 일은 실제로 일어난다."""
    assert client.post("/api/wallet/topup", json={"usd": 999999}).status_code == 422
    assert client.post("/api/wallet/topup", json={"usd": 0}).status_code == 422
    assert client.post("/api/wallet/topup", json={"usd": -5}).status_code == 422


# ── 다 써 가면 미리 말해 준다 ──────────────────────────────────────────────


def test_it_warns_before_the_money_runs_out(client) -> None:
    """다 쓰고 나서 알려 주면 늦다 — 곡을 만들다 중간에 멈춘다."""
    client.post("/api/wallet/topup", json={"usd": 10})
    STORE.jobs["spend_log"] = [_spent("2999-01-01T00:00:00+00:00", 6.5)]
    assert client.get("/api/wallet").json()["low"] is True
    assert client.get("/api/wallet").json()["empty"] is False


def test_it_says_plainly_when_the_money_is_gone(client) -> None:
    client.post("/api/wallet/topup", json={"usd": 1})
    STORE.jobs["spend_log"] = [_spent("2999-01-01T00:00:00+00:00", 1.4)]
    w = client.get("/api/wallet").json()
    assert w["empty"] is True
    assert w["remaining_usd"] < 0, "넘겨 쓴 것을 0 으로 반올림하면 얼마나 넘었는지 못 보신다"


# ── 화면이 한 번에 읽어 간다 ───────────────────────────────────────────────


def test_the_spending_screen_gets_the_wallet_in_the_same_breath(client) -> None:
    """대시보드가 두 번 물어보게 하면 한쪽만 새로 고쳐진 채 어긋난다."""
    client.post("/api/wallet/topup", json={"usd": 20})
    s = client.get("/api/spending").json()
    assert s["wallet"]["charged_usd"] == 20


def test_it_survives_a_restart(client) -> None:
    """적어 두신 충전액이 껐다 켜면 사라지면 적을 이유가 없다."""
    from app.api.deps import PERSISTED

    assert "jobs" in PERSISTED, "충전 기록은 jobs 버킷에 있다 — 파일로 내려가야 한다"
