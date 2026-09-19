"""저장소 계층 — 특히 워크스페이스 격리."""

from __future__ import annotations

import pytest

from saas.auth import InvalidCredentials
from saas.repositories import (
    AssetRepository,
    DuplicateEmail,
    ProjectRepository,
    UserRepository,
    WorkspaceRepository,
)

PASSWORD = "a-long-enough-password"


@pytest.fixture
def repos(db):
    return {
        "users": UserRepository(db),
        "workspaces": WorkspaceRepository(db),
        "projects": ProjectRepository(db),
        "assets": AssetRepository(db),
    }


@pytest.fixture
def two_tenants(repos):
    """서로 모르는 사용자 두 명과 각자의 워크스페이스·프로젝트."""
    made = {}
    for label, email in (("a", "a@example.com"), ("b", "b@example.com")):
        user = repos["users"].create(email, PASSWORD)
        workspace = repos["workspaces"].create(f"{label} 워크스페이스", user["id"])
        project = repos["projects"].create(workspace["id"], f"{label} 프로젝트", user["id"])
        made[label] = {"user": user, "workspace": workspace, "project": project}
    return made


# ── 사용자 ─────────────────────────────────────────────────


def test_signup_and_login(repos):
    user = repos["users"].create("New@Example.com", PASSWORD, "새 사용자")
    assert user["email"] == "new@example.com"
    assert repos["users"].authenticate("new@example.com", PASSWORD)["id"] == user["id"]


def test_login_is_case_insensitive_on_email(repos):
    repos["users"].create("mixed@example.com", PASSWORD)
    assert repos["users"].authenticate("MIXED@Example.COM", PASSWORD)


def test_duplicate_email_rejected(repos):
    repos["users"].create("dup@example.com", PASSWORD)
    with pytest.raises(DuplicateEmail):
        repos["users"].create("DUP@example.com", PASSWORD)


def test_wrong_password_and_unknown_account_fail_identically(repos):
    repos["users"].create("known@example.com", PASSWORD)
    with pytest.raises(InvalidCredentials) as wrong:
        repos["users"].authenticate("known@example.com", "not-the-password")
    with pytest.raises(InvalidCredentials) as unknown:
        repos["users"].authenticate("nobody@example.com", PASSWORD)
    # 메시지가 다르면 계정 존재 여부가 새어나간다.
    assert str(wrong.value) == str(unknown.value)


def test_disabled_account_cannot_log_in(repos, db):
    user = repos["users"].create("off@example.com", PASSWORD)
    db.execute("UPDATE users SET disabled_at = now() WHERE id = %s", (user["id"],))
    with pytest.raises(InvalidCredentials):
        repos["users"].authenticate("off@example.com", PASSWORD)


# ── 세션 ───────────────────────────────────────────────────


def test_session_token_resolves_to_principal_with_memberships(repos, two_tenants):
    user = two_tenants["a"]["user"]
    token, _ = repos["users"].issue_session(user["id"])
    principal = repos["users"].principal_for_token(token)
    assert principal.user_id == user["id"]
    assert principal.memberships == {two_tenants["a"]["workspace"]["id"]: "owner"}
    assert two_tenants["b"]["workspace"]["id"] not in principal.memberships


def test_plaintext_token_is_not_stored(repos, two_tenants, db):
    token, _ = repos["users"].issue_session(two_tenants["a"]["user"]["id"])
    rows = db.fetch_all("SELECT token_hash FROM sessions")
    assert rows and all(row["token_hash"] != token for row in rows)


def test_revoked_session_is_rejected(repos, two_tenants):
    token, _ = repos["users"].issue_session(two_tenants["a"]["user"]["id"])
    repos["users"].revoke_session(token)
    assert repos["users"].principal_for_token(token) is None


def test_expired_session_is_rejected(repos, two_tenants, db):
    token, _ = repos["users"].issue_session(two_tenants["a"]["user"]["id"])
    db.execute("UPDATE sessions SET expires_at = now() - interval '1 hour'")
    assert repos["users"].principal_for_token(token) is None


def test_garbage_token_is_rejected(repos):
    assert repos["users"].principal_for_token("ast_not-a-real-token") is None
    assert repos["users"].principal_for_token("") is None


# ── 격리 ───────────────────────────────────────────────────


def test_project_of_another_workspace_is_invisible(repos, two_tenants):
    a, b = two_tenants["a"], two_tenants["b"]
    assert repos["projects"].get(a["workspace"]["id"], a["project"]["id"]) is not None
    # B 의 워크스페이스 범위로 A 의 프로젝트를 찾으면 없어야 한다.
    assert repos["projects"].get(b["workspace"]["id"], a["project"]["id"]) is None


def test_project_list_is_scoped(repos, two_tenants):
    listed = repos["projects"].list(two_tenants["b"]["workspace"]["id"])
    assert [p["id"] for p in listed] == [two_tenants["b"]["project"]["id"]]


