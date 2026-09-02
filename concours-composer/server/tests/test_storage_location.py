"""만든 곡이 **어디에** 저장되는가.

원장이 곡을 통째로 잃었다. 새 판을 받는 방법이 "ZIP 을 다시 받아 폴더를 지우고 새로
푼다" 인데, 만든 곡이 **그 폴더 안**(`ROOT/data`)에 저장되고 있었기 때문이다.
폴더를 지우는 순간 곡도 함께 지워진다.

그래서 자료를 사람 계정에 딸린 자리로 옮긴다. 프로그램을 몇 번을 다시 깔아도 그대로다.
여기서 지키는 것은 넷이다.

1. 기본 자리는 **프로그램 폴더 바깥**이다.
2. 옛 자리에 있던 자료는 옮겨 오되 **지우지 않는다** — 옮기다 잘못되면 되돌릴 수 없다.
3. 새 자리에 이미 저장 파일이 있으면 **손대지 않는다**(그쪽이 최신이다).
4. 예시 설정(.env.example)이 다시 프로그램 폴더를 가리키지 않는다 — 그것이 원인이었다.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app.api.deps import STORE
from app.config import ROOT, migrate_old_data, user_data_dir
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    for bucket in (STORE.students, STORE.compositions, STORE.books):
        bucket.clear()
    with TestClient(app) as c:
        yield c


def test_the_default_place_is_outside_the_program_folder() -> None:
    """폴더를 지워도 곡이 남아야 한다 — 그것이 이 자리의 존재 이유다."""
    d = user_data_dir()
    assert not str(d.resolve()).startswith(str(ROOT.resolve()) + "/"), (
        f"자료가 프로그램 폴더 안({d})에 저장된다 — 새 판을 받으면 곡이 사라진다"
    )
    assert "ConcoursComposer" in str(d), "어느 프로그램의 자료인지 폴더 이름에 드러나야 한다"


def test_the_example_settings_do_not_pin_the_program_folder() -> None:
    """`.env.example` 이 DATA_DIR=./data 로 못 박고 있었다 — 이것이 곡을 날린 원인이다."""
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    live = [
        ln.strip()
        for ln in text.splitlines()
        if ln.strip().startswith("DATA_DIR=") and not ln.strip().startswith("#")
    ]
    assert not live, f"예시 설정이 자료 자리를 못 박고 있다: {live}"


def test_old_data_is_copied_not_moved(tmp_path: Path, monkeypatch) -> None:
    """옮기다 잘못되면 원장의 곡이 사라진다 — 옛 폴더는 그대로 둔다."""
    import app.config as cfg

    old = tmp_path / "program" / "data"
    old.mkdir(parents=True)
    (old / "store.sqlite3").write_bytes(b"sqlite-ish")
    (old / "reference_scores").mkdir()
    (old / "reference_scores" / "a.musicxml").write_text("<score/>", encoding="utf-8")
    (old / "backups").mkdir()
    (old / "backups" / "store-20260101-000000.sqlite3").write_bytes(b"old")

    monkeypatch.setattr(cfg, "ROOT", tmp_path / "program")
    new = tmp_path / "userdata"
    new.mkdir()

    moved = migrate_old_data(new)

    assert (new / "store.sqlite3").read_bytes() == b"sqlite-ish"
    assert (new / "reference_scores" / "a.musicxml").exists(), "참고 악보도 함께 와야 한다"
    assert not (new / "backups").exists(), "사본까지 옮길 필요는 없다 — 원본이 오면 새로 뜬다"
    assert (old / "store.sqlite3").exists(), "옛 파일을 지웠다 — 되돌릴 수 없는 일이다"
    assert "store.sqlite3" in moved


def test_migration_never_overwrites_newer_data(tmp_path: Path, monkeypatch) -> None:
    """새 자리에 이미 저장 파일이 있으면 그쪽이 최신이다 — 옛것으로 덮으면 안 된다."""
    import app.config as cfg

    old = tmp_path / "program" / "data"
    old.mkdir(parents=True)
    (old / "store.sqlite3").write_bytes(b"old")
    monkeypatch.setattr(cfg, "ROOT", tmp_path / "program")

    new = tmp_path / "userdata"
    new.mkdir()
    (new / "store.sqlite3").write_bytes(b"new")

    assert migrate_old_data(new) == ""
    assert (new / "store.sqlite3").read_bytes() == b"new"


def test_migration_is_silent_when_there_is_nothing_to_move(tmp_path: Path, monkeypatch) -> None:
    import app.config as cfg

    monkeypatch.setattr(cfg, "ROOT", tmp_path / "program")
    (tmp_path / "userdata").mkdir()
    assert migrate_old_data(tmp_path / "userdata") == ""


def test_the_screen_can_tell_where_the_pieces_live(client) -> None:
    """"저장은 도대체 어디에 있는가" 는 화면에서 답이 나와야 한다."""
    s = client.get("/api/storage").json()
    assert s["store_file"], "저장 파일 자리를 알려 주지 않는다"
    assert "data_dir" in s and "pieces" in s
    # 프로그램 폴더 안이면 위험을 **말해야** 한다. 아니면 경고가 없어야 한다.
    assert bool(s["warning"]) == bool(s["inside_program_folder"])


def test_an_empty_setting_does_not_land_in_the_program_folder(monkeypatch, tmp_path: Path) -> None:
    """`DATA_DIR=` 처럼 값만 지운 줄은 흔하다.

    파이썬은 빈 경로를 현재 폴더(`.`)로 읽는다. 그러면 자료가 프로그램 폴더 안에
    떨어지고, 새 판을 받을 때 곡이 사라진다 — 고치려던 바로 그 사고다.
    """
    from app.config import get_settings, resolve_data_dir

    monkeypatch.setenv("HOME", str(tmp_path))
    for value in ("", "  ", "."):
        monkeypatch.setenv("DATA_DIR", value)
        get_settings.cache_clear()
        got = resolve_data_dir()
        assert "ConcoursComposer" in str(got), f"DATA_DIR={value!r} 가 {got} 로 떨어졌다"
    get_settings.cache_clear()


def test_a_blocked_folder_moves_aside_instead_of_killing_the_icon(
    monkeypatch, tmp_path
) -> None:
    """저장 폴더를 못 만들면 **아이콘이 먹통이 된다** — 그래서 자리를 옮겨서라도 켜진다.

    백신이 AppData 를 잠그거나, 회사 PC 정책이 쓰기를 막거나, 디스크가 꽉 차면
    `mkdir` 이 실패한다. 창 없는 실행(pythonw)에서는 그 예외가 화면 어디에도
    안 보이고 그냥 아무 일도 안 일어난다 — 원장이 실제로 겪은 그 증상이다.
    """
    import app.config as cfg

    blocked = tmp_path / "막힌곳"
    real_mkdir = Path.mkdir

    def picky_mkdir(self, *a, **kw):  # type: ignore[no-untyped-def]
        if str(self).startswith(str(blocked)):
            raise OSError(13, "액세스가 거부되었습니다")
        return real_mkdir(self, *a, **kw)

    monkeypatch.setattr(Path, "mkdir", picky_mkdir)
    monkeypatch.setattr(cfg.Path, "home", classmethod(lambda cls: tmp_path / "집"))

    got = cfg._writable_or_fallback(blocked)

    assert got.exists(), "쓸 수 있는 자리를 하나도 못 잡았다 — 프로그램이 안 켜진다"
    assert not str(got).startswith(str(blocked))
    assert cfg.data_dir_warning(), "옮겨 앉았는데 화면에 알리지 않으면 곡을 잃어버린 것처럼 보인다"
    assert "저장" in cfg.data_dir_warning()
