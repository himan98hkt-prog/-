"""진행 화면이 **사실만** 말하는가.

원장님이 토카타를 '끝까지 만들기' 로 거셨을 때 26분이 걸렸다. 그동안 화면은 내내
"곡 하나에 보통 1~3분 걸립니다" 라고 적혀 있었고, 진행 칸은 하필 '급수별로 한 벌
만들기' 제목 아래에 떠 있었다. 그래서 이렇게 물으셨다.

    "왠지 불안해.. 비용은 비용대로 다쓰고 또 중지될까봐..."
    "1곡만 나오는 것이 아닌 5곡이 만들어지는거야? 난 한곡으로 할고 잇었는데.."

한 곡이 맞았다. 화면이 두 번 거짓말을 한 것이다 — 시간에서 한 번, 곡 수에서 한 번.
나조차 화면만 보고 "5곡" 이라고 잘못 답했다.

여기서 지키는 것:
  1. 남은 시간은 **실제 진행에서 잰다**. 지어낸 표를 쓰지 않는다
  2. 잴 수 없으면 **말하지 않는다** — 틀린 숫자보다 침묵이 낫다
  3. 몇 곡을 만드는지 화면이 직접 말한다
"""

from __future__ import annotations

import time
from pathlib import Path

WEB = Path(__file__).resolve().parents[2] / "web" / "index.html"


# ── 남은 시간은 잰 것이다 ─────────────────────────────────────────────────


def test_remaining_time_comes_from_real_progress() -> None:
    """절반 왔는데 1분 걸렸으면 남은 것도 대략 1분이다."""
    from app.progress import Job

    job = Job()
    job.started = time.monotonic() - 60.0     # 1분 전에 시작했고
    job.pct = 0.5                              # 절반 왔다

    left = job.remaining()
    assert 50 < left < 70, f"남은 시간이 실제 속도와 맞지 않는다: {left}"


def test_it_says_nothing_when_there_is_nothing_to_measure() -> None:
    """막 시작해 3% 도 못 갔으면 아직 잴 것이 없다. **모르면 모른다고 한다.**"""
    from app.progress import Job

    job = Job()
    job.started = time.monotonic() - 2.0
    job.pct = 0.01
    assert job.remaining() == 0.0, "잴 수 없는데 숫자를 지어냈다"


def test_a_finished_job_has_nothing_left() -> None:
    from app.progress import Job

    job = Job()
    job.pct = 1.0
    job.done = True
    assert job.remaining() == 0.0


def test_it_gets_more_accurate_as_the_piece_goes_on() -> None:
    """처음에는 대충, 갈수록 정확해진다 — 그게 재는 방식의 장점이다."""
    from app.progress import Job

    # 실제로 200초 걸릴 곡을 흉내낸다.
    guesses = []
    for pct in (0.1, 0.3, 0.6, 0.9):
        job = Job()
        job.started = time.monotonic() - 200.0 * pct
        job.pct = pct
        guesses.append(job.remaining() + 200.0 * pct)   # 예상 총 시간

    for total in guesses:
        assert 190 < total < 210, f"예상 총 시간이 실제(200초)와 크게 다르다: {total}"


def test_the_screen_is_told_the_remaining_time() -> None:
    """서버가 재도 화면에 안 보내면 소용이 없다."""
    from app.progress import Job

    job = Job()
    job.started = time.monotonic() - 60.0
    job.pct = 0.5
    snap = job.snapshot()
    assert "remaining" in snap, "남은 시간을 화면에 안 보낸다"
    assert snap["remaining"] > 0


def test_the_progress_endpoint_carries_it_through() -> None:
    """조각이 아니라 실제 경로로 확인한다."""
    from app.main import app
    from app.progress import tracker
    from fastapi.testclient import TestClient

    tracker().start("t-1", total=1)
    tracker().report("t-1", "realize", 0.5, "20-24마디 완료")

    with TestClient(app) as c:
        body = c.get("/api/progress/t-1").json()

    assert body["known"] is True
    assert "remaining" in body, "화면이 남은 시간을 받을 수 없다"
    assert body["total"] == 1


# ── 몇 곡인지 화면이 말한다 ───────────────────────────────────────────────


