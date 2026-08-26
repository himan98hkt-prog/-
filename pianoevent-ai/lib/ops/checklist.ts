import { formatShortDate } from '@/lib/format'
import type { EventRecord } from '@/lib/types'

/**
 * 연주회 준비 체크리스트.
 *
 * 매번 빠뜨리는 것은 정해져 있다 — 조율 예약, 프로그램 인쇄 부수, 상장 이름 오타,
 * 대기실 물품, 사진 담당자. 행사 날짜만 있으면 언제 무엇을 해야 하는지 계산할 수 있다.
 */

export interface ChecklistTask {
  id: string
  title: string
  detail: string
  /** 특히 자주 빠뜨리는 항목 — 인쇄물에서 강조한다 */
  critical?: boolean
}

export interface ChecklistGroup {
  id: string
  /** D-30 처럼 남은 일수 (0 = 당일, 양수 = 종료 후) */
  offset_days: number
  label: string
  /** 실제 날짜 (2026.09.02) */
  date: string
  tasks: ChecklistTask[]
}

interface GroupSpec {
  id: string
  offset_days: number
  label: string
  tasks: ChecklistTask[]
}

const SPECS: GroupSpec[] = [
  {
    id: 'd30',
    offset_days: -30,
    label: 'D-30 · 큰 것부터 잠급니다',
    tasks: [
      { id: 'venue', title: '공연장 대관 확정', detail: '계약금, 이용 가능 시간(리허설 포함), 주차 대수를 문서로 남깁니다.', critical: true },
      { id: 'tuner', title: '피아노 조율 예약', detail: '행사 1~2일 전으로 잡습니다. 당일 조율은 리허설과 겹칩니다.', critical: true },
      { id: 'date-notice', title: '학부모에게 날짜 공지', detail: '이 시점에 알려야 가족 일정이 잡힙니다.' },
      { id: 'repertoire', title: '학생별 연주곡 확정', detail: '난이도와 길이를 함께 적어 두면 순서표가 바로 나옵니다.' },
      { id: 'poster', title: '포스터 제작 · 게시', detail: '학원 현관, 엘리베이터, 단톡방에 올립니다.' },
    ],
  },
  {
    id: 'd14',
    offset_days: -14,
    label: 'D-14 · 만드는 것들',
    tasks: [
      { id: 'program', title: '연주 순서표 확정', detail: '한 학생이 연속으로 두 번 오르지 않는지, 총 러닝타임이 90분을 넘지 않는지 봅니다.', critical: true },
      { id: 'script', title: '사회자 대본 준비', detail: '곡 해설과 학생 소개를 미리 뽑아 두면 당일 목소리가 편안해집니다.' },
      { id: 'award', title: '상장 · 부상 준비', detail: '이름 한 글자 오타가 가장 많이 나는 곳입니다. 명단과 대조하세요.', critical: true },
      { id: 'photo', title: '사진·영상 담당 정하기', detail: '학부모에게 맡기면 놓칩니다. 담당자를 한 명 지정하세요.', critical: true },
      { id: 'flower', title: '꽃다발 · 간식 주문', detail: '수량은 참석 회신 인원 기준으로 잡습니다.' },
    ],
  },
  {
    id: 'd7',
    offset_days: -7,
    label: 'D-7 · 인원과 동선',
    tasks: [
      { id: 'rsvp', title: '참석 회신 마감 안내', detail: '좌석과 프로그램 부수를 정하려면 이 숫자가 필요합니다.', critical: true },
      { id: 'seats', title: '좌석 수 확인', detail: '참석 인원보다 10% 여유를 둡니다.' },
      { id: 'rehearsal', title: '리허설 시간 공지', detail: '학생별 도착 시각을 나눠 주면 대기실이 붐비지 않습니다.' },
      { id: 'dress', title: '의상 안내', detail: '페달을 밟아야 하니 굽 높은 신발은 피하도록 알려 줍니다.' },
      { id: 'nametag', title: '좌석 이름표 인쇄', detail: '대기 순서대로 붙여 두면 인솔이 훨씬 빨라집니다.' },
    ],
  },
  {
    id: 'd1',
    offset_days: -1,
    label: 'D-1 · 인쇄와 짐',
    tasks: [
      { id: 'print', title: '프로그램 · 입장권 · 상장 인쇄', detail: '참석 인원보다 20% 넉넉하게 뽑습니다.', critical: true },
      { id: 'final-check', title: '명단 최종 점검', detail: '이름·곡명 오타, 빠진 학생이 없는지 순서표를 소리 내어 읽어 봅니다.', critical: true },
      { id: 'route', title: '오시는 길 · 주차 안내 발송', detail: '지도 링크와 주차 가능 대수를 함께 보냅니다.' },
      { id: 'kit', title: '준비물 가방 싸기', detail: '연장선, 테이프, 여분 프로그램, 물티슈, 반짇고리, 밴드, 보면대.' },
      { id: 'charge', title: '기기 충전', detail: '촬영용 휴대폰·카메라 배터리와 보조배터리.' },
    ],
  },
  {
    id: 'day',
    offset_days: 0,
    label: '당일',
    tasks: [
      { id: 'arrive', title: '2시간 전 도착', detail: '피아노 위치, 의자 높이, 조명, 마이크를 직접 확인합니다.', critical: true },
      { id: 'rehearse', title: '리허설 진행', detail: '곡 전체가 아니라 입·퇴장과 인사, 첫 두 마디만 확인합니다.' },
      { id: 'brief', title: '스태프 브리핑', detail: '인솔·촬영·안내 데스크·응급 담당을 다시 확인합니다.' },
      { id: 'house', title: '객석 개방 30분 전 준비', detail: '순서지 배부 위치와 안내 문구를 정리합니다.' },
      { id: 'water', title: '대기실 물·휴지 배치', detail: '긴장한 아이들이 가장 먼저 찾는 두 가지입니다.' },
    ],
  },
  {
    id: 'after',
    offset_days: 2,
    label: '종료 후 · 이틀 안에',
    tasks: [
      { id: 'photos', title: '사진 공유', detail: '늦어질수록 감흥이 식습니다. 이틀 안에 링크를 보냅니다.', critical: true },
      { id: 'thanks', title: '감사 문자 발송', detail: '참석하지 못한 가정에도 사진과 함께 보냅니다.' },
      { id: 'award-left', title: '상장 미수령자 전달', detail: '결석한 학생의 상장을 다음 수업에 건넵니다.' },
      { id: 'settle', title: '대관 정산 · 영수증 보관', detail: '지출 내역을 그날 바로 정리해 둡니다.' },
      { id: 'retro', title: '한 줄 회고 남기기', detail: '다음 연주회에서 바꿀 것 한 가지만 적어 둡니다. 이 기록이 가장 값집니다.' },
    ],
  },
]

