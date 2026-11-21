// 서비스 워커 등록 — 오프라인 사용(Lite 는 완전 오프라인)이 제품의 전제라 필수.
export function registerServiceWorker() {
  if (!('serviceWorker' in navigator)) return
  if (import.meta.env?.DEV) return // 개발 중에는 캐시가 방해된다
  if (location.protocol !== 'https:' && location.hostname !== 'localhost') return
  window.addEventListener('load', () => {
    navigator.serviceWorker.register(new URL('./sw.js', import.meta.url), { type: 'module', scope: './' })
      .catch((err) => console.warn('서비스 워커 등록 실패', err))
  })
}
