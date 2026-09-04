"""윈도우 설치 스크립트가 한국어 윈도우에서 실제로 도는가.

이 검사가 없으면 조용히 되살아난다. 리눅스·맥에서는 아무 문제가 없고 CI 도 통과하는데,
정작 원장의 윈도우에서만 스크립트가 통째로 안 도는 종류의 결함이기 때문이다.

**BOM 이 없는 `.ps1` 은 Windows PowerShell 5.1(파란 창)이 시스템 코드페이지로 읽는다.**
한국어 윈도우에서는 CP949 다. UTF-8 로 저장한 한글이 깨지고, 깨진 바이트가 따옴표를
삼켜 스크립트가 파싱조차 되지 않는다. 실제로 첫 설치에서 이것에 걸렸다.

`.bat` 은 반대다. cmd.exe 는 배치 파일을 **현재 코드페이지로 먼저 읽으므로** CP949 로
저장해야 한다. UTF-8 로 저장하고 안에서 `chcp 65001` 을 불러도 이미 늦다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
UTF8_BOM = b"\xef\xbb\xbf"


def _powershell_scripts() -> list[Path]:
    return sorted(ROOT.glob("*.ps1"))


def _batch_scripts() -> list[Path]:
    return sorted(ROOT.glob("*.bat"))


def test_there_are_windows_scripts_to_check() -> None:
    """스크립트가 사라졌는데 테스트만 통과하는 일이 없게."""
    assert _powershell_scripts(), "설치용 .ps1 이 하나도 없다"
    assert _batch_scripts(), "두 번 눌러 실행하는 .bat 이 하나도 없다"


@pytest.mark.parametrize("path", _powershell_scripts(), ids=lambda p: p.name)
def test_powershell_script_has_utf8_bom(path: Path) -> None:
    """BOM 이 없으면 한국어 윈도우에서 한글이 깨져 스크립트가 파싱되지 않는다."""
    raw = path.read_bytes()
    assert raw.startswith(UTF8_BOM), (
        f"{path.name} 에 UTF-8 BOM 이 없다. "
        "Windows PowerShell 5.1 이 CP949 로 읽어 한글이 깨지고 스크립트가 통째로 죽는다."
    )
    # BOM 뒤가 정상적인 UTF-8 이어야 한다.
    raw[len(UTF8_BOM) :].decode("utf-8")


@pytest.mark.parametrize("path", _powershell_scripts(), ids=lambda p: p.name)
def test_powershell_script_uses_crlf(path: Path) -> None:
    """윈도우 도구가 읽는 파일이다 — 줄바꿈도 윈도우 것으로 맞춘다."""
    raw = path.read_bytes()
    lone_lf = raw.replace(b"\r\n", b"").count(b"\n")
    assert lone_lf == 0, f"{path.name} 에 CRLF 아닌 줄바꿈이 {lone_lf}개 있다"


@pytest.mark.parametrize("path", _batch_scripts(), ids=lambda p: p.name)
def test_batch_script_is_cp949(path: Path) -> None:
    """cmd.exe 는 배치 파일을 현재 코드페이지로 읽는다 — 한국어 윈도우는 CP949."""
    raw = path.read_bytes()
    assert not raw.startswith(UTF8_BOM), f"{path.name} 에 BOM 이 있으면 cmd 가 첫 줄을 못 읽는다"
    try:
        text = raw.decode("cp949")
    except UnicodeDecodeError as e:  # pragma: no cover - 실패 메시지가 본체다
        raise AssertionError(
            f"{path.name} 이 CP949 로 읽히지 않는다({e}). 한글이 깨져 화면에 글자가 아닌 것이 뜬다."
        ) from e
    assert text.lstrip().lower().startswith("@echo off")


@pytest.mark.parametrize("path", _batch_scripts(), ids=lambda p: p.name)
def test_batch_script_uses_crlf(path: Path) -> None:
    raw = path.read_bytes()
    lone_lf = raw.replace(b"\r\n", b"").count(b"\n")
    assert lone_lf == 0, f"{path.name} 에 CRLF 아닌 줄바꿈이 {lone_lf}개 있다"


def test_install_batch_bypasses_the_execution_policy() -> None:
    """윈도우는 인터넷에서 받은 .ps1 을 막는다 — 배치가 그 길을 열어 줘야 한다.

    이것이 없으면 원장은 PSSecurityException 앞에서 멈춘다. 명령을 외워 치게 하는
    순간 원터치가 아니다.
    """
    bat = ROOT / "설치.bat"
    assert bat.exists(), "설치.bat 이 없다"
    text = bat.read_bytes().decode("cp949")
    assert "-ExecutionPolicy Bypass" in text, "실행 정책을 풀지 않으면 막힌 채로 끝난다"
    assert "Unblock-File" in text, "압축을 푼 파일의 다운로드 표시도 벗겨야 한다"
    assert "install.ps1" in text
    assert "pause" in text, "창이 곧바로 닫히면 원장이 오류 글씨를 읽을 수 없다"


def _install_text() -> str:
    return (ROOT / "install.ps1").read_bytes().decode("utf-8-sig")


def test_python_probe_does_not_kill_the_installer() -> None:
    """파이썬을 찾다 난 오류가 설치를 통째로 중단시키면 안 된다.

    `py.exe` 는 맞는 버전이 없으면 붉은 글씨를 표준오류로 뱉는다. 스크립트 맨 위의
    `$ErrorActionPreference = "Stop"` 아래에서 그것은 **종료성 오류**가 되어, 준비해 둔
    "파이썬을 설치하십시오" 안내가 한 줄도 뜨지 못한 채 창이 닫힌다. 실제로 원장 PC
    첫 설치에서 이것에 걸렸다 — 화면에 남은 것은 알 수 없는 붉은 글씨뿐이었다.

    그래서 찾는 동안만 Stop 을 풀어야 한다.
    """
    text = _install_text()
    start = text.find("function Find-Python")
    assert start != -1, "파이썬 탐색이 함수로 묶여 있어야 오류를 가둘 수 있다"
    body = text[start : text.find("\nStep ", start)]
    assert '$ErrorActionPreference = "Continue"' in body, (
        "탐색 중 Stop 을 풀지 않으면 py.exe 의 붉은 글씨가 설치를 중단시킨다"
    )
    assert "finally" in body, "탐색이 끝나면 원래 설정으로 되돌려야 한다"


def test_missing_python_is_explained_not_just_failed() -> None:
    """파이썬이 없을 때 원장이 다음에 무엇을 할지 화면만 보고 알 수 있어야 한다."""
    text = _install_text()
    assert "https://www.python.org/downloads/" in text, "받을 곳을 알려 주지 않으면 막힌다"
    assert "Add python.exe to PATH" in text, (
        "이 체크를 빠뜨리면 설치하고도 같은 자리에서 또 막힌다 — 반드시 짚어 줘야 한다"
    )
    assert "winget install" in text, "가능하면 자동으로 깔아 주는 길이 있어야 원터치다"


def test_the_launcher_never_fails_silently() -> None:
    """아이콘을 눌렀는데 아무 일도 안 일어나는 것이 원장에게는 가장 나쁘다.

    바탕화면 아이콘은 `pythonw.exe` 로 뜬다 — 검은 창이 없어야 하기 때문이다.
    그런데 창이 없다는 것은 **오류 글씨도 없다**는 뜻이다. 부품 하나가 빠져 있으면
    프로그램은 조용히 죽고, 화면에는 아무 변화가 없다. 고장인지, 느린 건지,
    자기가 잘못 누른 건지 알 방법이 없다. 실제로 이 자리에서 막혔다.

    그래서 실행기는 무슨 일이 있었는지 파일에 적고, 실패하면 안내창을 띄운다.
    """
    text = (ROOT / "scripts" / "launch.py").read_text(encoding="utf-8")
    assert "MessageBoxW" in text, "윈도우에서 실패를 눈에 보이게 알리지 않는다"
    assert "실행기록.txt" in text, "무슨 일이 있었는지 남기지 않으면 물어볼 것도 없다"
    assert "def guarded(" in text and "guarded()" in text, (
        "main() 을 감싸지 않으면 예외가 그대로 조용히 사라진다"
    )
    # 어떤 예외든 잡아야 한다 — 미리 알던 것만 잡으면 나머지는 다시 조용해진다.
    assert text.count("except ") >= 3


def test_there_is_a_visible_way_to_run_it() -> None:
    """아이콘이 안 될 때 원장이 원인을 볼 수 있는 길이 있어야 한다."""
    bat = ROOT / "실행.bat"
    assert bat.exists(), "실행.bat 이 없다 — 아이콘이 안 되면 손쓸 방법이 없어진다"
    text = bat.read_bytes().decode("cp949")
    assert "launch.py" in text
    assert "설치.bat" in text, "설치가 안 된 경우를 먼저 짚어 줘야 한다"
    assert "pause" in text, "창이 곧바로 닫히면 오류 글씨를 읽을 수 없다"


@pytest.mark.parametrize("path", _batch_scripts(), ids=lambda p: p.name)
def test_batch_warns_about_the_click_that_freezes_it(path: Path) -> None:
    """창 안을 클릭하면 멈춘다 — 그 사실을 모르면 고장으로 오해한다.

    윈도우 명령창은 '빠른 편집' 이 기본으로 켜져 있다. 창 안을 한 번 클릭하면 제목이
    "선택 ..." 으로 바뀌면서 **돌던 작업이 그 자리에서 멈춘다.** 화면은 멈춘 그대로라
    프로그램이 죽은 것처럼 보인다. 실제로 원장이 여기서 막혔다 — 설치가 2/7 에서
    한참을 그대로 있었는데, 사실은 사람이 멈춰 세운 것이었다.

    사용자 전체 설정을 우리가 끄는 것은 지나치다. 대신 미리 말해 준다.
    """
    text = path.read_bytes().decode("cp949")
    assert "클릭하지 마십시오" in text, f"{path.name} 이 클릭 정지를 알려 주지 않는다"
    assert "Esc" in text, "이미 멈춘 사람에게 빠져나오는 법을 알려 줘야 한다"


def test_the_update_script_never_deletes_the_owner_s_own_things() -> None:
    """새 판으로 올릴 때 **덮어쓰기만** 한다 — 지우기 시작하면 언젠가 곡을 지운다.

    원장님은 지금까지 새 판마다 폴더를 통째로 지우고 다시 설치하셨다. 그 습관이
    위험해서 이 스크립트를 만들었는데, 스크립트가 같은 짓을 하면 아무 의미가 없다.
    """
    text = (ROOT / "update.ps1").read_text(encoding="utf-8-sig")

    for mine in (".env", "web\\vendor", "reference_scores", "data"):
        assert mine in text, f"{mine} 을 지키지 않는다"

    # 프로그램 폴더를 통째로 지우는 명령이 있으면 안 된다.
    assert "Remove-Item $Root" not in text
    assert "Remove-Item -Path $Root" not in text
    # 임시 폴더를 치우는 것만 허용된다.
    for line in text.splitlines():
        if "Remove-Item" in line:
            assert "$tmp" in line, f"임시 폴더 밖을 지운다: {line.strip()}"


def test_the_update_script_can_be_undone() -> None:
    """되돌릴 길이 없는 작업은 하지 않는다 — 바꾸기 전에 이전 판을 옆에 둔다."""
    text = (ROOT / "update.ps1").read_text(encoding="utf-8-sig")
    assert "이전판" in text and "Copy-Item" in text
    assert "self_check.py" in text, "바꾼 뒤 점검하지 않으면 고장난 채로 남는다"


def test_the_update_batch_file_is_readable_on_a_korean_windows() -> None:
    """한글 윈도우 명령창은 CP949 로 읽는다. UTF-8 로 저장하면 글자가 깨진다."""
    raw = (ROOT / "업데이트.bat").read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "BOM 이 붙으면 첫 줄이 깨진다"
    assert b"\r\n" in raw, "CRLF 가 아니면 줄이 붙어 실행된다"
    text = raw.decode("cp949")
    assert "update.ps1" in text
    # 빠른 편집 함정을 여기서도 알려야 한다 — 실제로 그것 때문에 멈춰 있었다.
    assert "클릭하지 마십시오" in text


def test_nothing_in_the_update_path_depends_on_a_bat_association() -> None:
    """윈도우에서 .bat 연결이 메모장으로 바뀌어 있으면 두 번 눌러도 메모장만 열린다.

    원장님 PC 가 정확히 그 상태였다. '두 번 누르십시오' 는 원장 손이 아니라 그 PC
    설정에 달린 일이라 믿을 수 없다 — 갱신 경로는 .bat 없이도 끝까지 가야 한다.
    """
    text = (ROOT / "update.ps1").read_text(encoding="utf-8-sig")
    assert "실행.bat" not in text, "다시 켤 때 .bat 을 거친다 — 연결이 깨져 있으면 안 켜진다"
    assert "pythonw.exe" in text, "파이썬을 직접 부르지 않는다"

    setup = (ROOT / "install.ps1").read_text(encoding="utf-8-sig")
    assert "콩쿨 작곡기 업데이트" in setup, "업데이트 바로가기를 만들지 않는다"
    assert "powershell.exe" in setup, "바로가기가 powershell 을 직접 부르지 않는다"


def test_the_app_itself_can_start_the_update() -> None:
    """가장 확실한 길은 화면의 단추다 — 파일 연결과 아무 상관이 없다."""
    api = (ROOT / "server" / "app" / "api" / "health.py").read_text(encoding="utf-8")
    assert '"/api/update"' in api
    # 프로그램이 꺼질 때 갱신도 같이 죽으면 안 된다 — 제 프로세스 그룹으로 띄운다.
    assert "creationflags" in api, "갱신을 떼어 내지 않으면 프로그램과 함께 죽는다"

    page = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    assert "btnUpdateNow" in page and "지금 올리기" in page


# ── 갱신이 눈에 보여야 한다 ────────────────────────────────────────────────


def test_the_update_gets_a_window_of_its_own() -> None:
    """**창 없이 띄우면 갱신은 시작하자마자 죽는다.**

    원장님: "지금 올리기 하고 대기중인데.. 프로그램이 꺼졌다가 다시 켜진다고 했는데
             움직임이 없은데.."

    앞선 판은 DETACHED_PROCESS(0x8) 로 띄웠다. 창이 없으면 update.ps1 둘째 줄의
    `[Console]::OutputEncoding` 이 "핸들이 잘못되었습니다" 로 터지고, 바로 위
    `$ErrorActionPreference = "Stop"` 때문에 그 자리에서 끝난다 — 프로그램을 끄기도
    전에, 원장님 눈에는 아무 흔적도 없이. 진행이 보이지 않는 것과 아예 안 도는 것을
    구분할 수 없다는 점에서 이것은 두 배로 나쁘다.
    """
    api = (ROOT / "server" / "app" / "api" / "health.py").read_text(encoding="utf-8")
    assert "0x00000010" in api, "CREATE_NEW_CONSOLE 로 띄우지 않는다 — 진행이 안 보인다"
    assert "0x00000008" not in api, (
        "DETACHED_PROCESS 로 돌아갔다 — 창이 없으면 갱신이 첫 줄에서 죽는다"
    )
    assert "0x00000200" in api, "제 프로세스 그룹이 없으면 프로그램과 함께 죽을 수 있다"


def test_the_update_script_survives_having_no_console() -> None:
    """창을 주고 띄우지만, 창 없는 자리에서 불려도 갱신은 계속되어야 한다.

    글씨가 깨지는 것과 갱신을 못 하는 것은 견줄 일이 아니다.
    """
    text = (ROOT / "update.ps1").read_text(encoding="utf-8-sig")
    code = [
        ln.strip() for ln in text.splitlines()
        if "OutputEncoding" in ln and not ln.strip().startswith("#")
    ]
    assert code, "인코딩 줄이 사라졌다"
    for ln in code:
        assert "try {" in ln and "catch" in ln, (
            f"콘솔이 없으면 여기서 터진다 — try 로 감싸야 한다: {ln}"
        )


def test_the_update_leaves_a_trace_on_disk() -> None:
    """창이 닫혀 버렸을 때 원장님이 '왜 안 됐나' 를 물으실 곳이 있어야 한다."""
    text = (ROOT / "update.ps1").read_text(encoding="utf-8-sig")
    assert "갱신기록.txt" in text and "Start-Transcript" in text, "기록을 남기지 않는다"

    page = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    assert "갱신기록.txt" in page, "막혔을 때 어디를 보라고 알려 주지 않는다"


def test_the_window_does_not_vanish_before_it_can_be_read() -> None:
    """다 됐는지 아무 일도 없었는지 구분이 안 되면 창이 없는 것과 같다."""
    text = (ROOT / "update.ps1").read_text(encoding="utf-8-sig")
    tail = text[text.rindex("Restart-App $Root"):]
    assert "Start-Sleep" in tail, "성공하고 나서 창이 곧바로 사라진다"


def test_the_screen_watches_instead_of_telling_the_user_to_guess() -> None:
    """**"잠시 뒤 F5 를 눌러 주십시오" 는 지켜보는 것이 아니다.**

    원장님이 물으신 "어느정도 기댜려야" 에 대한 답은 지어낸 숫자가 아니라,
    지금 몇 초가 흘렀는지와 지금 어느 단계인지다. 그리고 갱신이 아예 시작조차 못
    했으면 그것을 **다른 말로** 알려야 한다 — 앞선 판은 두 경우에 똑같은 말을 했다.
    """
    page = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    assert "function watchUpdate" in page, "화면이 갱신을 지켜보지 않는다"
    # 꺼지는 것을 봐야 '정말 시작됐다' 를 안다.
    assert "waitOff" in page and "waitOn" in page, "꺼짐·켜짐 두 마디로 나눠 보지 않는다"
    assert "갱신이 시작되지 않았습니다" in page, "시작조차 못 한 경우를 따로 말하지 않는다"
    assert "location.reload()" in page, "다시 켜져도 원장님이 F5 를 눌러야 한다"
    watch = page[page.index("function watchUpdate"):]
    watch = watch[:watch.index("// ── 새 판 알림")]
    assert "secs()" in watch, "몇 초가 흘렀는지 보여 주지 않는다"


# ── 갱신이 실패해도 프로그램은 돌아온다 ──────────────────────────────────


def test_the_update_never_leaves_the_program_switched_off() -> None:
    """**갱신 실패와 프로그램을 못 쓰게 만드는 것은 전혀 다른 일이다.**

    원장님: "프로그램이 꺼졌다가 다시 켜져야 하는데.. 잘안되네.."

    update.ps1 은 프로그램을 **먼저 끄고** 시작한다. 그런데 중간 어디서든 멈추면
    (인터넷이 끊기거나, 압축이 깨졌거나, 파일이 잠겼거나) 그대로 종료해서
    원장님께는 꺼진 프로그램만 남았다.

    갱신은 실패해도 된다. 프로그램은 반드시 돌아와야 한다.
    """
    import re

    text = (ROOT / "update.ps1").read_text(encoding="utf-8-sig")
    lines = text.splitlines()

    for i, line in enumerate(lines):
        if not re.search(r"\bexit\s+1\b", line):
            continue
        window = "\n".join(lines[max(0, i - 14):i])
        # 가상환경이 아예 없는 경우는 프로그램을 끄기 전이라 켤 것이 없다.
        if "가상환경이 없습니다" in window:
            continue
        assert "Restart-App" in window, (
            f"update.ps1 {i + 1}줄에서 프로그램을 꺼진 채로 두고 나간다"
        )


def test_die_brings_the_program_back() -> None:
    text = (ROOT / "update.ps1").read_text(encoding="utf-8-sig")
    die = text.split("function Die($m)")[1].split("\n}")[0]
    assert "Restart-App" in die, "갱신이 죽을 때 프로그램을 다시 켜지 않는다"
    # PowerShell 은 정의 순서를 따진다 — Die 안에서 부르려면 먼저 있어야 한다.
    assert text.index("function Restart-App") < text.index("function Die"), (
        "Die 가 Restart-App 보다 먼저 정의돼 있어 부를 수 없다"
    )


def test_it_waits_for_the_program_to_actually_stop() -> None:
    """켜진 채로 덮어쓰면 윈도우가 파일을 잠가 복사가 실패한다.

    예전에는 끄라고 부탁하고 **2초만 자고** 넘어갔다. 그 사이에 안 꺼지면
    반만 바뀐 프로그램이 남는다 — 가장 찾기 어려운 고장이다.
    """
    text = (ROOT / "update.ps1").read_text(encoding="utf-8-sig")
    stop = text.split("1/6")[1].split("2/6")[0]
    assert "Start-Sleep -Seconds 2" not in stop, "껐는지 확인하지 않고 2초만 잔다"
    assert "/health" in stop, "정말 꺼졌는지 확인하지 않는다"


def test_one_locked_file_does_not_abort_everything() -> None:
    """파일 하나가 잠겼다고 갱신 전체를 멈추면 프로그램이 반만 바뀐 채 남는다."""
    text = (ROOT / "update.ps1").read_text(encoding="utf-8-sig")
    copy = text.split("$changed = 0")[1].split("Ok \"$changed")[0]
    assert "catch" in copy, "복사가 실패하면 그대로 죽는다"
    assert "$stuck" in copy, "바꾸지 못한 파일을 알려 주지 않는다"


def test_the_powershell_actually_parses() -> None:
    """구문 오류 하나면 원장님은 꺼진 프로그램만 보신다.

    PowerShell 이 있는 곳에서는 진짜로 파싱해 본다.
    """
    import shutil
    import subprocess

    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    if not pwsh:
        pytest.skip("이 기계에는 PowerShell 이 없다")

    for name in ("update.ps1", "install.ps1", "start.ps1"):
        r = subprocess.run(
            [pwsh, "-NoProfile", "-Command",
             f"$e=$null; [void][System.Management.Automation.Language.Parser]::ParseFile("
             f"'{ROOT / name}', [ref]$null, [ref]$e); "
             f"if ($e) {{ $e | ForEach-Object {{ Write-Output $_.Message }}; exit 1 }}"],
            capture_output=True, text=True, timeout=60, check=False,
        )
        assert r.returncode == 0, f"{name} 에 구문 오류가 있다:\n{r.stdout}"


# ── 원장님 화면에 실제로 찍힌 것들 ─────────────────────────────────────────


def test_powershell_has_no_docstrings() -> None:
    """**\"\"\"...\"\"\" 는 PowerShell 에서 주석이 아니다 — 화면에 그대로 찍힌다.**

    원장님이 보내 주신 갱신 창에 개발자 메모가 통째로 출력돼 있었다:

        "프로그램을 다시 켠다 — **.bat 을 거치지 않는다.**
         윈도우에서 .bat 파일 연결이 메모장으로 바뀌어 있으면 ..."

    파이썬 습관으로 쓴 것인데 PowerShell 에는 독스트링이 없다. 그냥 문자열 식이고,
    함수가 불릴 때마다 출력된다. 원장님은 그것을 **자기더러 하라는 지시**로 읽으신다.
    """
    for name in ("update.ps1", "install.ps1", "start.ps1"):
        f = ROOT / name
        if not f.exists():
            continue
        text = f.read_text(encoding="utf-8-sig")
        assert '"""' not in text, (
            f"{name} 에 파이썬식 독스트링이 있다 — 원장님 화면에 그대로 찍힌다"
        )


