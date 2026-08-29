/**
 * 종이 미리보기 — 인쇄 대화상자를 열기 전에 "몇 장이 나오는지" 를 먼저 보여 준다.
 *
 * 원장님이 잉크와 종이를 버리시는 자리는 늘 같다.
 *  · 순서지가 두 장으로 넘어가는 줄 모르고 100부를 뽑는다
 *  · 배율이 "용지에 맞춤" 으로 잡혀 여백이 크게 남는다
 *  · "배경 그래픽" 이 꺼져 있어 색이 하나도 안 나온다
 * 세 가지 다 **뽑고 나서** 아신다. 그래서 뽑기 전에 화면에서 종이 모양 그대로
 * 보여 주고, 대화상자에서 만질 것을 딱 세 줄로 적어 둔다.
 */

/** 화면에 그릴 때 쓰는 종이 크기 (96dpi 기준 픽셀) */
export interface Paper {
  id: PaperId
  label: string
  /** 인쇄 CSS 의 @page size 에 그대로 넣는 값 */
  css: string
  w: number
  h: number
}

export type PaperId = 'a4-portrait' | 'a4-landscape' | 'a5-portrait' | 'b5-portrait' | 'letter-portrait'

export const PAPERS: Record<PaperId, Paper> = {
  'a4-portrait': { id: 'a4-portrait', label: 'A4 세로', css: 'A4 portrait', w: 794, h: 1123 },
  'a4-landscape': { id: 'a4-landscape', label: 'A4 가로', css: 'A4 landscape', w: 1123, h: 794 },
  'a5-portrait': { id: 'a5-portrait', label: 'A5 세로', css: 'A5 portrait', w: 559, h: 794 },
  'b5-portrait': { id: 'b5-portrait', label: 'B5 세로', css: 'B5 portrait', w: 665, h: 944 },
  'letter-portrait': { id: 'letter-portrait', label: '레터 세로', css: 'Letter portrait', w: 816, h: 1056 },
}

export const PAPER_LIST: Paper[] = Object.values(PAPERS)

export function getPaper(id: string | null | undefined): Paper {
  return PAPERS[(id ?? '') as PaperId] ?? PAPERS['a4-portrait']
}

/**
 * 내용 높이가 종이 몇 장인지.
 *
 * 여백을 뺀 "글이 들어가는 높이" 로 나눈다. 0 장은 없다 — 빈 종이도 한 장은 나온다.
 */
export function sheetsNeeded(contentHeightPx: number, paper: Paper, marginPx = 0): number {
  const usable = paper.h - marginPx * 2
  if (!Number.isFinite(contentHeightPx) || contentHeightPx <= 0 || usable <= 0) return 1
  return Math.max(1, Math.ceil(contentHeightPx / usable - 0.001))
}

/**
 * 내용이 종이 끝에 걸치는 자리 — 미리보기에 점선으로 긋는다.
 * "여기서 잘립니다" 를 눈으로 보시게 하는 것이 목적이다.
 */
export function pageBreakOffsets(contentHeightPx: number, paper: Paper, marginPx = 0): number[] {
  const usable = paper.h - marginPx * 2
  const sheets = sheetsNeeded(contentHeightPx, paper, marginPx)
  const cuts: number[] = []
  for (let i = 1; i < sheets; i += 1) cuts.push(i * usable)
  return cuts
}

/** 미리보기를 창 너비에 맞추는 배율 (1 을 넘기지 않는다 — 확대는 오히려 헷갈린다) */
export function fitScale(availableWidthPx: number, paper: Paper): number {
  if (!Number.isFinite(availableWidthPx) || availableWidthPx <= 0) return 1
  return Math.min(1, availableWidthPx / paper.w)
}

/**
 * 인쇄 대화상자에서 만질 것.
 * 브라우저마다 낱말이 다르므로 둘 다 적는다 — 원장님은 있는 낱말을 찾으신다.
 */
