// 인증키 게이트 — 활성화되지 않은 앱은 여기서 멈춘다.
//
// 순서: 저장된 인증키 → 유효하면 통과 / 체험 기간이 남았으면 통과(배너 표시) / 그 외에는 활성화 화면.
// 검증은 전부 오프라인이다(서버 왕복 없음). 데이터는 활성화 전에도 기기에 그대로 남아 있으므로
// 체험이 끝난 뒤 키를 넣으면 하던 작업을 그대로 이어서 쓴다.

import { h, toast, copyText, modal } from './dom.js'
import { icon } from './icons.js'
import * as repo from '../data/repo.js'
import { uid } from '../core/id.js'
import {
  verifyKey, hashKey, formatKey, normalizeKey, extractKey, keyFromLocation,
  deviceFingerprint, trialStatus, TRIAL_DAYS, PRODUCTS
} from '../core/license.js'
import { buyUrl } from '../core/store.js'

export function installId() {
  let id = repo.getSetting('installId')
  if (!id) {
    id = uid()
    repo.setSetting('installId', id) // 저장 완료를 기다리지 않아도 값은 캐시에 들어간다
  }
  return id
}

export function deviceCode() {
  return deviceFingerprint(installId())
}

/** 현재 사용 자격: {mode:'licensed'|'trial'|'none', plan, daysLeft} */
export function entitlement(now = new Date()) {
  const lic = repo.getSetting('license')
  if (lic?.key_hash) {
    return { mode: 'licensed', plan: lic.plan === 'pro' ? 'pro' : 'lite', license: lic, daysLeft: null }
  }
  const t = trialStatus({ startedAt: repo.getSetting('trialStartedAt'), today: now })
  if (t.active) return { mode: 'trial', plan: 'lite', daysLeft: t.daysLeft, trial: t }
  return { mode: 'none', plan: 'lite', daysLeft: 0, trial: t }
}

/**
 * @param {string} input        인증키
 * @param {{academyName?:string}} opts  피아노 관리노트의 '학원명 방식' 키를 쓸 때만 필요
 */
export async function activateWithKey(input, { academyName } = {}) {
  const name = academyName?.trim() || null
  // 12자리가 아니면 글 속에서 키를 찾아본다 (메일·문자를 통째로 붙여 넣은 경우)
  const candidate = normalizeKey(input).length === 12 ? input : (extractKey(input, { academyName: name }) || input)
  const res = verifyKey(candidate, { academyName: name })
  if (!res.ok) return res
  const lic = {
    key: res.key,
    key_hash: hashKey(res.key),
    plan: res.plan,
    product: res.product,
    version: res.version,
    scheme: res.scheme || 'academy-note',
    source: res.source || 'primary',
    academy_name: res.academyName || null,
    device: deviceCode(),
    activated_at: new Date().toISOString()
  }
  await repo.setSetting('license', lic)
  // 학원명으로 받은 키라면 그 이름이 곧 학원 이름이다 — 마법사에 미리 채워 준다
  if (res.academyName && !repo.getSetting('branding')?.name) {
    await repo.setSetting('pendingAcademyName', res.academyName)
  }
  repo.setPlan(res.plan)
  return { ok: true, license: lic, plan: res.plan }
}

export async function startTrial() {
  const started = repo.getSetting('trialStartedAt')
  if (started) return trialStatus({ startedAt: started })
  const now = new Date().toISOString()
  await repo.setSetting('trialStartedAt', now)
  return trialStatus({ startedAt: now })
}

/** 주소에 실려 온 키(#key=…)를 지운다 — 새로고침·즐겨찾기에 키가 남지 않게 */
function clearKeyFromAddress() {
  try {
    history.replaceState(null, '', location.pathname)
  } catch { /* file:// 등에서는 그냥 둔다 */ }
}

/**
 * 구매 메일의 "눌러서 바로 시작하기" 로 들어온 경우 — 키를 직접 넣지 않아도 인증된다.
 * 체험 중이던 사람이 구매 후 이 링크를 누르면 자료는 그대로 두고 정식으로 바뀐다.
 * @returns {Promise<{status:'none'|'activated'|'already'|'failed', key?:string, name?:string, reason?:string}>}
 */