function shiftDays(iso: string, days: number): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return new Date(d.getTime() + days * 86_400_000).toISOString()
}

export function buildChecklist(event: EventRecord): ChecklistGroup[] {
  return SPECS.map((spec) => ({
    id: spec.id,
    offset_days: spec.offset_days,
    label: spec.label,
    date: formatShortDate(shiftDays(event.event_at, spec.offset_days)),
    tasks: spec.tasks,
  }))
}

export function checklistTaskCount(groups: ChecklistGroup[]): number {
  return groups.reduce((sum, group) => sum + group.tasks.length, 0)
}

/** 오늘 기준으로 지금 손대야 하는 묶음 — 행사 화면 상단에 보여 준다 */
export function currentGroup(groups: ChecklistGroup[], event: EventRecord, now = new Date()): ChecklistGroup | null {
  const eventTime = new Date(event.event_at).getTime()
  if (Number.isNaN(eventTime)) return null
  const daysLeft = Math.floor((eventTime - now.getTime()) / 86_400_000)

  if (daysLeft < 0) return groups.find((g) => g.id === 'after') ?? null
  if (daysLeft === 0) return groups.find((g) => g.id === 'day') ?? null
  if (daysLeft <= 1) return groups.find((g) => g.id === 'd1') ?? null
  if (daysLeft <= 7) return groups.find((g) => g.id === 'd7') ?? null
  if (daysLeft <= 14) return groups.find((g) => g.id === 'd14') ?? null
  return groups.find((g) => g.id === 'd30') ?? null
}
