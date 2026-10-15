#!/usr/bin/env python3
"""앱 아이콘/스플래시 자리표시 이미지를 만든다.

디자이너 아트워크가 나오기 전까지 `expo start`/EAS 빌드가 깨지지 않게 하는 용도.
외부 라이브러리 없이 PNG 를 직접 인코딩한다.

사용법:  python3 tools/make_placeholder_assets.py
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

BG = (0xFF, 0xF9, 0xF4)
PAW = (0xFF, 0x8A, 0x3D)
ASSETS = Path(__file__).resolve().parent.parent / "assets"


def write_png(path: Path, width: int, height: int, pixels: list[bytearray]) -> None:
    raw = b"".join(b"\x00" + bytes(row) for row in pixels)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(png)


def blank(width: int, height: int) -> list[bytearray]:
    row = bytearray(BG * width)
    return [bytearray(row) for _ in range(height)]


def disc(pixels, cx: float, cy: float, r: float, color=PAW) -> None:
    """안티에일리어싱 없이 채운 원. 아이콘 크기에서는 충분히 매끈하다."""
    height, width = len(pixels), len(pixels[0]) // 3
    r2 = r * r
    for y in range(max(0, int(cy - r)), min(height, int(cy + r) + 1)):
        dy2 = (y - cy) ** 2
        for x in range(max(0, int(cx - r)), min(width, int(cx + r) + 1)):
            if (x - cx) ** 2 + dy2 <= r2:
                pixels[y][x * 3 : x * 3 + 3] = bytes(color)


def paw(pixels, cx: float, cy: float, scale: float) -> None:
    """발바닥 하나 + 발가락 넷."""
    disc(pixels, cx, cy + 0.30 * scale, 0.36 * scale)
    for dx, dy, r in ((-0.46, -0.22, 0.155), (-0.17, -0.46, 0.165), (0.17, -0.46, 0.165), (0.46, -0.22, 0.155)):
        disc(pixels, cx + dx * scale, cy + dy * scale, r * scale)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)

    for name, size in (("icon.png", 1024), ("adaptive-icon.png", 1024)):
        pixels = blank(size, size)
        # adaptive-icon 은 바깥 33% 가 잘릴 수 있어 안쪽에 작게 그린다
        scale = size * (0.42 if name == "icon.png" else 0.30)
        paw(pixels, size / 2, size / 2, scale)
        write_png(ASSETS / name, size, size, pixels)

    for name, (w, h) in (("splash.png", (1284, 2778)), ("favicon.png", (48, 48))):
        pixels = blank(w, h)
        paw(pixels, w / 2, h / 2, min(w, h) * 0.42)
        write_png(ASSETS / name, w, h, pixels)

    for f in sorted(ASSETS.iterdir()):
        print(f"{f.name}: {f.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
