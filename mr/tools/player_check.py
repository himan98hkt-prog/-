# -*- coding: utf-8 -*-
"""플레이어 PWA 를 진짜 브라우저에서 돌려 본다 (지시서 모듈 ⑤ 검증).

파이썬 테스트로는 서버가 맞는 걸 주는지까지만 볼 수 있다. 정작 중요한 건
**브라우저가 그걸로 소리를 내는가** 이고, 그건 크로미움을 띄워야 알 수 있다.

    python3 tools/player_check.py --catalog catalog

오프라인 검사는 브라우저의 오프라인 흉내(`set_offline`)에 기대지 않는다. 그건
페이지의 요청만 막고 **서비스워커 안에서 부르는 fetch 는 그대로 나간다** — 그래서
캐시가 비어 있어도 통과해 버린다. 여기서는 서버 프로세스를 아예 내린 뒤에 본다.

검사 항목:
  1. 곡 목록이 뜨고 반주 MIDI 를 받아 길이를 계산한다
  2. 실제로 소리가 난다 (AnalyserNode 로 RMS 측정)
  3. 템포를 바꾸면 다시 받지 않고 그 자리에서 빨라진다
  4. 서버를 내리고 HTTP 캐시를 지워도 전곡 목록이 뜨고 재생된다
  5. 화면에 쓰인 그 편성으로 재생된다 (엉뚱한 편성으로 바꿔치기하지 않는다)
"""
import argparse
import asyncio
import importlib.util
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME = os.environ.get('CHROME_PATH', '')

# 진짜 소리가 나는지 재 본다. `play()` 가 AudioContext 를 처음 만들기 때문에
# 계측기(AnalyserNode)는 재생을 시작한 **뒤에** 물려야 한다.
# 검사 스크립트들이 쓸 주소 해석기. **앱과 같은 규칙**(`data-api` + `baseURI`)
# 이다. 여기에 `/api/…` 를 박아 두면 도메인 루트에 올린 경우에만 맞고,
# `도메인/반주/` 같은 하위 폴더에서는 404 HTML 을 받아 "MIDI 파일이 아닙니다"
# 로 터진다 — 실제로 그렇게 터졌고, 그때까지 하위 폴더는 검사된 적이 없었다.
# 페이지가 열리기 전에 심어야 하므로 `add_init_script` 로 넣는다.
API_INIT = """window.API = (u) => new URL(
    u, new URL(document.documentElement.dataset.api || '/', document.baseURI)).href;"""

PROBE_JS = """async (id) => {
    const { Player } = await import('./js/engine.js');
    const pl = new Player();
    const r = await fetch(API('api/player/midi/' + id));
    pl.load(await r.arrayBuffer(), { bpm: 96, countInBars: 0 });
    pl.play(0);
    const an = pl.ctx.createAnalyser(); an.fftSize = 2048;
    pl.synth.master.connect(an);
    const buf = new Float32Array(an.fftSize);
    let peak = 0;
    for (let i = 0; i < 12; i++) {
        await new Promise((x) => setTimeout(x, 150));
        an.getFloatTimeDomainData(buf);
        let s = 0; for (const v of buf) s += v * v;
        peak = Math.max(peak, Math.sqrt(s / buf.length));
    }
    pl.stop();
    return { peak: +peak.toFixed(4), online: navigator.onLine };
}"""


