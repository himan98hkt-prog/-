// 앱 셸 — 헤더/탭/라우팅/로그인 커버.

import { h, $, clear, toast, modal, confirmDialog } from './dom.js'
import { icon } from './icons.js'
import { applyBranding, branding, logoDataUrl, initialsOf } from './branding.js'
import * as repo from '../data/repo.js'
import { navFor, can, ROLES } from '../core/perm.js'
import { currentUser, login, logout, findByPin, autoLoginIfSolo, DEFAULT_PIN } from './session.js'
import { openWizard } from './views/wizard.js'
import { requireActivation, entitlement, entitlementBadge, openKeyDialog, deviceCode, activateFromLink } from './activation.js'
import { keyFromLocation } from '../core/license.js'
import { STORE, buyUrl, trialNotice } from '../core/store.js'
import { showCoach } from './coach.js'
import { watchInstallPrompt, openInstallGuide, isStandalone } from './install.js'
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
  bars: null,
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
  app.bars = h('div', { class: 'app-bars' })
  app.main = h('main')
  app.nav = h('nav', { class: 'app-nav', 'aria-label': '주요 메뉴' })
  app.root.append(
    app.header,
    h('div', { class: 'app-body' }, app.rail, h('div', { class: 'app-col' }, app.bars, app.main)),
    app.nav)

  if (!repo.getSetting('wizardDone')) {
    // 샘플을 둘러본 뒤 "내 학원으로 시작" 을 눌러 돌아온 경우 첫 질문은 건너뛴다
    const skipIntro = sessionStorage.getItem('academy-note:skip-intro') === '1'
    sessionStorage.removeItem('academy-note:skip-intro')
    await openWizard({ skipIntro })
  }

  autoLoginIfSolo()
  if (!currentUser()) {
    await showLogin()
  }

  if (allowPro && repo.getPlan() === 'pro') {
    startSync().catch((e) => console.warn('동기화 시작 실패', e))
  }

  watchInstallPrompt()
  renderHelpButton()
  window.addEventListener('hashchange', async () => {
    // 앱을 쓰는 중에 구매 메일의 링크가 같은 창에서 열린 경우 — 화면 이동이 아니라 인증이다
    if (keyFromLocation(location)) {
      const res = await activateFromLink()
      if (res.status === 'activated') { toast('인증되었습니다. 감사합니다!', 'ok'); onActivated(entitlement()) }
      else if (res.status === 'failed') toast(res.reason, 'error')
      return
    }
    mount(location.hash.slice(1) || 'today')
  })
  renderHeader()
  renderBars()
  renderNav()
  mount(location.hash.slice(1) || 'today')
}

// ── 도움말 ──────────────────────────────────────────────────
// 설명서를 따로 찾지 않아도 되게, "하고 싶은 일" 로 찾는 짧은 안내를 앱 안에 둔다.
const HOWTO = [
  {
    icon: 'checkCircle', title: '출석 체크하기', view: 'attendance',
    steps: ['왼쪽(아래) 메뉴에서 "출결"을 누릅니다.', '반 이름을 고릅니다.', '학생 이름을 누르면 출석 → 지각 → 결석 순서로 바뀝니다.', '모두 왔으면 "전체 출석" 한 번이면 끝입니다.']
  },
  {
    icon: 'users', title: '원생 등록하기', view: 'students',
    steps: ['"원생" 메뉴에서 "원생 등록"을 누릅니다.', '이름만 넣어도 저장됩니다. 학부모 번호를 넣어 두면 문자 안내가 편해집니다.', '엑셀 명단이 있으면 "엑셀에서 가져오기"로 한 번에 넣을 수 있습니다.']
  },
  {
    icon: 'won', title: '수강료 받고 미납 안내하기', view: 'payments',
    steps: ['"수납" 메뉴에서 "이번 달 청구 만들기"를 누릅니다. 모든 원생의 수강료가 한 번에 만들어집니다.', '돈을 받으면 그 원생 줄의 "수정"을 눌러 "완납"으로 바꿉니다.', '안 낸 분들에게는 "미납자 일괄 안내"를 누르면 문구가 준비됩니다.']
  },
  {
    icon: 'send', title: '학부모에게 문자 보내기', view: 'today',
    steps: ['"오늘" 화면의 할 일에서 "일괄 안내"를 누릅니다.', '"전체 문구 복사"를 누릅니다.', '휴대폰 문자 앱을 열고 받는 사람을 고른 뒤, 입력 칸을 길게 눌러 "붙여넣기" 합니다.']
  },
  {
    icon: 'book', title: '교재·진도 적기', view: 'students',
    steps: ['"원생" 메뉴에서 학생 이름을 누릅니다.', '"교재·진도" 칸에서 교재를 고르고 오늘 진도를 적습니다. 예) 12번', '적어 둔 진도는 학부모 리포트와 레슨 안내 문자에 그대로 들어갑니다.']
  },
  {
    icon: 'save', title: '자료 안전하게 보관하기 (백업)', view: 'settings',
    steps: ['"설정" 메뉴에서 "백업 · 복원"을 엽니다.', '"백업 파일 받기"를 누르면 파일 하나가 저장됩니다.', '그 파일을 카카오톡 "나에게 보내기"나 USB에 넣어 두세요. 기기가 고장 나도 이 파일로 되살립니다.']
  }
]

