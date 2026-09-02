"""원장 PC 에 까는 목록이 실제 코드와 어긋나지 않게.

설치가 10분 넘게 멈춘 것처럼 보인 일이 있었다. 원인은 `pianoplayer` 였다 —
자동 운지를 위해 넣어 둔 것인데, 그것이 `vedo` → `vtk` 라는 **3D 시각화 도구**를
끌고 온다. 내려받는 바퀴 하나가 133MB, 풀면 566MB 다. 그런데 운지는
`app/analysis/teaching.py` 에서 직접 계산하므로 pianoplayer 는 코드 어디에서도
import 하지 않는다. PostgreSQL·Celery·Redis 도 마찬가지로 도커 배포용이다.

그래서 원장 PC 용 목록을 따로 둔다. 다만 목록을 나누면 **어긋나는 것**이 새 위험이
된다 — 새 의존성을 requirements.txt 에만 넣으면 원장 PC 에서만 ImportError 가 난다.
학원에서 프로그램이 안 켜지는 것으로 나타나고, 그때는 고쳐 줄 사람이 옆에 없다.

여기서 코드가 실제로 import 하는 것과 목록을 대조해 그 어긋남을 잡는다.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "server" / "app"
DESKTOP = ROOT / "server" / "requirements-desktop.txt"
FULL = ROOT / "server" / "requirements.txt"

# import 이름과 설치 이름이 다른 것들.
DIST_OF_MODULE = {
    "pydantic_settings": "pydantic-settings",
    "imageio_ffmpeg": "imageio-ffmpeg",
    "dateutil": "python-dateutil",
}

# import 문에는 안 나오지만 있어야 하는 것.
#   python-multipart — 참고 악보 업로드 라우트를 만들 때 FastAPI 가 직접 요구한다.
#                      없으면 앱이 import 단계에서 죽는다(실제로 확인).
INDIRECT = {"python-multipart"}


def _names(path: Path) -> set[str]:
    """requirements 파일에서 설치 이름만 뽑는다."""
    out: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        name = line.split("==")[0].split(">=")[0].split("[")[0].split("<")[0]
        out.add(name.strip().lower())
    return out


def _imported_modules() -> set[str]:
    """app 아래 코드가 실제로 import 하는 최상위 모듈 이름."""
    found: set[str] = set()
    for py in APP.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                found.add(node.module.split(".")[0])
    # scripts/ 안의 우리 모듈은 남의 것이 아니다(app/main.py 가 경로를 붙여 부른다).
    ours = {"app", "__future__"} | {f.stem for f in (ROOT / "scripts").glob("*.py")}
    return {m for m in found if m not in sys.stdlib_module_names and m not in ours}


def test_desktop_list_covers_everything_the_code_imports() -> None:
    """원장 PC 에서 ImportError 가 나면 프로그램이 아예 안 켜진다."""
    desktop = _names(DESKTOP)
    missing = {
        DIST_OF_MODULE.get(m, m)
        for m in _imported_modules()
        if DIST_OF_MODULE.get(m, m).lower() not in desktop
    }
    assert not missing, (
        f"코드가 import 하는데 원장 PC 목록에 없다: {sorted(missing)}. "
        "server/requirements-desktop.txt 에도 넣어라 — 안 그러면 학원 PC 에서만 안 켜진다."
    )


def test_desktop_list_is_a_subset_of_the_full_list() -> None:
    """두 목록이 따로 놀면 도커와 원장 PC 가 다른 프로그램이 된다."""
    extra = _names(DESKTOP) - _names(FULL) - INDIRECT
    assert not extra, f"원장 PC 목록에만 있는 것: {sorted(extra)} — requirements.txt 에도 넣어라"


def test_the_3d_toolkit_never_comes_back() -> None:
    """pianoplayer 는 vtk(내려받기 133MB · 설치 566MB)를 끌고 온다.

    운지는 app/analysis/teaching.py 가 직접 계산한다. 코드가 쓰지도 않는 3D 도구를
    학원 인터넷으로 내려받게 하면, 원장은 멈춘 것처럼 보이는 검은 창을 십수 분 본다.
    """
    heavy = {"pianoplayer", "vedo", "vtk"}
    assert not (heavy & _names(DESKTOP)), (
        "원장 PC 목록에 3D 시각화 도구가 다시 들어왔다 — 설치가 다시 느려진다"
    )
    assert "pianoplayer" not in " ".join(p.read_text(encoding="utf-8") for p in APP.rglob("*.py")), (
        "pianoplayer 를 실제로 쓰기 시작했다면 목록과 이 검사를 함께 고쳐라"
    )


def test_installer_uses_the_desktop_list() -> None:
    """목록을 만들어 두고 설치 스크립트가 안 쓰면 아무 소용이 없다."""
    text = (ROOT / "install.ps1").read_bytes().decode("utf-8-sig")
    assert "requirements-desktop.txt" in text
