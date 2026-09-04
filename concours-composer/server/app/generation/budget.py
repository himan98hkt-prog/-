"""작곡 한 곡에 **얼마를 쓸지 원장이 고른다**.

원장님이 중급 토카타를 만들다 곡당 상한($4)에 걸려 멈췄다. 프로그램 잘못이 아니라
정말로 그만큼 썼다 — 토카타는 이 프로그램이 만드는 곡 중 가장 비싸다. 16분음표가
쉬지 않고 달리므로 마디마다 음표가 많고, 음표는 곧 **출력 토큰**이고, 출력 토큰이
비용의 대부분이다. 게다가 지금까지는 가장 비싼 모델(Opus 5, 출력 100만 토큰당 $25)이
작곡과 심사를 **둘 다** 맡고 있었다.

그런데 그때 화면이 한 말은 ".env 의 MAX_COST_PER_COMPOSITION 을 올려라" 였다.
컴맹 원장에게 설정 파일을 열라는 것은 답이 아니고, 애초에 상한을 올리는 것은
"더 쓰라"는 말이지 "싸게 만들라"는 말이 아니다. 원장이 원한 것은 뒤쪽이다.

그래서 **비용을 고르는 손잡이**를 만든다. 손잡이는 네 개를 함께 움직인다.

    1. 작곡 모델   — 출력 단가가 곧 곡값이다. Opus $25 / Sonnet $10 / Haiku $5 (100만 토큰)
    2. 심사 모델   — 심사위원 3인이 악보 전체를 읽는다. 여기에 최고가 모델은 과하다.
    3. 고쳐 쓰는 횟수 — 한 라운드마다 프레이즈를 다시 작곡한다. 곧 한 곡값이 또 든다.
    4. 심사위원 수 — 세 사람이 각각 한 번씩 읽는다.

싸게 만든다고 규칙을 깎지는 않는다. 검증기·음악성 지표·표절 검사·다양성 검사는
**모든 등급에서 그대로** 돈다(절대 규칙 2). 달라지는 것은 '몇 번 더 다듬는가' 와
'누가 쓰는가' 뿐이다. 절약 등급의 곡도 검증기를 통과하지 못하면 저장되지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings, get_settings


@dataclass(frozen=True)
class Mode:
    """비용 등급 하나. 화면에 그대로 보여줄 수 있는 말로 적는다."""

    id: str
    name: str
    tagline: str
    composer_model: str
    judge_model: str
    revision_rounds: int
    judge_rounds: int
    judges: int
    cost_limit: float
    # 실측 전까지는 추정이다. 추정이라는 사실을 화면에서도 숨기지 않는다.
    typical_low: float
    typical_high: float
    detail: str


# 순서가 화면 순서다. 가운데(표준)가 기본값이다.
MODES: tuple[Mode, ...] = (
    Mode(
        id="saver",
        name="아껴 쓰기",
        tagline="한 곡에 커피 한 잔 값",
        composer_model="claude-sonnet-5",
        judge_model="claude-haiku-4-5",
        revision_rounds=0,
        judge_rounds=0,
        judges=1,
        cost_limit=1.50,
        typical_low=0.30,
        typical_high=0.90,
        detail=(
            "빠르고 쌉니다. 검증기와 지표는 그대로 돌지만 고쳐 쓰는 라운드가 없어서, "
            "심사 문턱에 못 미치는 초안이 나올 때가 있습니다. "
            "여러 성격을 훑어보며 마음에 드는 것을 찾을 때 쓰십시오."
        ),
    ),
    Mode(
        id="standard",
        name="표준",
        tagline="대부분의 곡은 이것으로 충분합니다",
        composer_model="claude-sonnet-5",
        judge_model="claude-sonnet-5",
        revision_rounds=1,
        judge_rounds=1,
        judges=3,
        cost_limit=3.00,
        typical_low=0.80,
        typical_high=2.20,
        detail=(
            "작곡은 Sonnet 이 하고, 심사위원 3인이 보고, 약한 곳을 한 번 고쳐 씁니다. "
            "학원에 파는 곡은 여기서 시작하시면 됩니다."
        ),
    ),
    Mode(
        id="best",
        name="최고 품질",
        tagline="콩쿨에 낼 그 한 곡",
        composer_model="claude-opus-5",
        judge_model="claude-opus-5",
        revision_rounds=2,
        judge_rounds=1,
        judges=3,
        cost_limit=6.00,
        typical_low=2.00,
        typical_high=5.00,
        detail=(
            "가장 좋은 모델이 작곡하고 심사하며, 약한 곳을 두 번까지 고쳐 씁니다. "
            "긴 곡(토카타·피날레·상급)은 여기서 $5 에 가까워질 수 있습니다. "
            "정말 낼 곡 하나에만 쓰십시오."
        ),
    ),
    Mode(
        id="finish",
        name="끝까지 만들기",
        tagline="상한 없이, 반드시 곡을 얻습니다",
        composer_model="claude-opus-5",
        judge_model="claude-sonnet-5",
        revision_rounds=1,
        judge_rounds=1,
        judges=3,
        # 0 = 상한 없음. 이 등급의 존재 이유가 이것 하나다.
        cost_limit=0.0,
        typical_low=2.00,
        typical_high=6.00,
        detail=(
            "**중간에 멈추지 않습니다.** 다른 등급은 정한 금액에 닿으면 거기서 멈추는데, "
            "토카타·피날레처럼 음표가 촘촘한 곡은 그 금액을 넘기 쉽습니다. "
            "'또 돈만 쓰고 곡을 못 얻는' 일을 겪고 싶지 않은 곡은 이것으로 만드십시오. "
            "대신 얼마가 나올지 미리 정해지지 않습니다 — 보통 $2~6 사이입니다."
        ),
    ),
)

# 원장이 직접 고르는 등급. 모델과 상한을 요청에서 받아 이 틀 위에 덮어쓴다.
CUSTOM = Mode(
    id="custom",
    name="직접 고르기",
    tagline="모델과 상한을 원장님이 정합니다",
    composer_model="claude-sonnet-5",
    judge_model="claude-sonnet-5",
    revision_rounds=1,
    judge_rounds=1,
    judges=3,
    cost_limit=0.0,          # 0 = 상한 없음. 넘더라도 끝까지 만든다.
    typical_low=0.0,
    typical_high=0.0,
    detail=(
        "작곡 모델과 곡당 상한을 직접 정합니다. 상한을 0 으로 두면 "
        "**넘더라도 끝까지 만듭니다** — 돈은 썼는데 곡은 못 얻는 일이 없습니다."
    ),
)

BY_ID: dict[str, Mode] = {m.id: m for m in (*MODES, CUSTOM)}
DEFAULT_MODE = "standard"

# 화면의 모델 목록. 출력 단가가 곧 곡값이므로 그 순서로 늘어놓는다.
# 값은 app/generation/client.py 의 PRICES 와 같은 출처(docs.claude.com)다.
PICKABLE_MODELS: tuple[dict[str, object], ...] = (
    {"id": "claude-haiku-4-5", "name": "Haiku 4.5", "note": "가장 쌉니다 · 짧은 곡·시안용",
     "out_price": 5.0, "relative": "가장 저렴"},
    {"id": "claude-sonnet-5", "name": "Sonnet 5", "note": "권장 · 품질과 값의 균형",
     "out_price": 10.0, "relative": "Opus 의 약 1/2.5"},
    {"id": "claude-opus-5", "name": "Opus 5", "note": "가장 좋습니다 · 콩쿨에 낼 곡",
     "out_price": 25.0, "relative": "가장 비쌈"},
)
PICKABLE_IDS = {str(m["id"]) for m in PICKABLE_MODELS}


def resolve(mode_id: str | None) -> Mode:
    """모르는 값이 와도 멈추지 않는다 — 기본 등급으로 돌아간다."""
    return BY_ID.get((mode_id or "").strip(), BY_ID[DEFAULT_MODE])


def custom_mode(model: str, cost_limit: float, revision_rounds: int, judges: int) -> Mode:
    """'직접 고르기' 를 원장이 넣은 값으로 채운다.

    모르는 모델 이름은 받지 않는다 — 오타 하나로 404 를 맞고 돈만 쓰는 일이 없도록,
    화면에 늘어놓은 목록 안에서만 고르게 한다.
    """
    picked = model if model in PICKABLE_IDS else CUSTOM.composer_model
    # 심사는 작곡보다 비쌀 이유가 없다. Opus 로 작곡하면 심사는 Sonnet 으로 충분하다.
    judge = "claude-sonnet-5" if picked == "claude-opus-5" else picked
    return Mode(
        id=CUSTOM.id,
        name=CUSTOM.name,
        tagline=CUSTOM.tagline,
        composer_model=picked,
        judge_model=judge,
        revision_rounds=max(0, min(2, revision_rounds)),
        judge_rounds=CUSTOM.judge_rounds,
        judges=max(1, min(3, judges)),
        cost_limit=max(0.0, cost_limit),
        typical_low=0.0,
        typical_high=0.0,
        detail=CUSTOM.detail,
    )


def settings_for(mode: Mode, base: Settings | None = None) -> Settings:
    """이 등급으로 곡을 만들 때 쓸 설정.

    `.env` 를 고치지 않는다. 이번 한 곡에만 적용되는 사본을 만들어 쓴다 —
    원장이 등급을 바꿔 가며 눌러도 서로 영향을 주지 않아야 한다.
    """
    s = base or get_settings()
    return s.model_copy(
        update={
            "composer_model": mode.composer_model,
            "judge_model": mode.judge_model,
            "max_cost_per_composition": mode.cost_limit,
            "max_revision_rounds": mode.revision_rounds,
            "judge_gate_rounds": mode.judge_rounds,
            "judge_count": mode.judges,
        }
    )


def as_dict(mode: Mode) -> dict[str, object]:
    """화면으로 보내는 모양. 원장이 고르는 데 필요한 것만 담는다."""
    return {
        "id": mode.id,
        "name": mode.name,
        "tagline": mode.tagline,
        "detail": mode.detail,
        "typical_low": mode.typical_low,
        "typical_high": mode.typical_high,
        "cost_limit": mode.cost_limit,
        "judges": mode.judges,
        "revision_rounds": mode.revision_rounds,
        "is_default": mode.id == DEFAULT_MODE,
        "composer_model": mode.composer_model,
    }
