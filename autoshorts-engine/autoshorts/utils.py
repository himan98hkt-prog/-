"""파일명·시간·로깅 등 공용 유틸리티."""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Sequence

__all__ = [
    "sanitize_filename",
    "human_duration",
    "ensure_dir",
    "which_or_raise",
    "run_command",
    "setup_logging",
    "get_logger",
    "ToolNotFoundError",
    "CommandError",
]

LOGGER_NAME = "autoshorts"

# 윈도우/맥/리눅스 공통으로 파일명에 쓸 수 없는 문자
_ILLEGAL = r'<>:"/\\|?*'
_ILLEGAL_RE = re.compile(f"[{re.escape(_ILLEGAL)}]")
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_SPACE_RE = re.compile(r"\s+")
_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


class ToolNotFoundError(RuntimeError):
    """ffmpeg/ffprobe 등 외부 실행 파일을 찾지 못했을 때."""


class CommandError(RuntimeError):
    """외부 명령이 0이 아닌 코드로 종료했을 때."""

    def __init__(self, command: Sequence[str], returncode: int, stderr: str = "") -> None:
        self.command = list(command)
        self.returncode = returncode
        self.stderr = stderr or ""
        tail = "\n".join(self.stderr.strip().splitlines()[-15:])
        super().__init__(
            f"명령 실패 (exit {returncode}): {' '.join(self.command[:6])} ...\n{tail}"
        )


def sanitize_filename(name: str, max_length: int = 40, replacement: str = "_") -> str:
    """한글을 보존하면서 파일 시스템에 안전한 이름으로 정리한다.

    - 경로 구분자/제어문자/예약문자 제거
    - 연속 공백을 하나의 ``_`` 로 축약
    - 유니코드 NFC 정규화(맥에서 자모 분리 방지)
    - ``max_length`` 자로 절단, 앞뒤 공백/점 제거
    """
    if name is None:
        return ""
    text = unicodedata.normalize("NFC", str(name))
    text = _CONTROL_RE.sub("", text)
    text = _ILLEGAL_RE.sub(" ", text)
    # 이모지 등 서러게이트 페어는 파일 시스템별 처리가 달라 제거한다.
    text = "".join(ch for ch in text if unicodedata.category(ch) not in {"Cs", "So", "Cf"})
    text = _SPACE_RE.sub(" ", text).strip()
    text = text.replace(" ", replacement)
    text = re.sub(rf"{re.escape(replacement)}{{2,}}", replacement, text)
    text = text.strip(f"{replacement}. ")
    if max_length > 0:
        text = text[:max_length].strip(f"{replacement}. ")
    if text.upper().split(".")[0] in _WINDOWS_RESERVED:
        text = f"{text}{replacement}"
    return text


def human_duration(seconds: float) -> str:
    """``95.4`` -> ``1분 35초`` 형태의 사람이 읽는 길이."""
    seconds = max(0, int(round(float(seconds or 0))))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}시간 {minutes}분 {secs}초"
    if minutes:
        return f"{minutes}분 {secs}초"
    return f"{secs}초"


def ensure_dir(path: str | Path) -> Path:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def which_or_raise(tool: str, hint: str = "") -> str:
    """실행 파일 경로를 찾고, 없으면 설치 안내와 함께 예외."""
    override = os.environ.get(f"AUTOSHORTS_{tool.upper()}")
    if override:
        if Path(override).exists():
            return override
        raise ToolNotFoundError(f"환경변수로 지정한 {tool} 경로가 없습니다: {override}")
    found = shutil.which(tool)
    if found:
        return found
    raise ToolNotFoundError(
        f"'{tool}' 을(를) 찾을 수 없습니다. {hint}".strip()
    )


def run_command(
    command: Sequence[str],
    *,
    capture: bool = True,
    check: bool = True,
    timeout: float | None = None,
    log: logging.Logger | None = None,
) -> subprocess.CompletedProcess:
    """외부 명령 실행 래퍼. 실패 시 stderr 꼬리를 담은 :class:`CommandError`."""
    log = log or get_logger()
    log.debug("실행: %s", " ".join(str(c) for c in command))
    proc = subprocess.run(
        [str(c) for c in command],
        capture_output=capture,
        text=True,
        timeout=timeout,
        check=False,
    )
    if check and proc.returncode != 0:
        raise CommandError(command, proc.returncode, proc.stderr or "")
    return proc


def setup_logging(verbose: bool = False, quiet: bool = False) -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    level = logging.DEBUG if verbose else (logging.WARNING if quiet else logging.INFO)
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler(stream=sys.stderr)
        handler.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-7s %(message)s", "%H:%M:%S"))
        logger.addHandler(handler)
    for handler in logger.handlers:
        handler.setLevel(level)
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    return logging.getLogger(LOGGER_NAME if not name else f"{LOGGER_NAME}.{name}")
