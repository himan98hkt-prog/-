# -*- coding: utf-8 -*-
"""사용설명서에 넣을 반주 화면을 캡처한다.

손으로 찍으면 다음에 화면이 바뀌었을 때 **설명서만 조용히 낡는다.** 그래서
스크립트로 남긴다 — 화면이 바뀌면 다시 돌리기만 하면 된다.

    python3 tools/manual_shots.py --catalog catalog --out ../screenshots

관리노트 쪽 화면은 `scripts/shots.mjs piano` 가 찍는다. 이쪽은 반주만 맡는다.
"""
import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
CHROME = os.environ.get('CHROME_PATH', '')

DESK = {'width': 1280, 'height': 900}
PHONE = {'width': 420, 'height': 880}


def roster_blob() -> bytes:
    """설명서 그림에 쓸 학생 명단 — 관리노트가 내보낸 모양 그대로."""
    names = ['김지우', '박서준', '이하은', '정도윤', '최서아',
             '강민준', '윤채원', '임시우', '한지호', '오예린']
    return json.dumps({
        'format': 'academy-note-piano-roster', 'version': 1,
        'academy': '아첼 음악학원',
        'students': [{'id': f's{i + 1}', 'name': n, 'class': '월수금 4시',
                      'active': True} for i, n in enumerate(names)],
    }, ensure_ascii=False).encode()


async def shoot(base: str, out: str, pkg_base: str):
    from playwright.async_api import async_playwright

    os.makedirs(out, exist_ok=True)
    made = []

    async with async_playwright() as p:
        launch = {'args': ['--no-sandbox', '--autoplay-policy=no-user-gesture-required']}
        if CHROME:
            launch['executable_path'] = CHROME
        b = await p.chromium.launch(**launch)

        async def snap(page, name):
            path = os.path.join(out, f'mr-{name}.png')
            await page.screenshot(path=path)
            made.append(name)
            print(f'  ✓ mr-{name}.png')

        # --- 제작용 화면 (우리 쪽 도구) ---------------------------------
        desk = await b.new_context(viewport=DESK, device_scale_factor=2)
        pg = await desk.new_page()

        await pg.goto(f'{base}/')
        await pg.wait_for_selector('table, .empty', timeout=30_000)
        await pg.wait_for_timeout(400)
        await snap(pg, '20-카탈로그')

        await pg.goto(f'{base}/static/verify.html?id=p05_waltz_c')
        await pg.wait_for_selector('.bar', timeout=30_000)
        await pg.wait_for_timeout(600)
        await snap(pg, '21-화성확인')

        await pg.goto(f'{base}/static/upload.html')
        await pg.wait_for_selector('.stat', timeout=30_000)
        await pg.wait_for_timeout(400)
        await snap(pg, '22-PDF올리기')

        await pg.goto(f'{base}/static/program.html')
        await pg.wait_for_selector('.stage, .queue, .empty', timeout=30_000)
        await pg.wait_for_timeout(1200)      # 무대 조명 애니메이션이 자리 잡게
        await snap(pg, '23-발표회운영')
        await desk.close()

        # --- 원장님이 쓰는 화면 (정적 꾸러미 그대로) ----------------------
        phone = await b.new_context(viewport=PHONE, device_scale_factor=2)
        pg = await phone.new_page()

        await pg.goto(f'{pkg_base}/')
        await pg.wait_for_selector('.row', timeout=30_000)
        await pg.wait_for_timeout(400)
        await snap(pg, '30-플레이어-곡목록')

        await pg.locator('[data-song="p05_waltz_c"]').click()
        await pg.wait_for_selector('#dur', timeout=30_000)
        await pg.wait_for_function(
            "() => document.querySelector('#dur').textContent !== '0:00'",
            timeout=30_000)
        await pg.wait_for_timeout(300)
        await pg.screenshot(path=os.path.join(out, 'mr-31-플레이어-연주.png'),
                            full_page=True)
        made.append('31-플레이어-연주')
        print('  ✓ mr-31-플레이어-연주.png')

        await pg.locator('#loopBtn').click()
        await pg.wait_for_selector('#loopCard:not([hidden])', timeout=10_000)
        await pg.wait_for_timeout(200)
        await pg.screenshot(path=os.path.join(out, 'mr-32-구간반복.png'),
                            full_page=True)
        made.append('32-구간반복')
        print('  ✓ mr-32-구간반복.png')

        await pg.goto(f'{pkg_base}/#/program?i=0')
        await pg.wait_for_selector('.queue .row', timeout=30_000)
        await pg.wait_for_timeout(400)
        await snap(pg, '33-발표회큐')
        await phone.close()
        await b.close()

    return made


def serve(cmd, cwd, port):
    return subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.DEVNULL,
                            stderr=subprocess.STDOUT)


def main() -> int:
    from player_check import free_port, wait_for

    ap = argparse.ArgumentParser(description='설명서용 반주 화면 캡처')
    ap.add_argument('--catalog', default=os.path.join(ROOT, 'catalog'))
    ap.add_argument('--out', default=os.path.join(os.path.dirname(ROOT), 'screenshots'))
    args = ap.parse_args()

    if not os.path.exists(os.path.join(args.catalog, 'catalog.json')):
        print(f'카탈로그가 없습니다: {args.catalog} '
              '(python3 seed_catalog.py --catalog ... 먼저)', file=sys.stderr)
        return 2

    # 명단을 넣어 두면 발표회 큐가 실제 이름으로 나온다 (설명서 그림이 현실과 같게)
    sys.path.insert(0, ROOT)
    from piano_mr import store
    st = store.CatalogStore(args.catalog)
    if not st.roster.loaded:
        st.import_roster(roster_blob())

    pkg = tempfile.mkdtemp(prefix='manual-pkg-')
    st.export_static(pkg, academy='아첼 음악학원')

    api_port, pkg_port = free_port(), free_port()
    procs = [
        serve([sys.executable, 'serve.py', '--catalog', args.catalog,
               '--port', str(api_port), '--host', '127.0.0.1'], ROOT, api_port),
        serve([sys.executable, '-m', 'http.server', str(pkg_port),
               '--bind', '127.0.0.1'], pkg, pkg_port),
    ]
    try:
        base = f'http://127.0.0.1:{api_port}'
        pkg_base = f'http://127.0.0.1:{pkg_port}'
        wait_for(f'{base}/api/stats')
        wait_for(f'{pkg_base}/api/player/bundle')
        made = asyncio.run(shoot(base, args.out, pkg_base))
        print(f'\n{len(made)}장을 {args.out} 에 저장했습니다.')
    finally:
        for p in procs:
            p.terminate()
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()
        shutil.rmtree(pkg, ignore_errors=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
