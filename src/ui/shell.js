// 앱 셸 — 헤더/탭/라우팅/로그인 커버.

import { h, $, clear, toast, modal } from './dom.js'
import { icon } from './icons.js'
import { applyBranding, branding, logoDataUrl, initialsOf } from './branding.js'
import * as repo from '../data/repo.js'
import { navFor, can, ROLES } from '../core/perm.js'
import { currentUser, login, logout, findByPin, autoLoginIfSolo } from './session.js'
import { openWizard } from './views/wizard.js'
import { requireActivation, entitlement, entitlementBadge } from './activation.js'
import { openKiosk } from './views/kiosk.js'

import * as today from './views/today.js'
import * as attendance from './views/attendance.js'
import * as students from './views/students.js'
import * as payments from './views/payments.js'
import * as timetable from './views/timetable.js'
import * as counsel from './views/counsel.js'
import * as expenses from './views/expenses.js'
import * as dashboard from './views/dashboard.js'
import * as settings from './views/settings.js'

const VIEWS = { today, attendance, students, payments, timetable, counsel, expenses, dashboard, settings }

export const app = {
  root: null,
  main: null,
  header: null,
  nav: null,
  rail: null,
  current: null,
  cleanup: null,
  allowPro: false,
  entitlement: null,
  sync: null
}

export async function boot({ allowPro = false } = {}) {
  app.allowPro = allowPro
  await repo.init()
  applyBranding()
  document.addEventListener('branding:changed', renderHeader)

  const ent = await requireActivation()
  repo.setPlan(ent.plan)
  app.entitlement = ent

  app.root = $('#app')
  clear(app.root)
  app.header = h('header', { class: 'app-header' })
  app.rail = h('nav', { class: 'app-rail', 'aria-label': '주요 메뉴' })
  app.main = h('main')
  app.nav = h('nav', { class: 'app-nav', 'aria-label': '주요 메뉴' })
  app.root.append(app.header, h('div', { class: 'app-body' }, app.rail, app.main), app.nav)

  if (!repo.getSetting('wizardDone')) {
    await openWizard()
  }

  autoLoginIfSolo()
  if (!currentUser()) {
    await showLogin()
  }

  if (allowPro && repo.getPlan() === 'pro') {
    startSync().catch((e) => console.warn('동기화 시작 실패', e))
  }

  window.addEventListener('hashchange', () => mount(location.hash.slice(1) || 'today'))
  renderHeader()
  renderNav()
  mount(location.hash.slice(1) || 'today')
}

export async function startSync() {
  const mod = await import('../data/sync.js')
  app.sync = mod
  await mod.start({ onStatus: renderHeader })
  return mod
}

export function renderHeader() {
  if (!app.header) return
  const b = branding()
  const user = currentUser()
  clear(app.header)

  const logo = b.logo
    ? h('img', { class: 'logo', src: b.logo, alt: '' })
    : h('div', { class: 'logo' }, initialsOf(b.name))

  const sync = app.sync?.status?.() || null
  const ent = app.entitlement || entitlement()
  const badge = entitlementBadge(ent)

  app.header.append(
    logo,
    h('div', { class: 'grow truncate' },
      h('div', { class: 'title truncate' }, b.name),
      h('div', { class: 'sub' },
        h('span', { class: `badge ${ent.mode === 'trial' ? 'warn' : 'brand'}` }, badge),
        user ? h('span', { class: 'truncate' }, `${user.name} · ${ROLES[user.role]?.label || user.role}`) : null,
        sync
          ? h('span', { class: 'row', style: { gap: '4px' } },
            h('span', { class: `sync-dot ${sync.online ? 'on' : 'off'}` }),
            h('span', {}, sync.pending ? `대기 ${sync.pending}` : '동기화됨'))
          : null
      )
    ),
    h('button', { class: 'hbtn', onClick: () => openKiosk(), title: '학생이 직접 출석 체크하는 화면' },
      icon('kiosk', { size: 17 }), h('span', { class: 'kiosk-label' }, '키오스크')),
    user
      ? h('button', {
        class: 'hbtn', title: '자리를 비울 때 잠급니다',
        onClick: async () => { logout(); location.reload() }
      }, icon('lock', { size: 17 }), h('span', { class: 'kiosk-label' }, '잠금'))
      : null
  )
}

