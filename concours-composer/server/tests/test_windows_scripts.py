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
