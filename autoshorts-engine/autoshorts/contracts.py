"""Phase 1 — Engine Service Boundary 계약.

SaaS worker 가 기존 엔진을 호출할 때 주고받는 자료구조를 여기서 고정한다.
모두 **JSON 직렬화 가능**해야 한다. 큐·DB·HTTP 어느 쪽을 통과하든 같은 모양이어야
하기 때문이다.

설계 원칙
---------
- 기존 :func:`autoshorts.pipeline.run_pipeline` 을 **바꾸지 않는다.** 계약은 바깥에
  두고 service layer 가 번역한다.
- 경로·디렉터리는 전역이나 홈 디렉터리에서 유추하지 않고 **명시적으로 주입**받는다.
- 권리가 확인되지 않은 소스는 계약 단계에서 걸러진다. "나중에 UI 가 막겠지" 로 두지
  않는다.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

__all__ = [
    "JobStatus",
    "ErrorCode",
    "ContentMode",
    "RightsStatus",
    "QualityProfile",
    "CONTENT_MODES",
    "RIGHTS_STATUSES",
    "QUALITY_PROFILES",
    "TERMINAL_STATUSES",
    "RETRYABLE_ERRORS",
    "ClipOptions",
    "RenderOptions",
    "ProviderSettings",
    "JobSpec",
    "StageTiming",
    "QualityCheck",
    "CostEvent",
    "JobWarning",
    "JobOutput",
    "JobResult",
    "ProgressEvent",
    "utc_now",
]


def utc_now() -> str:
    """계약에 쓰는 시각 표기. 항상 UTC ISO-8601."""
    return datetime.now(timezone.utc).isoformat()


# ── 열거형 ─────────────────────────────────────────────────


class JobStatus(str, Enum):
    """작업 수명주기.

    ``NEEDS_APPROVAL`` 은 실패가 아니다. 권리 확인 같은 사람의 결정이 남아 있어
    의도적으로 멈춘 상태이며, 승인 후 재개할 수 있다.
    """

    QUEUED = "queued"
    RUNNING = "running"
    NEEDS_APPROVAL = "needs_approval"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_STATUSES = frozenset(
    {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED}
)


class ErrorCode(str, Enum):
    """실패 원인 분류.

    재시도해도 되는 것과 재시도하면 안 되는 것을 갈라 둔다. 이 구분이 없으면
    worker 가 잘못된 입력을 무한히 재시도하며 credit 만 태운다.
    """

    # 재시도 무의미 — 입력/정책 문제
    INVALID_INPUT = "invalid_input"
    SOURCE_NOT_FOUND = "source_not_found"
    UNSUPPORTED_FORMAT = "unsupported_format"
    RIGHTS_NOT_CONFIRMED = "rights_not_confirmed"
    NO_SPEECH_DETECTED = "no_speech_detected"
    NO_CANDIDATES = "no_candidates"
    CANCELLED = "cancelled"

    # 재시도 가능 — 일시적 문제
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_RATE_LIMITED = "provider_rate_limited"
    TIMEOUT = "timeout"
    RENDER_FAILED = "render_failed"
    STORAGE_ERROR = "storage_error"
    INTERNAL_ERROR = "internal_error"


RETRYABLE_ERRORS = frozenset(
    {
        ErrorCode.PROVIDER_UNAVAILABLE,
        ErrorCode.PROVIDER_RATE_LIMITED,
        ErrorCode.TIMEOUT,
        ErrorCode.RENDER_FAILED,
        ErrorCode.STORAGE_ERROR,
    }
)


class ContentMode(str, Enum):
    """소스 성격. Phase 4 에서 signal weight 를 다르게 주는 데 쓴다."""

    AUTO = "auto"
    PODCAST = "podcast"
    LECTURE = "lecture"
    GAMING = "gaming"
    SPORTS = "sports"
    NEWS = "news"
    VLOG = "vlog"


class RightsStatus(str, Enum):
    """소스 권리 상태. 기본값은 항상 ``UNVERIFIED`` 다."""

    OWNED = "owned"
    LICENSED = "licensed"
    CREATIVE_COMMONS = "creative_commons"
    UNVERIFIED = "unverified"


class QualityProfile(str, Enum):
    STANDARD = "standard"
    HIGH = "high"


CONTENT_MODES = tuple(m.value for m in ContentMode)
RIGHTS_STATUSES = tuple(r.value for r in RightsStatus)
QUALITY_PROFILES = tuple(q.value for q in QualityProfile)

# 권리 확인 없이 렌더/게시로 넘기면 안 되는 상태
_REQUIRES_APPROVAL = frozenset({RightsStatus.UNVERIFIED})


def _coerce_enum(value: Any, enum_type: type, field_name: str):
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(str(value))
    except ValueError:
        allowed = ", ".join(e.value for e in enum_type)
        raise ValueError(f"{field_name} 는 [{allowed}] 중 하나여야 합니다: {value!r}") from None


# ── 옵션 ───────────────────────────────────────────────────


@dataclass
class ClipOptions:
    """하이라이트 선정 옵션."""

    min_seconds: float = 30.0
    max_seconds: float = 60.0
    min_clips: int = 3
    max_clips: int = 5

    def __post_init__(self) -> None:
        if self.min_seconds <= 0 or self.max_seconds <= 0:
            raise ValueError("클립 길이는 0보다 커야 합니다.")
        if self.min_seconds > self.max_seconds:
            raise ValueError(
                f"min_seconds({self.min_seconds}) 가 max_seconds({self.max_seconds}) 보다 큽니다."
            )
        if self.min_clips > self.max_clips:
            raise ValueError(
                f"min_clips({self.min_clips}) 가 max_clips({self.max_clips}) 보다 큽니다."
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ClipOptions":
        data = data or {}
        return cls(
            min_seconds=float(data.get("min_seconds", 30.0)),
            max_seconds=float(data.get("max_seconds", 60.0)),
            min_clips=int(data.get("min_clips", 3)),
            max_clips=int(data.get("max_clips", 5)),
        )


@dataclass
class RenderOptions:
    """렌더링 옵션."""

    reframe_mode: str = "blur"
    width: int = 1080
    height: int = 1920
    fps: int | None = None
    crf: int = 20
    preset: str = "veryfast"
    burn_subtitles: bool = True
    font_name: str = "NanumGothic Bold"
    font_size: int = 78

    def __post_init__(self) -> None:
        if self.reframe_mode not in ("blur", "crop"):
            raise ValueError(f"reframe_mode 는 blur/crop 중 하나여야 합니다: {self.reframe_mode!r}")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("width/height 는 양수여야 합니다.")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "RenderOptions":
        data = data or {}
        return cls(
            reframe_mode=data.get("reframe_mode", "blur"),
            width=int(data.get("width", 1080)),
            height=int(data.get("height", 1920)),
            fps=data.get("fps"),
            crf=int(data.get("crf", 20)),
            preset=data.get("preset", "veryfast"),
            burn_subtitles=bool(data.get("burn_subtitles", True)),
            font_name=data.get("font_name", "NanumGothic Bold"),
            font_size=int(data.get("font_size", 78)),
        )


@dataclass
class ProviderSettings:
    """외부 provider 참조.

    **비밀값을 담지 않는다.** 키는 이름으로만 참조하고 실제 값은 실행 환경에서
    해석한다. JobSpec 은 DB·로그·큐를 지나다니므로 여기에 키가 들어가면 전부 샌다.
    """

    transcription: str = "faster-whisper"
    highlight: str = "gemini"
    render: str = "ffmpeg"
    credentials_ref: str | None = None      # 예: "workspace:123:gemini"
    model_overrides: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for key, value in list(self.model_overrides.items()):
            if _looks_like_secret(str(value)):
                raise ValueError(
                    f"model_overrides[{key!r}] 에 비밀값으로 보이는 문자열이 있습니다. "
                    "JobSpec 에는 키를 담지 말고 credentials_ref 로 참조하세요."
                )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ProviderSettings":
        data = data or {}
        return cls(
            transcription=data.get("transcription", "faster-whisper"),
            highlight=data.get("highlight", "gemini"),
            render=data.get("render", "ffmpeg"),
            credentials_ref=data.get("credentials_ref"),
            model_overrides=dict(data.get("model_overrides") or {}),
        )


def _looks_like_secret(value: str) -> bool:
    """명백한 API 키 형태만 막는다. 완벽한 탐지가 목적이 아니라 사고 방지용이다."""
    text = value.strip()
    return (
        text.startswith(("AIza", "sk-", "ya29.", "ghp_"))
        or (len(text) >= 32 and text.replace("-", "").replace("_", "").isalnum()
            and any(c.isdigit() for c in text) and any(c.isalpha() for c in text)
            and text.lower() != text and text.upper() != text)
    )


# ── JobSpec ────────────────────────────────────────────────


@dataclass
class JobSpec:
    """worker 에게 넘기는 작업 명세."""

    source: str
    workspace_id: str = ""
    project_id: str = ""
    job_id: str = field(default_factory=lambda: f"job_{uuid.uuid4().hex[:16]}")

    content_mode: ContentMode = ContentMode.AUTO
    rights_status: RightsStatus = RightsStatus.UNVERIFIED
    quality_profile: QualityProfile = QualityProfile.STANDARD

    language: str | None = None
    clip_options: ClipOptions = field(default_factory=ClipOptions)
    render_options: RenderOptions = field(default_factory=RenderOptions)
    providers: ProviderSettings = field(default_factory=ProviderSettings)

    # 경로는 유추하지 않고 주입받는다.
    work_dir: str = ""
    output_dir: str = ""

    # 같은 키로 다시 제출하면 새로 실행하지 않는다.
    idempotency_key: str = ""
    # 권리 확인을 사람이 마쳤다는 명시적 승인.
    rights_approved_by: str = ""
    created_at: str = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.source).strip():
            raise ValueError("source 는 비어 있을 수 없습니다.")
        self.content_mode = _coerce_enum(self.content_mode, ContentMode, "content_mode")
        self.rights_status = _coerce_enum(self.rights_status, RightsStatus, "rights_status")
        self.quality_profile = _coerce_enum(self.quality_profile, QualityProfile, "quality_profile")
        if isinstance(self.clip_options, dict):
            self.clip_options = ClipOptions.from_dict(self.clip_options)
        if isinstance(self.render_options, dict):
            self.render_options = RenderOptions.from_dict(self.render_options)
        if isinstance(self.providers, dict):
            self.providers = ProviderSettings.from_dict(self.providers)
        if not self.idempotency_key:
            self.idempotency_key = self.compute_idempotency_key()

    # ── 권리 게이트 ────────────────────────────────────────
    @property
    def requires_rights_approval(self) -> bool:
        """렌더로 넘어가기 전에 사람 승인이 필요한지."""
        return self.rights_status in _REQUIRES_APPROVAL and not self.rights_approved_by

    def approved(self, approver: str) -> "JobSpec":
        """승인자를 기록한 사본. 원본을 바꾸지 않는다."""
        if not str(approver).strip():
            raise ValueError("승인자 식별자가 필요합니다.")
        data = self.to_dict()
        data["rights_approved_by"] = approver
        return JobSpec.from_dict(data)

    # ── 멱등성 ─────────────────────────────────────────────
    def compute_idempotency_key(self) -> str:
        """결과에 영향을 주는 필드만으로 만든 키.

        ``job_id``/``created_at`` 처럼 매번 달라지는 값은 제외한다. 같은 입력으로
        같은 결과가 나올 작업이라면 키가 같아야 한다.
        """
        payload = {
            "source": self.source,
            "workspace_id": self.workspace_id,
            "project_id": self.project_id,
            "content_mode": self.content_mode.value,
            "quality_profile": self.quality_profile.value,
            "language": self.language,
            "clip_options": self.clip_options.to_dict(),
            "render_options": self.render_options.to_dict(),
            "providers": {
                "transcription": self.providers.transcription,
                "highlight": self.providers.highlight,
                "render": self.providers.render,
                "model_overrides": self.providers.model_overrides,
            },
        }
        blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "source": self.source,
            "workspace_id": self.workspace_id,
            "project_id": self.project_id,
            "content_mode": self.content_mode.value,
            "rights_status": self.rights_status.value,
            "quality_profile": self.quality_profile.value,
            "language": self.language,
            "clip_options": self.clip_options.to_dict(),
            "render_options": self.render_options.to_dict(),
            "providers": self.providers.to_dict(),
            "work_dir": self.work_dir,
            "output_dir": self.output_dir,
            "idempotency_key": self.idempotency_key,
            "rights_approved_by": self.rights_approved_by,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JobSpec":
        spec = cls(
            source=data.get("source", ""),
            workspace_id=data.get("workspace_id", ""),
            project_id=data.get("project_id", ""),
            content_mode=data.get("content_mode", ContentMode.AUTO),
            rights_status=data.get("rights_status", RightsStatus.UNVERIFIED),
            quality_profile=data.get("quality_profile", QualityProfile.STANDARD),
            language=data.get("language"),
            clip_options=ClipOptions.from_dict(data.get("clip_options")),
            render_options=RenderOptions.from_dict(data.get("render_options")),
            providers=ProviderSettings.from_dict(data.get("providers")),
            work_dir=data.get("work_dir", ""),
            output_dir=data.get("output_dir", ""),
            idempotency_key=data.get("idempotency_key", ""),
            rights_approved_by=data.get("rights_approved_by", ""),
            metadata=dict(data.get("metadata") or {}),
        )
        if data.get("job_id"):
            spec.job_id = data["job_id"]
        if data.get("created_at"):
            spec.created_at = data["created_at"]
        return spec


# ── 결과 구성요소 ──────────────────────────────────────────


@dataclass
class StageTiming:
    """파이프라인 한 단계의 소요."""

    stage: str
    seconds: float = 0.0
    peak_memory_mb: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StageTiming":
        return cls(
            stage=data.get("stage", ""),
            seconds=float(data.get("seconds", 0.0)),
            peak_memory_mb=float(data.get("peak_memory_mb", 0.0)),
        )


@dataclass
class QualityCheck:
    """결과물에 대한 자동 점검 하나."""

    name: str
    passed: bool
    value: float | None = None
    threshold: float | None = None
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CostEvent:
    """원가 발생 기록.

    Phase 9 의 credit 보호가 이 기록 위에 올라간다. 지금은 형식만 고정한다.
    """

    kind: str                       # transcription | highlight | render | storage
    provider: str = ""
    units: float = 0.0
    unit_name: str = ""             # seconds | tokens | api_units | bytes
    at: str = field(default_factory=utc_now)
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class JobWarning:
    """실패는 아니지만 사람이 알아야 하는 것."""

    code: str
    message: str
    stage: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class JobOutput:
    """산출물 하나."""

    clip_index: int
    title: str = ""
    uri: str = ""                   # storage 가 해석하는 주소
    start: float = 0.0
    end: float = 0.0
    score: float = 0.0
    reason: str = ""
    size_bytes: int = 0
    subtitle_uri: str = ""

    @property
    def duration(self) -> float:
        return round(self.end - self.start, 3)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["duration"] = self.duration
        return data


@dataclass
class JobResult:
    """작업 결과."""

    job_id: str
    status: JobStatus = JobStatus.QUEUED
    error_code: ErrorCode | None = None
    error_message: str = ""
    outputs: list[JobOutput] = field(default_factory=list)
    stage_timings: list[StageTiming] = field(default_factory=list)
    warnings: list[JobWarning] = field(default_factory=list)
    quality_checks: list[QualityCheck] = field(default_factory=list)
    cost_events: list[CostEvent] = field(default_factory=list)
    transcript_uri: str = ""
    started_at: str = ""
    finished_at: str = ""
    idempotency_key: str = ""
    reused_from_job_id: str = ""     # 멱등 재사용 시 원본 작업

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES

    @property
    def is_retryable(self) -> bool:
        """이 실패를 재시도해도 되는지."""
        return self.error_code in RETRYABLE_ERRORS if self.error_code else False

    @property
    def total_seconds(self) -> float:
        return round(sum(t.seconds for t in self.stage_timings), 2)

    def add_warning(self, code: str, message: str, stage: str = "") -> None:
        self.warnings.append(JobWarning(code=code, message=message, stage=stage))

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "error_code": self.error_code.value if self.error_code else None,
            "error_message": self.error_message,
            "is_retryable": self.is_retryable,
            "outputs": [o.to_dict() for o in self.outputs],
            "stage_timings": [t.to_dict() for t in self.stage_timings],
            "total_seconds": self.total_seconds,
            "warnings": [w.to_dict() for w in self.warnings],
            "quality_checks": [q.to_dict() for q in self.quality_checks],
            "cost_events": [c.to_dict() for c in self.cost_events],
            "transcript_uri": self.transcript_uri,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "idempotency_key": self.idempotency_key,
            "reused_from_job_id": self.reused_from_job_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JobResult":
        result = cls(
            job_id=data.get("job_id", ""),
            status=JobStatus(data.get("status", "queued")),
            error_message=data.get("error_message", ""),
            transcript_uri=data.get("transcript_uri", ""),
            started_at=data.get("started_at", ""),
            finished_at=data.get("finished_at", ""),
            idempotency_key=data.get("idempotency_key", ""),
            reused_from_job_id=data.get("reused_from_job_id", ""),
        )
        if data.get("error_code"):
            result.error_code = ErrorCode(data["error_code"])
        result.outputs = [JobOutput(**{k: v for k, v in o.items() if k != "duration"})
                          for o in data.get("outputs", [])]
        result.stage_timings = [StageTiming.from_dict(t) for t in data.get("stage_timings", [])]
        result.warnings = [JobWarning(**w) for w in data.get("warnings", [])]
        result.quality_checks = [QualityCheck(**q) for q in data.get("quality_checks", [])]
        result.cost_events = [CostEvent(**c) for c in data.get("cost_events", [])]
        return result


@dataclass
class ProgressEvent:
    """진행 상황 한 건. 큐/SSE/WebSocket 어디로든 그대로 흘릴 수 있어야 한다."""

    job_id: str
    stage: str
    percent: float = 0.0
    message: str = ""
    timestamp: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.percent = round(max(0.0, min(100.0, float(self.percent))), 2)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProgressEvent":
        return cls(
            job_id=data.get("job_id", ""),
            stage=data.get("stage", ""),
            percent=float(data.get("percent", 0.0)),
            message=data.get("message", ""),
            timestamp=data.get("timestamp", utc_now()),
        )
