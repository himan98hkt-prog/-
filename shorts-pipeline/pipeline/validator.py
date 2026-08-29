"""입력 이미지 검증 · 9:16 변환."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from .ffmpeg_util import FFmpegError

TARGET_RATIO = 9 / 16
MIN_WIDTH, MIN_HEIGHT = 720, 1280
_SUPPORTED = {".png", ".jpg", ".jpeg", ".webp"}


class ValidationError(Exception):
    pass


def prepare_input(
    src: str | Path,
    dest: Path,
    *,
    pad: bool = False,
    width: int = 1080,
    height: int = 1920,
) -> list[str]:
    """입력 이미지를 9:16 로 맞춰 dest 에 PNG 로 저장한다.

    pad=False 면 중앙 크롭, True 면 블러 패딩.
    반환값은 사용자에게 보여줄 경고 메시지 목록.
    """
    src = Path(src)
    if not src.exists():
        raise ValidationError(f"입력 이미지가 없습니다: {src}")
    if src.suffix.lower() not in _SUPPORTED:
        raise ValidationError(
            f"지원하지 않는 형식입니다: {src.suffix} "
            f"(지원: {', '.join(sorted(_SUPPORTED))})"
        )

    warnings: list[str] = []
    try:
        img = Image.open(src)
        img.load()
    except Exception as exc:  # PIL 이 던지는 예외 종류가 다양하다
        raise ValidationError(f"이미지를 열지 못했습니다: {src} ({exc})") from exc

    img = img.convert("RGB")
    w, h = img.size
    # 출력 크기보다 작으면 늘려서 쓰게 되고, 늘린 만큼 흐려진다.
    # 기준을 720x1280 으로 고정해 두었더니 미드저니 기본 출력(816x1456)이
    # 조용히 통과했다 — 1080x1920 으로 32% 늘어나는데 아무 말이 없었다.
    if w < width or h < height:
        short = round((1 - min(w / width, h / height)) * 100)
        warnings.append(
            f"⚠ 입력이 출력보다 작습니다 ({w}x{h} -> {width}x{height}, "
            f"{short}% 늘림). 늘린 만큼 흐려지고 체이닝에서 더 뭉개집니다.\n"
            f"     미드저니에서 U 버튼 -> Upscale 로 다시 받으면 좋아집니다."
        )
    elif w < MIN_WIDTH or h < MIN_HEIGHT:
        warnings.append(
            f"⚠ 입력 해상도가 낮습니다 ({w}x{h}). "
            f"{MIN_WIDTH}x{MIN_HEIGHT} 이상을 권장합니다 — 체이닝을 거치면 더 뭉개집니다."
        )

    ratio = w / h
    if abs(ratio - TARGET_RATIO) > 0.01:
        how = "블러 패딩" if pad else "중앙 크롭"
        warnings.append(f"입력이 9:16 이 아닙니다 ({w}x{h}, {ratio:.3f}). {how} 으로 변환합니다.")
        img = _pad_to_ratio(img, width, height) if pad else _crop_to_ratio(img)

    img = img.resize((width, height), Image.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, "PNG")
    return warnings


def _crop_to_ratio(img: Image.Image) -> Image.Image:
    w, h = img.size
    if w / h > TARGET_RATIO:      # 너무 넓다 → 좌우를 자른다
        new_w = round(h * TARGET_RATIO)
        left = (w - new_w) // 2
        return img.crop((left, 0, left + new_w, h))
    new_h = round(w / TARGET_RATIO)  # 너무 높다 → 위아래를 자른다
    top = (h - new_h) // 2
    return img.crop((0, top, w, top + new_h))


def _pad_to_ratio(img: Image.Image, width: int, height: int) -> Image.Image:
    """원본을 꽉 채운 블러 배경 위에 원본을 얹는다."""
    from PIL import ImageFilter

    bg = img.copy()
    scale = max(width / bg.width, height / bg.height)
    bg = bg.resize((round(bg.width * scale), round(bg.height * scale)), Image.LANCZOS)
    left = (bg.width - width) // 2
    top = (bg.height - height) // 2
    bg = bg.crop((left, top, left + width, top + height))
    bg = bg.filter(ImageFilter.GaussianBlur(radius=40))

    fg = img.copy()
    scale = min(width / fg.width, height / fg.height)
    fg = fg.resize((round(fg.width * scale), round(fg.height * scale)), Image.LANCZOS)
    bg.paste(fg, ((width - fg.width) // 2, (height - fg.height) // 2))
    return bg
