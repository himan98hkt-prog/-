// 아주 작은 DOM 헬퍼 — 프레임워크 없이도 화면 코드가 읽히도록 하는 최소 도구.

export function h(tag, props = {}, ...children) {
  const node = document.createElement(tag)
  for (const [k, v] of Object.entries(props || {})) {
    if (v == null || v === false) continue
    if (k === 'class') node.className = v
    else if (k === 'style' && typeof v === 'object') Object.assign(node.style, v)
    else if (k === 'html') node.innerHTML = v
    else if (k.startsWith('on') && typeof v === 'function') node.addEventListener(k.slice(2).toLowerCase(), v)
    else if (k === 'dataset') Object.assign(node.dataset, v)
    else if (k in node && k !== 'list') node[k] = v
    else node.setAttribute(k, v)
  }
  for (const c of children.flat(3)) {
    if (c == null || c === false) continue
    node.append(c instanceof Node ? c : document.createTextNode(String(c)))
  }
  return node
}

export const $ = (sel, root = document) => root.querySelector(sel)
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)]

export function clear(node) {
  while (node.firstChild) node.firstChild.remove()
  return node
}

export function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))
}

export function debounce(fn, ms = 200) {
  let t
  const wrapped = (...args) => {
    clearTimeout(t)
    t = setTimeout(() => fn(...args), ms)
  }
  wrapped.cancel = () => clearTimeout(t)
  return wrapped
}

let toastTimer
export function toast(msg, kind = 'info') {
  let box = $('#toast')
  if (!box) {
    box = h('div', { id: 'toast', class: 'toast' })
    document.body.append(box)
  }
  box.textContent = msg
  box.className = `toast show ${kind}`
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => (box.className = 'toast'), 2600)
}

export function modal({ title, body, actions = [], wide = false, onClose }) {
  const backdrop = h('div', { class: 'modal-backdrop' })
  const close = () => {
    backdrop.remove()
    document.removeEventListener('keydown', onKey)
    onClose?.()
  }
  const onKey = (e) => { if (e.key === 'Escape') close() }
  document.addEventListener('keydown', onKey)

  const footer = h('div', { class: 'modal-actions' },
    actions.map((a) =>
      h('button', {
        class: `btn ${a.kind || ''}`,
        onClick: async () => {
          const r = await a.onClick?.(close)
          if (r !== false && a.keepOpen !== true) close()
        }
      }, a.label)
    )
  )
  const card = h('div', { class: `modal ${wide ? 'wide' : ''}` },
    h('div', { class: 'modal-head' },
      h('h3', {}, title),
      h('button', { class: 'icon-btn', onClick: close, 'aria-label': '닫기', title: '닫기' },
        h('span', { style: { fontSize: '18px', lineHeight: '1' } }, '×'))
    ),
    h('div', { class: 'modal-body' }, body),
    actions.length ? footer : null
  )
  backdrop.append(card)
  backdrop.addEventListener('click', (e) => { if (e.target === backdrop) close() })
  document.body.append(backdrop)
  return { close, card }
}

export function confirmDialog(message, { title = '확인', okLabel = '확인', danger = false } = {}) {
  return new Promise((resolve) => {
    modal({
      title,
      body: h('p', { class: 'muted' }, message),
      actions: [
        { label: '취소', onClick: () => resolve(false) },
        { label: okLabel, kind: danger ? 'danger' : 'primary', onClick: () => resolve(true) }
      ],
      onClose: () => resolve(false)
    })
  })
}

export function field(label, control, hint) {
  return h('label', { class: 'field' }, h('span', { class: 'field-label' }, label), control, hint ? h('small', { class: 'muted' }, hint) : null)
}

export function copyText(text) {
  if (navigator.clipboard?.writeText) return navigator.clipboard.writeText(text)
  const ta = h('textarea', { value: text, style: { position: 'fixed', opacity: '0' } })
  document.body.append(ta)
  ta.select()
  document.execCommand('copy')
  ta.remove()
  return Promise.resolve()
}
