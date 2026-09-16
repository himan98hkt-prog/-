"""HTTP API — 명세의 E2E(User A 흐름 / User B 접근 거부)를 그대로 옮긴 것."""

from __future__ import annotations

import pytest
from saas_fakes import fake_pipeline

from autoshorts.storage import LocalStorage
from saas.api import AppContext, create_app
from saas.worker import Worker, WorkerConfig

PASSWORD = "a-long-enough-password"
VIDEO = b"\x00\x01\x02" * 400


@pytest.fixture
def context(db, tmp_path) -> AppContext:
    return AppContext(
        db,
        storage=LocalStorage(tmp_path / "storage"),
        upload_secret="test-upload-secret",
        storage_root=tmp_path / "storage",
    )


@pytest.fixture
def client(context):
    from fastapi.testclient import TestClient

    with TestClient(create_app(context)) as test_client:
        yield test_client


@pytest.fixture
def worker(db, context, tmp_path):
    return Worker(
        db,
        config=WorkerConfig(
            worker_id="test-worker",
            work_root=tmp_path / "work",
            output_root=tmp_path / "output",
            storage_root=tmp_path / "storage",
        ),
        storage=context.storage,
        run_pipeline=fake_pipeline(clips=2),
    )


class Account:
    """한 사용자의 세션. 테스트 가독성을 위해 얇게 감싼다."""

    def __init__(self, client, email: str) -> None:
        self.client = client
        response = client.post("/v1/auth/signup", json={
            "email": email, "password": PASSWORD, "workspace_name": f"{email} 워크스페이스"})
        assert response.status_code == 201, response.text
        body = response.json()
        self.token = body["token"]
        self.user_id = body["user"]["id"]
        self.workspace = body["workspace"]["id"]

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def get(self, path, **kw):
        return self.client.get(path, headers=self.headers, **kw)

    def post(self, path, **kw):
        return self.client.post(path, headers=self.headers, **kw)

    def create_project(self, name="P") -> str:
        response = self.post(f"/v1/workspaces/{self.workspace}/projects", json={"name": name})
        assert response.status_code == 201, response.text
        return response.json()["id"]

    def upload(self, project_id: str, *, body: bytes = VIDEO, filename="clip.mp4") -> str:
        ticket = self.post(f"/v1/projects/{project_id}/uploads",
                           json={"filename": filename, "content_type": "video/mp4"})
        assert ticket.status_code == 201, ticket.text
        upload = ticket.json()["upload"]
        # 바이트는 인증 헤더 없이 presigned URL 로 직접 간다.
        put = self.client.put(upload["url"], content=body)
        assert put.status_code == 200, put.text
        return ticket.json()["asset_id"]

    def confirm_rights(self, asset_id: str, status="owned"):
        return self.post(f"/v1/assets/{asset_id}/rights", json={"status": status})

    def submit(self, project_id: str, asset_id: str, **extra):
        return self.post(f"/v1/projects/{project_id}/jobs",
                         json={"asset_id": asset_id, **extra})


@pytest.fixture
def alice(client) -> Account:
    return Account(client, "alice@example.com")


@pytest.fixture
def bob(client) -> Account:
    return Account(client, "bob@example.com")


# ── 기본 ───────────────────────────────────────────────────


def test_factory_plan_is_persisted_and_scoped(client, alice, bob):
    project = alice.create_project()
    path = f"/v1/projects/{project}/factory-plan"
    data = {"topic": "우주", "theme": "space", "script": "테스트 대본"}
    assert client.put(path, headers=alice.headers, json=data).status_code == 200
    assert alice.get(path).json()["plan"]["script"] == "테스트 대본"
    assert bob.get(path).status_code == 404
    assert client.put(path, headers=bob.headers, json=data).status_code == 404
    assert client.get(path).status_code == 401


def test_factory_generation_is_blocked_server_side(alice, db):
    project = alice.create_project()
    assert alice.post(f"/v1/projects/{project}/factory-jobs").status_code == 409
    assert db.fetch_one("SELECT count(*) AS n FROM job_queue")["n"] == 0


def test_job_history_is_scoped_to_project_owner(alice, bob):
    project = alice.create_project()
    asset = alice.upload(project)
    alice.confirm_rights(asset)
    job = alice.submit(project, asset).json()["job"]
    assert alice.get(f"/v1/projects/{project}/jobs").json()["jobs"][0]["id"] == job["id"]
    assert bob.get(f"/v1/projects/{project}/jobs").status_code == 404


