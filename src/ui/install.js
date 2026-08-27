// 홈 화면에 설치하기 도우미.
//
// 원장님들은 "앱"을 기대하신다. 브라우저 주소창에서 열 때마다 시작하면 프로그램처럼 느껴지지 않는다.
// 안드로이드는 브라우저가 주는 설치 창을 그대로 띄우고, 아이폰은 그 창이 없으므로 그림 대신 절차를 글로 안내한다.

import { h, modal, toast } from './dom.js'
import { icon } from './icons.js'
import { branding } from './branding.js'

let deferred = null

export function watchInstallPrompt() {
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault()
    deferred = e
  })
  window.addEventListener('appinstalled', () => { deferred = null })
}

export function isStandalone() {
  return window.matchMedia?.('(display-mode: standalone)').matches || window.navigator.standalone === true
}

export function canPromptInstall() {
  return !!deferred
}

function platform() {
  const ua = navigator.userAgent
  if (/iPhone|iPad|iPod/.test(ua)) return 'ios'
  if (/Android/.test(ua)) return 'android'
  return 'desktop'
}

const GUIDE = {
  ios: [
    '사파리(Safari)에서 이 화면을 엽니다. 다른 브라우저에서는 설치가 되지 않습니다.',
    '화면 아래 가운데의 공유 버튼(↑ 네모)을 누릅니다.',
    '목록을 내려 "홈 화면에 추가" 를 누릅니다.',
    '오른쪽 위 "추가" 를 누르면 끝. 홈 화면에 아이콘이 생깁니다.'
  ],
  android: [
    '크롬(Chrome)에서 이 화면을 엽니다.',
    '오른쪽 위 점 세 개(⋮) 를 누릅니다.',
    '"홈 화면에 추가" 또는 "앱 설치" 를 누릅니다.',
    '"설치" 를 누르면 끝. 홈 화면에 아이콘이 생깁니다.'
  ],
  desktop: [
    '크롬(Chrome) 또는 엣지(Edge)에서 이 화면을 엽니다.',
    '주소창 오른쪽 끝의 설치 아이콘(⊕ 또는 모니터 모양)을 누릅니다.',
    '"설치" 를 누르면 바탕화면과 시작 메뉴에 프로그램처럼 등록됩니다.'
  ]
}

export function openInstallGuide() {
  const b = branding()
  const kind = platform()
  const body = h('div', {})

  if (isStandalone()) {
    body.append(h('div', { class: 'callout ok' },
      h('p', {}, h('b', {}, '이미 설치된 상태로 열려 있습니다.'), ' 홈 화면 아이콘으로 여신 것이 맞습니다.')))
  } else {
    body.append(
      h('div', { class: 'callout tip' },
        h('p', {}, h('b', {}, `${b.name} 을(를) 홈 화면에 두면`), ' 주소를 외울 필요 없이 아이콘 한 번으로 열리고, 인터넷이 끊겨도 그대로 씁니다.')),
      canPromptInstall()
        ? h('div', {},
          h('p', { class: 'small muted' }, '이 기기는 바로 설치할 수 있습니다.'),
          h('button', {
            class: 'btn primary lg block',
            onClick: async () => {
              const e = deferred
              if (!e) return toast('설치 창을 열 수 없습니다. 아래 방법으로 진행해 주세요', 'error')
              deferred = null
              e.prompt()
              const res = await e.userChoice
              toast(res?.outcome === 'accepted' ? '설치했습니다' : '설치를 취소했습니다', res?.outcome === 'accepted' ? 'ok' : 'info')
            }
          }, icon('download', { size: 18 }), '지금 설치하기'),
          h('div', { class: 'section-head' }, h('h2', {}, '직접 설치하려면')))
        : null,
      h('ol', { class: 'steps' }, ...GUIDE[kind].map((t) => h('li', {}, t)))
    )
  }

  modal({
    title: '홈 화면에 설치하기',
    body,
    actions: [{ label: '닫기', kind: 'primary' }]
  })
}
