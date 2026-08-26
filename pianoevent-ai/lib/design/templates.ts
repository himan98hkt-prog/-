export type PageSize = 'a4-portrait' | 'a4-landscape' | 'square'

export type TemplateCategory = 'poster' | 'program' | 'invite' | 'stage' | 'ops'

export interface TemplateDef {
  id: string
  name: string
  description: string
  category: TemplateCategory
  page: PageSize
  /** 순서표가 확정되어야 의미가 있는 양식 */
  needsProgram: boolean
  /** 학생 수만큼 반복 인쇄되는 양식(이름표·상장) */
  perStudent: boolean
  /** 한 장에 몇 개가 배치되는지 — 안내 문구용 */
  perSheet?: number
}

/** 96dpi 기준 픽셀 크기. A4 210×297mm */
export const PAGE_PX: Record<PageSize, { w: number; h: number; label: string; css: string }> = {
  'a4-portrait': { w: 794, h: 1123, label: 'A4 세로', css: 'A4 portrait' },
  'a4-landscape': { w: 1123, h: 794, label: 'A4 가로', css: 'A4 landscape' },
  square: { w: 900, h: 900, label: '정사각 (SNS)', css: '900px 900px' },
}

export const DESIGN_TEMPLATES: TemplateDef[] = [
  {
    id: 'poster-classic',
    name: '클래식 포스터',
    description: '가운데 정렬에 액자 장식. 학원 현관과 엘리베이터에 붙이는 가장 무난한 형태.',
    category: 'poster',
    page: 'a4-portrait',
    needsProgram: false,
    perStudent: false,
  },
  {
    id: 'poster-modern',
    name: '모던 포스터',
    description: '큰 날짜와 비대칭 여백. 사진 없이도 시선을 끄는 편집형 포스터.',
    category: 'poster',
    page: 'a4-portrait',
    needsProgram: false,
    perStudent: false,
  },
  {
    id: 'poster-photo',
    name: '사진 포스터',
    description: '학원 전경이나 지난 연주회 사진을 크게 싣는 포스터. 사진 한 장이 설명을 대신합니다.',
    category: 'poster',
    page: 'a4-portrait',
    needsProgram: false,
    perStudent: false,
  },
  {
    id: 'poster-fullbleed',
    name: '전면 사진 포스터',
    description: '사진이 지면 전체를 채우고 글씨가 그 위에 얹힙니다. 실제 촬영 사진이 있을 때 가장 실감 납니다.',
    category: 'poster',
    page: 'a4-portrait',
    needsProgram: false,
    perStudent: false,
  },
  {
    id: 'poster-program',
    name: '포스터 + 출연진',
    description: '포스터 한 장에 연주자 이름과 곡을 모두 담습니다. 게시용 겸 안내용.',
    category: 'poster',
    page: 'a4-portrait',
    needsProgram: true,
    perStudent: false,
  },
  {
    id: 'program-cover',
    name: '프로그램 표지',
    description: '관객에게 나눠 주는 순서지의 표지. 인사말을 함께 싣습니다.',
    category: 'program',
    page: 'a4-portrait',
    needsProgram: false,
    perStudent: false,
  },
  {
    id: 'program-inner',
    name: '프로그램 순서지',
    description: '연주 순서와 곡목. 테마 색과 서체가 표지와 이어집니다.',
    category: 'program',
    page: 'a4-portrait',
    needsProgram: true,
    perStudent: false,
  },
  {
    id: 'program-bifold',
    name: '반접지 프로그램',
    description: 'A4 가로 한 장을 반으로 접으면 표지와 순서가 되는 4면 구성.',
    category: 'program',
    page: 'a4-landscape',
    needsProgram: true,
    perStudent: false,
  },
  {
    id: 'ticket-strip',
    name: '입장권 3매',
    description: 'A4 한 장에 입장권 세 장. 절취선을 따라 자르면 됩니다.',
    category: 'invite',
    page: 'a4-portrait',
    needsProgram: false,
    perStudent: false,
    perSheet: 3,
  },
  {
    id: 'social-card',
    name: 'SNS 카드',
    description: '카카오톡·인스타그램에 올리는 정사각 안내 이미지.',
    category: 'invite',
    page: 'square',
    needsProgram: false,
    perStudent: false,
  },
  {
    id: 'thankyou-card',
    name: '감사 카드 2매',
    description: '연주가 끝난 뒤 학부모에게 드리는 카드. A4 한 장에 두 장.',
    category: 'stage',
    page: 'a4-portrait',
    needsProgram: false,
    perStudent: false,
    perSheet: 2,
  },
  {
    id: 'cue-sheet',
    name: '당일 진행표',
    description: '도착·리허설·객석 개방·연주·시상·정리까지 시각과 담당이 적힌 큐시트. 사회자와 스태프가 손에 듭니다.',
    category: 'ops',
    page: 'a4-portrait',
    needsProgram: true,
    perStudent: false,
  },
  {
    id: 'checklist',
    name: '준비 체크리스트',
    description: 'D-30부터 종료 후까지 무엇을 언제 해야 하는지. 행사 날짜에 맞춰 날짜가 자동으로 계산됩니다.',
    category: 'ops',
    page: 'a4-portrait',
    needsProgram: false,
    perStudent: false,
  },
  {
    id: 'certificate',
    name: '참가 상장',
    description: '학생 이름이 자동으로 들어간 상장. 인원수만큼 이어서 인쇄됩니다.',
    category: 'stage',
    page: 'a4-landscape',
    needsProgram: true,
    perStudent: true,
  },
  {
    id: 'nametag',
    name: '좌석 이름표',
    description: '연주 순서와 이름이 적힌 이름표. A4 한 장에 여덟 개.',
    category: 'stage',
    page: 'a4-portrait',
    needsProgram: true,
    perStudent: true,
    perSheet: 8,
  },
]