export async function activateFromLink(loc = globalThis.location) {
  const link = keyFromLocation(loc || {})
  if (!link) return { status: 'none' }
  clearKeyFromAddress()
  if (repo.getSetting('license')?.key_hash) return { status: 'already' }
  const res = await activateWithKey(link.key, { academyName: link.name })
  if (res.ok) return { status: 'activated', key: link.key }
  return { status: 'failed', key: link.key, name: link.name, reason: res.reason }
}

/**
 * 인증키 입력 칸 — 첫 화면과 "인증키 입력" 창이 함께 쓴다.
 * 12자리를 한 자씩 옮겨 적지 않아도 되도록, 메일을 통째로 붙여 넣으면 키만 골라낸다.
 */
function keyForm({ initialKey = '', initialName = '', initialMsg = '', onDone, primary = false }) {
  const input = h('input', {
    type: 'text', class: 'keyinput', placeholder: 'XXXX-XXXX-XXXX', autocomplete: 'off', spellcheck: 'false',
    autocapitalize: 'characters', inputMode: 'text', value: initialKey, dataset: { act: 'key' }, 'aria-label': '인증키'
  })
  input.addEventListener('paste', (e) => {
    const text = e.clipboardData?.getData('text') || ''
    const found = extractKey(text, { academyName: nameInput.value.trim() || null })
    if (!found) return
    e.preventDefault()
    input.value = found
    msg.textContent = ''
  })
  input.addEventListener('input', () => {
    // 붙여넣기 이벤트가 오지 않는 입력기(일부 휴대폰 자판의 붙여넣기)를 위한 두 번째 그물
    if (normalizeKey(input.value).length > 12) {
      const found = extractKey(input.value)
      if (found) { input.value = found; return }
    }
    input.value = formatKey(input.value).slice(0, 14)
  })
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter') submit() })

  const msg = h('p', { class: 'small activation-msg', role: 'alert' }, initialMsg)

  // 피아노 관리노트에서 '학원명으로 받은 키' 는 학원명이 있어야 검증된다.
  // 평소에는 접어 두고, 필요할 때(또는 그 키로 실패했을 때) 펼친다.
  const nameInput = h('input', { type: 'text', placeholder: '예) 아첼음악학원', autocomplete: 'off', value: initialName, dataset: { act: 'name' } })
  const nameRow = h('div', { class: 'act-name', style: { display: initialName ? 'block' : 'none' } },
    h('div', { class: 'small muted', style: { marginBottom: '6px' } },
      '피아노 관리노트에서 학원명으로 받은 키라면, 그때 알려 주신 학원명을 그대로 넣어 주세요.'),
    nameInput)
  nameInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') submit() })

  function showName(on) {
    nameRow.style.display = on ? 'block' : 'none'
    if (on) nameInput.focus()
  }

  async function submit() {
    const typed = input.value.trim()
    if (!typed) { msg.textContent = '인증키를 넣어 주세요. 구매 후 받은 메일에 있습니다.'; input.focus(); return }
    const res = await activateWithKey(typed, { academyName: nameInput.value })
    if (!res.ok) {
      msg.textContent = res.reason
      if (/학원명/.test(res.reason)) showName(true)
      return
    }
    onDone?.(res)
  }

  const button = h('button', {
    class: `btn block lg ${primary ? 'primary' : 'ink'}`, type: 'button', dataset: { act: 'submit' }, onClick: submit
  }, icon('check', { size: 18, stroke: 2.2 }), '인증하고 시작하기')

  const node = h('div', { class: 'keyform' },
    input,
    h('div', { class: 'tiny muted keyhint' }, '받은 메일을 통째로 복사해 붙여 넣어도 됩니다.'),
    nameRow, msg, button)

  /** 밖에서 받은 키(메일 링크)를 칸에 넣고 바로 인증을 시도한다 */
  function submitWith(key, name = '') {
    input.value = formatKey(key)
    if (name) { nameInput.value = name; showName(true) }
    return submit()
  }

  return { node, input, showName, submitWith, toggleName: () => showName(nameRow.style.display === 'none') }
}

