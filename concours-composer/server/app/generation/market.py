"""학원에 팔 **대중 콩쿨곡** — 한 아이가 아니라 그 급수의 아이들 전부를 위한 곡.

맞춤곡과 목적이 다르다. 맞춤곡은 우리 학원 민준이의 손 크기·강점·약점에 딱 맞춘다.
파는 곡은 **얼굴을 모르는 아이들**이 친다. 학원 원장이 사서 자기 학생 여럿에게 쓰고,
그중 누구 하나라도 "우리 애 손엔 안 닿는다" 가 되면 그 곡은 팔리지 않는다.

그래서 기준이 뒤집힌다.

    맞춤곡   — 이 아이가 **할 수 있는 최대**를 쓴다. 강점을 드러내는 것이 목표다.
    대중곡   — 그 급수 아이들이 **모두 할 수 있는 선**을 쓴다. 안 되는 아이가 없어야 한다.

구체적으로 셋을 낮춰 잡는다.
1. **손 크기** — 그 나이대의 가운데가 아니라 **작은 쪽**에 맞춘다. 손이 큰 아이는 작은 곡을
   칠 수 있지만, 손이 작은 아이는 큰 곡을 못 친다. 한 방향으로만 실패한다.
2. **빠르기** — 무대에서 흔들리지 않는 선. 학원에서 두 달 연습해 콩쿨에 올리는 곡이다.
3. **악보 읽기** — 임시표를 적게. 못 읽으면 못 친다.

강점·약점은 비운다. 특정 아이에게 치우친 곡은 다른 아이에게 안 맞는다.

여기 숫자는 골든 20곡과 프리셋의 레벨 대역에서 잡았다. 새 급수를 넣거나 값을 바꿀 때는
"이 급수의 **가장 작은 손**이 칠 수 있는가" 를 기준으로 판단하라.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.generation.presets import Preset, suitable
from app.schemas.student import CompetitionProfile, HandSpan, Student

# 심사에서 안전한 성격들.
#
# 콩쿨 심사표는 형식이 뚜렷하고 클라이맥스가 분명한 곡에 후하다. 실험적인 성격은
# 잘 맞으면 크게 먹히지만 어긋나면 크게 깎인다 — 팔 곡은 그 도박을 하지 않는다.
# 이 차례대로 권한다.
SAFE_FIRST: tuple[str, ...] = ("march", "waltz", "sonatina", "dance", "singing", "study")


@dataclass(frozen=True)
class Tier:
    """파는 급수 하나. 원장이 고르는 단위다."""

    id: str
    name: str          # 화면에 보이는 이름
    who: str           # 누가 치는 곡인지 — 원장이 이것만 보고 고른다
    level: int         # 목표 난이도의 기준
    span: int          # 이 급수에서 **작은 쪽** 손이 닿는 음정(도)
    tempo: int         # 무대에서 흔들리지 않는 상한
    reading: int       # 악보 읽기
    limit_sec: int     # 부문의 흔한 연주 시간 제한


TIERS: tuple[Tier, ...] = (
    Tier("beginner", "초급", "피아노 1~2년 · 초등 저학년",
         level=3, span=6, tempo=104, reading=4, limit_sec=120),
    Tier("lower", "초중급", "체르니 100 무렵 · 초등 중학년",
         level=4, span=6, tempo=112, reading=5, limit_sec=150),
    Tier("middle", "중급", "체르니 30 무렵 · 초등 고학년",
         level=5, span=7, tempo=120, reading=6, limit_sec=150),
    Tier("upper", "중상급", "체르니 40 무렵 · 초등 고학년~중학생",
         level=6, span=8, tempo=132, reading=7, limit_sec=180),
    Tier("advanced", "상급", "소나타를 치는 학생 · 중학생 이상",
         level=7, span=8, tempo=144, reading=8, limit_sec=180),
)

BY_TIER = {t.id: t for t in TIERS}


def standard_student(tier: Tier) -> Student:
    """그 급수의 **가장 작은 손**을 기준으로 세운 표준 학생.

    이름은 사람 이름이 아니다 — 이 곡은 누구의 것도 아니고, 악보 표지에도 학생 이름이
    나가지 않는다(파는 곡이므로 연주자 자리는 비워 둔다).
    """
    return Student(
        id=f"market-{tier.id}",
        name=f"{tier.name} 표준",
        grade=tier.name,
        years_of_study=0,
        hand_span=HandSpan(max_interval=tier.span),
        level=tier.level,
        repertoire_done=[],
        # 비워 둔다. 특정 아이의 강점에 기댄 곡은 다른 아이에게 안 맞는다.
        strengths=[],
        weaknesses=[],
        tempo_comfort_max_bpm=tier.tempo,
        reading_level=tier.reading,
        # 음역도 넉넉히 좁힌다 — 작은 피아노·전자피아노에서도 다 나오게.
        lowest_midi=36,
        highest_midi=93,
        notes="학원 판매용 대중 콩쿨곡. 이 급수의 작은 손을 기준으로 한다.",
    )


def standard_competition(tier: Tier) -> CompetitionProfile:
    """부문의 흔한 규정. 특정 대회가 아니라 **여러 대회에 낼 수 있는** 공통분모다."""
    return CompetitionProfile(
        id=f"market-{tier.id}",
        name="일반 콩쿨",
        division=tier.name,
        time_limit_sec=tier.limit_sec,
        original_allowed=True,
        criteria_text="형식·표현·정확도를 고루 본다",
    )


def recommended_presets(tier: Tier) -> list[Preset]:
    """이 급수에 권할 성격 — 심사에서 안전한 것을 앞으로.

    맞춤곡과 달리 약점으로 걸러 낼 것이 없다(표준 학생은 약점을 비워 두었다).
    대신 심사에서 잘 먹히는 순서로 세운다.
    """
    fits = suitable(tier.level)
    order = {pid: i for i, pid in enumerate(SAFE_FIRST)}
    return sorted(fits, key=lambda p: (order.get(p.id, len(SAFE_FIRST)), p.id))