def test_the_screen_says_how_many_pieces_it_is_making() -> None:
    """한 곡 만들기와 한 벌 만들기가 **같은 진행 칸**을 쓴다.

    그 칸이 '한 벌 만들기' 제목 아래에 있어서 한 곡을 만드는 중에도 여러 곡처럼
    보였다. 무엇을 몇 개 만드는지 적어야 헷갈리지 않는다.
    """
    page = WEB.read_text(encoding="utf-8")
    assert 'id="mkOf"' in page and 'id="makeOf"' in page, "몇 번째 곡인지 적을 자리가 없다"
    assert "곡 1개" in page, "한 곡을 만들 때 그렇다고 말하지 않는다"
    assert "곡 ${tiers.length}개" in page, "한 벌 만들 때 몇 곡인지 말하지 않는다"


def test_the_screen_no_longer_promises_one_to_three_minutes() -> None:
    """등급·성격에 따라 몇 분에서 30분까지 벌어진다. 못 박아 두면 거짓이 된다.

    주석에는 남아 있어도 된다 — 왜 뺐는지 적어 두는 편이 낫다. 원장님 눈에
    보이는 자리에만 없으면 된다.
    """
    import re

    page = WEB.read_text(encoding="utf-8")
    visible = re.sub(r"<!--.*?-->", "", page, flags=re.S)
    assert "곡 하나에 보통 1~3분" not in visible, "화면이 아직 1~3분이라고 말하고 있다"


def test_the_screen_has_a_place_for_the_remaining_time() -> None:
    page = WEB.read_text(encoding="utf-8")
    assert 'id="mkLeft"' in page and 'id="makeLeft"' in page
    assert "남은 시간 약" in page, "잰 값을 보여 줄 문구가 없다"


def test_one_draft_is_not_described_as_several() -> None:
    """"1/1 안 생성" 은 여러 곡처럼 읽힌다."""
    src = (
        Path(__file__).resolve().parents[1] / "app" / "generation" / "pipeline.py"
    ).read_text(encoding="utf-8")
    assert 'f"{i + 1}/{n} 안 생성"' not in src, "한 안뿐인데 여러 안처럼 적고 있다"

    from app.progress import STAGE_KO

    assert STAGE_KO["candidates"] != "후보곡 만들기", (
        "곡 하나를 만드는 중에도 '후보곡' 이라고 적으면 여러 곡인 줄 아신다"
    )


# ── 업데이트가 됐는지 원장님이 확인할 수 있는가 ───────────────────────────


def test_the_screen_confirms_when_already_up_to_date() -> None:
    """**최신일 때 아무 말도 안 하면 확인할 길이 없다.**

    원장님: "업데이터 아이콘을 눌렀는데 작곡기까지 열리는데.. 맞는건가?
             업데이트가 된건가"

    맞다 — 켜져 있던 프로그램을 끄고, 바꾸고, 다시 켜 준다. 그런데 그 창이
    '성공해서 다시 켜진 것' 인지 '그냥 실행된 것' 인지 화면만 봐서는 알 수 없었다.
    새 판이 있을 때만 띠가 뜨고, 최신이면 띠가 사라져 아무것도 안 남았기 때문이다.
    """
    import re

    page = WEB.read_text(encoding="utf-8")
    visible = re.sub(r"<!--.*?-->", "", page, flags=re.S)
    assert "최신 판입니다" in visible, "최신일 때 최신이라고 말하지 않는다"
    assert "판 번호" in visible, "어느 판인지 안 알려 준다"
    assert 'id="btnUpdRecheck"' in visible, "다시 확인할 단추가 없다"


def test_the_update_script_tells_the_owner_how_to_check() -> None:
    """검은 창이 닫히고 나면 원장님께 남는 것은 작곡기 화면뿐이다.

    그 화면에서 무엇을 보면 되는지 스크립트가 알려 줘야 한다.
    """
    text = (
        Path(__file__).resolve().parents[2] / "update.ps1"
    ).read_text(encoding="utf-8-sig")
    assert text.count("최신 판입니다") >= 2, (
        "업데이트를 마친 뒤 무엇을 확인하면 되는지 말하지 않는다"
    )