/** 앱 안에서 여는 "인증키 입력" 창 — 체험 중에 구매한 사람이 쓴다 */
export function openKeyDialog({ onActivated } = {}) {
  let dialog = null
  const form = keyForm({
    primary: true,
    onDone: () => {
      dialog?.close()
      toast('인증되었습니다. 감사합니다!', 'ok')
      onActivated?.(entitlement())
    }
  })
  dialog = modal({
    title: '인증키 입력',
    body: h('div', {},
      h('p', { class: 'muted small', style: { marginTop: 0 } },
        '구매 후 받은 메일의 인증키를 넣어 주세요. 지금까지 넣은 자료는 그대로 이어집니다.'),
      form.node,
      h('div', { class: 'row', style: { marginTop: '14px', justifyContent: 'space-between' } },
        h('button', { class: 'linkbtn', type: 'button', onClick: form.toggleName }, '피아노 관리노트 키인가요?'),
        h('a', { class: 'linkbtn', href: buyUrl('keydialog'), target: '_blank', rel: 'noopener' }, '아직 구매 전이라면 →'))),
    actions: []
  })
  setTimeout(() => form.input.focus(), 50)
  return dialog
}

/**
 * 활성화될 때까지 화면을 잡고 있는다. 통과하면 자격 객체를 돌려준다.
 *
 * 이 화면은 제품의 얼굴이다. 구매 전인 사람도 여기로 들어오므로
 * "무엇을 해 주는 프로그램인지 → 지금 바로 써 보기 → 이미 샀다면 키 넣기" 순서로 보여 준다.
 * @param {{onActivated?:Function}} opts
 */
export async function requireActivation({ onActivated } = {}) {
  const linked = await activateFromLink()
  if (linked.status === 'activated') {
    // 화면이 뜬 뒤에 보이도록 조금 늦춘다
    setTimeout(() => toast('인증되었습니다. 감사합니다!', 'ok'), 600)
  }

  const first = entitlement()
  if (first.mode !== 'none') return first

  return new Promise((resolve) => {
    const cover = h('div', { class: 'cover activation' })
    document.body.append(cover)

    const done = (ent) => {
      window.removeEventListener('hashchange', onLink)
      cover.remove()
      onActivated?.(ent)
      resolve(ent)
    }

    // 이 화면이 떠 있는 채로 메일의 링크가 같은 창에서 열리면(설치한 앱이 링크를 받아 여는 경우)
    // 새로 불러오지 않고 주소만 바뀐다. 그때도 키를 받아 바로 인증한다.
    function onLink() {
      const link = keyFromLocation(location)
      if (!link) return
      clearKeyFromAddress()
      form.submitWith(link.key, link.name)
    }
    window.addEventListener('hashchange', onLink)

    const trial = trialStatus({ startedAt: repo.getSetting('trialStartedAt') })
    const form = keyForm({
      initialKey: linked.status === 'failed' ? linked.key : '',
      initialName: linked.status === 'failed' ? linked.name : '',
      initialMsg: linked.status === 'failed' ? linked.reason : '',
      primary: trial.expired,
      onDone: () => { toast('인증되었습니다. 감사합니다!', 'ok'); done(entitlement()) }
    })

    const buy = (from, cls = 'btn block lg') => h('a', {
      class: cls, href: buyUrl(from), target: '_blank', rel: 'noopener', dataset: { act: 'buy' }
    }, '구매하러 가기', icon('chevronRight', { size: 17 }))

    const top = trial.expired
      ? h('div', {},
        h('div', { class: 'callout warn', style: { marginTop: 0 } },
          h('p', {}, h('b', {}, `무료 체험 ${TRIAL_DAYS}일이 끝났습니다.`)),
          h('p', {}, '넣어 두신 원생·출결·수납 자료는 이 기기에 그대로 있습니다. 인증키를 넣으면 바로 이어서 쓰실 수 있습니다.')),
        buy('expired', 'btn block lg primary'))
      : h('div', {},
        h('button', {
          class: 'btn primary block xl', type: 'button', dataset: { act: 'trial' },
          onClick: async () => {
            await startTrial()
            done(entitlement())
          }
        }, `${TRIAL_DAYS}일 무료로 써 보기`),
        h('p', { class: 'small muted center', style: { margin: '10px 0 0' } },
          '가입·카드 등록 없이 바로 시작합니다.'))

    const card = h('div', { class: 'panel card act-card' },
      h('h2', {}, trial.expired ? '이어서 쓰시려면' : '처음 오셨나요?'),
      top,
      h('div', { class: 'or' }, h('span', {}, trial.expired ? '인증키가 있으신가요?' : '이미 구매하셨나요?')),
      form.node,
      h('div', { class: 'act-links' },
        h('button', { class: 'linkbtn', type: 'button', onClick: form.toggleName }, '피아노 관리노트 키인가요?'),
        trial.expired ? null : h('a', {
          class: 'linkbtn', href: buyUrl('activation'), target: '_blank', rel: 'noopener', dataset: { act: 'buy' }
        }, '구매하러 가기 →')),
      h('div', { class: 'act-foot' },
        h('span', {}, `기기번호 ${deviceCode()}`),
        h('button', {
          class: 'linkbtn', type: 'button',
          onClick: () => copyText(deviceCode()).then(() => toast('기기번호를 복사했습니다'))
        }, '복사'),
        h('span', { class: 'grow' }),
        h('span', {}, '문의하실 때 알려 주세요')))

    cover.append(h('div', { class: 'act' }, hero(), card))
    if (linked.status === 'failed' || trial.expired) form.input.focus()
  })
}

