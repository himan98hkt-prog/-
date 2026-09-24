# -*- coding: utf-8 -*-
"""반주 프로그램을 **혼자 서는 제품**으로 빼낸다.

관리노트와 따로 파는 물건이므로, 나가는 꾸러미에 관리노트가 한 조각도
섞이면 안 됩니다. 다행히 `mr/` 는 처음부터 바깥을 참조하지 않게 써 왔습니다 —
명단은 **파일로** 받고(연동이 켜져 있든 아니든 프로그램은 돕니다), 인증키는
같은 키를 **인정**할 뿐 관리노트 코드를 부르지 않습니다.

그래서 이 도구가 하는 일은 베껴 담는 것보다 **빼는 것**에 가깝습니다.

    python3 tools/standalone.py ../dist/피아노반주 --zip

무엇이 빠지나

    tests/ bench.py Makefile pytest.ini   개발용. 구매자에게 필요 없고,
                                          pytest 같은 걸 깔라고 하게 된다
    catalog/                              우리 작업물. 구매자는 설치기가
                                          넣어 주는 연습곡 20곡으로 시작한다
    .venv/ __pycache__/ *.pyc             기계가 만든 것

무엇이 들어가나 — 나머지 전부. 엔진·카탈로그·화성 확인 화면·플레이어·
PDF 올리기·발표회 운영·설치기, 그리고 구매자가 읽을 `읽어보세요.txt`.
"""
import argparse
import os
import shutil
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
MR = os.path.dirname(HERE)
HANDOVER = os.path.join(HERE, 'handover')

# 폴더 통째로 뺀다
DROP_DIRS = {'tests', 'catalog', '.venv', '__pycache__', '.pytest_cache',
             'node_modules', '.git'}
# 파일 하나씩 뺀다 (개발용). `README.md` 도 여기 있다 — 우리가 읽는 글이라
# 「지시서 9장」이며 테스트 건수며 관리노트 연동 이야기가 그대로 들어 있다.
# 구매자가 받는 꾸러미에 그게 섞이면 안 된다. 구매자는 `읽어보세요.txt` 를 읽는다.
DROP_FILES = {'bench.py', 'Makefile', 'pytest.ini', 'conftest.py', 'README.md'}
DROP_SUFFIX = ('.pyc', '.pyo', '.rev')

# 이것들이 없으면 제품이 아니다. 베낀 뒤에 확인한다.
MUST_HAVE = (
    'mr.py', 'serve.py', 'catalog_cli.py', 'seed_catalog.py',
    'requirements.txt', 'install-windows.bat', 'install-mac.command',
    'piano_mr/harmony.py', 'piano_mr/orchestration.py', 'piano_mr/render.py',
    'piano_mr/score_loader.py', 'piano_mr/provenance.py',
    'server/app.py', 'server/static/player/index.html',
    'server/static/player/js/app.js', 'server/static/player/sw.js',
    'tools/setup.py', 'tools/single_file.py',
    'fixtures/scores/p05_waltz_c.musicxml',
    'repertoire/competition.json',
)

# 관리노트 쪽 파일 이름이 섞여 들어오지 않았는지 보는 그물. 코드 의존은 원래
# 없지만, 앞으로 누가 실수로 끌어다 놓는 것을 여기서 잡는다.
FOREIGN = ('academy-note', 'supabase', 'package.json', 'vite.config',
           'src/main.js', 'scripts/shots.mjs')


class BuildError(Exception):
    pass


def wanted(rel, dev=False):
    """이 상대경로를 제품에 넣나."""
    parts = rel.split(os.sep)
    if any(p in DROP_DIRS for p in parts if not (dev and p == 'tests')):
        return False
    if parts[-1] in DROP_FILES and not dev:
        return False
    if rel.endswith(DROP_SUFFIX):
        return False
    return True


