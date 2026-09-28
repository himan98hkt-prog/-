"""윈도우 작업 스케줄러 연동.

매일 정해진 시각에 자동 생성·업로드가 돌도록 예약을 만들고 지운다.
관리자 권한 없이 현재 사용자 계정으로 등록된다.

채널마다 예약이 따로 만들어진다. 예전에는 작업 이름과 daily.bat 이
하나뿐이라, 두 번째 채널의 예약을 켜는 순간 첫 채널의 예약을 덮어썼다.

리눅스·맥에서는 동작하지 않는다. supported() 로 먼저 확인할 것.
"""

from __future__ import annotations

import platform
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

# 채널을 지정하지 않던 시절의 이름. 이미 등록된 예약을 잃지 않으려고 그대로 둔다.
TASK_NAME = "AI DEOKHU 자동업로드"
ROOT = Path(__file__).resolve().parent.parent

# 생성에 5~10분이 걸리므로 게시 시각보다 앞서 시작한다.
LEAD_MINUTES = 30

# 한 번 돌기 시작하면 이 시간 안에 끝나야 한다. 넘으면 작업 스케줄러가
# 끊는다. 넉넉히 두되 무한정은 아니다 — 멈춘 작업이 다음 날 실행을 막는다.
MAX_RUNTIME_HOURS = 2


@dataclass
class Schedule:
    enabled: bool
    start_time: str = ""        # 작업이 시작되는 시각 (HH:MM)
    publish_time: str = ""      # 실제 게시 시각 (HH:MM)
    next_run: str = ""
    targets: list[str] = None
    raw: str = ""

    def __post_init__(self):
        if self.targets is None:
            self.targets = []


def supported() -> bool:
    return platform.system() == "Windows"


def task_name(slug: str = "default", name: str = "") -> str:
    """이 채널의 작업 스케줄러 이름.

    기본 채널은 예전 이름을 그대로 쓴다. 이름을 바꾸면 이미 등록된 예약이
    고아가 되어, 끄지도 못하는 작업이 매일 남는다.
    """
    if slug == "default":
        return TASK_NAME
    return f"쇼츠 자동업로드 - {name or slug}"


def runner_path(slug: str = "default") -> Path:
    """이 채널의 예약이 실행할 배치 파일 경로."""
    return ROOT / ("daily.bat" if slug == "default" else f"daily-{slug}.bat")


def _run(args: list[str]) -> tuple[int, str]:
    try:
        p = subprocess.run(args, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=30)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)


def _minus(hhmm: str, minutes: int) -> str:
    h, m = (int(x) for x in hhmm.split(":"))
    t = datetime(2000, 1, 1, h, m) - timedelta(minutes=minutes)
    return t.strftime("%H:%M")


def write_runner(publish_time: str, targets: list[str], mode: str = "chain",
                 *, config: str = "config.yaml", seeds: str = "seeds",
                 slug: str = "default", runs_dir: str = "runs") -> Path:
    """예약이 실행할 배치 파일. 폴더를 옮겨도 따라가도록 %~dp0 을 쓴다."""
    flags = " ".join(f"--{t}" for t in targets) or "--youtube"
    bat = runner_path(slug)
    # cmd 는 배치 파일을 OEM 코드페이지(한국어 윈도우는 949)로 읽는다.
    # UTF-8 로 저장한 한글 주석은 깨져서 명령으로 실행되려다 오류를 낸다.
    # 그래서 이 파일 안에는 ASCII 만 쓴다. 채널 이름도 slug(영문) 를 쓴다.
    bat.write_text(
        "@echo off\r\n"
        f"REM Daily auto-upload for channel: {slug}\r\n"
        "REM Run by Windows Task Scheduler.\r\n"
        "REM Generated automatically when you turn the schedule on. Do not edit.\r\n"
        'cd /d "%~dp0"\r\n'
        f'if not exist "%~dp0{runs_dir}" mkdir "%~dp0{runs_dir}"\r\n'
        f"python -m publish.scheduler --at {publish_time} --mode {mode} "
        f'--config "{config}" --seeds "{seeds}" {flags} '
        f'>> "%~dp0{runs_dir}\\cron.log" 2>&1\r\n',
        encoding="ascii", newline="")
    return bat


