"""윈도우 작업 스케줄러 연동.

매일 정해진 시각에 자동 업로드가 돌도록 예약을 만들고 지운다.
관리자 권한 없이 현재 사용자 계정으로 등록된다.

**예전 방식이 매일 조용히 실패하던 이유 네 가지** (전부 여기서 막는다)

  1. 출력 인코딩. `python ... >> cron.log` 로 돌리면 한국어 윈도우에서는
     cp949 로 쓰는데 `—` 같은 글자가 없어서 첫 로그 줄에서 죽었다.
     (pipeline/console.py 에 자세히 적었다.) -> UTF-8 을 강제한다.
  2. `python` 이라는 이름. 작업실은 `py` 로도 켜지지만 예약은 `python` 만
     찾았다. PATH 에 없거나 스토어 가짜 python 이면 아무것도 안 한다.
     -> 작업실을 돌리는 바로 그 파이썬의 전체 경로를 쓴다.
  3. schtasks 의 기본 설정. 그 시각에 PC 가 절전이거나 꺼져 있으면 그날은
     건너뛴다. 노트북이 배터리면 아예 시작하지 않는다.
     -> 켜지면 바로 돌기 · 절전에서 깨우기 · 배터리에서도 돌기.
  4. 검은 창. 아침에 뜬 빈 창을 닫으면 작업이 그대로 죽는다.
     -> 창 없는 pythonw 로 돌리고 출력은 runs/cron.log 에 쓴다.

리눅스·맥에서는 동작하지 않는다. supported() 로 먼저 확인할 것.
"""

from __future__ import annotations

import base64
import json
import platform
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

TASK_NAME = "AI DEOKHU 자동업로드"
ROOT = Path(__file__).resolve().parent.parent

# 게시 시각보다 이만큼 앞서 시작한다. 클라우드는 한 편에 5~10분이면 되지만
# 내 PC(LTX) 는 그래픽카드에 따라 한 시간을 넘길 수 있다.
LEAD_MINUTES = 30
LEAD_MINUTES_LOCAL = 120

# 이보다 오래 걸리면 작업 스케줄러가 끊는다. 내 PC 생성까지 넉넉히.
TIME_LIMIT_HOURS = 6

DEFAULT_PUBLISH_TIME = "09:00"
LOG_REL = "runs/cron.log"


def task_name(slug: str = "default", name: str = "") -> str:
    """이 채널의 작업 스케줄러 이름.

    기본 채널은 예전 이름을 그대로 쓴다. 이름을 바꾸면 이미 걸려 있는 예약이
    고아가 되어, 끄지도 못하는 작업이 매일 남는다.
    """
    if slug == "default":
        return TASK_NAME
    return f"쇼츠 자동업로드 - {name or slug}"


def runner_path(slug: str = "default") -> Path:
    """이 채널의 예약이 실행할 배치 파일."""
    return ROOT / ("daily.bat" if slug == "default" else f"daily-{slug}.bat")


def log_rel(runs_dir: str = "runs") -> str:
    """채널별 예약 로그. 한 파일에 섞이면 어느 채널이 실패했는지 못 읽는다."""
    return f"{runs_dir}/cron.log"

# 작업 스케줄러 결과 코드 -> 사람이 읽을 말
RESULT_TEXT = {
    0: "정상 종료",
    1: "프로그램이 오류로 끝났습니다",
    2: "프로그램이 오류로 끝났습니다",
    9009: "python 을 찾지 못했습니다",
    267009: "지금 실행 중입니다",
    267011: "아직 한 번도 실행되지 않았습니다",
    267014: "누군가 중지했습니다",
    2147750687: "이전 실행이 아직 안 끝나 이번 회차를 건너뛰었습니다",
    2147942402: "실행할 파일을 찾지 못했습니다 (파이썬이나 폴더를 옮겼나요?)",
    2147942667: "작업 폴더를 찾지 못했습니다 (AI DEOKHU 폴더를 옮겼나요?)",
    3221225786: "창을 닫거나 Ctrl+C 로 중단됐습니다",
}


