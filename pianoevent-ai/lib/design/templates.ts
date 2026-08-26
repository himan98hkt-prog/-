export type PageSize = 'a4-portrait' | 'a4-landscape' | 'square'

export type TemplateCategory = 'poster' | 'program' | 'invite' | 'stage'

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
