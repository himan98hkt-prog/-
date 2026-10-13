"""HomePilot 아이콘 생성기 (벡터 도형 → PNG/ICO).

디자인 시안은 로컬 ComfyUI(Flux schnell)로 만들었고(design/concepts/), 작은 크기에서도
선명하도록 같은 디자인을 도형으로 다시 그린다. 외부 서비스·유료 도구를 쓰지 않는다.

    python design/make_icons.py          # HomePilot-Remote 폴더에서 실행

만드는 것
- android-app: 런처 아이콘(mipmap-*/ic_launcher.png, 둥근 버전), 적응형 아이콘 전경/배경/단색
- windows-agent/assets: 트레이 상태 아이콘(PNG 32px), 실행 파일 아이콘(.ico)
- design/store: 플레이스토어 앱 아이콘 512px
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
SS = 4  # 초과 표본(안티에일리어싱)

# 시안(icon_33) 색
TOP = (106, 61, 240)      # 보라
BOTTOM = (0, 214, 240)    # 청록
NAVY = (12, 28, 92)
SCREEN_TOP = (52, 110, 235)
SCREEN_BOTTOM = (24, 60, 190)
ROOF = (214, 246, 255)
WHITE = (255, 255, 255)


def gradient(size, top, bottom):
    g = Image.new("RGBA", (1, 256))
    for y in range(256):
        t = y / 255
        g.putpixel((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) + (255,))
    return g.resize((size, size), Image.BICUBIC)


def glyph(size, simple=False, mono=None):
    """지붕 + 모니터 + 커서. 크기 size 정사각형 안에 꽉 차게 그린다(투명 배경).
    simple: 16~24px 용 (받침대 생략, 선 굵게). mono: 단색으로 그릴 색."""
    S = size * SS
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    u = S / 100  # 100 단위 좌표계

    def P(x, y):
        return (x * u, y * u)

    navy = mono or NAVY
    roof = mono or ROOF
    stroke = (9 if simple else 7) * u
    # 지붕 (모니터 위로 튀어나온 꺾쇠)
    d.line([P(18, 36), P(50, 10), P(82, 36)], fill=roof, width=int(stroke), joint="curve")
    for x, y in [(18, 36), (50, 10), (82, 36)]:
        r = stroke / 2
        d.ellipse([x * u - r, y * u - r, x * u + r, y * u + r], fill=roof)
    # 모니터 테두리 + 화면
    mon = [P(12, 28), P(88, 78 if simple else 74)]
    d.rounded_rectangle([*mon[0], *mon[1]], radius=10 * u, fill=navy)
    inset = (6 if simple else 5) * u
    scr = [mon[0][0] + inset, mon[0][1] + inset, mon[1][0] - inset, mon[1][1] - inset]
    if mono:
        # 단색 아이콘: 화면은 비워서(투명) 커서만 보이게
        d.rounded_rectangle(scr, radius=6 * u, fill=(0, 0, 0, 0))
    else:
        sg = gradient(int(scr[3] - scr[1]), SCREEN_TOP, SCREEN_BOTTOM).resize((int(scr[2] - scr[0]), int(scr[3] - scr[1])))
        mask = Image.new("L", sg.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, sg.size[0] - 1, sg.size[1] - 1], radius=int(6 * u), fill=255)
        im.paste(sg, (int(scr[0]), int(scr[1])), mask)
    if not simple:
        # 받침대
        d.rectangle([*P(45, 74), *P(55, 82)], fill=navy)
        d.rounded_rectangle([*P(33, 82), *P(67, 88)], radius=3 * u, fill=navy)
    # 커서 (화면 중앙)
    cx, cy = (50, 50) if not simple else (50, 52)
    k = 1.25 if simple else 1.0
    arrow = [(0, 0), (0, 22), (6, 17), (10, 26), (14, 24), (10, 15.5), (17, 15.5)]
    pts = [P(cx - 7 * k + x * k, cy - 13 * k + y * k) for x, y in arrow]
    cursor_color = mono or WHITE
    if not mono:
        sh = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        ImageDraw.Draw(sh).polygon([(x + 1.2 * u, y + 1.6 * u) for x, y in pts], fill=(0, 0, 40, 110))
        im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(1.2 * u)))
    if mono:
        # 단색: 화면이 투명이므로 커서는 테두리 색으로
        d.polygon(pts, fill=cursor_color)
    else:
        ImageDraw.Draw(im).polygon(pts, fill=cursor_color)
    return im.resize((size, size), Image.LANCZOS)


def squircle_mask(size, radius_ratio=0.23):
    S = size * SS
    m = Image.new("L", (S, S), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * radius_ratio), fill=255)
    return m.resize((size, size), Image.LANCZOS)


def app_icon(size, shape="squircle", glyph_ratio=0.66, simple=False, top=TOP, bottom=BOTTOM, badge=None):
    """배경 + 기호. badge: 오른쪽 아래 상태 점 색 (트레이용)."""
    bg = gradient(size, top, bottom)
    if shape == "circle":
        S = size * SS
        m = Image.new("L", (S, S), 0)
        ImageDraw.Draw(m).ellipse([0, 0, S - 1, S - 1], fill=255)
        mask = m.resize((size, size), Image.LANCZOS)
    else:
        mask = squircle_mask(size, 0.23 if size > 32 else 0.18)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(bg, (0, 0), mask)
    g = int(size * glyph_ratio)
    out.alpha_composite(glyph(g, simple=simple), ((size - g) // 2, (size - g) // 2))
    if badge:
        S = size * SS
        b = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        bd = ImageDraw.Draw(b)
        r = S * 0.24
        c = (S - r - S * 0.02, S - r - S * 0.02)
        bd.ellipse([c[0] - r - S * 0.06, c[1] - r - S * 0.06, c[0] + r + S * 0.06, c[1] + r + S * 0.06], fill=(255, 255, 255, 255))
        bd.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], fill=badge)
        out.alpha_composite(b.resize((size, size), Image.LANCZOS))
    return out


def save(im, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path)
    print("  ", path.relative_to(ROOT))


def android():
    res = ROOT / "android-app/android/app/src/main/res"
    dens = {"mdpi": 1, "hdpi": 1.5, "xhdpi": 2, "xxhdpi": 3, "xxxhdpi": 4}
    for name, k in dens.items():
        s = int(48 * k)
        save(app_icon(s), res / f"mipmap-{name}/ic_launcher.png")
        save(app_icon(s, shape="circle", glyph_ratio=0.6), res / f"mipmap-{name}/ic_launcher_round.png")
        # 적응형 아이콘: 108dp 캔버스, 기호는 가운데 66dp(안전 영역) 안
        a = int(108 * k)
        fg = Image.new("RGBA", (a, a), (0, 0, 0, 0))
        g = int(a * 0.5)
        fg.alpha_composite(glyph(g), ((a - g) // 2, (a - g) // 2))
        save(fg, res / f"mipmap-{name}/ic_launcher_foreground.png")
        save(gradient(a, TOP, BOTTOM), res / f"mipmap-{name}/ic_launcher_background.png")
        mono = Image.new("RGBA", (a, a), (0, 0, 0, 0))
        mono.alpha_composite(glyph(g, mono=(255, 255, 255, 255)), ((a - g) // 2, (a - g) // 2))
        save(mono, res / f"mipmap-{name}/ic_launcher_monochrome.png")
    xml = """<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@mipmap/ic_launcher_background"/>
    <foreground android:drawable="@mipmap/ic_launcher_foreground"/>
    <monochrome android:drawable="@mipmap/ic_launcher_monochrome"/>
