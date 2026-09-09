"""업데이트 — 코드만 갈아끼우고 사용자 데이터는 절대 건드리지 않는다."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

from utils import updater
from utils.updater import UpdateError, Version, apply_update, check, read_version, write_version

SHA_OLD = "a" * 40
SHA_NEW = "b" * 40


def _make_zip(files: dict[str, str], root="repo-branch", subdir="auto_trader") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        for name, text in files.items():
            bundle.writestr(f"{root}/{subdir}/{name}", text)
    return buffer.getvalue()


COMPLETE = {
    "main.py": "print('new')\n",
    "requirements.txt": "requests>=2.32.0\n",
    "utils/helper.py": "VALUE = 2\n",
    "config/settings.yaml": "risk:\n  stop_loss_pct: -5\n",
}


@pytest.fixture
def install(tmp_path):
    """키와 운영 데이터가 들어 있는 기존 설치."""
    base = tmp_path / "auto_trader"
    (base / "utils").mkdir(parents=True)
    (base / "config").mkdir()
    (base / "data").mkdir()
    (base / "logs").mkdir()
    (base / ".venv").mkdir()

    (base / "main.py").write_text("print('old')\n", encoding="utf-8")
    (base / "requirements.txt").write_text("requests>=2.32.0\n", encoding="utf-8")
    (base / "utils" / "helper.py").write_text("VALUE = 1\n", encoding="utf-8")
    (base / "config" / "settings.yaml").write_text("risk:\n  stop_loss_pct: -5\n", encoding="utf-8")

    # 사용자 데이터 — 이 세 개는 무슨 일이 있어도 그대로여야 한다.
    (base / ".env").write_text("ANTHROPIC_API_KEY=sk-ant-mine\n", encoding="utf-8")
    (base / "data" / "trader.db").write_bytes(b"sqlite-bytes")
    (base / "logs" / "trader.log").write_text("어제 기록\n", encoding="utf-8")
    (base / ".venv" / "marker").write_text("venv\n", encoding="utf-8")
    return base


@pytest.fixture
def remote(monkeypatch):
    """GitHub 대역. payload 를 바꿔 상황을 만든다."""
    state = {"zip": _make_zip(COMPLETE), "sha": SHA_NEW, "message": "새 기능"}

    def fake_get(url, *, as_json=False):
        if as_json:
            return {"sha": state["sha"], "commit": {"message": state["message"]}}
        return state["zip"]

    monkeypatch.setattr(updater, "_http_get", fake_get)
    return state


# --- 사용자 데이터 보존 (가장 중요) ---------------------------------------- #


def test_env_file_is_never_touched(install, remote):
    apply_update(install)
    assert (install / ".env").read_text(encoding="utf-8") == "ANTHROPIC_API_KEY=sk-ant-mine\n"


def test_database_and_logs_survive(install, remote):
    apply_update(install)
    assert (install / "data" / "trader.db").read_bytes() == b"sqlite-bytes"
    assert (install / "logs" / "trader.log").read_text(encoding="utf-8") == "어제 기록\n"


def test_venv_is_left_alone(install, remote):
    apply_update(install)
    assert (install / ".venv" / "marker").exists()


def test_env_survives_repeated_updates(install, remote):
    for sha in ("c" * 40, "d" * 40, "e" * 40):
        remote["sha"] = sha
        apply_update(install)
    assert "sk-ant-mine" in (install / ".env").read_text(encoding="utf-8")


# --- 코드 교체 -------------------------------------------------------------- #


def test_code_files_are_replaced(install, remote):
    apply_update(install)
    assert (install / "main.py").read_text(encoding="utf-8") == "print('new')\n"
    assert (install / "utils" / "helper.py").read_text(encoding="utf-8") == "VALUE = 2\n"


def test_stale_module_is_removed(install, remote):
    """지워진 모듈이 남아 있으면 안 된다."""
    (install / "utils" / "gone.py").write_text("old\n", encoding="utf-8")
    apply_update(install)
    assert not (install / "utils" / "gone.py").exists()


def test_version_is_recorded(install, remote):
    result = apply_update(install)
    assert result.version.sha == SHA_NEW
    assert read_version(install).sha == SHA_NEW
    assert read_version(install).updated_at


# --- 설정 파일은 덮어쓰지 않는다 --------------------------------------------- #


def test_user_edited_settings_are_kept(install, remote):
    (install / "config" / "settings.yaml").write_text(
        "risk:\n  stop_loss_pct: -3\n", encoding="utf-8")
    remote["zip"] = _make_zip({**COMPLETE, "config/settings.yaml": "risk:\n  stop_loss_pct: -9\n"})

    result = apply_update(install)

    assert "-3" in (install / "config" / "settings.yaml").read_text(encoding="utf-8")
    assert (install / "config" / "settings.yaml.new").exists()
    assert any("settings.yaml" in note for note in result.notes)


def test_identical_settings_leave_no_new_file(install, remote):
    apply_update(install)
    assert not (install / "config" / "settings.yaml.new").exists()


def test_missing_settings_are_created(install, remote):
    (install / "config" / "settings.yaml").unlink()
    apply_update(install)
    assert (install / "config" / "settings.yaml").exists()


# --- 안전장치 --------------------------------------------------------------- #


def test_incomplete_download_changes_nothing(install, remote):
    remote["zip"] = _make_zip({"README.md": "설명뿐\n"})  # main.py 없음

    with pytest.raises(UpdateError, match="온전하지"):
        apply_update(install)

    assert (install / "main.py").read_text(encoding="utf-8") == "print('old')\n"
    assert (install / ".env").exists()


def test_corrupt_archive_changes_nothing(install, remote):
    remote["zip"] = "이건 zip 이 아니다".encode("utf-8")

    with pytest.raises(UpdateError, match="손상"):
        apply_update(install)

    assert (install / "main.py").read_text(encoding="utf-8") == "print('old')\n"


def test_network_failure_is_reported_plainly(install, monkeypatch):
    def boom(url, *, as_json=False):
        raise UpdateError("인터넷 연결을 확인하세요 (timed out)")

    monkeypatch.setattr(updater, "_http_get", boom)
    with pytest.raises(UpdateError, match="인터넷 연결"):
        apply_update(install)


def test_dependency_change_is_flagged(install, remote):
    remote["zip"] = _make_zip({**COMPLETE, "requirements.txt": "requests>=2.32.0\nnewpkg>=1.0\n"})
    result = apply_update(install)
    assert result.deps_changed
    assert any("의존성" in note for note in result.notes)


def test_unchanged_dependencies_are_not_flagged(install, remote):
    assert not apply_update(install).deps_changed


# --- 버전 확인 -------------------------------------------------------------- #


def test_check_reports_available_update(install, remote):
    write_version(install, Version(sha=SHA_OLD))
    available, current, latest = check(install)
    assert available and current.sha == SHA_OLD and latest.sha == SHA_NEW


def test_check_reports_up_to_date(install, remote):
    write_version(install, Version(sha=SHA_NEW))
    available, _, _ = check(install)
    assert not available


def test_check_treats_fresh_install_as_updatable(install, remote):
    available, current, _ = check(install)
    assert available and current.sha == ""


def test_broken_version_file_is_tolerated(install):
    (install / "data" / "version.json").write_text("{깨진 json", encoding="utf-8")
    assert read_version(install).sha == ""
