"""멀티테넌트 HTTP API.

Phase 1 의 :mod:`autoshorts.api` 는 엔진 하나를 감싼 단일 사용자용이다. 이 파일은
그 위에 인증·워크스페이스·프로젝트·업로드·큐를 얹는다. Phase 1 api 는 그대로 둔다
(엔진만 띄우고 싶은 경우가 있다).

격리 원칙
---------
- 모든 라우트는 :class:`~saas.auth.Principal` 을 먼저 만든다.
- 자원 조회는 예외 없이 ``workspace_id`` 로 범위를 좁힌 저장소 메서드를 쓴다.
- 남의 자원과 없는 자원은 **같은 404** 로 답한다.

이 파일은 응답 본문을 직접 만든다. 프런트엔드(Phase 3)가 아직 없으므로 계약을
JSON 으로 고정해 두는 편이 낫다.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from autoshorts.contracts import ClipOptions, JobResult, JobSpec, JobStatus, RenderOptions
from autoshorts.service import JobRecord
from autoshorts.storage import LocalStorage, Storage
from autoshorts.utils import ensure_dir, get_logger

from .auth import AuthError, InvalidCredentials, new_id
from .db import Database
from .jobstore import PostgresJobStore
from .ledger import InsufficientCredits, Ledger, estimate_job_credits
from .queue import PostgresJobQueue
from .repositories import (
    AssetRepository,
    ClipRepository,
    DuplicateEmail,
    OutputRepository,
    ProgressRepository,
    ProjectRepository,
    UserRepository,
    WorkspaceRepository,
)
from .tenancy import AccessDenied, NotFound, Role, require_member, require_role
from .uploads import (
    ALLOWED_CONTENT_TYPES,
    MAX_UPLOAD_BYTES,
    LocalPresigner,
    Presigner,
    UploadError,
    storage_key_for_asset,
)

# FastAPI 는 선택 의존성이지만, 라우트 인자의 타입 힌트는 **모듈 전역**에서 해석된다.
# 함수 안에서만 import 하면 ``request: Request`` 가 쿼리 파라미터로 오해받는다.
try:  # pragma: no cover - 설치 여부에 따라 갈린다
    from fastapi import Request
except ImportError:  # pragma: no cover
    Request = Any  # type: ignore[assignment,misc]

__all__ = ["create_app", "AppContext", "SIGNUP_CREDITS"]

LOG = get_logger("saas.api")

# 체험용 크레딧. 1 크레딧 = 산출물 1초이므로 30분 분량이다. 예약은 최악의 경우
# (max_clips × max_clip_seconds)로 잡히므로 동시에 여러 건을 걸어볼 만큼은 돼야 한다.
# Phase 7 의 요금제가 이 값을 대체한다.
SIGNUP_CREDITS = 1800
CONSOLE_HTML = Path(__file__).resolve().parent / "console.html"


class AppContext:
    """앱이 들고 다니는 협력자 묶음. 테스트에서 통째로 교체할 수 있게 한 곳에 모은다."""

    def __init__(
        self,
        db: Database,
        *,
        storage: Storage | None = None,
        presigner: Presigner | None = None,
        upload_secret: str = "",
        storage_root: str | Path = "var/storage",
        serve_console: bool = True,
    ) -> None:
        self.db = db
        self.storage = storage or LocalStorage(ensure_dir(Path(storage_root)))
        secret = upload_secret or os.environ.get("AUTOSHORTS_UPLOAD_SECRET", "")
        if not secret:
            # 개발 편의를 위해 생성하되, 재시작하면 기존 티켓이 무효가 된다는 점을 알린다.
            secret = new_id("upl")
            LOG.warning(
                "AUTOSHORTS_UPLOAD_SECRET 이 없어 임시 키를 생성했습니다. "
                "재시작하면 발급된 업로드 티켓이 모두 무효가 됩니다."
            )
        self.presigner = presigner or LocalPresigner(secret, self.storage)
        self.users = UserRepository(db)
        self.workspaces = WorkspaceRepository(db)
        self.projects = ProjectRepository(db)
        self.assets = AssetRepository(db)
        self.clips = ClipRepository(db)
        self.outputs = OutputRepository(db)
        self.progress = ProgressRepository(db)
        self.ledger = Ledger(db)
        self.queue = PostgresJobQueue(db)
        self.jobs = PostgresJobStore(db, enqueue=True)
        self.serve_console = serve_console


def _job_view(row: dict[str, Any]) -> dict[str, Any]:
    result = row.get("result") or {}
    return {
        "id": row["id"],
        "workspace_id": row["workspace_id"],
        "project_id": row["project_id"],
        "asset_id": row.get("asset_id"),
        "project_revision": row.get("project_revision"),
        "status": row["status"],
        "stage": row.get("stage") or "",
        "progress": float(row.get("progress") or 0.0),
        "error_code": row.get("error_code"),
        "error_message": row.get("error_message") or "",
        "reused_from_job_id": row.get("reused_from_job_id"),
        "warnings": result.get("warnings", []),
        "quality_checks": result.get("quality_checks", []),
        "stage_timings": result.get("stage_timings", []),
        "outputs": result.get("outputs", []),
        "created_at": row.get("created_at"),
        "started_at": row.get("started_at"),
        "finished_at": row.get("finished_at"),
    }


def create_app(context: AppContext):
    """FastAPI 앱을 만든다.

    FastAPI 는 선택 의존성이다. 엔진만 쓰는 사용자에게 웹 프레임워크를 강요하지 않는다.
    """
    try:
        from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, Response
        from fastapi.responses import FileResponse, HTMLResponse
    except ImportError as exc:  # pragma: no cover - 설치 안내 경로
        raise RuntimeError(
            "FastAPI 가 필요합니다. `pip install 'autoshorts[saas]'` 로 설치하세요."
        ) from exc

    app = FastAPI(title="AutoShorts SaaS API", version="0.2.0")

    # ── 신원 ───────────────────────────────────────────────
    def principal(authorization: str = Header(default="")):
        token = ""
        if authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
        found = context.users.principal_for_token(token)
        if found is None:
            raise HTTPException(status_code=401, detail="인증이 필요합니다.")
        return found

    def _workspace(user, workspace_id: str, minimum: str = Role.VIEWER) -> str:
        try:
            return require_role(user, workspace_id, minimum)
        except NotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except AccessDenied as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    def _project(user, project_id: str, minimum: str = Role.VIEWER) -> dict[str, Any]:
        """프로젝트를 찾되, 사용자가 속한 워크스페이스 안에서만 찾는다.

        프로젝트 ID 로 먼저 조회한 뒤 소유자를 확인하는 순서는 쓰지 않는다. 그러면
        존재 여부가 타이밍으로 새어나간다.
        """
        for workspace_id in user.memberships:
            found = context.projects.get(workspace_id, project_id)
            if found:
                _workspace(user, workspace_id, minimum)
                return found
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")

    # ── 상태 ───────────────────────────────────────────────
    @app.get("/v1/product")
    def product():
        return {"name": "Shorts Studio", "analysis": "available",
                "paid_ai_enabled": os.environ.get("AUTOSHORTS_ALLOW_PAID_AI", "0") == "1",
                "factory": "planning_only", "publishing": "disabled"}

    @app.get("/health")
    def health() -> dict[str, Any]:
        healthy = context.db.ping()
        return {"status": "ok" if healthy else "degraded", "database": healthy}

    @app.get("/", response_class=HTMLResponse)
    def console() -> Any:
        """Phase 2 개발용 콘솔.

        브랜드도 카피도 없다. 브라우저에서 격리와 큐를 눈으로 확인하기 위한
        점검용 화면이고, Phase 3 의 웹 셸이 이것을 대체한다.
        """
        if not context.serve_console or not CONSOLE_HTML.exists():
            return HTMLResponse("<h1>AutoShorts API</h1>", status_code=200)
        return HTMLResponse(CONSOLE_HTML.read_text(encoding="utf-8"))

    # ── 인증 ───────────────────────────────────────────────
    @app.post("/v1/auth/signup", status_code=201)
    def signup(payload: dict = Body(...)) -> dict[str, Any]:
        try:
            user = context.users.create(
                payload.get("email", ""),
                payload.get("password", ""),
                payload.get("display_name", ""),
            )
        except DuplicateEmail as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except AuthError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        workspace = context.workspaces.create(
            payload.get("workspace_name") or f"{user['display_name']}의 워크스페이스",
            user["id"],
            initial_credits=SIGNUP_CREDITS,
        )
        token, expires = context.users.issue_session(user["id"])
        return {
            "user": {"id": user["id"], "email": user["email"], "display_name": user["display_name"]},
            "workspace": workspace,
            "token": token,
            "expires_at": expires.isoformat(),
        }

    @app.post("/v1/auth/login")
    def login(payload: dict = Body(...)) -> dict[str, Any]:
        try:
            user = context.users.authenticate(payload.get("email", ""), payload.get("password", ""))
        except InvalidCredentials as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        token, expires = context.users.issue_session(user["id"])
        return {"user": user, "token": token, "expires_at": expires.isoformat()}

    @app.post("/v1/auth/logout", status_code=204, response_class=Response)
    def logout(authorization: str = Header(default="")):
        if authorization.lower().startswith("bearer "):
            context.users.revoke_session(authorization[7:].strip())
        return Response(status_code=204)

    @app.get("/v1/me")
    def me(user=Depends(principal)) -> dict[str, Any]:
        return {
            "user": {"id": user.user_id, "email": user.email, "display_name": user.display_name},
            "workspaces": context.workspaces.list_for_user(user.user_id),
        }

    # ── 워크스페이스 ────────────────────────────────────────
    @app.post("/v1/workspaces", status_code=201)
    def create_workspace(payload: dict = Body(...), user=Depends(principal)) -> dict[str, Any]:
        return context.workspaces.create(payload.get("name", ""), user.user_id)

    @app.get("/v1/workspaces/{workspace_id}/members")
    def list_members(workspace_id: str, user=Depends(principal)) -> dict[str, Any]:
        _workspace(user, workspace_id)
        return {"members": context.workspaces.members(workspace_id)}

    @app.post("/v1/workspaces/{workspace_id}/members", status_code=201)
    def add_member(workspace_id: str, payload: dict = Body(...), user=Depends(principal)) -> dict:
        _workspace(user, workspace_id, Role.ADMIN)
        target = context.db.fetch_one(
            "SELECT id FROM users WHERE email = %s", (str(payload.get("email", "")).lower(),)
        )
        if not target:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
        role = payload.get("role", Role.EDITOR)
        if role not in {Role.OWNER, Role.ADMIN, Role.EDITOR, Role.VIEWER}:
            raise HTTPException(status_code=400, detail="알 수 없는 역할입니다.")
        context.workspaces.add_member(workspace_id, target["id"], role)
        return {"workspace_id": workspace_id, "user_id": target["id"], "role": role}

    @app.get("/v1/workspaces/{workspace_id}/usage")
    def usage(workspace_id: str, user=Depends(principal)) -> dict[str, Any]:
        _workspace(user, workspace_id)
        summary = context.ledger.summary(workspace_id)
        summary["credit_ledger"] = context.ledger.entries(workspace_id, limit=50)
        return summary

    # ── 프로젝트 ────────────────────────────────────────────
    @app.post("/v1/workspaces/{workspace_id}/projects", status_code=201)
    def create_project(workspace_id: str, payload: dict = Body(...), user=Depends(principal)):
        _workspace(user, workspace_id, Role.EDITOR)
        return context.projects.create(
            workspace_id,
            payload.get("name", ""),
            user.user_id,
            content_mode=payload.get("content_mode", "auto"),
        )

    @app.get("/v1/workspaces/{workspace_id}/projects")
    def list_projects(workspace_id: str, user=Depends(principal)) -> dict[str, Any]:
        _workspace(user, workspace_id)
        return {"projects": context.projects.list(workspace_id)}

    @app.get("/v1/projects/{project_id}")
    def get_project(project_id: str, user=Depends(principal)) -> dict[str, Any]:
        project = _project(user, project_id)
        workspace_id = project["workspace_id"]
        return {
            "project": project,
            "assets": context.assets.list(workspace_id, project_id),
            "revisions": context.projects.revisions(workspace_id, project_id),
        }

    @app.get("/v1/projects/{project_id}/jobs")
    def project_jobs(project_id: str, user=Depends(principal)):
        project = _project(user, project_id)
        rows = context.db.fetch_all(
            "SELECT * FROM render_jobs WHERE workspace_id = %s AND project_id = %s "
            "ORDER BY created_at DESC LIMIT 100", (project["workspace_id"], project_id))
        return {"jobs": [_job_view(row) for row in rows]}

    @app.get("/v1/projects/{project_id}/factory-plan")
    def factory_plan(project_id: str, user=Depends(principal)):
        _project(user, project_id)
        row = context.db.fetch_one(
            "SELECT snapshot FROM project_revisions WHERE project_id = %s "
            "AND change_kind = 'factory_plan' ORDER BY revision DESC LIMIT 1", (project_id,))
        return {"plan": row["snapshot"] if row else None, "generation": "paused"}

    @app.put("/v1/projects/{project_id}/factory-plan")
    def save_factory_plan(project_id: str, payload: dict = Body(...), user=Depends(principal)):
        project = _project(user, project_id, Role.EDITOR)
        topic, script = str(payload.get("topic", "")).strip(), str(payload.get("script", "")).strip()
        theme = str(payload.get("theme", "knowledge"))
        if not topic or len(topic) > 300 or len(script) > 20000:
            raise HTTPException(status_code=400, detail="주제는 1~300자, 대본은 20,000자 이내입니다.")
        if theme not in {"knowledge", "quote", "news", "music", "space"}:
            raise HTTPException(status_code=400, detail="지원하지 않는 테마입니다.")
        plan = {"format": "shorts-studio.factory-plan.v1", "topic": topic, "script": script,
                "theme": theme, "generation": "paused", "auto_publish": False}
        revision = context.projects.bump_revision(project["workspace_id"], project_id,
            "factory_plan", changed_by=user.user_id, snapshot=plan)
        return {"plan": plan, "revision": revision}

    @app.post("/v1/projects/{project_id}/factory-jobs")
    def factory_job(project_id: str, user=Depends(principal)):
        _project(user, project_id, Role.EDITOR)
        raise HTTPException(status_code=409, detail="주제 기반 자동 생성은 비용 차단 상태입니다. 기획 저장만 가능합니다.")

    # ── 업로드 ──────────────────────────────────────────────
    @app.post("/v1/projects/{project_id}/uploads", status_code=201)
    def create_upload(project_id: str, payload: dict = Body(...), user=Depends(principal)):
        project = _project(user, project_id, Role.EDITOR)
        workspace_id = project["workspace_id"]
        filename = str(payload.get("filename", "source.mp4"))
        content_type = str(payload.get("content_type", "video/mp4"))
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=415,
                detail=f"지원하지 않는 형식입니다: {content_type}",
            )
        max_bytes = min(int(payload.get("max_bytes", MAX_UPLOAD_BYTES)), MAX_UPLOAD_BYTES)

        asset = context.assets.create(
            workspace_id, project_id, origin="upload", uploaded_by=user.user_id,
            original_filename=filename, content_type=content_type,
        )
        key = storage_key_for_asset(workspace_id, project_id, asset["id"], filename)
        context.db.execute(
            "UPDATE source_assets SET storage_key = %s WHERE id = %s AND workspace_id = %s",
            (key, asset["id"], workspace_id),
        )
        presigned = context.presigner.presign_put(
            key, content_type=content_type, max_bytes=max_bytes, ttl_seconds=900
        )
        ticket_id = presigned.url.rsplit("/", 1)[-1].split("?")[0]
        context.db.execute(
            "INSERT INTO upload_tickets (id, workspace_id, project_id, asset_id, storage_key, "
            "  content_type, max_bytes, created_by, expires_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (ticket_id, workspace_id, project_id, asset["id"], key, content_type,
             presigned.max_bytes, user.user_id, presigned.expires_at),
        )
        context.projects.bump_revision(
            workspace_id, project_id, "asset_added", changed_by=user.user_id,
            snapshot={"asset_id": asset["id"], "filename": filename},
        )
        return {"asset_id": asset["id"], "upload": presigned.to_dict()}

    @app.put("/v1/uploads/{ticket_id}")
    async def receive_upload(
        ticket_id: str,
        request: Request,
        expires: int = Query(0),
        signature: str = Query(""),
    ) -> dict[str, Any]:
        """서명 업로드 수신구.

        인증 헤더를 요구하지 않는다. 서명 자체가 자격증명이기 때문이다(그래서
        수명이 짧고 키 하나에 묶여 있다).
        """
        ticket = context.db.fetch_one(
            "SELECT id, workspace_id, project_id, asset_id, storage_key, max_bytes, consumed_at "
            "FROM upload_tickets WHERE id = %s",
            (ticket_id,),
        )
        if not ticket:
            raise HTTPException(status_code=404, detail="업로드 티켓을 찾을 수 없습니다.")
        if ticket["consumed_at"] is not None:
            raise HTTPException(status_code=409, detail="이미 사용된 업로드 티켓입니다.")

        presigner = context.presigner
        if not isinstance(presigner, LocalPresigner):
            raise HTTPException(status_code=404, detail="이 배포에서는 지원하지 않는 경로입니다.")
        try:
            presigner.verify(
                ticket_id, ticket["storage_key"], expires, int(ticket["max_bytes"]), signature
            )
        except UploadError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

        import io

        body = await request.body()
        try:
            checksum, size = presigner.receive(
                io.BytesIO(body), ticket["storage_key"], max_bytes=int(ticket["max_bytes"])
            )
        except UploadError as exc:
            context.db.execute(
                "UPDATE source_assets SET upload_state = 'failed' WHERE id = %s",
                (ticket["asset_id"],),
            )
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        context.assets.mark_uploaded(
            ticket["workspace_id"], ticket["asset_id"], size_bytes=size, checksum=checksum
        )
        context.db.execute(
            "UPDATE upload_tickets SET consumed_at = now() WHERE id = %s", (ticket_id,)
        )
        context.ledger.record_usage(
            ticket["workspace_id"], event_type="upload_bytes", quantity=size, unit="bytes",
            project_id=ticket["project_id"], metadata={"asset_id": ticket["asset_id"]},
        )
        return {"asset_id": ticket["asset_id"], "size_bytes": size, "checksum_sha256": checksum}

    @app.post("/v1/assets/{asset_id}/rights", status_code=201)
    def confirm_rights(asset_id: str, payload: dict = Body(...), user=Depends(principal)):
        """권리 확인 기록.

        서비스가 권리를 **판정하지 않는다.** 사용자가 근거와 함께 선언하고, 그 선언을
        지우지 않고 남긴다. 판정은 사람이 한다.
        """
        status = str(payload.get("status", ""))
        if status not in {"owned", "licensed", "creative_commons", "unverified"}:
            raise HTTPException(status_code=400, detail="알 수 없는 권리 상태입니다.")
        for workspace_id in user.memberships:
            asset = context.assets.get(workspace_id, asset_id)
            if asset:
                _workspace(user, workspace_id, Role.EDITOR)
                return context.assets.confirm_rights(
                    workspace_id, asset_id, status=status, confirmed_by=user.user_id,
                    evidence_uri=str(payload.get("evidence_uri", "")),
                    note=str(payload.get("note", "")),
                )
        raise HTTPException(status_code=404, detail="자산을 찾을 수 없습니다.")

    # ── 작업 ────────────────────────────────────────────────
    @app.post("/v1/projects/{project_id}/jobs", status_code=202)
    def submit_job(project_id: str, payload: dict = Body(...), user=Depends(principal)):
        """작업을 큐에 넣는다. **여기서 실행하지 않는다.**

        HTTP 요청 스레드에서 렌더를 돌리면 브라우저를 닫는 순간 작업이 사라진다.
        API 가 하는 일은 검증 · 크레딧 예약 · 큐 삽입까지다.
        """
        project = _project(user, project_id, Role.EDITOR)
        workspace_id = project["workspace_id"]

        asset_id = payload.get("asset_id")
        source = str(payload.get("source", "") or "")
        rights_status = "unverified"
        if asset_id:
            asset = context.assets.get(workspace_id, str(asset_id))
            if not asset:
                raise HTTPException(status_code=404, detail="자산을 찾을 수 없습니다.")
            if asset["upload_state"] != "uploaded":
                raise HTTPException(status_code=409, detail="업로드가 완료되지 않은 자산입니다.")
            rights_status = asset["rights_status"]
            source = (
                asset["source_url"]
                if asset["origin"] == "url"
                else str(context.storage.open_local(asset["storage_key"]))
            )
        elif not source:
            raise HTTPException(status_code=400, detail="asset_id 또는 source 가 필요합니다.")

        try:
            clip_options = ClipOptions.from_dict(payload.get("clip_options"))
            render_options = RenderOptions.from_dict(payload.get("render_options"))
            if not (1 <= clip_options.min_clips <= clip_options.max_clips <= 10):
                raise ValueError("쇼츠 개수는 1~10개입니다.")
            if not (1 <= clip_options.min_seconds <= clip_options.max_seconds <= 180):
                raise ValueError("쇼츠 길이는 1~180초입니다.")
        except (ValueError, TypeError, AttributeError, OverflowError):
            raise HTTPException(status_code=422, detail="쇼츠 개수·길이·렌더 설정을 확인하세요.") from None

        spec = JobSpec(
            source=source,
            workspace_id=workspace_id,
            project_id=project_id,
            content_mode=project.get("content_mode", "auto"),
            rights_status=rights_status,
            language=payload.get("language"),
            clip_options=clip_options,
            render_options=render_options,
            idempotency_key=str(payload.get("idempotency_key", "") or ""),
            metadata={
                "asset_id": asset_id,
                "created_by": user.user_id,
                "project_revision": project["revision"],
            },
        )
        if not spec.idempotency_key:
            spec.idempotency_key = spec.compute_idempotency_key()

        # 중복 제출은 크레딧을 예약하지 않는다.
        existing = context.jobs.find_by_idempotency_key(spec.idempotency_key, workspace_id)
        if existing is not None:
            row = context.jobs.row(workspace_id, existing.spec.job_id)
            return {"job": _job_view(row), "deduplicated": True}

        credits = estimate_job_credits(
            source_seconds=None,
            max_clips=clip_options.max_clips,
            max_clip_seconds=clip_options.max_seconds,
        )
        try:
            context.ledger.reserve(workspace_id, spec.job_id, credits, reason=f"작업 {spec.job_id}")
        except InsufficientCredits as exc:
            raise HTTPException(status_code=402, detail=str(exc)) from exc
        spec.metadata["reserved_credits"] = credits

        result = JobResult(job_id=spec.job_id, status=JobStatus.QUEUED,
                           idempotency_key=spec.idempotency_key)
        try:
            context.jobs.create(JobRecord(spec, result))
        except Exception:
            context.ledger.release(workspace_id, spec.job_id, credits, reason="작업 생성 실패")
            raise
        context.ledger.record_usage(
            workspace_id, event_type="job_submitted", quantity=1, unit="job",
            project_id=project_id, job_id=spec.job_id, user_id=user.user_id,
            metadata={"reserved_credits": credits},
        )
        row = context.jobs.row(workspace_id, spec.job_id)
        return {"job": _job_view(row), "deduplicated": False, "reserved_credits": credits}

    @app.get("/v1/jobs/{job_id}")
    def get_job(job_id: str, user=Depends(principal)) -> dict[str, Any]:
        for workspace_id in user.memberships:
            row = context.jobs.row(workspace_id, job_id)
            if row:
                view = _job_view(row)
                view["outputs_detail"] = context.outputs.list_for_job(workspace_id, job_id)
                view["candidates"] = context.clips.list_for_job(workspace_id, job_id)
                return view
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")

    @app.get("/v1/jobs/{job_id}/progress")
    def job_progress(job_id: str, after_id: int = Query(0), user=Depends(principal)):
        for workspace_id in user.memberships:
            row = context.jobs.row(workspace_id, job_id)
            if row:
                return {
                    "status": row["status"],
                    "stage": row.get("stage") or "",
                    "percent": float(row.get("progress") or 0.0),
                    "events": context.progress.list(workspace_id, job_id, after_id=after_id),
                }
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")

    @app.post("/v1/jobs/{job_id}/cancel")
    def cancel_job(job_id: str, user=Depends(principal)) -> dict[str, Any]:
        for workspace_id in user.memberships:
            row = context.jobs.row(workspace_id, job_id)
            if not row:
                continue
            _workspace(user, workspace_id, Role.EDITOR)
            if row["status"] in {"succeeded", "failed", "cancelled"}:
                raise HTTPException(status_code=409, detail="이미 끝난 작업입니다.")
            context.jobs.request_cancel(workspace_id, job_id)
            # 아직 아무도 잡지 않았다면 즉시 취소로 마감한다.
            if context.jobs.mark_queued_cancelled(workspace_id, job_id):
                reserved = int((row["spec"].get("metadata") or {}).get("reserved_credits", 0) or 0)
                if reserved:
                    context.ledger.release(workspace_id, job_id, reserved, reason="대기 중 취소")
                return {"job_id": job_id, "status": "cancelled"}
            return {"job_id": job_id, "status": "cancel_requested"}
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")

    @app.get("/v1/workspaces/{workspace_id}/jobs")
    def list_jobs(
        workspace_id: str,
        project_id: str = Query(default=""),
        limit: int = Query(default=50),
        user=Depends(principal),
    ) -> dict[str, Any]:
        _workspace(user, workspace_id)
        rows = context.jobs.rows_for_workspace(
            workspace_id, project_id=project_id or None, limit=limit
        )
        return {"jobs": [_job_view(row) for row in rows], "queue": context.queue.stats()}

    @app.get("/v1/outputs/{output_id}/download")
    def download_output(output_id: str, user=Depends(principal)) -> Any:
        """산출물 내려받기.

        저장소 키를 URL 에 노출하지 않는다. 사용자는 출력 ID 만 알고, 워크스페이스
        확인 후 서버가 키를 해석한다.
        """
        for workspace_id in user.memberships:
            output = context.outputs.get(workspace_id, output_id)
            if not output:
                continue
            try:
                path = context.storage.open_local(output["storage_key"])
            except Exception as exc:
                raise HTTPException(status_code=404, detail="산출물 파일이 없습니다.") from exc
            return FileResponse(
                path, media_type="video/mp4", filename=f"{output['title'] or output_id}.mp4"
            )
        raise HTTPException(status_code=404, detail="산출물을 찾을 수 없습니다.")

    return app
