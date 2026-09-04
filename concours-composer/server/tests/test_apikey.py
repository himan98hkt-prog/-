"""API 키를 넣는 길 — 원장이 실제로 막혔던 자리를 다시 막지 않게.

원장은 키를 정확히 복사해 명령창에 붙여넣었는데 "Anthropic 키는 sk-ant- 로
시작한다"는 말만 들었다. 윈도우 PowerShell 의 **숨김 입력에서는 Ctrl+V 가
붙여넣기로 동작하지 않는다** — 대신 보이지 않는 제어문자 하나(`\x16`)가 들어간다.
화면에 아무것도 안 보이니 무엇이 잘못됐는지 알 길이 없었다.

그래서 둘을 한다. 그 경우를 이름 붙여 잡고, 애초에 명령창을 거치지 않는 길
(프로그램 화면)을 둔다.
"""

from __future__ import annotations

from pathlib import Path

from app.apikey import clean, looks_valid, mask, write_key

GOOD = "sk-ant-api03-" + "x" * 40


def test_ctrl_v_is_named_not_mistaken_for_a_bad_key() -> None:
    """이 메시지가 없으면 원장은 자기가 뭘 잘못했는지 영영 모른다."""
    problem = looks_valid("\x16")
    assert problem is not None
    assert "Ctrl+V" in problem and "오른쪽" in problem, (
        f"제어문자를 'sk-ant- 로 시작한다' 로 뭉뚱그리면 안 된다: {problem}"
    )


def test_ordinary_problems_still_have_their_own_words() -> None:
    assert "아무것도" in (looks_valid("") or "")
    assert "sk-ant-" in (looks_valid("abcdefghijklmnopqrstuvwxyz") or "")
    assert "짧" in (looks_valid("sk-ant-1") or "")
    assert "공백" in (looks_valid(GOOD[:20] + " " + GOOD[20:]) or "")
    assert looks_valid(GOOD) is None


def test_quotes_and_spaces_around_the_key_are_forgiven() -> None:
    """콘솔에서 복사하면 따옴표가 딸려 오기도 한다 — 그걸로 되돌려보내지 않는다."""
    assert clean(f'  "{GOOD}" \n') == GOOD
    assert looks_valid(clean(f"'{GOOD}'")) is None


def test_key_never_appears_in_full(tmp_path: Path) -> None:
    m = mask(GOOD)
    assert GOOD not in m and m.startswith("sk-ant-api") and m.endswith(GOOD[-4:])


def test_write_keeps_the_rest_of_the_file_and_backs_it_up(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("COMPOSER_MODEL=claude-opus-5\nANTHROPIC_API_KEY=old\nSTORE_PERSIST=1\n", encoding="utf-8")
    write_key(env, GOOD)

    text = env.read_text(encoding="utf-8")
    assert f"ANTHROPIC_API_KEY={GOOD}" in text
    assert "COMPOSER_MODEL=claude-opus-5" in text, "다른 설정을 지우면 안 된다"
    assert "STORE_PERSIST=1" in text
    assert "old" not in text
    assert (tmp_path / ".env.bak").exists(), "덮어쓰기 전 사본이 있어야 되돌릴 수 있다"


def test_write_adds_the_line_when_it_is_missing(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("COMPOSER_MODEL=claude-opus-5\n", encoding="utf-8")
    write_key(env, GOOD)
    assert f"ANTHROPIC_API_KEY={GOOD}" in env.read_text(encoding="utf-8")


def test_commented_out_line_is_not_treated_as_the_key(tmp_path: Path) -> None:
    """`# ANTHROPIC_API_KEY=...` 는 예시다 — 그 줄을 고치면 진짜 키가 안 들어간다."""
    env = tmp_path / ".env"
    env.write_text("# ANTHROPIC_API_KEY=sk-ant-...\n", encoding="utf-8")
    write_key(env, GOOD)
    text = env.read_text(encoding="utf-8")
    assert "# ANTHROPIC_API_KEY=sk-ant-..." in text
    assert f"ANTHROPIC_API_KEY={GOOD}" in text


# ── 화면에서 넣는 길 ───────────────────────────────────────────────────────


def _client(tmp_path: Path, monkeypatch):
    """`.env` 를 임시 파일로 돌린 앱. 진짜 .env 를 건드리면 안 된다."""
    import app.api.apikey as mod
    from app.main import app as fastapi_app
    from fastapi.testclient import TestClient

    env = tmp_path / ".env"
    env.write_text("COMPOSER_MODEL=claude-opus-5\n", encoding="utf-8")
    monkeypatch.setattr(mod, "ENV_FILE", env)
    monkeypatch.setattr(mod, "read_api_key_from_env_file", lambda: _read(env))
    # 이 PC 에서만 넣게 막아 두었으므로 테스트도 로컬 주소로 붙는다.
    return TestClient(fastapi_app, client=("127.0.0.1", 51000)), env


def _read(env: Path) -> str:
    for raw in env.read_text(encoding="utf-8").splitlines():
        name, _, value = raw.partition("=")
        if name.strip() == "ANTHROPIC_API_KEY" and not raw.lstrip().startswith("#"):
            return value.strip()
    return ""


def test_screen_accepts_the_key_and_never_reads_it_back(tmp_path: Path, monkeypatch) -> None:
    c, env = _client(tmp_path, monkeypatch)

    before = c.get("/api/api-key").json()
    assert before["present"] is False and before["engine"] == "stub-rule-based"

    r = c.put("/api/api-key", json={"key": GOOD})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["present"] is True and body["engine"] == "claude"
    assert GOOD not in r.text, "키 전체를 화면으로 돌려주면 안 된다"

    assert f"ANTHROPIC_API_KEY={GOOD}" in env.read_text(encoding="utf-8")
    assert GOOD not in c.get("/api/api-key").text


def test_screen_explains_a_bad_key_in_words(tmp_path: Path, monkeypatch) -> None:
    c, _ = _client(tmp_path, monkeypatch)
    r = c.put("/api/api-key", json={"key": "sk-live-something"})
    assert r.status_code == 400
    assert "sk-ant-" in r.json()["detail"]


def test_screen_can_clear_the_key(tmp_path: Path, monkeypatch) -> None:
    """PC 를 넘기거나 팔 때 키를 지우고 무료로 되돌릴 수 있어야 한다."""
    c, env = _client(tmp_path, monkeypatch)
    c.put("/api/api-key", json={"key": GOOD})
    r = c.delete("/api/api-key")
    assert r.status_code == 200 and r.json()["present"] is False
    assert GOOD not in env.read_text(encoding="utf-8")
