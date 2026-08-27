// 시작 마법사 — 학원명/계열/브랜드/과목/원장 PIN 을 3분 안에 끝낸다.

import { h, clear, toast } from '../dom.js'
import * as repo from '../../data/repo.js'
import { saveBranding, applyBranding } from '../branding.js'
import { PRESETS } from '../../core/customfields.js'
import { DEFAULT_TEMPLATES } from '../../core/templates.js'
import { DEFAULT_REASON_TAGS } from '../../core/attendance.js'
import { uid } from '../../core/id.js'

const CATEGORIES = [
  { key: '교과', label: '교과 (수학·영어·국어)', subjects: ['수학', '영어', '국어'] },
  { key: '어학', label: '어학원', subjects: ['Reading', 'Speaking', 'Grammar'] },
  { key: '예체능', label: '예체능 (음악·미술)', subjects: ['피아노', '미술'] },
  { key: '체육', label: '체육 (태권도·주짓수)', subjects: ['품새', '겨루기'] },
  { key: '공부방', label: '공부방 · 스터디카페', subjects: ['자기주도'] }
]
const COLORS = ['#2563eb', '#dc2626', '#16a34a', '#7c3aed', '#db2777', '#f59e0b', '#0891b2', '#111827']

export function openWizard() {
  return new Promise((resolve) => {
    // 피아노 관리노트의 '학원명 방식' 키로 인증했다면 그 이름을 그대로 채워 준다
    const state = {
      name: repo.getSetting('pendingAcademyName') || '',
      category: '교과', color: COLORS[0], pin: '0000', demo: false
    }
    let step = 0
    const body = h('div')
    const cover = h('div', { class: 'cover' }, h('div', { class: 'panel card' }, body))
    document.body.append(cover)

    const steps = [stepName, stepBrand, stepSubjects, stepAccount]

    function paint() {
      clear(body)
      body.append(
        h('div', { class: 'small muted', style: { marginBottom: '6px' } }, `${step + 1} / ${steps.length}`),
        steps[step]()
      )
    }

    function nav(onNext, nextLabel = '다음') {
      return h('div', { class: 'row', style: { marginTop: '16px' } },
        step > 0 ? h('button', { class: 'btn', onClick: () => { step--; paint() } }, '이전') : null,
        h('button', { class: 'btn primary right', onClick: onNext }, nextLabel))
    }

    function stepName() {
      const input = h('input', { type: 'text', value: state.name, placeholder: '예) 아라 잉글리시' })
      const catSel = h('div', { class: 'row wrap' })
      const paintCats = () => {
        clear(catSel)
        for (const c of CATEGORIES) {
          catSel.append(h('button', {
            class: `chip ${state.category === c.key ? 'active' : ''}`,
            onClick: () => { state.category = c.key; paintCats() }
          }, c.label))
        }
      }
      paintCats()
      return h('div', {},
        h('h2', {}, '학원 관리노트 시작하기'),
        h('p', { class: 'muted small' }, '학원명과 계열만 정하면 나머지는 자동으로 준비됩니다.'),
        h('label', { class: 'field' }, h('span', { class: 'field-label' }, '학원명'), input),
        h('label', { class: 'field' }, h('span', { class: 'field-label' }, '계열'), catSel),
        nav(() => {
          if (!input.value.trim()) return toast('학원명을 입력해 주세요', 'error')
          state.name = input.value.trim()
          step++
          paint()
        })
      )
    }

    function stepBrand() {
      const colorRow = h('div', { class: 'row wrap' })
      const paintColors = () => {
        clear(colorRow)
        for (const c of COLORS) {
          colorRow.append(h('button', {
            class: 'chip', style: { background: c, color: '#fff', outline: state.color === c ? '3px solid #111827' : 'none' },
            onClick: () => { state.color = c; document.documentElement.style.setProperty('--brand', c); paintColors() }
          }, ' '))
        }
      }
      paintColors()
      return h('div', {},
        h('h2', {}, '브랜드 컬러'),
        h('p', { class: 'muted small' }, '앱 헤더, 리포트카드, 설치 아이콘에 이 색이 쓰입니다. 로고는 나중에 설정에서 올릴 수 있습니다.'),
        colorRow,
        nav(() => { step++; paint() })
      )
    }

    function stepSubjects() {
      const cat = CATEGORIES.find((c) => c.key === state.category)
      const box = h('div', { class: 'row wrap' })
      const chosen = new Set(cat.subjects)
      const custom = h('input', { type: 'text', placeholder: '과목 추가 후 Enter' })
      const paintSubs = () => {
        clear(box)
        for (const s of chosen) {
          box.append(h('span', { class: 'chip active', onClick: () => { chosen.delete(s); paintSubs() } }, `${s} ✕`))
        }
      }
      custom.addEventListener('keydown', (e) => {
        if (e.key !== 'Enter' || !custom.value.trim()) return
        chosen.add(custom.value.trim())
        custom.value = ''
        paintSubs()
      })
      paintSubs()
      return h('div', {},
        h('h2', {}, '과목'),
        h('p', { class: 'muted small' }, `${cat.label} 기본 과목입니다. 지우거나 추가할 수 있습니다.`),
        box, custom,
        h('label', { class: 'row small', style: { gap: '6px', marginTop: '12px' } },
          h('input', { type: 'checkbox', style: { width: 'auto' }, onChange: (e) => { state.demo = e.target.checked } }),
          '샘플 원생 데이터도 함께 넣기 (연습용, 나중에 삭제 가능)'),
        nav(() => { state.subjects = [...chosen]; step++; paint() })
      )
    }

    function stepAccount() {
      const pin = h('input', { type: 'text', value: '0000', maxLength: 4, inputMode: 'numeric' })
      return h('div', {},
        h('h2', {}, '원장 PIN'),
        h('p', { class: 'muted small' }, '앱을 열 때 쓰는 4자리 숫자입니다. 강사·데스크 계정은 설정에서 추가하세요.'),
        h('label', { class: 'field' }, h('span', { class: 'field-label' }, 'PIN 4자리'), pin),
        nav(async () => {
          if (!/^\d{4}$/.test(pin.value)) return toast('숫자 4자리를 입력해 주세요', 'error')
          state.pin = pin.value
          await finish()
        }, '시작하기')
      )
    }

    async function finish() {
      await repo.setSetting('branding', { name: state.name, brand_color: state.color, logo: null, phone: '' })
      await repo.setSetting('customFields', PRESETS[state.category] || [])
      await repo.setSetting('templates', DEFAULT_TEMPLATES)
      await repo.setSetting('reasonTags', DEFAULT_REASON_TAGS)
      await repo.setSetting('category', state.category)

      if (!repo.cache.users.length) {
        await repo.put('users', { id: uid('u'), name: '원장', role: 'owner', pin: state.pin })
      }
      for (const name of state.subjects || []) {
        if (repo.cache.subjects.some((s) => s.name === name)) continue
        await repo.put('subjects', { name, color: state.color })
      }
      await repo.setSetting('wizardDone', true)
      applyBranding()

      if (state.demo) {
        const { seedDemo } = await import('../../data/seed.js')
        const map = { 교과: 'english', 어학: 'english', 예체능: 'piano', 체육: 'taekwondo', 공부방: 'english' }
        await seedDemo(map[state.category] || 'english', { students: 24 })
        await repo.setSetting('branding', { name: state.name, brand_color: state.color, logo: null, phone: '' })
        await repo.setSetting('wizardDone', true)
        location.reload()
        return
      }

      cover.remove()
      toast('준비 완료! 시간표 탭에서 반을 만들어 보세요', 'ok')
      resolve(state)
    }

    paint()
  })
}
