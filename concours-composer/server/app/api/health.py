from __future__ import annotations

from fastapi import APIRouter, Request

from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health(request: Request) -> dict:
    s = get_settings()
    return {
        "status": "ok",
        "composer_model": s.composer_model,
        "writer_model": s.writer_model,
        "engine": "claude" if s.has_api_key else "stub-rule-based",
        "quality_threshold": s.quality_threshold,
        "max_revision_rounds": s.max_revision_rounds,
        "max_cost_per_composition": s.max_cost_per_composition,
        "model_problems": getattr(request.app.state, "model_problems", []),
    }
