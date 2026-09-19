"""Phase 0 — 기준선 측정 도구.

무엇을 위한 모듈인가
-------------------
상용화를 시작하기 전에 **지금 엔진이 실제로 어떤 결과를 내는지** 숫자로 고정한다.
기능을 새로 만들지 않고, 이미 있는 파이프라인을 돌려 다음을 기록한다.

- 처리시간 (전체 / 스테이지별)
- peak memory (파이썬 + FFmpeg 등 자식 프로세스 포함)
- output size / 개수 / 길이
- render 성공률
- 측정 가능한 품질 지표 — 문장 중간 절단률, 클립 간 중복률,
  gold moment 적중률(manifest 가 정답 구간을 줄 때만)

설계 원칙
--------
- **파이프라인을 고치지 않는다.** 스테이지 소요시간은 기존 ``on_progress``
  콜백의 스테이지 전환을 관찰해 얻는다. Phase 1 의 ``JobResult.stage_timings``
  계약을 여기서 미리 구현하지 않는다.
- **품질 엔진을 만들지 않는다.** 여기 있는 지표는 *현재* 산출물을 재는 자다.
  multimodal/narrative 점수는 Phase 4 의 일이다.
- 지표 계산은 순수 함수로 두어 영상 없이 단위 테스트한다.
"""

from __future__ import annotations

import json
import platform
import resource
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from .models import Clip, Transcript
from .utils import get_logger

__all__ = [
    "GoldMoment",
    "BenchmarkSample",
    "BenchmarkManifest",
    "SampleRun",
    "BenchmarkReport",
    "StageTimer",
    "MANIFEST_VERSION",
    "DURATION_BUCKETS",
    "CONTENT_MODES",
    "RIGHTS_STATUSES",
    "peak_memory_mb",
    "mid_sentence_cut_rate",
    "duplicate_overlap_rate",
    "gold_acceptance",
    "clip_boundary_flags",
    "load_manifest",
]

LOG = get_logger("benchmark")

#: manifest 스키마 버전. 필드를 바꾸면 올린다.
MANIFEST_VERSION = 1

#: Prompt 0 이 요구하는 길이 구간 (분).
DURATION_BUCKETS = (10, 30, 60)

#: MASTER_V3 Phase 1 JobSpec 의 content_mode 와 같은 어휘를 쓴다(측정 분류용).
CONTENT_MODES = ("auto", "podcast", "lecture", "gaming", "sports", "news", "vlog")

#: 권리 상태. Phase 0 은 분류만 하고 판정은 하지 않는다.
RIGHTS_STATUSES = ("owned", "licensed", "creative_commons", "unverified")

#: 문장이 끝났다고 볼 문자. 한국어/영어/일본어 종결부호를 함께 본다.
_SENTENCE_END = tuple(".!?…。！？")


# ──────────────────────────────────────────────────────────────
# manifest
# ──────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class GoldMoment:
    """사람이 지정한 정답 구간. 영상마다 3~5개를 권장한다."""

    start: float
    end: float
    label: str = ""

    def overlaps(self, start: float, end: float) -> float:
        """겹치는 길이(초). 겹치지 않으면 0."""
        return max(0.0, min(self.end, end) - max(self.start, start))


@dataclass(frozen=True)
class BenchmarkSample:
    """벤치마크 영상 한 편."""

    id: str
    source: str
    #: 길이 구간(분). :data:`DURATION_BUCKETS` 중 하나를 권장하지만 강제하지 않는다.
    duration_bucket: int | None = None
    content_mode: str = "auto"
    rights_status: str = "unverified"
    gold_moments: tuple[GoldMoment, ...] = ()
    notes: str = ""

    def validate(self) -> list[str]:
        """사람이 고칠 수 있는 문제를 목록으로 돌려준다(예외를 던지지 않는다)."""
        problems: list[str] = []
        if not self.id:
            problems.append("id 가 비었습니다.")
        if not self.source:
            problems.append(f"[{self.id}] source 가 비었습니다.")
        if self.content_mode not in CONTENT_MODES:
            problems.append(
                f"[{self.id}] content_mode '{self.content_mode}' 는 {CONTENT_MODES} 중 하나여야 합니다."
            )
        if self.rights_status not in RIGHTS_STATUSES:
            problems.append(
                f"[{self.id}] rights_status '{self.rights_status}' 는 {RIGHTS_STATUSES} 중 하나여야 합니다."
            )
        for moment in self.gold_moments:
            if moment.end <= moment.start:
                problems.append(f"[{self.id}] gold moment 구간이 뒤집혔습니다: {moment}")
        return problems

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["gold_moments"] = [asdict(m) for m in self.gold_moments]
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "BenchmarkSample":
        moments = tuple(
            GoldMoment(
                start=float(m.get("start", 0.0)),
                end=float(m.get("end", 0.0)),
                label=str(m.get("label", "")),
            )
            for m in data.get("gold_moments", ()) or ()
        )
        bucket = data.get("duration_bucket")
        return cls(
            id=str(data.get("id", "")),
            source=str(data.get("source", "")),
            duration_bucket=int(bucket) if bucket is not None else None,
            content_mode=str(data.get("content_mode", "auto")),
            rights_status=str(data.get("rights_status", "unverified")),
            gold_moments=moments,
            notes=str(data.get("notes", "")),
        )