@dataclass
class Schedule:
    enabled: bool
    start_time: str = ""        # 작업이 시작되는 시각 (HH:MM)
    publish_time: str = ""      # 실제 게시 시각 (HH:MM)
    next_run: str = ""
    targets: list[str] = field(default_factory=list)
    mode: str = "chain"
    raw: str = ""
    info: dict = field(default_factory=dict)   # PowerShell 로 읽은 원자료


def supported() -> bool:
    return platform.system() == "Windows"


def _run(args: list[str], timeout: int = 60) -> tuple[int, str]:
    try:
        p = subprocess.run(args, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout,
                           creationflags=0x08000000 if supported() else 0)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)


def _powershell(script: str, timeout: int = 60) -> tuple[int, str]:
    """따옴표·한글이 섞여도 깨지지 않게 UTF-16 base64 로 넘긴다."""
    prelude = "[Console]::OutputEncoding = [Text.Encoding]::UTF8\n"
    encoded = base64.b64encode((prelude + script).encode("utf-16-le")).decode()
    return _run(["powershell", "-NoProfile", "-NonInteractive",
                 "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded], timeout)


def _q(text: str) -> str:
    """PowerShell 작은따옴표 문자열."""
    return "'" + str(text).replace("'", "''") + "'"


def _minus(hhmm: str, minutes: int) -> str:
    h, m = (int(x) for x in hhmm.split(":"))
    t = datetime(2000, 1, 1, h, m) - timedelta(minutes=minutes)
    return t.strftime("%H:%M")


def lead_minutes_for(provider: str) -> int:
    return LEAD_MINUTES_LOCAL if provider == "local" else LEAD_MINUTES


# ── 어떤 파이썬으로 돌릴 것인가 ─────────────────────────────────────────
def python_exe(*, windowless: bool = False) -> Path:
    """작업실을 돌리고 있는 바로 그 파이썬. 창 없이 돌릴 때는 pythonw."""
    exe = Path(sys.executable)
    if windowless:
        w = exe.with_name("pythonw.exe")
        if w.exists():
            return w
    if exe.name.lower() == "pythonw.exe":
        c = exe.with_name("python.exe")
        if c.exists():
            return c
    return exe


def scheduler_args(publish_time: str, targets: list[str], mode: str, *,
                   config: str = "config.yaml", seeds: str = "",
                   runs_dir: str = "runs") -> str:
    flags = " ".join(f"--{t}" for t in targets) or "--youtube"
    extra = f' --config "{config}"'
    if seeds:
        extra += f' --seeds "{seeds}"'
    return (f"-m publish.scheduler --at {publish_time} --mode {mode} {flags}"
            f"{extra} --log {log_rel(runs_dir)}")


def write_runner(publish_time: str, targets: list[str], mode: str = "chain", *,
                 slug: str = "default", config: str = "config.yaml",
                 seeds: str = "", runs_dir: str = "runs") -> Path:
    """손으로 눌러 시험하거나, PowerShell 이 막혔을 때 쓰는 배치 파일.

    cmd 는 배치 파일을 OEM 코드페이지(한국어 윈도우는 949)로 읽는다.
    UTF-8 로 저장한 한글은 깨져서 명령으로 실행되려다 오류를 낸다.
    그래서 가능하면 ASCII 로만 쓰고, 파이썬 경로에 한글이 있을 때만(사용자
    이름이 한글이면 그렇다) OEM 으로 쓴다.
    """
    bat = runner_path(slug)
    py = str(python_exe())
    body = (
        "@echo off\r\n"
        f"REM Daily auto-upload for channel: {slug}\r\n"
        "REM Run by Windows Task Scheduler.\r\n"
        "REM Generated automatically when you turn the schedule on. Do not edit.\r\n"
        'cd /d "%~dp0"\r\n'
        # 1번 원인. 이게 없으면 첫 로그 줄에서 죽는다.
        "set PYTHONUTF8=1\r\n"
        "set PYTHONIOENCODING=utf-8\r\n"
        f'if not exist "%~dp0{runs_dir}" mkdir "%~dp0{runs_dir}"\r\n'
        f'"{py}" {scheduler_args(publish_time, targets, mode, config=config, seeds=seeds, runs_dir=runs_dir)}\r\n'
    )
    try:
        data = body.encode("ascii")
    except UnicodeEncodeError:
        try:
            data = body.encode("oem")            # 윈도우에만 있는 코덱
        except (LookupError, UnicodeEncodeError):
            # 경로를 못 담으면 예전처럼 PATH 의 python 에 맡긴다
            data = body.replace(f'"{py}"', "python").encode("ascii", "replace")
    bat.write_bytes(data)
    return bat


# ── 등록 ──────────────────────────────────────────────────────────────
def register_script(start: str, publish_time: str, targets: list[str], mode: str,
                    *, pythonw: str, workdir: str, task: str = TASK_NAME,
                    config: str = "config.yaml", seeds: str = "",
                    runs_dir: str = "runs") -> str:
    """Register-ScheduledTask 스크립트. 설정 하나하나가 예전 실패 원인 하나씩이다."""
    return "\n".join([
        "$ErrorActionPreference = 'Stop'",
        f"$a = New-ScheduledTaskAction -Execute {_q(pythonw)} "
        f"-Argument {_q(scheduler_args(publish_time, targets, mode, config=config, seeds=seeds, runs_dir=runs_dir))} "
        f"-WorkingDirectory {_q(workdir)}",
        f"$t = New-ScheduledTaskTrigger -Daily -At {_q(start)}",
        # 켜지면 바로 · 절전에서 깨우기 · 배터리여도 시작하고 안 멈추기
        "$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun "
        "-AllowStartIfOnBatteries -DontStopIfGoingOnBatteries "
        f"-ExecutionTimeLimit (New-TimeSpan -Hours {TIME_LIMIT_HOURS}) "
        "-MultipleInstances IgnoreNew "
        "-RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 10)",
        "$u = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name",
        "$p = New-ScheduledTaskPrincipal -UserId $u -LogonType Interactive -RunLevel Limited",
        f"Register-ScheduledTask -TaskName {_q(task)} -Action $a -Trigger $t "
        "-Settings $s -Principal $p -Force | Out-Null",
        "'OK'",
    ])


def allow_wake_timers() -> str:
    """전원 설정의 '깨우기 타이머 허용' 을 켠다(전원 연결 시).

    WakeToRun 을 걸어도 이게 꺼져 있으면 절전에서 안 깨어난다. 윈도우 11
    기본값이 '중요한 깨우기 타이머만' 인 PC 가 많다.
    """
    code1, out1 = _run(["powercfg", "/SETACVALUEINDEX", "SCHEME_CURRENT",
                        "SUB_SLEEP", "RTCWAKE", "1"])
    code2, _ = _run(["powercfg", "/SETACTIVE", "SCHEME_CURRENT"])
    if code1 == 0 and code2 == 0:
        return "절전 중이어도 그 시각에 깨우도록 전원 설정을 켰습니다."
    return ("전원 설정의 '깨우기 타이머 허용' 을 바꾸지 못했습니다. PC 를 절전 "
            "상태로 두면 못 깨울 수 있습니다. (" + out1.strip()[:80] + ")")


def enable(publish_time: str = DEFAULT_PUBLISH_TIME, targets: list[str] | None = None,
           mode: str = "chain", *, lead_minutes: int = LEAD_MINUTES,
           config: str = "config.yaml", seeds: str = "", slug: str = "default",
           name: str = "", runs_dir: str = "runs") -> tuple[bool, str]:
    """매일 실행 예약을 만든다. 이미 있으면 덮어쓴다."""
    if not supported():
        return False, "윈도우에서만 예약을 만들 수 있습니다."
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", publish_time):
        return False, f"시각 형식이 잘못됐습니다: {publish_time} (예: 09:00)"

    targets = targets or ["youtube"]
    bad = [t for t in targets if t not in ("youtube", "instagram")]
    if bad:
        return False, f"알 수 없는 업로드 대상: {', '.join(bad)}"
    if mode not in ("chain", "montage"):
        mode = "chain"

    bat = write_runner(publish_time, targets, mode, slug=slug, config=config,
                       seeds=seeds, runs_dir=runs_dir)
    start = _minus(publish_time, lead_minutes)
    tname = task_name(slug, name)

    code, out = _powershell(register_script(
        start, publish_time, targets, mode,
        pythonw=str(python_exe(windowless=True)), workdir=str(ROOT),
        task=tname, config=config, seeds=seeds, runs_dir=runs_dir))
    if code == 0 and "OK" in out:
        wake = allow_wake_timers()
        return True, (f"매일 {start} 에 시작해 {publish_time} 에 게시합니다 "
                      f"(만드는 시간 {lead_minutes}분 확보).\n"
                      f"PC 가 그 시각에 꺼져 있었으면 켜지는 대로 바로 돌고, "
                      f"창은 뜨지 않습니다.\n{wake}")

    # PowerShell 이 막힌 PC 를 위한 예전 방식. 깨우기·놓친 회차 보충은 안 된다.
    code2, out2 = _run(["schtasks", "/Create", "/TN", tname,
                        "/TR", f'"{bat}"', "/SC", "DAILY", "/ST", start, "/F"])
    if code2 != 0:
        return False, (f"예약 등록 실패:\n{out.strip()[:300]}\n{out2.strip()[:300]}")
    return True, (f"매일 {start} 에 시작해 {publish_time} 에 게시합니다.\n"
                  "⚠ 간단한 방식으로 등록됐습니다. 그 시각에 PC 가 켜져 있고 "
                  "로그인돼 있어야 돕니다.")


def disable(*, slug: str = "default", name: str = "") -> tuple[bool, str]:
    if not supported():
        return False, "윈도우에서만 예약을 지울 수 있습니다."
    code, out = _run(["schtasks", "/Delete", "/TN", task_name(slug, name), "/F"])
    if code != 0 and "ERROR" in out.upper() and "cannot find" not in out.lower():
        return False, f"예약 해제 실패:\n{out.strip()[:300]}"
    return True, "예약을 껐습니다."


def run_now(*, slug: str = "default", name: str = "") -> tuple[bool, str]:
    """예약을 지금 한 번 돌린다. 아침 9시에 도는 것과 **똑같은 경로**로 돈다.

    작업실에서 누르는 [만들기] 는 작업실 안에서 돈다. 예약은 작업 스케줄러가
    따로 띄운다. 예약이 안 되는 원인은 대부분 그 차이에 있으니, 시험도
    예약 쪽으로 해야 의미가 있다.
    """
    if not supported():
        return False, "윈도우에서만 됩니다."
    code, out = _run(["schtasks", "/Run", "/TN", task_name(slug, name)])
    if code != 0:
        return False, f"실행하지 못했습니다:\n{out.strip()[:300]}"
    return True, ("예약을 지금 한 번 돌렸습니다. 창은 뜨지 않습니다. "
                  "몇 분 뒤 아래 '마지막 실행' 을 확인하세요.")


# ── 상태 읽기 ─────────────────────────────────────────────────────────
def query_script(task: str = TASK_NAME) -> str:
    return "\n".join([
        "$ErrorActionPreference = 'Stop'",
        f"$t = Get-ScheduledTask -TaskName {_q(task)}",
        "$i = $t | Get-ScheduledTaskInfo",
        "$last = if ($i.LastRunTime) { $i.LastRunTime.ToString('s') } else { '' }",
        "$next = if ($i.NextRunTime) { $i.NextRunTime.ToString('s') } else { '' }",
        "$act = $t.Actions | Select-Object -First 1",
        "$trg = $t.Triggers | Select-Object -First 1",
        "[pscustomobject]@{",
        "  last_run = $last; result = [int64]$i.LastTaskResult; next_run = $next;",
        "  missed = [int]$i.NumberOfMissedRuns;",
        "  wake = [bool]$t.Settings.WakeToRun;",
        "  when_available = [bool]$t.Settings.StartWhenAvailable;",
        "  no_battery = [bool]$t.Settings.DisallowStartIfOnBatteries;",
        "  execute = [string]$act.Execute; arguments = [string]$act.Arguments;",
        "  start = [string]$trg.StartBoundary",
        "} | ConvertTo-Json -Compress",
    ])


def parse_info(text: str) -> dict:
    """PowerShell 이 준 JSON 한 줄. 앞뒤 잡음은 버린다."""
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return {}
    try:
        data = json.loads(m.group(0))
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _hhmm(iso: str) -> str:
    m = re.search(r"T(\d{2}:\d{2})", iso or "")
    return m.group(1) if m else ""


def read_args(text: str) -> tuple[str, list[str], str]:
    """실행 인자(또는 배치 파일)에서 게시 시각 · 대상 · 방식을 되읽는다."""
    m = re.search(r"--at\s+(\d{2}:\d{2})", text or "")
    publish = m.group(1) if m else ""
    targets = [t for t in ("youtube", "instagram") if f"--{t}" in (text or "")]
    mm = re.search(r"--mode\s+(chain|montage)", text or "")
    return publish, targets, mm.group(1) if mm else "chain"


def status(*, slug: str = "default", name: str = "") -> Schedule:
    """현재 예약 상태. 없으면 enabled=False."""
    if not supported():
        return Schedule(enabled=False, raw="윈도우가 아닙니다.")

    code, out = _powershell(query_script(task_name(slug, name)))
    info = parse_info(out) if code == 0 else {}
    if info:
        text = info.get("arguments", "")
        if not text:                               # 예전 방식: 배치 파일을 부른다
            bat = runner_path(slug)
            text = bat.read_text(encoding="utf-8", errors="replace") if bat.exists() else ""
        publish, targets, mode = read_args(text)
        return Schedule(enabled=True, start_time=_hhmm(info.get("start", "")),
                        publish_time=publish, next_run=info.get("next_run", ""),
                        targets=targets, mode=mode, info=info)

    # PowerShell 이 막혔으면 schtasks 로 있는지만 본다
    code, out = _run(["schtasks", "/Query", "/TN", task_name(slug, name),
                      "/FO", "LIST", "/V"])
    if code != 0:
        return Schedule(enabled=False, raw=out.strip()[:200])

    def pick(*names: str) -> str:
        for line in out.splitlines():
            for n in names:
                if line.strip().startswith(n):
                    return line.split(":", 1)[1].strip() if ":" in line else ""
        return ""

    bat = runner_path(slug)
    text = bat.read_text(encoding="utf-8", errors="replace") if bat.exists() else ""
    publish, targets, mode = read_args(text)
    return Schedule(enabled=True, start_time=pick("Start Time", "시작 시간"),
                    publish_time=publish,
                    next_run=pick("Next Run Time", "다음 실행 시간"),
                    targets=targets, mode=mode)


def is_legacy(info: dict) -> bool:
    """예전 방식(daily.bat + 기본 설정)으로 등록돼 있는가."""
    if not info:
        return False
    return ("--log" not in (info.get("arguments") or "")
            or not info.get("when_available"))


def repair(lead_minutes: int | None = None) -> tuple[bool, str]:
    """예전 방식으로 등록된 예약을 새 방식으로 다시 건다.

    업데이트만 하고 [예약 저장] 을 다시 안 누르면 예전 예약이 계속 남아
    매일 똑같이 죽는다. 작업실을 켤 때와 업데이트 직후에 부른다.
    """
    if not supported():
        return False, ""
    st = status()
    if not st.enabled:
        return False, ""
    if st.info and not is_legacy(st.info):
        return False, ""                         # 이미 새 방식
    publish = st.publish_time or DEFAULT_PUBLISH_TIME
    if lead_minutes is None and st.start_time and st.publish_time:
        h1, m1 = (int(x) for x in st.start_time.split(":"))
        h2, m2 = (int(x) for x in st.publish_time.split(":"))
        lead_minutes = ((h2 * 60 + m2) - (h1 * 60 + m1)) % (24 * 60) or LEAD_MINUTES
    return enable(publish, st.targets or ["youtube"], st.mode,
                  lead_minutes=lead_minutes or LEAD_MINUTES)


# ── 왜 안 됐나 ────────────────────────────────────────────────────────
def _parse_iso(text: str) -> datetime | None:
    try:
        d = datetime.fromisoformat((text or "").strip())
    except ValueError:
        return None
    return d if d.year >= 2000 else None          # 안 돈 작업은 1999-11-30 이 온다


def _last_history(root: Path) -> str:
    path = root / "runs" / "schedule.log"
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return lines[-1] if lines else ""


def _log_error(root: Path) -> str:
    """cron.log 끝에서 사람이 읽을 만한 오류 한 줄."""
    path = root / "runs" / "cron.log"
    try:
        tail = path.read_text(encoding="utf-8", errors="replace").splitlines()[-60:]
    except OSError:
        return ""
    for line in reversed(tail):
        s = line.strip()
        if re.search(r"(Error|Exception|✗|실패)", s) and not s.startswith("File "):
            return s[:240]
    return ""


def _history_reason(line: str) -> tuple[str, str]:
    """schedule.log 의 FAIL 줄 -> (무슨 일, 어떻게)."""
    if "시드 소진" in line:
        return ("넣어둔 이미지를 다 썼습니다.",
                "[만들기] 탭에서 이미지를 더 넣으세요. 한 번에 일주일치를 넣어두면 편합니다.")
    if "시드 폴더 없음" in line:
        return ("seeds 폴더가 없습니다.", "[만들기] 탭에서 이미지를 넣으면 만들어집니다.")
    if "생성 실패" in line:
        return ("영상을 만들다가 실패했습니다.",
                "아래 오류를 보고, [점검] 탭에서 빨간 항목이 있는지 확인하세요.")
    if "결과물 없음" in line:
        return ("만든 영상 파일을 찾지 못했습니다.", "[점검] 탭에서 ffmpeg 을 확인하세요.")
    if "예상 못 한 오류" in line:
        return ("프로그램이 예상 못 한 오류로 멈췄습니다.", "아래 오류 내용을 보내주시면 고치겠습니다.")
    if "PARTIAL" in line:
        return ("한 곳에만 올라가고 다른 한 곳은 실패했습니다.",
                "[설정] 탭에서 실패한 쪽 연결을 다시 확인하세요.")
    return ("실패했습니다.", "아래 오류를 확인하세요.")


def explain(info: dict, state: dict, history: str, log_error: str,
            now: datetime | None = None) -> dict:
    """예약 상태를 사람 말로. 순수 함수라 리눅스에서도 시험할 수 있다.

    돌려주는 것: level(ok|warn|bad|info), headline, details[], fixes[]
    """
    now = now or datetime.now()
    details: list[str] = []
    fixes: list[str] = []

    if not info:
        return {"level": "info", "headline": "예약이 꺼져 있습니다.",
                "details": [], "fixes": ["아래에서 시각을 고르고 [예약 저장] 을 누르세요."]}

    last = _parse_iso(info.get("last_run", ""))
    code = int(info.get("result") or 0)
    start_hhmm = _hhmm(info.get("start", ""))

    # 설정 점검 — 이게 틀려 있으면 결과가 좋아도 언젠가 빠진다
    if is_legacy(info):
        details.append("예전 방식으로 등록돼 있습니다. 이 방식은 한국어 윈도우에서 "
                       "매번 첫 줄에서 멈췄습니다.")
        fixes.append("[예약 저장] 을 한 번 누르면 새 방식으로 다시 걸립니다.")
    if info.get("no_battery"):
        details.append("노트북이 배터리로 돌 때는 시작하지 않게 돼 있습니다.")
    if info.get("wake") is False:
        details.append("절전 중에는 깨우지 않게 돼 있습니다.")

    # 지금 돌고 있음. 기록만 'running' 이고 오래됐으면 도중에 PC 가 꺼진 것이다.
    started = _parse_iso(state.get("started", ""))
    still = (state.get("result") == "running" and not state.get("finished")
             and started is not None
             and now - started < timedelta(hours=TIME_LIMIT_HOURS))
    if code == 267009 or still:
        return {"level": "info", "headline": "지금 만드는 중입니다.",
                "details": details, "fixes": fixes}

    if last is None or code == 267011:
        nxt = info.get("next_run", "")
        return {"level": "warn" if details else "info",
                "headline": "아직 한 번도 실행되지 않았습니다."
                            + (f" 다음 실행: {nxt.replace('T', ' ')[:16]}" if nxt else ""),
                "details": details,
                "fixes": fixes or ["[지금 한 번 돌려보기] 로 미리 시험해 보세요."]}

    when = last.strftime("%m월 %d일 %H:%M")

    # 이번 회차를 놓쳤는가 — 오늘 시작 시각이 지났는데 마지막 실행이 그 전이다
    if start_hhmm:
        h, m = (int(x) for x in start_hhmm.split(":"))
        today_start = now.replace(hour=h, minute=m, second=0, microsecond=0)
        due = today_start if now >= today_start else today_start - timedelta(days=1)
        if last < due - timedelta(minutes=5):
            details.insert(0, f"{due.strftime('%m월 %d일 %H:%M')} 회차가 돌지 않았습니다. "
                              "그 시각에 PC 가 꺼져 있었거나 로그아웃 상태였습니다.")
            fixes.append("PC 를 끄지 말고 절전으로 두세요. 절전이면 깨워서 돌리고, "
                         "꺼져 있었으면 켜지는 대로 바로 돕니다.")
            return {"level": "warn", "headline": f"마지막 실행은 {when} 입니다.",
                    "details": details, "fixes": fixes}

    failed = (code != 0 or state.get("result") in ("fail", "crash")
              or "FAIL" in history or "PARTIAL" in history)
    if failed:
        what, how = _history_reason(history) if history else (
            RESULT_TEXT.get(code, f"오류 코드 {code}"), "아래 오류를 확인하세요.")
        if code not in (0, 1, 2) and code in RESULT_TEXT:
            what = RESULT_TEXT[code]
        details.insert(0, what)
        if log_error:
            details.append("오류: " + log_error)
        fixes.insert(0, how)
        return {"level": "bad", "headline": f"{when} 실행이 실패했습니다.",
                "details": details, "fixes": fixes}

    return {"level": "warn" if details else "ok",
            "headline": f"{when} 에 정상적으로 돌았습니다.",
            "details": details, "fixes": fixes}


def diagnose(root: Path = ROOT) -> dict:
    """작업실 [자동 업로드] 화면에 보여줄 '왜 안 됐나'."""
    if not supported():
        return {"level": "info", "headline": "윈도우에서만 예약을 씁니다.",
                "details": [], "fixes": []}
    st = status()
    state = {}
    try:
        state = json.loads((root / "runs" / "schedule_state.json")
                           .read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    info = st.info if st.enabled else {}
    if st.enabled and not info:
        info = {"arguments": "", "when_available": False}   # schtasks 로만 읽힘
    return explain(info, state, _last_history(root), _log_error(root))
