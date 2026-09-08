/**
 * 인쇄소 견적용 요약.
 *
 * 원장님이 인쇄소에 전화를 거시면 저쪽에서 이렇게 물으신다 —
 * "몇 절이요? 종이는요? 몇 부요? 양면이요?"
 * 원장님은 그 낱말을 모르시고, 모르시니 전화를 못 거신다. 그래서 결국 집 프린터로
 * 100장을 뽑으신다.
 *
 * 여기서 그 답을 미리 적어 드린다. 종이 이름과 평량은 **연주회 인쇄물에서 흔히
 * 쓰는 것**으로 권해 드리는 것이고, 인쇄소에서 다른 것을 권하면 그쪽이 맞다.
 * 종이 한 장을 들고 전화를 거실 수 있으면 그것으로 충분하다.
 */
import type { TemplateCategory, TemplateDef } from '@/lib/design/templates'
import { PAGE_PX, sheetCount } from '@/lib/design/templates'
import { pxToMm } from '@/lib/print/paper'

export interface QuoteRow {
  name: string
  /** "A4 세로 (210 × 297mm)" */
  paper: string
  /** 한 부에 몇 장 */
  sheets: number
  copies: number
  total: number
  /** 권해 드리는 종이 */
  stock: string
  /** 인쇄소에 함께 말씀하실 것 */
  note: string
}

/**
 * 갈래마다 흔히 쓰는 종이.
 * 평량(g)이 클수록 두껍다 — 포스터는 빳빳해야 벽에 붙고, 순서지는 넘기기 좋아야 한다.
 */
const STOCK: Record<TemplateCategory, { stock: string; note: string }> = {
  poster: { stock: '스노우지 200g (반광)', note: '단면 컬러. 벽에 붙이실 거면 코팅은 안 하셔도 됩니다' },
  program: { stock: '모조지 120g', note: '단면 컬러. 여러 장이면 가운데 스테이플러(중철) 를 물어보세요' },
  invite: { stock: '아트지 250g', note: '단면 컬러. 손에 들고 계시는 것이라 조금 두꺼운 편이 좋습니다' },
  stage: { stock: '모조지 100g', note: '단면 컬러. 당일 한 번 쓰고 마는 것이라 얇아도 됩니다' },
  ops: { stock: '모조지 80g (복사지)', note: '흑백도 됩니다. 진행용이라 색이 없어도 무방합니다' },
}

/** "A4 세로 (210 × 297mm)" — 인쇄소는 mm 로 말한다 */
export function paperText(page: keyof typeof PAGE_PX): string {
  const box = PAGE_PX[page]
  return `${box.label} (${Math.round(pxToMm(box.w))} × ${Math.round(pxToMm(box.h))}mm)`
}

export function quoteRow(template: TemplateDef, studentCount: number, copies: number): QuoteRow {
  const sheets = sheetCount(template.id, studentCount)
  const n = Math.max(1, Math.round(copies))
  const paperInfo = STOCK[template.category]
  return {
    name: template.name,
    paper: paperText(template.page),
    sheets,
    copies: n,
    total: sheets * n,
    stock: paperInfo.stock,
    note: paperInfo.note,
  }
}

export function quoteRows(templates: TemplateDef[], studentCount: number, copies: number): QuoteRow[] {
  return templates.map((t) => quoteRow(t, studentCount, copies))
}

/** 인쇄소가 가장 먼저 묻는 것 — 다 합쳐 몇 장인가 */
export function quoteTotal(rows: QuoteRow[]): number {
  return rows.reduce((sum, row) => sum + row.total, 0)
}

/**
 * 전화로 읽으실 한 줄.
 * 인쇄소에 전화를 거는 것이 목적이지, 견적서를 쓰는 것이 목적이 아니다.
 */
export function quoteSentence(row: QuoteRow): string {
  return `${row.name} — ${row.paper}, ${row.stock}, ${row.copies}부 (총 ${row.total}장)`
}

/** 복사해서 문자로 보내실 글 */
export function quoteText(title: string, rows: QuoteRow[]): string {
  const lines = [`[${title}] 인쇄 견적 문의`, '']
  for (const row of rows) lines.push(`· ${quoteSentence(row)}`)
  lines.push('', `합계 ${quoteTotal(rows)}장`, '', '· 재단선과 물림 여백 3mm 를 넣은 PDF 로 보내 드리겠습니다.')
  return lines.join('\n')
}
