"""§7.4 음악성 지표 — 지표가 실제로 '이상한 곡'을 구별하는지."""
from __future__ import annotations

from app.analysis.musicality import (
    WEIGHTS,
    evaluate,
    motif_consistency,
    phrase_balance,
    repetition_balance,
    texture_contrast,
)
from app.schemas.music import (
    Climax,
    CompositionPlan,
    DynamicPoint,
    Ending,
    HarmonyStep,
    Measure,
    MotifCandidate,
    PhrasePlan,
    ScoreEvent,
    SectionPlan,
    Voice,
)
from helpers import simple_measure


def test_weights_sum_to_one():
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-6


def _motif() -> MotifCandidate:
    return MotifCandidate(
        id="m", key="C", meter="4/4", tempo=100, character_label="테스트",
        measures=[
            Measure(number=1, rh=[Voice(events=[
                ScoreEvent(dur=1, pitches=["C5"]),
                ScoreEvent(dur=1, pitches=["D5"]),
                ScoreEvent(dur=1, pitches=["E5"]),
                ScoreEvent(dur=1, pitches=["G5"]),
            ])]),
            Measure(number=2, rh=[Voice(events=[ScoreEvent(dur=4, pitches=["E5"])])]),
        ],
    )


def _plan(total: int = 8) -> CompositionPlan:
    return CompositionPlan(
        key="C", meter="4/4", tempo=100, total_measures=total, duration_est=total * 2.4,
        form=[
            SectionPlan(label="A", measures=[1, 4], phrases=[
                PhrasePlan(measures=[1, 4], motif_treatment="statement",
                           texture_rh="선율", texture_lh="분산화음", dynamic="mf")]),
            SectionPlan(label="B", measures=[5, total], phrases=[
                PhrasePlan(measures=[5, total], motif_treatment="inversion",
                           texture_rh="선율", texture_lh="지속 화음", dynamic="p")]),
        ],
        harmony=[HarmonyStep(measure=i, roman="I") for i in range(1, total + 1)],
        climax=Climax(measure=int(total * 0.7), how="최고음"),
        ending=Ending(type="완전종지", measures=[total - 1, total]),
        dynamics_curve=[DynamicPoint(measure=1, dyn="mf"), DynamicPoint(measure=5, dyn="p")],
        difficulty_target=4.0,
    )


def test_motif_consistency_detects_a_piece_that_forgets_its_motif():
    motif = _motif()
    plan = _plan()
    # 모티브(상행 순차 + 도약)를 그대로 쓴 곡
    faithful = [simple_measure(i, ["C5", "D5", "E5", "G5"], ["C3"]) for i in range(1, 9)]
    # 모티브와 무관한 하행 반음계
    unrelated = [simple_measure(i, ["B5", "B-5", "A5", "A-5"], ["C3"]) for i in range(1, 9)]

    hi = motif_consistency(faithful, motif, plan).value
    lo = motif_consistency(unrelated, motif, plan).value
    assert hi > lo, f"모티브를 지킨 곡({hi})이 무관한 곡({lo})보다 높아야 한다"
    assert hi >= 0.7


def test_motif_consistency_accepts_inversion_and_retrograde():
    """전위·역행으로 전개한 프레이즈도 '모티브가 살아 있다' 로 세야 한다."""
    from app.analysis.pitch import midi_to_pitch

    motif = _motif()
    plan = _plan(8)
    head = motif.head_intervals()          # 모티브 머리 음정열

    def line_from(intervals: list[int], start: int = 79) -> list[Measure]:
        """주어진 음정열을 그대로 따라가는 선율을 4마디로 만든다."""
        pitches = [start]
        while len(pitches) < 33:
            for iv in intervals:
                pitches.append(pitches[-1] + iv)
        names = [midi_to_pitch(p) for p in pitches]
        return [
            simple_measure(i, names[(i - 1) * 4 : (i - 1) * 4 + 4], ["C3"])
            for i in range(1, 9)
        ]

    inverted = line_from([-i for i in head])
    retrograde = line_from(head[::-1])
    assert motif_consistency(inverted, motif, plan).value > 0
    assert motif_consistency(retrograde, motif, plan).value > 0


def test_repetition_balance_punishes_both_extremes():
    identical = [simple_measure(i, ["C5", "D5", "E5", "G5"], ["C3"]) for i in range(1, 9)]
    tops = ["C5", "D5", "E5", "F5", "G5", "A5", "B5", "C6"]
    all_different = [simple_measure(i, [tops[i - 1], "D5", "E5", "G5"], ["C3"]) for i in range(1, 9)]
    assert repetition_balance(identical).value < 0.5     # 전부 같은 마디 = 지루함
    assert repetition_balance(all_different).value < 1.0  # 반복이 전혀 없음 = 산만함


