"""Phase 0 — 품질/성능 기준선 측정.

이 모듈은 "기능이 있느냐" 가 아니라 **결과물이 얼마나 쓸 만한가**를 숫자로
남기기 위한 것이다. Phase 4 이후 멀티모달 엔진을 붙였을 때 개선을 주장하려면
지금의 transcript-only 파이프라인 성능을 먼저 고정해 두어야 한다.

구성
----
1. :class:`BenchmarkSample` / :class:`SampleManifest`
   벤치마크 영상 목록과 사람이 지정한 gold moment 를 담는 선언적 스키마.
2. 품질 지표 (순수 함수)
   클립 목록과 전사본만 있으면 계산되므로 FFmpeg·네트워크 없이 테스트된다.
3. :class:`RunRecord` / :class:`BenchmarkReport`
   처리 시간·peak memory·출력 크기·성공률을 담는 측정 형식.

측정하지 못하는 것
------------------
``standalone comprehension`` 과 ``gold moment`` 지정은 본질적으로 사람의 판단이다.
여기서는 **대리 지표**(문맥 의존 표현으로 시작하는지)와 **사람 평가를 받아 적을
자리**를 함께 둔다. 대리 지표를 사람 평가로 둔갑시키지 않는다.
"""

from __future__ import annotations

import json
import re
import resource
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

from .models import Clip, Segment, Transcript
from .utils import ensure_dir, get_logger

__all__ = [
    "CONTENT_MODES",
    "RIGHTS_STATUSES",
    "GoldMoment",
    "BenchmarkSample",
    "SampleManifest",
    "StageTiming",
    "RunRecord",
    "BenchmarkReport",
    "QualityMetrics",
    "measure_quality",
    "mid_sentence_cut_rate",
    "duplicate_overlap_rate",
    "gold_acceptance",
    "context_dependency_flags",
    "peak_memory_mb",
    "track_stage",
]

LOG = get_logger("benchmark")

# COMPETITIVE_BENCHMARK_2026.md 의 콘텐츠 분포와 MASTER_V3 의 content_mode 를 맞춘다.
CONTENT_MODES = (
    "podcast", "lecture", "gaming", "sports", "news", "vlog", "auto",
)

# 권리 상태는 Phase 1 JobSpec 과 같은 어휘를 쓴다.
RIGHTS_STATUSES = ("owned", "licensed", "creative_commons", "unverified")

# 클립 경계가 발화 경계와 이만큼 이내로 붙어 있으면 "문장 경계에서 잘렸다" 로 본다.
BOUNDARY_TOLERANCE_SECONDS = 0.6

# 두 클립이 이보다 많이 겹치면 중복으로 센다. (ai_analyzer 의 허용치와 같은 값)
DUPLICATE_OVERLAP_SECONDS = 1.0

# gold moment 를 맞혔다고 인정할 최소 IoU.
GOLD_IOU_THRESHOLD = 0.5

# 문맥 없이는 이해하기 어려운 시작 표현. standalone 대리 지표에 쓴다.
_CONTEXT_DEPENDENT_OPENERS = (
    "그래서", "그런데", "근데", "그리고", "그러면", "그럼", "그게", "그건", "그거",
    "이게", "이건", "이거", "저게", "저건", "저거", "그래도", "하지만", "그러니까",
    "거기서", "여기서", "그때", "걔", "걔가", "얘", "얘가",
    "so", "but", "and", "then", "it", "that", "this", "he", "she", "they", "those",
)
_WORD_SPLIT = re.compile(r"\s+")


def _round(value: float, digits: int = 3) -> float:
    return round(float(value), digits)


# ── 1. 샘플 매니페스트 ─────────────────────────────────────