def test_the_console_is_put_back_the_way_it_was() -> None:
    """**글자표는 창 전체의 설정이라 스크립트가 끝나도 남는다.**

    update.ps1 이 UTF-8 로 바꿔 놓고 나가면, 이어서 찍는 '업데이트.bat' 의 한글이
    전부 깨진다. 원장님 화면 마지막 줄이 ??????? 로 나온 것이 이것이다 — 다 해 놓고
    마지막 한 줄에서 '뭔가 잘못됐다' 는 인상만 남겼다.
    """
    text = (ROOT / "update.ps1").read_text(encoding="utf-8-sig")
    assert "function Restore-Console" in text, "콘솔을 되돌리지 않는다"
    # 빠져나가는 자리마다 되돌려야 한다 — 한 곳만 빠져도 그 길로 나가면 깨진다.
    lines = text.splitlines()
    exits = [i for i, ln in enumerate(lines) if ln.strip().startswith("exit ")]
    assert exits, "나가는 자리를 못 찾았다"
    for i in exits:
        before = "\n".join(lines[max(0, i - 8):i])
        assert "Restore-Console" in before, (
            f"{i + 1}번째 줄로 나가면 콘솔이 UTF-8 인 채로 남는다: {lines[i].strip()}"
        )


def test_it_only_shuts_down_the_program_in_this_folder() -> None:
    """**남의 폴더 프로그램을 꺼 놓고 제 폴더에서 켜려 하면 아무것도 안 켜진다.**

    원장님 PC 에는 사본이 둘이다(바탕화면 · C 드라이브). 8000 번이 응답한다는 이유만으로
    끄면, 지금 쓰시던 프로그램을 꺼 버리고 이 폴더에서 다시 켜려 한다. 이 폴더에
    .venv 가 없으면 그대로 끝이고, 원장님께는 '프로그램이 사라졌다' 로 보인다.
    """
    api = (ROOT / "server" / "app" / "api" / "health.py").read_text(encoding="utf-8")
    assert '"root": str(ROOT)' in api, "/health 가 어느 폴더인지 밝히지 않는다"

    text = (ROOT / "update.ps1").read_text(encoding="utf-8-sig")
    assert ".root" in text and "$Root" in text, "폴더를 견주지 않고 끈다"
    assert "다른 폴더" in text, "다른 폴더의 프로그램이라고 알려 주지 않는다"


