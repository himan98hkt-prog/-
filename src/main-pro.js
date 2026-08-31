// Pro 진입점 — 라이선스가 Pro 이면 Supabase 동기화까지 켠다.
import './styles.css'
import { boot } from './ui/shell.js'
import { registerServiceWorker } from './pwa.js'

boot({ allowPro: true }).then(registerServiceWorker).catch((err) => {
  console.error(err)
  document.body.innerHTML = `<pre style="padding:20px;white-space:pre-wrap">앱을 시작하지 못했습니다.\n${err?.message || err}</pre>`
})
