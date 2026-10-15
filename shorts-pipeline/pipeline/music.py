"""영상에 깔 배경음악을 자동으로 고른다.

영상만 나오면 아무도 끝까지 보지 않는다. 소리가 있어야 한다.

수노(Suno)로 만든 음원을 `music/` 아래 **분위기 폴더**에 넣어 두면
테마에 맞는 것을 자동으로 골라 붙인다. 테마마다 폴더를 만들 필요는 없다.
테마 20개에 폴더 20개는 관리가 안 된다. 분위기 5개면 충분하다.

    music/
      bright/   밝고 상쾌 — 다운힐, 해안, 애니 톤
      epic/     웅장    — 용·비행, 거대 존재, 부유섬, 신전
      calm/     잔잔    — 영혼의 길, 도서관, 숲, 기차
      mystic/   신비    — 크리스탈, 심해, 얼음, 우주
      city/     도시 밤  — 마법 도시, 야간 드라이브, 골목
      any/      아무 데나 쓸 것 (위 폴더가 비었을 때의 보험)

고르는 방식은 **파일명 해시**다. 같은 시드는 항상 같은 곡을 받는다.
매번 무작위로 고르면 다시 만들 때마다 곡이 바뀌어 비교가 안 된다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}

MOODS = ("bright", "epic", "calm", "mystic", "city")

MOOD_LABEL = {
    "bright": "밝고 상쾌",
    "epic":   "웅장",
    "calm":   "잔잔",
    "mystic": "신비",
    "city":   "도시 밤",
    "any":    "아무 데나",
}

# 테마 -> 분위기. curate.THEMES 의 키와 맞춰 둔다.
MOOD_OF: dict[str, str] = {
    "downhill":      "bright",
    "coast":         "bright",
    "anime":         "bright",
    "alley_bike":    "city",
    "magic_city":    "city",
    "night_drive":   "city",
    "dragon":        "epic",
    "titan":         "epic",
    "sky_islands":   "epic",
    "temple":        "epic",
    "spirit_forest": "calm",
    "spirit_path":   "calm",
    "library":       "calm",
    "train":         "calm",
    "crystal_cave":  "mystic",
    "underwater":    "mystic",
    "ice":           "mystic",
    "space":         "mystic",
    "tunnel":        "mystic",
    "misc":          "any",
}


@dataclass
class Track:
    path: Path
    mood: str

    @property
    def name(self) -> str:
        return self.path.name


def mood_for(theme: str) -> str:
    return MOOD_OF.get(theme, "any")


def _tracks_in(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir()
                  if p.is_file() and p.suffix.lower() in AUDIO_EXT)


def catalog(music_dir: Path) -> dict[str, list[Path]]:
    """분위기별로 몇 곡이 있는지. 작업실 화면에 그대로 보여준다."""
    music_dir = Path(music_dir)
    out: dict[str, list[Path]] = {}
    for mood in (*MOODS, "any"):
        found = _tracks_in(music_dir / mood)
        if found:
            out[mood] = found
    loose = _tracks_in(music_dir)
    if loose:
        out.setdefault("any", []).extend(loose)
    return out


def total_tracks(music_dir: Path) -> int:
    return sum(len(v) for v in catalog(music_dir).values())


def _hash(seed: str) -> int:
    h = 2166136261
    for ch in seed:
        h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return h


def pick(theme: str, seed_key: str, music_dir: Path) -> Track | None:
    """테마에 맞는 곡 하나. **곡이 한 곡이라도 있으면 무음으로 가지 않는다.**

    찾는 순서: 딱 맞는 분위기 -> any -> 가진 것 중 아무거나.

    마지막 단계가 중요하다. 예전에는 딱 맞는 분위기 폴더가 비면 그대로
    무음이었다. 실제로 `music/epic` 과 `music/bright` 에 곡 4개를 넣어둔
    사용자가, `alley_bike`(=city) 시드로 만든 영상에서 소리를 못 들었다.
    분위기가 조금 안 맞는 것과 아무 소리도 없는 것 중에서는 **소리가 있는
    쪽이 언제나 낫다** — 무음이면 끝까지 보지 않는다.
    """
    music_dir = Path(music_dir)
    mood = mood_for(theme)
    shelf = catalog(music_dir)

    order = [mood, "any"]
    # 남은 분위기도 정해진 순서로 훑는다. 같은 시드는 늘 같은 곡을 받아야 한다.
    order += [m for m in (*MOODS, "any") if m not in order]

    for key in order:
        found = shelf.get(key)
        if found:
            return Track(found[_hash(seed_key or theme) % len(found)], key)
    return None


def describe(music_dir: Path) -> str:
    """`music/` 상태를 한 줄로. 비어 있으면 뭘 해야 하는지까지 알려준다."""
    shelf = catalog(music_dir)
    if not shelf:
        return (f"{music_dir} 가 비어 있습니다 — 영상이 무음으로 나갑니다. "
                f"수노에서 만든 곡을 {music_dir}/bright 같은 폴더에 넣으세요.")
    parts = [f"{MOOD_LABEL.get(k, k)} {len(v)}곡" for k, v in shelf.items()]
    return " · ".join(parts)


_SAFE = re.compile(r"[^0-9A-Za-z가-힣._-]+")


def safe_track_name(name: str) -> str:
    """수노에서 받은 파일명은 길고 특수문자가 많다. ffmpeg 인자로 안전하게."""
    stem = _SAFE.sub("_", Path(name).stem).strip("_")[:60] or "track"
    return stem + Path(name).suffix.lower()