def test_phrase_balance_wants_breath_at_phrase_ends():
    plan = _plan(8)
    no_breath = [simple_measure(i, ["C5", "D5", "E5", "G5"], ["C3"]) for i in range(1, 9)]
    with_breath = list(no_breath)
    for end in (4, 8):
        with_breath[end - 1] = Measure(
            number=end,
            rh=[Voice(events=[ScoreEvent(dur=4, pitches=["C5"])])],
            lh=[Voice(events=[ScoreEvent(dur=4, pitches=["C3"])])],
        )
    assert phrase_balance(with_breath, plan).value > phrase_balance(no_breath, plan).value
    assert phrase_balance(with_breath, plan).value == 1.0


def test_texture_contrast_detects_unchanged_left_hand():
    plan = _plan(8)
    same_lh = [simple_measure(i, ["C5", "D5", "E5", "G5"], ["C3", "G3", "E3", "G3"])
               for i in range(1, 9)]
    changed = list(same_lh[:4])
    changed += [
        Measure(
            number=i,
            rh=[Voice(events=[ScoreEvent(dur=1, pitches=[p]) for p in ["C5", "D5", "E5", "G5"]])],
            lh=[Voice(events=[ScoreEvent(dur=4, pitches=["C2", "G2"])])],
        )
        for i in range(5, 9)
    ]
    assert texture_contrast(changed, plan).value > texture_contrast(same_lh, plan).value


def test_full_evaluation_scores_a_good_piece_above_a_bad_one():
    motif = _motif()
    plan = _plan(8)
    good = [simple_measure(i, ["C5", "D5", "E5", "G5"], ["C3", "G3", "E3", "G3"])
            for i in range(1, 5)]
    good += [
        Measure(
            number=i,
            rh=[Voice(events=[ScoreEvent(dur=1, pitches=[p]) for p in ["C5", "D5", "E5", "G5"]])],
            lh=[Voice(events=[ScoreEvent(dur=4, pitches=["C2", "G2"])])],
            dynamics="p" if i == 5 else None,
        )
        for i in range(5, 9)
    ]
    good[0] = good[0].model_copy(update={"dynamics": "mf"})
    for end in (4, 8):
        good[end - 1] = Measure(
            number=end,
            rh=[Voice(events=[ScoreEvent(dur=4, pitches=["E5"])])],
            lh=[Voice(events=[ScoreEvent(dur=4, pitches=["C3"])])],
        )
    bad = [simple_measure(i, ["B5", "B-5", "A5", "A-5"], ["B3"]) for i in range(1, 9)]

    g = evaluate(good, motif=motif, plan=plan).score
    b = evaluate(bad, motif=motif, plan=plan).score
    assert g > b, f"좋은 곡 {g} vs 나쁜 곡 {b}"


def test_playability_measures_each_hand_separately():
    """두 손을 이어 붙여 세면 오른손→왼손 건너뛰기가 매 마디 거대한 '이동' 으로 잡힌다.

    아래 곡은 양손 모두 제자리에서 순차로만 움직인다 — 연주가 어려울 이유가 없다.
    """
    from app.analysis.musicality import playability

    calm = [
        Measure(
            number=i,
            rh=[Voice(events=[ScoreEvent(dur=1, pitches=[p]) for p in ["C5", "D5", "E5", "D5"]])],
            lh=[Voice(events=[ScoreEvent(dur=1, pitches=[p]) for p in ["C3", "D3", "E3", "D3"]])],
        )
        for i in range(1, 9)
    ]
    m = playability(calm, max_span_semitones=12)
    assert m.met, m.detail
    # 손마다 순차 이동이므로 평균 이동은 2반음 근처여야 한다.
    assert "평균 이동 1" not in m.detail or "평균 이동 1." in m.detail


# ── 표현 다양성 (§7.4 추가 지표) ─────────────────────────────────────────────


def _bland_piece(n: int = 16):
    """4분음표만, 6도 안, 다이내믹 하나 — 문법은 맞지만 심심한 곡."""
    from app.schemas.music import Measure, ScoreEvent, Voice

    return [
        Measure(
            number=i + 1,
            rh=[Voice(events=[ScoreEvent(dur=1.0, pitches=[p]) for p in ("C5", "D5", "E5", "C5")])],
            lh=[Voice(events=[ScoreEvent(dur=4.0, pitches=["C3"])])],
            dynamics="mf" if i == 0 else None,
        )
        for i in range(n)
    ]


def _varied_piece(n: int = 16):
    from app.schemas.music import Measure, ScoreEvent, Voice

    shapes = [
        [(0.5, "C5"), (0.5, "E5"), (1.0, "G5"), (2.0, "F5")],
        [(1.5, "A5"), (0.5, "G5"), (2.0, "E5")],
        [(0.25, "C5"), (0.25, "D5"), (0.5, "E5"), (1.0, "G5"), (2.0, "C6")],
        [(4.0, "G4")],
    ]
    out = []
    for i in range(n):
        shape = shapes[i % len(shapes)]
        out.append(
            Measure(
                number=i + 1,
                rh=[Voice(events=[
                    ScoreEvent(dur=d, pitches=[p], artic="staccato" if i % 4 == 2 else "none")
                    for d, p in shape
                ])],
                lh=[Voice(events=[ScoreEvent(dur=4.0, pitches=["C3", "G3"])])],
                dynamics=["p", "mf", "f", "mp"][i % 4] if i % 4 == 0 or i == 8 else None,
            )
        )
    return out