export const DEFAULT_TEMPLATE_ID = 'poster-classic'

export function getTemplate(id: string | null | undefined): TemplateDef {
  return DESIGN_TEMPLATES.find((t) => t.id === id) ?? DESIGN_TEMPLATES[0]
}

export const CATEGORY_LABEL: Record<TemplateCategory, string> = {
  poster: '포스터',
  program: '프로그램·순서지',
  invite: '초대·홍보',
  stage: '행사 당일',
  ops: '진행 문서',
}

export function templatesByCategory(): { category: TemplateCategory; items: TemplateDef[] }[] {
  return (Object.keys(CATEGORY_LABEL) as TemplateCategory[]).map((category) => ({
    category,
    items: DESIGN_TEMPLATES.filter((t) => t.category === category),
  }))
}

/** 인쇄하면 몇 장이 나오는지 — 원장에게 미리 알려 준다 */
export function sheetCount(templateId: string, studentCount: number): number {
  const template = DESIGN_TEMPLATES.find((t) => t.id === templateId)
  if (!template?.perStudent) return 1
  const perSheet = template.perSheet ?? 1
  return Math.max(1, Math.ceil(studentCount / perSheet))
}

/**
 * 한 벌 인쇄 — 원장이 매번 양식을 하나씩 골라 인쇄하던 것을 묶는다.
 * 인쇄 대화상자는 용지 크기를 한 번만 정할 수 있으므로 한 벌 안의 양식은 용지가 같아야 한다.
 */
export interface PrintPack {
  id: string
  name: string
  description: string
  templates: string[]
}

export const PRINT_PACKS: PrintPack[] = [
  {
    id: 'audience',
    name: '관객용 한 벌',
    description: '포스터 · 프로그램 표지 · 순서지 · 입장권을 한 번에 인쇄합니다.',
    templates: ['poster-classic', 'program-cover', 'program-inner', 'ticket-strip'],
  },
  {
    id: 'day',
    name: '당일 운영 한 벌',
    description: '진행표 · 준비 체크리스트 · 좌석 이름표를 한 번에 인쇄합니다.',
    templates: ['cue-sheet', 'checklist', 'nametag'],
  },
]

export function getPack(id: string | null | undefined): PrintPack | null {
  return PRINT_PACKS.find((p) => p.id === id) ?? null
}

/** 한 벌 안에서 실제로 인쇄할 양식 — 첫 양식과 용지가 같은 것만 남긴다 */
export function packTemplates(pack: PrintPack): TemplateDef[] {
  const defs = pack.templates.map((id) => getTemplate(id))
  const page = defs[0]?.page
  return defs.filter((def) => def.page === page)
}
