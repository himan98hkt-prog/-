/**
 * 테마 색 대비 검사 — 새 테마를 넣을 때마다 돌린다.
 * 인쇄물은 화면보다 대비가 떨어져 보이므로 기준을 화면보다 높게 잡는다.
 */
import { readFileSync } from 'node:fs'
const src = readFileSync('lib/design/themes.ts', 'utf8')
const lum = (h) => {
  const v = h.replace('#', '')
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(v.slice(i, i + 2), 16) / 255)
  const l = (c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4)
  return 0.2126 * l(r) + 0.7152 * l(g) + 0.0722 * l(b)
}
const ct = (a, b) => {
  const [x, y] = [lum(a), lum(b)].sort((m, n) => n - m)
  return (x + 0.05) / (y + 0.05)
}
let bad = 0
let total = 0
for (const block of src.split('\n  {\n').slice(1)) {
  const id = block.match(/id: '([^']+)'/)?.[1]
  if (!id || !block.includes('palette')) continue
  const g = (k) => block.match(new RegExp(`${k}: '(#[0-9a-fA-F]{6})'`))?.[1]
  const p = { paper: g('paper'), ink: g('ink'), muted: g('muted'), accent: g('accent'), band: g('band'), bandInk: g('bandInk') }
  if (!p.paper) continue
  total += 1
  const checks = [
    ['ink/paper', ct(p.ink, p.paper), 7],
    ['muted/paper', ct(p.muted, p.paper), 3],
    ['accent/paper', ct(p.accent, p.paper), 3],
    ['bandInk/band', ct(p.bandInk, p.band), 4.5],
  ]
  const fail = checks.filter(([, v, m]) => v < m)
  if (fail.length) {
    bad += 1
    console.log(id.padEnd(20), fail.map(([n, v, m]) => `${n} ${v.toFixed(2)} < ${m}`).join('  |  '))
  }
}
console.log(bad ? `\n${total}종 중 ${bad}종 실패` : `${total}종 전부 통과`)
process.exit(bad ? 1 : 0)
