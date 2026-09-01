#!/usr/bin/env python3
"""컨셉 하나로 곡을 끝까지 만들고 **실측치**를 찍는다 — 실제 API 실행용.

대시보드가 하는 일과 같은 경로를 CLI 로 돈다. 다른 점은 결과를 눈으로 보는 대신
**시간·비용·심사 결과**를 표로 남긴다는 것뿐이다. 실제 API 로 돌릴 때 곡당 얼마가
드는지, 사전 심사 게이트를 통과하는지 재려고 만들었다.

    .venv/bin/python scripts/auto_compose.py --preset march --level 4
    .venv/bin/python scripts/auto_compose.py --preset finale --level 9 --difficulty 8

API 키는 **프로젝트 .env 에서만** 읽는다(app/config.py). 키가 없으면 규칙 기반 스텁으로
돌고, 그 사실을 먼저 알린다 — 실측이 아니라는 것을 모르고 지나칠 수는 없어야 한다.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

OUT_DIR = ROOT / "runs" / "auto"


def main() -> int:
    from app.api.deps import STORE, get_pipeline
    from app.api.studio import AutoComposeIn, auto_compose
    from app.config import get_settings
    from app.generation.presets import BY_ID
    from app.schemas.student import CompetitionProfile, HandSpan, Student

    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", default="march", help=f"컨셉 id ({', '.join(BY_ID)})")
    ap.add_argument("--level", type=int, default=4, help="학생 레벨 1~10")
    ap.add_argument("--grade", default="초3")
    ap.add_argument("--span", type=int, default=7, help="손 스팬(도)")
    ap.add_argument("--comfort", type=int, default=112, help="편안한 템포 상한")
    ap.add_argument("--reading", type=int, default=5, help="독보 수준 1~10")
    ap.add_argument("--strengths", default="빠른 손가락")
    ap.add_argument("--weaknesses", default="옥타브")
    ap.add_argument("--difficulty", type=float, default=None, help="목표 난이도(기본: 레벨)")
    ap.add_argument("--limit", type=int, default=150, help="콩쿨 제한 시간(초)")
    ap.add_argument("--out", default=str(OUT_DIR), help="산출물 폴더")
    args = ap.parse_args()

    if args.preset not in BY_ID:
        print(f"알 수 없는 컨셉: {args.preset} — 쓸 수 있는 것: {', '.join(BY_ID)}", file=sys.stderr)
        return 2

    s = get_settings()
    engine = "claude" if s.has_api_key else "stub-rule-based"
    print(f"엔진 {engine} · COMPOSER_MODEL={s.composer_model} · 비용 상한 ${s.max_cost_per_composition}")
    if not s.has_api_key:
        print("  ! .env 의 ANTHROPIC_API_KEY 가 비어 있다 — 규칙 기반 스텁으로 돈다(실측 아님)")

    student = Student(
        id="s-auto", name="학생", grade=args.grade, years_of_study=0,
        hand_span=HandSpan(max_interval=args.span), level=args.level,
        strengths=[x.strip() for x in args.strengths.split(",") if x.strip()],
        weaknesses=[x.strip() for x in args.weaknesses.split(",") if x.strip()],
        tempo_comfort_max_bpm=args.comfort, reading_level=args.reading,
    )
    competition = CompetitionProfile(
        id="c-auto", name="콩쿨", division=args.grade, time_limit_sec=args.limit,
        original_allowed=True,
    ) if args.limit > 0 else None

    body = AutoComposeIn(
        preset_id=args.preset, student=student, competition=competition,
        target_difficulty=args.difficulty,
    )
    t0 = time.time()
    out = auto_compose(body, store=STORE, pipeline=get_pipeline(), settings=s)
    secs = time.time() - t0

    j = out.judge
    print(f"\n[{out.preset_id}] {out.title}")
    print(f"  {out.measures}마디 · {out.key} {out.meter} ♩={out.tempo} · 난이도 {out.difficulty}")
    print(f"  검증 {out.validation['summary']} · 저장 가능 {out.savable}")
    print(f"  음악성 {out.musicality} · 종합 {out.combined_score}")
    print(f"  사전 심사 {'통과' if j.passed else '미달'} · 평균 {j.average} / 최저 {j.minimum} "
          f"(문턱 {j.required_average}·{j.required_minimum}) · 되먹임 {j.rounds}회")
    if j.consensus_fixes:
        print("  공통 지적: " + " / ".join(j.consensus_fixes))
    print(f"  걸린 시간 {secs:.1f}초 · 비용 {out.cost or '기록 없음'}")

    res = STORE.compositions[out.composition_id]
    d = Path(args.out) / f"{out.preset_id}-{out.composition_id}"
    d.mkdir(parents=True, exist_ok=True)
    (d / "score.musicxml").write_text(res.musicxml, encoding="utf-8")
    (d / "summary.json").write_text(
        json.dumps(out.model_dump(), ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"  → {d.relative_to(ROOT)}")
    return 0 if out.savable else 1


if __name__ == "__main__":
    raise SystemExit(main())
