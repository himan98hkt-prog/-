"""PC 를 켜면 자동매매가 스스로 뜨도록 등록한다 (Windows).

윈도우 업데이트로 PC 가 재부팅돼도 매매가 멈춰 있지 않게 하는 장치다.
**시작 프로그램 폴더**에 바로가기를 넣는 방식이라 관리자 권한이 필요 없고,
비밀번호를 어디에도 저장하지 않는다.

한계는 분명히 해 둔다: 시작 프로그램은 **로그인해야** 실행된다. 재부팅 후
잠금화면에 머물러 있으면 그동안은 매매도 멈춰 있다. 자동 로그인을 켜 두거나,
장 시작 전에 한 번 로그인해 두어야 한다.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from utils.logger import get_logger

logger = get_logger("autostart")

SHORTCUT_NAME = "자동매매 자동시작.lnk"
# 이 파일이 있으면 부팅 시 대시보드뿐 아니라 매매까지 시작한다.
TRADING_FLAG = "autostart_trading"


@dataclass
class AutostartStatus:
    supported: bool
    enabled: bool
    trade_on_boot: bool
    path: str = ""
    detail: str = ""


def startup_dir() -> Path:
    """윈도우 '시작 프로그램' 폴더."""
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    return base / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def _shortcut_path() -> Path:
    return startup_dir() / SHORTCUT_NAME


def _flag_path(data_dir: Path | str) -> Path:
    return Path(data_dir) / TRADING_FLAG


def is_supported() -> bool:
    return sys.platform == "win32"


def status(base_dir: Path | str, data_dir: Path | str) -> AutostartStatus:
    if not is_supported():
        return AutostartStatus(False, False, False,
                               detail="Windows 에서만 지원합니다 (macOS/Linux 는 cron 을 쓰세요)")
    link = _shortcut_path()
    return AutostartStatus(
        supported=True,
        enabled=link.exists(),
        trade_on_boot=_flag_path(data_dir).exists(),
        path=str(link),
    )


def enable(base_dir: Path | str, data_dir: Path | str, *, trade_on_boot: bool = True) -> AutostartStatus:
    """시작 프로그램에 등록한다."""
    if not is_supported():
        return status(base_dir, data_dir)

    target = Path(base_dir) / "boot.bat"
    if not target.exists():
        return AutostartStatus(True, False, False, detail=f"boot.bat 을 찾을 수 없습니다: {target}")

    link = _shortcut_path()
    link.parent.mkdir(parents=True, exist_ok=True)
    script = (
        "$s = New-Object -ComObject WScript.Shell; "
        f"$l = $s.CreateShortcut('{link}'); "
        f"$l.TargetPath = '{target}'; "
        f"$l.WorkingDirectory = '{target.parent}'; "
        "$l.WindowStyle = 7; "  # 최소화로 뜬다 — 부팅 때 창이 튀어나오지 않게
        "$l.Description = 'Multi-Agent 자동매매 자동시작'; "
        "$l.Save()"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            check=True, capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        logger.error("자동시작 등록 실패: %s", detail)
        return AutostartStatus(True, False, False, detail=str(detail)[:200])

    flag = _flag_path(data_dir)
    flag.parent.mkdir(parents=True, exist_ok=True)
    if trade_on_boot:
        flag.write_text("1", encoding="utf-8")
    elif flag.exists():
        flag.unlink()

    logger.info("자동시작 등록 완료: %s (매매까지 시작=%s)", link, trade_on_boot)
    return status(base_dir, data_dir)


def disable(base_dir: Path | str, data_dir: Path | str) -> AutostartStatus:
    """시작 프로그램에서 뺀다. 매매 기록과 키는 건드리지 않는다."""
    if is_supported():
        link = _shortcut_path()
        if link.exists():
            try:
                link.unlink()
            except OSError as exc:
                return AutostartStatus(True, True, False, detail=str(exc)[:200])
    flag = _flag_path(data_dir)
    if flag.exists():
        flag.unlink()
    logger.info("자동시작 해제 완료")
    return status(base_dir, data_dir)


def should_trade_on_boot(data_dir: Path | str) -> bool:
    return _flag_path(data_dir).exists()