export function openHelp() {
  const list = h('div', { class: 'howto' })
  let dialog = null
  for (const item of HOWTO) {
    const steps = h('ol', { class: 'steps' }, ...item.steps.map((t) => h('li', {}, t)))
    const go = h('button', {
      class: 'btn soft block', type: 'button',
      onClick: () => { dialog?.close(); location.hash = item.view }
    }, '이 화면으로 가기', icon('chevronRight', { size: 16 }))
    list.append(h('details', {},
      h('summary', {}, h('span', { class: 'todo-ico' }, icon(item.icon, { size: 19 })), h('b', {}, item.title), icon('chevronRight', { size: 17, class: 'chev' })),
      h('div', { class: 'howto-body' }, steps, go)))
  }

  dialog = modal({
    title: '도움말 — 무엇을 하고 싶으세요?',
    wide: true,
    body: h('div', {},
      list,
      h('div', { class: 'row wrap', style: { marginTop: '16px' } },
        h('button', { class: 'btn', type: 'button', onClick: () => { dialog?.close(); showCoach() } },
          icon('sparkle', { size: 17 }), '처음 안내 다시 보기'),
        h('button', { class: 'btn', type: 'button', onClick: () => { dialog?.close(); openInstallGuide() } },
          icon('download', { size: 17 }), isStandalone() ? '설치 상태 확인' : '홈 화면에 설치하기'),
        STORE.supportUrl
          ? h('a', { class: 'btn', href: STORE.supportUrl, target: '_blank', rel: 'noopener' }, icon('chat', { size: 17 }), STORE.supportLabel)
          : null),
      h('p', { class: 'small muted', style: { marginBottom: 0 } },
        `글씨가 작으면 설정 → 화면에서 "크게"를 고르세요. 문의하실 때는 기기번호 ${deviceCode()} 를 알려 주세요.`)),
    actions: []
  })
  return dialog
}

/** 휴대폰에서는 화면 오른쪽 아래 물음표 — 넓은 화면에서는 사이드바 아래에 같은 버튼이 있다 */
function renderHelpButton() {
  document.body.append(h('button', {
    class: 'helpfab', title: '도움말', 'aria-label': '도움말', type: 'button', onClick: () => openHelp()
  }, icon('help', { size: 22 })))
}

export async function startSync() {
  const mod = await import('../data/sync.js')
  app.sync = mod
  await mod.start({ onStatus: renderHeader })
  return mod
}

/** 학원 이름표 — 휴대폰은 위쪽 머리말, 넓은 화면은 사이드바 맨 위에 같은 것을 둔다 */
function brandBlock() {
  const b = branding()
  const user = currentUser()
  const logo = b.logo
    ? h('img', { class: 'logo', src: b.logo, alt: '' })
    : h('div', { class: 'logo' }, initialsOf(b.name))
  const sync = app.sync?.status?.() || null
  const ent = app.entitlement || entitlement()

  return [
    logo,
    h('div', { class: 'grow truncate' },
      h('div', { class: 'title truncate' }, b.name),
      h('div', { class: 'sub' },
        h('span', { class: `badge ${ent.mode === 'trial' ? 'warn' : 'brand'}` }, entitlementBadge(ent)),
        user ? h('span', { class: 'truncate' }, `${user.name} · ${ROLES[user.role]?.label || user.role}`) : null,
        sync
          ? h('span', { class: 'row', style: { gap: '4px' } },
            h('span', { class: `sync-dot ${sync.online ? 'on' : 'off'}` }),
            h('span', {}, sync.pending ? `대기 ${sync.pending}` : '동기화됨'))
          : null))
  ]
}

