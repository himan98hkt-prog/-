#!/usr/bin/env python3
"""바탕화면 바로가기용 아이콘(.ico)을 그린다.

윈도우 기본 shell32 아이콘 대신 채널 브랜드를 쓴다.
콘셉트는 배너·프로필과 같다 — 소실점으로 빨려드는 네온 터널.

작은 크기에서 뭉개지지 않는 것이 전부다. 그래서
  - 16~24px 은 고리를 줄이고 중심 빛만 남긴다
  - 크기마다 따로 그린 뒤 한 파일에 담는다 (한 장을 축소하면 뭉갠다)
  - 뱃지(↓, 폴더)는 32px 이상에서만 붙인다

  python brand/make_icons.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).parent / "icons"

# 배너·프로필과 같은 팔레트
NAVY_DEEP = (6, 10, 24)
NAVY = (17, 26, 51)
CYAN = (34, 211, 238)
MAGENTA = (232, 121, 249)
AMBER = (251, 191, 36)
SLATE = (135, 145, 176)
WHITE = (255, 255, 255)

# 윈도우가 실제로 꺼내 쓰는 크기들
SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)

SS = 8          # 슈퍼샘플링 배수. 이 배로 그린 뒤 줄여서 계단을 없앤다


def lerp(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def _rings(d: ImageDraw.ImageDraw, S: int, accent, count: int, width: float):
    """바깥에서 중심으로 좁아지는 사각 고리. 안쪽일수록 밝고 촘촘하다.

    등비로 줄여야 원근이 산다. 비율이 크면(0.75) 고리가 중심 쪽에 몰려
    실제로 빨려드는 것처럼 보이고, 작으면 그냥 동심원 몇 개로 보인다.
    """
    cx = cy = S / 2
    halves = []
    for i in range(count):
        t = i / max(1, count - 1)              # 0=바깥 1=안쪽
        half = S * 0.385 * (0.755 ** i)
        halves.append(half)
        col = lerp(accent, WHITE, t * 0.8)
        alpha = round(70 + 185 * t)
        d.rounded_rectangle(
            [cx - half, cy - half, cx + half, cy + half],
            radius=max(1.0, half * 0.34), outline=col + (alpha,),
            width=max(1, round(width * (1 - t * 0.5))))

    # 큰 크기에서만 모서리를 잇는 소실선을 깔아 터널로 읽히게 한다
    if S >= 48 * SS and len(halves) >= 2:
        a, b = halves[0] * 0.74, halves[-1] * 0.74
        for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            d.line([(cx + sx * a, cy + sy * a), (cx + sx * b, cy + sy * b)],
                   fill=lerp(accent, NAVY, 0.35) + (90,),
                   width=max(1, round(width * 0.55)))


def _core(img: Image.Image, S: int, accent):
    """소실점의 빛. 이게 작은 크기에서 아이콘을 알아보게 해준다."""
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    g = ImageDraw.Draw(glow)
    cx = cy = S / 2
    for rad, col, a in (
        (S * 0.135, accent, 120),
        (S * 0.075, lerp(accent, WHITE, 0.55), 210),
        (S * 0.036, WHITE, 255),
    ):
        g.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=col + (a,))
    glow = glow.filter(ImageFilter.GaussianBlur(S * 0.018))
    return Image.alpha_composite(img, glow)


BADGE_R = 0.152          # 아이콘 한 변 대비 뱃지 반지름


def _badge_plate(d: ImageDraw.ImageDraw, S: int, col):
    """뱃지가 앉을 어두운 원판. 터널 위에 그냥 얹으면 안 읽힌다."""
    bx = by = S * 0.755
    r = S * BADGE_R
    d.ellipse([bx - r, by - r, bx + r, by + r], fill=NAVY_DEEP + (255,),
              outline=col + (255,), width=max(1, round(S * 0.020)))
    return bx, by, r


def _badge_arrow(d: ImageDraw.ImageDraw, S: int, col):
    """업데이트용 — 내려받기 화살표."""
    bx, by, r = _badge_plate(d, S, col)
    stem = max(1, round(S * 0.040))
    d.line([(bx, by - r * 0.50), (bx, by + r * 0.10)],
           fill=col + (255,), width=stem)
    w = r * 0.40
    d.polygon([(bx - w, by - r * 0.04), (bx + w, by - r * 0.04),
               (bx, by + r * 0.50)], fill=col + (255,))


def _badge_folder(d: ImageDraw.ImageDraw, S: int, col):
    """폴더용 — 탭이 달린 폴더. 몸통과 탭을 나눠 그려야 폴더로 읽힌다."""
    bx, by, r = _badge_plate(d, S, col)
    w, h = r * 1.06, r * 0.80
    x0, y0 = bx - w / 2, by - h / 2
    rr = max(1.0, r * 0.10)
    # 탭 (왼쪽 위)
    d.rounded_rectangle([x0, y0, x0 + w * 0.46, y0 + h * 0.34],
                        radius=rr, fill=col + (255,))
    # 몸통
    d.rounded_rectangle([x0, y0 + h * 0.20, x0 + w, y0 + h],
                        radius=rr, fill=col + (255,))
    # 뚜껑 선 — 납작한 사각형으로 안 보이게 한 칸 판다
    d.line([(x0 + w * 0.10, y0 + h * 0.46), (x0 + w * 0.90, y0 + h * 0.46)],
           fill=NAVY_DEEP + (200,), width=max(1, round(S * 0.012)))


def draw(size: int, accent, badge: str | None = None) -> Image.Image:
    S = size * SS
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # 바탕: 둥근 사각형 + 중심이 살짝 밝은 그라데이션
    pad = S * 0.035
    d.rounded_rectangle([pad, pad, S - pad, S - pad],
                        radius=S * 0.215, fill=NAVY_DEEP + (255,))
    inner = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    di = ImageDraw.Draw(inner)
    steps = 26
    for i in range(steps, 0, -1):
        t = i / steps
        rad = S * 0.5 * t
        di.ellipse([S / 2 - rad, S / 2 - rad, S / 2 + rad, S / 2 + rad],
                   fill=lerp(NAVY_DEEP, NAVY, 1 - t) + (round(26 * (1 - t) + 8),))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [pad, pad, S - pad, S - pad], radius=S * 0.215, fill=255)
    img = Image.alpha_composite(img, Image.composite(
        inner, Image.new("RGBA", (S, S), (0, 0, 0, 0)), mask))
    d = ImageDraw.Draw(img)

    # 아주 작을 때는 고리를 줄인다. 다 그리면 회색 덩어리가 된다.
    count = 2 if size <= 20 else 3 if size <= 32 else 5 if size <= 48 else 8
    _rings(d, S, accent, count, width=S * 0.026)
    img = _core(img, S, accent)

    if badge and size >= 32:
        d = ImageDraw.Draw(img)
        (_badge_arrow if badge == "arrow" else _badge_folder)(d, S, accent)

    # 테두리 한 줄 — 어두운 배경에서 아이콘 경계가 사라지지 않게
    ImageDraw.Draw(img).rounded_rectangle(
        [pad, pad, S - pad, S - pad], radius=S * 0.215,
        outline=lerp(accent, NAVY, 0.55) + (150,), width=max(1, round(S * 0.012)))

    return img.resize((size, size), Image.LANCZOS)


def build(name: str, accent, badge: str | None = None) -> Path:
    frames = [draw(s, accent, badge) for s in SIZES]
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.ico"
    # 크기마다 따로 그린 것을 그대로 담는다. sizes= 로 넘기면 PIL 이
    # 한 장을 축소해버려서 16px 이 뭉개진다.
    frames[-1].save(path, format="ICO", append_images=frames[:-1],
                    sizes=[(s, s) for s in SIZES])
    return path


def build_png(name: str, size: int, accent) -> Path:
    """브라우저 탭·설치형 앱이 쓰는 PNG. 배경을 채워 어떤 테마에서도 또렷하게."""
    OUT.mkdir(parents=True, exist_ok=True)
    img = draw(size, accent)
    path = OUT / f"{name}.png"
    img.save(path, "PNG", optimize=True)
    return path


def main() -> None:
    made = [
        build("studio", CYAN),                    # 작업실 — 대표 아이콘
        build("update", AMBER, badge="arrow"),    # 업데이트
        build("folder", SLATE, badge="folder"),   # 폴더
        # 브라우저 탭과 [앱으로 설치] 용
        build_png("app-32", 32, CYAN),
        build_png("app-192", 192, CYAN),
        build_png("app-512", 512, CYAN),
    ]
    for p in made:
        print(f"  {p.relative_to(Path(__file__).parent.parent)}  "
              f"{p.stat().st_size / 1024:.1f} KB")

    # 눈으로 확인할 미리보기 (여러 크기를 한 장에)
    show = (256, 48, 32, 24, 16)
    pad, gap = 18, 16
    w = pad * 2 + sum(show) + gap * (len(show) - 1)
    sheet = Image.new("RGB", (w, pad * 2 + (256 + gap) * 3 - gap), (28, 28, 34))
    for row, (name, accent, badge) in enumerate((
            ("studio", CYAN, None), ("update", AMBER, "arrow"),
            ("folder", SLATE, "folder"))):
        x, y = pad, pad + row * (256 + gap)
        for s in show:
            sheet.paste(draw(s, accent, badge), (x, y + (256 - s) // 2),
                        draw(s, accent, badge))
            x += s + gap
    sheet.save(OUT / "_preview.png")
    print(f"  brand/icons/_preview.png")


if __name__ == "__main__":
    main()
