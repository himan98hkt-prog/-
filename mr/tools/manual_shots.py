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

# 화성 확인 화면을 찍을 곡 — 34마디에 「확인 필요」 칸이 실제로 있다
VERIFY_SHOT_SONG = 'bach_bwv846_prelude'

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



def stage_progress(st) -> None:
    """설명서 그림용으로 **작업이 진행 중인 카탈로그**를 만든다.

    갓 만든 카탈로그는 26곡 전부 「확인 대기」라 진척 막대가 0%다. 그 그림으로는
    카탈로그 화면이 무슨 일을 하는지 설명서가 못 보여 준다. 그래서 사본에
    절반쯤 해 둔 상태를 만든다 — **사본에서만** 한다.

    카탈로그 화면과 같은 차례(교재→난이도)로 앞쪽부터 확인한다. 실제로도 교재
    한 권씩 훑지, 쉬운 곡만 골라 다니지 않는다. 덕분에 카탈로그 표와 플레이어
    곡 목록 둘 다 위쪽에 「완료」가 섞여 나온다.

    다만 화성 확인 화면을 찍을 바흐 전주곡은 **일부러 남겨 둔다.** 확인이 끝난
    곡을 열면 머리말이 「확인 완료됨」인데 화면은 「확인 필요 12곳」이라 말한다 —
    설명서 그림 한 장이 두 말을 하게 된다.

    검수 시간은 마디 수에서 뽑는다(90초 + 마디×13초) — 손으로 적은 숫자가 아니라
    곡 길이에서 나오게 해야 평균·남은 시간 어림이 그럴듯하게 맞는다.
    """
    rows = [s for s in sorted(st.catalog.songs.values(),
                              key=lambda x: (x.book, x.level, x.id))
            if s.id != VERIFY_SHOT_SONG]
    for song in rows[:len(rows) // 2]:
        st.save_harmony(song.id, [], add_seconds=90 + song.measures * 13,
                        verified=True)


async def shoot(base: str, out: str, pkg_base: str):
    from playwright.async_api import async_playwright

    os.makedirs(out, exist_ok=True)
    made = []

    async with async_playwright() as p:
        launch = {'args': ['--no-sandbox', '--autoplay-policy=no-user-gesture-required']}
        if CHROME:
            launch['executable_path'] = CHROME
        b = await p.chromium.launch(**launch)

        async def snap(page, name, full=False):
            # 전체 페이지로 찍으면 `position:sticky` 머리말이 **두 번** 그려진다
            # (제자리에 한 번, 스크롤 끝에 한 번). 화면은 멀쩡한데 설명서 그림만
            # 고장 난 것처럼 보인다. 찍는 동안만 붙박이를 풀어 둔다.
            fix = None
            if full:
                fix = await page.add_style_tag(
                    content='.top{position:static !important}')
            path = os.path.join(out, f'mr-{name}.png')
            await page.screenshot(path=path, full_page=full)
            if fix is not None:
                await fix.evaluate('e => e.remove()')
            made.append(name)
            print(f'  ✓ mr-{name}.png')

        # --- 제작용 화면 (우리 쪽 도구) ---------------------------------
        desk = await b.new_context(viewport=DESK, device_scale_factor=2)
        pg = await desk.new_page()

        await pg.goto(f'{base}/')
        await pg.wait_for_selector('table, .empty', timeout=30_000)
        await pg.wait_for_timeout(1400)      # 진척 막대가 끝까지 자라게 (1.1초)
        await snap(pg, '20-카탈로그')

        # 8마디짜리 연습곡을 찍으면 화면 아래 2/3 가 빈 채로 설명서에 실린다.
        # 34마디에 「확인 필요」 칸이 실제로 있는 곡을 골라, 이 화면이 하는 일
        # (사람이 노란 칸을 훑는다)이 그림 한 장에 보이게 한다.
        await pg.goto(f'{base}/static/verify.html?id={VERIFY_SHOT_SONG}')
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

        # 멈춘 화면에서는 눈금도 화음도 페이드아웃 단추도 다 잠들어 있다.
        # 카운트인 1마디를 지나 2마디째가 울릴 때 찍어야 이 화면이 설명된다.
        await pg.locator('#play').click()
        try:
            await pg.wait_for_function(
                "() => Number(document.querySelector('#barno').textContent) >= 2",
                timeout=15_000)
        except Exception:
            await pg.wait_for_timeout(2_500)   # 소리가 안 나는 환경이면 그냥 기다린다
        await snap(pg, '31-플레이어-연주', full=True)
        await pg.locator('#play').click()      # 다음 그림을 위해 멈춘다
        await pg.wait_for_timeout(200)

        await pg.locator('#loopBtn').click()
        await pg.wait_for_selector('#loopCard:not([hidden])', timeout=10_000)
        await pg.wait_for_timeout(200)
        await snap(pg, '32-구간반복', full=True)

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

    # 카탈로그는 **사본**에서 찍는다. 원본을 건드리면 다음에 돌릴 때 그림이 달라지고,
    # 무엇보다 남의 작업 카탈로그에 명단과 가짜 검수 기록을 남기게 된다.
    sys.path.insert(0, ROOT)
    from piano_mr import store
    work = tempfile.mkdtemp(prefix='manual-catalog-')
    # 카탈로그 화면 머리말에 이 경로의 끝 두 칸이 그대로 뜬다. 임시 폴더 이름이
    # 설명서 그림에 박히지 않게, 원장님 컴퓨터에 있을 법한 이름으로 한 겹 감싼다.
    shot_catalog = os.path.join(work, '피아노반주', 'catalog')
    shutil.copytree(args.catalog, shot_catalog)

    st = store.CatalogStore(shot_catalog)
    st.import_roster(roster_blob())   # 발표회 큐가 실제 이름으로 나오게
    stage_progress(st)

    pkg = tempfile.mkdtemp(prefix='manual-pkg-')
    st.export_static(pkg, academy='아첼 음악학원')

    api_port, pkg_port = free_port(), free_port()
    procs = [
        serve([sys.executable, 'serve.py', '--catalog', shot_catalog,
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
        shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
