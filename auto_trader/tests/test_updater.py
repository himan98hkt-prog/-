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


def test_version_is_recorded_even_if_the_lookup_fails(install, remote, monkeypatch):
    """코드는 새것인데 화면에 옛 버전이 남으면 '업데이트가 안 됐다' 로 오해한다."""
    original = updater._http_get  # 픽스처가 이미 대역으로 바꿔 둔 것

    def flaky(url, *, as_json=False):
        # apply_update 는 마지막에 버전 조회만 as_json 으로 한다.
        if as_json:
            raise UpdateError("인터넷 연결을 확인하세요")
        return original(url, as_json=as_json)

    monkeypatch.setattr(updater, "_http_get", flaky)

    result = apply_update(install)
    assert (install / "main.py").read_text(encoding="utf-8") == "print('new')\n"
    assert read_version(install).updated_at, "언제 갱신했는지는 남아야 합니다"
    assert "코드는 갱신됨" in result.version.message


# --- 설정 파일: 손댔으면 지키고, 안 댔으면 갱신 ------------------------------ #

def test_edited_settings_are_never_overwritten(install, remote):
    """직접 고친 매매 파라미터를 업데이트가 덮어쓰면 안 된다."""
    settings = install / "config" / "settings.yaml"
    settings.write_text("risk:\n  stop_loss_pct: -3   # 내가 고침\n", encoding="utf-8")
    remote["zip"] = _make_zip({**COMPLETE, "config/settings.yaml": "risk:\n  stop_loss_pct: -9\n"})

    result = apply_update(install)

    assert "내가 고침" in settings.read_text(encoding="utf-8")
    assert (install / "config" / "settings.yaml.new").exists()
    assert any("직접 고치신" in note for note in result.notes)


def test_untouched_settings_are_updated_in_place(install, remote):
    """손댄 적 없는 설정은 새 기본값으로 갱신돼야 한다.

    그러지 않으면 매매 파라미터를 바꿔도 사용자가 파일 이름을 손으로
    바꿔야만 반영된다.
    """
    settings = install / "config" / "settings.yaml"
    # 첫 업데이트가 '우리가 내려준 값' 을 기록한다.
    apply_update(install)
    assert settings.read_text(encoding="utf-8") == COMPLETE["config/settings.yaml"]

    # 사용자가 손대지 않은 채 다음 업데이트가 새 기본값을 들고 온다.
    remote["zip"] = _make_zip({**COMPLETE, "config/settings.yaml": "risk:\n  stop_loss_pct: -7\n"})
    result = apply_update(install)

    assert settings.read_text(encoding="utf-8") == "risk:\n  stop_loss_pct: -7\n"
    assert not (install / "config" / "settings.yaml.new").exists()
    assert any("새 기본값으로 갱신" in note for note in result.notes)


def test_known_shipped_default_is_recognised_without_a_record(install, remote, monkeypatch):
    """갱신 기록이 없는 설치본에서도 '손대지 않음' 을 알아봐야 한다."""
    import hashlib

    settings = install / "config" / "settings.yaml"
    original = settings.read_bytes()
    monkeypatch.setitem(updater.SHIPPED_DEFAULTS, "config/settings.yaml",
                        {hashlib.sha256(original).hexdigest()})
    remote["zip"] = _make_zip({**COMPLETE, "config/settings.yaml": "risk:\n  stop_loss_pct: -8\n"})

    apply_update(install)

    assert settings.read_text(encoding="utf-8") == "risk:\n  stop_loss_pct: -8\n"
    assert not (install / "config" / "settings.yaml.new").exists()


def test_recording_a_version_does_not_wipe_config_hashes(install, remote):
    """버전만 다시 적는 호출이 해시 기록을 지우면 안 된다."""
    apply_update(install)
    before = updater.read_config_hashes(install)
    assert before

    updater.write_version(install, updater.Version(sha="x", message="y"))
    assert updater.read_config_hashes(install) == before


# --- 업데이트 누락 방지 -------------------------------------------------------- #

def test_every_python_file_is_covered_by_the_update():
    """빠진 파일은 **영원히** 옛 버전으로 남는다.

    config/loader.py 가 이 목록에 없어서 한 번도 갱신되지 않았고, 설정 스키마를
    고칠 때마다 사용자 화면에 '없는 속성' 오류가 났다. 다시는 조용히 빠지지 않게
    한다.
    """
    from utils.updater import CODE_DIRS, CODE_FILES

    root = Path(__file__).resolve().parent.parent
    uncovered = []
    for path in root.rglob("*.py"):
        relative = path.relative_to(root)
        if "__pycache__" in relative.parts or ".venv" in relative.parts:
            continue
        if relative.parts[0] in CODE_DIRS:
            continue
        if relative.as_posix() in CODE_FILES:
            continue
        uncovered.append(relative.as_posix())

    assert not uncovered, (
        "업데이트가 건드리지 않는 파이썬 파일이 있습니다 — "
        f"CODE_DIRS 나 CODE_FILES 에 넣으세요: {sorted(uncovered)}"
    )


def test_user_settings_survive_a_config_code_update(install, remote):
    """config/ 를 통째로 복사하면 사용자가 고친 매매 파라미터가 날아간다."""
    settings = install / "config" / "settings.yaml"
    settings.write_text("risk:\n  stop_loss_pct: -3   # 내가 고침\n", encoding="utf-8")
    (install / "config" / "loader.py").write_text("VERSION = 1\n", encoding="utf-8")

    remote["zip"] = _make_zip({
        **COMPLETE,
        "config/loader.py": "VERSION = 2\n",
        "config/settings.yaml": "risk:\n  stop_loss_pct: -9\n",
    })
    apply_update(install)

    assert (install / "config" / "loader.py").read_text(encoding="utf-8") == "VERSION = 2\n"
    assert "내가 고침" in settings.read_text(encoding="utf-8"), "사용자 설정이 날아갔습니다"