@dataclass(frozen=True)
class BenchmarkManifest:
    """벤치마크 세트. JSON 파일 하나로 주고받는다."""

    samples: tuple[BenchmarkSample, ...] = ()
    version: int = MANIFEST_VERSION
    name: str = ""
    notes: str = ""

    def validate(self) -> list[str]:
        problems: list[str] = []
        if self.version != MANIFEST_VERSION:
            problems.append(
                f"manifest version {self.version} 은 이 코드가 아는 {MANIFEST_VERSION} 과 다릅니다."
            )
        seen: set[str] = set()
        for sample in self.samples:
            if sample.id in seen:
                problems.append(f"id 가 중복됩니다: {sample.id}")
            seen.add(sample.id)
            problems.extend(sample.validate())
        return problems

    def by_bucket(self) -> dict[int | None, list[BenchmarkSample]]:
        out: dict[int | None, list[BenchmarkSample]] = {}
        for sample in self.samples:
            out.setdefault(sample.duration_bucket, []).append(sample)
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "name": self.name,
            "notes": self.notes,
            "samples": [s.to_dict() for s in self.samples],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "BenchmarkManifest":
        return cls(
            samples=tuple(BenchmarkSample.from_dict(s) for s in data.get("samples", ()) or ()),
            version=int(data.get("version", MANIFEST_VERSION)),
            name=str(data.get("name", "")),
            notes=str(data.get("notes", "")),
        )

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return path


def load_manifest(path: str | Path) -> BenchmarkManifest:
    """manifest JSON 을 읽는다. 스키마 문제는 경고로 남기고 계속 진행한다."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    manifest = BenchmarkManifest.from_dict(data)
    for problem in manifest.validate():
        LOG.warning("manifest: %s", problem)
    return manifest


# ──────────────────────────────────────────────────────────────
# 측정 — 자원
# ──────────────────────────────────────────────────────────────
def peak_memory_mb() -> float:
    """프로세스와 자식(FFmpeg 포함)의 peak RSS 중 큰 값 (MiB).

    ``ru_maxrss`` 단위가 리눅스는 KiB, macOS 는 byte 다. 플랫폼을 보고 맞춘다.
    """
    divisor = 1024.0 * 1024.0 if platform.system() == "Darwin" else 1024.0
    peaks = [
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
    ]
    return round(max(peaks) / divisor, 1)


class StageTimer:
    """``on_progress`` 콜백을 관찰해 스테이지별 소요시간을 재는 도구.

    파이프라인을 고치지 않고 붙일 수 있도록, 콜백을 감싸는 형태로 쓴다.

        timer = StageTimer()
        run_pipeline(settings, on_progress=timer.observe)
        timer.finish()
        timer.seconds   # {"ingest": 12.3, "transcribe": 88.1, ...}
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._current: str | None = None
        self._started_at: float | None = None
        self.seconds: dict[str, float] = {}

    def observe(self, stage: str, fraction: float, message: str) -> None:
        """진행률 콜백 자리에 그대로 끼워 넣는다."""
        if stage == self._current:
            return
        # 이전 스테이지가 끝난 순간과 새 스테이지가 시작한 순간은 같다.
        # 시계를 한 번만 읽어야 두 스테이지 사이에 시간이 새지 않는다.
        now = self._clock()
        self._close_current(now)
        self._current = stage
        self._started_at = now

    def _close_current(self, now: float) -> None:
        if self._current is None or self._started_at is None:
            return
        spent = now - self._started_at
        self.seconds[self._current] = round(self.seconds.get(self._current, 0.0) + spent, 2)

    def finish(self) -> dict[str, float]:
        """마지막 스테이지를 닫고 결과를 돌려준다."""
        self._close_current(self._clock())
        self._current = None
        self._started_at = None
        return dict(self.seconds)