async function lockNow() {
  logout()
  location.reload()
}

/** 잠금은 걸어 둘 번호가 있을 때만 의미가 있다 — 혼자 쓰고 번호도 기본값이면 버튼을 감춘다 */
function lockable() {
  const users = repo.cache.users
  return users.length > 1 || users.some((u) => String(u.pin || DEFAULT_PIN) !== DEFAULT_PIN)
}

export function renderHeader() {
  if (!app.header) return
  clear(app.header)
  app.header.append(
    ...brandBlock(),
    h('button', { class: 'hbtn', type: 'button', onClick: () => openKiosk(), title: '학생이 들어오면서 직접 출석을 누르는 화면' },
      icon('kiosk', { size: 18 }), h('span', { class: 'hlabel' }, '등원 체크')),
    lockable()
      ? h('button', { class: 'hbtn', type: 'button', title: '자리를 비울 때 잠급니다', onClick: lockNow },
        icon('lock', { size: 18 }), h('span', { class: 'hlabel' }, '잠금'))
      : null)
  renderNav()
}

/** 화면 맨 위의 한 줄 안내 — 샘플 자료를 보는 중인지, 체험이 며칠 남았는지 */
export function renderBars() {
  if (!app.bars) return
  clear(app.bars)
  const ent = app.entitlement || entitlement()

  if (repo.getSetting('demoMode')) {
    app.bars.append(h('div', { class: 'noticebar demo', dataset: { bar: 'demo' } },
      icon('sparkle', { size: 17 }),
      h('span', { class: 'grow' }, h('b', {}, '샘플 학원입니다.'), h('span', { class: 'long' }, ' 연습용 자료이니 마음껏 눌러 보세요.')),
      h('button', { class: 'btn sm ink', type: 'button', dataset: { act: 'leave-demo' }, onClick: leaveDemo }, '내 학원으로 시작하기')))
  }

  if (ent.mode === 'trial') {
    const note = trialNotice(ent.daysLeft)
    app.bars.append(h('div', { class: `noticebar trial ${note.tone}`, dataset: { bar: 'trial' } },
      icon('clock', { size: 17 }),
      h('span', { class: 'grow' }, h('span', { class: 'long' }, note.text), h('span', { class: 'short' }, note.short)),
      h('button', {
        class: 'btn sm ghost', type: 'button', dataset: { act: 'enter-key' },
        onClick: () => openKeyDialog({ onActivated })
      }, '인증키 입력'),
      h('a', { class: 'btn sm primary', href: buyUrl('trial'), target: '_blank', rel: 'noopener', dataset: { act: 'buy' } }, '구매하기')))
  }
}

/** 체험 중에 키를 넣었다 — 화면을 다시 열지 않고 그 자리에서 정식으로 바꾼다 */
function onActivated(ent) {
  app.entitlement = ent
  repo.setPlan(ent.plan)
  renderHeader()
  renderBars()
  if (app.allowPro && ent.plan === 'pro') startSync().catch((e) => console.warn('동기화 시작 실패', e))
  if (app.current === 'settings') refresh()
}

/** 샘플을 다 봤다 — 샘플 자료를 지우고 내 학원 만들기로 넘어간다 (인증·체험 기간은 그대로) */
async function leaveDemo() {
  const ok = await confirmDialog(
    '샘플 원생·출결·수납 자료를 모두 지우고, 원장님 학원을 새로 만듭니다. 계속할까요?',
    { title: '내 학원으로 시작하기', okLabel: '샘플 지우고 시작' })
  if (!ok) return
  const { clearAll } = await import('../data/seed.js')
  await clearAll()
  logout()
  sessionStorage.setItem('academy-note:skip-intro', '1')
  location.hash = ''
  location.reload()
}

