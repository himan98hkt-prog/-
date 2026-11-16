// 시작 마법사 — 처음 한 번, 1분 안에 끝낸다.
//
// 묻는 것은 세 가지뿐이다: 어떻게 시작할지 · 학원 이름과 종류 · 색.
// 나머지(과목, 학습 항목, 안내 문구)는 고른 종류에 맞춰 알아서 깔아 준다.
// 잠금 번호(PIN)는 여기서 묻지 않는다 — 혼자 쓰는 원장님에게는 걸림돌이라 설정에서 원할 때 켠다.

import { h, clear, toast } from '../dom.js'
import { icon } from '../icons.js'
import * as repo from '../../data/repo.js'
import { applyBranding } from '../branding.js'
import { login } from '../session.js'
import { PRESETS } from '../../core/customfields.js'
import { DEFAULT_TEMPLATES } from '../../core/templates.js'
import { DEFAULT_REASON_TAGS } from '../../core/attendance.js'
import { uid } from '../../core/id.js'

// 구매하시는 분이 대부분 피아노 원장님이라 음악을 맨 앞에 둔다
export const CATEGORIES = [
  { key: '음악', label: '피아노 · 음악', icon: 'music', subjects: ['피아노'], demo: 'piano' },
  { key: '예체능', label: '미술', icon: 'brush', subjects: ['미술'], demo: 'art' },
  { key: '어학', label: '영어 · 어학', icon: 'chat', subjects: ['영어'], demo: 'english' },
  { key: '교과', label: '수학 · 교과', icon: 'book', subjects: ['수학'], demo: 'math' },
  { key: '체육', label: '태권도 · 체육', icon: 'medal', subjects: ['태권도'], demo: 'taekwondo' },
  { key: '공부방', label: '공부방', icon: 'home', subjects: ['자기주도'], demo: 'math' }
]

// 간판·현수막에 인쇄해도 촌스럽지 않은 톤으로 골랐다 (형광·원색 제외)
const COLORS = [
  { hex: '#2c4a7c', name: '남색' },
  { hex: '#7a3b62', name: '자주' },
  { hex: '#2e6b4f', name: '초록' },
  { hex: '#a8843f', name: '금색' },
  { hex: '#a63a3a', name: '진홍' },
  { hex: '#2f6d8f', name: '청록' },
  { hex: '#5b4b8a', name: '보라' },
  { hex: '#33302c', name: '먹색' }
]

/**
 * @param {{skipIntro?:boolean}} opts  샘플을 둘러본 뒤 "내 학원으로 시작" 을 누른 경우 첫 질문을 건너뛴다
 */
