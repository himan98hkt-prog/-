// 앱 셸 캐시 — 네트워크 우선(최신 배포 반영) + 실패 시 캐시(오프라인).
const CACHE = 'academy-note-v1'

self.addEventListener('install', (e) => {
  self.skipWaiting()
  e.waitUntil(caches.open(CACHE))
})

self.addEventListener('activate', (e) => {
  e.waitUntil((async () => {
    for (const key of await caches.keys()) if (key !== CACHE) await caches.delete(key)
    await self.clients.claim()
  })())
})

self.addEventListener('fetch', (e) => {
  const req = e.request
  if (req.method !== 'GET') return
  const url = new URL(req.url)
  if (url.origin !== location.origin) return // Supabase 등 API 는 그대로 통과
  e.respondWith((async () => {
    const cache = await caches.open(CACHE)
    try {
      const res = await fetch(req)
      if (res.ok) cache.put(req, res.clone())
      return res
    } catch {
      const hit = await cache.match(req)
      if (hit) return hit
      if (req.mode === 'navigate') {
        const shell = await cache.match('./index.html') || await cache.match('./')
        if (shell) return shell
      }
      throw new Error('offline')
    }
  })())
})
