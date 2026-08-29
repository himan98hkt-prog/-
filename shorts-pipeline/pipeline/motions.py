"""카메라 움직임 프리셋.

영어 프롬프트를 직접 쓰라고 하면 두 가지가 일어난다. 안 쓰거나, 잘못 쓴다.
잘못 쓰면 애니메이션이 이상해지고 그 값은 이미 나간 뒤다.

그래서 **검증된 문장 몇 개를 골라 쓰게** 한다. 각 프리셋은 세 가지를 지킨다.

  1. 카메라가 무엇을 하는지 한 가지만 말한다.
     두 가지를 시키면(전진하면서 회전) 모델이 둘 다 어설프게 한다.
  2. 속도를 못 박는다. `steady speed` 가 없으면 클립마다 속도가 달라져
     이어붙였을 때 덜컹거린다.
  3. 컷을 금지한다. `no scene cut` 이 없으면 모델이 장면을 바꿔 버린다 —
     끊김 없는 영상을 만들려는데 이게 제일 치명적이다.

`negative` 는 그 움직임에서만 특별히 막아야 하는 것이다. 공통 금지 사항은
config.yaml 의 negative_prompt 에 있고, 여기 것이 뒤에 더해진다.
"""

from __future__ import annotations

from dataclasses import dataclass

# 끊김 없이 이어붙이려면 어떤 움직임이든 이 두 가지는 들어가야 한다.
_SPINE = "constant steady speed, no camera shake, no scene cut, cinematic"


@dataclass(frozen=True)
class Motion:
    key: str
    label: str        # 화면에 보이는 이름
    note: str         # 언제 쓰는지 한 줄
    prompt: str
    negative: str = ""

    def as_dict(self) -> dict[str, str]:
        return {"key": self.key, "label": self.label, "note": self.note,
                "prompt": self.prompt, "negative": self.negative}


MOTIONS: tuple[Motion, ...] = (
    Motion(
        "forward", "앞으로 계속 전진",
        "골목·터널·길처럼 앞이 뚫린 그림. 가장 무난합니다.",
        f"smooth drone camera moving forward through the scene, {_SPINE}, "
        "consistent lighting",
        "zoom out, reverse motion, turning around",
    ),
    Motion(
        "follow", "뒤에서 따라가기",
        "사람·자전거·동물처럼 움직이는 대상이 있을 때.",
        f"smooth drone camera following the subject from behind at a fixed "
        f"distance, {_SPINE}, subject stays centered",
        "subject turns to face camera, overtaking the subject, zoom out",
    ),
    Motion(
        "rise", "위로 천천히 상승",
        "탑·절벽·거대한 건축물. 크기를 보여줄 때.",
        f"camera slowly craning upward while facing the subject, {_SPINE}, "
        "scale revealed gradually",
        "descending, tilting down, zoom out",
    ),
    Motion(
        "descend", "아래로 천천히 하강",
        "계단·협곡·깊은 곳으로 내려가는 그림.",
        f"camera slowly descending along the path ahead, {_SPINE}, "
        "consistent lighting",
        "ascending, tilting up, reverse motion",
    ),
    Motion(
        "approach", "대상에 천천히 다가가기",
        "신전·문·생물처럼 목표가 하나 뚜렷할 때.",
        f"camera slowly pushing in toward the main subject, {_SPINE}, "
        "subject stays centered and in focus",
        "zoom out, pulling back, losing the subject",
    ),
    Motion(
        "glide", "옆으로 미끄러지듯",
        "풍경·해안선처럼 옆으로 긴 그림.",
        f"camera gliding sideways in one direction, {_SPINE}, "
        "parallax between foreground and background",
        "changing direction, rotating, zoom",
    ),
    Motion(
        "orbit", "대상 주위를 도는",
        "중심이 되는 대상 하나를 여러 각도로 보여줄 때.",
        f"camera orbiting slowly around the subject in one direction, {_SPINE}, "
        "subject stays centered",
        "reversing direction, zoom in, zoom out",
    ),
    Motion(
        "drift", "거의 멈춘 듯 아주 천천히",
        "잔잔한 그림. 소리와 분위기로 끌고 갈 때.",
        f"camera drifting forward almost imperceptibly, very slow, {_SPINE}, "
        "meditative pace",
        "fast motion, sudden movement, zoom",
    ),
)

_BY_KEY = {m.key: m for m in MOTIONS}


def get(key: str) -> Motion | None:
    return _BY_KEY.get((key or "").strip().lower())


def as_list() -> list[dict[str, str]]:
    """화면에 그대로 넘길 목록."""
    return [m.as_dict() for m in MOTIONS]


def combine_negative(base: str, motion_key: str) -> str:
    """공통 금지 사항 뒤에 **프리셋 이름으로** 그 움직임의 금지 사항을 더한다."""
    found = get(motion_key)
    return merge_negative(base, found.negative if found else "")


def merge_negative(base: str, extra: str) -> str:
    """두 금지 사항 목록을 합친다. 순서를 지키고 중복은 뺀다."""
    parts: list[str] = []
    seen: set[str] = set()
    for chunk in (base or "", extra or ""):
        for word in chunk.split(","):
            word = " ".join(word.split())
            if word and word.lower() not in seen:
                seen.add(word.lower())
                parts.append(word)
    return ", ".join(parts)