export function openWizard({ skipIntro = false } = {}) {
  return new Promise((resolve) => {
    // 피아노 관리노트의 '학원명 방식' 키로 인증했다면 그 이름을 그대로 채워 준다
    const state = {
      mode: skipIntro ? 'mine' : null,
      name: repo.getSetting('pendingAcademyName') || '',
      category: CATEGORIES[0].key,
      color: COLORS[0].hex
    }
    let step = skipIntro ? 1 : 0
    const body = h('div')
    const cover = h('div', { class: 'cover wizard' }, h('div', { class: 'panel card' }, body))
    document.body.append(cover)

    const flow = () => (state.mode === 'sample' ? [stepStart, stepSample] : [stepStart, stepName, stepColor])

    function paint() {
      const steps = flow()
      clear(body)
      body.append(
        h('div', { class: 'wiz-steps' }, ...steps.map((_, i) => h('i', { class: i <= step ? 'on' : '' }))),
        steps[step]())
    }

    function nav(onNext, nextLabel = '다음') {
      const canBack = step > (skipIntro ? 1 : 0)
      return h('div', { class: 'wiz-nav' },
        canBack ? h('button', { class: 'btn ghost', type: 'button', onClick: () => { step--; paint() } }, icon('chevronLeft', { size: 17 }), '이전') : h('span'),
        h('button', { class: 'btn primary lg', type: 'button', dataset: { wiz: 'next' }, onClick: onNext }, nextLabel))
    }

    function categoryTiles() {
      const box = h('div', { class: 'tiles' })
      const paintTiles = () => {
        clear(box)
        for (const c of CATEGORIES) {
          box.append(h('button', {
            class: `tile ${state.category === c.key ? 'on' : ''}`, type: 'button', dataset: { cat: c.key },
            onClick: () => { state.category = c.key; paintTiles() }
          }, icon(c.icon, { size: 24 }), h('span', {}, c.label)))
        }
      }
      paintTiles()
      return box
    }

    // 0) 어떻게 시작할까요
    function stepStart() {
      const choice = (mode, ico, title, desc, tag) => h('button', {
        class: 'choice', type: 'button', dataset: { wiz: mode },
        onClick: () => { state.mode = mode; step = 1; paint() }
      },
        h('span', { class: 'ico' }, icon(ico, { size: 24 })),
        h('span', { class: 'grow' },
          h('b', {}, title, tag ? h('em', { class: 'tag' }, tag) : null),
          h('span', { class: 'desc' }, desc)),
        icon('chevronRight', { size: 18 }))

      return h('div', {},
        h('h2', {}, '어떻게 시작할까요?'),
        h('p', { class: 'muted' }, '둘 중 편한 쪽을 고르세요. 나중에 언제든 바꿀 수 있습니다.'),
        choice('sample', 'sparkle', '샘플 학원으로 먼저 둘러보기',
          '원생 24명이 들어 있는 연습용 학원입니다. 마음껏 눌러 보고, 다 보면 지우고 시작합니다.', '처음이라면'),
        choice('mine', 'edit', '내 학원으로 바로 시작하기',
          '학원 이름만 정하면 됩니다. 1분이면 끝납니다.'))
    }

    // 1-a) 샘플 — 어떤 학원인지만 고른다
    function stepSample() {
      return h('div', {},
        h('h2', {}, '어떤 학원을 보여 드릴까요?'),
        h('p', { class: 'muted' }, '원장님 학원과 가장 비슷한 것을 고르세요.'),
        categoryTiles(),
        nav(startSample, '샘플 학원 열기'))
    }

    // 1-b) 내 학원 — 이름과 종류
    function stepName() {
      const input = h('input', {
        type: 'text', value: state.name, placeholder: '예) 아첼 음악학원', maxLength: 30,
        dataset: { wiz: 'name' }, style: { fontSize: '1.1em', height: '54px' }
      })
      input.addEventListener('keydown', (e) => { if (e.key === 'Enter') next() })
      setTimeout(() => input.focus(), 30)

      function next() {
        if (!input.value.trim()) { toast('학원 이름을 넣어 주세요', 'error'); input.focus(); return }
        state.name = input.value.trim()
        step++
        paint()
      }

      return h('div', {},
        h('h2', {}, '학원 이름을 알려 주세요'),
        h('p', { class: 'muted' }, '화면 맨 위와 학부모에게 보내는 리포트·영수증에 들어갑니다.'),
        h('label', { class: 'field' }, h('span', { class: 'field-label' }, '학원 이름'), input),
        h('div', { class: 'field' },
          h('span', { class: 'field-label' }, '어떤 학원인가요?'),
          categoryTiles(),
          h('div', { class: 'field-hint' }, '고른 종류에 맞춰 과목과 기록 항목을 미리 준비해 드립니다.')),
        nav(next))
    }

    // 2) 색
    function stepColor() {
      const row = h('div', { class: 'swatches' })
      const paintColors = () => {
        clear(row)
        for (const c of COLORS) {
          row.append(h('button', {
            class: `swatch ${state.color === c.hex ? 'on' : ''}`, type: 'button',
            style: { background: c.hex }, title: c.name,
            onClick: () => {
              state.color = c.hex
              document.documentElement.style.setProperty('--brand', c.hex)
              paintColors()
            }
          }, h('span', { class: 'swatch-name' }, c.name)))
        }
      }
      paintColors()
      return h('div', {},
        h('h2', {}, `${state.name}의 색을 골라 주세요`),
        h('p', { class: 'muted' }, '버튼과 리포트에 이 색이 쓰입니다. 마음에 안 들면 설정에서 바꿀 수 있습니다.'),
        row,
        nav(finish, '시작하기'))
    }

    async function finish() {
      const cat = CATEGORIES.find((c) => c.key === state.category) || CATEGORIES[0]
      await repo.setSetting('branding', { name: state.name, brand_color: state.color, logo: null, phone: '' })
      await repo.setSetting('customFields', PRESETS[cat.key] || [])
      await repo.setSetting('templates', DEFAULT_TEMPLATES)
      await repo.setSetting('reasonTags', DEFAULT_REASON_TAGS)
      await repo.setSetting('category', cat.key)
      await repo.setSetting('pendingAcademyName', null)

      if (!repo.cache.users.length) {
        await repo.put('users', { id: uid('u'), name: '원장', role: 'owner', pin: '0000' })
      }
      for (const name of cat.subjects) {
        if (repo.cache.subjects.some((s) => s.name === name)) continue
        await repo.put('subjects', { name, color: state.color })
      }
      await repo.setSetting('wizardDone', true)
      applyBranding()

      cover.remove()
      resolve(state)
    }

    /** 샘플 학원을 깔고 원장으로 바로 들어간다 (잠금 번호를 묻지 않는다) */
    async function startSample() {
      const cat = CATEGORIES.find((c) => c.key === state.category) || CATEGORIES[0]
      clear(body)
      body.append(h('div', { class: 'empty' },
        h('div', { class: 'emoji' }, icon('sparkle', { size: 26 })),
        h('b', {}, '샘플 학원을 준비하고 있습니다'),
        h('p', {}, '잠시만 기다려 주세요…')))

      const { seedDemo } = await import('../../data/seed.js')
      await seedDemo(cat.demo, { students: 24 })
      await repo.init()
      await repo.setSetting('demoMode', true)
      const owner = repo.cache.users.find((u) => u.role === 'owner')
      if (owner) login(owner, { remember: true })
      location.hash = ''
      location.reload()
    }

    paint()
  })
}
