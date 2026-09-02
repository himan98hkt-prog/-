"""곡이 만들어지는 동안 어디까지 왔는지 화면이 알 수 있어야 한다.

컨셉 카드를 누르면 1~3분이 지나간다. 그동안 화면에 "만드는 중…" 한 줄만 있으면
사람은 **고장인지 기다려야 하는지** 알 수 없다. 설치 화면에서 이미 겪은 일이다 —
멈춘 것처럼 보이면 창을 닫는다.

여기서 지키는 것은 셋이다.
1. 진행은 **지어내지 않는다** — 파이프라인이 실제로 보고한 것만 나간다.
2. 막대는 **뒤로 가지 않는다** — 뒤로 가는 막대는 없느니만 못하다.
3. 진행 보고가 막혀도 **작곡은 계속된다** — 곁다리가 본체를 죽이면 안 된다.
"""

from __future__ import annotations

import pytest
from app.api.deps import STORE
from app.main import app
from app.progress import STAGE_SPAN, Tracker
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """빈 학원에서 시작한다 — 앞 시험이 만든 곡과 표절로 부딪히지 않게."""
    for bucket in (
        STORE.students,
        STORE.competitions,
        STORE.requests,
        STORE.motifs,
        STORE.plans,
        STORE.compositions,
        STORE.versions,
        STORE.recitals,
        STORE.judgements,
        STORE.rights,
    ):
        bucket.clear()
    STORE.jobs.clear()
    from app.api.corpus import get_corpus

    corpus = get_corpus()
    corpus.scores.clear()
    corpus._ngrams.clear()
    with TestClient(app) as c:
        yield c


def test_stages_cover_the_whole_way_without_gaps() -> None:
    """구간이 끊기거나 겹치면 막대가 튀거나 뒤로 간다."""
    order = ["motif", "plan", "realize", "revise", "polish", "targeted", "judge", "save"]
    prev_hi = 0.0
    for stage in order:
        lo, hi = STAGE_SPAN[stage]
        assert lo >= prev_hi - 1e-9, f"{stage} 구간이 앞 단계와 겹친다"
        assert hi > lo, f"{stage} 구간이 비어 있다"
        prev_hi = hi
    assert STAGE_SPAN["save"][1] == 1.0, "끝이 100% 가 아니면 막대가 끝까지 안 간다"


def test_progress_reflects_what_the_pipeline_reported() -> None:
    tr = Tracker()
    tr.start("j1")
    tr.report("j1", "realize", 0.5, "17-24마디 완료")

    got = tr.get("j1")
    assert got is not None
    assert got["stage"] == "realize"
    assert got["stage_ko"] == "마디 쓰기"
    assert got["message"] == "17-24마디 완료"
    lo, hi = STAGE_SPAN["realize"]
    assert abs(got["pct"] - (lo + (hi - lo) * 0.5)) < 0.01


def test_the_bar_never_goes_backwards() -> None:
    """단계가 겹쳐 보고돼도 사람 눈에는 한 방향이어야 한다.

    실제로 그렇게 보고된다 — 다듬기(polish)가 고쳐 쓰기(revise)를 부르고,
    겨냥 수정(targeted)이 다시 고쳐 쓰기를 부른다.
    """
    tr = Tracker()
    tr.start("j2")
    tr.report("j2", "targeted", 0.9, "겨냥 수정")
    high = tr.get("j2")["pct"]
    tr.report("j2", "motif", 0.0, "뒤늦게 도착한 보고")
    assert tr.get("j2")["pct"] >= high, "막대가 뒤로 갔다"


def test_steps_are_collapsed_by_stage() -> None:
    """같은 단계가 여러 번 보고돼도 줄이 늘어나지 않는다 — 화면이 지저분해진다."""
    tr = Tracker()
    tr.start("j3")
    for i in range(5):
        tr.report("j3", "realize", i / 5, f"{i}번째")
    steps = tr.get("j3")["steps"]
    assert len(steps) == 1
    assert steps[0]["message"] == "4번째", "마지막 소식이 남아야 한다"


def test_reporting_to_an_unknown_job_is_harmless() -> None:
    """진행 보고가 막혀서 작곡이 죽으면 본말이 뒤집힌다."""
    tr = Tracker()
    tr.report("없는작업", "realize", 0.4, "무시된다")  # 예외가 나면 안 된다
    assert tr.get("없는작업") is None


def test_finish_marks_it_done_and_full() -> None:
    tr = Tracker()
    tr.start("j4")
    tr.report("j4", "plan", 0.5, "설계 중")
    tr.finish("j4")
    got = tr.get("j4")
    assert got["done"] is True and got["pct"] == 1.0 and not got["failed"]


def test_failure_is_recorded_not_hidden() -> None:
    tr = Tracker()
    tr.start("j5")
    tr.finish("j5", failed="비용 상한을 넘었습니다")
    got = tr.get("j5")
    assert got["done"] is True and got["failed"] == "비용 상한을 넘었습니다"
    assert got["pct"] < 1.0, "실패했는데 100% 로 보이면 안 된다"


# ── 화면이 실제로 물어보는 길 ───────────────────────────────────────────────


def test_the_screen_can_watch_a_real_composition(client) -> None:
    """작곡을 걸어 놓고 진행을 물어보면, 실제로 지나온 단계가 나온다.

    스텁 엔진은 곡을 순식간에 만든다. 그래서 여기서는 '만드는 도중' 을 잡으려 하지 않고,
    **끝난 뒤에 남은 기록**이 실제 단계를 담고 있는지를 본다 — 지어낸 숫자가 아니라는
    것이 요점이다.
    """
    client.post("/api/students", json=_student())
    r = client.post(
        "/api/compositions/auto",
        json={"preset_id": "march", "student_id": "s-prog", "n_candidates": 1, "progress_id": "watch1"},
    )
    assert r.status_code == 200, r.text

    p = client.get("/api/progress/watch1").json()
    assert p["known"] is True
    assert p["done"] is True
    assert p["pct"] == 1.0
    stages = {s["stage"] for s in p["steps"]}
    assert {"motif", "plan"} <= stages, f"실제 단계가 안 남았다: {stages}"


def test_asking_about_an_unknown_job_is_not_an_error(client) -> None:
    """화면은 작곡이 시작되기 전에도 물어본다 — 그때 500 이 나면 안 된다."""
    p = client.get("/api/progress/그런것없음").json()
    assert p["known"] is False and p["pct"] == 0.0


def test_composing_without_a_progress_id_still_works(client) -> None:
    """진행 표시는 곁다리다. 없어도 곡은 나와야 한다."""
    client.post("/api/students", json=_student())
    r = client.post(
        "/api/compositions/auto",
        json={"preset_id": "waltz", "student_id": "s-prog", "n_candidates": 1},
    )
    assert r.status_code == 200, r.text


def _student() -> dict:
    return {
        "id": "s-prog",
        "name": "김민준",
        "grade": "초3",
        "years_of_study": 0,
        "hand_span": {"max_interval": 7},
        "level": 4,
        "repertoire_done": [],
        "strengths": ["리듬감"],
        "weaknesses": ["레가토"],
        "tempo_comfort_max_bpm": 112,
        "reading_level": 5,
        "lowest_midi": 36,
        "highest_midi": 93,
        "notes": "",
        "media_consent": {"reels_public": False, "show_full_name": False},
    }
