export type PageSize = 'a4-portrait' | 'a4-landscape' | 'square' | 'story' | 'banner' | 'banner-wide'

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
  story: { w: 720, h: 1280, label: '세로 스토리 (9:16)', css: '720px 1280px' },
  banner: { w: 500, h: 1500, label: 'X배너 시안 (1:3)', css: '500px 1500px' },
  'banner-wide': { w: 1500, h: 500, label: '가로 현수막 시안 (3:1)', css: '1500px 500px' },
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
  /* ── 명품 연주회 포스터 ────────────────────────────────────────────
     예술회관·콩쿠르 포스터를 뜯어보면 늘 같다 — 큰 그림 하나, 아주 큰 제목,
     시원한 여백, 어둠에서 빛으로 번지는 깊이. 그 문법으로 짠 여덟 장이다.
     고르시기만 하면 되고, 손보실 것은 없다. */
  {
    id: 'gala-piano',
    name: '그랜드피아노',
    description: '어두운 무대 위 그랜드피아노. 가장 널리 쓰이는 연주회 포스터의 얼굴입니다.',
    category: 'poster',
    page: 'a4-portrait',
    needsProgram: false,
    perStudent: false,
  },
  {
    id: 'gala-keys',
    name: '건반 무대',
    description: '건반이 종이 아래를 가로지릅니다. 보는 사람이 피아노 앞에 앉은 자리에 섭니다.',
    category: 'poster',
    page: 'a4-portrait',
    needsProgram: false,
    perStudent: false,
  },
  {
    id: 'gala-spotlight',
    name: '무대 조명',
    description: '위에서 내려오는 빛 한 줄기 안에 제목이 섭니다. 제목이 가장 큰 판입니다.',
    category: 'poster',
    page: 'a4-portrait',
    needsProgram: false,
    perStudent: false,
  },
  {
    id: 'gala-arch',
    name: '무대 아치',
    description: '커튼이 걷힌 무대가 제목을 감쌉니다. 격식 있는 정기 연주회에.',
    category: 'poster',
    page: 'a4-portrait',
    needsProgram: false,
    perStudent: false,
  },
  {
    id: 'gala-editorial',
    name: '큰 날짜 편집',
    description: '날짜를 아주 큰 숫자로 세운 비대칭 판. 밝은 바탕에 현대적인 느낌.',
    category: 'poster',
    page: 'a4-portrait',
    needsProgram: false,
    perStudent: false,
  },
  {
    id: 'gala-photo',
    name: '사진 전면 (고급)',
    description: '학원 사진이 종이를 가득 채우고 그 위에 글이 얹힙니다. 사진이 없으면 무대 조명으로 나옵니다.',
    category: 'poster',
    page: 'a4-portrait',
    needsProgram: false,
    perStudent: false,
  },
  {
    id: 'gala-laurel',
    name: '월계관 (콩쿠르)',
    description: '월계관 안에 연도를 앉힌 콩쿠르 문법. 시상이 있는 연주회에 잘 맞습니다.',
    category: 'poster',
    page: 'a4-portrait',
    needsProgram: false,
    perStudent: false,
  },
  {
    id: 'gala-minimal',
    name: '여백',
    description: '비운 자리가 격을 만듭니다. 제목 하나로 끝내는 미술관 포스터 문법.',
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

  {
    id: 'poster-typographic',
    name: '타이포 포스터',
    description: '사진 없이 글자만으로 지면을 채웁니다. 제목이 길거나 학원 이름이 강한 곳에.',
    category: 'poster',
    page: 'a4-portrait',
    needsProgram: false,
    perStudent: false,
  },
  {
    id: 'poster-duo',
    name: '사진 2단 포스터',
    description: '위는 사진, 아래는 정보 두 칸. 사진 한 장으로 안정된 구성을 만듭니다.',
    category: 'poster',
    page: 'a4-portrait',
    needsProgram: false,
    perStudent: false,
  },
  {
    id: 'program-notes',
    name: '곡 해설 순서지',
    description: '연주 순서마다 곡 해설을 함께 싣습니다. 관객이 무엇을 듣는지 알고 듣게 됩니다.',
    category: 'program',
    page: 'a4-portrait',
    needsProgram: true,
    perStudent: false,
  },
  {
    id: 'program-trifold',
    name: '3단 접지 프로그램',
    description: 'A4 가로를 세 번 접는 6면 구성. 표지·인사말·순서·안내가 한 장에 들어갑니다.',
    category: 'program',
    page: 'a4-landscape',
    needsProgram: true,
    perStudent: false,
  },
  {
    id: 'invitation-card',
    name: '초대장 카드 2매',
    description: '손으로 건네는 초대장. A4 한 장에 두 장이 나옵니다.',
    category: 'invite',
    page: 'a4-portrait',
    needsProgram: false,
    perStudent: false,
    perSheet: 2,
  },
  {
    id: 'story-card',
    name: 'SNS 세로 스토리',
    description: '인스타그램·카카오 스토리용 9:16 세로 이미지.',
    category: 'invite',
    page: 'story',
    needsProgram: false,
    perStudent: false,
  },
  {
    id: 'banner-stand',
    name: 'X배너 시안',
    description: '입구에 세우는 배너 시안. 인쇄소에 그대로 넘길 수 있는 1:3 비율입니다.',
    category: 'invite',
    page: 'banner',
    needsProgram: false,
    perStudent: false,
  },
  {
    id: 'seating-chart',
    name: '좌석 배치도',
    description: '참석 회신을 가정 단위로 앉힌 배치도. 접수처에 붙여 두면 안내가 끝납니다.',
    category: 'stage',
    page: 'a4-landscape',
    needsProgram: false,
    perStudent: false,
  },
  {
    id: 'backstage-board',
    name: '대기 순서판',
    description: '무대 뒤 벽에 붙이는 큰 글씨 순서판. 아이들이 스스로 자기 차례를 봅니다.',
    category: 'stage',
    page: 'a4-portrait',
    needsProgram: true,
    perStudent: false,
  },
  {
    id: 'photo-zone',
    name: '포토존 보드',
    description: '연주가 끝난 뒤 사진 찍는 자리에 세우는 안내판. 학원 이름과 날짜가 사진에 남습니다.',
    category: 'stage',
    page: 'a4-landscape',
    needsProgram: false,
    perStudent: false,
  },
  {
    id: 'award-sheet',
    name: '시상 명단',
    description: '호명 순서와 상장 종류가 적힌 시상용 낭독지. 사회자와 원장이 한 장씩 듭니다.',
    category: 'stage',
    page: 'a4-portrait',
    needsProgram: true,
    perStudent: false,
  },
  {
    id: 'mc-script',
    name: '사회자 대본',
    description: '오프닝부터 클로징까지 큰 글씨 대본. 무대 조명 아래에서도 읽힙니다.',
    category: 'ops',
    page: 'a4-portrait',
    needsProgram: true,
    perStudent: false,
  },
  {
    id: 'rehearsal-sheet',
    name: '리허설 시간표',
    description: '조별 소집 시각과 학생별 무대 시각. 당일 아침 계산을 대신합니다.',
    category: 'ops',
    page: 'a4-portrait',
    needsProgram: true,
    perStudent: false,
  },
  {
    id: 'attendance-sheet',
    name: '접수 확인표',
    description: '도착 체크·좌석 안내·특이사항을 적는 접수처용 표.',
    category: 'ops',
    page: 'a4-portrait',
    needsProgram: true,
    perStudent: false,
  },
  {
    id: 'budget-sheet',
    name: '예산·정산표',
    description: '항목별 예산과 1인당 원가, 권장 참가비까지 계산된 표.',
    category: 'ops',
    page: 'a4-portrait',
    needsProgram: false,
    perStudent: false,
  },
  {
    id: 'parent-notice',
    name: '학부모 안내문',
    description: '시간·장소·주차·관람 예절을 한 장에. 같은 질문을 스무 번 받지 않게 됩니다.',
    category: 'ops',
    page: 'a4-portrait',
    needsProgram: false,
    perStudent: false,
  },
  {
    id: 'student-notice',
    name: '학생 준비 안내문',
    description: '복장·준비물·도착 시각·무대 인사법. 아이가 들고 가서 냉장고에 붙입니다.',
    category: 'ops',
    page: 'a4-portrait',
    needsProgram: false,
    perStudent: false,
  },

  {
    id: 'stage-map',
    name: '무대 배치도',
    description: '피아노·의자·사회자 자리·조명을 그린 배치도. 대관처와 스태프에게 그대로 보냅니다.',
    category: 'stage',
    page: 'a4-landscape',
    needsProgram: false,
    perStudent: false,
  },
  {
    id: 'banner-horizontal',
    name: '가로 현수막 시안',
    description: '무대 뒤에 거는 가로 현수막. 인쇄소에 그대로 넘길 수 있는 3:1 비율입니다.',
    category: 'invite',
    page: 'banner-wide',
    needsProgram: false,
    perStudent: false,
  },
  {
    id: 'signage',
    name: '안내 표지판 4매',
    description: '“대기실 →”, “객석 입구”, “접수처”, “화장실”. 당일 길을 묻는 일이 사라집니다.',
    category: 'stage',
    page: 'a4-portrait',
    needsProgram: false,
    perStudent: false,
    perSheet: 4,
  },
  {
    id: 'practice-log',
    name: '연습 기록표',
    description: '행사 4주 전부터 날짜가 찍힌 연습 체크표. 학생이 들고 가서 냉장고에 붙입니다.',
    category: 'ops',
    page: 'a4-portrait',
    needsProgram: false,
    perStudent: false,
  },
  {
    id: 'performer-cards',
    name: '연주자 소개 카드',
    description: '이름·곡·한 줄 소개가 담긴 카드. 로비 게시판이나 포토존 옆에 붙입니다.',
    category: 'stage',
    page: 'a4-portrait',
    needsProgram: true,
    perStudent: true,
    perSheet: 4,
  },
  {
    id: 'guestbook',
    name: '응원 메시지 카드',
    description: '학부모가 아이에게 한 줄 남기는 카드. 연주가 끝나면 아이가 가져갑니다.',
    category: 'stage',
    page: 'a4-portrait',
    needsProgram: false,
    perStudent: false,
    perSheet: 4,
  },
  {
    id: 'thanks-letter',
    name: '감사장',
    description: '대관처·반주자·도움 주신 분께 드리는 감사장. 이름만 채우면 됩니다.',
    category: 'stage',
    page: 'a4-landscape',
    needsProgram: false,
    perStudent: false,
  },
  {
    id: 'after-notice',
    name: '종료 후 안내문',
    description: '사진·영상 전달 방법과 다음 행사 안내. 연주회가 끝나고 하루 안에 보냅니다.',
    category: 'ops',
    page: 'a4-portrait',
    needsProgram: false,
    perStudent: false,
  },
  /* ── 책자형 · 티켓형 열 가지 ──────────────────────────────────────
     원장님들이 가장 많이 물으신 두 가지다 — "책자로 만들 수 있나요",
     "입장권을 여러 장 뽑고 싶은데요". 전부 집 프린터 한 대로 끝나게 짰다. */
  {
    id: 'booklet-cover',
    name: '책자 겉장 (반 접기)',
    description: 'A4 가로를 반 접으면 A5 책자 겉장이 됩니다. 접는 자리에 점선을 그어 두었습니다.',
    category: 'program',
    page: 'a4-landscape',
    needsProgram: false,
    perStudent: false,
  },
  {
    id: 'booklet-inner',
    name: '책자 속장 (반 접기)',
    description: '왼쪽에 인사말, 오른쪽에 연주 순서. 겉장과 등을 맞대어 뽑으면 책자가 됩니다.',
    category: 'program',
    page: 'a4-landscape',
    needsProgram: true,
    perStudent: false,
  },
  {
    id: 'program-large',
    name: '큰 글씨 순서지',
    description: '이름과 곡을 줄을 나눠 크게. 어르신 손님이 많은 연주회에.',
    category: 'program',
    page: 'a4-portrait',
    needsProgram: true,
    perStudent: false,
  },
  {
    id: 'program-memo',
    name: '순서지 + 메모 칸',
    description: '곡마다 한 줄 적는 칸이 있습니다. 관객이 소감을 적어 가시게.',
    category: 'program',
    page: 'a4-portrait',
    needsProgram: true,
    perStudent: false,
  },
  {
    id: 'ticket-sheet',
    name: '입장권 4매 (반쪽 떼기)',
    description: 'A4 한 장에 넉 장. 오른쪽 반쪽을 접수처에서 떼어 두면 참석 수가 세집니다.',
    category: 'invite',
    page: 'a4-portrait',
    needsProgram: false,
    perStudent: false,
    perSheet: 4,
  },
  {
    id: 'seat-ticket',
    name: '좌석권 6매',
    description: '좌석 번호를 손으로 적는 칸이 있는 입장권. A4 한 장에 여섯 장.',
    category: 'invite',
    page: 'a4-portrait',
    needsProgram: false,
    perStudent: false,
    perSheet: 6,
  },
  {
    id: 'performer-tags',
    name: '연주자 이름표',
    description: '대기실 의자에 붙이는 이름표. 한 장에 여덟 장씩 나옵니다.',
    category: 'stage',
    page: 'a4-portrait',
    needsProgram: true,
    perStudent: true,
    perSheet: 8,
  },
  {
    id: 'cue-cards',
    name: '무대 순서 카드',
    description: '무대 옆 스태프가 손에 드는 카드. 순서·이름·시각이 큼직하게.',
    category: 'ops',
    page: 'a4-portrait',
    needsProgram: true,
    perStudent: true,
    perSheet: 6,
  },
  {
    id: 'thankyou-bookmark',
    name: '감사 책갈피 4매',
    description: '돌아가시는 길에 나눠 드리는 책갈피. A4 한 장에 넉 장.',
    category: 'invite',
    page: 'a4-portrait',
    needsProgram: false,
    perStudent: false,
    perSheet: 4,
  },
  {
    id: 'stage-divider',
    name: '부 표지 (1부 · 2부)',
    description: '부가 바뀔 때 세워 두는 판. 부마다 한 장씩 뽑아 두세요.',
    category: 'stage',
    page: 'a4-landscape',
    needsProgram: true,
    perStudent: false,
  },
  {
    id: 'projector-card',
    name: '빔프로젝터 연결 카드',
    description: '노트북을 스크린에 띄우는 법과 챙길 것. 당일 가방에 한 장 넣어 가세요.',
    category: 'ops',
    page: 'a4-portrait',
    needsProgram: false,
    perStudent: false,
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
    description: '진행표 · 준비 체크리스트 · 빔프로젝터 연결 카드 · 좌석 이름표를 한 번에 인쇄합니다.',
    templates: ['cue-sheet', 'checklist', 'projector-card', 'nametag'],
  },
  {
    id: 'notice',
    name: '안내문 한 벌',
    description: '학부모 안내문 · 학생 준비 안내문 · 리허설 시간표를 한 번에 인쇄합니다.',
    templates: ['parent-notice', 'student-notice', 'rehearsal-sheet'],
  },
  {
    id: 'mc',
    name: '사회자 한 벌',
    description: '사회자 대본 · 당일 진행표 · 시상 명단을 한 번에 인쇄합니다.',
    templates: ['mc-script', 'cue-sheet', 'award-sheet'],
  },
  {
    id: 'reception',
    name: '접수처 한 벌',
    description: '좌석 배치도 · 포토존 보드 · 무대 배치도를 한 번에 인쇄합니다. (A4 가로)',
    templates: ['seating-chart', 'photo-zone', 'stage-map'],
  },
  {
    id: 'venue',
    name: '현장 안내 한 벌',
    description: '안내 표지판 · 연주자 소개 카드 · 응원 메시지 카드를 한 번에 인쇄합니다.',
    templates: ['signage', 'performer-cards', 'guestbook'],
  },
  /* ── 새 양식으로 묶은 한 벌 ─────────────────────────────────────
     한 벌 안의 양식은 **용지가 같아야** 한다 — 인쇄 대화상자는 용지를 한 번만 정한다.
     그래서 A4 가로짜리(책자·부 표지)와 세로짜리를 섞지 않는다. */
  {
    id: 'booklet',
    name: '책자 한 벌 (A4 가로 · 양면)',
    description: '겉장과 속장을 한 번에. 양면으로 뽑아 반 접으면 A5 책자가 됩니다.',
    templates: ['booklet-cover', 'booklet-inner'],
  },
  {
    id: 'front-desk',
    name: '접수·배부 한 벌',
    description: '입장권 4매 · 좌석권 6매 · 감사 책갈피를 한 번에 인쇄합니다.',
    templates: ['ticket-sheet', 'seat-ticket', 'thankyou-bookmark'],
  },
  {
    id: 'backstage',
    name: '무대 뒤 한 벌',
    description: '무대 순서 카드 · 연주자 이름표를 한 번에. 스태프와 대기실에서 씁니다.',
    templates: ['cue-cards', 'performer-tags'],
  },
  {
    id: 'guest-friendly',
    name: '손님 배려 한 벌',
    description: '큰 글씨 순서지 · 메모 칸 순서지. 어르신 손님과 소감을 적어 가실 분께.',
    templates: ['program-large', 'program-memo'],
  },
  {
    id: 'gala',
    name: '예술회관 한 벌',
    description: '명품 포스터 · 프로그램 표지 · 순서지 · 입장권. 예술회관 연주회처럼 보이는 한 벌입니다.',
    templates: ['gala-piano', 'program-cover', 'program-inner', 'ticket-strip'],
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
