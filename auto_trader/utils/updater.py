"""GitHub 에서 최신 코드를 받아 제자리에 덮어쓴다.

매번 ZIP 을 내려받아 압축을 풀고 키를 다시 넣는 일을 없애기 위한 모듈이다.
**사용자 데이터는 절대 건드리지 않는다** — `.env`(키), `data/`(DB·상태),
`logs/`, `.venv/`, 그리고 사용자가 손댔을 `config/settings.yaml`·`holidays.txt`.
그래서 몇 번을 업데이트해도 키를 다시 입력할 일이 없다.

적용 순서는 '받아서 검증한 뒤 교체' 다. 내려받은 것이 온전한 프로젝트인지
확인하기 전에는 기존 파일을 하나도 건드리지 않는다.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from utils.logger import get_logger

KST = ZoneInfo("Asia/Seoul")
logger = get_logger("updater")

OWNER = "himan98hkt-prog"
REPO = "-"
BRANCH = "claude/program-development-n5frzn"
SUBDIR = "auto_trader"  # 저장소 안에서 프로그램이 들어 있는 폴더

API_COMMIT = "https://api.github.com/repos/{owner}/{repo}/commits/{branch}"
ZIP_URL = "https://codeload.github.com/{owner}/{repo}/zip/refs/heads/{branch}"

TIMEOUT_SEC = 60
VERSION_FILE = "version.json"

# 업데이트가 덮어쓸 대상. 여기 없는 것은 손대지 않는다.
CODE_DIRS = ("agents", "data_pipeline", "dashboard", "logic", "scripts", "tests", "trading", "utils")
CODE_FILES = ("main.py", "requirements.txt", "pytest.ini", "start.sh", "start.bat",
              "update.bat", "install.bat", ".env.example", "README.md", "SETUP.md")

# 사용자가 고쳤을 수 있는 설정 파일 — 덮어쓰지 않고 `.new` 로 남긴다.
USER_EDITABLE = ("config/settings.yaml", "config/holidays.txt")


class UpdateError(RuntimeError):
    """업데이트를 진행할 수 없을 때. 이 예외가 나도 기존 설치는 그대로다."""


@dataclass
class Version:
    sha: str = ""
    message: str = ""
    updated_at: str = ""

    @property
    def short(self) -> str:
        return self.sha[:7] if self.sha else "(알 수 없음)"


@dataclass
class UpdateResult:
    updated: bool
    version: Version
    changed: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    deps_changed: bool = False


def _http_get(url: str, *, as_json: bool = False):
    request = urllib.request.Request(url, headers={"User-Agent": "auto-trader-updater"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SEC) as response:
            payload = response.read()
    except urllib.error.HTTPError as exc:
        raise UpdateError(f"서버 응답 오류 (HTTP {exc.code}) — 잠시 후 다시 시도하세요") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise UpdateError(f"인터넷 연결을 확인하세요 ({exc})") from exc
    return json.loads(payload) if as_json else payload


def read_version(base_dir: Path) -> Version:
    """현재 설치된 버전. 파일이 없거나 깨졌으면 빈 값."""
    path = Path(base_dir) / "data" / VERSION_FILE
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return Version()
    return Version(sha=raw.get("sha", ""), message=raw.get("message", ""),
                   updated_at=raw.get("updated_at", ""))


def write_version(base_dir: Path, version: Version) -> None:
    path = Path(base_dir) / "data" / VERSION_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "sha": version.sha, "message": version.message,
        "updated_at": version.updated_at,
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def latest_version(*, branch: str = BRANCH) -> Version:
    """GitHub 에서 최신 커밋 정보를 읽는다."""
    data = _http_get(API_COMMIT.format(owner=OWNER, repo=REPO, branch=branch), as_json=True)
    message = (data.get("commit", {}).get("message") or "").splitlines()[0]
    return Version(sha=data.get("sha", ""), message=message)


def check(base_dir: Path, *, branch: str = BRANCH) -> tuple[bool, Version, Version]:
    """(새 버전 있음?, 현재, 최신)."""
    current = read_version(Path(base_dir))
    latest = latest_version(branch=branch)
    return (bool(latest.sha) and latest.sha != current.sha, current, latest)


def _download_source(branch: str, workdir: Path) -> Path:
    """ZIP 을 받아 풀고, 프로그램 폴더 경로를 돌려준다."""
    archive = workdir / "source.zip"
    archive.write_bytes(_http_get(ZIP_URL.format(owner=OWNER, repo=REPO, branch=branch)))

    extract_to = workdir / "extracted"
    try:
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(extract_to)
    except zipfile.BadZipFile as exc:
        raise UpdateError("내려받은 파일이 손상됐습니다 — 다시 시도하세요") from exc

    roots = [p for p in extract_to.iterdir() if p.is_dir()]
    if len(roots) != 1:
        raise UpdateError("압축 구조가 예상과 다릅니다")
    source = roots[0] / SUBDIR

    # 온전한 프로젝트인지 확인하기 전에는 기존 파일을 건드리지 않는다.
    if not (source / "main.py").exists() or not (source / "requirements.txt").exists():
        raise UpdateError("내려받은 코드가 온전하지 않습니다 — 기존 설치는 그대로 두었습니다")
    return source


def _copy_tree(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def apply_update(base_dir: Path, *, branch: str = BRANCH) -> UpdateResult:
    """최신 코드를 받아 적용한다. 사용자 데이터는 그대로 둔다."""
    base = Path(base_dir)
    current = read_version(base)
    changed: list[str] = []
    notes: list[str] = []

    with tempfile.TemporaryDirectory(prefix="auto-trader-update-") as tmp:
        workdir = Path(tmp)
        source = _download_source(branch, workdir)

        old_requirements = (base / "requirements.txt").read_text(encoding="utf-8") \
            if (base / "requirements.txt").exists() else ""

        for name in CODE_DIRS:
            incoming = source / name
            if incoming.is_dir():
                _copy_tree(incoming, base / name)
                changed.append(f"{name}/")

        for name in CODE_FILES:
            incoming = source / name
            if incoming.is_file():
                shutil.copy2(incoming, base / name)
                changed.append(name)

        # 설정 파일은 덮어쓰지 않는다 — 사용자가 손댔을 수 있다.
        for relative in USER_EDITABLE:
            incoming = source / relative
            existing = base / relative
            if not incoming.is_file():
                continue
            if not existing.exists():
                existing.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(incoming, existing)
                changed.append(relative)
            elif incoming.read_bytes() != existing.read_bytes():
                shutil.copy2(incoming, existing.with_suffix(existing.suffix + ".new"))
                notes.append(f"{relative} 이(가) 바뀌었습니다 — 새 파일을 {relative}.new 로 뒀습니다")

        new_requirements = (base / "requirements.txt").read_text(encoding="utf-8") \
            if (base / "requirements.txt").exists() else ""

    latest = latest_version(branch=branch)
    latest.updated_at = datetime.now(KST).isoformat(timespec="seconds")
    write_version(base, latest)

    deps_changed = old_requirements != new_requirements
    if deps_changed:
        notes.append("의존성이 바뀌었습니다 — start.bat / start.sh 를 다시 실행하면 자동으로 설치됩니다")

    logger.info("업데이트 적용: %s → %s (%d개 항목)", current.short, latest.short, len(changed))
    return UpdateResult(updated=True, version=latest, changed=changed,
                        notes=notes, deps_changed=deps_changed)
