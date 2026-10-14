// 처음 한 번만 뜨는 안내.
//
// 컴퓨터가 익숙하지 않은 선생님이 처음 앱을 열었을 때, 설명서를 찾지 않고도
// "어디서 무엇을 하는지" 알 수 있게 세 장으로 끝낸다. 다시 보고 싶으면 설정에서 켤 수 있다.

import { h, clear } from './dom.js'
import { icon } from './icons.js'
import * as repo from '../data/repo.js'

const KEY = 'coachDone'

const STEPS = [
  {
    icon: 'home',
    title: '이 화면 하나만 보시면 됩니다',
    body: '오늘 해야 할 일이 여기 모입니다. 출결 안 한 반, 결석 안내할 학부모, 미납 안내까지 — 옆의 버튼만 누르시면 됩니다.'
  },
  {
    icon: 'checkCircle',
    title: '출석은 이름을 한 번 누르면 끝',
    body: '출결 탭에서 학생 이름을 누를 때마다 출석 → 지각 → 결석으로 바뀝니다. 반 전체가 왔으면 "전체 출석" 한 번이면 됩니다.'
  },
  {
    icon: 'send',
    title: '문자는 한 번에 보냅니다',
    body: '결석·미납 안내는 이름과 금액이 자동으로 채워집니다. 문구를 복사해 문자앱에 붙여 넣기만 하면 됩니다.'
  }
]

export function coachSeen() {
  return !!repo.getSetting(KEY)
}

export async function resetCoach() {
  await repo.setSetting(KEY, false)
}

/** 아직 안 본 사람에게만 보여 준다 */
export function maybeShowCoach() {
  if (coachSeen()) return null
  return showCoach()
}

export function showCoach() {
  let step = 0
  const box = h('div', { class: 'box' })
  const cover = h('div', { class: 'coach' }, box)
  document.body.append(cover)
  paint()

  async function done() {
    cover.remove()
    await repo.setSetting(KEY, true)
  }

  function paint() {
    const s = STEPS[step]
    clear(box)
    box.append(
      h('div', { class: 'step-ico' }, icon(s.icon, { size: 28 })),
      h('h2', { style: { fontSize: '1.15em', margin: '0 0 6px' } }, s.title),
      h('p', { class: 'muted', style: { margin: 0, fontSize: '.92em' } }, s.body),
      h('div', { class: 'dots' }, ...STEPS.map((_, i) => h('i', { class: i === step ? 'on' : '' }))),
      h('button', {
        class: 'btn primary block lg',
        onClick: () => { if (step < STEPS.length - 1) { step++; paint() } else done() }
      }, step < STEPS.length - 1 ? '다음' : '시작하기'),
      h('button', { class: 'btn ghost block', onClick: done }, '건너뛰기')
    )
  }

  return cover
}