def build_task_xml(bat: Path, start_time: str, *, description: str = "") -> str:
    """작업 스케줄러 등록용 XML.

    schtasks /Create 의 명령줄 옵션만으로는 **놓친 실행을 따라잡을 수 없다.**
    아침 9시 예약에서 이게 그대로 문제가 된다 — 새벽에 PC 가 절전으로
    들어가 있으면 8시 30분 실행이 그냥 건너뛰어지고, 그날 영상이 안 올라가는데
    화면에는 아무 오류도 남지 않는다.

    StartWhenAvailable 로 깨어난 직후에 따라잡게 하고, WakeToRun 으로
    절전에서 깨우기까지 시도한다. 둘 다 XML 로만 지정할 수 있다.
    """
    h, m = (int(x) for x in start_time.split(":"))
    # StartBoundary 의 날짜는 '이 시각부터 유효' 라는 뜻일 뿐, 반복은
    # ScheduleByDay 가 정한다. 과거 날짜를 써야 오늘부터 바로 유효하다.
    start = f"2020-01-01T{h:02d}:{m:02d}:00"
    return (
        '<?xml version="1.0" encoding="UTF-16"?>\n'
        '<Task version="1.2" '
        'xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">\n'
        "  <RegistrationInfo>\n"
        f"    <Description>{_xml_escape(description)}</Description>\n"
        "  </RegistrationInfo>\n"
        "  <Triggers>\n"
        "    <CalendarTrigger>\n"
        f"      <StartBoundary>{start}</StartBoundary>\n"
        "      <Enabled>true</Enabled>\n"
        "      <ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>\n"
        "    </CalendarTrigger>\n"
        "  </Triggers>\n"
        "  <Principals>\n"
        '    <Principal id="Author">\n'
        "      <LogonType>InteractiveToken</LogonType>\n"
        "      <RunLevel>LeastPrivilege</RunLevel>\n"
        "    </Principal>\n"
        "  </Principals>\n"
        "  <Settings>\n"
        # 놓친 실행을 깨어난 뒤에 따라잡는다. 이 예약의 핵심.
        "    <StartWhenAvailable>true</StartWhenAvailable>\n"
        "    <WakeToRun>true</WakeToRun>\n"
        # 노트북에서 배터리로 돌 때도 실행한다. 막아 두면 전원을 안 꽂은
        # 날에는 조용히 건너뛴다.
        "    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>\n"
        "    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>\n"
        f"    <ExecutionTimeLimit>PT{MAX_RUNTIME_HOURS}H</ExecutionTimeLimit>\n"
        # 앞 작업이 아직 돌고 있으면 새로 시작하지 않는다. 같은 시드로
        # 두 편이 만들어지면 값이 두 번 나간다.
        "    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>\n"
        "    <Enabled>true</Enabled>\n"
        "  </Settings>\n"
        '  <Actions Context="Author">\n'
        "    <Exec>\n"
        f"      <Command>{_xml_escape(str(bat))}</Command>\n"
        f"      <WorkingDirectory>{_xml_escape(str(bat.parent))}</WorkingDirectory>\n"
        "    </Exec>\n"
        "  </Actions>\n"
        "</Task>\n"
    )


def _xml_escape(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))