/** 첫 화면 왼쪽 — 이 프로그램이 무엇을 해 주는지 세 줄로 */
function hero() {
  const point = (ico, title, desc) => h('li', {},
    h('span', { class: 'ico' }, icon(ico, { size: 20 })),
    h('span', {}, h('b', {}, title), h('em', {}, desc)))

  // 실제 화면을 줄여 놓은 그림 — 글보다 먼저 "아, 이런 거구나" 가 보이게 한다
  const mockRow = (state, name, note) => h('div', { class: `mock-row ${state}` },
    h('i', {}), h('b', {}, name), h('span', {}, note))

  return h('div', { class: 'act-hero' },
    h('div', { class: 'brandmark' }, 'ACADEMY NOTE'),
    h('h1', { class: 'act-title' }, '학원 관리노트'),
    h('p', { class: 'act-lead' }, '출석부, 수강료 장부, 학부모 문자.', h('br'), '매일 하던 일을 한 화면에서 끝냅니다.'),
    h('ul', { class: 'act-points' },
      point('checkCircle', '출석은 이름 한 번 누르면 끝', '반 전체가 왔으면 버튼 하나로 마칩니다'),
      point('won', '수강료 청구·미납 안내를 한 번에', '형제 할인도 알아서 계산합니다'),
      point('lock', '내 기기 안에만 저장됩니다', '인터넷이 끊겨도 그대로 쓰고, 자료가 밖으로 나가지 않습니다')),
    h('div', { class: 'act-mock', 'aria-hidden': 'true' },
      h('div', { class: 'mock-head' }, h('b', {}, '오늘 할 일'), h('span', {}, '3건')),
      mockRow('ok', '월수 4시반 출석', '8명 모두 출석'),
      mockRow('warn', '결석 안내 2명', '문구가 준비됐습니다'),
      mockRow('bad', '이달 미납 3건', '한 번에 안내하기')))
}

/** 헤더에 붙일 자격 배지 텍스트 */
export function entitlementBadge(ent = entitlement()) {
  if (ent.mode === 'trial') return `체험 D-${ent.daysLeft}`
  if (ent.mode === 'licensed') return ent.plan === 'pro' ? 'Pro' : 'Lite'
  return '미인증'
}

export { PRODUCTS }
