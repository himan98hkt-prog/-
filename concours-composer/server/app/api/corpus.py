"""§6.1 참고 악보 라이브러리 API."""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.api.deps import Store, get_store
from app.ingest.corpus import Corpus
from app.ingest.parse import UnsupportedScore, parse_score

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/corpus", tags=["corpus"])

CORPUS = Corpus()


def get_corpus() -> Corpus:
    return CORPUS


class CorpusSummary(BaseModel):
    id: str
    title: str
    composer: str
    copyright_status: str
    era: str = ""
    division_tags: list[str] = Field(default_factory=list)
    difficulty: float
    teacher_difficulty: float | None = None
    measures: int
    key: str
    meter: str
    tempo: int
    has_notes: bool = Field(description="음표열 보관 여부. 저작권곡은 항상 False")
    needs_review: bool = False


class SearchResult(BaseModel):
    score: CorpusSummary
    similarity: float


@router.post("", response_model=CorpusSummary)
async def upload_score(
    file: UploadFile = File(...),
    title: str = Form(""),
    composer: str = Form(""),
    copyright_status: str = Form("public_domain"),
    era: str = Form(""),
    source: str = Form(""),
    division_tags: str = Form(""),
    teacher_difficulty: float | None = Form(None),
    corpus: Corpus = Depends(get_corpus),
) -> CorpusSummary:
    """MusicXML/MIDI 업로드 → StyleProfile 추출 → 검색 인덱스 등록.

    `copyright_status=copyrighted` 면 통계만 저장하고 음표열은 **보관하지 않는다**
    (절대 규칙 3). 새어나갈 경로 자체를 만들지 않는 것이 정책이다.
    """
    if copyright_status not in ("public_domain", "copyrighted", "own"):
        raise HTTPException(422, f"알 수 없는 저작권 상태: {copyright_status}")

    suffix = Path(file.filename or "score.musicxml").suffix
    data = await file.read()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    try:
        measures, meta = parse_score(tmp_path)
    except UnsupportedScore as e:
        raise HTTPException(422, str(e)) from e
    except Exception as e:  # music21 이 던지는 파싱 오류는 종류가 많다
        raise HTTPException(422, f"악보를 읽지 못했다: {type(e).__name__}: {e}") from e
    finally:
        tmp_path.unlink(missing_ok=True)

    if not measures:
        raise HTTPException(422, "마디를 하나도 읽지 못했다 — 파일을 확인하라")

    score_id = f"corpus-{len(corpus.scores) + 1:04d}"
    entry = corpus.add(
        measures,
        score_id=score_id,
        title=title or str(meta["title"]),
        composer=composer or str(meta["composer"]),
        copyright_status=copyright_status,  # type: ignore[arg-type]
        key=str(meta["key"]), meter=str(meta["meter"]), tempo=int(str(meta["tempo"])),
        era=era, source=source,
        division_tags=[t.strip() for t in division_tags.split(",") if t.strip()],
        teacher_difficulty=teacher_difficulty,
        # OMR·자동 파싱 결과는 원장 검수를 거쳐야 한다(§13 리스크 대응).
        needs_review=suffix.lower() in (".mid", ".midi"),
    )
    return CorpusSummary(**entry.summary())


@router.get("", response_model=list[CorpusSummary])
def list_scores(corpus: Corpus = Depends(get_corpus)) -> list[CorpusSummary]:
    return [CorpusSummary(**s.summary()) for s in corpus.scores.values()]


@router.get("/{score_id}/profile")
def get_profile(score_id: str, corpus: Corpus = Depends(get_corpus)) -> dict[str, Any]:
    if score_id not in corpus.scores:
        raise HTTPException(404, f"코퍼스 곡을 찾을 수 없다: {score_id}")
    s = corpus.scores[score_id]
    return {"id": score_id, "profile": s.profile.as_dict(), "vector": s.profile.vector()}


@router.delete("/{score_id}")
def delete_score(score_id: str, corpus: Corpus = Depends(get_corpus)) -> dict[str, bool]:
    if not corpus.remove(score_id):
        raise HTTPException(404, f"코퍼스 곡을 찾을 수 없다: {score_id}")
    return {"deleted": True}


@router.post("/search", response_model=list[SearchResult])
def search(
    request_id: str,
    store: Store = Depends(get_store),
    corpus: Corpus = Depends(get_corpus),
) -> list[SearchResult]:
    """이 요청에 어떤 참고곡이 붙는지 미리 본다 — 프롬프트에 뭐가 들어가는지 보이게."""
    if request_id not in store.requests:
        raise HTTPException(404, f"요청을 찾을 수 없다: {request_id}")
    req = store.requests[request_id]
    from app.analysis.style_profile import StyleProfile

    target = StyleProfile(
        key=(req.key_preference or ["C"])[0], meter=req.meter, tempo=req.tempo,
        difficulty_score=req.target_difficulty,
    )
    results = corpus.search(
        target, difficulty=req.target_difficulty,
        division=req.competition.division if req.competition else "",
        pinned_ids=req.reference_style_ids,
    )
    return [
        SearchResult(score=CorpusSummary(**s.summary()), similarity=round(sim, 4))
        for s, sim in results
    ]