export const PRINT_CHECKLIST = [
  {
    what: '대상 (프린터)',
    how: '종이로 뽑으시려면 프린터를, 파일로 두시려면 "PDF로 저장" 을 고르세요.',
  },
  {
    what: '배율',
    how: '"100%" 또는 "기본값". "용지에 맞춤" 으로 두면 여백이 크게 남습니다.',
  },
  {
    what: '여백',
    how: '"없음". 여백은 디자인 안에 이미 잡혀 있습니다.',
  },
  {
    what: '배경 그래픽',
    how: '켜 주세요. 이걸 끄면 색과 무늬가 하나도 안 나옵니다. (더보기 안에 있습니다)',
  },
] as const

/** 몇 장을 몇 부 뽑으면 종이가 몇 장인지 — 100부 뽑기 전에 아셔야 한다 */
export function totalSheets(sheetsPerCopy: number, copies: number): number {
  const perCopy = Math.max(1, Math.round(sheetsPerCopy))
  const n = Math.max(1, Math.round(copies))
  return perCopy * n
}

/* ─────────────────────────────────────────────────────────────────
   인쇄소에 맡기실 때 — 재단선과 물림 여백
   ───────────────────────────────────────────────────────────────── */

/**
 * 인쇄소는 종이를 크게 뽑아 **잘라 냅니다.** 자르는 자리가 종이마다 1~2mm 씩
 * 어긋나기 때문에, 가장자리까지 색이 차 있는 디자인은 사방 3mm 를 더 그려 둡니다
 * (이것을 물림 여백·bleed 라고 합니다). 그 여백은 잘려 나가고, 잘릴 자리를
 * 알려 주는 것이 재단선(crop mark)입니다.
 *
 * 원장님이 이 낱말들을 아셔야 할 이유는 없습니다. **[인쇄소용]** 한 번이면 됩니다.
 */
export const BLEED_MM = 3

/** 재단선 길이 — 인쇄소가 보는 표준값 */
export const CROP_MM = 4

/** 96dpi 픽셀 → mm (인쇄 CSS 는 mm 로 적어야 실물 크기가 맞는다) */
export function pxToMm(px: number): number {
  return Math.round((px / 96) * 25.4 * 10) / 10
}

export function mmToPx(mm: number): number {
  return Math.round((mm / 25.4) * 96)
}

/** 물림 여백을 더한 인쇄면 크기 — `@page size` 에 그대로 넣는다 */
export function bleedPageCss(widthPx: number, heightPx: number, bleedMm = BLEED_MM): string {
  return `${pxToMm(widthPx) + bleedMm * 2}mm ${pxToMm(heightPx) + bleedMm * 2}mm`
}

/**
 * 첫 장만 뽑아 보기.
 *
 * 인쇄 설정을 네 줄로 적어 두어도, 맞게 하셨는지는 뽑아 봐야 아신다.
 * 100부를 걸기 전에 **한 장만** 뽑아 보시게 한다. 종이 한 장이 100장을 살린다.
 */
export const FIRST_ONLY_CLASS = 'print-first-only'

/** 첫 장에 담기는 높이 — 여기서 잘라 두면 둘째 장이 딸려 나오지 않는다 */
export function firstPageClipPx(paper: Paper, marginPx = 0): number {
  // 브라우저마다 반올림이 조금씩 달라 딱 맞추면 빈 둘째 장이 붙는다. 조금 덜 잡는다.
  return Math.max(1, paper.h - marginPx * 2 - 8)
}


/* ─────────────────────────────────────────────────────────────────
   양면 인쇄 · 인쇄물 글씨 크기
   ───────────────────────────────────────────────────────────────── */

/**
 * 양면으로 뽑아야 뜻이 있는 인쇄물이 있다 — 반 접는 책자가 그렇다.
 *
 * 그런데 인쇄 대화상자의 양면 설정에는 **넘기는 방향**이 함께 있다.
 * "긴 쪽 넘기기" 로 두면 뒷장이 거꾸로 찍혀 접었을 때 속장이 뒤집힌다.
 * 원장님은 다 뽑고 접어 보신 뒤에야 아신다. 그래서 미리 적어 둔다.
 */
