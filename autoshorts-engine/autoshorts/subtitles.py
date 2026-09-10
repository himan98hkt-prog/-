"""쇼츠용 동적 ASS 자막 생성.

단어 타임스탬프를 짧은 큐(cue)로 묶고, 현재 발화 중인 단어를 노란색으로
강조하는 ASS 파일을 만든다. FFmpeg 의 ``subtitles`` 필터로 하드서브
(번인) 렌더링하는 것을 전제로 한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

from .config import SubtitleStyle
from .models import Segment, Transcript, Word, format_ass_timestamp
from .utils import ensure_dir

__all__ = [
    "Cue",
    "chunk_words",
    "wrap_text",
    "escape_ass_text",
    "build_ass",
    "words_from_segments",
    "write_clip_subtitles",
]

# 큐가 끊길 만한 침묵 길이(초)
DEFAULT_MAX_GAP = 0.8
# 큐 표시가 너무 짧아 깜빡이지 않도록 하는 최소 노출 시간
MIN_CUE_DURATION = 0.35


@dataclass
class Cue:
    """화면에 한 번에 띄우는 자막 한 덩어리."""

    words: list[Word] = field(default_factory=list)

    @property
    def start(self) -> float:
        return self.words[0].start if self.words else 0.0

    @property
    def end(self) -> float:
        return self.words[-1].end if self.words else 0.0

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words).strip()

    @property
    def duration(self) -> float:
        return round(self.end - self.start, 3)


def escape_ass_text(text: str) -> str:
    """ASS 본문에서 특수 의미를 갖는 문자를 무력화한다."""
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace("{", "\\{")
        .replace("}", "\\}")
        .replace("\r\n", "\\N")
        .replace("\n", "\\N")
    )


def wrap_text(text: str, max_chars: int) -> str:
    """``max_chars`` 기준으로 줄바꿈(``\\N``)을 넣는다.

    공백 단위로 채우되, 한 단어가 기준보다 길면 그 단어는 자르지 않는다.
    """
    if max_chars <= 0 or not text:
        return text
    words = text.split()
    if not words:
        return text
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > max_chars:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return "\\N".join(lines)


def chunk_words(
    words: Sequence[Word],
    *,
    max_chars: int = 14,
    max_words: int = 6,
    max_duration: float = 2.4,
    max_gap: float = DEFAULT_MAX_GAP,
) -> list[Cue]:
    """단어 목록을 읽기 좋은 크기의 큐로 묶는다.

    글자 수/단어 수/노출 시간 중 하나라도 한계를 넘거나, 단어 사이 침묵이
    ``max_gap`` 을 넘으면 큐를 끊는다. 문장 종결 부호에서도 끊는다.
    """
    cues: list[Cue] = []
    current: list[Word] = []

    def flush() -> None:
        nonlocal current
        if current:
            cues.append(Cue(words=list(current)))
            current = []

    for word in words:
        if not word.text.strip():
            continue
        if current:
            gap = word.start - current[-1].end
            pending_chars = len(" ".join(w.text for w in current)) + 1 + len(word.text)
            pending_span = word.end - current[0].start
            if (
                gap > max_gap
                or len(current) >= max_words
                or (max_chars > 0 and pending_chars > max_chars * 2)
                or pending_span > max_duration
            ):
                flush()
        current.append(word)
        if word.text.strip()[-1:] in {".", "?", "!", "。", "？", "！"}:
            flush()
    flush()
    return cues


def _ass_bool(value: bool) -> str:
    return "-1" if value else "0"


def _header(style: SubtitleStyle, width: int, height: int) -> str:
    return "\n".join(
        [
            "[Script Info]",
            "; AutoShorts-Engine 이 생성한 쇼츠 자막",
            "ScriptType: v4.00+",
            "WrapStyle: 2",
            "ScaledBorderAndShadow: yes",
            "YCbCr Matrix: TV.709",
            f"PlayResX: {width}",
            f"PlayResY: {height}",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
            "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
            "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            (
                f"Style: Shorts,{style.font_name},{style.font_size},{style.primary_color},"
                f"{style.highlight_color},{style.outline_color},{style.back_color},"
                f"{_ass_bool(style.bold)},0,0,0,100,100,0,0,1,{style.outline:g},{style.shadow:g},"
                f"{style.alignment},{style.margin_h},{style.margin_h},{style.margin_v},1"
            ),
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]
    )


def _dialogue(start: float, end: float, text: str) -> str:
    return (
        f"Dialogue: 0,{format_ass_timestamp(start)},{format_ass_timestamp(end)},"
        f"Shorts,,0,0,0,,{text}"
    )


def _cue_lines_plain(cue: Cue, style: SubtitleStyle) -> list[str]:
    text = cue.text.upper() if style.uppercase else cue.text
    body = wrap_text(escape_ass_text(text), style.max_chars_per_line)
    end = max(cue.end, cue.start + MIN_CUE_DURATION)
    return [_dialogue(cue.start, end, body)]


def _cue_lines_highlight(cue: Cue, style: SubtitleStyle) -> list[str]:
    """단어별로 이벤트를 쪼개 현재 단어만 강조색으로 칠한다."""
    lines: list[str] = []
    tokens = [w.text.upper() if style.uppercase else w.text for w in cue.words]
    for index, word in enumerate(cue.words):
        start = word.start if index else cue.start
        end = cue.words[index + 1].start if index + 1 < len(cue.words) else max(
            cue.end, cue.start + MIN_CUE_DURATION
        )
        if end <= start:
            continue
        parts: list[str] = []
        for position, token in enumerate(tokens):
            escaped = escape_ass_text(token)
            if position == index:
                parts.append(
                    "{" + f"\\c{style.highlight_color}\\fscx108\\fscy108" + "}"
                    + escaped
                    + "{" + f"\\c{style.primary_color}\\fscx100\\fscy100" + "}"
                )
            else:
                parts.append(escaped)
        body = _wrap_tagged(parts, style.max_chars_per_line)
        lines.append(_dialogue(start, end, body))
    return lines


def _wrap_tagged(parts: Sequence[str], max_chars: int) -> str:
    """태그가 섞인 토큰 목록을 보이는 글자 수 기준으로 줄바꿈한다."""
    if max_chars <= 0:
        return " ".join(parts)
    lines: list[str] = []
    current: list[str] = []
    current_len = 0
    for part in parts:
        visible = _visible_length(part)
        if current and current_len + 1 + visible > max_chars:
            lines.append(" ".join(current))
            current, current_len = [part], visible
        else:
            current.append(part)
            current_len += (1 if current_len else 0) + visible
    if current:
        lines.append(" ".join(current))
    return "\\N".join(lines)


def _visible_length(part: str) -> int:
    """``{...}`` 오버라이드 태그를 뺀 실제 표시 길이."""
    out = []
    depth = 0
    index = 0
    while index < len(part):
        char = part[index]
        if char == "\\" and index + 1 < len(part) and part[index + 1] in "{}":
            out.append(part[index + 1])
            index += 2
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth = max(0, depth - 1)
        elif depth == 0:
            out.append(char)
        index += 1
    return len("".join(out))


def build_ass(
    words: Iterable[Word],
    style: SubtitleStyle | None = None,
    *,
    width: int = 1080,
    height: int = 1920,
    offset: float = 0.0,
) -> str:
    """단어 목록으로 ASS 자막 전체 문자열을 만든다.

    ``offset`` 은 클립 시작 시각. 클립 기준(0초 시작)으로 시간축을 옮긴다.
    """
    style = style or SubtitleStyle()
    shifted = [w.shifted(offset) for w in words if w.text.strip()]
    shifted = [Word(max(0.0, w.start), max(0.0, w.end), w.text, w.probability) for w in shifted]
    cues = chunk_words(
        shifted,
        max_chars=style.max_chars_per_line,
        max_words=style.max_words_per_cue,
        max_duration=style.max_cue_duration,
    )
    lines = [_header(style, width, height)]
    for cue in cues:
        if not cue.text:
            continue
        if style.highlight_active_word and len(cue.words) > 1:
            lines.extend(_cue_lines_highlight(cue, style))
        else:
            lines.extend(_cue_lines_plain(cue, style))
    return "\n".join(lines) + "\n"


def words_from_segments(segments: Iterable[Segment]) -> list[Word]:
    """세그먼트 목록을 단어 목록으로 편다."""
    out: list[Word] = []
    for segment in segments:
        out.extend(segment.words)
    return out


def write_clip_subtitles(
    transcript: Transcript,
    start: float,
    end: float,
    destination: str | Path,
    style: SubtitleStyle | None = None,
    *,
    width: int = 1080,
    height: int = 1920,
) -> Path:
    """클립 구간에 해당하는 ASS 파일을 저장하고 경로를 돌려준다."""
    destination = Path(destination)
    ensure_dir(destination.parent)
    segments = transcript.slice(start, end)
    words = words_from_segments(segments)
    content = build_ass(words, style, width=width, height=height, offset=start)
    destination.write_text(content, encoding="utf-8")
    return destination