def enable(publish_time: str = "21:00", targets: list[str] | None = None,
           mode: str = "chain", *, config: str = "config.yaml",
           seeds: str = "seeds", slug: str = "default", name: str = "",
           runs_dir: str = "runs") -> tuple[bool, str]:
    """매일 실행 예약을 만든다. 이미 있으면 덮어쓴다."""
    if not supported():
        return False, "윈도우에서만 예약을 만들 수 있습니다."
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", publish_time):
        return False, f"시각 형식이 잘못됐습니다: {publish_time} (예: 09:00)"

    targets = targets or ["youtube"]
    bad = [t for t in targets if t not in ("youtube", "instagram")]
    if bad:
        return False, f"알 수 없는 업로드 대상: {', '.join(bad)}"

    bat = write_runner(publish_time, targets, mode, config=config,
                       seeds=seeds, slug=slug, runs_dir=runs_dir)
    start = _minus(publish_time, LEAD_MINUTES)
    tname = task_name(slug, name)
    label = name or slug

    # 먼저 XML 로 등록한다. 놓친 실행 따라잡기(StartWhenAvailable)가 여기에만 있다.
    xml_path = ROOT / f".task-{slug}.xml"
    note = ""
    try:
        # schtasks /XML 은 유니코드 파일을 요구한다. UTF-16 로 쓴다.
        xml_path.write_text(
            build_task_xml(bat, start, description=f"쇼츠 자동 생성·업로드 ({label})"),
            encoding="utf-16")
        code, out = _run(["schtasks", "/Create", "/TN", tname,
                          "/XML", str(xml_path), "/F"])
    except OSError as exc:
        code, out = 1, str(exc)
    finally:
        xml_path.unlink(missing_ok=True)

    if code != 0:
        # XML 등록이 막히는 환경(정책·권한)이 있다. 예전 방식으로 물러선다.
        # 이 경로로 등록되면 절전 중 놓친 실행은 따라잡지 못하므로 그렇게 알린다.
        code, out = _run(["schtasks", "/Create", "/TN", tname,
                          "/TR", f'"{bat}"', "/SC", "DAILY", "/ST", start, "/F"])
        if code != 0:
            return False, f"예약 등록 실패:\n{out.strip()[:400]}"
        note = ("\n  ⚠ 이 PC 에서는 '놓친 실행 따라잡기' 를 걸지 못했습니다. "
                f"{start} 에 PC 가 꺼져 있거나 절전이면 그날은 건너뜁니다.")

    return True, (f"[{label}] 매일 {start} 에 시작해 {publish_time} 에 게시합니다. "
                  f"(생성 시간 {LEAD_MINUTES}분 확보){note}")


def disable(*, slug: str = "default", name: str = "") -> tuple[bool, str]:
    if not supported():
        return False, "윈도우에서만 예약을 지울 수 있습니다."
    code, out = _run(["schtasks", "/Delete", "/TN", task_name(slug, name), "/F"])
    if code != 0 and "ERROR" in out.upper() and "cannot find" not in out.lower():
        return False, f"예약 해제 실패:\n{out.strip()[:300]}"
    return True, "예약을 껐습니다."


def status(*, slug: str = "default", name: str = "") -> Schedule:
    """현재 예약 상태. 없으면 enabled=False."""
    if not supported():
        return Schedule(enabled=False, raw="윈도우가 아닙니다.")

    code, out = _run(["schtasks", "/Query", "/TN", task_name(slug, name),
                      "/FO", "LIST", "/V"])
    if code != 0:
        return Schedule(enabled=False, raw=out.strip()[:200])

    def field(*names: str) -> str:
        for line in out.splitlines():
            for n in names:
                if line.strip().startswith(n):
                    return line.split(":", 1)[1].strip() if ":" in line else ""
        return ""

    next_run = field("Next Run Time", "다음 실행 시간")
    start = field("Start Time", "시작 시간")
    # 등록된 배치에서 실제 게시 시각과 대상을 되읽는다
    publish_time, targets = "", []
    bat = runner_path(slug)
    if bat.exists():
        text = bat.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"--at\s+(\d{2}:\d{2})", text)
        if m:
            publish_time = m.group(1)
        targets = [t for t in ("youtube", "instagram") if f"--{t}" in text]

    return Schedule(enabled=True, start_time=start, publish_time=publish_time,
                    next_run=next_run, targets=targets, raw="")
