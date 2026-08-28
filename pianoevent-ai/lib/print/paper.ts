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
