import { formatEventDate, formatShortDate } from '@/lib/format'
import type { Academy, EventRecord, ProgramPlan } from '@/lib/types'

/**
 * 학부모에게 보내는 안내 문구.
 *
 * 원장이 매번 처음부터 쓰는 네 통이 있다 — 첫 공지, 사흘 전 알림, 당일 아침, 끝나고 감사.
 * 행사 정보로 채워 두고 복사만 하면 되게 한다. 문자·카카오톡에 그대로 붙여넣는 길이로 맞춘다.
 */

export type MessageKind = 'invite' | 'remind' | 'today' | 'thanks'

export interface MessageTemplate {
  kind: MessageKind
  title: string
  /** 언제 보내는지 */
  when: string
  body: string
}

export interface MessageInput {
  academy: Academy
  event: EventRecord
  plan: ProgramPlan
  /** 초대장 전체 주소 (https://... /e/{id}). 없으면 링크 문구를 뺀다 */
  inviteUrl?: string
  /** 사진 공유 링크 (종료 후 문자) */
  photoUrl?: string
}

const clean = (text: string) =>
  text
    .split('\n')
    .map((line) => line.trimEnd())
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()

export function buildMessages(input: MessageInput): MessageTemplate[] {
  const { academy, event, plan } = input
  const when = formatEventDate(event.event_at)
  const place = event.venue ? `\n장소: ${event.venue}` : ''
  const link = input.inviteUrl ? `\n\n초대장과 참석 회신은 아래에서 부탁드립니다.\n${input.inviteUrl}` : ''
  const runtime = plan.total_sec > 0 ? `약 ${Math.round(plan.total_sec / 60)}분` : '약 한 시간'

  return [
    {
      kind: 'invite',
      title: '① 첫 공지 · 초대',
      when: '행사 3~4주 전',
      body: clean(`[${academy.name}] ${event.title} 안내

안녕하세요, ${academy.name}입니다.
아이들이 한 해 동안 준비한 무대에 학부모님을 모십니다.

일시: ${when}${place}
소요: ${runtime} 예정

좌석 준비를 위해 참석 여부를 미리 알려 주시면 감사하겠습니다.${link}`),
    },
    {
      kind: 'remind',
      title: '② 사흘 전 알림',
      when: 'D-3',
      body: clean(`[${academy.name}] ${event.title}이 사흘 앞으로 다가왔습니다.

일시: ${when}${place}

· 아이는 편한 신발로 와 주세요. 페달을 밟아야 합니다.
· 시작 20분 전까지 도착해 주시면 여유 있게 앉으실 수 있습니다.
· 아직 참석 여부를 알려 주지 않으셨다면 오늘까지 부탁드립니다.${link}`),
    },
    {
      kind: 'today',
      title: '③ 당일 아침',
      when: '행사 당일 오전',
      body: clean(`[${academy.name}] 오늘 ${event.title}이 열립니다.

시간: ${when}${place}

· 연주자는 시작 30분 전까지 대기실로 와 주세요.
· 공연 중에는 휴대전화를 무음으로 해 주시고, 촬영 시 플래시는 꺼 주세요.
· 곡이 끝난 뒤 박수로 아이들의 용기에 답해 주시면 큰 힘이 됩니다.

오늘 아이의 무대를 함께 기다려 주셔서 감사합니다.`),
    },
    {
      kind: 'thanks',
      title: '④ 끝나고 감사',
      when: '종료 후 이틀 안',
      body: clean(`[${academy.name}] ${event.title}을 마쳤습니다.

${formatShortDate(event.event_at)} 무대에 오른 ${plan.items.length || ''}명의 연주자 모두 한 곡을 끝까지 마쳤습니다.
끝까지 자리를 지켜 주신 학부모님께 깊이 감사드립니다.

아이가 무대에서 느낀 것을 오늘 한 번 물어봐 주세요. 그 대답이 다음 한 해의 연습을 이끕니다.${
        input.photoUrl ? `\n\n사진은 아래에서 받으실 수 있습니다.\n${input.photoUrl}` : ''
      }`),
    },
  ]
}

/** 문자 발송 화면에서 쓰는 글자 수 (SMS 90바이트 / LMS 2000바이트 기준 안내용) */
export function messageBytes(body: string): number {
  return new TextEncoder().encode(body).length
}

export function messageKindLabel(kind: MessageKind): string {
  switch (kind) {
    case 'invite':
      return '초대'
    case 'remind':
      return '사흘 전'
    case 'today':
      return '당일'
    case 'thanks':
      return '감사'
  }
}