def test_the_latest_stamp_is_only_pressed_when_everything_really_changed() -> None:
    """반만 바뀐 프로그램이 '최신' 이라는 이름으로 굳으면 다음 갱신이 통째로 막힌다."""
    text = (ROOT / "update.ps1").read_text(encoding="utf-8-sig")
    i = text.index("[IO.File]::WriteAllText($Stamp")
    guard = text[max(0, i - 400):i]
    assert "$stuck.Count -eq 0" in guard, (
        "잠긴 파일이 남았는데도 '최신' 도장을 찍는다 — 다음 번에 '이미 최신입니다' 로 막힌다"
    )


def test_already_latest_tells_the_owner_how_to_see_it() -> None:
    """**'이미 최신입니다' 만으로는 아무것도 안 바뀐 것과 구분이 안 된다.**

    원장님: "전혀 업그레이드가 안되는데. 어떻게 해야 하는거야... 정말"
    그때 파일은 이미 최신이었다. 눈으로 확인하는 법을 함께 드려야 한다.
    """
    text = (ROOT / "update.ps1").read_text(encoding="utf-8-sig")
    i = text.index("이미 최신입니다")
    after = text[i:i + 900]
    assert "Ctrl" in after and "F5" in after, (
        "그냥 F5 는 예전 화면이 그대로 나온다 — Ctrl+F5 를 알려 주지 않는다"
    )


