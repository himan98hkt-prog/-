/**
 * "이렇게 읽었습니다" — 붙여넣은 명단을 넣기 **전에** 보여 주는 확인 쪽지.
 *
 * 지금까지는 붙여넣고 [명단에 추가] 를 누른 다음에야 표를 보고 잘못을 아셨다.
 * 12명인 줄 알았는데 11명이 들어갔다거나, 이름과 곡이 한 칸에 붙어 있어
 * "김서연 엘리제를 위하여" 가 통째로 이름이 되어 있다거나.
 *
 * 그래서 넣기 전에 사람 말로 정리해 드린다. 숫자만 던지면 원장님이 해석하셔야 한다.
 */
import type { RosterParseResult } from '@/lib/program/roster'
import { LEVEL_LABEL } from '@/lib/types'

export interface ReceiptLine {
  /** 'ok' 는 그대로 두셔도 되는 것, 'warn' 은 한 번 보셔야 하는 것 */
  tone: 'ok' | 'warn'
  text: string
}

export interface RosterReceipt {
  /** 실제로 명단에 들어갈 줄 수 */
  count: number
  /** 사람 수 (한 아이가 두 곡이면 줄은 둘, 사람은 하나) */
  people: number
  lines: ReceiptLine[]
  /** 하나라도 살펴보실 것이 있는지 */
  needsLook: boolean
}

/** 이름이 이상하게 긴 줄 — 칸을 안 나누고 통째로 넣으신 것이다 */
const SUSPICIOUS_NAME = /\s/

export function buildReceipt(parsed: RosterParseResult): RosterReceipt {
  const lines: ReceiptLine[] = []
  const rows = parsed.rows
  const people = new Set(rows.map((r) => r.student_name)).size

  lines.push({
    tone: 'ok',
    text:
      people === rows.length
        ? `아이 ${rows.length}명을 읽었습니다.`
        : `아이 ${people}명 · 무대 ${rows.length}번을 읽었습니다. (두 곡 맡은 아이가 있습니다)`,
  })

  lines.push({
    tone: 'ok',
    text: parsed.headerDetected
      ? '첫 줄은 머리글로 보고 건너뛰었습니다.'
      : '머리글이 없어 왼쪽부터 이름 · 연주곡 · 작곡가 · 소요시간 · 난이도 · 비고 차례로 읽었습니다.',
  })

  const noPiece = rows.filter((r) => !r.piece_title.trim())
  if (noPiece.length > 0) {
    lines.push({
      tone: 'warn',
      text: `연주곡이 빈 아이가 ${noPiece.length}명입니다 — ${names(noPiece.map((r) => r.student_name))}. 표에서 채우시면 됩니다.`,
    })
  }

  if (parsed.autofilled.length > 0) {
    const what = new Set(parsed.autofilled.flatMap((a) => a.fields))
    lines.push({
      tone: 'ok',
      text: `곡 사전이 ${parsed.autofilled.length}곡의 ${[...what].join(' · ')}를 대신 채웠습니다.`,
    })
  }

  const guessedLevel = rows.filter((r) => r.level === 'beginner').length
  if (guessedLevel === rows.length && rows.length > 1) {
    lines.push({
      tone: 'warn',
      text: `난이도가 전부 ${LEVEL_LABEL.beginner}으로 들어갔습니다. 난이도 칸이 비었거나 못 알아본 낱말입니다 — 연주 순서를 짜는 기준이라 한 번 보세요.`,
    })
  }

  const longNames = rows.filter((r) => SUSPICIOUS_NAME.test(r.student_name) && r.student_name.length > 6)
  if (longNames.length > 0) {
    lines.push({
      tone: 'warn',
      text: `이름이 "${longNames[0].student_name}" 처럼 읽힌 줄이 ${longNames.length}개 있습니다. 이름과 곡이 한 칸에 붙어 있는 것 같습니다 — 엑셀에서 칸을 나눠 주세요.`,
    })
  }

  const skipped = parsed.errors.filter((e) => e.includes('건너뛰'))
  if (skipped.length > 0) {
    lines.push({ tone: 'warn', text: `${skipped.length}줄은 이름이 없어 건너뛰었습니다.` })
  }

  return { count: rows.length, people, lines, needsLook: lines.some((l) => l.tone === 'warn') }
}

/** "김서연 · 박지호 외 3명" — 다 늘어놓으면 오히려 안 읽으신다 */
function names(list: string[], limit = 3): string {
  if (list.length <= limit) return list.join(' · ')
  return `${list.slice(0, limit).join(' · ')} 외 ${list.length - limit}명`
}