export const DUPLEX_HINT = {
  what: '양면 인쇄',
  how: '"양면 인쇄" 를 켜고 **"짧은 쪽 넘기기"** 를 고르세요. "긴 쪽" 으로 두면 뒷장이 거꾸로 찍힙니다.',
} as const

/** 이 양식이 양면으로 뽑아야 하는 것인가 */
export function needsDuplex(templateIds: string[]): boolean {
  return templateIds.some((id) => id.startsWith('booklet-'))
}

/**
 * 인쇄물 글씨 크기.
 *
 * 화면 글씨는 머리띠에서 키우실 수 있는데, 정작 **종이**가 안 보이신다는 분이 계신다.
 * 관객석은 어둡고, 순서지는 작다. 종이에서도 키울 수 있어야 한다.
 *
 * 다만 키우면 줄이 늘어 장수가 는다. 그래서 몇 장이 되는지 함께 보여 준다.
 */
export type PrintTextSize = 'normal' | 'big' | 'huge'

export const PRINT_TEXT_SIZES: { id: PrintTextSize; label: string; scale: number }[] = [
  { id: 'normal', label: '보통', scale: 1 },
  { id: 'big', label: '크게', scale: 1.15 },
  { id: 'huge', label: '아주 크게', scale: 1.3 },
]

export function getPrintTextSize(id: string | null | undefined): { id: PrintTextSize; label: string; scale: number } {
  return PRINT_TEXT_SIZES.find((s) => s.id === id) ?? PRINT_TEXT_SIZES[0]
}

/**
 * 글씨를 키우면 내용이 길어져 장수가 는다.
 * 글씨가 1.15배면 줄 높이도 1.15배라, 세로로 차지하는 자리도 그만큼 는다.
 */
export function sheetsAtTextSize(contentHeightPx: number, paper: Paper, marginPx: number, id: PrintTextSize): number {
  return sheetsNeeded(contentHeightPx * getPrintTextSize(id).scale, paper, marginPx)
}

/**
 * 뽑기 직전 **마지막 한 줄.**
 *
 * 인쇄 대화상자는 브라우저 것이라 우리가 못 고친다. 거기서 잘못 눌러 종이를 버리는
 * 자리는 늘 같은 넷이다 — 종이 · 장수 · 색 · 양면. 그래서 누르시기 **전에**
 * 이 넷을 큰 글씨로 한 번 되짚어 드린다. 다르면 그때 인쇄 창에서 고치시면 된다.
 *
 * 숫자를 새로 지어내지 않는다. 위 띠에서 이미 세어 둔 값을 그대로 옮긴다.
 */
export interface PrintSummaryRow {
  what: string
  value: string
}

export function printSummary(input: {
  paperLabel: string
  sheets: number
  copies?: number
  duplex?: boolean
  /** 색을 빼고 뽑아도 되는 인쇄물인가 (진행표·체크리스트처럼 글만 있는 것) */
  grayOk?: boolean
}): PrintSummaryRow[] {
  const copies = Math.max(1, Math.round(input.copies ?? 1))
  const total = totalSheets(input.sheets, copies)
  return [
    { what: '종이', value: input.paperLabel },
    {
      what: '장수',
      value: copies > 1 ? `${input.sheets}장 × ${copies}부 = ${total.toLocaleString('ko-KR')}장` : `${input.sheets}장`,
    },
    { what: '색', value: input.grayOk ? '흑백으로 뽑으셔도 됩니다' : '컬러' },
    { what: '양면', value: input.duplex ? '예 · 짧은 쪽 넘기기' : '아니요 (한 면씩)' },
  ]
}

