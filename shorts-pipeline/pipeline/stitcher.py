"""클립들을 하나의 세로 영상으로 합성한다.

chain 모드   : 경계마다 xfade 크로스페이드. 이음매를 눈에 덜 띄게 한다.
montage 모드 : 하드 컷(concat) 또는 짧은 fade.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import look
from .ffmpeg_util import FFmpegError, duration_of, fps_of, has_audio, run


@dataclass
class StitchResult:
    path: Path
    duration: float
    size_bytes: int
    fps: int = 0

    @property
    def size_mb(self) -> float:
        return self.size_bytes / (1024 * 1024)


# 클립들이 서로 다른 프레임률일 때 고를 후보. 여기 없는 값이면 최댓값을 쓴다.
COMMON_FPS = (24, 25, 30, 50, 60)
FALLBACK_FPS = 30


def resolve_fps(clips: list[Path], wanted) -> int:
    """실제로 쓸 프레임률을 정한다.

    **왜 'auto' 가 기본인가.** 예전에는 무조건 30 으로 맞췄다. 그런데 영상
    모델이 25fps 를 준다. 25 짜리를 30 으로 올리면 ffmpeg 은 없는 프레임을
    만들어내지 못하고 **5장마다 한 장을 복제**한다. 4초 클립에서 재어 보니
    120장 중 20장이 복제본이었다 — 1초에 6번, 눈에 보이는 떨림이다.
    끊김 없이 앞으로 나아가는 화면에서는 특히 잘 보인다.

    그래서 모델이 준 프레임률을 그대로 쓴다. 유튜브 Shorts 도 인스타
    릴스도 24~60fps 를 그대로 받는다. 올릴 이유가 없다.
    """
    if not (isinstance(wanted, str) and wanted.strip().lower() == "auto"):
        try:
            return max(1, int(wanted))
        except (TypeError, ValueError):
            return FALLBACK_FPS

    rates = []
    for clip in clips:
        try:
            value = fps_of(clip)
        except (FFmpegError, OSError):
            value = None
        if value:
            rates.append(round(value, 3))
    if not rates:
        return FALLBACK_FPS

    # 소수점 프레임률(29.97 등)은 가장 가까운 표준값으로 붙인다.
    def snap(value: float) -> int:
        near = min(COMMON_FPS, key=lambda c: abs(c - value))
        return near if abs(near - value) <= 0.5 else int(round(value))

    snapped = {snap(r) for r in rates}
    # 섞여 있으면 가장 높은 것에 맞춘다. 낮추면 프레임을 버리게 된다.
    return max(snapped)


def stitch(
    clips: list[Path],
    dest: Path,
    *,
    width: int = 1080,
    height: int = 1920,
    fps: int | str = "auto",
    crf: int = 18,
    crossfade: float = 0.3,
    transition: str = "fade",
    audio: str = "silent",
    audio_file: str | None = None,
    hook: str = "",
    hook_seconds: float = 0.0,
    hook_font: str | None = None,
    hook_font_size: int = 0,
    grade: str = "none",
    logo: str = "",
    logo_height: int = 64,
    logo_margin: int = 36,
    logo_opacity: float = 0.55,
) -> StitchResult:
    """clips 를 순서대로 이어붙여 dest 에 쓴다.

    transition: "cut"(하드 컷) 또는 xfade 트랜지션 이름("fade", "fadeblack" 등).

    훅 자막·색보정·로고는 **한 번의 인코딩 안에서** 같이 처리한다. 따로
    한 번 더 돌리면 그만큼 다시 압축돼 화질이 깎인다.
    """
    if not clips:
        raise FFmpegError("합성할 클립이 없습니다.")
    missing = [c for c in clips if not c.exists() or c.stat().st_size == 0]
    if missing:
        raise FFmpegError(
            "다음 클립이 비었거나 없습니다: " + ", ".join(p.name for p in missing)
        )

    dest.parent.mkdir(parents=True, exist_ok=True)
    fps = resolve_fps(clips, fps)
    scale_chain = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},fps={fps},setsar=1,format=yuv420p"
    )

    if len(clips) == 1 or transition == "cut" or crossfade <= 0:
        filter_complex, last_label = _concat_graph(clips, scale_chain)
    else:
        filter_complex, last_label = _xfade_graph(
            clips, scale_chain, crossfade, transition
        )

    # 색보정 -> 훅 자막 -> 로고 순서. 색보정을 자막 뒤에 두면 글씨 색까지
    # 같이 물든다.
    post = [f for f in (look.grade_filter(grade),
                        look.hook_filter(hook, seconds=hook_seconds, height=height,
                                         font=hook_font, font_size=hook_font_size,
                                         width=width))
            if f]
    if post:
        filter_complex += f";[{last_label}]" + ",".join(post) + "[styled]"
        last_label = "styled"

    args = ["ffmpeg", "-v", "error", "-stats"]
    for c in clips:
        args += ["-i", str(c)]

    logo_args = look.logo_inputs(logo)
    args += logo_args

    audio_args, audio_map, audio_graph = _audio_args(
        audio, audio_file, len(clips) + (1 if logo_args else 0),
        _total_seconds(clips, crossfade, transition))
    args += audio_args

    # 로고는 영상 입력 다음, 소리 입력 앞이다. 번호를 그렇게 잡아야 한다.
    if logo_args:
        filter_complex += ";" + look.logo_filter(
            len(clips), height=logo_height, margin=logo_margin,
            opacity=logo_opacity, video_label=last_label, out_label="branded")
        last_label = "branded"

    if audio_graph:
        filter_complex = f"{filter_complex};{audio_graph}"
    args += [
        "-filter_complex", filter_complex,
        "-map", f"[{last_label}]",
        *audio_map,
        "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
        "-shortest", "-y", str(dest),
    ]
    run(args, desc="최종 합성")

    if not dest.exists() or dest.stat().st_size == 0:
        raise FFmpegError("합성은 끝났는데 출력 파일이 비어 있습니다.")
    return StitchResult(dest, duration_of(dest), dest.stat().st_size, fps)


def _concat_graph(clips: list[Path], scale_chain: str) -> tuple[str, str]:
    """하드 컷 이어붙이기."""
    parts = [f"[{i}:v]{scale_chain}[v{i}]" for i in range(len(clips))]
    inputs = "".join(f"[v{i}]" for i in range(len(clips)))
    parts.append(f"{inputs}concat=n={len(clips)}:v=1:a=0[outv]")
    return ";".join(parts), "outv"


def _xfade_graph(
    clips: list[Path], scale_chain: str, crossfade: float, transition: str
) -> tuple[str, str]:
    """xfade 를 누적 연결한다.

    offset 은 '지금까지 누적된 길이 - 크로스페이드' 다. 클립 길이를 가정하지 않고
    실제로 probe 한 값을 쓴다 — 모델이 요청한 길이를 정확히 지키지 않는 일이 잦다.
    """
    durations = [duration_of(c) for c in clips]
    shortest = min(durations)
    if crossfade >= shortest:
        raise FFmpegError(
            f"크로스페이드({crossfade}초)가 가장 짧은 클립({shortest:.2f}초)보다 "
            "짧아야 합니다. config 의 crossfade_seconds 를 줄이세요."
        )

    parts = [f"[{i}:v]{scale_chain}[v{i}]" for i in range(len(clips))]
    current = "v0"
    accumulated = durations[0]

    for i in range(1, len(clips)):
        offset = accumulated - crossfade
        label = "outv" if i == len(clips) - 1 else f"x{i}"
        parts.append(
            f"[{current}][v{i}]xfade=transition={transition}"
            f":duration={crossfade}:offset={offset:.4f}[{label}]"
        )
        current = label
        accumulated += durations[i] - crossfade

    return ";".join(parts), current


def _total_seconds(clips: list[Path], crossfade: float, transition: str) -> float:
    """합성 후 최종 길이. 크로스페이드만큼 겹치므로 단순 합이 아니다."""
    try:
        total = sum(duration_of(c) for c in clips)
    except FFmpegError:
        return 0.0
    if len(clips) > 1 and transition != "cut" and crossfade > 0:
        total -= crossfade * (len(clips) - 1)
    return max(0.0, total)


# 음악이 영상보다 크면 안 된다. 유튜브·인스타 권장 라우드니스에 맞춘다.
MUSIC_LUFS = -14.0
FADE_IN = 1.0
FADE_OUT = 1.6


def _audio_args(
    audio: str, audio_file: str | None, n_clips: int, total: float = 0.0
) -> tuple[list[str], list[str], str]:
    """오디오 입력·매핑·필터그래프를 만든다.

    Shorts / Reels 는 오디오 트랙이 없는 파일에서 종종 문제를 일으키므로
    기본값은 무음 트랙 삽입이다.

    음원을 쓸 때는 그냥 붙이지 않는다. 수노에서 받은 곡은 저마다 음량이
    달라서 어떤 편은 크고 어떤 편은 안 들린다. 라우드니스를 맞추고
    앞뒤로 페이드를 넣는다. 끊기듯 끝나는 소리는 이탈로 이어진다.
    """
    if audio == "file":
        if not audio_file:
            raise FFmpegError("output.audio 가 file 인데 output.audio_file 이 비었습니다.")
        path = Path(audio_file)
        if not path.exists():
            raise FFmpegError(f"음원 파일이 없습니다: {path}")

        # 길이를 모르면 예전 방식 그대로 간다. 필터를 걸지 않는다.
        # 무한 반복 입력을 필터그래프에 물리면 ffmpeg 이 그 스트림을 계속
        # 당겨 읽어 메모리가 GB 단위로 불어나고 끝나지 않는다. 실제로
        # 16초짜리 테스트에서 3.8GB 까지 올라가 멈췄다. -t 로 길이를
        # 못 박아 유한한 스트림으로 만들어야 한다.
        if total <= 0:
            return (["-stream_loop", "-1", "-i", str(path)],
                    ["-map", f"{n_clips}:a"], "")

        chain = [f"loudnorm=I={MUSIC_LUFS}:TP=-1.5:LRA=11",
                 "aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo",
                 f"afade=t=in:st=0:d={FADE_IN}"]
        if total > FADE_IN + FADE_OUT:
            chain.append(f"afade=t=out:st={total - FADE_OUT:.2f}:d={FADE_OUT}")
        graph = f"[{n_clips}:a]" + ",".join(chain) + "[aout]"
        # -t 는 -i 앞에 와야 입력 읽기 자체를 끊는다. 뒤에 두면 출력 옵션이 된다.
        return (["-stream_loop", "-1", "-t", f"{total:.3f}", "-i", str(path)],
                ["-map", "[aout]"], graph)

    # 무음 트랙
    return (
        ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"],
        ["-map", f"{n_clips}:a"],
        "",
    )