export function renderNav() {
  const user = currentUser()
  const items = navFor(user?.role || 'owner')
  const primary = items.filter((n) => n.primary)
  const rest = items.filter((n) => !n.primary)

  // 넓은 화면: 왼쪽 사이드바에 전부 펼친다
  clear(app.rail)
  app.rail.append(h('div', { class: 'rail-brand' }, ...brandBlock()))
  const menu = h('div', { class: 'rail-menu' })
  for (const item of items) {
    if (item.id === 'timetable' && rest.length) menu.append(h('div', { class: 'rail-label' }, '관리'))
    menu.append(h('button', {
      class: app.current === item.id ? 'active' : '', type: 'button',
      dataset: { view: item.id },
      onClick: () => { location.hash = item.id }
    }, icon(item.icon, { size: 20 }), h('span', {}, item.label)))
  }
  app.rail.append(menu,
    h('div', { class: 'rail-foot' },
      h('button', { type: 'button', dataset: { act: 'kiosk' }, onClick: () => openKiosk(), title: '학생이 들어오면서 직접 출석을 누르는 화면' },
        icon('kiosk', { size: 19 }), h('span', {}, '등원 체크 화면')),
      h('button', { type: 'button', dataset: { act: 'help' }, onClick: () => openHelp() },
        icon('help', { size: 19 }), h('span', {}, '도움말')),
      lockable()
        ? h('button', { type: 'button', title: '자리를 비울 때 잠급니다', onClick: lockNow }, icon('lock', { size: 19 }), h('span', {}, '화면 잠금'))
        : null))

  // 휴대폰: 네 칸 + 더보기
  clear(app.nav)
  for (const item of primary) {
    app.nav.append(h('button', {
      class: app.current === item.id ? 'active' : '', type: 'button',
      dataset: { view: item.id },
      onClick: () => { location.hash = item.id }
    }, h('span', { class: 'ico' }, icon(item.icon, { size: 22 })), h('span', {}, item.label)))
  }
  if (rest.length) {
    const activeInRest = rest.some((n) => n.id === app.current)
    app.nav.append(h('button', {
      class: activeInRest ? 'active' : '', type: 'button',
      dataset: { view: 'more' },
      onClick: () => openMoreSheet(rest)
    }, h('span', { class: 'ico' }, icon('list', { size: 22 })), h('span', {}, '더보기')))
  }
}

/** 하단 탭에 들어가지 못한 메뉴 — 큰 글씨·설명과 함께 보여 준다 */
function openMoreSheet(items) {
  const list = h('div', {})
  const { close } = modal({ title: '메뉴', body: list, actions: [] })
  for (const item of items) {
    list.append(h('button', {
      class: 'list-row link', type: 'button',
      style: { width: '100%', border: 0, background: 'none', textAlign: 'left', cursor: 'pointer' },
      onClick: () => { close(); location.hash = item.id }
    },
      h('span', { class: 'todo-ico', style: { width: '38px', height: '38px' } }, icon(item.icon, { size: 19 })),
      h('span', { class: 'grow' },
        h('b', {}, item.label),
        h('div', { class: 'small muted' }, item.desc || '')),
      icon('chevronRight', { size: 18 })))
  }

  // 휴대폰에서는 위쪽에 버튼을 두지 않는다 — 그림만으로는 뜻을 알 수 없어서, 이름과 설명을 붙여 여기에 둔다
  const extra = (ico, label, desc, onClick) => list.append(h('button', {
    class: 'list-row link', type: 'button',
    style: { width: '100%', border: 0, background: 'none', textAlign: 'left', cursor: 'pointer' },
    onClick: () => { close(); onClick() }
  },
    h('span', { class: 'todo-ico', style: { width: '38px', height: '38px' } }, icon(ico, { size: 19 })),
    h('span', { class: 'grow' }, h('b', {}, label), h('div', { class: 'small muted' }, desc)),
    icon('chevronRight', { size: 18 })))
  extra('kiosk', '등원 체크 화면', '학생이 들어오면서 직접 출석을 누릅니다', () => openKiosk())
  extra('help', '도움말', '하고 싶은 일을 순서대로 알려 드립니다', () => openHelp())
  if (lockable()) extra('lock', '화면 잠금', '자리를 비울 때 잠급니다', lockNow)
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
    const msg = h('div', { class: 'small muted center', style: { minHeight: '20px' } }, '잠금 번호 4자리를 눌러 주세요')

    const update = () => { dots.textContent = '●'.repeat(pin.length) + '○'.repeat(Math.max(0, 4 - pin.length)) }

    const tryLogin = () => {
      const user = findByPin(pin)
      if (!user) {
        msg.textContent = '번호가 맞지 않습니다. 다시 눌러 주세요'
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
        h('div', { class: 'small muted center', style: { marginTop: '12px' } }, '번호를 정한 적이 없다면 0000 입니다')
      )
    )
    update()
    document.body.append(cover)
  })
}

export { toast }
