# -*- coding: utf-8 -*-
"""집 PC 설치기 — 원장님이 두 번 눌러 쓰는 것.

여기서 막히면 **제품을 아예 못 써 보신다.** 그런데 설치기는 성질상 검사하기
어렵다 — 진짜로 돌리면 venv 를 만들고 인터넷에서 받아 온다. 그래서 돌려 보지
않고도 틀린 것을 알 수 있는 것들만 못 박는다.

제일 중요한 것은 `NEEDED` 다. 설치기는 이 목록이 전부 import 되면 **내려받기를
통째로 건너뛴다.** 나중에 누가 requirements.txt 에 새 의존성을 넣고 이 목록에
안 더하면, 설치기가 "다 있다"고 판단해 지나가고 **프로그램이 import 에서
죽는다.** 그 고장은 원장님 PC 에서만 보인다.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import setup as S   # noqa: E402

MR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 파이썬 패키지 이름과 import 이름이 다른 것들.
# python-multipart 는 판에 따라 둘이라 설치기가 NEEDED_EITHER 로 따로 본다.
IMPORT_NAME = {'python-multipart': 'python_multipart'}


def skip_names():
    """설치기가 「다 깔렸나」를 볼 때 쓰는 이름 전부."""
    names = set(S.NEEDED)
    for group in S.NEEDED_EITHER:
        names.update(group)
    return names

# 돌리는 데는 필요 없고 개발·시험에만 쓰는 것. 설치기가 안 봐도 된다.
DEV_ONLY = {'pytest', 'httpx2'}


def requirements():
    """requirements.txt 의 패키지 이름들."""
    path = os.path.join(MR, 'requirements.txt')
    out = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.split('#')[0].strip()
            if not line:
                continue
            out.append(re.split(r'[<>=!~\[]', line)[0].strip())
    return out


def test_the_requirements_file_is_readable():
    assert requirements(), 'requirements.txt 에서 아무것도 못 읽었습니다'


def test_every_runtime_dependency_is_in_the_skip_check():
    """**이 검사가 제일 중요하다.**

    새 의존성을 넣고 `NEEDED` 에 안 더하면 설치기가 "다 깔려 있다"고 보고
    내려받기를 건너뛴다. 그러면 원장님 PC 에서 import 에러로 죽는다.
    새 의존성을 넣을 때 `NEEDED` 에 더하거나, 개발용이면 `DEV_ONLY` 에 넣어라.
    """
    missed = []
    for pkg in requirements():
        if pkg in DEV_ONLY:
            continue
        mod = IMPORT_NAME.get(pkg, pkg)
        if mod not in skip_names():
            missed.append(f'{pkg} (import {mod})')
    assert missed == [], (
        'requirements.txt 에 있는데 설치기의 NEEDED 에 없습니다: '
        + ', '.join(missed))


def test_the_skip_check_does_not_list_things_we_do_not_install():
    """반대 방향 — 안 까는 것을 기다리면 설치기가 매번 다시 받는다."""
    known = {IMPORT_NAME.get(p, p) for p in requirements()}
    known.update(n for g in S.NEEDED_EITHER for n in g)   # 별칭은 통과
    assert set(S.NEEDED) <= known, (
        'NEEDED 에 있는데 requirements.txt 에 없습니다: '
        + ', '.join(sorted(set(S.NEEDED) - known)))


def test_those_modules_really_import():
    """목록에 적은 이름이 실제 import 이름인지. 오타면 영영 건너뛰지 못한다."""
    import importlib
    for mod in S.NEEDED:
        importlib.import_module(mod)


def test_at_least_one_alias_works_for_each_either_group():
    """판이 바뀌어 **둘 다** 안 되면 설치기가 매번 다시 받는다."""
    import importlib
    for group in S.NEEDED_EITHER:
        ok = False
        for name in group:
            try:
                importlib.import_module(name)
                ok = True
                break
            except Exception:
                pass
        assert ok, f'{group} 중 되는 것이 하나도 없습니다'


def test_the_probe_code_is_valid_python():
    """설치기가 만들어 넘기는 검사 코드 자체가 문법에 맞아야 한다."""
    compile(S._probe_code(), '<probe>', 'exec')


# --------------------------------------------------------------------------
# 두 번 눌러 실행하는 파일들
# --------------------------------------------------------------------------

def test_both_launchers_exist():
    for name in ('install-windows.bat', 'install-mac.command'):
        assert os.path.exists(os.path.join(MR, name)), f'{name} 이 없습니다'


def test_the_mac_launcher_is_executable():
    """실행 권한이 없으면 맥에서 두 번 눌러도 아무 일이 안 일어난다."""
    path = os.path.join(MR, 'install-mac.command')
    assert os.access(path, os.X_OK), 'chmod +x 가 안 돼 있습니다'


def test_the_launchers_point_at_the_setup_script():
    for name in ('install-windows.bat', 'install-mac.command'):
        with open(os.path.join(MR, name), encoding='utf-8') as f:
            body = f.read()
        assert 'setup.py' in body, f'{name} 이 setup.py 를 안 부릅니다'


def test_windows_launcher_prefers_the_py_launcher():
    """윈도우에서 `python` 은 파이썬이 없을 때 Microsoft Store 를 연다.

    그러면 "있다"고 착각해 넘어가고, 다음 줄에서 알 수 없는 말로 죽는다.
    `py -3` 는 없으면 깨끗하게 실패한다.
    """
    with open(os.path.join(MR, 'install-windows.bat'), encoding='utf-8') as f:
        body = f.read()
    assert body.index('py -3') < body.index('python --version')


def test_the_windows_launcher_says_to_tick_add_to_path():
    """이걸 빠뜨린 설치가 제일 흔한 실패다 — 깔았는데 못 찾는다."""
    with open(os.path.join(MR, 'install-windows.bat'), encoding='utf-8') as f:
        body = f.read()
    assert 'Add python.exe to PATH' in body


# --------------------------------------------------------------------------
# 설치기가 보는 자리
# --------------------------------------------------------------------------

def test_the_venv_python_path_matches_the_platform():
    p = S.venv_python()
    assert p.startswith(S.VENV)
    assert ('Scripts' in p) if os.name == 'nt' else ('bin' in p)


def test_the_venv_and_catalog_are_not_committed():
    """원장님 PC 안에서만 의미가 있는 것들. 저장소에 들어가면 안 된다."""
    with open(os.path.join(MR, '.gitignore'), encoding='utf-8') as f:
        ignored = f.read()
    assert '.venv/' in ignored
    assert 'catalog/' in ignored


def test_the_minimum_python_is_not_lower_than_music21_needs():
    assert S.MIN_PY >= (3, 10), 'music21 9 는 3.10 이상이 필요합니다'