# ⑤-4 카운트인을 이어폰으로만. 출력이 둘로 갈렸는지 양쪽에서 동시에 재 본다.
CUE_JS = """async (id) => {
    const { Player } = await import('./js/engine.js');
    if (!Player.canRouteCue) return { supported: false };
    try { await navigator.mediaDevices.getUserMedia({ audio: true }); } catch (e) { /* 라벨용 */ }
    const outs = (await navigator.mediaDevices.enumerateDevices())
        .filter((d) => d.kind === 'audiooutput' && d.deviceId && d.deviceId !== 'default');
    if (!outs.length) return { supported: false };
    const pl = new Player();
    const r = await fetch(API('api/player/midi/' + id));
    pl.load(await r.arrayBuffer(), { bpm: 96, countInBars: 2 });
    if (!await pl.setCueOutput(outs[0].deviceId)) return { supported: false };
    pl.play(0);
    const mainAn = pl.ctx.createAnalyser(); mainAn.fftSize = 2048;
    pl.synth.master.connect(mainAn);
    const cueAn = pl.cueCtx.createAnalyser(); cueAn.fftSize = 2048;
    pl.cueSynth.master.connect(cueAn);
    const rms = (an) => { const b = new Float32Array(an.fftSize);
        an.getFloatTimeDomainData(b); let s = 0; for (const v of b) s += v * v;
        return Math.sqrt(s / b.length); };
    const win = async (ms) => { let m = 0, c = 0; const end = performance.now() + ms;
        while (performance.now() < end) { await new Promise((x) => setTimeout(x, 60));
            m = Math.max(m, rms(mainAn)); c = Math.max(c, rms(cueAn)); }
        return { main: +m.toFixed(4), cue: +c.toFixed(4) }; };
    const during = await win(3400);      // 카운트인 2마디 (3/4, ♩=96) = 3.75초
    const after = await win(2500);       // 반주가 시작된 뒤
    pl.stop();
    return { supported: true, device: outs[0].label, during, after };
}"""


# ⑤-2 페이드아웃. `setTargetAtTime` 은 지수라 영원히 0 에 닿지 않는다 — 연주홀에서
# -60 dB 는 무음이 아니다. 진짜 0 이 되는 시각을 잰다.
FADE_JS = """async (id) => {
    const { Player, FADE_SECONDS } = await import('./js/engine.js');
    const pl = new Player();
    const r = await fetch(API('api/player/midi/' + id));
    pl.load(await r.arrayBuffer(), { bpm: 96, countInBars: 0 });
    pl.play(0);
    const an = pl.ctx.createAnalyser(); an.fftSize = 2048;
    pl.synth.master.connect(an);
    const rms = () => { const b = new Float32Array(an.fftSize);
        an.getFloatTimeDomainData(b); let s = 0; for (const v of b) s += v * v;
        return Math.sqrt(s / b.length); };
    await new Promise((x) => setTimeout(x, 1500));
    const before = rms();
    const t0 = performance.now();
    pl.fadeOut();
    let silent = null;
    while (performance.now() - t0 < 8000) {
        await new Promise((x) => setTimeout(x, 30));
        if (rms() < 0.0005) { silent = (performance.now() - t0) / 1000; break; }
    }
    pl.stop();
    return { limit: FADE_SECONDS, before: +before.toFixed(4), silent };
}"""


def free_port() -> int:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def wait_for(url: str, timeout: float = 60.0) -> None:
    import urllib.error
    import urllib.request
    end = time.time() + timeout
    while time.time() < end:
        try:
            urllib.request.urlopen(url, timeout=2).read()
            return
        except (urllib.error.URLError, OSError):
            time.sleep(0.3)
    raise RuntimeError(f'서버가 안 떴습니다: {url}')


def sw_version() -> str:
    src = open(os.path.join(ROOT, 'server/static/player/sw.js'), encoding='utf-8').read()
    return re.search(r"const VERSION = '([^']+)'", src).group(1)


async def open_song(page, song_id: str) -> str:
    await page.locator(f'[data-song="{song_id}"]').click()
    await page.wait_for_selector('#dur', timeout=30_000)
    await page.wait_for_function(
        "() => document.querySelector('#dur').textContent !== '0:00'", timeout=30_000)
    return await page.locator('#dur').inner_text()


