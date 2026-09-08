// 인쇄 — 출석부·수납대장처럼 "종이로 보관해야 하는" 표를 A4 로 뽑는다.
//
// 새 창을 여는 대신 현재 문서에 인쇄 전용 블록을 잠깐 붙였다가 지운다.
// (팝업 차단·PWA 독립창에서도 동작하고, 브랜드 색·글꼴을 그대로 쓴다)

import { h } from './dom.js'
import { branding } from './branding.js'
import { toYmd } from '../core/date.js'

/**
 * @param {{title:string, subtitle?:string, headers:string[], rows:Array<Array<string|number>>, footer?:string}} spec
 */
export function printTable(spec) {
  const b = branding()
  const node = h('div', { class: 'print-only', id: 'print-area' },
    h('div', { style: { marginBottom: '8px' } },
      h('h2', { style: { margin: '0 0 2px' } }, `${b.name || '학원'} — ${spec.title}`),
      h('div', { style: { fontSize: '11px', color: '#555' } },
        [spec.subtitle, `출력일 ${toYmd()}`].filter(Boolean).join(' · '))),
    h('table', { class: 'print-table' },
      h('thead', {}, h('tr', {}, ...spec.headers.map((x) => h('th', {}, String(x))))),
      h('tbody', {}, ...spec.rows.map((r) => h('tr', {}, ...r.map((c) => h('td', {}, c === null || c === undefined ? '' : String(c))))))),
    spec.footer ? h('div', { style: { marginTop: '8px', fontSize: '11px' } }, spec.footer) : null
  )

  document.body.append(node)
  const cleanup = () => { node.remove(); window.removeEventListener('afterprint', cleanup) }
  window.addEventListener('afterprint', cleanup)
  window.print()
  // afterprint 를 주지 않는 브라우저 대비 (모바일 사파리)
  setTimeout(cleanup, 4000)
  return node
}