@pytest.mark.parametrize("options", [{"min_clips": -1}, {"max_clips": 10000}, {"min_seconds": "nan"}, {"max_seconds": 100000}])
def test_invalid_clip_limits_are_rejected_before_queue(alice, db, options):
    project = alice.create_project()
    asset = alice.upload(project)
    alice.confirm_rights(asset)
    assert alice.submit(project, asset, clip_options=options).status_code == 422
    assert db.fetch_one("SELECT count(*) AS n FROM job_queue")["n"] == 0


def test_retry_is_scoped_and_idempotent(alice, bob, db):
    project = alice.create_project()
    asset = alice.upload(project)
    alice.confirm_rights(asset)
    original = alice.submit(project, asset).json()["job"]["id"]
    path = f"/v1/jobs/{original}/retry"
    assert alice.post(path).status_code == 409
    assert bob.post(path).status_code == 404
    db.execute("UPDATE render_jobs SET status = 'failed' WHERE id = %s", (original,))
    first = alice.post(path)
    assert first.status_code == 202, first.text
    assert first.json()["job"]["id"] != original
    second = alice.post(path)
    assert second.json()["deduplicated"] is True
    assert second.json()["job"]["id"] == first.json()["job"]["id"]


def test_health_reports_database(client):
    body = client.get("/health").json()
    assert body == {"status": "ok", "database": True}


