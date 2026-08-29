#!/usr/bin/env python3
"""AI DEOKHU 브랜드 에셋 생성.

유튜브/인스타 프로필·배너를 정확한 규격으로 만든다. AI 이미지 생성 대신
직접 그리므로 한글이 깨지지 않고 규격이 정확하다.

  python brand/make_assets.py

콘셉트: 소실점으로 빨려드는 네온 터널.
        채널 콘텐츠(끊김 없는 전진)를 그대로 상징한다.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).parent / "assets"

# ── 팔레트 ───────────────────────────────────────────────────────────
# 레퍼런스 계정들의 공통 색: 심야 네이비 바탕 + 시안/마젠타 네온 + 따뜻한 지평선
NAVY_DEEP = (6, 10, 24)
NAVY = (13, 20, 46)
CYAN = (34, 211, 238)
VIOLET = (168, 85, 247)
MAGENTA = (232, 121, 249)
AMBER = (253, 224, 71)
ORANGE = (251, 146, 60)
WHITE = (255, 255, 255)

CJK_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
CJK_REG = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
LATIN_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"


def font(path: str, size: int, index: int = 0) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size, index=index)
    except OSError:
        return ImageFont.load_default()


def kr(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    """한글이 나오는 폰트.

    예전에는 리눅스 Noto 경로만 봤다. **윈도우에는 그 경로가 없다.**
    그러면 PIL 기본 비트맵 폰트로 떨어져서 프로필·배너의 한글이 뭉개진다.
    이 프로그램은 윈도우에서 돌아가는데도 그랬다.

    이제 pipeline.look 이 운영체제별로 찾아준다(윈도우 맑은 고딕 등).
    """
    for path in (CJK_BOLD if bold else CJK_REG, _system_kr()):
        if not path:
            continue
        for idx in (1, 0):
            try:
                f = ImageFont.truetype(path, size, index=idx)
            except OSError:
                continue
            # 한글이 실제로 그려지는 인덱스인지 확인
            if f.getbbox("한") != (0, 0, 0, 0):
                return f
    return font(LATIN_BOLD, size)


def _system_kr() -> str | None:
    try:
        import sys as _sys
        from pathlib import Path as _P
        _sys.path.insert(0, str(_P(__file__).resolve().parent.parent))
        from pipeline.look import find_font
        return find_font()
    except Exception:          # noqa: BLE001 — 폰트를 못 찾아도 그림은 그린다
        return None


def lerp(a: tuple, b: tuple, t: float) -> tuple:
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ── 배경 요소 ────────────────────────────────────────────────────────
def radial_bg(size: tuple[int, int], inner: tuple, outer: tuple,
              center: tuple[float, float] = (0.5, 0.5)) -> Image.Image:
    """중심에서 바깥으로 퍼지는 그라데이션. 작게 그린 뒤 확대해 빠르게 만든다."""
    w, h = size
    small = (max(w // 6, 64), max(h // 6, 64))
    img = Image.new("RGB", small)
    px = img.load()
    cx, cy = center[0] * small[0], center[1] * small[1]
    max_d = math.hypot(max(cx, small[0] - cx), max(cy, small[1] - cy))
    for y in range(small[1]):
        for x in range(small[0]):
            t = min(math.hypot(x - cx, y - cy) / max_d, 1.0)
            px[x, y] = lerp(inner, outer, t ** 0.85)
    return img.resize(size, Image.BICUBIC)


def star_field(size: tuple[int, int], count: int, seed: int = 7) -> Image.Image:
    """별. random 대신 결정적 해시를 써 실행마다 같은 그림이 나오게 한다."""
    w, h = size
    layer = Image.new("RGB", size, (0, 0, 0))
    d = ImageDraw.Draw(layer)
    for i in range(count):
        n = (i * 2654435761) & 0xFFFFFFFF
        x = (n >> 8) % w
        y = (n >> 16) % h
        bright = 90 + ((n >> 4) % 165)
        r = 1 if (n % 10) else 2
        d.ellipse([x - r, y - r, x + r, y + r], fill=(bright, bright, min(255, bright + 30)))
    return layer


def tunnel(size: tuple[int, int], vp: tuple[float, float], *,
           rays: int = 44, spread: float = 1.0) -> Image.Image:
    """소실점에서 방사되는 네온 선. 이 채널 콘텐츠의 핵심 모티프.

    굵기와 밝기를 선마다 다르게 준다. 균일하면 방사형 클립아트처럼 보인다.
    """
    w, h = size
    ss = 2  # 슈퍼샘플링
    layer = Image.new("RGB", (w * ss, h * ss), (0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = vp[0] * w * ss, vp[1] * h * ss
    reach = math.hypot(w * ss, h * ss) * spread

    for i in range(rays):
        n = (i * 2654435761) & 0xFFFFFFFF
        # 균등 배치에 흔들림을 줘 규칙성을 깬다
        ang = (i / rays) * math.tau + ((n % 1000) / 1000 - 0.5) * (math.tau / rays)
        t = (math.sin(ang * 1.5) + 1) / 2
        col = lerp(CYAN, MAGENTA, t)
        # 3할은 굵고 밝게, 나머지는 가늘고 어둡게
        strong = (n >> 12) % 10 < 3
        width = ss * (3 if strong else 1)
        dim = 1.0 if strong else 0.35 + ((n >> 20) % 40) / 100
        col = tuple(int(c * dim) for c in col)
        length = reach * (0.65 + ((n >> 6) % 35) / 100)
        d.line([cx, cy, cx + math.cos(ang) * length, cy + math.sin(ang) * length],
               fill=col, width=width)

    layer = layer.resize((w, h), Image.LANCZOS)

    # 소실점에서 멀어질수록 어두워지게 (중앙만 빛나야 원근이 산다)
    mask = Image.new("L", (w, h))
    md = ImageDraw.Draw(mask)
    steps = 60
    for i in range(steps, 0, -1):
        t = i / steps
        r = reach / ss * t
        md.ellipse([cx / ss - r, cy / ss - r, cx / ss + r, cy / ss + r],
                   fill=int(255 * (t ** 0.6)))
    layer.putalpha(mask)
    return layer


def _screen(base: Image.Image, top: Image.Image) -> Image.Image:
    """스크린 블렌드: 255 - (255-a)(255-b)/255. 빛을 더하는 합성."""
    from PIL import ImageChops

    inv_b = ImageChops.invert(base.convert("RGB"))
    inv_t = ImageChops.invert(top.convert("RGB"))
    return ImageChops.invert(ImageChops.multiply(inv_b, inv_t))


def glow(img: Image.Image, radius: int, strength: float = 1.0) -> Image.Image:
    """블러 사본을 스크린 합성해 네온 발광을 만든다."""
    blurred = img.filter(ImageFilter.GaussianBlur(radius))
    if strength != 1.0:
        blurred = Image.eval(blurred, lambda v: min(255, int(v * strength)))
    return _screen(img, blurred)


def warm_core(size: tuple[int, int], vp: tuple[float, float],
              radius_frac: float = 0.22) -> Image.Image:
    """소실점 주변의 따뜻한 빛.

    전폭 띠로 깔면 화면을 가로지르는 얼룩처럼 보인다. 소실점에 모아야
    '멀리 있는 광원' 으로 읽힌다.
    """
    w, h = size
    layer = Image.new("RGB", size, (0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = vp[0] * w, vp[1] * h
    base = min(w, h) * radius_frac
    for i in range(28, 0, -1):
        t = i / 28
        r = base * t
        col = lerp(AMBER, ORANGE, 1 - t)
        col = tuple(int(c * (1 - t) ** 1.4) for c in col)
        d.ellipse([cx - r, cy - r, cx + r * 1.6, cy + r], fill=col)
    return layer.filter(ImageFilter.GaussianBlur(int(base / 2.2)))


def text_glow(canvas: Image.Image, xy: tuple[int, int], text: str,
              fnt: ImageFont.FreeTypeFont, color: tuple, glow_col: tuple,
              radius: int = 18, anchor: str = "mm") -> None:
    """글자 뒤에 발광을 깔고 그 위에 선명한 글자를 얹는다."""
    layer = Image.new("RGB", canvas.size, (0, 0, 0))
    ImageDraw.Draw(layer).text(xy, text, font=fnt, fill=glow_col, anchor=anchor)
    layer = layer.filter(ImageFilter.GaussianBlur(radius))
    canvas.paste(_screen(canvas, layer), (0, 0))
    ImageDraw.Draw(canvas).text(xy, text, font=fnt, fill=color, anchor=anchor)


def circle_crop(img: Image.Image) -> Image.Image:
    """플랫폼이 원형으로 자르므로, 가장자리를 미리 정리해 둔다."""
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).ellipse([0, 0, img.size[0] - 1, img.size[1] - 1], fill=255)
    out = Image.new("RGB", img.size, NAVY_DEEP)
    out.paste(img, (0, 0), mask)
    return out


# ══════════════════════════════════════════════════════════════════════
#  에셋
# ══════════════════════════════════════════════════════════════════════
def build_avatar(size: int = 1080) -> Image.Image:
    """프로필 이미지. 유튜브·인스타 공용, 원형으로 잘려 표시된다.

    98px 로 줄여도 형태가 읽히도록 요소를 크고 단순하게 잡는다.
    """
    S = (size, size)
    img = radial_bg(S, NAVY, NAVY_DEEP, center=(0.5, 0.46))

    # 소실점으로 빨려드는 터널
    t = tunnel(S, (0.5, 0.46), rays=36, spread=0.75)
    img.paste(_screen(img, t.convert("RGB")), (0, 0), t.split()[-1])
    img = glow(img, size // 28, 1.15)

    img = _screen(img, warm_core(S, (0.5, 0.46), 0.16))

    # 중심 코어 — 작게 축소돼도 남는 밝은 점.
    # 흰색을 넣으면 글자가 묻히므로 보라 계열로만 쌓는다.
    cx, cy = size // 2, int(size * 0.46)
    core = Image.new("RGB", S, (0, 0, 0))
    cd = ImageDraw.Draw(core)
    for r, col in ((size // 7, VIOLET), (size // 4, (60, 30, 110))):
        cd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
    core = core.filter(ImageFilter.GaussianBlur(size // 14))
    img = _screen(img, core)

    # 워드마크
    text_glow(img, (cx, int(size * 0.455)), "AI", kr(int(size * 0.30)),
              WHITE, CYAN, radius=size // 26)
    text_glow(img, (cx, int(size * 0.70)), "DEOKHU", kr(int(size * 0.115)),
              WHITE, MAGENTA, radius=size // 40)

    # 테두리 링
    ring = Image.new("RGB", S, (0, 0, 0))
    rd = ImageDraw.Draw(ring)
    pad = size // 26
    rd.ellipse([pad, pad, size - pad, size - pad], outline=CYAN, width=size // 90)
    rd.arc([pad, pad, size - pad, size - pad], 200, 340, fill=MAGENTA, width=size // 70)
    img = _screen(img, ring.filter(ImageFilter.GaussianBlur(size // 300)))

    return circle_crop(img)


def build_banner(w: int = 2048, h: int = 1152) -> Image.Image:
    """유튜브 배너.

    2048x1152 전체는 TV 에서만 보인다. 데스크톱은 가운데 2048x423,
    모바일은 1546x423 만 나온다. 글자는 전부 1546x423 안에 넣는다.
    """
    S = (w, h)
    img = radial_bg(S, NAVY, NAVY_DEEP, center=(0.5, 0.52))
    img = _screen(img, star_field(S, 260))

    t = tunnel(S, (0.5, 0.52), rays=56, spread=1.15)
    img.paste(_screen(img, t.convert("RGB")), (0, 0), t.split()[-1])
    img = glow(img, 26, 1.05)
    img = _screen(img, warm_core(S, (0.5, 0.52), 0.20))

    # 글자가 얹힐 자리를 어둡게 눌러 대비를 만든다
    from PIL import ImageChops

    veil = Image.new("RGB", S, (0, 0, 0))
    ImageDraw.Draw(veil).ellipse(
        [w // 2 - int(w * 0.30), h // 2 - int(h * 0.17),
         w // 2 + int(w * 0.30), h // 2 + int(h * 0.17)],
        fill=(96, 92, 112))
    veil = veil.filter(ImageFilter.GaussianBlur(w // 18))
    img = ImageChops.subtract(img, veil)

    cx, cy = w // 2, h // 2
    text_glow(img, (cx, cy - 78), "AI DEOKHU", kr(150), WHITE, CYAN, radius=34)
    text_glow(img, (cx, cy + 40), "끝나지 않는 여행", kr(62), (226, 232, 240),
              MAGENTA, radius=22)

    d = ImageDraw.Draw(img)
    d.text((cx, cy + 118), "AI ANIMATION  ·  CINEMATIC LOOPS",
           font=kr(34), fill=(203, 213, 225), anchor="mm")

    # 업로드 주기 — 구독 전환에 실제로 효과가 있다
    pill = kr(33)
    label = "매일 저녁 9시"
    bbox = d.textbbox((cx, cy + 186), label, font=pill, anchor="mm")
    pad_x, pad_y = 30, 15
    d.rounded_rectangle(
        [bbox[0] - pad_x, bbox[1] - pad_y, bbox[2] + pad_x, bbox[3] + pad_y],
        radius=(bbox[3] - bbox[1] + pad_y * 2) // 2, outline=CYAN, width=3)
    d.text((cx, cy + 186), label, font=pill, fill=CYAN, anchor="mm")

    return img


def build_instagram_avatar(size: int = 1080) -> Image.Image:
    """인스타 프로필. 유튜브와 같은 마크를 쓰되 핸들을 넣어 통일감을 준다."""
    img = build_avatar(size)
    d = ImageDraw.Draw(img)
    d.text((size // 2, int(size * 0.845)), "@ai.deokhu", font=kr(int(size * 0.052)),
           fill=(148, 163, 184), anchor="mm")
    return circle_crop(img)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = [
        ("youtube_avatar_800.png", lambda: build_avatar(1080).resize((800, 800), Image.LANCZOS)),
        ("youtube_banner_2048x1152.png", build_banner),
        ("instagram_avatar_1080.png", lambda: build_instagram_avatar(1080)),
    ]
    for name, fn in jobs:
        path = OUT / name
        fn().save(path, "PNG", optimize=True)
        kb = path.stat().st_size / 1024
        print(f"  ✓ {name:34} {kb:7.0f} KB")

    # 작게 줄였을 때 형태가 남는지 확인용
    av = Image.open(OUT / "youtube_avatar_800.png")
    prev = Image.new("RGB", (98 + 48 + 32 + 60, 130), NAVY_DEEP)
    x = 20
    for s in (98, 48, 32):
        prev.paste(av.resize((s, s), Image.LANCZOS), (x, (130 - s) // 2))
        x += s + 20
    prev.save(OUT / "_avatar_smallsizes.png")
    print(f"  ✓ {'_avatar_smallsizes.png':34} (98/48/32px 가독성 확인용)")


if __name__ == "__main__":
    main()
