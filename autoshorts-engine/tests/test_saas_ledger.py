"""크레딧 원장 — Master Guard 11번(실패가 크레딧을 먹지 않는다)의 검증."""

from __future__ import annotations

import threading

import pytest

from saas.ledger import InsufficientCredits, Ledger, estimate_job_credits
from saas.repositories import UserRepository, WorkspaceRepository


@pytest.fixture
def workspace(db):
    user = UserRepository(db).create("owner@example.com", "a-long-enough-password")
    return WorkspaceRepository(db).create("W", user["id"], initial_credits=1000)["id"]


@pytest.fixture
def ledger(db):
    return Ledger(db)


def test_grant_recorded_at_signup(db, ledger, workspace):
    assert ledger.state(workspace).balance == 1000
    entries = ledger.entries(workspace)
    assert [e["entry_type"] for e in entries] == ["grant"]


def test_reserve_moves_balance_to_reserved_without_changing_total(ledger, workspace):
    state = ledger.reserve(workspace, "job_1", 300)
    assert (state.balance, state.reserved) == (700, 300)
    assert state.balance + state.reserved == 1000


def test_commit_charges_only_what_was_used(ledger, workspace):
    ledger.reserve(workspace, "job_1", 300)
    state = ledger.commit(workspace, "job_1", reserved=300, actual=120)
    assert (state.balance, state.reserved) == (880, 0)   # 180 은 돌려받는다


def test_commit_never_charges_more_than_reserved(ledger, workspace):
    """엔진이 예상보다 긴 결과를 냈다고 예약 밖까지 걷지 않는다."""
    ledger.reserve(workspace, "job_1", 100)
    state = ledger.commit(workspace, "job_1", reserved=100, actual=100_000)
    assert (state.balance, state.reserved) == (900, 0)


def test_failed_job_refunds_everything(ledger, workspace):
    ledger.reserve(workspace, "job_1", 300)
    state = ledger.release(workspace, "job_1", 300, reason="렌더 실패")
    assert (state.balance, state.reserved) == (1000, 0)


def test_cancelled_job_refunds_everything(ledger, workspace):
    ledger.reserve(workspace, "job_1", 250)
    assert ledger.release(workspace, "job_1", 250, reason="취소").balance == 1000


def test_insufficient_credits_rejected_and_nothing_moves(ledger, workspace):
    with pytest.raises(InsufficientCredits):
        ledger.reserve(workspace, "job_1", 2000)
    assert (ledger.state(workspace).balance, ledger.state(workspace).reserved) == (1000, 0)


def test_double_commit_does_not_double_charge(db, ledger, workspace):
    """재시도가 원장을 두 번 쓰면 사용자가 두 번 낸다."""
    ledger.reserve(workspace, "job_1", 300)
    ledger.commit(workspace, "job_1", reserved=300, actual=100)
    entries = [e for e in ledger.entries(workspace) if e["entry_type"] == "commit"]
    assert len(entries) == 1
    # 같은 작업에 두 번째 commit 원장은 유니크 인덱스가 막는다.
    rows = db.fetch_all(
        "SELECT COUNT(*) AS n FROM credit_ledger WHERE job_id = 'job_1' AND entry_type = 'commit'"
    )
    assert rows[0]["n"] == 1


def test_concurrent_reserves_cannot_overdraw(db, workspace):
    """읽고-확인하고-쓰면 동시 요청 두 개가 같은 잔액을 보고 둘 다 통과한다.

    조건부 UPDATE 로 막았는지 실제 스레드로 확인한다.
    """
    successes, failures = [], []
    barrier = threading.Barrier(10)

    def attempt(index: int) -> None:
        ledger = Ledger(db)
        barrier.wait()
        try:
            ledger.reserve(workspace, f"job_{index}", 200)   # 1000 / 200 = 5 건만 가능
            successes.append(index)
        except InsufficientCredits:
            failures.append(index)

    threads = [threading.Thread(target=attempt, args=(i,)) for i in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(successes) == 5
    assert len(failures) == 5
    state = Ledger(db).state(workspace)
    assert (state.balance, state.reserved) == (0, 1000)


def test_usage_and_cost_events_are_recorded(ledger, workspace):
    ledger.record_usage(workspace, event_type="render_output_seconds", quantity=87.2, unit="seconds")
    ledger.record_cost(workspace, provider="gemini", resource="highlight",
                       quantity=1200, unit="tokens", micro_usd=350)
    summary = ledger.summary(workspace)
    assert summary["usage"][0]["event_type"] == "render_output_seconds"
    assert summary["usage"][0]["total"] == pytest.approx(87.2)
    assert summary["cost"][0]["micro_usd"] == 350


def test_engine_cost_events_are_translated(ledger, workspace):
    """autoshorts.contracts.CostEvent 의 kind/units/unit_name 어휘를 원장 어휘로 옮긴다."""
    from autoshorts.contracts import CostEvent

    events = [
        CostEvent(kind="render", provider="ffmpeg", units=87.2, unit_name="seconds").to_dict(),
        CostEvent(kind="storage", units=6_503_276, unit_name="bytes").to_dict(),
    ]
    assert ledger.record_cost_events(workspace, "job_1", events) == 2
    cost = {row["resource"]: row for row in ledger.summary(workspace)["cost"]}
    assert cost["render"]["total"] == pytest.approx(87.2)
    assert cost["render"]["unit"] == "seconds"
    assert cost["storage"]["total"] == pytest.approx(6_503_276)


def test_grant_requires_positive_amount(ledger, workspace):
    with pytest.raises(ValueError):
        ledger.grant(workspace, 0)


def test_unknown_workspace_raises(ledger):
    with pytest.raises(LookupError):
        ledger.state("ws_does_not_exist")


# ── 예약액 산정 ────────────────────────────────────────────


def test_estimate_uses_worst_case():
    """부족하게 잡으면 실행 도중 잔액이 마이너스가 된다. 남는 건 commit 때 돌려준다."""
    assert estimate_job_credits(source_seconds=None, max_clips=5, max_clip_seconds=60) == 300


def test_estimate_capped_by_source_length():
    """20초짜리 원본에서 5×60초가 나올 수는 없다."""
    assert estimate_job_credits(source_seconds=20, max_clips=5, max_clip_seconds=60) == 20


def test_estimate_has_a_floor():
    assert estimate_job_credits(source_seconds=1, max_clips=1, max_clip_seconds=1) == 10
