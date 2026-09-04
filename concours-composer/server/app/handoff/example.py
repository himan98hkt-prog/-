"""의뢰서에 붙이는 **본보기** — 코드가 만들고, 코드가 검사하고, **요청을 따라간다**.

여기가 손으로 적힌 글이면 스키마가 바뀔 때 조용히 어긋난다. 실제로 그랬다:
의뢰서에 `plan.sections` · `motif.pitches` 같은, **실제로는 존재하지 않는 모양**을
적어 두었다. 그대로 작곡해 오면 프로그램이 못 읽고, 원장님은 좋은 곡을 들고도
"또 안 되네" 를 겪으신다. 그래서 본보기를 **모델로 지어서** 내놓는다.

**그리고 본보기는 요청을 따라가야 한다.** 이것을 한 번 더 틀렸다 — 본보기가 조성 A,
박자 4/4, 짜임새 "16분음표 달음질", 제목 "달음질" 로 **고정**되어 있었다. 왈츠(3/4)를
부탁해도 본보기는 4/4 토카타였다. 사람이든 모델이든 긴 글보다 **눈앞의 예시를 따라간다.**
원장님이 "성격을 바꿔도 비슷한 곡이 나온다" 고 하신 것의 남은 절반이 이것이다.

이제 본보기는 그 의뢰의 조성·박자·빠르기·마디 수·짜임새를 그대로 쓴다. 제목 자리는
비워 두어 베끼지 않게 한다.
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


def bar_length(meter: str) -> float:
    """한 마디가 몇 박인가(4분음표 = 1.0)."""
    from music21 import meter as m21meter

    try:
        return float(m21meter.TimeSignature(meter).barDuration.quarterLength)
    except Exception:
        return 4.0


def scale_of(key_name: str) -> list[str]:
    """그 조성의 음계를 으뜸음부터 — 본보기 음높이를 조성에 맞추려고.

    본보기가 다장조인데 의뢰는 가장조면, 작곡하는 쪽은 어느 쪽을 따라야 할지 헷갈린다.
    """
    from music21 import key as m21key

    from app.analysis.keyname import normalize_key

    k = m21key.Key(normalize_key(key_name))
    t = k.tonic.name
    return [str(p) for p in k.getPitches(f"{t}2", f"{t}6")]


def _durs(bar: float) -> tuple[list[float], list[float]]:
    """그 박자에서 **기보 가능한** 길이로 본보기 리듬을 만든다.

    4/4 → 0.5×4 + 2.0 · 3/4·6/8 → 0.5×4 + 1.0 · 2/4 → 0.25×4 + 1.0
    """
    rh = ([0.5, 0.5, 0.5, 0.5, bar - 2.0] if bar >= 3.0
          else [0.25, 0.25, 0.25, 0.25, bar - 1.0])
    return rh, [bar / 2, bar / 2]


def _bar(n: int, rh: list[tuple[float, list[str]]], lh: list[tuple[float, list[str]]],
         dyn: Dynamic | None = None) -> Measure:
    return Measure(
        number=n,
        rh=[Voice(events=[ScoreEvent(dur=d, pitches=p) for d, p in rh])],
        lh=[Voice(events=[ScoreEvent(dur=d, pitches=p) for d, p in lh])],
        dynamics=dyn,
    )


def example_motif(key: str = "C", meter: str = "4/4", tempo: int = 100) -> MotifCandidate:
    """모티브는 **음이름 목록이 아니라 마디 2~4개**다. 이것을 틀리면 통째로 못 읽는다."""
    sc = scale_of(key)
    bar = bar_length(meter)
    rd, ld = _durs(bar)
    # 으뜸음 위 한 옥타브 언저리에서 도는 다섯 음 — 조성이 바뀌면 음도 함께 바뀐다.
    hi = [sc[9], sc[11], sc[10], sc[9], sc[8]]
    lo = [sc[0], sc[2], sc[4]]
    lo2 = [sc[4], sc[6], sc[8]]
    return MotifCandidate(
        id="motif-1",
        measures=[
            _bar(1, list(zip(rd, [[p] for p in hi], strict=True)),
                 [(ld[0], lo), (ld[1], lo)], "mf"),
            _bar(2, list(zip(rd, [[p] for p in (sc[10], sc[12], sc[11], sc[10], sc[9])],
                             strict=True)),
                 [(ld[0], lo2), (ld[1], lo2)]),
        ],
        key=key,
        meter=meter,
        tempo=tempo,
        character_label="여기에 이 모티브의 성격을 한 줄로",
        why_it_works="여기에 왜 이 모티브가 이 곡에 맞는지",
    )


def example_plan(
    key: str = "C", meter: str = "4/4", tempo: int = 100,
    total: int = 48, difficulty: float = 5.0,
    texture_rh: str = "오른손 짜임새", texture_lh: str = "왼손 짜임새",
) -> CompositionPlan:
    bar = bar_length(meter)
    return CompositionPlan(
        title_candidates=["여기에 곡 제목", "다른 제목 후보"],
        key=key,
        meter=meter,
        tempo=tempo,
        total_measures=total,
        duration_est=round(total * bar * 60.0 / max(1, tempo), 1),
        form=[
            SectionPlan(label="A", measures=[1, total // 3], phrases=[
                PhrasePlan(measures=[1, total // 6], motif_treatment="statement",
                           texture_rh=texture_rh, texture_lh=texture_lh, dynamic="mf"),
                PhrasePlan(measures=[total // 6 + 1, total // 3],
                           motif_treatment="sequence_up_2nd",
                           texture_rh="여기서 오른손이 하는 일",
                           texture_lh="여기서 왼손이 하는 일", dynamic="f"),
            ]),
            SectionPlan(label="B", measures=[total // 3 + 1, total * 2 // 3], phrases=[
                PhrasePlan(measures=[total // 3 + 1, total * 2 // 3],
                           motif_treatment="texture_swap",
                           texture_rh="가운데에서 오른손이 하는 일",
                           texture_lh="가운데에서 왼손이 하는 일", dynamic="p"),
            ]),
            SectionPlan(label="A'", measures=[total * 2 // 3 + 1, total], phrases=[
                PhrasePlan(measures=[total * 2 // 3 + 1, total],
                           motif_treatment="octave_shift",
                           texture_rh="재현부에서 오른손이 하는 일",
                           texture_lh="재현부에서 왼손이 하는 일", dynamic="ff"),
            ]),
        ],
        harmony=[HarmonyStep(measure=1, roman="I"), HarmonyStep(measure=2, roman="V")],
        climax=Climax(measure=int(total * 0.7), how="클라이맥스에서 무슨 일이 일어나는가"),
        showcase_measures=[Showcase(range=[1, total // 6], strength_used="이 아이의 강점")],
        contrast_section={"label": "B", "how": "가운데에서 무엇이 달라지는가"},
        modulations=[f"{key} 안에서 어떻게 기우는가"],
        ending=Ending(type="완전정격종지", measures=[total - 3, total]),
        dynamics_curve=[DynamicPoint(measure=1, dyn="mf"),
                        DynamicPoint(measure=int(total * 0.7), dyn="ff")],
        pedal_plan="페달을 어디서 밟는가",
        difficulty_target=difficulty,
    )


def example_critic() -> CriticReport:
    return CriticReport(
        scores=RubricScores(
            motif_development=8, form_clarity=8, harmony=7, voice_leading=7, phrasing=8,
            climax_ending=8, student_fit=8, competition_effect=8, notation=9, originality=7,
        ),
        overall_comment="곡을 다 쓴 뒤, 심사위원의 눈으로 냉정하게 본 총평을 여기에 적습니다.",
    )


def example_json(
    key: str = "C", meter: str = "4/4", tempo: int = 100,
    total: int = 48, difficulty: float = 5.0,
    texture_rh: str = "오른손 짜임새", texture_lh: str = "왼손 짜임새",
) -> str:
    """의뢰서에 그대로 박히는 본보기. **마디는 예시로만** 보여 주고 나머지는 말로 줄인다."""
    plan = json.loads(example_plan(key, meter, tempo, total, difficulty,
                                   texture_rh, texture_lh).model_dump_json())
    motif = json.loads(example_motif(key, meter, tempo).model_dump_json())
    body = {
        "title": "여기에 곡 제목",
        "plan": plan,
        "motif": motif,
        "measures": [f"...여기에 마디 객체를 {total}개..."],
        "critic": json.loads(example_critic().model_dump_json()),
    }
    return json.dumps(body, ensure_ascii=False, indent=2)


def example_measure_json(key: str = "C", meter: str = "4/4") -> str:
    sc = scale_of(key)
    bar = bar_length(meter)
    rd, ld = _durs(bar)
    m = _bar(
        1,
        list(zip(rd, [[p] for p in (sc[9], sc[11], sc[10], sc[9], sc[8])], strict=True)),
        [(ld[0], [sc[0], sc[4]]), (ld[1], [sc[0], sc[4]])],
        "mf",
    )
    return json.dumps(json.loads(m.model_dump_json()), ensure_ascii=False, indent=2)