@dataclass
class GoldMoment:
    """사람이 "이 구간은 쇼츠감이다" 라고 지정한 정답 구간."""

    start: float
    end: float
    label: str = ""
    rationale: str = ""

    def __post_init__(self) -> None:
        self.start = _round(max(0.0, self.start))
        self.end = _round(max(self.end, self.start))

    @property
    def duration(self) -> float:
        return _round(self.end - self.start)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GoldMoment":
        return cls(
            start=float(data.get("start", 0.0)),
            end=float(data.get("end", 0.0)),
            label=data.get("label", ""),
            rationale=data.get("rationale", ""),
        )


@dataclass
class BenchmarkSample:
    """벤치마크 영상 한 편."""

    sample_id: str
    source: str                          # 로컬 경로 또는 URL
    content_mode: str = "auto"
    duration_seconds: float = 0.0
    rights_status: str = "unverified"
    language: str = ""
    notes: str = ""
    gold_moments: list[GoldMoment] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not str(self.sample_id).strip():
            raise ValueError("sample_id 는 비어 있을 수 없습니다.")
        if self.content_mode not in CONTENT_MODES:
            raise ValueError(
                f"content_mode 는 {CONTENT_MODES} 중 하나여야 합니다: {self.content_mode!r}"
            )
        if self.rights_status not in RIGHTS_STATUSES:
            raise ValueError(
                f"rights_status 는 {RIGHTS_STATUSES} 중 하나여야 합니다: {self.rights_status!r}"
            )
        self.duration_seconds = _round(self.duration_seconds)

    @property
    def needs_rights_confirmation(self) -> bool:
        """권리 확인 없이 렌더/게시로 넘기면 안 되는 소스인지."""
        return self.rights_status == "unverified"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["gold_moments"] = [g.to_dict() for g in self.gold_moments]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BenchmarkSample":
        return cls(
            sample_id=data["sample_id"],
            source=data.get("source", ""),
            content_mode=data.get("content_mode", "auto"),
            duration_seconds=float(data.get("duration_seconds", 0.0) or 0.0),
            rights_status=data.get("rights_status", "unverified"),
            language=data.get("language", ""),
            notes=data.get("notes", ""),
            gold_moments=[GoldMoment.from_dict(g) for g in data.get("gold_moments", [])],
        )


@dataclass
class SampleManifest:
    """벤치마크 세트 전체."""

    name: str = "autoshorts-benchmark"
    version: int = 1
    samples: list[BenchmarkSample] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.samples)

    def by_mode(self, mode: str) -> list[BenchmarkSample]:
        return [s for s in self.samples if s.content_mode == mode]

    def mode_distribution(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for sample in self.samples:
            counts[sample.content_mode] = counts.get(sample.content_mode, 0) + 1
        return counts

    def validate(self) -> list[str]:
        """매니페스트의 문제를 경고 목록으로 돌려준다(예외를 던지지 않는다)."""
        problems: list[str] = []
        seen: set[str] = set()
        for sample in self.samples:
            if sample.sample_id in seen:
                problems.append(f"중복 sample_id: {sample.sample_id}")
            seen.add(sample.sample_id)
            if not sample.gold_moments:
                problems.append(f"{sample.sample_id}: gold_moment 가 없습니다")
            for gold in sample.gold_moments:
                if gold.duration <= 0:
                    problems.append(f"{sample.sample_id}: 길이가 0인 gold moment")
                if sample.duration_seconds and gold.end > sample.duration_seconds + 1:
                    problems.append(
                        f"{sample.sample_id}: gold moment 가 영상 길이를 넘습니다"
                    )
        return problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "samples": [s.to_dict() for s in self.samples],
        }

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        ensure_dir(path.parent)
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return path

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SampleManifest":
        return cls(
            name=data.get("name", "autoshorts-benchmark"),
            version=int(data.get("version", 1) or 1),
            samples=[BenchmarkSample.from_dict(s) for s in data.get("samples", [])],
        )

    @classmethod
    def load(cls, path: str | Path) -> "SampleManifest":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


# ── 2. 품질 지표 (순수 함수) ────────────────────────────────


def _boundary_starts(segments: Sequence[Segment]) -> list[float]:
    return [s.start for s in segments]


