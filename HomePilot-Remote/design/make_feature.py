"""플레이스토어 대표 이미지(1024x500) 생성.

배경: 로컬 ComfyUI(Flux schnell)로 만든 design/concepts/flux_feature_bg.png
글꼴: Noto Sans KR (SIL OFL — 상업적 사용 가능)

    python design/make_feature.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONT = "C:/Windows/Fonts/NotoSansKR-VF.ttf"


def font(size, weight):
    f = ImageFont.truetype(FONT, size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


def main():
    bg = Image.open(ROOT / "design/concepts/flux_feature_bg.png").convert("RGBA")
    # 1024x512 → 1024x500 (위아래 6px 잘라냄)
    bg = bg.resize((1024, 512), Image.LANCZOS).crop((0, 6, 1024, 506))
    # 글씨 읽기 쉽게 왼쪽 위를 살짝 어둡게
    # 배경의 휴대폰(왼쪽 아래)·모니터(오른쪽)를 가리지 않도록 제목은 위쪽, 기능 소개는 아래쪽 띠에
    shade = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    sd.rounded_rectangle([24, 20, 600, 156], radius=26, fill=(20, 12, 60, 150))
    sd.rectangle([0, 440, 1024, 500], fill=(16, 10, 50, 170))
    bg.alpha_composite(shade.filter(ImageFilter.GaussianBlur(5)))

    logo = Image.open(ROOT / "design/store/app_icon_512.png").convert("RGBA").resize((104, 104), Image.LANCZOS)
    bg.alpha_composite(logo, (40, 36))
    d = ImageDraw.Draw(bg)
    d.text((164, 30), "HomePilot", font=font(56, 800), fill=(255, 255, 255))
    d.text((166, 100), "집 PC 를 내 손안에", font=font(28, 600), fill=(220, 240, 255))
    line = "원격 화면 · 키보드·마우스 · PC 상태 · 종단간 암호화"
    f = font(22, 500)
    w = d.textlength(line, font=f)
    d.text(((1024 - w) / 2, 452), line, font=f, fill=(240, 240, 255))
    out = ROOT / "design/store/feature_graphic_1024x500.png"
    bg.convert("RGB").save(out)
    print(out.relative_to(ROOT))


if __name__ == "__main__":
    main()
