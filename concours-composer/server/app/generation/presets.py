"""컨셉·테마 프리셋 — 대시보드에서 버튼 하나로 곡을 시작하기 위한 재료.

원장이 매번 mood·form·박자·템포·텍스처를 손으로 채우는 것은 실수가 나기 쉽고,
무엇보다 **무엇을 골라야 하는지 모른다**. 콩쿨 무대에서 실제로 통하는 성격 12가지를
미리 묶어 두고, 학생의 수준·강점에 맞는 것만 추려 보여 준다.

프리셋은 **요청의 초안**이지 결정이 아니다. 원장이 어느 값이든 덮어쓸 수 있고,
난이도·조성은 학생에 맞춰 프리셋 위에서 다시 계산된다.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Form = Literal["AB", "ABA", "rondo", "sonatina", "variations"]


@dataclass(frozen=True)
class Preset:
    id: str
    name: str
    blurb: str                       # 원장에게 보이는 한 줄
    mood: str                        # 작곡 프롬프트로 들어가는 성격
    form: Form
    meter: str
    tempo: tuple[int, int]           # 권장 템포 대역
    texture_options: list[str]
    keys: list[str]                  # 이 성격에 잘 맞는 조성 후보(난이도에 따라 고른다)
    level_range: tuple[int, int]     # 이 성격이 살아나는 학생 레벨 대역
    shows_off: list[str] = field(default_factory=list)   # 드러나는 강점
    avoid_if: list[str] = field(default_factory=list)    # 이 약점이면 권하지 않는다

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# 난이도가 높을수록 조표가 많은 쪽을 고른다 — 난이도 모델에서 조표는 고정 특징이고,
# 곡을 다 쓴 뒤에는 바꿀 수 없다(difficulty.key_signature_advice 참고).
PRESETS: list[Preset] = [
    Preset(
        id="march", name="행진곡", blurb="또렷한 박과 점음표. 무대에서 가장 안전한 첫 곡",
        mood="씩씩한 행진 — 또렷한 박, 점음표, 짧은 스타카토", form="ABA", meter="4/4",
        tempo=(88, 120), texture_options=["단음 선율 + 화음 반주", "왼손 행진 베이스"],
        keys=["C", "G", "F", "D", "B-"], level_range=(1, 6),
        shows_off=["리듬감", "타건"], avoid_if=["레가토"],
    ),
    Preset(
        id="waltz", name="왈츠", blurb="3박의 흔들림. 왼손 도-화음-화음이 손을 가르친다",
        mood="우아하게 흔들리는 왈츠", form="ABA", meter="3/4",
        tempo=(66, 152), texture_options=["왼손 왈츠 반주", "오른손 노래하는 선율"],
        keys=["F", "B-", "E-", "A-", "D-"], level_range=(2, 8),
        shows_off=["표현력", "레가토"], avoid_if=["박자감"],
    ),
    Preset(
        id="lyric", name="노래하는 소품", blurb="느리고 긴 호흡. 표현력이 강점인 학생용",
        mood="서정적이고 노래하는 — 긴 호흡, 넓은 다이내믹", form="ABA", meter="4/4",
        tempo=(56, 84), texture_options=["오른손 선율 + 왼손 분산화음", "페달 지속"],
        keys=["F", "B-", "E-", "A-", "D-"], level_range=(2, 9),
        shows_off=["표현력", "레가토", "음색"], avoid_if=["손가락 속도"],
    ),
    Preset(
        id="toccata", name="토카타", blurb="쉬지 않고 달리는 16분음표. 손가락이 강점일 때",
        mood="쉬지 않고 달리는 — 16분음표 연속, 양손 교대", form="ABA", meter="4/4",
        tempo=(112, 152), texture_options=["양손 교대 음형", "반복음"],
        keys=["C", "A", "E", "B", "F#"], level_range=(5, 10),
        shows_off=["손가락 속도", "화려한 스케일", "지구력"], avoid_if=["지구력", "집중력"],
    ),
    Preset(
        id="variations", name="주제와 변주", blurb="한 주제가 네 얼굴로. 형식을 배우기 좋다",
        mood="한 주제를 리듬·텍스처·음가로 바꿔 가는 변주", form="variations", meter="4/4",
        tempo=(80, 116), texture_options=["주제 단순 화음", "변주마다 텍스처 교체"],
        keys=["C", "G", "D", "A", "E"], level_range=(3, 9),
        shows_off=["형식 이해", "다양한 터치"], avoid_if=["암보"],
    ),
    Preset(
        id="sonatina", name="소나티네 1악장", blurb="제시–전개–재현. 심사위원이 형식을 본다",
        mood="고전적인 소나티네 1악장 — 두 주제의 대비", form="sonatina", meter="4/4",
        tempo=(96, 132), texture_options=["알베르티 베이스", "옥타브 저음"],
        keys=["C", "G", "D", "A", "E"], level_range=(4, 9),
        shows_off=["형식 이해", "고전 터치"], avoid_if=["집중력"],
    ),
    Preset(
        id="rondo", name="론도", blurb="돌아오는 후렴. 집중력이 약한 학생에게 유리",
        mood="경쾌하게 돌아오는 론도 — 후렴이 세 번 온다", form="rondo", meter="2/4",
        tempo=(100, 138), texture_options=["가벼운 스타카토", "짧은 에피소드"],
        keys=["C", "G", "D", "F", "B-"], level_range=(2, 8),
        shows_off=["리듬감", "명료한 터치"], avoid_if=[],
    ),
    Preset(
        id="nocturne", name="야상곡풍", blurb="왼손 넓은 분산화음 위의 노래. 페달을 배운 뒤",
        mood="밤의 노래 — 왼손 넓은 분산화음, 오른손 장식", form="ABA", meter="6/8",
        tempo=(50, 76), texture_options=["왼손 넓은 분산화음", "오른손 장식음"],
        keys=["E-", "A-", "D-", "B", "F#"], level_range=(5, 10),
        shows_off=["페달", "음색", "표현력"], avoid_if=["손 크기"],
    ),
    Preset(
        id="dance", name="춤곡", blurb="민속 춤의 걸음. 리듬 하나로 곡이 선다",
        mood="민속 춤 — 또렷한 리듬형이 곡 전체를 끌고 간다", form="ABA", meter="3/4",
        tempo=(104, 144), texture_options=["리듬 오스티나토", "손 교차"],
        keys=["G", "D", "A", "E", "B"], level_range=(3, 9),
        shows_off=["리듬감", "악센트"], avoid_if=[],
    ),
    Preset(
        id="etude", name="연습곡풍 소품", blurb="한 가지 기교만 판다. 약점을 무대에서 강점으로",
        mood="한 가지 음형을 끝까지 미는 연습곡풍", form="AB", meter="4/4",
        tempo=(96, 138), texture_options=["같은 음형 반복", "음역 이동"],
        keys=["C", "G", "F", "D", "A"], level_range=(3, 9),
        shows_off=["손가락 독립", "지구력"], avoid_if=["집중력"],
    ),
    Preset(
        id="miniature", name="아주 작은 소품", blurb="60~90초. 유치·초등 저학년 첫 무대",
        mood="짧고 또렷한 소품 — 같은 것이 한 번 더 온다", form="AB", meter="4/4",
        tempo=(80, 108), texture_options=["양손 단음", "짧은 화음"],
        keys=["C", "G", "F"], level_range=(1, 4),
        shows_off=["또렷한 타건"], avoid_if=[],
    ),
    Preset(
        id="finale", name="피날레·화려한 마무리", blurb="옥타브와 스케일. 마지막 무대용",
        mood="거대한 피날레 — 옥타브 화음과 화려한 스케일", form="ABA", meter="4/4",
        tempo=(126, 152), texture_options=["양손 옥타브", "왼손 10도 스트라이드", "반음계 스케일"],
        keys=["B-", "E-", "A", "E", "B"], level_range=(7, 10),
        shows_off=["옥타브", "화려한 스케일", "표현력"], avoid_if=["손 크기", "지구력"],
    ),
]

BY_ID = {p.id: p for p in PRESETS}


def suitable(level: int, weaknesses: list[str] | None = None) -> list[Preset]:
    """이 학생에게 권할 만한 프리셋만. 레벨 대역 밖이거나 약점을 정면으로 건드리면 뺀다."""
    weak = set(weaknesses or [])
    out = []
    for p in PRESETS:
        lo, hi = p.level_range
        if not lo <= level <= hi:
            continue
        if weak & set(p.avoid_if):
            continue
        out.append(p)
    return out


def pick_key(preset: Preset, target_difficulty: float) -> str:
    """난이도가 높을수록 조표가 많은 쪽으로. 조성은 Plan 뒤에는 못 바꾼다."""
    if not preset.keys:
        return "C"
    idx = min(len(preset.keys) - 1, max(0, round((target_difficulty - 1) / 9 * (len(preset.keys) - 1))))
    return preset.keys[idx]


def pick_tempo(preset: Preset, target_difficulty: float, comfort_max: int) -> int:
    """난이도에 비례해 대역 안에서 고르되, 학생이 편한 상한을 절대 넘지 않는다."""
    lo, hi = preset.tempo
    want = round(lo + (hi - lo) * min(1.0, max(0.0, (target_difficulty - 1) / 9)))
    return min(want, comfort_max)
