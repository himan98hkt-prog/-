"""곡 사이 다양성 — 같은 학원이 형제 같은 곡을 여러 개 내보내는 것을 막는다.

음악성 지표(§7.4)도 비평 루브릭(§7.5)도 **곡 하나만** 본다. 그래서 다섯 곡을
따로 채점하면 전부 9점대인데 나란히 놓으면 형식이 같은 틀이라는 사실이 보이지
않는다. 실제로 g01·g02·g03 은 마지막 여섯 마디 화성이 `IV ii V7 vi V7 I` 로
글자 하나 다르지 않았다.

한 학원이 같은 콩쿨에 20곡을 내면 학생들이 형제 같은 곡을 친다. 그것은 곡
하나하나의 결함이 아니라 **곡 사이의 결함**이므로, 곡을 다 쓴 뒤가 아니라
설계(Plan) 단계에서 잡아야 싸다. 음표를 쓰기 전이기 때문이다.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.schemas.music import CompositionPlan

# 종지 공식을 몇 마디로 볼 것인가. 마지막 6마디면 '거짓 종지 → V7 → I' 같은
# 관용구가 통째로 들어온다.
CADENCE_TAIL = 6
# 모티브 처리열은 앞 네 개가 곡의 인상을 결정한다.
TREATMENT_HEAD = 4
# 이 이상 겹치면 '같은 틀' 로 본다.
SIMILARITY_LIMIT = 0.60


@dataclass(frozen=True)
class FormFingerprint:
    """설계도의 뼈대만 남긴 지문. 조성·템포는 뺀다 — 조만 바꾼 같은 곡도 잡아야 한다."""

    labels: tuple[str, ...]
    phrase_lengths: tuple[int, ...]
    treatments: tuple[str, ...]
    cadence: tuple[str, ...]
    climax_ratio: float

    @classmethod
    def of(cls, plan: CompositionPlan) -> FormFingerprint:
        phrases = plan.phrases()
        harmony = sorted(plan.harmony, key=lambda h: h.measure)
        return cls(
            labels=tuple(s.label for s in plan.form),
            phrase_lengths=tuple(p.measures[1] - p.measures[0] + 1 for p in phrases),
            treatments=tuple(p.motif_treatment for p in phrases),
            cadence=tuple(h.roman for h in harmony[-CADENCE_TAIL:]),
            climax_ratio=round(plan.climax.measure / max(1, plan.total_measures), 2),
        )


# 어느 축이 겹칠 때 얼마나 '같은 곡' 인가.
#   종지가 가장 무겁다 — 마지막 여섯 마디는 심사위원이 마지막으로 듣는 것이다.
#   형식 라벨은 가장 가볍다 — ABA' 는 이 나이대 소품의 표준이라 겹치는 게 정상이다.
WEIGHTS = {
    "cadence": 0.30,
    "phrase_lengths": 0.25,
    "treatments": 0.20,
    "climax": 0.15,
    "labels": 0.10,
}


def _head_match(a: Sequence[object], b: Sequence[object], n: int) -> bool:
    return bool(a[:n]) and list(a[:n]) == list(b[:n])


def compare(a: FormFingerprint, b: FormFingerprint) -> tuple[float, list[str]]:
    """0~1 유사도와 겹친 축 이름들."""
    shared: list[str] = []
    score = 0.0
    if a.cadence and a.cadence == b.cadence:
        score += WEIGHTS["cadence"]
        shared.append("종지 공식")
    if a.phrase_lengths == b.phrase_lengths:
        score += WEIGHTS["phrase_lengths"]
        shared.append("프레이즈 길이열")
    elif _head_match(a.phrase_lengths, b.phrase_lengths, 6):
        score += WEIGHTS["phrase_lengths"] * 0.5
        shared.append("프레이즈 길이 앞 6개")
    if _head_match(a.treatments, b.treatments, TREATMENT_HEAD):
        score += WEIGHTS["treatments"]
        shared.append(f"모티브 처리 앞 {TREATMENT_HEAD}개")
    if abs(a.climax_ratio - b.climax_ratio) <= 0.05:
        score += WEIGHTS["climax"]
        shared.append("클라이맥스 위치")
    if a.labels == b.labels:
        score += WEIGHTS["labels"]
        shared.append("형식 라벨")
    return round(score, 4), shared


@dataclass(frozen=True)
class Collision:
    other_id: str
    similarity: float
    shared: list[str]


def collisions(
    plan: CompositionPlan,
    previous: Sequence[tuple[str, CompositionPlan]],
    limit: float = SIMILARITY_LIMIT,
) -> list[Collision]:
    """이미 만든 곡들과 얼마나 같은 틀인가. 높은 순으로."""
    me = FormFingerprint.of(plan)
    out: list[Collision] = []
    for other_id, other in previous:
        sim, shared = compare(me, FormFingerprint.of(other))
        if sim >= limit:
            out.append(Collision(other_id, sim, shared))
    return sorted(out, key=lambda c: c.similarity, reverse=True)


def suggest(shared: Sequence[str]) -> str:
    """무엇을 바꾸면 되는지 — 작곡가가 그대로 실행할 수 있게."""
    tips = {
        "종지 공식": "마지막 여섯 마디 화성을 바꿔라(거짓 종지 대신 피카르디 3도, "
                     "이끔음 없는 종지, 아래로 내려가는 베이스 중 하나)",
        "프레이즈 길이열": "분절과 확장을 다른 자리에 놓아라 — 예: 전개부를 2+2+4 로 뒤집거나 "
                           "제시부에 6마디 확장을 넣어라",
        f"모티브 처리 앞 {TREATMENT_HEAD}개": "두 번째 프레이즈를 repeat 말고 inversion 이나 "
                                              "augmentation 으로 시작하라",
        "클라이맥스 위치": "클라이맥스를 60~80% 대역의 반대편 끝으로 옮겨라",
        "형식 라벨": "ABA' 대신 ABAC 나 AABA 를 써 보라",
    }
    return " / ".join(tips.get(s, s) for s in shared)


# ── 음색 팔레트(조성·박자) ───────────────────────────────────────────────────
#
# 형식 지문에는 조성을 **일부러** 넣지 않았다 — 넣으면 조만 바꾼 같은 곡이 검사를
# 빠져나간다. 하지만 같은 콩쿨 같은 부문에 다장조 소품이 연달아 세 곡 나가는 것도
# 학원 입장에서는 문제다. 그래서 형식과 별개의 **소프트** 신호로 따로 본다.

PALETTE_WINDOW = 6        # 최근 몇 곡을 보는가
PALETTE_LIMIT = 2         # 그 안에 같은 조성이 몇 번까지면 봐줄 것인가


def palette_repeats(
    plan: CompositionPlan,
    previous: Sequence[tuple[str, CompositionPlan]],
    *,
    window: int = PALETTE_WINDOW,
    limit: int = PALETTE_LIMIT,
) -> str | None:
    """최근 곡들과 조성·박자가 얼마나 겹치는가. 겹치면 한 줄로 알려 준다(하드 실패 아님)."""
    recent = list(previous)[-window:]
    if not recent:
        return None
    same_key = [i for i, p in recent if p.key == plan.key]
    same_both = [i for i, p in recent if p.key == plan.key and p.meter == plan.meter]
    if len(same_key) < limit:
        return None
    who = ", ".join(same_both or same_key)
    what = f"{plan.key} {plan.meter}" if same_both else plan.key
    return (
        f"최근 {len(recent)}곡 중 {len(same_both or same_key)}곡이 이미 {what} 다({who}). "
        "형식은 달라도 같은 부문에 같은 색이 연달아 나가면 심사위원 귀에는 비슷하게 들린다 — "
        "나란한조·딸림조로 옮기거나 박자를 바꾸는 것을 검토하라."
    )