# ──────────────────────────────────────────────────────────────
# 측정 — 품질 (현재 산출물을 재는 자. Phase 4 엔진이 아니다)
# ──────────────────────────────────────────────────────────────
def _word_spans(transcript: Transcript) -> list[tuple[float, float, str]]:
    return [(w.start, w.end, w.text) for w in transcript.words() if w.text]


def clip_boundary_flags(clip: Clip, transcript: Transcript, *, tolerance: float = 0.25) -> dict[str, bool]:
    """클립 한 개의 시작/끝이 문장을 자르고 있는지 본다.

    판정 방법: 경계 시각이 어떤 단어의 **내부**에 들어가면 자른 것으로 본다.
    경계가 단어 사이 공백에 있다면, 시작 경계는 직전 단어가 문장을 끝맺었는지,
    끝 경계는 그 단어가 문장을 끝맺었는지를 본다.

    ``tolerance`` 는 경계가 단어 끝에 거의 붙어 있을 때 봐주는 여유(초)다.
    """
    spans = _word_spans(transcript)
    if not spans:
        return {"start_mid_sentence": False, "end_mid_sentence": False}

    def splits_word(boundary: float) -> bool:
        for start, end, _text in spans:
            if start + tolerance < boundary < end - tolerance:
                return True
        return False

    def word_before(boundary: float) -> str | None:
        prior = [text for start, end, text in spans if end <= boundary + tolerance]
        return prior[-1] if prior else None

    def word_at_or_after(boundary: float) -> str | None:
        later = [text for start, end, text in spans if end > boundary - tolerance]
        return later[0] if later else None

    start_cut = splits_word(clip.start)
    if not start_cut:
        # 클립이 문장 중간에서 시작하면, 직전 단어가 종결부호로 끝나지 않는다.
        previous = word_before(clip.start)
        first = word_at_or_after(clip.start)
        if previous is not None and first is not None:
            start_cut = not previous.rstrip().endswith(_SENTENCE_END)

    end_cut = splits_word(clip.end)
    if not end_cut:
        last = word_before(clip.end)
        following = word_at_or_after(clip.end)
        # 뒤에 말이 더 있는데 마지막 단어가 문장을 끝맺지 않았다면 자른 것이다.
        if last is not None and following is not None:
            end_cut = not last.rstrip().endswith(_SENTENCE_END)

    return {"start_mid_sentence": start_cut, "end_mid_sentence": end_cut}


def mid_sentence_cut_rate(clips: Sequence[Clip], transcript: Transcript) -> float:
    """경계 중 문장을 자른 비율 (0.0~1.0).

    클립마다 경계가 둘이므로 분모는 ``len(clips) * 2`` 다.
    """
    if not clips:
        return 0.0
    cuts = 0
    for clip in clips:
        flags = clip_boundary_flags(clip, transcript)
        cuts += int(flags["start_mid_sentence"]) + int(flags["end_mid_sentence"])
    return round(cuts / (len(clips) * 2), 4)


def duplicate_overlap_rate(clips: Sequence[Clip]) -> float:
    """클립끼리 겹친 시간이 전체 클립 시간에서 차지하는 비율 (0.0~1.0)."""
    total = sum(c.duration for c in clips)
    if total <= 0:
        return 0.0
    overlap = 0.0
    ordered = sorted(clips, key=lambda c: c.start)
    for i, first in enumerate(ordered):
        for second in ordered[i + 1:]:
            if second.start >= first.end:
                break
            overlap += max(0.0, min(first.end, second.end) - second.start)
    return round(min(1.0, overlap / total), 4)


def gold_acceptance(
    clips: Sequence[Clip],
    gold: Sequence[GoldMoment],
    *,
    top_n: int | None = None,
    min_overlap_ratio: float = 0.5,
) -> float | None:
    """gold moment 중 몇 개를 잡았는지 (0.0~1.0). 정답이 없으면 ``None``.

    한 gold moment 는 어떤 클립이 그 길이의 ``min_overlap_ratio`` 이상을 덮으면
    잡은 것으로 센다.
    """
    if not gold:
        return None
    considered = list(clips)[:top_n] if top_n else list(clips)
    if not considered:
        return 0.0
    hit = 0
    for moment in gold:
        span = moment.end - moment.start
        if span <= 0:
            continue
        best = max((moment.overlaps(c.start, c.end) for c in considered), default=0.0)
        if best / span >= min_overlap_ratio:
            hit += 1
    return round(hit / len(gold), 4)


