/**
 * 내려받는 자리에 남은 옛 첨부물을 치운다.
 *
 * 파일 이름을 한글로 두었더니 깃허브가 한글을 통째로 지워 「-.exe」 로 올라갔다.
 * 이름을 영문으로 고친 뒤에도 옛것은 그 자리에 남는다 — 원장님이 목록에서
 * 「-.exe」와 「PianoEvent-Setup-Windows.exe」 둘을 보고 무엇을 눌러야 할지
 * 망설이시게 된다. 받는 자리에는 받을 것 하나만 있어야 한다.
 *
 *   node scripts/clean-release-assets.mjs
 *   환경변수: GH_TOKEN (필수) · REPO (owner/name, 필수) · TAG (기본 installer-latest)
 *
 * 지우는 것은 **지금 상품 이름으로 시작하지 않는 첨부물**뿐이다. 지킬 이름은 상품 이름
 * 한 자리(`desktop/brand.js`)에서 가져온다 — 예전에는 여기에 「PianoEvent-」 라고 적어
 * 두었는데, 상품 이름을 바꾸자 **새로 올린 설치본을 옛것으로 보고 지워 버렸다.**
 * 빌드는 전부 성공인데 받는 자리에는 옛 파일만 남아 있었다.
 *
 * 그래서 지우기 전에 **새것이 실제로 올라와 있는지 먼저 본다.** 하나도 없으면
 * 올리기가 실패한 것이므로 아무것도 지우지 않는다 — 받는 자리가 비는 것이 가장 나쁘다.
 */
import { createRequire } from 'node:module'

const BRAND = createRequire(import.meta.url)('../desktop/brand.js')
/** 지킬 이름 — 지금 상품의 설치본 (예: RecitalManager-…) */
const KEEP = `${BRAND.slug}-`

const token = process.env.GH_TOKEN
const repo = process.env.REPO
const tag = process.env.TAG || 'installer-latest'
if (!token || !repo) {
  console.error('GH_TOKEN 과 REPO 가 있어야 합니다')
  process.exit(1)
}

const api = `https://api.github.com/repos/${repo}`
const headers = {
  Authorization: `Bearer ${token}`,
  Accept: 'application/vnd.github+json',
  'X-GitHub-Api-Version': '2022-11-28',
}

const res = await fetch(`${api}/releases/tags/${tag}`, { headers })
if (res.status === 404) {
  console.log(`${tag} 판올림 표가 아직 없습니다 — 치울 것도 없습니다`)
  process.exit(0)
}
if (!res.ok) {
  console.error(`판올림 표를 읽지 못했습니다 (${res.status})`)
  process.exit(1)
}

const release = await res.json()
const assets = release.assets ?? []
const keep = assets.filter((a) => a.name.startsWith(KEEP))
const stale = assets.filter((a) => !a.name.startsWith(KEEP))

if (keep.length === 0) {
  console.log(`「${KEEP}」 로 시작하는 설치본이 하나도 없습니다 — 올리기가 안 된 것으로 보고 아무것도 지우지 않습니다`)
  process.exit(0)
}
console.log(`지킬 것 ${keep.length}개: ${keep.map((a) => a.name).join(', ')}`)
if (stale.length === 0) {
  console.log('치울 옛 첨부물이 없습니다')
  process.exit(0)
}

for (const asset of stale) {
  const del = await fetch(`${api}/releases/assets/${asset.id}`, { method: 'DELETE', headers })
  console.log(`${del.ok ? '치웠습니다' : `못 치웠습니다 (${del.status})`} · ${asset.name}`)
}
