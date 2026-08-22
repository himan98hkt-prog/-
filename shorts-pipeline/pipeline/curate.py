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

    # 어둡고 채도 높게 — 레퍼런스 계정들의 공통점
    dark_fit = _bell(s.brightness, 0.16, 0.46)
    if s.brightness > 0.62:
        s.reasons.append("너무 밝음")
    elif s.brightness < 0.10:
        s.reasons.append("너무 어두움")

    sat_fit = min(s.saturation / 0.45, 1.0)
    if s.saturation < 0.18:
        s.reasons.append("채도 낮음")

    contrast_fit = min(s.contrast / 0.26, 1.0)
    if s.contrast < 0.12:
        s.reasons.append("밋밋함")

    # 소실점 대용 — 가운데가 밝으면 '앞으로 갈 길'이 있을 확률이 높다
    depth_fit = min(s.center_pull / 0.14, 1.0)

    s.score = round(100 * (
        0.28 * ratio_fit +
        0.10 * res_fit +
        0.20 * dark_fit +
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


def prompt_from_filename(path: Path) -> str:
    """미드저니 파일명에서 프롬프트 문장을 복원한다 (해시·사용자명 제거)."""
    stem = path.stem
    stem = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "", stem)
    stem = re.sub(r"_+", " ", stem).strip(" _-")
    # 앞쪽 사용자명 토큰을 떼어낸다
    parts = stem.split()
    if parts and len(parts) > 3:
        parts = parts[1:]
    text = " ".join(parts).strip()
    return re.sub(r"\s+", " ", text)[:200]
