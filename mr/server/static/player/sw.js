/* 서비스워커 — 지시서 모듈 ⑤-1 "오프라인 재생. 타협 불가."
 *
 *   "학원·연주홀 와이파이는 믿을 수 없다. 다운로드 후 로컬 재생."
 *
 * 앱 껍데기와 곡 목록, 반주 MIDI 를 캐시한다. MIDI 는 한 곡에 1 KB 안팎이라
 * 카탈로그 전체를 넣어도 수십 KB 다. mp3 였다면 한 곡에 600 KB 라 불가능하다.
 */
// v2 — 미리 받는 주소에 편성(style·level)이 붙었다. v1 캐시에는 편성 없는 주소만
// 들어 있어 영영 맞지 않으므로, 버전을 올려 activate 에서 통째로 지운다.
// v3 — 디자인을 새로 했다. tokens.css 가 늘었고, 목록에 안 넣으면 **오프라인에서
// 색이 통째로 빠진 화면**이 뜬다. 버전을 올려야 이미 깔린 기기가 새로 받아 간다.
const VERSION = 'mr-player-v4';

// 이 워커가 놓인 폴더. 경로를 박아 두면 안 된다 — 원장님은 도메인 루트에 올릴 수도,
// `/반주/` 같은 하위 폴더에 올릴 수도 있다. 그때마다 껍데기가 오프라인에서 안 뜨면
// 「타협 불가」라던 ⑤-1 이 무너진다.
const SCOPE = new URL('./', self.location.href).pathname;
const SHELL = `${VERSION}-shell`;
const DATA = `${VERSION}-data`;
const MIDI = `${VERSION}-midi`;

const SHELL_FILES = [
  './', './index.html', './tokens.css', './player.css',
  './manifest.webmanifest', './icon.svg',
  './js/app.js', './js/engine.js', './js/midi.js', './js/synth.js', './js/store.js',
];

self.addEventListener('install', (e) => {
  e.waitUntil((async () => {
    const c = await caches.open(SHELL);
    await c.addAll(SHELL_FILES);
    self.skipWaiting();
  })());
});

self.addEventListener('activate', (e) => {
  e.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter((k) => !k.startsWith(VERSION)).map((k) => caches.delete(k)));
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET') return;

  // 반주 MIDI — 한 번 받으면 바뀌지 않는다. 캐시 우선.
  // `startsWith` 가 아니라 `includes` 인 이유는 위 SCOPE 와 같다 — 하위 폴더에
  // 올리면 경로 앞에 그 폴더가 붙는다.
  if (url.pathname.includes('/api/player/midi/')) {
    e.respondWith(cacheFirst(e.request, MIDI));
    return;
  }
  // 곡 목록 — 새 것이 있으면 받고, 없으면 캐시로.
  if (url.pathname.includes('/api/player/bundle')) {
    e.respondWith(networkFirst(e.request, DATA));
    return;
  }
  // 앱 껍데기 — 이 워커의 폴더 안이면 전부
  if (url.origin === self.location.origin && url.pathname.startsWith(SCOPE)) {
    e.respondWith(cacheFirst(e.request, SHELL));
  }
});

async function cacheFirst(req, cacheName) {
  const c = await caches.open(cacheName);
  const hit = await c.match(req, { ignoreSearch: false });
  if (hit) return hit;
  try {
    const res = await fetch(req);
    if (res.ok) c.put(req, res.clone());
    return res;
  } catch (err) {
    // 정확히 그 편성은 없지만 같은 곡의 다른 편성은 있는 경우. 조용히 바꿔치기하면
    // 화면과 소리가 어긋나므로, 헤더로 알려 준다 (화면이 안내 문구를 띄운다).
    const loose = await c.match(req, { ignoreSearch: true });
    if (loose) {
      const h = new Headers(loose.headers);
      h.set('X-MR-Fallback', 'default');
      return new Response(await loose.blob(), {
        status: loose.status, statusText: loose.statusText, headers: h,
      });
    }
    throw err;
  }
}

async function networkFirst(req, cacheName) {
  const c = await caches.open(cacheName);
  try {
    const res = await fetch(req);
    if (res.ok) c.put(req, res.clone());
    return res;
  } catch (err) {
    const hit = await c.match(req, { ignoreSearch: true });
    if (hit) return hit;
    throw err;
  }
}

/* 화면에서 "오프라인 준비"를 누르면 곡 전체를 미리 받아 둔다.
 *
 * 곡 목록(bundle)도 반드시 여기서 같이 받는다. 첫 방문 때는 서비스워커가 아직
 * 페이지를 잡기 전이라 목록 요청이 워커를 안 거치고 지나갈 수 있다. 그러면
 * 오프라인에서 목록이 뜨는 건 브라우저 HTTP 캐시 운이지 우리 설계가 아니다.
 */
self.addEventListener('message', (e) => {
  if (!e.data || e.data.type !== 'precache') return;
  const urls = e.data.urls || [];
  e.waitUntil((async () => {
    const data = await caches.open(DATA);
    for (const u of (e.data.data || [])) {
      try {
        const res = await fetch(u, { cache: 'reload' });
        if (res.ok) await data.put(u, res.clone());
      } catch (err) { /* 목록을 못 받아도 곡은 계속 받는다 */ }
    }
    const c = await caches.open(MIDI);
    let done = 0;
    for (const u of urls) {
      try {
        const res = await fetch(u, { cache: 'reload' });
        if (res.ok) await c.put(u, res.clone());
      } catch (err) { /* 한 곡 실패해도 나머지는 계속 */ }
      done++;
      if (done % 5 === 0 || done === urls.length) {
        (await self.clients.matchAll()).forEach((cl) =>
          cl.postMessage({ type: 'precache-progress', done, total: urls.length }));
      }
    }
    (await self.clients.matchAll()).forEach((cl) =>
      cl.postMessage({ type: 'precache-done', total: urls.length }));
  })());
});
