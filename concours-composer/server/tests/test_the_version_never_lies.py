"""**BOM 한 글자가 "새 판이 나왔습니다" 를 영영 붙잡고 있었다.**

원장님: "돈띠는 보이는데 위에 새판이 나왔다고 해서 지금 올리기 눌렀더니
         아무 변화없이 있어.. 맞는건가?"

새 판은 없었다. 화면이 그렇게 말한 이유는 이렇다.

  * 판 번호를 적는 쪽은 윈도우 PowerShell 5.1 의 `Set-Content -Encoding UTF8` 이다.
    5.1 의 UTF8 은 **파일 앞에 BOM 세 바이트를 붙인다.**
  * 그것을 읽는 쪽이 `encoding="utf-8"` 이었다. 그러면 값이 "\\ufeffbf43a47..." 이 된다.
  * `latest.startswith(here)` 는 언제나 False → `update_available` 은 **언제나 True**.

그래서 몇 번을 올려도 화면은 "새 판이 나왔습니다" 라고 했고, 눌러도 바뀌는 것이
없었다. 원장님은 이것을 며칠 겪으셨다. 이 파일은 그 한 글자를 다시 들이지 않는다.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app.main import app
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
SHA = "bf43a477565cab0b3c72a2f54aed6e205b8a307a"


@pytest.fixture
def stamped(tmp_path, monkeypatch):
    """설치버전.txt 를 원하는 바이트로 놓고 /api/version 을 물어보게 한다."""
    def put(raw: bytes) -> dict:
        (tmp_path / "설치버전.txt").write_bytes(raw)
        monkeypatch.setattr("app.config.ROOT", tmp_path)
        # 인터넷에 묻지 않고 최신 판 번호를 준다.
        from app.api import health

        health._VERSION_ASKED_AT[0] = 0.0
        health._VERSION_ANSWER.clear()
        monkeypatch.setattr(
            "urllib.request.urlopen",
            lambda *a, **k: _FakeGitHub(SHA),
        )
        with TestClient(app) as c:
            return c.get("/api/version").json()
    return put


class _FakeGitHub:
    def __init__(self, sha: str) -> None:
        self._sha = sha

    def read(self) -> bytes:
        import json

        return json.dumps({"sha": self._sha}).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a) -> None:
        return None


# ── BOM 이 붙어 있어도 최신은 최신이다 ─────────────────────────────────────


def test_a_bom_does_not_make_the_program_look_out_of_date(stamped) -> None:
    """윈도우 PowerShell 5.1 이 적어 준 그대로의 바이트."""
    v = stamped(b"\xef\xbb\xbf" + SHA.encode() + b"\r\n")
    assert v["update_available"] is False, (
        "BOM 하나 때문에 영영 '새 판이 나왔습니다' 라고 한다 — 원장님이 며칠 겪으신 그것"
    )
    assert v["installed"] == "bf43a47", f"판 번호에 안 보이는 글자가 섞였다: {v['installed']!r}"


def test_plain_utf8_still_works(stamped) -> None:
    v = stamped(SHA.encode())
    assert v["update_available"] is False
    assert v["installed"] == "bf43a47"


def test_stray_whitespace_and_case_do_not_matter(stamped) -> None:
    v = stamped(("  " + SHA.upper() + " \r\n").encode())
    assert v["update_available"] is False, "대문자로 적혀 있다고 새 판이 되는 것은 아니다"


def test_a_real_old_version_is_still_reported(stamped) -> None:
    """고치느라 반대쪽을 망가뜨리면 안 된다 — 진짜 옛 판은 옛 판이라고 해야 한다."""
    v = stamped(b"\xef\xbb\xbf" + b"0" * 40)
    assert v["update_available"] is True
    assert v["latest"] == SHA[:7]


def test_no_stamp_means_we_do_not_guess(stamped, tmp_path, monkeypatch) -> None:
    """옛 설치에는 도장이 없다. 없으면 '새 판' 이라고 우기지 않는다."""
    monkeypatch.setattr("app.config.ROOT", tmp_path)
    with TestClient(app) as c:
        v = c.get("/api/version?check=false").json()
    assert v["update_available"] is False


# ── 도장을 찍는 쪽도 BOM 을 붙이지 않는다 ──────────────────────────────────


def test_the_scripts_write_the_stamp_without_a_bom() -> None:
    """읽는 쪽만 고치면 다음에 또 다른 곳에서 같은 일이 난다."""
    for name in ("update.ps1", "install.ps1"):
        text = (ROOT / name).read_text(encoding="utf-8-sig")
        for ln in text.splitlines():
            if "설치버전.txt" in ln or "$Stamp" in ln:
                assert "Set-Content" not in ln, (
                    f"{name}: PowerShell 5.1 의 Set-Content -Encoding UTF8 은 BOM 을 붙인다 — "
                    f"[IO.File]::WriteAllText 를 쓰라: {ln.strip()}"
                )


def test_the_reader_eats_the_bom() -> None:
    api = (ROOT / "server" / "app" / "api" / "health.py").read_text(encoding="utf-8")
    i = api.index('stamp = ROOT / "설치버전.txt"')
    near = api[i:i + 1500]
    assert 'encoding="utf-8-sig"' in near, "utf-8 로 읽으면 BOM 이 값에 섞인다"


# ── 올리고 나서 30분 동안 거짓말하지 않는다 ────────────────────────────────


def test_the_cache_does_not_keep_saying_there_is_a_new_version(monkeypatch, tmp_path) -> None:
    """**들고 있어도 되는 것은 '최신 판 번호' 뿐이다.**

    새 판이 있느냐는 지금 도장을 다시 보고 그 자리에서 셈해야 한다. 옛 답을 통째로
    돌려주면, 방금 올리고 났는데도 30분 동안 "새 판이 나왔습니다" 라고 한다.
    """
    from app.api import health

    health._VERSION_ASKED_AT.clear()
    health._VERSION_ASKED_AT.append(9e9)      # 방금 물어본 것으로 해 둔다
    health._VERSION_ANSWER.clear()
    health._VERSION_ANSWER.append(
        {"latest": SHA[:7], "update_available": True, "asked": True}
    )
    import time

    monkeypatch.setattr(time, "monotonic", lambda: 9e9)
    (tmp_path / "설치버전.txt").write_bytes(b"\xef\xbb\xbf" + SHA.encode())
    monkeypatch.setattr("app.config.ROOT", tmp_path)
    with TestClient(app) as c:
        v = c.get("/api/version").json()
    assert v["update_available"] is False, (
        "캐시가 옛 답을 붙들고 있다 — 올리고 나서도 30분 동안 '새 판' 이라고 한다"
    )
    health._VERSION_ANSWER.clear()
    health._VERSION_ASKED_AT.clear()
    health._VERSION_ASKED_AT.append(0.0)


# ── 남은 돈으로 되는지 **고르기 전에** 말한다 ──────────────────────────────


def test_the_screen_warns_before_the_money_is_gone_not_after() -> None:
    """원장님이 20 달러로 곡 하나 못 얻고 12 달러를 쓰셨다.

    그때 고르신 것이 '상한 없음' 등급이었다 — 한 번 실패에 최대 $6. 화면 어디에도
    "지금 남은 돈으로는 몇 번 못 한다" 는 말이 없었다.
    """
    page = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    assert "function moneyOkToStart" in page, "시작하기 전에 돈을 보지 않는다"
    assert "budget-w" in page and "nomoney" in page, "등급 카드에 모자란다는 표시가 없다"
    # 막지는 않는다 — 원장님 돈이다. 다만 모르고 쓰시는 일은 없어야 한다.
    assert "그래도 이대로 시작할까요?" in page, "고르실 기회를 드리지 않는다"
    assert page.count("moneyOkToStart(") >= 4, (
        "만들기 자리 세 곳 모두에 걸려 있어야 한다 — 한 곳이라도 빠지면 그 길로 새 나간다"
    )