/**
 * 종이를 **몸으로 아는 단위**로 바꿔 준다.
 *
 * "1,200장" 은 숫자일 뿐이라 크기가 안 그려진다. A4 한 박스는 2,500장(5연)이고
 * 한 연(포장 한 묶음)은 500장이다. "한 박스의 절반" 이라고 하면 그 자리에서 아신다.
 * 프린터에 그만큼 넣어 두셨는지, 잉크가 버티는지를 **뽑기 전에** 가늠하시라는 것이다.
 */
export const REAM_SHEETS = 500
export const BOX_SHEETS = REAM_SHEETS * 5

/** 이만큼부터는 "종이가 꽤 드는구나" 를 아셔야 한다 */
export const BULK_FROM_SHEETS = 100

export function paperBulkNote(totalSheets: number): string | null {
  if (totalSheets < BULK_FROM_SHEETS) return null
  if (totalSheets < REAM_SHEETS) {
    const part = Math.max(1, Math.round(REAM_SHEETS / totalSheets))
    return `A4 한 연(500장)의 ${part}분의 1쯤입니다. 프린터에 종이를 채워 두세요.`
  }
  if (totalSheets < BOX_SHEETS) {
    const reams = Math.round((totalSheets / REAM_SHEETS) * 10) / 10
    return `A4 ${reams}연(한 연 500장)입니다. 프린터에 그만큼 있는지 먼저 보세요.`
  }
  const boxes = Math.round((totalSheets / BOX_SHEETS) * 10) / 10
  return `A4 ${boxes}박스(한 박스 2,500장)입니다. 학원 프린터로는 벅찹니다 — 인쇄소를 알아보세요.`
}

/**
 * **잉크는 종이보다 먼저 떨어진다.**
 *
 * 원장님은 종이만 세신다. 그런데 실제로 연주회 전날 밤에 멈추는 것은 잉크다.
 * 색을 꽉 채운 포스터는 글만 있는 문서와 잉크 드는 양이 열 배쯤 다르다.
 *
 * 정확한 장수는 프린터마다 다르므로 **어림수**로만 말씀드리고, 그렇다고 밝힌다.
 * 제조사가 말하는 "한 통에 몇 장" 은 종이의 5%만 칠했을 때 값이라, 포스터에는
 * 그대로 못 쓴다. 그 사실을 아시는 것만으로도 여분을 챙기신다.
 */
export const INK_FROM_SHEETS = 30

export function inkNote(totalSheets: number, opts: { heavy?: boolean } = {}): string | null {
  if (totalSheets < INK_FROM_SHEETS) return null
  if (!opts.heavy) {
    return totalSheets >= REAM_SHEETS
      ? `글 위주라 잉크는 덜 듭니다. 그래도 ${totalSheets.toLocaleString('ko-KR')}장이면 검정 잉크는 미리 봐 두세요.`
      : null
  }
  // 색을 꽉 채우는 인쇄물 — 제조사 값(5% 칠했을 때)의 서너 배로 닳는다
  if (totalSheets < 100) {
    return '색을 꽉 채운 인쇄물이라 잉크가 빨리 닳습니다. 컬러 잉크가 얼마나 남았는지 먼저 보세요.'
  }
  return `색을 꽉 채운 인쇄물 ${totalSheets.toLocaleString('ko-KR')}장이면 컬러 잉크 한 통으로는 모자랍니다. 여분을 두시거나, 인쇄소에 맡기시는 편이 쌉니다.`
}

/**
 * 색을 꽉 채우는 갈래인가.
 *
 * 포스터 · 프로그램(표지) · 초대·홍보는 종이 전체가 색이다.
 * 진행 문서(`ops`)와 무대용 카드(`stage`)는 글 위주라 잉크가 훨씬 덜 든다.
 */
export function isHeavyInk(categories: string[]): boolean {
  return categories.some((c) => c === 'poster' || c === 'program' || c === 'invite')
}

/** 한 줄로 — "A4 세로 · 12장 · 컬러 · 양면 아님" */
export function printSummaryLine(rows: PrintSummaryRow[]): string {
  return rows.map((row) => row.value).join(' · ')
}