def _boundary_ends(segments: Sequence[Segment]) -> list[float]:
    return [s.end for s in segments]


def _near(value: float, boundaries: Sequence[float], tolerance: float) -> bool:
    return any(abs(value - b) <= tolerance for b in boundaries)


def mid_sentence_cut_rate(
    clips: Sequence[Clip],
    transcript: Transcript,
    *,
    tolerance: float = BOUNDARY_TOLERANCE_SECONDS,
) -> float:
    """문장 중간에서 잘린 클립의 비율 (0~1).

    시작이나 끝 중 하나라도 발화 경계에 붙어 있지 않으면 잘린 것으로 센다.
    전사본이 비어 있으면 판단할 근거가 없으므로 0.0 을 돌려준다.
    """
    segments = list(transcript.segments)
    if not clips or not segments:
        return 0.0
    starts, ends = _boundary_starts(segments), _boundary_ends(segments)
    bad = 0
    for clip in clips:
        if not _near(clip.start, starts, tolerance) or not _near(clip.end, ends, tolerance):
            bad += 1
    return _round(bad / len(clips))


def duplicate_overlap_rate(
    clips: Sequence[Clip], *, threshold: float = DUPLICATE_OVERLAP_SECONDS
) -> float:
    """서로 겹치는 클립 쌍의 비율 (0~1). 클립이 1개 이하면 0."""
    if len(clips) < 2:
        return 0.0
    pairs = 0
    overlapping = 0
    for index, first in enumerate(clips):
        for second in clips[index + 1:]:
            pairs += 1
            overlap = min(first.end, second.end) - max(first.start, second.start)
            if overlap > threshold:
                overlapping += 1
    return _round(overlapping / pairs) if pairs else 0.0


