"""Storage keys must remain inside the root, including symlink resolution."""

import pytest

from autoshorts.storage import LocalStorage, StorageError


@pytest.mark.parametrize("operation", ["open_local", "uri_for", "put"])
def test_prefix_sibling_is_rejected(tmp_path, operation):
    storage = LocalStorage(tmp_path / "media")
    outside = tmp_path / "media-other"
    outside.mkdir()
    target = outside / "clip.mp4"
    target.write_bytes(b"original")
    source = tmp_path / "source.mp4"
    source.write_bytes(b"replacement")
    key = "../media-other/clip.mp4"
    with pytest.raises(StorageError):
        if operation == "put":
            storage.put(source, key)
        else:
            getattr(storage, operation)(key)
    assert target.read_bytes() == b"original"
    assert not storage.exists(key)


def test_symlink_to_prefix_sibling_is_rejected(tmp_path):
    storage = LocalStorage(tmp_path / "media")
    outside = tmp_path / "media-other"
    outside.mkdir()
    (outside / "clip.mp4").write_bytes(b"private")
    try:
        (storage.root / "link").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks unavailable on this platform")
    with pytest.raises(StorageError):
        storage.open_local("link/clip.mp4")


def test_nested_roundtrip_still_works(tmp_path):
    storage = LocalStorage(tmp_path / "media")
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    storage.put(source, "workspace/project/clip.mp4")
    assert storage.open_local("workspace/project/clip.mp4").read_bytes() == b"video"


def test_db_fixture_never_uses_application_database(monkeypatch):
    from conftest import _test_dsn

    monkeypatch.delenv("AUTOSHORTS_TEST_DATABASE_URL", raising=False)
    monkeypatch.setenv("AUTOSHORTS_DATABASE_URL", "postgresql://production/app")
    assert _test_dsn() == ""
    monkeypatch.setenv("AUTOSHORTS_TEST_DATABASE_URL", "postgresql://localhost/disposable")
    assert _test_dsn() == "postgresql://localhost/disposable"
