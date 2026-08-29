"""영상에 채널의 얼굴을 입히는 것들 — 훅 자막 · 색보정 · 로고 · 무한 루프.

전부 ffmpeg 으로 끝난다. **모델 호출이 없으니 비용은 0원이다.**
그런데 효과는 생성 파라미터를 바꾸는 것 못지않다.

  훅 자막   첫 1~3초에 이탈이 결정된다. 훅 문구는 이미 쓰고 있는데
            인스타 캡션에만 나가고 정작 영상 안에는 안 들어가 있었다.
  무한 루프 끝을 첫 장면으로 이어 붙인다. Shorts 는 반복 재생이 조회수로
            잡힌다. 모델로 클립을 하나 더 사는 loop_back($0.49)과 달리 공짜다.
  채널 룩   일정한 색보정과 구석 로고. 스크롤하다가 "이 채널이구나" 가
            되는 지점이다.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from .ffmpeg_util import FFmpegError, duration_of, run

# 한글이 나오는 폰트. 위에서부터 있는 것을 쓴다.
#
# 리눅스 경로만 박아두면 **윈도우에서 한글이 통째로 깨진다.** 실제로
# brand/make_assets.py 가 그 상태였다 — 폰트를 못 찾으면 기본 비트맵으로
# 떨어져서 프로필 이미지의 한글이 뭉개진다.
FONT_CANDIDATES = (
    # 윈도우
    r"C:\Windows\Fonts\malgunbd.ttf",
    r"C:\Windows\Fonts\malgun.ttf",
    # macOS
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/Library/Fonts/AppleGothic.ttf",
    # 리눅스
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
)

# 색보정 프리셋. 과하게 잡으면 원본이 상한다 — 눈에 겨우 보일 만큼만.
GRADES: dict[str, str] = {
    "none": "",
    # 따뜻하게. 노을·불빛·골목에 어울린다.
    "warm": "eq=contrast=1.06:saturation=1.10,colorbalance=rs=.04:gs=.01:bs=-.04",
    # 차갑게. 얼음·우주·심해.
    "cool": "eq=contrast=1.06:saturation=1.06,colorbalance=rs=-.04:gs=0:bs=.05",
    # 시네마 느낌. 대비를 올리고 채도를 살짝 내린다.
    "cinema": "eq=contrast=1.12:saturation=0.94:gamma=0.97,"
              "colorbalance=rs=-.02:bs=.03",
}

GRADE_LABEL = {
    "none": "그대로",
    "warm": "따뜻하게",
    "cool": "차갑게",
    "cinema": "시네마",
}


def find_font(explicit: str = "") -> str | None:
    """한글이 나오는 폰트 경로. 못 찾으면 None."""
    if explicit and Path(explicit).exists():
        return explicit
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return path
    # 마지막 수단: fontconfig 에 물어본다 (리눅스/맥)
    if shutil.which("fc-match"):
        try:
            import subprocess
            out = subprocess.run(["fc-match", "-f", "%{file}", ":lang=ko"],
                                 capture_output=True, text=True, timeout=5)
            found = out.stdout.strip()
            if found and Path(found).exists():
                return found
        except (OSError, subprocess.SubprocessError):
            pass
    return None


def _escape(text: str) -> str:
    """drawtext 는 콜론·작은따옴표·역슬래시·퍼센트를 특별하게 읽는다."""
    out = text.replace("\\", "\\\\")
    for ch in (":", "'", "%", ",", "[", "]", ";"):
        out = out.replace(ch, "\\" + ch)
    return out


def _font_arg(path: str) -> str:
    """윈도우 경로의 역슬래시와 드라이브 콜론을 필터그래프용으로 바꾼다."""
    return path.replace("\\", "/").replace(":", "\\:")


def measure(text: str, font: str, size: int) -> int:
    """이 폰트·크기로 그렸을 때 글자 폭(픽셀). 못 재면 어림값.

    어림값은 한글을 1.0, 나머지를 0.55 로 잡는다. 실제로 재는 쪽이 훨씬
    정확해서 PIL 이 있으면 그쪽을 먼저 쓴다.
    """
    try:
        from PIL import ImageFont
        for index in (1, 0):     # CJK TTC 안에서 KR 이 1번인 경우가 많다
            try:
                f = ImageFont.truetype(font, size, index=index)
            except OSError:
                continue
            if index == 0 or f.getbbox("한") != (0, 0, 0, 0):
                return round(f.getlength(text))
    except Exception:          # noqa: BLE001 — 재기 실패는 어림값으로 넘어간다
        pass
    wide = sum(1 for ch in text if ord(ch) > 0x2E80)
    return round(size * (wide + (len(text) - wide) * 0.55))


def wrap(text: str, *, font: str, size: int, max_width: int,
         max_lines: int = 2) -> tuple[list[str], int]:
    """폭에 맞게 줄을 나누고, 그래도 넘치면 글자를 줄인다.

    이걸 안 하면 긴 훅이 **화면 밖으로 잘린다.** 실제로 270px 폭에서
    "이 길 끝에 뭐가 있을까" 가 양쪽 다 잘려 나갔다.
    """
    words = text.split()
    if not words:
        return [], size

    for _ in range(12):                      # 크기를 줄여가며 최대 12번 시도
        lines, current = [], ""
        for word in words:
            trial = f"{current} {word}".strip()
            if current and measure(trial, font, size) > max_width:
                lines.append(current)
                current = word
            else:
                current = trial
        if current:
            lines.append(current)
        too_wide = any(measure(ln, font, size) > max_width for ln in lines)
        if len(lines) <= max_lines and not too_wide:
            return lines, size
        if size <= 14:
            break
        size = max(14, round(size * 0.88))
    return lines[:max_lines], size


def hook_filter(text: str, *, seconds: float, height: int,
                font: str | None, font_size: int = 0, width: int = 0) -> str:
    """앞 몇 초에 훅 문구를 큰 글씨로. 못 그리면 빈 문자열(그냥 건너뛴다)."""
    text = " ".join((text or "").split())
    if not text or seconds <= 0:
        return ""
    if font is None:
        return ""

    size = font_size or max(34, round(height * 0.042))
    # 좌우 7% 는 비워 둔다. 꽉 채우면 잘려 보인다.
    frame_w = width or round(height * 9 / 16)
    lines, size = wrap(text, font=font, size=size,
                       max_width=round(frame_w * 0.86))
    if not lines:
        return ""
    text = "\n".join(lines)
    fade = min(0.4, seconds / 4)
    hold = max(0.1, seconds - fade)
    # 아래에서 1/4 되는 지점. 얼굴이나 중심 피사체를 가리지 않는다.
    y = "h-h/4-text_h"
    return (
        f"drawtext=text='{_escape(text)}'"
        f":line_spacing={max(4, size // 5)}"
        f":fontfile='{_font_arg(font)}'"
        f":fontsize={size}:fontcolor=white"
        f":borderw={max(2, size // 16)}:bordercolor=black@0.85"
        f":box=1:boxcolor=black@0.35:boxborderw={size // 3}"
        f":x=(w-text_w)/2:y={y}"
        f":enable='between(t,0,{seconds:.2f})'"
        f":alpha='if(lt(t,{fade:.2f}),t/{fade:.2f},"
        f"if(lt(t,{hold:.2f}),1,max(0,({seconds:.2f}-t)/{fade:.2f})))'"
    )


def logo_inputs(logo: str) -> list[str]:
    """로고를 쓸 때 ffmpeg 에 더할 입력 인자."""
    return ["-i", str(logo)] if logo and Path(logo).exists() else []


def logo_filter(index: int, *, height: int, margin: int, opacity: float,
                video_label: str, out_label: str) -> str:
    """구석에 로고. index 는 ffmpeg 입력 번호."""
    op = max(0.05, min(1.0, opacity))
    return (
        f"[{index}:v]scale=-1:{height},format=rgba,"
        f"colorchannelmixer=aa={op:.2f}[lg];"
        f"[{video_label}][lg]overlay=W-w-{margin}:{margin}[{out_label}]"
    )


def grade_filter(name: str) -> str:
    return GRADES.get((name or "none").strip().lower(), "")


def make_seamless(path: Path, *, overlap: float, crf: int, fps: int) -> float:
    """끝을 첫 장면으로 이어 붙여 반복 재생이 자연스럽게 만든다.

    **어떻게 이어지는가.** 길이 D 짜리 영상의 마지막 L 초를 떼어 맨 앞에
    겹쳐 넣고, 그 구간에서 원본 앞부분으로 서서히 넘긴다.

        결과[0]    = 원본[D-L]      (떼어낸 꼬리의 첫 장면)
        결과[끝]   = 원본[D-L]      (앞부분의 마지막 장면)

    시작과 끝이 **같은 장면**이 된다. 그래서 다시 재생될 때 튀지 않는다.
    길이는 L 초 짧아진다.

    모델로 클립을 하나 더 사서 첫 프레임으로 돌아오게 하는 방법(loop_back)
    도 있지만 그건 $0.49 다. 이건 0원이다.
    """
    total = duration_of(path)
    if overlap <= 0 or total <= overlap * 3:
        raise FFmpegError(
            f"루프 겹침({overlap}초)이 영상 길이({total:.1f}초)에 비해 큽니다. "
            "seamless_loop.seconds 를 줄이세요."
        )

    head_start = total - overlap
    tmp = path.with_name(path.stem + "_loop.mp4")
    graph = (
        f"[0:v]trim=start={head_start:.4f},setpts=PTS-STARTPTS[tail];"
        f"[0:v]trim=end={head_start:.4f},setpts=PTS-STARTPTS[main];"
        f"[tail][main]xfade=transition=fade:duration={overlap:.4f}:offset=0[outv]"
    )
    args = ["ffmpeg", "-v", "error", "-i", str(path),
            "-filter_complex", graph, "-map", "[outv]"]
    # 소리가 있으면 영상과 같은 길이로 잘라 붙인다.
    if _has_audio(path):
        args += ["-map", "0:a", "-c:a", "aac", "-b:a", "128k", "-shortest"]
    args += ["-r", str(fps), "-c:v", "libx264", "-preset", "medium",
             "-crf", str(crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart",
             "-y", str(tmp)]
    run(args, desc="무한 루프 잇기")
    if not tmp.exists() or tmp.stat().st_size == 0:
        raise FFmpegError("루프 처리 결과가 비어 있습니다.")
    os.replace(tmp, path)
    return duration_of(path)


def _has_audio(path: Path) -> bool:
    from .ffmpeg_util import has_audio
    try:
        return has_audio(path)
    except (FFmpegError, OSError):
        return False


def describe(cfg: dict) -> str:
    """지금 설정을 한 줄로. 화면과 콘솔에서 같은 문장을 쓴다."""
    bits = []
    hook = cfg.get("hook_overlay") or {}
    if hook.get("enabled"):
        bits.append(f"훅 자막 {float(hook.get('seconds', 2.2)):.1f}초")
    loop = cfg.get("seamless_loop") or {}
    if loop.get("enabled"):
        bits.append(f"무한 루프 {float(loop.get('seconds', 0.6)):.1f}초")
    look = cfg.get("look") or {}
    grade = (look.get("grade") or "none").lower()
    if grade != "none":
        bits.append(f"색보정 {GRADE_LABEL.get(grade, grade)}")
    if look.get("logo"):
        bits.append("로고")
    return " · ".join(bits) if bits else "없음"