async def check(base: str, song_id: str, stop_server) -> None:
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        launch = {'args': [
            '--no-sandbox', '--autoplay-policy=no-user-gesture-required',
            # 출력 장치를 둘 이상 만들어 준다 — ⑤-4 (카운트인만 이어폰으로) 검사용
            '--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream']}
        if CHROME:
            launch['executable_path'] = CHROME
        b = await p.chromium.launch(**launch)
        ctx = await b.new_context(viewport={'width': 420, 'height': 880},
                                  permissions=['microphone'])
        await ctx.add_init_script(API_INIT)
        pg = await ctx.new_page()
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))

        await pg.goto(base)
        await pg.wait_for_selector('.row', timeout=30_000)
        songs = await pg.locator('[data-song]').count()
        assert songs > 0, '곡 목록이 비었습니다'
        print(f'[1] 곡 목록 {songs}곡')

        dur = await open_song(pg, song_id)
        print(f'[2] 반주를 읽음 · 길이 {dur}')

        rms = (await pg.evaluate(PROBE_JS, song_id))['peak']
        assert rms > 0.01, f'소리가 안 납니다 (RMS {rms})'
        print(f'[3] 소리 남 · 최대 RMS {rms}')

        # 템포는 다시 받지 않고 바뀌어야 한다 (지시서 ⑤-2 "실시간")
        slow, fast = await pg.evaluate("""async (id) => {
            const { Player } = await import('./js/engine.js');
            const pl = new Player();
            const r = await fetch(API('api/player/midi/' + id));
            pl.load(await r.arrayBuffer(), { bpm: 60, countInBars: 0 });
            const a = pl.totalSeconds;
            pl.setTempo(120);
            return [a, pl.totalSeconds];
        }""", song_id)
        assert slow > fast * 1.8, f'템포를 바꿔도 길이가 그대로입니다 ({slow} → {fast})'
        print(f'[4] ♩=60 {slow:.1f}초 → ♩=120 {fast:.1f}초 (다시 받지 않음)')

        # ⑤-2 "3초 안에 반주만 사라짐" — 이 버튼 하나가 원장님 마음을 산다
        fade = await pg.evaluate(FADE_JS, song_id)
        assert fade['before'] > 0.01, '페이드 전에 소리가 없었습니다'
        assert fade['silent'] is not None, '페이드아웃이 완전한 무음에 닿지 않습니다'
        assert fade['silent'] <= fade['limit'] + 0.4, \
            f"페이드아웃이 {fade['silent']:.2f}초 걸립니다 (기준 {fade['limit']}초)"
        print(f"[5] 페이드아웃 — 완전 무음까지 {fade['silent']:.2f}초 "
              f"(기준 {fade['limit']}초)")

        # 오프라인 준비 (지시서 ⑤-1 "타협 불가")
        await pg.wait_for_function(
            "() => navigator.serviceWorker.controller !== null", timeout=30_000)
        await pg.goto(base)
        await pg.wait_for_selector('#offline')
        await pg.locator('#offline').click()
        await pg.wait_for_selector('#toast', timeout=30_000)
        await pg.wait_for_function(
            "() => document.querySelector('#toast').textContent.includes('오프라인 준비 완료')",
            timeout=180_000)
        version = sw_version()
        cached = await pg.evaluate("""async () => {
            const out = {};
            for (const n of await caches.keys())
                out[n] = (await (await caches.open(n)).keys()).map((r) => r.url);
            return out;
        }""")
        data = cached.get(f'{version}-data', [])
        assert any('/api/player/bundle' in u for u in data), \
            '곡 목록이 서비스워커 캐시에 없습니다 (브라우저 HTTP 캐시에 기대면 안 됩니다)'
        midi = cached.get(f'{version}-midi', [])
        assert len(midi) >= songs, f'반주 캐시가 모자랍니다 ({len(midi)}/{songs})'
        # 곡마다 **재생할 때 부르는 바로 그 주소**가 캐시에 있어야 한다.
        #   서버 배포 : /api/player/midi/<곡>?style=..&level=..  (쿼리로 편성을 지정)
        #   정적 배포 : /api/player/midi/<곡>[__<편성>_<두께>]    (편성마다 파일이 따로)
        # 어느 쪽이든, 미리 받은 주소와 재생하는 주소가 다르면 오프라인에서 엉뚱한
        # 편성이 조용히 나온다. 모양만 다를 뿐 지켜야 할 성질은 같다.
        info = await pg.evaluate(
            "async () => { const b = await (await fetch(API('api/player/bundle'))).json();"
            " return { static: !!b.static, ids: b.songs.map((s) => s.id),"
            " urls: b.songs.flatMap((s) => s.variants ? s.variants.map((v) => v.url) : []) }; }")
        ids, is_static = info['ids'], info['static']
        if is_static:
            missing = [u for u in info['urls']
                       if not any(c.endswith(u) for c in midi)]
            assert not missing, f'꾸러미에 있는데 캐시에 없는 반주: {missing[:3]}'
        else:
            missing = [i for i in ids if not any(f'/midi/{i}?' in u for u in midi)]
            assert not missing, f'편성이 붙은 주소가 없는 곡: {missing[:3]}'
        where = '정적 꾸러미' if is_static else '서버'
        print(f'[6] 오프라인 준비 — 목록 1 · 반주 {len(ids)}곡 ({where} · 주소까지 일치)')

        # 서버를 **내린다**. 브라우저의 오프라인 흉내는 서비스워커 안의 fetch 를
        # 막지 못해서, 캐시가 비어 있어도 통과해 버린다.
        stop_server()
        cdp = await ctx.new_cdp_session(pg)
        await cdp.send('Network.clearBrowserCache')
        await ctx.set_offline(True)
        print('[7] 서버 종료 + HTTP 캐시 삭제 — 남은 건 서비스워커 캐시뿐')

        pg2 = await ctx.new_page()
        pg2.on('pageerror', lambda e: errs.append('오프라인 ' + str(e)))
        await pg2.goto(base, wait_until='domcontentloaded')
        await pg2.wait_for_selector('.row', timeout=30_000)
        off = await pg2.locator('[data-song]').count()
        assert off == songs, f'오프라인에서 곡이 줄었습니다 ({off}/{songs})'

        res = await pg2.evaluate(PROBE_JS, song_id)
        assert res['peak'] > 0.01, f"오프라인에서 소리가 안 납니다 (RMS {res['peak']})"
        print(f"[8] 서버 없이 {off}곡 · 재생 RMS {res['peak']}")

        # 기본 편성은 **정확히 그 주소**가 캐시에 있어야 한다. 대충 맞는 걸로
        # 대신 주면 화면엔 「실내악」인데 스피커에선 기본 편성이 나온다.
        await open_song(pg2, song_id)
        swapped = await pg2.evaluate(
            "() => document.querySelector('#toast').textContent.includes('기본 편성')")
        assert not swapped, '요청한 편성이 캐시에 없어 기본 편성으로 바뀌었습니다'
        print('[9] 화면에 쓰인 그 편성 그대로 재생')

        # 없는 편성을 부르면 조용히 바꿔치기하지 말고 알려 줘야 한다
        told = await pg2.evaluate("""async (id) => {
            const r = await fetch(API(`api/player/midi/${id}?style=march&level=rich`));
            return { ok: r.ok, fb: r.headers.get('X-MR-Fallback') };
        }""", song_id)
        assert told['ok'] and told['fb'] == 'default', \
            f'캐시에 없는 편성을 말없이 내줬습니다: {told}'
        print('[10] 캐시에 없는 편성은 기본 편성으로 대신하되 헤더로 알림')

        # ⑤-4 "이어폰으로 원장님만 듣기" — 딸깍 소리와 반주가 다른 데로 나가야 한다
        cue = await pg2.evaluate(CUE_JS, song_id)
        assert cue['supported'], 'setSinkId 를 지원하지 않는 브라우저입니다'
        assert cue['during']['cue'] > 0.002, \
            f"이어폰에서 카운트인이 안 들립니다 ({cue['during']})"
        assert cue['during']['main'] < 0.002, \
            f"카운트인이 스피커로 샙니다 ({cue['during']})"
        assert cue['after']['main'] > 0.01, \
            f"스피커로 반주가 안 나옵니다 ({cue['after']})"
        print(f"[11] 카운트인 이어폰 {cue['during']['cue']} · 그때 스피커 "
              f"{cue['during']['main']} → 반주는 스피커 {cue['after']['main']}")

        assert not errs, f'자바스크립트 오류: {errs}'
        await b.close()
    print('\n플레이어 PWA 검사 통과 — 서버가 죽어도 반주가 나옵니다.')