# ──────────────────────────────────────────────────────────────
# 결과
# ──────────────────────────────────────────────────────────────
@dataclass
class SampleRun:
    """영상 한 편의 측정 결과."""

    sample_id: str
    ok: bool = False
    error: str = ""
    source_seconds: float = 0.0
    elapsed_seconds: float = 0.0
    stage_seconds: dict[str, float] = field(default_factory=dict)
    peak_memory_mb: float = 0.0
    clip_count: int = 0
    output_bytes: int = 0
    output_count: int = 0
    used_offline_analysis: bool = False
    mid_sentence_cut_rate: float | None = None
    duplicate_overlap_rate: float | None = None
    gold_acceptance: float | None = None

    @property
    def realtime_factor(self) -> float | None:
        """원본 1초를 처리하는 데 든 시간. 낮을수록 빠르다."""
        if self.source_seconds <= 0:
            return None
        return round(self.elapsed_seconds / self.source_seconds, 3)

    @property
    def seconds_per_source_minute(self) -> float | None:
        factor = self.realtime_factor
        return None if factor is None else round(factor * 60, 2)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["realtime_factor"] = self.realtime_factor
        data["seconds_per_source_minute"] = self.seconds_per_source_minute
        return data


@dataclass
class BenchmarkReport:
    """벤치마크 한 회차 전체."""

    runs: list[SampleRun] = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""
    manifest_name: str = ""
    environment: dict[str, Any] = field(default_factory=dict)

    @property
    def render_success_rate(self) -> float | None:
        if not self.runs:
            return None
        return round(sum(1 for r in self.runs if r.ok) / len(self.runs), 4)

    def _mean(self, values: Iterable[float | None]) -> float | None:
        present = [v for v in values if v is not None]
        return round(sum(present) / len(present), 4) if present else None

    def aggregate(self) -> dict[str, Any]:
        """Beta gate 와 대조할 요약값."""
        ok_runs = [r for r in self.runs if r.ok]
        return {
            "samples": len(self.runs),
            "succeeded": len(ok_runs),
            "render_success_rate": self.render_success_rate,
            "mean_seconds_per_source_minute": self._mean(
                r.seconds_per_source_minute for r in ok_runs
            ),
            "peak_memory_mb": max((r.peak_memory_mb for r in self.runs), default=0.0),
            "mean_mid_sentence_cut_rate": self._mean(r.mid_sentence_cut_rate for r in ok_runs),
            "mean_duplicate_overlap_rate": self._mean(r.duplicate_overlap_rate for r in ok_runs),
            "mean_gold_acceptance": self._mean(r.gold_acceptance for r in ok_runs),
            "total_output_bytes": sum(r.output_bytes for r in ok_runs),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_name": self.manifest_name,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "environment": self.environment,
            "aggregate": self.aggregate(),
            "runs": [r.to_dict() for r in self.runs],
        }

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return path

    def to_markdown(self) -> str:
        """사람이 읽고 PR 에 붙일 표."""
        agg = self.aggregate()
        lines = [
            f"# 벤치마크 결과 — {self.manifest_name or '(이름 없음)'}",
            "",
            f"- 측정 시각: {self.started_at} → {self.finished_at}",
            f"- 영상 {agg['samples']}편 중 {agg['succeeded']}편 성공"
            f" (render success {_pct(agg['render_success_rate'])})",
            f"- 원본 1분당 처리시간 평균: {_num(agg['mean_seconds_per_source_minute'])}초",
            f"- peak memory: {agg['peak_memory_mb']} MiB",
            f"- 문장 중간 절단률 평균: {_pct(agg['mean_mid_sentence_cut_rate'])}",
            f"- 클립 중복률 평균: {_pct(agg['mean_duplicate_overlap_rate'])}",
            f"- gold moment 적중률 평균: {_pct(agg['mean_gold_acceptance'])}",
            "",
            "| 영상 | 결과 | 원본(초) | 처리(초) | 원본1분당(초) | peak(MiB) | 클립 | 절단률 | 중복률 | 적중률 |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for run in self.runs:
            lines.append(
                f"| {run.sample_id} | {'OK' if run.ok else 'FAIL'} | {run.source_seconds:.0f} | "
                f"{run.elapsed_seconds:.1f} | {_num(run.seconds_per_source_minute)} | "
                f"{run.peak_memory_mb} | {run.clip_count} | "
                f"{_pct(run.mid_sentence_cut_rate)} | {_pct(run.duplicate_overlap_rate)} | "
                f"{_pct(run.gold_acceptance)} |"
            )
        failed = [r for r in self.runs if not r.ok]
        if failed:
            lines += ["", "## 실패", ""]
            lines += [f"- `{r.sample_id}`: {r.error}" for r in failed]
        if self.environment:
            lines += ["", "## 환경", ""]
            lines += [f"- {k}: {v}" for k, v in sorted(self.environment.items())]
        return "\n".join(lines) + "\n"


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.1f}%"


