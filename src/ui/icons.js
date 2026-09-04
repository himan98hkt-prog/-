// 아이콘 — 이모지 대신 선(stroke) 아이콘을 쓴다.
//
// 이모지는 기기마다 모양이 달라 화면이 들쭉날쭉해지고, 크기·색을 맞출 수 없다.
// 여기 아이콘은 전부 currentColor 를 따르고 굵기가 같아, 어떤 브랜드 색에도 톤이 맞는다.

const P = {
  home: 'M3 10.5 12 3l9 7.5M5.5 9.5V20a1 1 0 0 0 1 1H10v-6h4v6h3.5a1 1 0 0 0 1-1V9.5',
  check: 'M4 12.5 9 17.5 20 6.5',
  checkCircle: 'M21 11.2V12a9 9 0 1 1-5.3-8.2M21.5 5 12 14.5l-2.8-2.8',
  users: 'M16 20v-1.5a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4V20M9 10.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7ZM22 20v-1.5a4 4 0 0 0-3-3.9M16 3.6a4 4 0 0 1 0 7.7',
  user: 'M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z',
  won: 'M4 6l3 12 3-8 3 8 3-12M3 10h18M3 13.5h18',
  calendar: 'M8 3v3M16 3v3M4.5 9.5h15M6 5.5h12a1.5 1.5 0 0 1 1.5 1.5v12A1.5 1.5 0 0 1 18 20.5H6A1.5 1.5 0 0 1 4.5 19V7A1.5 1.5 0 0 1 6 5.5Z',
  chat: 'M21 12a8 8 0 0 1-8 8H7l-4 3 1.2-4.2A8 8 0 1 1 21 12Z',
  wallet: 'M3 8.5A2.5 2.5 0 0 1 5.5 6H18a2 2 0 0 1 2 2v1M3 8.5V17a2.5 2.5 0 0 0 2.5 2.5H18a2 2 0 0 0 2-2V15M20.5 9.5h-4a2.5 2.5 0 0 0 0 5h4a.5.5 0 0 0 .5-.5v-4a.5.5 0 0 0-.5-.5Z',
  chart: 'M4 20V10M10 20V4M16 20v-7M22 20H2',
  settings: 'M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-1.8-.3 1.6 1.6 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.6 1.6 0 0 0-1-1.5 1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0 .3-1.8 1.6 1.6 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.6 1.6 0 0 0 1.5-1 1.6 1.6 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.8.3H9a1.6 1.6 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.6 1.6 0 0 0 1 1.5 1.6 1.6 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8V9a1.6 1.6 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1Z',
  more: 'M5 12h.01M12 12h.01M19 12h.01',
  bell: 'M18 8.5a6 6 0 1 0-12 0c0 6-2.5 7.5-2.5 7.5h17S18 14.5 18 8.5ZM13.7 20a2 2 0 0 1-3.4 0',
  send: 'M21.5 2.5 11 13M21.5 2.5 15 21l-4-8-8-4 18.5-6.5Z',
  printer: 'M6.5 9V3.5h11V9M6.5 17H5a1.5 1.5 0 0 1-1.5-1.5v-5A1.5 1.5 0 0 1 5 9h14a1.5 1.5 0 0 1 1.5 1.5v5A1.5 1.5 0 0 1 19 17h-1.5M6.5 14h11v6.5h-11z',
  download: 'M12 3v12M7.5 10.5 12 15l4.5-4.5M4 20h16',
  upload: 'M12 16V4M7.5 8.5 12 4l4.5 4.5M4 20h16',
  plus: 'M12 5v14M5 12h14',
  search: 'M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14ZM20 20l-4-4',
  chevronRight: 'M9 5l7 7-7 7',
  chevronLeft: 'M15 5l-7 7 7 7',
  warning: 'M12 9v4.5M12 17.2v.1M10.3 3.9 2.6 17.2A2 2 0 0 0 4.3 20.2h15.4a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z',
  clock: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM12 7v5.2l3.2 2',
  refresh: 'M3.5 12a8.5 8.5 0 0 1 14.6-6M20.5 12a8.5 8.5 0 0 1-14.6 6M18.5 3v3h-3M5.5 21v-3h3',
  key: 'M15.5 8.5h.01M21 3l-2 2M17 7l-3.2 3.2M13.8 10.2a5.5 5.5 0 1 1-3.8 3.8l-7 7v-3h3v-3h3l4.8-4.8Z',
  save: 'M6 3.5h9.5L20.5 8.5V19a1.5 1.5 0 0 1-1.5 1.5H6A1.5 1.5 0 0 1 4.5 19V5A1.5 1.5 0 0 1 6 3.5ZM8 3.5v6h7v-6M8 20.5V14h8v6.5',
  receipt: 'M6 2.5h12v19l-2.5-2-2.5 2-3-2-2.5 2-1.5-1.2V2.5ZM9 8h6M9 12h6M9 16h3',
  phone: 'M6.5 3.5h3l1.5 4-2 1.5a12 12 0 0 0 6 6l1.5-2 4 1.5v3a2 2 0 0 1-2.2 2A17 17 0 0 1 4.5 5.7a2 2 0 0 1 2-2.2Z',
  sparkle: 'M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3ZM18.5 15.5l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7.7-2Z',
  repeat: 'M17 2.5 20.5 6 17 9.5M20.5 6H7a3.5 3.5 0 0 0-3.5 3.5v1M7 21.5 3.5 18 7 14.5M3.5 18H17a3.5 3.5 0 0 0 3.5-3.5v-1',
  lock: 'M7 10.5V7a5 5 0 0 1 10 0v3.5M5.5 10.5h13A1.5 1.5 0 0 1 20 12v7a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 19v-7a1.5 1.5 0 0 1 1.5-1.5Z',
  kiosk: 'M8 21h8M12 17.5V21M5.5 3.5h13A1.5 1.5 0 0 1 20 5v11a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 16V5a1.5 1.5 0 0 1 1.5-1.5ZM9 10.5l2 2 4-4',
  book: 'M4 4.5A2 2 0 0 1 6 2.5h13v16H6a2 2 0 0 0-2 2v-16ZM4 20.5a2 2 0 0 1 2-2h13v3H6a2 2 0 0 1-2-2Z',
  trash: 'M4 6.5h16M9.5 6.5V4h5v2.5M6.5 6.5 7.5 21h9l1-14.5M10 10.5v6.5M14 10.5v6.5',
  edit: 'M4 20h4L19 9a2.1 2.1 0 0 0-3-3L5 17v3ZM14.5 6.5l3 3'
}

/**
 * @param {keyof P} name
 * @param {{size?:number, stroke?:number, class?:string}} opts
 */
export function icon(name, { size = 20, stroke = 1.7, class: cls = '' } = {}) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
  svg.setAttribute('viewBox', '0 0 24 24')
  svg.setAttribute('width', String(size))
  svg.setAttribute('height', String(size))
  svg.setAttribute('fill', 'none')
  svg.setAttribute('stroke', 'currentColor')
  svg.setAttribute('stroke-width', String(stroke))
  svg.setAttribute('stroke-linecap', 'round')
  svg.setAttribute('stroke-linejoin', 'round')
  svg.setAttribute('aria-hidden', 'true')
  if (cls) svg.setAttribute('class', cls)
  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path')
  path.setAttribute('d', P[name] || P.home)
  svg.append(path)
  return svg
}

export const ICON_NAMES = Object.keys(P)