# ── 이름이 깨져도 설치할 수 있어야 한다 ──────────────────────────────────


def test_there_is_an_ascii_way_in() -> None:
    """**한글 파일 이름은 압축을 건너다 깨질 수 있다.**

    원장님이 받으신 첫 설치본이 그랬다 — 압축 안의 한글 이름에 UTF-8 표시가 없어
    윈도우 탐색기가 폴더 이름을 깨진 글자로 읽었고, 원장님 눈에는 "아무것도 없는"
    압축 파일이었다. 압축을 어떻게 만들든, **영문 이름 하나는 늘 있어야 한다.**
    """
    for name, ps in (("INSTALL.bat", "install.ps1"),
                     ("START.bat", "start.ps1"),
                     ("UPDATE.bat", "update.ps1")):
        f = ROOT / name
        assert f.exists(), f"{name} 이 없다 — 한글 이름이 깨지면 들어갈 길이 없다"
        raw = f.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf"), f"{name} 에 BOM 이 붙었다 — cmd 가 첫 줄을 못 읽는다"
        assert b"\r\n" in raw, f"{name} 이 윈도우 줄바꿈이 아니다"
        assert ps.encode() in raw, f"{name} 이 {ps} 를 부르지 않는다"


def test_the_first_thing_to_read_is_there() -> None:
    """처음 여시는 분이 무엇부터 눌러야 하는지 알 길이 있어야 한다."""
    for name in ("맨먼저읽어주세요.txt", "README-FIRST.txt"):
        f = ROOT / name
        assert f.exists(), f"{name} 이 없다"
        text = f.read_text(encoding="utf-8")
        assert "INSTALL.bat" in text, f"{name} 이 영문 단추를 알려 주지 않는다"
        assert "\r\n" in f.read_bytes().decode("utf-8"), f"{name} 이 메모장에서 한 줄로 붙는다"