def test_console_is_served_for_manual_checks(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "AutoShorts" in response.text


def test_signup_creates_workspace_and_credits(alice):
    body = alice.get("/v1/me").json()
    assert body["user"]["email"] == "alice@example.com"
    assert len(body["workspaces"]) == 1
    assert body["workspaces"][0]["role"] == "owner"
    assert body["workspaces"][0]["credit_balance"] > 0


def test_duplicate_signup_rejected(client, alice):
    response = client.post("/v1/auth/signup",
                           json={"email": "alice@example.com", "password": PASSWORD})
    assert response.status_code == 409


def test_weak_password_rejected(client):
    response = client.post("/v1/auth/signup", json={"email": "weak@example.com", "password": "123"})
    assert response.status_code == 400


def test_login_returns_a_working_token(client, alice):
    response = client.post("/v1/auth/login",
                           json={"email": "alice@example.com", "password": PASSWORD})
    assert response.status_code == 200
    token = response.json()["token"]
    assert client.get("/v1/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_wrong_password_rejected(client, alice):
    response = client.post("/v1/auth/login",
                           json={"email": "alice@example.com", "password": "wrong-password-x"})
    assert response.status_code == 401


@pytest.mark.parametrize("headers", [
    {},
    {"Authorization": "Bearer ast_garbage"},
    {"Authorization": "Basic abc"},
])
def test_unauthenticated_requests_rejected(client, headers):
    assert client.get("/v1/me", headers=headers).status_code == 401


def test_logout_revokes_the_token(client, alice):
    assert client.post("/v1/auth/logout", headers=alice.headers).status_code == 204
    assert alice.get("/v1/me").status_code == 401


# ── E2E: User A 의 전체 흐름 ───────────────────────────────


def test_user_a_project_upload_job_result(db, alice, worker):
    """명세 E2E 1: User A project → upload → job → result."""
    project_id = alice.create_project("내 프로젝트")

    asset_id = alice.upload(project_id)
    detail = alice.get(f"/v1/projects/{project_id}").json()
    asset = detail["assets"][0]
    assert asset["upload_state"] == "uploaded"
    assert asset["size_bytes"] == len(VIDEO)
    assert asset["rights_status"] == "unverified"

    assert alice.confirm_rights(asset_id).status_code == 201

    submitted = alice.submit(project_id, asset_id)
    assert submitted.status_code == 202, submitted.text
    job = submitted.json()["job"]
    assert job["status"] == "queued"
    assert submitted.json()["reserved_credits"] > 0

    # 요청 스레드에서 렌더하지 않는다. 워커가 별도로 처리한다.
    assert worker.run_once() is True

    done = alice.get(f"/v1/jobs/{job['id']}").json()
    assert done["status"] == "succeeded"
    assert done["progress"] == 100.0
    assert len(done["outputs_detail"]) == 2
    assert len(done["candidates"]) == 2

    progress = alice.get(f"/v1/jobs/{job['id']}/progress").json()
    assert [e["stage"] for e in progress["events"]][-1] == "render"

    download = alice.get(f"/v1/outputs/{done['outputs_detail'][0]['id']}/download")
    assert download.status_code == 200
    assert len(download.content) == 2048


def test_upload_creates_a_project_revision(alice):
    project_id = alice.create_project()
    alice.upload(project_id)
    detail = alice.get(f"/v1/projects/{project_id}").json()
    assert detail["project"]["revision"] == 2
    assert [r["change_kind"] for r in detail["revisions"]] == ["asset_added", "created"]


def test_job_records_the_project_revision_it_ran_against(alice, db):
    project_id = alice.create_project()
    asset_id = alice.upload(project_id)
    alice.confirm_rights(asset_id)
    job_id = alice.submit(project_id, asset_id).json()["job"]["id"]
    assert alice.get(f"/v1/jobs/{job_id}").json()["project_revision"] == 2


def test_unverified_rights_hold_the_job(alice, worker):
    """권리 확인 없이 제출하면 렌더 전에 멈춘다."""
    project_id = alice.create_project()
    asset_id = alice.upload(project_id)
    job_id = alice.submit(project_id, asset_id).json()["job"]["id"]
    worker.run_once()

    job = alice.get(f"/v1/jobs/{job_id}").json()
    assert job["status"] == "needs_approval"
    assert job["outputs_detail"] == []


def test_resubmitting_the_same_work_does_not_charge_twice(alice, db):
    """중복 클릭이 크레딧을 두 번 태우지 않는다."""
    project_id = alice.create_project()
    asset_id = alice.upload(project_id)
    alice.confirm_rights(asset_id)

    first = alice.submit(project_id, asset_id).json()
    after_first = alice.get(f"/v1/workspaces/{alice.workspace}/usage").json()["credits"]

    second = alice.submit(project_id, asset_id).json()
    assert second["deduplicated"] is True
    assert second["job"]["id"] == first["job"]["id"]
    assert alice.get(f"/v1/workspaces/{alice.workspace}/usage").json()["credits"] == after_first


def test_insufficient_credits_rejected(db, alice):
    project_id = alice.create_project()
    asset_id = alice.upload(project_id)
    alice.confirm_rights(asset_id)
    db.execute("UPDATE workspaces SET credit_balance = 0 WHERE id = %s", (alice.workspace,))
    assert alice.submit(project_id, asset_id).status_code == 402


def test_queued_job_can_be_cancelled_and_credits_return(alice, db):
    project_id = alice.create_project()
    asset_id = alice.upload(project_id)
    alice.confirm_rights(asset_id)
    before = alice.get(f"/v1/workspaces/{alice.workspace}/usage").json()["credits"]["balance"]
    job_id = alice.submit(project_id, asset_id).json()["job"]["id"]

    response = alice.post(f"/v1/jobs/{job_id}/cancel")
    assert response.json()["status"] == "cancelled"
    credits = alice.get(f"/v1/workspaces/{alice.workspace}/usage").json()["credits"]
    assert credits["balance"] == before
    assert credits["reserved"] == 0


def test_finished_job_cannot_be_cancelled(alice, worker):
    project_id = alice.create_project()
    asset_id = alice.upload(project_id)
    alice.confirm_rights(asset_id)
    job_id = alice.submit(project_id, asset_id).json()["job"]["id"]
    worker.run_once()
    assert alice.post(f"/v1/jobs/{job_id}/cancel").status_code == 409


def test_usage_summary_reports_ledgers(alice, worker):
    project_id = alice.create_project()
    asset_id = alice.upload(project_id)
    alice.confirm_rights(asset_id)
    alice.submit(project_id, asset_id)
    worker.run_once()

    summary = alice.get(f"/v1/workspaces/{alice.workspace}/usage").json()
    usage = {row["event_type"] for row in summary["usage"]}
    assert {"upload_bytes", "job_submitted", "job_succeeded", "render_output_seconds"} <= usage
    assert summary["cost"]
    assert [e["entry_type"] for e in summary["credit_ledger"]][-1] == "grant"


def test_unsupported_content_type_rejected(alice):
    project_id = alice.create_project()
    response = alice.post(f"/v1/projects/{project_id}/uploads",
                          json={"filename": "a.exe", "content_type": "application/x-msdownload"})
    assert response.status_code == 415


def test_upload_ticket_cannot_be_replayed(client, alice):
    project_id = alice.create_project()
    ticket = alice.post(f"/v1/projects/{project_id}/uploads",
                        json={"filename": "a.mp4", "content_type": "video/mp4"}).json()
    url = ticket["upload"]["url"]
    assert client.put(url, content=VIDEO).status_code == 200
    assert client.put(url, content=VIDEO).status_code == 409


def test_tampered_upload_signature_rejected(client, alice):
    project_id = alice.create_project()
    ticket = alice.post(f"/v1/projects/{project_id}/uploads",
                        json={"filename": "a.mp4", "content_type": "video/mp4"}).json()
    url = ticket["upload"]["url"]
    forged = url.rsplit("signature=", 1)[0] + "signature=" + "0" * 64
    assert client.put(forged, content=VIDEO).status_code == 403


def test_job_needs_a_completed_upload(alice):
    project_id = alice.create_project()
    ticket = alice.post(f"/v1/projects/{project_id}/uploads",
                        json={"filename": "a.mp4", "content_type": "video/mp4"}).json()
    assert alice.submit(project_id, ticket["asset_id"]).status_code == 409


def test_job_needs_a_source(alice):
    project_id = alice.create_project()
    assert alice.post(f"/v1/projects/{project_id}/jobs", json={}).status_code == 400


# ── E2E: User B 는 A 의 것에 닿지 못한다 ───────────────────


def test_user_b_cannot_see_user_a_project(alice, bob):
    """명세 E2E 2: User B → A project/file 접근 거부."""
    project_id = alice.create_project("A 의 비밀 프로젝트")
    assert alice.get(f"/v1/projects/{project_id}").status_code == 200
    assert bob.get(f"/v1/projects/{project_id}").status_code == 404


def test_user_b_cannot_list_user_a_projects(alice, bob):
    alice.create_project()
    assert bob.get(f"/v1/workspaces/{alice.workspace}/projects").status_code == 404
    assert bob.get(f"/v1/workspaces/{bob.workspace}/projects").json()["projects"] == []


def test_user_b_cannot_upload_into_user_a_project(alice, bob):
    project_id = alice.create_project()
    response = bob.post(f"/v1/projects/{project_id}/uploads",
                        json={"filename": "evil.mp4", "content_type": "video/mp4"})
    assert response.status_code == 404


def test_user_b_cannot_read_user_a_asset_or_confirm_its_rights(alice, bob):
    project_id = alice.create_project()
    asset_id = alice.upload(project_id)
    assert bob.post(f"/v1/assets/{asset_id}/rights", json={"status": "owned"}).status_code == 404


def test_user_b_cannot_submit_a_job_on_user_a_project(alice, bob):
    project_id = alice.create_project()
    asset_id = alice.upload(project_id)
    alice.confirm_rights(asset_id)
    assert bob.submit(project_id, asset_id).status_code == 404


def test_user_b_cannot_read_user_a_job(alice, bob, worker):
    project_id = alice.create_project()
    asset_id = alice.upload(project_id)
    alice.confirm_rights(asset_id)
    job_id = alice.submit(project_id, asset_id).json()["job"]["id"]
    worker.run_once()

    assert alice.get(f"/v1/jobs/{job_id}").status_code == 200
    assert bob.get(f"/v1/jobs/{job_id}").status_code == 404
    assert bob.get(f"/v1/jobs/{job_id}/progress").status_code == 404
    assert bob.post(f"/v1/jobs/{job_id}/cancel").status_code == 404


def test_user_b_cannot_download_user_a_output(alice, bob, worker):
    """명세 E2E 2 의 'file 접근 거부' — 산출물 바이트까지 막혀야 한다."""
    project_id = alice.create_project()
    asset_id = alice.upload(project_id)
    alice.confirm_rights(asset_id)
    job_id = alice.submit(project_id, asset_id).json()["job"]["id"]
    worker.run_once()
    output_id = alice.get(f"/v1/jobs/{job_id}").json()["outputs_detail"][0]["id"]

    assert alice.get(f"/v1/outputs/{output_id}/download").status_code == 200
    assert bob.get(f"/v1/outputs/{output_id}/download").status_code == 404


def test_user_b_cannot_list_user_a_jobs_or_usage(alice, bob):
    assert bob.get(f"/v1/workspaces/{alice.workspace}/jobs").status_code == 404
    assert bob.get(f"/v1/workspaces/{alice.workspace}/usage").status_code == 404
    assert bob.get(f"/v1/workspaces/{alice.workspace}/members").status_code == 404


def test_same_source_in_two_workspaces_does_not_share_results(alice, bob, worker):
    """멱등 키가 워크스페이스를 넘어 결과를 공유하면 안 된다."""
    a_project = alice.create_project()
    a_asset = alice.upload(a_project)
    alice.confirm_rights(a_asset)
    a_job = alice.submit(a_project, a_asset).json()

    b_project = bob.create_project()
    b_asset = bob.upload(b_project)
    bob.confirm_rights(b_asset)
    b_job = bob.submit(b_project, b_asset).json()

    assert b_job["deduplicated"] is False
    assert b_job["job"]["id"] != a_job["job"]["id"]


# ── 초대와 역할 ────────────────────────────────────────────


def test_invited_member_gains_access(alice, bob):
    project_id = alice.create_project()
    assert bob.get(f"/v1/projects/{project_id}").status_code == 404

    invite = alice.post(f"/v1/workspaces/{alice.workspace}/members",
                        json={"email": "bob@example.com", "role": "editor"})
    assert invite.status_code == 201
    assert bob.get(f"/v1/projects/{project_id}").status_code == 200


def test_viewer_cannot_create_projects(alice, bob):
    alice.post(f"/v1/workspaces/{alice.workspace}/members",
               json={"email": "bob@example.com", "role": "viewer"})
    response = bob.post(f"/v1/workspaces/{alice.workspace}/projects", json={"name": "몰래"})
    assert response.status_code == 403         # 소속은 맞지만 권한이 없다


def test_editor_cannot_invite_members(alice, bob):
    alice.post(f"/v1/workspaces/{alice.workspace}/members",
               json={"email": "bob@example.com", "role": "editor"})
    response = bob.post(f"/v1/workspaces/{alice.workspace}/members",
                        json={"email": "alice@example.com", "role": "viewer"})
    assert response.status_code == 403


def test_inviting_an_unknown_email_fails(alice):
    response = alice.post(f"/v1/workspaces/{alice.workspace}/members",
                          json={"email": "nobody@example.com", "role": "editor"})
    assert response.status_code == 404


def test_unknown_role_rejected(alice, bob):
    response = alice.post(f"/v1/workspaces/{alice.workspace}/members",
                          json={"email": "bob@example.com", "role": "superadmin"})
    assert response.status_code == 400


# ── 워커 지속성 ────────────────────────────────────────────


def test_job_completes_after_the_submitting_client_is_gone(context, db, tmp_path):
    """명세 E2E 4: browser close 후 worker 지속.

    제출에 쓴 HTTP 클라이언트를 완전히 닫은 뒤 워커를 돌리고, **새 클라이언트**로
    결과를 읽는다. 작업이 요청 수명이 아니라 DB+큐에 산다는 뜻이다.
    """
    from fastapi.testclient import TestClient

    app = create_app(context)
    with TestClient(app) as first:
        alice = Account(first, "alice@example.com")
        project_id = alice.create_project()
        asset_id = alice.upload(project_id)
        alice.confirm_rights(asset_id)
        job_id = alice.submit(project_id, asset_id).json()["job"]["id"]
        token = alice.token
    # 여기서 클라이언트(=브라우저)가 사라졌다.

    Worker(
        db,
        config=WorkerConfig(worker_id="detached", work_root=tmp_path / "w",
                            output_root=tmp_path / "o", storage_root=tmp_path / "storage"),
        storage=context.storage,
        run_pipeline=fake_pipeline(clips=2),
    ).run_once()

    with TestClient(app) as second:
        job = second.get(f"/v1/jobs/{job_id}", headers={"Authorization": f"Bearer {token}"}).json()
    assert job["status"] == "succeeded"
    assert len(job["outputs_detail"]) == 2


def test_three_jobs_queue_concurrently(alice, db, context, tmp_path):
    """명세 E2E 3: 3 jobs concurrent queue."""
    import threading

    job_ids = []
    for index in range(3):
        project_id = alice.create_project(f"P{index}")
        asset_id = alice.upload(project_id, body=VIDEO + bytes([index]))
        alice.confirm_rights(asset_id)
        job_ids.append(alice.submit(project_id, asset_id).json()["job"]["id"])

    assert alice.get(f"/v1/workspaces/{alice.workspace}/jobs").json()["queue"]["ready"] == 3

    def drain(name: str) -> None:
        worker = Worker(
            db,
            config=WorkerConfig(worker_id=name, work_root=tmp_path / name / "w",
                                output_root=tmp_path / name / "o",
                                storage_root=tmp_path / "storage"),
            storage=context.storage,
            run_pipeline=fake_pipeline(clips=1, delay=0.1),
        )
        while worker.run_once():
            pass

    threads = [threading.Thread(target=drain, args=(f"w{i}",)) for i in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    listing = alice.get(f"/v1/workspaces/{alice.workspace}/jobs").json()
    assert {job["status"] for job in listing["jobs"]} == {"succeeded"}
    assert len(listing["jobs"]) == 3
    assert listing["queue"]["ready"] == 0
    assert alice.get(f"/v1/workspaces/{alice.workspace}/usage").json()["credits"]["reserved"] == 0
