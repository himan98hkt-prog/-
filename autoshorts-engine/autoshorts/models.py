"""파이프라인 전 구간에서 공유하는 데이터 모델.

무거운 서드파티 의존성 없이 순수 파이썬으로만 구성되어 있어
단위 테스트에서 그대로 다룰 수 있다.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

__all__ = [
    "Word",
    "Segment",
    "Transcript",
    "Clip",
    "format_srt_timestamp",
    "format_ass_timestamp",
]


def _round(value: float, digits: int = 3) -> float:
    return round(float(value), digits)


def format_srt_timestamp(seconds: float) -> str:
    """초 -> ``HH:MM:SS,mmm`` (SRT 규격)."""
    if seconds is None or math.isnan(seconds):
        seconds = 0.0
    seconds = max(0.0, float(seconds))
    millis = int(round(seconds * 1000))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def format_ass_timestamp(seconds: float) -> str:
    """초 -> ``H:MM:SS.cc`` (ASS 규격, 1/100초)."""
    if seconds is None or math.isnan(seconds):
        seconds = 0.0
    seconds = max(0.0, float(seconds))
    centis = int(round(seconds * 100))
    hours, centis = divmod(centis, 360_000)
    minutes, centis = divmod(centis, 6_000)
    secs, centis = divmod(centis, 100)
    return f"{hours:d}:{minutes:02d}:{secs:02d}.{centis:02d}"


@dataclass
class Word:
    """단어 단위 타임스탬프."""

    start: float
    end: float
    text: str
    probability: float | None = None

    def __post_init__(self) -> None:
        self.start = _round(self.start)
        self.end = _round(max(self.end, self.start))
        self.text = str(self.text)

    @property
    def duration(self) -> float:
        return _round(self.end - self.start)

    def shifted(self, offset: float) -> "Word":
        return Word(self.start - offset, self.end - offset, self.text, self.probability)

    def to_dict(self) -> dict[str, Any]:
        data = {"start": self.start, "end": self.end, "text": self.text}
        if self.probability is not None:
            data["probability"] = _round(self.probability, 4)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Word":
        return cls(
            start=data["start"],
            end=data["end"],
            text=data.get("text", data.get("word", "")),
            probability=data.get("probability"),
        )


@dataclass
class Segment:
    """문장(발화) 단위 타임스탬프."""

    start: float
    end: float
    text: str
    words: list[Word] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.start = _round(self.start)
        self.end = _round(max(self.end, self.start))
        self.text = str(self.text).strip()

    @property
    def duration(self) -> float:
        return _round(self.end - self.start)

    def overlaps(self, start: float, end: float) -> bool:
        return self.start < end and self.end > start

    def to_dict(self) -> dict[str, Any]:
        return {
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "words": [w.to_dict() for w in self.words],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Segment":
        return cls(
            start=data["start"],
            end=data["end"],
            text=data.get("text", ""),
            words=[Word.from_dict(w) for w in data.get("words", [])],
        )


@dataclass
class Transcript:
    """전사 결과 전체. ``transcription.json`` 의 직렬화 대상."""

    segments: list[Segment] = field(default_factory=list)
    language: str | None = None
    duration: float = 0.0
    source: str | None = None
    model: str | None = None

    def __post_init__(self) -> None:
        self.duration = _round(self.duration)
        if not self.duration and self.segments:
            self.duration = _round(max(s.end for s in self.segments))

    def __len__(self) -> int:
        return len(self.segments)

    def __iter__(self):
        return iter(self.segments)

    @property
    def text(self) -> str:
        return " ".join(s.text for s in self.segments if s.text).strip()

    def words(self) -> list[Word]:
        """세그먼트를 가로지르는 전체 단어 목록.

        단어 타임스탬프가 없는 세그먼트는 텍스트 길이 비율로 균등 분할해
        의사(pseudo) 단어를 만들어 자막 렌더링이 끊기지 않게 한다.
        """
        out: list[Word] = []
        for seg in self.segments:
            if seg.words:
                out.extend(seg.words)
            elif seg.text:
                out.extend(_synthesize_words(seg))
        return out

    def slice(self, start: float, end: float) -> list[Segment]:
        """``[start, end)`` 구간과 겹치는 세그먼트를 잘라서 반환."""
        out: list[Segment] = []
        for seg in self.segments:
            if not seg.overlaps(start, end):
                continue
            words = [w for w in (seg.words or _synthesize_words(seg)) if w.end > start and w.start < end]
            out.append(
                Segment(
                    start=max(seg.start, start),
                    end=min(seg.end, end),
                    text=seg.text,
                    words=words,
                )
            )
        return out

    def timestamped_text(self, max_chars: int | None = None) -> str:
        """AI 분석 프롬프트에 넣을 ``[초] 텍스트`` 형태의 본문."""
        lines = []
        for seg in self.segments:
            if not seg.text:
                continue
            lines.append(f"[{seg.start:.1f}-{seg.end:.1f}] {seg.text}")
        body = "\n".join(lines)
        if max_chars is not None and len(body) > max_chars:
            body = body[:max_chars].rsplit("\n", 1)[0] + "\n... (이하 생략)"
        return body

    def to_srt(self) -> str:
        blocks = []
        for i, seg in enumerate(self.segments, start=1):
            blocks.append(
                f"{i}\n{format_srt_timestamp(seg.start)} --> {format_srt_timestamp(seg.end)}\n{seg.text}\n"
            )
        return "\n".join(blocks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "duration": self.duration,
            "source": self.source,
            "model": self.model,
            "segments": [s.to_dict() for s in self.segments],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Transcript":
        return cls(
            segments=[Segment.from_dict(s) for s in data.get("segments", [])],
            language=data.get("language"),
            duration=data.get("duration", 0.0),
            source=data.get("source"),
            model=data.get("model"),
        )

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: str | Path) -> "Transcript":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def _synthesize_words(segment: Segment) -> list[Word]:
    """단어 타임스탬프가 없을 때 글자 수 비례로 나눈 의사 단어."""
    tokens = [t for t in re.split(r"(\s+)", segment.text) if t.strip()]
    if not tokens:
        return []
    total = sum(len(t) for t in tokens) or 1
    span = max(segment.duration, 0.001)
    out: list[Word] = []
    cursor = segment.start
    for token in tokens:
        width = span * (len(token) / total)
        out.append(Word(cursor, min(cursor + width, segment.end), token))
        cursor += width
    return out


@dataclass
class Clip:
    """AI가 선정한 하이라이트 한 구간."""

    start: float
    end: float
    title: str
    reason: str = ""
    score: float = 0.0
    index: int = 0

    def __post_init__(self) -> None:
        self.start = _round(max(0.0, self.start))
        self.end = _round(max(self.end, self.start))
        self.title = str(self.title).strip()
        self.reason = str(self.reason).strip()
        self.score = _round(self.score, 2)
        self.index = int(self.index)

    @property
    def duration(self) -> float:
        return _round(self.end - self.start)

    def output_filename(self, extension: str = "mp4", max_title_chars: int = 40) -> str:
        """``output_[클립번호]_[후킹제목].mp4`` 규격 파일명."""
        from .utils import sanitize_filename

        title = sanitize_filename(self.title, max_length=max_title_chars) or "highlight"
        return f"output_{self.index:02d}_{title}.{extension}"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["duration"] = self.duration
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Clip":
        return cls(
            start=_coerce_time(data.get("start_time", data.get("start"))),
            end=_coerce_time(data.get("end_time", data.get("end"))),
            title=data.get("title", ""),
            reason=data.get("reason", ""),
            score=_coerce_float(data.get("score", data.get("viral_score", 0.0))),
            index=int(data.get("index", 0) or 0),
        )


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_time(value: Any) -> float:
    """숫자, ``"83.5"``, ``"01:23"``, ``"00:01:23.500"`` 을 모두 초로 변환."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", ".")
    if not text:
        return 0.0
    if ":" in text:
        parts = text.split(":")
        try:
            numbers = [float(p) for p in parts]
        except ValueError:
            return 0.0
        total = 0.0
        for number in numbers:
            total = total * 60 + number
        return total
    return _coerce_float(text)


def clips_to_json(clips: Sequence[Clip]) -> str:
    return json.dumps([c.to_dict() for c in clips], ensure_ascii=False, indent=2)


def clips_from_iterable(items: Iterable[dict[str, Any]]) -> list[Clip]:
    return [Clip.from_dict(item) for item in items]