def main() -> int:
    ap = argparse.ArgumentParser(description='플레이어 PWA 브라우저 검사')
    ap.add_argument('--catalog', default=os.path.join(ROOT, 'catalog'))
    ap.add_argument('--song', default='p05_waltz_c', help='재생해 볼 곡 id')
    ap.add_argument('--port', type=int, default=0)
    ap.add_argument('--static', metavar='폴더',
                    help='정적 꾸러미를 **평범한 정적 서버**로 띄워 검사한다 '
                         '(MR 서버 없이 — 원장님 배포 형태 그대로)')
    ap.add_argument('--subfolder', metavar='이름', nargs='?', const='반주',
                    help='도메인 루트가 아니라 **하위 폴더**에 올린 것처럼 검사한다 '
                         '(웹호스팅의 실제 모습: 도메인/반주/). 기본 이름이 한글인 '
                         '것은 일부러다 — 주소에 한글이 들어가는 쪽이 실제이고 '
                         '깨질 수 있는 쪽이다')
    args = ap.parse_args()

    if importlib.util.find_spec('playwright') is None:
        print('playwright 가 없습니다: pip install playwright && '
              'python3 -m playwright install chromium', file=sys.stderr)
        return 2
    if not args.static and not os.path.exists(
            os.path.join(args.catalog, 'catalog.json')):
        print(f'카탈로그가 없습니다: {args.catalog} '
              '(python3 seed_catalog.py --catalog ... 먼저)', file=sys.stderr)
        return 2

    port = args.port or free_port()
    sub = ''
    if args.static:
        # 파이썬 반주 서버가 아니라 **아무 파일이나 내주는 서버**다. 원장님 홈페이지와
        # 같은 조건이다 — 여기서 통과하면 원장님 PC 에 파이썬이 필요 없다는 뜻이다.
        base_dir = os.path.abspath(args.static)
        if not os.path.exists(os.path.join(base_dir, 'api', 'player', 'bundle')):
            print(f'정적 꾸러미가 아닙니다: {base_dir} '
                  '(catalog_cli.py package 로 먼저 만드세요)', file=sys.stderr)
            return 2
        if args.subfolder:
            # 꾸러미를 건드리지 않고 **그 위에 한 겹** 씌운다. 심볼릭 링크라
            # 파일을 복사하지 않는다 — 원본이 곧 검사 대상이다.
            holder = tempfile.mkdtemp(prefix='mr-sub-')
            link = os.path.join(holder, args.subfolder)
            os.symlink(base_dir, link)
            base_dir, sub = holder, args.subfolder
        srv = subprocess.Popen(
            [sys.executable, '-m', 'http.server', str(port), '--bind', '127.0.0.1'],
            cwd=base_dir, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    else:
        srv = subprocess.Popen(
            [sys.executable, 'serve.py', '--catalog', args.catalog,
             '--port', str(port), '--host', '127.0.0.1'],
            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

    def stop_server():
        if srv.poll() is None:
            srv.terminate()
            try:
                srv.wait(timeout=10)
            except subprocess.TimeoutExpired:
                srv.kill()
                srv.wait(timeout=5)

    try:
        base = f'http://127.0.0.1:{port}'
        if args.static:
            # 주소에 한글이 들어가면 브라우저가 퍼센트 인코딩해서 보낸다.
            # 그 상태에서도 상대경로가 제자리를 찾는지가 이 검사의 요점이다.
            here = f'{base}/{urllib.parse.quote(sub)}/' if sub else f'{base}/'
            wait_for(here + 'api/player/bundle')
            asyncio.run(check(here, args.song, stop_server))
        else:
            wait_for(f'{base}/api/stats')
            asyncio.run(check(f'{base}/static/player/', args.song, stop_server))
    finally:
        stop_server()
    return 0


if __name__ == '__main__':
    sys.exit(main())
