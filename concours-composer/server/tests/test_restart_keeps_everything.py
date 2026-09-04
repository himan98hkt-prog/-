"""프로그램을 껐다 켜면 만든 것이 **전부** 돌아와야 한다.

곡은 돌아오는데 사전 심사 결과만 조용히 사라지고 있었다. 저장은 되는데 복원에서
튕겨 나갔기 때문이다 — `@computed_field`(total·average·persona_label)가 저장 파일에
함께 들어가는데, 모델이 `extra="forbid"` 라 그것을 되읽을 때 거부했다.

화면에는 심사 칸이 "—" 로 남고, 곡집의 "팔 수 있는 곡" 이 0이 된다. **파는 프로그램에서
이보다 나쁜 침묵은 없다** — 원장은 심사를 통과한 곡을 통과하지 않은 것으로 보게 된다.
게다가 복원 실패는 로그에 경고 한 줄로만 남아서, 화면만 보면 알 수가 없다.

그래서 여기서는 곡·곡집·권리·심사를 다 만들어 저장하고, 다시 읽어 **하나도 빠지지
않는지** 본다. 버킷 하나가 조용히 비는 것을 잡는 것이 이 검사의 존재 이유다.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app.api.deps import STORE, Store
from app.main import app
from app.store.persistence import SqlitePersistence
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    for bucket in (STORE.students, STORE.competitions, STORE.requests, STORE.motifs,
                   STORE.plans, STORE.compositions, STORE.versions, STORE.recitals,
                   STORE.judgements, STORE.rights, STORE.books):
        bucket.clear()
    STORE.jobs.clear()
    from app.api.corpus import get_corpus

    corpus = get_corpus()
    corpus.scores.clear()
    corpus._ngrams.clear()
    with TestClient(app) as c:
        yield c


def test_nothing_is_lost_when_the_program_is_reopened(client, tmp_path: Path, caplog) -> None:
    """만들 수 있는 것을 다 만들어 놓고 저장 → 새 저장소로 복원 → 하나도 안 빠졌는지."""
    client.post("/api/compositions/market", json={"tier_id": "beginner"})
    client.post("/api/compositions/market", json={"tier_id": "middle"})
    ids = [r["composition_id"] for r in client.get("/api/compositions").json()]
    assert len(ids) == 2

    client.post("/api/books", json={"title": "시험 곡집", "composition_ids": ids})
    client.put(f"/api/compositions/{ids[0]}/rights", json={"work_type": "original"})

    before = client.get("/api/compositions").json()
    judged_before = [(r["composition_id"], r["judge_average"], r["judge_passed"]) for r in before]
    assert all(a is not None for _, a, _ in judged_before), "심사 결과가 애초에 없다"

    # ── 저장하고, 프로그램을 새로 켠 것처럼 다시 읽는다 ──────────────────────
    path = tmp_path / "store.sqlite3"
    STORE.attach(path)
    STORE.save()

    fresh = Store()
    fresh.persistence = SqlitePersistence(path)
    with caplog.at_level("WARNING"):
        fresh.load()

    failed = [r.message % r.args for r in caplog.records if "복원 실패" in r.getMessage()]
    assert not failed, f"버킷이 조용히 비었다: {failed}"

    assert len(fresh.compositions) == 2, "곡이 사라졌다"
    assert len(fresh.books) == 1, "곡집이 사라졌다"
    assert len(fresh.judgements) == 2, "사전 심사 결과가 사라졌다 — 팔 수 있는 곡이 초안으로 보인다"
    assert len(fresh.rights) >= 1, "권리 정보가 사라졌다"

    # 심사 점수가 값까지 그대로여야 한다. 껍데기만 남으면 화면 숫자가 달라진다.
    for cid, avg, _ in judged_before:
        panel = fresh.judgements[cid]
        assert abs(panel.average - avg) < 0.01, f"{cid} 심사 평균이 {avg} → {panel.average}"


def test_computed_values_survive_a_round_trip() -> None:
    """계산해서 만든 값(total·average)이 저장 파일을 거쳐도 그대로여야 한다."""
    from app.schemas.quality import CriticReport, JudgePanel, JudgeVerdict, RubricScores

    v = JudgeVerdict(
        persona="technique", accuracy=8, expression=7, structure=8, difficulty_fit=9, impression=7
    )
    for obj in (
        v,
        JudgePanel(verdicts=[v]),
        CriticReport(scores=RubricScores(**dict.fromkeys(RubricScores.model_fields, 8.0))),
    ):
        dumped = obj.model_dump()
        assert type(obj)(**dumped).model_dump() == dumped, f"{type(obj).__name__} 이 왕복하지 않는다"


def test_a_typo_in_llm_output_is_still_refused() -> None:
    """계산 필드를 걷어 내면서 오타까지 눈감아 주면 안 된다 — forbid 는 그대로다."""
    from app.schemas.quality import JudgeVerdict
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        JudgeVerdict(
            persona="technique", accuracy=8, expression=7, structure=8,
            difficulty_fit=9, impression=7, 오타필드=1,
        )