def _iou(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    intersection = max(0.0, min(a_end, b_end) - max(a_start, b_start))
    union = max(a_end, b_end) - min(a_start, b_start)
    return intersection / union if union > 0 else 0.0


def gold_acceptance(
    clips: Sequence[Clip],
    gold_moments: Sequence[GoldMoment],
    *,
    iou_threshold: float = GOLD_IOU_THRESHOLD,
) -> float:
    """사람이 지정한 gold moment 중 클립이 잡아낸 비율 (0~1).

    gold moment 가 없으면 측정 불가이므로 ``-1.0`` 을 돌려준다(0 과 구분한다).
    """
    if not gold_moments:
        return -1.0
    if not clips:
        return 0.0
    hit = 0
    for gold in gold_moments:
        if any(_iou(c.start, c.end, gold.start, gold.end) >= iou_threshold for c in clips):
            hit += 1
    return _round(hit / len(gold_moments))


def context_dependency_flags(clips: Sequence[Clip], transcript: Transcript) -> list[str]:
    """문맥 의존 표현으로 시작하는 클립의 id 목록.

    standalone comprehension 의 **대리 지표**다. 사람 평가를 대신하지 않는다.
    """
    flagged: list[str] = []
    for clip in clips:
        opening = ""
        for segment in transcript.slice(clip.start, clip.end):
            if segment.text.strip():
                opening = segment.text.strip()
                break
        if not opening:
            continue
        first_word = _WORD_SPLIT.split(opening)[0].strip(" ,.?!\"'").lower()
        if first_word in _CONTEXT_DEPENDENT_OPENERS:
            flagged.append(f"clip_{clip.index:02d}")
    return flagged


@dataclass
class QualityMetrics:
    """클립 품질 측정 결과."""

    clip_count: int = 0
    mid_sentence_cut_rate: float = 0.0
    duplicate_overlap_rate: float = 0.0
    gold_acceptance: float = -1.0          # -1 = gold moment 미지정
    context_dependent_clips: list[str] = field(default_factory=list)
    mean_clip_seconds: float = 0.0
    clips_outside_length_range: int = 0
    # 사람 평가를 받아 적는 자리. 자동 계산하지 않는다.
    human_standalone_rate: float | None = None
    human_notes: str = ""

    @property
    def context_dependency_rate(self) -> float:
        if not self.clip_count:
            return 0.0
        return _round(len(self.context_dependent_clips) / self.clip_count)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["context_dependency_rate"] = self.context_dependency_rate
        return data


def measure_quality(
    clips: Sequence[Clip],
    transcript: Transcript,
    gold_moments: Sequence[GoldMoment] = (),
    *,
    min_seconds: float = 30.0,
    max_seconds: float = 60.0,
) -> QualityMetrics:
    """클립 묶음 하나의 품질 지표를 한 번에 계산한다."""
    clips = list(clips)
    durations = [c.duration for c in clips]
    outside = sum(1 for d in durations if d < min_seconds - 0.5 or d > max_seconds + 0.5)
    return QualityMetrics(
        clip_count=len(clips),
        mid_sentence_cut_rate=mid_sentence_cut_rate(clips, transcript),
        duplicate_overlap_rate=duplicate_overlap_rate(clips),
        gold_acceptance=gold_acceptance(clips, gold_moments),
        context_dependent_clips=context_dependency_flags(clips, transcript),
        mean_clip_seconds=_round(sum(durations) / len(durations)) if durations else 0.0,
        clips_outside_length_range=outside,
    )


# ── 3. 성능 측정 ───────────────────────────────────────────


def peak_memory_mb() -> float:
    """이 프로세스와 자식 프로세스(FFmpeg 포함)의 peak RSS.

    ``ru_maxrss`` 단위가 리눅스는 KB, macOS 는 byte 다.
    """
    import sys

    divisor = 1024 * 1024 if sys.platform == "darwin" else 1024
    total = (
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        + resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    )
    return _round(total / divisor, 1)


@dataclass
class StageTiming:
    """파이프라인 한 단계의 소요 시간."""

    stage: str
    seconds: float = 0.0
    peak_memory_mb: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@contextmanager
def track_stage(stage: str, into: list[StageTiming]):
    """``with track_stage("transcribe", timings):`` 로 단계 소요를 기록한다."""
    started = time.monotonic()
    try:
        yield
    finally:
        into.append(
            StageTiming(
                stage=stage,
                seconds=_round(time.monotonic() - started, 2),
                peak_memory_mb=peak_memory_mb(),
            )
        )


@dataclass
class RunRecord:
    """샘플 한 편에 대한 실행 결과."""

    sample_id: str
    content_mode: str = "auto"
    source_seconds: float = 0.0
    succeeded: bool = False
    error: str = ""
    stage_timings: list[StageTiming] = field(default_factory=list)
    total_seconds: float = 0.0
    peak_memory_mb: float = 0.0
    output_bytes: int = 0
    output_count: int = 0
    quality: QualityMetrics | None = None

    @property
    def seconds_per_source_minute(self) -> float:
        """소스 1분당 처리 시간. 영상 길이가 달라도 비교할 수 있게 한다."""
        if self.source_seconds <= 0:
            return 0.0
        return _round(self.total_seconds / (self.source_seconds / 60.0), 2)

    @property
    def output_mb(self) -> float:
        return _round(self.output_bytes / 1_048_576, 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "content_mode": self.content_mode,
            "source_seconds": self.source_seconds,
            "succeeded": self.succeeded,
            "error": self.error,
            "stage_timings": [t.to_dict() for t in self.stage_timings],
            "total_seconds": _round(self.total_seconds, 2),
            "seconds_per_source_minute": self.seconds_per_source_minute,
            "peak_memory_mb": self.peak_memory_mb,
            "output_bytes": self.output_bytes,
            "output_mb": self.output_mb,
            "output_count": self.output_count,
            "quality": self.quality.to_dict() if self.quality else None,
        }


@dataclass
class BenchmarkReport:
    """실행 전체 요약. Phase 4 이후 비교의 기준선이 된다."""

    manifest_name: str = ""
    engine_version: str = ""
    baseline_label: str = "transcript-only"
    runs: list[RunRecord] = field(default_factory=list)

    @property
    def render_success_rate(self) -> float:
        if not self.runs:
            return 0.0
        return _round(sum(1 for r in self.runs if r.succeeded) / len(self.runs))

    def _successful(self) -> list[RunRecord]:
        return [r for r in self.runs if r.succeeded and r.quality]

    def aggregate_quality(self) -> dict[str, float]:
        """성공한 실행들의 품질 지표 평균."""
        rows = self._successful()
        if not rows:
            return {}
        gold_rows = [r for r in rows if r.quality and r.quality.gold_acceptance >= 0]
        aggregate = {
            "mid_sentence_cut_rate": _round(
                sum(r.quality.mid_sentence_cut_rate for r in rows) / len(rows)
            ),
            "duplicate_overlap_rate": _round(
                sum(r.quality.duplicate_overlap_rate for r in rows) / len(rows)
            ),
            "context_dependency_rate": _round(
                sum(r.quality.context_dependency_rate for r in rows) / len(rows)
            ),
            "mean_clip_seconds": _round(
                sum(r.quality.mean_clip_seconds for r in rows) / len(rows)
            ),
        }
        if gold_rows:
            aggregate["gold_acceptance"] = _round(
                sum(r.quality.gold_acceptance for r in gold_rows) / len(gold_rows)
            )
        return aggregate

    def aggregate_performance(self) -> dict[str, float]:
        rows = [r for r in self.runs if r.succeeded]
        if not rows:
            return {}
        per_minute = [r.seconds_per_source_minute for r in rows if r.seconds_per_source_minute]
        return {
            "mean_seconds_per_source_minute": _round(
                sum(per_minute) / len(per_minute), 2
            ) if per_minute else 0.0,
            "max_peak_memory_mb": max(r.peak_memory_mb for r in rows),
            "mean_output_mb": _round(sum(r.output_mb for r in rows) / len(rows), 2),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_name": self.manifest_name,
            "engine_version": self.engine_version,
            "baseline_label": self.baseline_label,
            "sample_count": len(self.runs),
            "render_success_rate": self.render_success_rate,
            "quality": self.aggregate_quality(),
            "performance": self.aggregate_performance(),
            "runs": [r.to_dict() for r in self.runs],
        }

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        ensure_dir(path.parent)
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return path

    def to_markdown(self) -> str:
        """사람이 읽을 요약표."""
        quality = self.aggregate_quality()
        performance = self.aggregate_performance()
        lines = [
            f"# 벤치마크 결과 — {self.manifest_name or '(이름 없음)'}",
            "",
            f"- 기준선: `{self.baseline_label}`",
            f"- 샘플 수: {len(self.runs)}",
            f"- 렌더 성공률: {self.render_success_rate:.1%}",
            "",
            "## 품질",
            "",
            "| 지표 | 값 |",
            "|---|---|",
        ]
        for key, value in quality.items():
            lines.append(f"| {key} | {value} |")
        if not quality:
            lines.append("| (성공한 실행 없음) | - |")
        lines += ["", "## 성능", "", "| 지표 | 값 |", "|---|---|"]
        for key, value in performance.items():
            lines.append(f"| {key} | {value} |")
        if not performance:
            lines.append("| (성공한 실행 없음) | - |")
        lines += ["", "## 샘플별", "", "| sample | mode | 성공 | 초/소스분 | peak MB | 클립 | 중간절단 |", "|---|---|---|---|---|---|---|"]
        for run in self.runs:
            cut = f"{run.quality.mid_sentence_cut_rate:.2f}" if run.quality else "-"
            clips = run.quality.clip_count if run.quality else 0
            lines.append(
                f"| {run.sample_id} | {run.content_mode} | "
                f"{'✅' if run.succeeded else '❌'} | {run.seconds_per_source_minute} | "
                f"{run.peak_memory_mb} | {clips} | {cut} |"
            )
        return "\n".join(lines) + "\n"