export function renderNav() {
  const user = currentUser()
  const items = navFor(user?.role || 'owner')
  const primary = items.filter((n) => n.primary)
  const rest = items.filter((n) => !n.primary)

  // 데스크톱: 왼쪽 사이드바에 전부 펼친다
  clear(app.rail)
  app.rail.append(h('div', { class: 'rail-label' }, '메뉴'))
  for (const item of items) {
    if (item.id === 'timetable' && rest.length) {
      app.rail.append(h('div', { class: 'rail-label' }, '관리'))
    }
    app.rail.append(h('button', {
      class: app.current === item.id ? 'active' : '',
      dataset: { view: item.id },
      onClick: () => { location.hash = item.id }
    }, icon(item.icon, { size: 19 }), h('span', {}, item.label)))
  }

  // 모바일: 다섯 칸 + 더보기
  clear(app.nav)
  for (const item of primary) {
    app.nav.append(h('button', {
      class: app.current === item.id ? 'active' : '',
      dataset: { view: item.id },
      onClick: () => { location.hash = item.id }
    }, h('span', { class: 'ico' }, icon(item.icon, { size: 21 })), h('span', {}, item.label)))
  }
  if (rest.length) {
    const activeInRest = rest.some((n) => n.id === app.current)
    app.nav.append(h('button', {
      class: activeInRest ? 'active' : '',
      dataset: { view: 'more' },
      onClick: () => openMoreSheet(rest)
    }, h('span', { class: 'ico' }, icon('more', { size: 21 })), h('span', {}, '더보기')))
  }
}

/** 하단 탭에 들어가지 못한 메뉴 — 큰 글씨·설명과 함께 보여 준다 */
function openMoreSheet(items) {
  const list = h('div', {})
  const { close } = modal({ title: '메뉴', body: list, actions: [] })
  for (const item of items) {
    list.append(h('button', {
      class: 'list-row link',
      style: { width: '100%', border: 0, background: 'none', textAlign: 'left', cursor: 'pointer' },
      onClick: () => { close(); location.hash = item.id }
    },
      h('span', { class: 'todo-ico', style: { width: '38px', height: '38px' } }, icon(item.icon, { size: 19 })),
      h('span', { class: 'grow' },
        h('b', {}, item.label),
        h('div', { class: 'small muted' }, item.desc || '')),
      icon('chevronRight', { size: 18 })))
  }
}

export async function mount(viewId) {
  const user = currentUser()
  const allowed = navFor(user?.role || 'owner').map((n) => n.id)
  const id = allowed.includes(viewId) ? viewId : allowed[0]
  const view = VIEWS[id]
  if (!view) return
  app.cleanup?.()
  app.cleanup = null
  app.current = id
  renderNav()
  clear(app.main)
  const container = h('section', { class: 'view' })
  app.main.append(container)
  app.main.scrollTop = 0
  try {
    app.cleanup = await view.render(container, { user, repo, can: (a) => can(user?.role || 'owner', a) })
  } catch (err) {
    console.error(err)
    container.append(h('div', { class: 'card' }, h('p', {}, '화면을 여는 중 오류가 발생했습니다.'), h('pre', { class: 'small muted' }, String(err?.message || err))))
  }
}

export function refresh() {
  mount(app.current || 'attendance')
}

// ── 로그인 (PIN) ────────────────────────────────────────────
export function showLogin() {
  return new Promise((resolve) => {
    const b = branding()
    let pin = ''
    const dots = h('div', { class: 'pin-dots' })
    const msg = h('div', { class: 'small muted center', style: { minHeight: '20px' } }, 'PIN 4자리를 입력하세요')

    const update = () => { dots.textContent = '●'.repeat(pin.length) + '○'.repeat(Math.max(0, 4 - pin.length)) }

    const tryLogin = () => {
      const user = findByPin(pin)
      if (!user) {
        msg.textContent = 'PIN 이 올바르지 않습니다'
        msg.className = 'small center'
        msg.style.color = 'var(--danger)'
        pin = ''
        update()
        return
      }
      login(user, { remember: repo.getPlan() !== 'pro' })
      cover.remove()
      resolve(user)
    }

    const press = (d) => {
      if (pin.length >= 4) return
      pin += d
      update()
      if (pin.length === 4) setTimeout(tryLogin, 120)
    }

    const pad = h('div', { class: 'pin-pad' },
      ...['1', '2', '3', '4', '5', '6', '7', '8', '9'].map((d) => h('button', { onClick: () => press(d) }, d)),
      h('button', { onClick: () => { pin = ''; update() } }, '↺'),
      h('button', { onClick: () => press('0') }, '0'),
      h('button', { onClick: () => { pin = pin.slice(0, -1); update() } }, '←')
    )

    const cover = h('div', { class: 'cover' },
      h('div', { class: 'panel card' },
        h('div', { class: 'center', style: { flexDirection: 'column', gap: '8px', marginBottom: '14px' } },
          h('img', { src: logoDataUrl(192), style: { width: '64px', height: '64px', borderRadius: '16px' }, alt: '' }),
          h('h2', { style: { margin: '4px 0 0' } }, b.name),
          h('div', { class: 'small muted' }, '학원 관리노트')
        ),
        dots, msg,
        h('div', { style: { height: '10px' } }),
        pad,
        h('div', { class: 'small muted center', style: { marginTop: '12px' } }, '처음이신가요? 기본 PIN 은 0000 입니다')
      )
    )
    update()
    document.body.append(cover)
  })
}

export { toast }
