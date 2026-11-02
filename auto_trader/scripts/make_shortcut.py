#!/usr/bin/env python3
"""바탕화면에 '자동매매' 바로가기를 만든다 (Windows 전용).

배치 파일에 한글을 넣으면 cmd 코드페이지에서 깨지므로, 이름을 다루는 일은
전부 여기서 한다. PowerShell 로 .lnk 를 만들고, 실패하면 이유를 알려준다.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SHORTCUT_NAME = "자동매매.lnk"
ICON = r"%SystemRoot%\System32\SHELL32.dll,137"  # 초록 위쪽 화살표


def desktop_dir() -> Path:
    """OneDrive 로 옮겨간 바탕화면도 찾는다."""
    for candidate in (
        os.environ.get("OneDrive"), os.environ.get("OneDriveConsumer"),
        os.environ.get("USERPROFILE"),
    ):
        if not candidate:
            continue
        path = Path(candidate) / "Desktop"
        if path.is_dir():
            return path
    return Path.home() / "Desktop"


def build_script(target: Path, shortcut: Path) -> str:
    return (
        "$s = New-Object -ComObject WScript.Shell; "
        f"$l = $s.CreateShortcut('{shortcut}'); "
        f"$l.TargetPath = '{target}'; "
        f"$l.WorkingDirectory = '{target.parent}'; "
        f"$l.IconLocation = '{ICON}'; "
        "$l.Description = 'Multi-Agent 자동매매'; "
        "$l.Save()"
    )


def main() -> int:
    if sys.platform != "win32":
        print("이 스크립트는 Windows 전용입니다. macOS/Linux 는 ./start.sh 를 쓰세요.")
        return 1

    target = BASE_DIR / "start.bat"
    if not target.exists():
        print(f"start.bat 을 찾을 수 없습니다: {target}")
        return 1

    shortcut = desktop_dir() / SHORTCUT_NAME
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-Command", build_script(target, shortcut)],
            check=True, capture_output=True, text=True, timeout=60,
        )
    except FileNotFoundError:
        print("PowerShell 을 찾지 못했습니다. start.bat 을 직접 더블클릭해 실행하세요.")
        return 1
    except subprocess.TimeoutExpired:
        print("바로가기 생성이 시간 초과됐습니다. start.bat 을 직접 실행하세요.")
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"바로가기를 만들지 못했습니다: {(exc.stderr or '').strip()[:200]}")
        print("start.bat 을 직접 더블클릭해도 똑같이 실행됩니다.")
        return 1

    if not shortcut.exists():
        print("바로가기가 만들어지지 않았습니다. start.bat 을 직접 실행하세요.")
        return 1

    print(f"✅ 바탕화면에 '자동매매' 아이콘을 만들었습니다.\n   {shortcut}")
    print("   앞으로는 이 아이콘만 더블클릭하면 됩니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
