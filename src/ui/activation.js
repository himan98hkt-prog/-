// 인증키 게이트 — 활성화되지 않은 앱은 여기서 멈춘다.
//
// 순서: 저장된 인증키 → 유효하면 통과 / 체험 기간이 남았으면 통과(배너 표시) / 그 외에는 활성화 화면.
// 검증은 전부 오프라인이다(서버 왕복 없음). 데이터는 활성화 전에도 기기에 그대로 남아 있으므로
// 체험이 끝난 뒤 키를 넣으면 하던 작업을 그대로 이어서 쓴다.

import { h, clear, toast, copyText } from './dom.js'
import * as repo from '../data/repo.js'
import { uid } from '../core/id.js'
import {
  verifyKey, hashKey, formatKey, deviceFingerprint, trialStatus, TRIAL_DAYS, PRODUCTS
} from '../core/license.js'

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
  const res = verifyKey(input, { academyName: academyName?.trim() || null })
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

/**
 * 활성화될 때까지 화면을 잡고 있는다. 통과하면 자격 객체를 돌려준다.
 * @param {{onActivated?:Function}} opts
 */
export function requireActivation({ onActivated } = {}) {
  return new Promise((resolve) => {
    const first = entitlement()
    if (first.mode !== 'none') return resolve(first)

    const body = h('div')
    const cover = h('div', { class: 'cover activation' }, h('div', { class: 'panel card' }, body))
    document.body.append(cover)
    paint()

    function done(ent) {
      cover.remove()
      onActivated?.(ent)
      resolve(ent)
    }

    function paint() {
      const trial = trialStatus({ startedAt: repo.getSetting('trialStartedAt') })
      const input = h('input', {
        type: 'text', placeholder: 'AAAA-AAAA-AAAA', autocomplete: 'off', spellcheck: 'false',
        style: { fontSize: '18px', letterSpacing: '2px', textAlign: 'center' }
      })
      input.addEventListener('input', () => {
        const pos = input.value.length
        input.value = formatKey(input.value).slice(0, 14)
        if (pos >= input.value.length) input.setSelectionRange(input.value.length, input.value.length)
      })
      input.addEventListener('keydown', (e) => { if (e.key === 'Enter') submit() })

      const msg = h('p', { class: 'small activation-msg', style: { minHeight: '18px', color: 'var(--danger)' } })

      // 피아노 관리노트에서 '학원명으로 받은 키' 는 학원명이 있어야 검증된다.
      // 평소에는 접어 두고, 필요할 때(또는 그 키로 실패했을 때) 펼친다.
      const nameInput = h('input', { type: 'text', placeholder: '예) 아첼음악학원', autocomplete: 'off' })
      const nameRow = h('div', { style: { display: 'none', marginTop: '10px' } },
        h('div', { class: 'small muted', style: { marginBottom: '4px', textAlign: 'left' } },
          '피아노 관리노트에서 학원명으로 받은 키라면 그때 알려 주신 학원명을 그대로 넣어 주세요'),
        nameInput)
      const nameToggle = h('button', {
        class: 'linkbtn', type: 'button',
        onClick: () => { showName(nameRow.style.display === 'none') }
      }, '피아노 관리노트 키인가요?')
      nameInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') submit() })

      function showName(on) {
        nameRow.style.display = on ? 'block' : 'none'
        if (on) nameInput.focus()
      }

      async function submit() {
        const res = await activateWithKey(input.value, { academyName: nameInput.value })
        if (!res.ok) {
          msg.textContent = res.reason
          if (/학원명/.test(res.reason)) showName(true)
          return
        }
        toast('인증되었습니다. 감사합니다!', 'ok')
        done(entitlement())
      }

      clear(body)
      body.append(
        h('h2', { style: { marginBottom: '4px' } }, '학원 관리노트'),
        h('p', { class: 'muted small' }, '구매하신 인증키를 입력하면 바로 시작합니다.'),
        h('div', { style: { marginTop: '18px' } }, input),
        nameRow,
        msg,
        h('button', { class: 'btn primary block', onClick: submit }, '인증하고 시작하기'),
        h('div', { class: 'divider' }),
        trial.expired
          ? h('div', {},
            h('p', { class: 'small' }, `체험 기간(${TRIAL_DAYS}일)이 끝났습니다. 저장된 자료는 그대로 있으니 인증키를 넣으면 이어서 사용할 수 있습니다.`))
          : h('button', {
            class: 'btn block', onClick: async () => {
              await startTrial()
              toast(`${TRIAL_DAYS}일 체험을 시작합니다`, 'ok')
              done(entitlement())
            }
          }, `${TRIAL_DAYS}일 무료 체험 시작 (키 없이 전 기능)`),
        h('div', { class: 'row small muted', style: { marginTop: '14px' } },
          nameToggle,
          h('span', { class: 'grow right' }, `기기번호 ${deviceCode()}`),
          h('button', {
            class: 'linkbtn',
            onClick: () => copyText(deviceCode()).then(() => toast('기기번호를 복사했습니다'))
          }, '복사')),
        h('p', { class: 'small muted' },
          '구매·재발급 문의 시 위 기기번호를 함께 알려 주세요. ',
          h('b', {}, '피아노 관리노트에서 쓰던 인증키를 그대로 쓸 수 있습니다.'))
      )
      input.focus()
    }
  })
}

/** 헤더에 붙일 자격 배지 텍스트 */
export function entitlementBadge(ent = entitlement()) {
  if (ent.mode === 'trial') return `체험 D-${ent.daysLeft}`
  if (ent.mode === 'licensed') return ent.plan === 'pro' ? 'Pro' : 'Lite'
  return '미인증'
}

export { PRODUCTS }