def test_expressive_variety_catches_bland_piece() -> None:
    from app.analysis.musicality import expressive_variety

    m = expressive_variety(_bland_piece(), difficulty_target=2.0)
    assert not m.met, m.detail
    assert m.value < 0.4, m.detail
    assert "같은 리듬형 100%" in m.detail


def test_expressive_variety_passes_varied_piece() -> None:
    from app.analysis.musicality import expressive_variety

    m = expressive_variety(_varied_piece(), difficulty_target=4.0)
    assert m.met, m.detail


def test_expressive_variety_is_relative_to_difficulty() -> None:
    """같은 곡이라도 유치부 목표면 덜 요구한다 — 쉬운 곡에 16분음표를 강요하지 않는다."""
    from app.analysis.musicality import expressive_variety

    piece = _bland_piece()
    easy = expressive_variety(piece, difficulty_target=1.0).value
    hard = expressive_variety(piece, difficulty_target=9.0).value
    assert easy > hard


def test_musicality_weights_sum_to_one() -> None:
    from app.analysis.musicality import TARGETS, WEIGHTS

    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-6
    assert set(WEIGHTS) == set(TARGETS)


def test_describe_texture_reports_what_the_score_actually_does() -> None:
    """설계도가 '스트라이드' 라고 적혀 있어도, 온음표로 쓴 왼손은 온음표로 보고돼야 한다.

    비평가가 Plan 의 문장만 믿고 실제 악보에 없는 것을 지적한 일이 있었다.
    """
    from app.analysis.musicality import describe_texture

    plan = _plan(8)
    plan.form[0].phrases[0].texture_lh = "왼손 10도 스트라이드"
    plan.form[1].phrases[0].texture_lh = "왼손 10도 스트라이드"
    ms = [
        Measure(number=i,
                rh=[Voice(events=[ScoreEvent(dur=1, pitches=["C5"]) for _ in range(4)])],
                lh=[Voice(events=[ScoreEvent(dur=4, pitches=["C3", "G3", "C4"])])])
        for i in range(1, 9)
    ]
    rows = describe_texture(ms, plan)
    assert len(rows) == 2
    lh = rows[0]["왼손"]
    assert lh["평균음길이"] == 4.0
    assert "스트라이드" not in str(lh["모양"]), lh
    assert lh["동시음"] == 3.0


def test_describe_texture_names_a_real_stride() -> None:
    from app.analysis.musicality import describe_texture

    def bar(n: int) -> Measure:
        ev = []
        for _ in range(4):
            ev.append(ScoreEvent(dur=0.5, pitches=["C2"]))
            ev.append(ScoreEvent(dur=0.5, pitches=["C3", "E3", "G3"]))
        return Measure(number=n,
                       rh=[Voice(events=[ScoreEvent(dur=4, pitches=["C5"])])],
                       lh=[Voice(events=ev)])

    rows = describe_texture([bar(i) for i in range(1, 9)], _plan(8))
    assert "스트라이드" in str(rows[0]["왼손"]["모양"]), rows[0]


def test_texture_contrast_notices_a_right_hand_change() -> None:
    """왼손이 그대로여도 오른손이 홑음에서 4음 화음으로 두꺼워지면 텍스처가 바뀐 것이다."""
    plan = _plan(8)
    lh = [ScoreEvent(dur=2, pitches=["C3", "G3"]), ScoreEvent(dur=2, pitches=["C3", "G3"])]
    thin = [Measure(number=i,
                    rh=[Voice(events=[ScoreEvent(dur=1, pitches=["C5"]) for _ in range(4)])],
                    lh=[Voice(events=list(lh))]) for i in range(1, 5)]
    thick = [Measure(number=i,
                     rh=[Voice(events=[ScoreEvent(dur=1, pitches=["C5", "E5", "G5", "C6"])
                                       for _ in range(4)])],
                     lh=[Voice(events=list(lh))]) for i in range(5, 9)]
    m = texture_contrast(thin + thick, plan)
    assert m.value == 1.0, m.detail
    assert "오른손" in m.detail


def test_motif_consistency_names_the_phrases_that_lost_the_motif() -> None:
    motif = _motif()
    plan = _plan(8)
    ms = [simple_measure(i, ["C5", "D5", "E5", "G5"], ["C3"]) for i in range(1, 5)]
    ms += [simple_measure(i, ["B5", "B-5", "A5", "A-5"], ["C3"]) for i in range(5, 9)]
    m = motif_consistency(ms, motif, plan)
    assert "없는 곳" in m.detail and "5-8" in m.detail, m.detail
