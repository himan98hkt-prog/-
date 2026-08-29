"""시드 이미지 자동 분류·선별.

미드저니로 수백 장을 뽑으면 손으로 고를 수 없다. 이 모듈이 대신 한다.

  1. 테마 분류 — 미드저니 파일명에 프롬프트 문장이 들어 있어 그것으로 판별한다
  2. 중복 제거 — 한 프롬프트에서 4장씩 나오므로 거의 같은 그림이 많다
  3. 점수 — 이 파이프라인에 맞는 정도를 수치로 잰다
  4. 정리 — 깔끔한 이름으로 seeds/ 에 복사하고 제목 양식까지 만든다

[한계] 점수는 '포맷 적합도'지 '예술적 완성도'가 아니다. 밝기·채도·대비·
소실점 여부는 잴 수 있어도 그림이 멋진지는 못 잰다. 그래서 컨택트 시트를
만들어 눈으로 최종 확인할 수 있게 한다.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
TARGET_RATIO = 9 / 16
# 이 범위를 벗어나면 9:16 으로 자를 때 원본의 상당 부분이 사라진다.
# 예: 16:9 를 9:16 으로 자르면 가로의 32% 만 남는다. 구도가 무너진다.
PORTRAIT_MIN, PORTRAIT_MAX = 0.42, 0.80

# 미드저니 파일명에서 찾을 키워드 -> 테마. 위에서부터 먼저 맞는 것을 쓴다.
THEMES: list[tuple[str, str, tuple[str, ...]]] = [
    ("sky_islands",   "부유섬 · 천공",   ("floating_island", "floating island", "rope_bridge",
                                          "rope bridge", "cloud_sea", "cloud sea", "sky_kingdom",
                                          "sky kingdom", "sky_temple", "floating_rock")),
    ("spirit_forest", "정령의 숲",       ("spirit_forest", "spirit forest", "mushroom", "wisp",
                                          "will-o", "tree_root", "giant_tree", "swamp",
                                          "autumn_forest", "fireflies", "spirit_fox")),
    ("temple",        "고대 유적 · 신전", ("temple", "cathedral", "shrine_corridor", "causeway",
                                          "ruined_gate", "stone_guardian", "brazier", "pillar")),
    ("crystal_cave",  "크리스탈 동굴",    ("crystal", "cavern", "subterranean", "underground_river",
                                          "dwarven", "stalactite", "molten")),
    # "ice_"/"_ice" 로 두면 파일명의 r-ice, serv-ice 가 얼음으로 잡힌다.
    # 실제로 "green rice terraces" 가 얼음 왕국이 됐다. 양쪽을 다 막는다.
    ("ice",           "얼음 왕국",       ("frozen", "_ice_", "_icy_", "aurora", "snowfield",
                                          "snowy", "glacier", "northern_lights")),
    ("magic_city",    "마법 도시",       ("magic_city", "wizard", "arcane", "canal_street",
                                          "clocktower", "clock_tower", "festival", "lantern_city",
                                          "floating_lantern")),
    ("dragon",        "용 · 비행",       ("dragon", "airship", "giant_white_bird", "wings",
                                          "gliding", "flying_low")),
    ("underwater",    "심해 · 수중",     ("underwater", "sunken_city", "ocean_trench", "coral",
                                          "jellyfish", "swimming")),
    ("titan",         "거대 존재",       ("colossal", "titanic", "giant_statue", "sleeping_creature",
                                          "impossibly_large", "spine_of")),
    ("library",       "마법 도서관",     ("library", "bookshelf", "floating_book")),
    ("spirit_path",   "영혼의 길",       ("torii", "shrine", "river_of_stars", "stone_lantern",
                                          "cherry")),
    ("anime",         "애니메이션 톤",    ("hand-painted", "hand_painted", "animation_style",
                                          "watercolor", "pastel")),
    ("night_drive",   "야간 드라이브",    ("dashboard", "windshield", "steering", "car_at_night",
                                          "cockpit", "highway", "tunnel_at_night")),
    # 다운힐은 alley_bike 보다 먼저 봐야 한다. 둘 다 자전거라
    # 뒤에 두면 산악 다운힐이 '골목' 으로 분류된다.
    ("downhill",      "자전거 다운힐",    ("downhill", "switchback", "hairpin",
                                          "descending_a_mountain", "ridge_road")),
    ("alley_bike",    "골목 · 자전거",    ("bicycle", "alley", "hydrangea", "handlebar")),
    ("train",         "기차 · 궤도",      ("train", "railway", "track")),
    ("tunnel",        "터널 · 통로",      ("tunnel", "corridor", "subway", "passage")),
    ("coast",         "해안 · 바다",      ("beach", "pier", "ocean", "coastal", "shore",
                                          "bioluminescent_wave")),
    ("space",         "우주 · 행성",      ("alien_planet", "space_station", "moon", "portal",
                                          "starfield", "nebula", "ringed_planet")),
]

# 테마별 기본 제목·훅. 사이드카에 미리 채워 넣는다.
COPY: dict[str, tuple[str, str]] = {
    "sky_islands":   ("구름 위 다리를 건너", "이 다리 끝에 뭐가 있을까"),
    "downhill": ("바람을 가르며 내려가는 길", "브레이크 잡지 마세요"),
    "spirit_forest": ("빛나는 숲을 지나", "여긴 지도에 없는 곳입니다"),
    "temple":        ("잊혀진 신전으로", "문을 열면 안 되는 거였는데"),
    "crystal_cave":  ("수정 동굴 아래로", "빛이 어디서 오는 걸까"),
    "ice":           ("얼음 왕국을 건너", "소리 켜고 보세요"),
    "magic_city":    ("마법 도시의 밤", "30초 동안 다른 세계에"),
    "dragon":        ("용을 타고 계곡을", "돌아가는 길은 없었습니다"),
    "underwater":    ("가라앉은 도시로", "숨을 참고 따라오세요"),
    "titan":         ("거인의 등을 걷다", "이게 살아있는 거라고?"),
    "library":       ("끝없는 도서관", "끝까지 본 사람만 아는 장면"),
    "spirit_path":   ("천 개의 붉은 문", "여긴 존재하지 않는 곳입니다"),
    "anime":         ("그 여름의 어딘가", "이런 곳에 살고 싶다"),
    "night_drive":   ("빗속을 달리는 밤", "한 번도 안 멈추고 달렸습니다"),
    "alley_bike":    ("골목을 지나", "이 길 끝에 뭐가 있을까"),
    "train":         ("설산을 달리는 기차", "창밖만 30초"),
    "tunnel":        ("끝나지 않는 터널", "출구가 보이시나요"),
    "coast":         ("빛나는 밤바다", "파도 소리 켜고 보세요"),
    "space":         ("낯선 행성에서", "여긴 지구가 아닙니다"),
    "misc":          ("끝나지 않는 여행", "이 길 끝에 뭐가 있을까"),
}


def prompt_signature(path: Path) -> str:
    """미드저니 파일명에서 프롬프트 부분만 뽑아 정규화한다.

    같은 프롬프트로 뽑은 4장은 이 값이 같다. 중복 판정을 이 안에서만 하면
    서로 다른 장면이 하나로 뭉치는 일이 없다.
    """
    stem = path.stem.lower()
    stem = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "", stem)
    stem = re.sub(r"[^a-z0-9]+", " ", stem).strip()
    words = [w for w in stem.split() if len(w) > 2][:12]
    return " ".join(words)


@dataclass
class Shot:
    path: Path
    theme: str = "misc"
    width: int = 0
    height: int = 0
    ratio: float = 0.0
    brightness: float = 0.0     # 0~1 평균 밝기
    saturation: float = 0.0     # 0~1 평균 채도
    contrast: float = 0.0       # 0~1 밝기 표준편차
    center_pull: float = 0.0    # 중앙이 가장자리보다 밝은 정도 (소실점 대용)
    dhash: int = 0
    signature: str = ""
    score: float = 0.0
    disqualified: bool = False
    reasons: list[str] = field(default_factory=list)

    @property
    def megapixels(self) -> float:
        return self.width * self.height / 1_000_000


def classify(path: Path) -> str:
    """미드저니 파일명에서 테마를 추정한다."""
    name = path.stem.lower()
    for key, _label, words in THEMES:
        if any(w in name for w in words):
            return key
    return "misc"


def theme_label(key: str) -> str:
    for k, label, _ in THEMES:
        if k == key:
            return label
    return "기타"


def _dhash(img: Image.Image, size: int = 16) -> int:
    """가로 인접 픽셀 밝기 비교 해시. 거의 같은 그림을 찾는 데 쓴다.

    8x8(64비트)은 부드러운 그라데이션 그림을 전부 같다고 판정한다.
    16x16(256비트)으로 올려 변별력을 확보했다.
    """
    small = img.convert("L").resize((size + 1, size), Image.LANCZOS)
    px = list(small.getdata())
    bits = 0
    for row in range(size):
        base = row * (size + 1)
        for col in range(size):
            bits = (bits << 1) | int(px[base + col] < px[base + col + 1])
    return bits


def analyze(path: Path) -> Shot | None:
    """이미지 하나를 재서 Shot 으로 만든다. 열 수 없으면 None."""
    try:
        img = Image.open(path)
        img.draft("RGB", (512, 512))   # JPEG 은 디코딩 자체를 줄여 빠르게
        img.load()
    except Exception:
        return None

    shot = Shot(path=path, theme=classify(path), signature=prompt_signature(path))
    shot.width, shot.height = Image.open(path).size
    shot.ratio = shot.width / shot.height if shot.height else 0

    rgb = img.convert("RGB")
    rgb.thumbnail((160, 160), Image.LANCZOS)
    shot.dhash = _dhash(rgb)

    hsv = rgb.convert("HSV")
    _h, s, v = hsv.split()
    vals = list(v.getdata())
    n = len(vals) or 1
    mean_v = sum(vals) / n / 255
    var = sum((x / 255 - mean_v) ** 2 for x in vals) / n
    shot.brightness = mean_v
    shot.contrast = var ** 0.5
    shot.saturation = sum(s.getdata()) / n / 255

    # 중앙 1/3 과 전체의 밝기 차 — 소실점·광원이 가운데 있으면 커진다
    w, h = rgb.size
    cx0, cy0, cx1, cy1 = w // 3, h // 3, w * 2 // 3, h * 2 // 3
    center = v.crop((cx0, cy0, cx1, cy1))
    cvals = list(center.getdata())
    center_mean = sum(cvals) / (len(cvals) or 1) / 255
    shot.center_pull = max(0.0, center_mean - mean_v)

    _score(shot)
    return shot


def _bell(x: float, lo: float, hi: float) -> float:
    """lo~hi 구간이면 1, 벗어날수록 0 에 가까워진다."""
    if lo <= x <= hi:
        return 1.0
    d = (lo - x) if x < lo else (x - hi)
    span = max(hi - lo, 1e-6)
    return max(0.0, 1.0 - d / span)


def _score(s: Shot) -> None:
    """이 파이프라인에 얼마나 맞는지 0~100 으로 점수를 매긴다."""
    # 비율 — 세로가 아니면 탈락시킨다. 잘라내면 구도가 남지 않는다.
    ratio_fit = _bell(s.ratio, TARGET_RATIO - 0.04, TARGET_RATIO + 0.04)
    if not (PORTRAIT_MIN <= s.ratio <= PORTRAIT_MAX):
        s.disqualified = True
        shape = "가로" if s.ratio > 1 else "정사각에 가까움"
        s.reasons.append(f"{shape} ({s.width}x{s.height}) — 9:16 크롭 시 손실 과다")
    elif ratio_fit < 0.5:
        s.reasons.append(f"9:16 에서 벗어남 ({s.width}x{s.height})")

    # 해상도
    res_fit = min(s.megapixels / 2.0, 1.0)
    # 미드저니 9:16 기본 출력이 816x1456 이다. 900px 을 기준으로 잡으면
    # 정상 출력물 전부에 경고가 붙어 쓸모가 없다.
    if s.width < 720:
        s.disqualified = True
        s.reasons.append(f"해상도 부족 ({s.width}px) — 720px 이상 필요")
    elif s.width < 800:
        s.reasons.append(f"해상도 낮음 ({s.width}px)")

    # 톤 — 어두운 판타지와 밝은 대낮 월드, 둘 다 받는다.
    # 예전에는 0.46 위를 전부 깎았다. 레퍼런스가 어두운 계정뿐이었기 때문인데,
    # 밝고 탁 트인 3인칭 월드 톤이 늘면서 멀쩡한 이미지가 "너무 밝음" 으로
    # 20점씩 깎여 나갔다. 실제로 못 쓰는 것은 하늘이 날아간 0.78 위쪽이다.
    tone_fit = _bell(s.brightness, 0.16, 0.66)
    if s.brightness > 0.78:
        s.reasons.append("너무 밝음 — 하늘이 하얗게 날아갔는지 보세요")
    elif s.brightness < 0.10:
        s.reasons.append("너무 어두움")

    sat_fit = min(s.saturation / 0.45, 1.0)
    if s.saturation < 0.18:
        s.reasons.append("채도 낮음")

    contrast_fit = min(s.contrast / 0.26, 1.0)
    if s.contrast < 0.12:
        s.reasons.append("밋밋함")

    # 소실점 대용 — 가운데가 밝으면 '앞으로 갈 길'이 있을 확률이 높다.
    # 다만 하늘이 넓은 대낮 사진은 위쪽이 제일 밝아 이 값이 0 이 된다.
    # 그런 사진도 대비가 살아 있으면 깊이가 있는 것이므로 절반은 인정한다.
    depth_fit = min(s.center_pull / 0.14, 1.0)
    if depth_fit < 0.5 and s.contrast >= 0.20:
        depth_fit = 0.5

    s.score = round(100 * (
        0.28 * ratio_fit +
        0.10 * res_fit +
        0.20 * tone_fit +
        0.14 * sat_fit +
        0.13 * contrast_fit +
        0.15 * depth_fit
    ), 1)


def dedupe(shots: list[Shot], threshold: int = 24) -> list[list[Shot]]:
    """거의 같은 그림끼리 묶는다.

    미드저니는 한 프롬프트에서 4장을 낸다. 중복은 그 안에서만 생기므로
    **같은 프롬프트 서명끼리만** 비교한다. 서명이 다르면 아무리 비슷해 보여도
    다른 장면이므로 합치지 않는다. threshold 는 256비트 해시 기준이다.
    """
    buckets: dict[str, list[list[Shot]]] = {}
    for shot in sorted(shots, key=lambda s: -s.score):
        # 서명이 비면 파일명이 특이한 경우다. 테마로 대신 묶는다.
        key = shot.signature or f"__theme__{shot.theme}"
        groups = buckets.setdefault(key, [])
        for group in groups:
            if bin(group[0].dhash ^ shot.dhash).count("1") <= threshold:
                group.append(shot)
                break
        else:
            groups.append([shot])
    return [g for groups in buckets.values() for g in groups]


def contact_sheet(shots: list[Shot], dest: Path, *, cols: int = 6,
                  cell: int = 190, title: str = "") -> Path:
    """고른 이미지를 격자로 붙여 한눈에 보게 한다. 최종 판단은 눈으로."""
    if not shots:
        raise ValueError("컨택트 시트를 만들 이미지가 없습니다.")
    cols = max(1, min(cols, len(shots)))   # 3장인데 6칸이면 절반이 빈다
    rows = (len(shots) + cols - 1) // cols
    pad, label_h, head = 10, 26, 40 if title else 0
    cw, ch = cell, round(cell * 16 / 9)
    sheet = Image.new("RGB", (cols * (cw + pad) + pad,
                              head + rows * (ch + label_h + pad) + pad), (12, 16, 32))
    draw = ImageDraw.Draw(sheet)

    def font(sz):
        for p in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
                  "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"):
            try:
                return ImageFont.truetype(p, sz, index=1 if p.endswith("ttc") else 0)
            except OSError:
                continue
        return ImageFont.load_default()

    if title:
        draw.text((pad + 2, 11), title, font=font(19), fill=(226, 232, 240))

    for i, shot in enumerate(shots):
        r, c = divmod(i, cols)
        x = pad + c * (cw + pad)
        y = head + pad + r * (ch + label_h + pad)
        try:
            thumb = Image.open(shot.path)
            thumb.draft("RGB", (cw * 2, ch * 2))
            thumb = thumb.convert("RGB")
            thumb = thumb.resize((cw, ch), Image.LANCZOS)
            sheet.paste(thumb, (x, y))
        except Exception:
            draw.rectangle([x, y, x + cw, y + ch], fill=(40, 46, 70))
        label = f"{i + 1:>2}. {shot.score:.0f}점"
        draw.text((x + 2, y + ch + 5), label, font=font(14), fill=(148, 163, 184))

    dest.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(dest, "JPEG", quality=86)
    return dest


def safe_name(theme: str, index: int) -> str:
    return f"{theme}_{index:02d}"


def write_sidecar(dest_image: Path, theme: str, prompt_hint: str = "") -> Path:
    """이미지 내용에 맞는 제목·훅·움직임 프롬프트를 지어 사이드카에 넣는다.

    테마별 고정 문구를 돌려쓰면 같은 제목이 여러 편 나간다. 원본 프롬프트에서
    장면의 특징을 뽑아 편마다 다른 제목을 만든다.
    """
    from .copywriter import write as write_copy

    copy = write_copy(theme, prompt_hint, seed_key=dest_image.stem)
    dest = dest_image.with_suffix(".yaml")
    dest.write_text(
        "# 제목과 훅은 조회수에 직접 영향을 줍니다. 마음에 안 들면 고치세요.\n"
        f"title:  {copy.title}\n"
        f"hook:   {copy.hook}\n"
        "\n"
        "# 영상의 카메라 움직임. 비우면 config.yaml 의 motion_prompt 를 씁니다.\n"
        f"prompt: {copy.prompt}\n"
        "\nscene_prompts: []\n",
        encoding="utf-8")
    return dest


# 사용자명으로 보이는 토큰 — 숫자가 섞여 있으면 거의 확실하다 (himan98, u1 …).
_HANDLE = re.compile(r"^(?=.*\d)[a-z0-9]+$", re.I)
# 숫자가 섞였어도 프롬프트에 흔히 쓰이는 말은 사용자명이 아니다.
_NOT_HANDLE = {"3d", "2d", "4k", "8k", "16k", "1st", "35mm", "50mm", "85mm"}
# 세 글자 이하지만 멀쩡한 낱말 — 잘린 조각과 구분해야 한다.
_SHORT_OK = {
    "a", "an", "the", "at", "in", "on", "of", "up", "to", "by", "no",
    "sea", "sky", "ice", "fog", "sun", "red", "old", "far", "dim", "wet",
    "two", "one", "big", "top", "low", "hot", "cat", "dog", "man", "eye",
    "run", "fly", "war", "art", "sad", "new", "koi", "zen", "jet", "car",
}
# 문장 끝에 남으면 어색한 토큰 — 잘린 자리에 흔히 남는다.
_DANGLING = {"a", "an", "the", "at", "in", "on", "of", "to", "by", "with",
             "and", "over", "under", "near", "into", "from", "through",
             "down", "up", "for", "as", "its", "his", "her", "their"}


def prompt_from_filename(path: Path) -> str:
    """미드저니 파일명에서 프롬프트 문장을 복원한다.

    파일명은 프롬프트를 그대로 담지만 **온전하지 않다.** 앞에 사용자명이,
    뒤에 격자 번호(_0.._3)가 붙고, 95자쯤에서 낱말 한가운데가 잘린다.
    그대로 쓰면 돈 내고 부르는 영상 모델에 이런 게 들어간다:

        first person view riding a bicycle down a narrow japanese all 1
                                                                ^^^^^^^
        (alley 가 잘려 all, 뒤의 1 은 격자 번호)

    실제로 사용자가 "애니메이션이 이상하다" 고 신고한 영상의 프롬프트다.
    예전 코드는 여기에 더해 **앞 토큰을 무조건 하나 버려서**,
    `first_person_view_…` 의 first 와 `aurora_over_a_frozen_lake` 의
    aurora 까지 날렸다 — 주제어가 통째로 사라진 것이다.
    """
    stem = path.stem
    stem = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "", stem)
    stem = re.sub(r"_+", " ", stem).strip(" _-")
    parts = stem.split()

    # 1) 끝의 격자 번호를 뗀다 (0~3, 넉넉히 두 자리까지)
    while parts and re.fullmatch(r"\d{1,2}", parts[-1]):
        parts.pop()

    # 2) 앞의 사용자명 — **숫자가 섞였을 때만** 뗀다. 확실하지 않으면 남긴다.
    #    낱말 하나를 잘못 버리는 쪽이 남겨두는 쪽보다 훨씬 나쁘다.
    if len(parts) > 3 and _HANDLE.match(parts[0]) and parts[0].lower() not in _NOT_HANDLE:
        parts = parts[1:]

    # 3) 잘려나간 끝 조각을 뗀다 (three 글자 이하이면서 멀쩡한 낱말이 아닌 것)
    while len(parts) > 2 and len(parts[-1]) <= 3 and parts[-1].lower() not in _SHORT_OK:
        parts.pop()

    # 4) 끝에 남은 전치사·관사를 정리한다
    while len(parts) > 2 and parts[-1].lower() in _DANGLING:
        parts.pop()

    text = " ".join(parts).strip()
    return re.sub(r"\s+", " ", text)[:200]
