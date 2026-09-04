"""**새 판을 깔았는데 옛 화면이 보이는 일**을 없앤다.

원장님: "받아 설치하니 최신 파일이 아닌것 같은데.. 업데이트 된 자료 맞는건가?"
        "이렇게 나오는 것 맞아? 프롬프트 보여지는 것이 없어"

압축 파일에는 새 화면이 분명히 들어 있었다. 그런데 브라우저가 옛 화면을 보여 주었다.

원인은 서버가 화면 파일을 **아무 말 없이** 내보낸 데 있다. 캐시 지시가 없으면
브라우저는 "얼마나 오래 써도 되나" 를 스스로 어림한다(마지막 수정 시각의 10% 쯤).
그동안은 서버에 묻지도 않고 기억해 둔 옛 화면을 그대로 쓴다.

프로그램은 새 판인데 화면만 옛 판인 것 — 가장 헷갈리는 고장이다. 원장님은 설치가
잘못됐다고 여기시고, 지우고 다시 받으신다. 실제로 그렇게 하셨다.

"Ctrl+F5 를 누르십시오" 는 답이 아니다. 원장님이 그것을 아셔야 할 이유가 없다.
서버가 처음부터 제대로 말하면 된다.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app.main import app
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_the_page_is_always_revalidated(client) -> None:
    """`no-cache` 는 "쓰지 마라" 가 아니라 **"쓰기 전에 반드시 물어보라"** 는 뜻이다."""
    for path in ("/app/", "/app/index.html"):
        r = client.get(path)
        assert r.status_code == 200, path
        cc = r.headers.get("cache-control", "")
        assert "no-cache" in cc, (
            f"{path} 에 캐시 지시가 없다 — 브라우저가 옛 화면을 계속 쓴다: {cc!r}"
        )


def test_big_downloaded_parts_may_still_be_cached(client) -> None:
    """악보 렌더러 같은 부품까지 매번 다시 받으면 화면이 느려진다.

    그것은 이름이 바뀌지 않는 한 내용도 바뀌지 않는다 — 캐시해도 안전하다.
    """
    import inspect

    from app.main import FreshHtml

    src = inspect.getsource(FreshHtml.get_response)
    assert ".html" in src, "무엇에 걸지 정하지 않고 통째로 막으면 안 된다"


def test_the_version_is_always_on_screen() -> None:
    """**"이게 최신인가" 를 원장님이 물으실 필요가 없어야 한다.**

    화면에 판 번호가 늘 떠 있으면, 옛 화면을 새 화면으로 착각할 일이 없다.
    """
    page = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    assert 'id="headVer"' in page, "머리말에 판 번호 자리가 없다"
    # 판을 물어본 뒤 그 자리에 실제로 찍어야 한다.
    i = page.index('$("headVer")')
    near = page[i:i + 200]
    assert "installed" in near, "판 번호를 받아 놓고 화면에 안 쓴다"


def test_the_shipped_page_really_has_this_version_of_the_screen() -> None:
    """포장한 화면이 옛 것이면 무엇을 고쳐도 소용이 없다.

    설치본을 만들 때마다 사람이 눈으로 확인할 수는 없으므로 여기서 못 박는다.
    """
    page = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    for mark, name in [
        ("대화창에서 작곡해 오기", "의뢰서 구역"),
        ('id="apiFold"', "비용 구역 접기"),
        ("function layoutDashboard", "대시보드 차례"),
        ("이 곡을 남다르게 만들 것", "차별화 항목"),
        ('id="hoFile"', "파일 고르기"),
        ('id="headVer"', "판 번호 표시"),
    ]:
        assert mark in page, f"화면에 {name} 가 없다"