</adaptive-icon>
"""
    for n in ("ic_launcher", "ic_launcher_round"):
        p = res / "mipmap-anydpi-v26" / f"{n}.xml"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(xml, encoding="utf-8", newline="\n")
        print("  ", p.relative_to(ROOT))
    # 앱 안에서 쓰는 로고 (첫 화면 등)
    save(app_icon(512), ROOT / "android-app/assets/logo.png")


GRAY_TOP, GRAY_BOTTOM = (120, 128, 150), (78, 86, 108)
TRAY_STATES = {
    # 상태: (배경 위, 배경 아래, 상태 점)
    "online": (TOP, BOTTOM, None),
    "offline": (GRAY_TOP, GRAY_BOTTOM, None),
    "active": (TOP, BOTTOM, (255, 59, 48, 255)),     # 원격 접속 중: 빨간 점
    "blocked": (GRAY_TOP, GRAY_BOTTOM, (255, 149, 0, 255)),  # 차단: 주황 점
}


def windows():
    assets = ROOT / "windows-agent/assets"
    for state, (t, b, badge) in TRAY_STATES.items():
        for s in (16, 32):
            save(app_icon(s, glyph_ratio=0.86 if s == 16 else 0.78, simple=True, top=t, bottom=b, badge=badge), assets / f"tray_{state}_{s}.png")
    sizes = [16, 24, 32, 48, 64, 128, 256]
    imgs = [app_icon(s, simple=s <= 24, glyph_ratio=0.86 if s <= 24 else 0.7) for s in sizes]
    ico = assets / "homepilot.ico"
    imgs[-1].save(ico, sizes=[(s, s) for s in sizes], append_images=imgs[:-1])
    print("  ", ico.relative_to(ROOT))


def store():
    save(app_icon(512, glyph_ratio=0.62).convert("RGBA"), ROOT / "design/store/app_icon_512.png")
    # 크기별 미리보기
    sheet = Image.new("RGBA", (16 + 24 + 32 + 48 + 96 + 192 + 70, 200), (245, 245, 248, 255))
    x = 10
    for s in (16, 24, 32, 48, 96, 192):
        im = app_icon(s, simple=s <= 24, glyph_ratio=0.86 if s <= 24 else 0.66)
        sheet.alpha_composite(im, (x, 100 - s // 2))
        x += s + 10
    save(sheet, ROOT / "design/preview_sizes.png")
    tray = Image.new("RGBA", (4 * 48 + 50, 60), (32, 32, 36, 255))
    for i, st in enumerate(TRAY_STATES):
        im = Image.open(ROOT / f"windows-agent/assets/tray_{st}_32.png")
        tray.alpha_composite(im, (10 + i * 58, 14))
    save(tray, ROOT / "design/preview_tray.png")


if __name__ == "__main__":
    print("Android")
    android()
    print("Windows")
    windows()
    print("Store / 미리보기")
    store()