def copy_tree(src, dst, dev=False):
    keep = DROP_DIRS - {'tests'} if dev else DROP_DIRS
    made = []
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in keep]
        for name in files:
            full = os.path.join(root, name)
            rel = os.path.relpath(full, src)
            if not wanted(rel, dev):
                continue
            target = os.path.join(dst, rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(full, target)
            made.append(rel)
    return made


README = """피아노학원 자동 반주 프로그램
==============================

악보를 넣으면 **곡의 화성을 자동으로 분석해** 오케스트라 반주를 만들어 줍니다.
만든 반주는 아이가 폰·태블릿으로 열어 연습하고, 발표회 당일에는 무대 화면으로
순서대로 틀 수 있습니다.


처음 시작하기
-------------

  윈도       install-windows.bat  을 두 번 누르세요
  맥·리눅스  install-mac.command  을 두 번 누르세요

처음 한 번만 1~3분 걸리고, 그 다음부터는 2초면 뜹니다. 끝나면 브라우저가
알아서 열립니다. 연습곡 20곡이 들어 있어 빈 화면으로 시작하지 않습니다.

  곡 목록·반주 만들기   http://127.0.0.1:8765/
  아이가 연습하는 화면   http://127.0.0.1:8765/static/player/
  발표회 운영 화면       http://127.0.0.1:8765/static/program.html

깔아야 하는 것은 **파이썬 하나뿐**입니다. 없으면 설치 창이 어디서 받는지
알려 드립니다. 그때 「Add python.exe to PATH」를 꼭 체크하세요.


폰·태블릿에서 열기
------------------

  install-phone-windows.bat  (맥은 install-phone-mac.command)

두 번 누르면 주소가 뜹니다. 같은 와이파이에 있는 폰 브라우저에 그대로 치면
곡 목록이 나옵니다.

아이 집에서도 열리게 하시려면 꾸러미를 웹호스팅에 올리시면 됩니다.

  python3 catalog_cli.py package ../반주 --zip

나온 압축 파일을 웹호스팅 파일관리자에 올리고 그 자리에서 푸세요.
주소가 https 여야 아이 폰이 곡을 저장해 두고 인터넷 없이도 재생합니다.


설치 없이 들어만 보시려면
-------------------------

  python3 tools/single_file.py ../반주 -o 들어보기.html

파일 하나가 나옵니다. 두 번 누르면 바로 열리고, 곡이 전부 그 안에 들어
있어서 인터넷도 설치도 필요 없습니다. 다만 **들어 보는 용도**입니다 —
악보를 넣어 새 반주를 만드는 것은 위의 제작 화면이 합니다.


알아 두실 것
------------

**나가는 소리에는 원곡 피아노가 없습니다. 반주만 나옵니다.** 피아노는 아이가
칩니다. 원곡이 섞여 있으면 아이가 녹음된 피아노와 겹쳐 치게 되어 연습이
되지 않습니다. 확인용으로 피아노를 섞어 들으시려면 `--mix full` 을 쓰세요.

**악보는 들어 있지 않습니다.** 저작권이 끝난 곡이라도 그 악보를 컴퓨터에
쳐 넣은 사람의 조건이 따로 붙습니다. 어디서 받는지와 무엇을 조심해야 하는지는
사용설명서의 「악보는 어디서 구하나」 절에 정리해 두었습니다.

**mp3·wav 로 구워 내실 때만** fluidsynth 와 ffmpeg 가 필요합니다. 반주를
만들고 브라우저에서 듣는 데에는 필요 없습니다.

  맥      brew install fluid-synth ffmpeg
  우분투  sudo apt-get install fluidsynth ffmpeg fluid-soundfont-gm


지울 때
-------

`.venv` 폴더와 `catalog` 폴더를 지우시면 됩니다.
"""


def hand_over(out):
    """집 PC 에서 이어서 개발하실 수 있게 — 문서와 git 을 같이 넣는다.

    `CLAUDE.md` 가 핵심이다. 새 대화를 그 폴더에서 열면 먼저 읽으므로,
    「절대 하지 말 것」이 사람의 기억이 아니라 **파일**에 남는다.
    """
    for name in ('CLAUDE.md', '인수인계.md'):
        shutil.copy2(os.path.join(HANDOVER, name), os.path.join(out, name))
    shutil.copy2(os.path.join(HANDOVER, 'gitignore.txt'),
                 os.path.join(out, '.gitignore'))


def git_start(out):
    """첫 커밋까지 만들어 둔다. 없으면 첫날 실수가 되돌릴 수 없다."""
    import subprocess
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0')
    def run(*args):
        return subprocess.run(('git',) + args, cwd=out, env=env,
                              capture_output=True, text=True)
    if run('init', '-q', '-b', 'main').returncode != 0:
        return '(git 이 없어 저장소는 못 만들었습니다)'
    run('config', 'user.name', '반주 개발')
    run('config', 'user.email', 'dev@localhost')
    run('add', '-A')
    r = run('commit', '-q', '-m',
            '반주 프로그램 분리 — 관리노트에서 떼어낸 첫 상태\n\n'
            '개발지시서 1~5단계 구현분. 파이썬 545건 · 브라우저 11항목 × 3배치.\n'
            '무엇을 하면 안 되는지는 CLAUDE.md, 남은 일은 인수인계.md 에 있다.')
    return 'git 저장소 · 첫 커밋 완료' if r.returncode == 0 else '(첫 커밋 실패)'


def build(out, source=MR, zip_it=False, dev=False, handover=False):
    out = os.path.abspath(out)
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out)

    made = copy_tree(source, out, dev)

    for need in MUST_HAVE:
        if not os.path.exists(os.path.join(out, need.replace('/', os.sep))):
            raise BuildError(f'제품에 빠진 것이 있습니다: {need}')

    stray = [r for r in made if any(f in r.replace(os.sep, '/') for f in FOREIGN)]
    if stray:
        raise BuildError(f'관리노트 쪽 파일이 섞였습니다: {stray[:3]}')

    with open(os.path.join(out, '읽어보세요.txt'), 'w', encoding='utf-8') as f:
        f.write(README)

    info_git = ''
    if handover:
        hand_over(out)
        info_git = git_start(out)

    total = sum(os.path.getsize(os.path.join(r, n))
                for r, _, fs in os.walk(out) for n in fs)
    info = {'out': out, 'files': len(made) + 1, 'bytes': total, 'zip': '',
            'git': info_git}

    if zip_it:
        zpath = out + '.zip'
        if os.path.exists(zpath):
            os.remove(zpath)
        base = os.path.basename(out)
        with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
            for root, _, files in os.walk(out):
                for name in files:
                    full = os.path.join(root, name)
                    # 압축 안에 제품 폴더가 한 겹 있어야 한다 — 바탕화면에서
                    # 풀었을 때 파일 수백 개가 흩어지지 않게.
                    z.write(full, os.path.join(
                        base, os.path.relpath(full, out)))
        info['zip'] = zpath
    return info


