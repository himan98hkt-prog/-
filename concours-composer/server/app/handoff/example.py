"""의뢰서에 붙이는 **본보기** — 코드가 만들고, 코드가 검사한다.

여기가 손으로 적힌 글이면 스키마가 바뀔 때 조용히 어긋난다. 실제로 그랬다:
의뢰서에 `plan.sections` · `motif.pitches` 같은, **실제로는 존재하지 않는 모양**을
적어 두었다. 그대로 작곡해 오면 프로그램이 못 읽고, 원장님은 좋은 곡을 들고도
"또 안 되네" 를 겪으신다. 곡을 못 만든 것보다 나쁜 실패다.

그래서 본보기를 **모델로 지어서** 내놓는다. 스키마가 바뀌면 이 파일이 먼저 터지고,
테스트가 그것을 잡는다. 의뢰서는 언제나 진짜 모양을 말한다.
"""
from __future__ import annotations

import json

from app.schemas.music import (
    Climax,
    CompositionPlan,
    Dynamic,
    DynamicPoint,
    Ending,
    HarmonyStep,
    Measure,
    MotifCandidate,
    PhrasePlan,
    ScoreEvent,
    SectionPlan,
    Showcase,
    Voice,
)
from app.schemas.quality import CriticReport, RubricScores


def _bar(n: int, rh: list[tuple[float, list[str]]], lh: list[tuple[float, list[str]]],
         dyn: Dynamic | None = None) -> Measure:
    return Measure(
        number=n,
        rh=[Voice(events=[ScoreEvent(dur=d, pitches=p) for d, p in rh])],
        lh=[Voice(events=[ScoreEvent(dur=d, pitches=p) for d, p in lh])],
        dynamics=dyn,
    )


def example_motif() -> MotifCandidate:
    """모티브는 **음이름 목록이 아니라 마디 2~4개**다. 이것을 틀리면 통째로 못 읽는다."""
    return MotifCandidate(
        id="motif-1",
        measures=[
            _bar(1, [(0.25, ["C#5"]), (0.25, ["E5"]), (0.25, ["D5"]), (0.25, ["C#5"]),
                     (0.25, ["B4"]), (0.25, ["C#5"]), (0.25, ["D5"]), (0.25, ["E5"]),
                     (1.0, ["A5"]), (1.0, ["G#5"])],
                 [(2.0, ["A2", "E3"]), (2.0, ["A2", "E3"])], "mf"),
            _bar(2, [(0.5, ["F#5"]), (0.5, ["E5"]), (1.0, ["D5"]), (2.0, ["C#5"])],
                 [(2.0, ["E2", "B2"]), (2.0, ["E2", "B2"])]),
        ],
        key="A",
        meter="4/4",
        tempo=112,
        character_label="돌다 솟는 얼굴 — 으뜸음을 비껴 돌다 4도로 뛴다",
        why_it_works="첫 네 음이 제자리를 맴돌아 귀에 남고, 다섯째 음에서 솟아 달음질이 시작된다",
    )


def example_plan() -> CompositionPlan:
    return CompositionPlan(
        title_candidates=["달음질", "구르는 바람"],
        key="A",
        meter="4/4",
        tempo=112,
        total_measures=48,
        duration_est=103.0,
        form=[
            SectionPlan(label="A", measures=[1, 16], phrases=[
                PhrasePlan(measures=[1, 8], motif_treatment="statement",
                           texture_rh="16분음표 달음질", texture_lh="2분음표 화음", dynamic="mf"),
                PhrasePlan(measures=[9, 16], motif_treatment="sequence_up_2nd",
                           texture_rh="분산화음", texture_lh="4분음표 걸음", dynamic="f"),
            ]),
            SectionPlan(label="B", measures=[17, 32], phrases=[
                PhrasePlan(measures=[17, 32], motif_treatment="texture_swap",
                           texture_rh="긴 음 선율", texture_lh="16분음표 반주", dynamic="p"),
            ]),
            SectionPlan(label="A'", measures=[33, 48], phrases=[
                PhrasePlan(measures=[33, 48], motif_treatment="octave_shift",
                           texture_rh="모티브 회귀", texture_lh="끊는 옥타브", dynamic="ff"),
            ]),
        ],
        harmony=[
            HarmonyStep(measure=1, roman="I", bass_note="A2"),
            HarmonyStep(measure=2, roman="V", bass_note="E2"),
        ],
        climax=Climax(measure=38, how="양손 교대 16분음표가 최고음까지 오르고 ff 로 터진다"),
        showcase_measures=[Showcase(range=[9, 16], strength_used="손가락 속도")],
        contrast_section={"label": "B", "how": "왼손이 16분음표를 맡고 오른손이 노래한다"},
        modulations=["A → f#단조(B단락) → A"],
        ending=Ending(type="완전정격종지", measures=[45, 48]),
        dynamics_curve=[DynamicPoint(measure=1, dyn="mf"), DynamicPoint(measure=38, dyn="ff")],
        pedal_plan="B단락과 코다에만. 달리는 구간은 밟지 않는다",
        difficulty_target=5.0,
    )


def example_critic() -> CriticReport:
    return CriticReport(
        scores=RubricScores(
            motif_development=8, form_clarity=8, harmony=7, voice_leading=7, phrasing=8,
            climax_ending=8, student_fit=8, competition_effect=8, notation=9, originality=7,
        ),
        overall_comment="곡을 다 쓴 뒤, 심사위원의 눈으로 냉정하게 본 총평을 여기에 적습니다.",
    )


def example_json() -> str:
    """의뢰서에 그대로 박히는 본보기. **마디는 두 개만** 보여 주고 나머지는 말로 줄인다."""
    plan = json.loads(example_plan().model_dump_json())
    motif = json.loads(example_motif().model_dump_json())
    body = {
        "title": "달음질",
        "plan": plan,
        "motif": motif,
        "measures": ["...여기에 마디 객체를 total_measures 개수만큼..."],
        "critic": json.loads(example_critic().model_dump_json()),
    }
    return json.dumps(body, ensure_ascii=False, indent=2)


def example_measure_json() -> str:
    m = _bar(
        1,
        [(0.25, ["C#5"]), (0.25, ["E5"]), (0.25, ["D5"]), (0.25, ["C#5"]),
         (0.25, ["B4"]), (0.25, ["C#5"]), (0.25, ["D5"]), (0.25, ["E5"]),
         (1.0, ["A5"]), (1.0, ["G#5"])],
        [(2.0, ["A2", "E3"]), (2.0, ["A2", "E3"])],
        "mf",
    )
    return json.dumps(json.loads(m.model_dump_json()), ensure_ascii=False, indent=2)
