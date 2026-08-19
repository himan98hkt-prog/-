// 앱 셸 — 헤더/탭/라우팅/로그인 커버.

import { h, $, clear, toast } from './dom.js'
import { applyBranding, branding, logoDataUrl, initialsOf } from './branding.js'
import * as repo from '../data/repo.js'
import { navFor, can, ROLES } from '../core/perm.js'
import { currentUser, login, logout, findByPin, autoLoginIfSolo } from './session.js'
import { openWizard } from './views/wizard.js'
import { openKiosk } from './views/kiosk.js'

import * as attendance from './views/attendance.js'
import * as students from './views/students.js'
import * as payments from './views/payments.js'
import * as timetable from './views/timetable.js'
import * as counsel from './views/counsel.js'
import * as expenses from './views/expenses.js'
import * as dashboard from './views/dashboard.js'
import * as settings from './views/settings.js'

const VIEWS = { attendance, students, payments, timetable, counsel, expenses, dashboard, settings }

export const app = {
  root: null,
  main: null,
  header: null,
  nav: null,
  current: null,
  cleanup: null,
  allowPro: false,
  sync: null
}

export async function boot({ allowPro = false } = {}) {
  app.allowPro = allowPro
  await repo.init()
  applyBranding()
  document.addEventListener('branding:changed', renderHeader)

  app.root = $('#app')
  clear(app.root)
  app.header = h('header', { class: 'app-header' })
  app.main = h('main')
  app.nav = h('nav', { class: 'app-nav' })
  app.root.append(app.header, app.main, app.nav)

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

  window.addEventListener('hashchange', () => mount(location.hash.slice(1) || 'attendance'))
  renderHeader()
  renderNav()
  mount(location.hash.slice(1) || 'attendance')
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
    ? h('img', { class: 'logo', src: b.logo, alt: b.name })
    : h('div', { class: 'logo center', style: { fontWeight: '700', fontSize: '13px' } }, initialsOf(b.name))

  const syncState = app.sync?.status?.() || null
  app.header.append(
    logo,
    h('div', { class: 'grow truncate' },
      h('div', { class: 'title truncate' }, b.name),
      h('div', { class: 'sub' },
        `${repo.getPlan() === 'pro' ? 'Pro' : 'Lite'}${user ? ` · ${user.name}(${ROLES[user.role]?.label || user.role})` : ''}`,
        syncState ? h('span', { style: { marginLeft: '6px' } },
          h('span', { class: `sync-dot ${syncState.online ? 'on' : 'off'}` }),
          syncState.pending ? ` 대기 ${syncState.pending}` : ' 동기화됨') : null
      )
    ),
    h('button', { class: 'hbtn', onClick: () => openKiosk() }, '키오스크'),
    user ? h('button', {
      class: 'hbtn',
      onClick: async () => { logout(); location.reload() }
    }, '잠금') : null
  )
}

export function renderNav() {
  const user = currentUser()
  const items = navFor(user?.role || 'owner')
  clear(app.nav)
  for (const item of items) {
    app.nav.append(h('button', {
      class: app.current === item.id ? 'active' : '',
      dataset: { view: item.id },
      onClick: () => { location.hash = item.id }
    }, h('span', { class: 'ico' }, item.icon), h('span', {}, item.label)))
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
