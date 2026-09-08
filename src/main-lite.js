// Lite 진입점 — 완전 오프라인. Supabase 모듈은 번들에도 포함되지 않는다.
import './styles.css'
import { boot } from './ui/shell.js'
import { registerServiceWorker } from './pwa.js'

boot({ allowPro: false }).then(registerServiceWorker).catch((err) => {
  console.error(err)
  document.body.innerHTML = `<pre style="padding:20px;white-space:pre-wrap">앱을 시작하지 못했습니다.\n${err?.message || err}</pre>`
})