def _num(value: float | None) -> str:
    return "—" if value is None else f"{value:g}"


def describe_environment() -> dict[str, Any]:
    """측정값을 나중에 해석할 수 있게 환경을 남긴다."""
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "processor": platform.processor() or "unknown",
        "measured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


# ──────────────────────────────────────────────────────────────
# 실행
# ──────────────────────────────────────────────────────────────
#: 파이프라인 실행부. 테스트에서 갈아끼울 수 있게 주입받는다.
PipelineRunner = Callable[..., Any]


def _output_bytes(result: Any) -> tuple[int, int]:
    """산출물 개수와 총 바이트. 파일이 사라져 있어도 터지지 않는다."""
    total = 0
    count = 0
    for path in getattr(result, "output_paths", []) or []:
        try:
            total += Path(path).stat().st_size
            count += 1
        except OSError:
            LOG.warning("산출물을 찾지 못해 크기를 세지 못했습니다: %s", path)
    return count, total


def _load_transcript(result: Any) -> Transcript | None:
    """``transcription.json`` 을 읽어 품질 지표 계산에 쓴다."""
    path = getattr(result, "transcript_path", None)
    if not path:
        return None
    try:
        return Transcript.load(path)
    except (OSError, json.JSONDecodeError) as exc:
        LOG.warning("전사 파일을 읽지 못해 품질 지표를 건너뜁니다: %s", exc)
        return None
    except Exception as exc:                                  # 스키마가 달라도 측정은 계속한다
        LOG.warning("전사 파일 구조를 해석하지 못했습니다: %s", exc)
        return None


def run_sample(
    settings: Any,
    sample: BenchmarkSample,
    *,
    runner: PipelineRunner,
    clock: Callable[[], float] = time.monotonic,
) -> SampleRun:
    """영상 한 편을 처리하고 재서 :class:`SampleRun` 을 돌려준다.

    실패해도 예외를 올리지 않는다 — 벤치마크는 한 편이 깨져도 끝까지 돌아야 한다.
    """
    run = SampleRun(sample_id=sample.id)
    timer = StageTimer(clock=clock)
    started = clock()
    try:
        result = runner(settings, on_progress=timer.observe)
    except Exception as exc:
        run.elapsed_seconds = round(clock() - started, 2)
        run.stage_seconds = timer.finish()
        run.peak_memory_mb = peak_memory_mb()
        run.error = f"{type(exc).__name__}: {exc}"
        LOG.error("[%s] 실패 — %s", sample.id, run.error)
        return run

    run.elapsed_seconds = round(clock() - started, 2)
    run.stage_seconds = timer.finish()
    run.peak_memory_mb = peak_memory_mb()
    clips = list(getattr(result, "clips", []) or [])
    run.clip_count = len(clips)
    run.output_count, run.output_bytes = _output_bytes(result)
    run.used_offline_analysis = bool(getattr(result, "used_offline_analysis", False))
    # 산출물이 하나도 없으면 성공이라 부르지 않는다.
    run.ok = run.output_count > 0

    transcript = _load_transcript(result)
    if transcript is not None:
        run.source_seconds = float(getattr(transcript, "duration", 0.0) or 0.0)
        if clips:
            run.mid_sentence_cut_rate = mid_sentence_cut_rate(clips, transcript)
    if clips:
        run.duplicate_overlap_rate = duplicate_overlap_rate(clips)
        run.gold_acceptance = gold_acceptance(clips, sample.gold_moments)
    if not run.ok and not run.error:
        run.error = "산출물이 생성되지 않았습니다."
    return run


def run_benchmark(
    settings_for: Callable[[BenchmarkSample], Any],
    manifest: BenchmarkManifest,
    *,
    runner: PipelineRunner,
    clock: Callable[[], float] = time.monotonic,
) -> BenchmarkReport:
    """manifest 전체를 돌린다.

    ``settings_for`` 는 영상마다 :class:`~autoshorts.config.Settings` 를 만들어
    주는 콜러블이다(작업 디렉터리를 분리하기 위해 영상별로 다르게 만든다).
    """
    report = BenchmarkReport(
        manifest_name=manifest.name,
        started_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        environment=describe_environment(),
    )
    for sample in manifest.samples:
        LOG.info("[%s] 측정 시작 — %s", sample.id, sample.source)
        report.runs.append(
            run_sample(settings_for(sample), sample, runner=runner, clock=clock)
        )
    report.finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return report
