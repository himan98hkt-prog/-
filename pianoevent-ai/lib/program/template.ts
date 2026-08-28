import { LEVEL_LABEL, type Level } from '@/lib/types'

/**
 * 명단 양식.
 *
 * 원장님이 가장 자주 멈추는 자리가 "명단을 어떻게 넣느냐" 다.
 * 빈칸에 붙여넣으라고만 하면 무엇을 어떤 차례로 적어야 하는지 알 수 없다.
 *
 * 그래서 **채워진 양식 파일**을 내려받게 한다. 엑셀에서 열어 이름만 바꾸시면 된다.
 * 설명은 화면에도 있지만, 파일 안에도 예시 두 줄을 넣어 둔다 —
 * 파일만 열어 보셔도 무엇을 적는지 아시게.
 */

export const ROSTER_HEADERS = ['이름', '연주곡', '작곡가', '소요시간', '난이도', '비고'] as const

/** 양식 안에 넣어 두는 예시 — 지우고 쓰시면 된다 */
export const ROSTER_SAMPLE: string[][] = [
  ['김서연', '엘리제를 위하여', '베토벤', '3:30', '중급', '세 번째 무대입니다'],
  ['박지호', '즐거운 나의 집', '비숍', '1:10', '초급', '시작한 지 다섯 달'],
  ['정예린', '아라베스크', '부르크뮐러', '', '중급', ''],
]

export interface FieldGuide {
  name: string
  required: boolean
  /** 무엇을 적는가 */
  what: string
  /** 비우면 어떻게 되는가 */
  blank: string
  example: string
}

/** 칸마다 무엇을 적는지 — 화면과 양식 파일이 같은 글을 쓴다 */
export const ROSTER_FIELDS: FieldGuide[] = [
  {
    name: '이름',
    required: true,
    what: '아이 이름. 같은 이름이 두 줄이면 그 아이가 두 곡을 맡은 것으로 봅니다.',
    blank: '이름이 없는 줄은 건너뜁니다.',
    example: '김서연',
  },
  {
    name: '연주곡',
    required: false,
    what: '곡 제목. 아시는 대로 적으시면 됩니다 — 정식 제목이 아니어도 됩니다.',
    blank: '나중에 표에서 채우셔도 됩니다.',
    example: '엘리제를 위하여',
  },
  {
    name: '작곡가',
    required: false,
    what: '곡을 쓴 사람.',
    blank: '곡 사전에 있는 곡이면 알아서 채웁니다.',
    example: '베토벤',
  },
  {
    name: '소요시간',
    required: false,
    what: '연주에 걸리는 시간. `3:30` `3분30초` `210` 전부 알아봅니다.',
    blank: '난이도로 어림잡습니다. 지난 무대 기록이 있으면 그 값을 씁니다.',
    example: '3:30',
  },
  {
    name: '난이도',
    required: false,
    what: `${Object.values(LEVEL_LABEL).join(' · ')} 중 하나. 연주 순서를 짜는 기준이 됩니다.`,
    blank: '초급으로 봅니다.',
    example: '중급',
  },
  {
    name: '비고',
    required: false,
    what: '아이의 한 줄 이야기. 사회자 멘트의 재료가 됩니다.',
    blank: '멘트가 조금 담백해집니다.',
    example: '올해 처음 무대에 섭니다',
  },
]

/**
 * 난이도 칸에 적을 수 있는 말 — 화면에 그대로 보여 준다.
 *
 * 여기 적은 말은 **전부 실제로 읽혀야 한다.** 화면에서 된다고 해 놓고 안 되면
 * 원장님은 시킨 대로 하고도 막히신다. `tests/roster-template.test.ts` 가
 * 한 낱말씩 실제로 넣어 보고 확인한다.
 * (숫자 1·2·3 은 학원마다 뜻이 달라 넣지 않았다 — 지어내 읽으면 순서가 틀어진다)
 */
export const LEVEL_WORDS: Record<Level, string[]> = {
  beginner: ['초급', '기초', '입문'],
  intermediate: ['중급'],
  advanced: ['고급', '상급', '심화'],
  ensemble: ['듀엣', '앙상블', '연탄', '합주'],
}

/** 자주 하는 실수 — 화면에 미리 적어 두면 문의가 줄어든다 */
export const ROSTER_PITFALLS: { wrong: string; why: string }[] = [
  { wrong: '한 칸에 "김서연 엘리제를 위하여"', why: '이름과 곡은 **다른 칸**이어야 합니다. 엑셀에서 칸을 나눠 주세요.' },
  { wrong: '맨 윗줄에 "1학년 3반" 같은 제목', why: '머리글은 이름·연주곡… 한 줄만 두시고 나머지는 지워 주세요.' },
  { wrong: '소요시간에 "3분 정도"', why: '`3:30` 이나 `210` 처럼 숫자로 적어 주세요. 비워 두셔도 됩니다.' },
  { wrong: '빈 줄이 사이사이에', why: '빈 줄은 그냥 건너뛰니 괜찮습니다.' },
]

/**
 * CSV 양식 만들기.
 *
 * 엑셀은 UTF-8 CSV 를 그냥 열면 한글이 깨진다. 맨 앞에 BOM 을 넣어야 제대로 열린다 —
 * 원장님이 파일을 열자마자 글자가 깨져 있으면 거기서 끝이다.
 */
export function rosterTemplateCsv(): string {
  const rows = [ROSTER_HEADERS as unknown as string[], ...ROSTER_SAMPLE]
  const body = rows.map((row) => row.map(csvCell).join(',')).join('\r\n')
  return `﻿${body}\r\n`
}

function csvCell(value: string): string {
  return /[",\r\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value
}

/** 붙여넣기 칸에 넣어 주는 예시 (탭으로 나뉜 표 — 엑셀에서 복사한 모양 그대로) */
export function rosterSampleText(): string {
  return [ROSTER_HEADERS as unknown as string[], ...ROSTER_SAMPLE].map((row) => row.join('\t')).join('\n')
}
