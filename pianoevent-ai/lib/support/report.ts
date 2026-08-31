import { BRAND } from '@/lib/brand'
/**
 * "막히면 여기" — 원장님이 저희에게 보내실 쪽지를 만들어 준다.
 *
 * 막히셨을 때 오는 연락은 늘 "안 돼요" 한 줄이다. 그것만으로는 아무것도 못 한다.
 * 필요한 것은 다섯 가지뿐이다 — 어느 화면에서, 무엇을 하셨을 때, 무슨 글이 떴고,
 * 프로그램 판이 무엇이고, 브라우저가 무엇인가.
 *
 * 그런데 화면을 통째로 찍어 보내시면 **아이들 이름과 얼굴이 함께 나간다.**
 * 그래서 쪽지에는 이름·사진·연락처를 절대 담지 않는다. 숫자와 화면 이름만 담는다.
 * 아래 buildReport 는 담을 것을 스스로 정한다 — 원장님이 지우실 것이 없어야 한다.
 */

export interface ReportInput {
  /** 어느 화면에서 막히셨는지 — 주소에서 행사 번호는 지운다 */
  path: string
  version: string
  driver: 'demo' | 'supabase'
  userAgent: string
  screen: string
  online: boolean
  /** 원장님이 손으로 적으신 설명 */
  note: string
  /** 화면에서 실제로 난 오류 (가장 최근 것부터) */
  errors: string[]
  now?: string
  /** 규모만 — 이름은 담지 않는다 */
  counts?: { events?: number; students?: number; photos?: number }
}

/**
 * 주소에서 사람을 알아볼 수 있는 토막을 지운다.
 * `/events/8f3c-…/video` → `/events/[행사]/video`
 */
export function scrubPath(path: string): string {
  const clean = (path.split('?')[0] || '/').replace(/\/+$/, '') || '/'
  return clean
    .split('/')
    .map((part) => (looksLikeId(part) ? '[행사]' : part))
    .join('/')
}

function looksLikeId(part: string): boolean {
  if (part.length < 6) return false
  if (/^[0-9a-f]{8}-[0-9a-f]{4}/i.test(part)) return true
  return /^[0-9a-z-]{12,}$/i.test(part) && /\d/.test(part)
}

/** 브라우저 이름만 남긴다. 긴 UA 문자열은 원장님도 저희도 읽지 않는다 */
export function browserName(ua: string): string {
  if (/Edg\//.test(ua)) return 'Edge'
  if (/OPR\//.test(ua)) return 'Opera'
  if (/Whale\//.test(ua)) return 'Whale'
  if (/Chrome\//.test(ua)) return 'Chrome'
  if (/Firefox\//.test(ua)) return 'Firefox'
  if (/Safari\//.test(ua)) return 'Safari'
  return '알 수 없음'
}

export function osName(ua: string): string {
  if (/Windows NT 10/.test(ua)) return 'Windows 10/11'
  if (/Windows/.test(ua)) return 'Windows'
  if (/Mac OS X/.test(ua)) return 'macOS'
  if (/Android/.test(ua)) return 'Android'
  if (/iPhone|iPad/.test(ua)) return 'iPhone·iPad'
  if (/Linux/.test(ua)) return 'Linux'
  return '알 수 없음'
}

/**
 * 오류 글에 섞여 들어올 수 있는 것들을 지운다.
 * 파일 경로에는 윈도우 사용자 이름이 들어 있고(C:\Users\김원장\…),
 * data: 사진은 통째로 아이 얼굴이다.
 */
export function scrubError(line: string): string {
  return line
    .replace(/data:[a-z/+.-]+;base64,[A-Za-z0-9+/=]+/gi, '[사진]')
    .replace(/[A-Za-z]:\\Users\\[^\\\s"']+/g, 'C:\\Users\\[사용자]')
    .replace(/\/(?:home|Users)\/[^/\s"']+/g, '/home/[사용자]')
    .replace(/https?:\/\/[^\s"']*/g, (url) => scrubPath(url.replace(/^https?:\/\/[^/]+/, '')) || '[주소]')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 300)
}

/** 원장님이 복사해 보내실 글 */
export function buildReport(input: ReportInput): string {
  const at = input.now ?? new Date().toISOString()
  const lines = [
    `[${BRAND.name} — 막힌 자리]`,
    `때 : ${at.slice(0, 16).replace('T', ' ')}`,
    `화면 : ${scrubPath(input.path)}`,
    `판 : ${input.version}`,
    `저장 : ${input.driver === 'supabase' ? '서버(Supabase)' : '이 컴퓨터'}`,
    `브라우저 : ${browserName(input.userAgent)} · ${osName(input.userAgent)} · ${input.screen}`,
    `인터넷 : ${input.online ? '연결됨' : '끊김'}`,
  ]

  const counts = input.counts ?? {}
  const scale = [
    counts.events !== undefined ? `행사 ${counts.events}개` : null,
    counts.students !== undefined ? `명단 ${counts.students}줄` : null,
    counts.photos !== undefined ? `사진 ${counts.photos}장` : null,
  ].filter(Boolean)
  if (scale.length > 0) lines.push(`규모 : ${scale.join(' · ')}`)

  lines.push('', '[무엇을 하셨을 때]', input.note.trim() || '(적지 않으심)')

  const errors = input.errors.map(scrubError).filter(Boolean).slice(0, 5)
  lines.push('', '[화면에서 난 오류]', errors.length > 0 ? errors.map((e) => `· ${e}`).join('\n') : '(없음)')

  lines.push(
    '',
    '— 이 쪽지에는 아이 이름·사진·연락처가 들어 있지 않습니다. 숫자와 화면 이름만 담았습니다.',
  )
  return lines.join('\n')
}

/** 쪽지에 아이 이름이 섞여 들어가지 않았는지 마지막으로 확인한다 */
export function containsAny(report: string, words: string[]): string[] {
  return words.filter((w) => w.trim().length > 1 && report.includes(w))
}