def main(argv=None):
    ap = argparse.ArgumentParser(
        description='반주 프로그램만 독립 제품으로 빼낸다 (관리노트 없이)')
    ap.add_argument('out', help='만들 폴더 (예: ../dist/피아노반주)')
    ap.add_argument('--zip', action='store_true', help='압축까지 만든다')
    ap.add_argument('--handover', action='store_true',
                    help='집 PC 에서 이어서 개발하실 묶음 — 개발용 + CLAUDE.md '
                         '+ 인수인계.md + git 첫 커밋')
    ap.add_argument('--with-dev', action='store_true',
                    help='개발용도 같이 (tests·README·Makefile). '
                         '**파는 꾸러미에는 쓰지 마세요**')
    args = ap.parse_args(argv)

    try:
        info = build(args.out, zip_it=args.zip,
                     dev=args.with_dev or args.handover,
                     handover=args.handover)
    except BuildError as e:
        print(e, file=sys.stderr)
        return 2

    print(f"  {info['out']}")
    print(f"  파일 {info['files']}개 · {info['bytes'] / 1024 / 1024:.1f} MB")
    if info['zip']:
        print(f"  압축: {info['zip']}  "
              f"({os.path.getsize(info['zip']) / 1024 / 1024:.1f} MB)")
    print('  관리노트는 한 조각도 들어가지 않았습니다.')
    if info['git']:
        print(f"  {info['git']}")
    if args.with_dev or args.handover:
        print('  ⚠ 개발용이 들어 있습니다 — 파실 꾸러미는 이 옵션 없이 만드세요.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