def test_asset_of_another_workspace_is_invisible(repos, two_tenants):
    a, b = two_tenants["a"], two_tenants["b"]
    asset = repos["assets"].create(
        a["workspace"]["id"], a["project"]["id"], origin="upload",
        uploaded_by=a["user"]["id"], original_filename="a.mp4",
    )
    assert repos["assets"].get(a["workspace"]["id"], asset["id"]) is not None
    assert repos["assets"].get(b["workspace"]["id"], asset["id"]) is None


def test_rights_confirmation_across_tenants_is_refused(repos, two_tenants):
    a, b = two_tenants["a"], two_tenants["b"]
    asset = repos["assets"].create(
        a["workspace"]["id"], a["project"]["id"], origin="upload", uploaded_by=a["user"]["id"]
    )
    with pytest.raises(LookupError):
        repos["assets"].confirm_rights(
            b["workspace"]["id"], asset["id"], status="owned", confirmed_by=b["user"]["id"]
        )


def test_membership_grants_access(repos, two_tenants):
    a, b = two_tenants["a"], two_tenants["b"]
    repos["workspaces"].add_member(a["workspace"]["id"], b["user"]["id"], "viewer")
    token, _ = repos["users"].issue_session(b["user"]["id"])
    principal = repos["users"].principal_for_token(token)
    assert principal.role_in(a["workspace"]["id"]) == "viewer"
    assert principal.role_in(b["workspace"]["id"]) == "owner"


# ── 권리 · 출처 ────────────────────────────────────────────


def test_new_asset_defaults_to_unverified_rights(repos, two_tenants):
    a = two_tenants["a"]
    asset = repos["assets"].create(
        a["workspace"]["id"], a["project"]["id"], origin="upload", uploaded_by=a["user"]["id"]
    )
    row = repos["assets"].get(a["workspace"]["id"], asset["id"])
    assert row["rights_status"] == "unverified"
    assert row["upload_state"] == "pending"


def test_url_asset_records_provenance(repos, two_tenants):
    a = two_tenants["a"]
    asset = repos["assets"].create(
        a["workspace"]["id"], a["project"]["id"], origin="url",
        uploaded_by=a["user"]["id"], source_url="https://example.com/v.mp4",
    )
    row = repos["assets"].get(a["workspace"]["id"], asset["id"])
    assert (row["origin"], row["source_url"]) == ("url", "https://example.com/v.mp4")
    assert row["uploaded_by"] == a["user"]["id"]


def test_rights_history_is_append_only(repos, two_tenants):
    """누가 언제 무엇을 근거로 확인했는지 나중에 답할 수 있어야 한다."""
    a = two_tenants["a"]
    asset = repos["assets"].create(
        a["workspace"]["id"], a["project"]["id"], origin="upload", uploaded_by=a["user"]["id"]
    )
    repos["assets"].confirm_rights(
        a["workspace"]["id"], asset["id"], status="licensed",
        confirmed_by=a["user"]["id"], evidence_uri="https://example.com/license",
    )
    repos["assets"].confirm_rights(
        a["workspace"]["id"], asset["id"], status="owned", confirmed_by=a["user"]["id"]
    )
    history = repos["assets"].rights_history(a["workspace"]["id"], asset["id"])
    assert [h["status"] for h in history] == ["owned", "licensed"]
    assert repos["assets"].get(a["workspace"]["id"], asset["id"])["rights_status"] == "owned"


def test_upload_completion_records_checksum(repos, two_tenants):
    a = two_tenants["a"]
    asset = repos["assets"].create(
        a["workspace"]["id"], a["project"]["id"], origin="upload", uploaded_by=a["user"]["id"]
    )
    repos["assets"].mark_uploaded(a["workspace"]["id"], asset["id"], size_bytes=1234, checksum="ab" * 32)
    row = repos["assets"].get(a["workspace"]["id"], asset["id"])
    assert (row["upload_state"], row["size_bytes"], row["checksum_sha256"]) == (
        "uploaded", 1234, "ab" * 32
    )


# ── 프로젝트 개정 ──────────────────────────────────────────


def test_project_starts_at_revision_one_with_history(repos, two_tenants):
    a = two_tenants["a"]
    revisions = repos["projects"].revisions(a["workspace"]["id"], a["project"]["id"])
    assert [(r["revision"], r["change_kind"]) for r in revisions] == [(1, "created")]


def test_revision_increments_and_records_change(repos, two_tenants):
    a = two_tenants["a"]
    assert repos["projects"].bump_revision(
        a["workspace"]["id"], a["project"]["id"], "asset_added", changed_by=a["user"]["id"]
    ) == 2
    assert repos["projects"].bump_revision(
        a["workspace"]["id"], a["project"]["id"], "renamed", changed_by=a["user"]["id"]
    ) == 3
    project = repos["projects"].get(a["workspace"]["id"], a["project"]["id"])
    assert project["revision"] == 3
    kinds = [r["change_kind"] for r in repos["projects"].revisions(
        a["workspace"]["id"], a["project"]["id"])]
    assert kinds == ["renamed", "asset_added", "created"]


def test_revision_bump_across_tenants_is_refused(repos, two_tenants):
    a, b = two_tenants["a"], two_tenants["b"]
    with pytest.raises(LookupError):
        repos["projects"].bump_revision(b["workspace"]["id"], a["project"]["id"], "renamed")
