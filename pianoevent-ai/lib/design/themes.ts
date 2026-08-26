/**
 * 연주회 인쇄물 테마.
 *
 * 학원마다 색과 분위기가 다르다. 원장이 테마 하나를 고르면 포스터·순서표·초대장·티켓·상장이
 * 모두 같은 옷을 입는다. 색과 서체, 장식, 프레임을 한 벌로 묶어 두는 이유다.
 */

export type OrnamentId =
  | 'keys'
  | 'deco'
  | 'floral'
  | 'leaf'
  | 'stars'
  | 'spotlight'
  | 'holly'
  | 'moon'
  | 'wave'
  /** 금박 이중선 — 격식 있는 초청장 느낌 */
  | 'foil'
  /** 리라(고대 현악기) — 고전 음악회의 상징 */
  | 'lyre'
  /** 잎 갈랜드 — 단정한 화환 */
  | 'garland'
  /** 색종이와 음표 — 축하 분위기 */
  | 'confetti'
  | 'none'

export type FrameId = 'deco' | 'thin' | 'double' | 'rounded' | 'ribbon' | 'none'

/** 로고를 어떤 모양으로 앉힐지 — 테마 성격에 맞춘다 */
export type LogoShape =
  /** 이미지 그대로 */
  | 'plain'
  /** 원형으로 잘라 넣기 */
  | 'circle'
  /** 원형 + 얇은 금/강조색 테두리 */
  | 'ring'
  /** 밝은 판 위에 올려 어두운 배경에서도 보이게 */
  | 'plate'

/** 사진을 어떤 모양으로 앉힐지 */
export type PhotoShape =
  /** 직각 사각형 */
  | 'rect'
  /** 모서리를 둥글린 사각형 */
  | 'rounded'
  /** 원형 */
  | 'circle'
  /** 위쪽이 둥근 아치 — 무대 커튼 같은 인상 */
  | 'arch'

export interface DesignTheme {
  id: string
  name: string
  /** 어떤 학원·행사에 어울리는지 한 줄 */
  tagline: string
  mood: string[]
  palette: {
    /** 종이 바탕 */
    paper: string
    /** 종이 위 은은한 두 번째 면 */
    paperAlt: string
    ink: string
    muted: string
    accent: string
    accentSoft: string
    line: string
    /** 제목 밴드 등 강한 블록 */
    band: string
    bandInk: string
  }
  fonts: { display: string; body: string }
  ornament: OrnamentId
  frame: FrameId
  /** 배경 질감 */
  texture: 'none' | 'grain' | 'glow' | 'gradient'
  /** 로고 자리 표현 방식과 기본 높이(px, 96dpi 기준) */
  logo: { shape: LogoShape; height: number }
  /** 사진 자리 표현 방식과 톤 보정 */
  photo: { shape: PhotoShape; treatment?: PhotoTreatment }
}

/**
 * 사진 톤 보정 — 학원마다 사진 밝기가 제각각이라 테마 색과 겉돌기 쉽다.
 * natural(그대로) · bright(밝게) · warm(따뜻하게) · soft(부드럽게) · mono(흑백)
 */
export type PhotoTreatment = 'natural' | 'bright' | 'warm' | 'soft' | 'mono'

export const PHOTO_FILTER: Record<PhotoTreatment, string> = {
  natural: 'none',
  bright: 'brightness(1.06) saturate(1.04)',
  warm: 'sepia(0.12) saturate(1.08) brightness(1.02)',
  soft: 'contrast(0.94) brightness(1.04) saturate(0.96)',
  mono: 'grayscale(1) contrast(1.05)',
}

const SERIF_CLASSIC = "'Nanum Myeongjo', 'Apple SD Gothic Neo', serif"
const SERIF_SOFT = "'Gowun Batang', 'Nanum Myeongjo', serif"
const SERIF_THIN = "'Song Myung', 'Nanum Myeongjo', serif"
const SERIF_NOTO = "'Noto Serif KR', 'Nanum Myeongjo', serif"
const SANS = "'Noto Sans KR', Pretendard, 'Apple SD Gothic Neo', sans-serif"
const ROUND = "'Jua', 'Noto Sans KR', sans-serif"
const HAND = "'Gaegu', 'Noto Sans KR', cursive"

export const DESIGN_THEMES: DesignTheme[] = [
  {
    id: 'daylight-studio',
    name: '데이라이트 스튜디오',
    tagline: '흰 바탕에 사진이 주인공. 실제 사진을 크게 쓰고 싶을 때 가장 잘 맞습니다.',
    mood: ['밝음', '사진', '깨끗'],
    palette: {
      paper: '#ffffff',
      paperAlt: '#f4f5f7',
      ink: '#1c1f24',
      muted: '#6d737d',
      accent: '#2f6f6a',
      accentSoft: '#e3efed',
      line: '#e2e5ea',
      band: '#1c1f24',
      bandInk: '#ffffff',
    },
    fonts: { display: SANS, body: SANS },
    ornament: 'wave',
    frame: 'none',
    texture: 'none',
    logo: { shape: 'plain', height: 54 },
    photo: { shape: 'rect', treatment: 'natural' },
  },
  {
    id: 'sunlit-ivory',
    name: '햇살 아이보리',
    tagline: '창으로 빛이 드는 연습실 같은 밝기. 낮 시간 연주회에.',
    mood: ['밝음', '따뜻', '부드러움'],
    palette: {
      paper: '#fffdf8',
      paperAlt: '#fdf4e5',
      ink: '#403528',
      muted: '#8b7c66',
      accent: '#c9932f',
      accentSoft: '#f7e9cd',
      line: '#eadcc2',
      band: '#c9932f',
      bandInk: '#fffdf8',
    },
    fonts: { display: SERIF_SOFT, body: SANS },
    ornament: 'garland',
    frame: 'thin',
    texture: 'none',
    logo: { shape: 'ring', height: 60 },
    photo: { shape: 'rounded', treatment: 'warm' },
  },
  {
    id: 'blossom-white',
    name: '블라썸 화이트',
    tagline: '흰 바탕에 옅은 분홍. 사진이 화사하게 보입니다.',
    mood: ['밝음', '화사', '깨끗'],
    palette: {
      paper: '#ffffff',
      paperAlt: '#fdf3f4',
      ink: '#3d2f33',
      muted: '#8a757b',
      accent: '#c96b7a',
      accentSoft: '#fbe4e7',
      line: '#f0dde1',
      band: '#c96b7a',
      bandInk: '#ffffff',
    },
    fonts: { display: SERIF_THIN, body: SANS },
    ornament: 'floral',
    frame: 'rounded',
    texture: 'none',
    logo: { shape: 'circle', height: 62 },
    photo: { shape: 'rounded', treatment: 'bright' },
  },
  {
    id: 'sky-linen',
    name: '스카이 리넨',
    tagline: '맑은 하늘빛과 리넨 질감. 야외·주말 낮 공연에.',
    mood: ['밝음', '산뜻', '가벼움'],
    palette: {
      paper: '#fbfcfe',
      paperAlt: '#eaf1f8',
      ink: '#22303f',
      muted: '#63768a',
      accent: '#3f7fb0',
      accentSoft: '#dcebf6',
      line: '#d3e0ec',
      band: '#22303f',
      bandInk: '#fbfcfe',
    },
    fonts: { display: SERIF_SOFT, body: SANS },
    ornament: 'wave',
    frame: 'thin',
    texture: 'grain',
    logo: { shape: 'circle', height: 58 },
    photo: { shape: 'rect', treatment: 'bright' },
  },
  {
    id: 'classic-navy',
    name: '클래식 네이비',
    tagline: '정통 정기 연주회. 격식 있는 공연장, 학부모 초청 행사에.',
    mood: ['정통', '격식', '차분'],
    palette: {
      paper: '#fbfaf6',
      paperAlt: '#f2efe6',
      ink: '#141d33',
      muted: '#5d6478',
      accent: '#b3892f',
      accentSoft: '#e8dcc0',
      line: '#c9c2ae',
      band: '#141d33',
      bandInk: '#f8f5ec',
    },
    fonts: { display: SERIF_CLASSIC, body: SANS },
    ornament: 'deco',
    frame: 'double',
    texture: 'grain',
    logo: { shape: 'ring', height: 62 },
    photo: { shape: 'arch' },
  },
  {
    id: 'ivory-gold',
    name: '아이보리 골드',
    tagline: '얇은 금선과 여백. 소규모 살롱 연주회에 어울립니다.',
    mood: ['우아', '여백', '고급'],
    palette: {
      paper: '#fdfcf8',
      paperAlt: '#f6f1e4',
      ink: '#3c3527',
      muted: '#8a8069',
      accent: '#c2a35c',
      accentSoft: '#efe5cd',
      line: '#ddd2b6',
      band: '#c2a35c',
      bandInk: '#fffdf7',
    },
    fonts: { display: SERIF_THIN, body: SANS },
    ornament: 'keys',
    frame: 'thin',
    texture: 'none',
    logo: { shape: 'ring', height: 58 },
    photo: { shape: 'arch' },
  },
  {
    id: 'blush-romance',
    name: '블러시 로맨스',
    tagline: '따뜻하고 부드러운 인상. 유아·초등 학부모 초청에 반응이 좋습니다.',
    mood: ['따뜻', '부드러움', '로맨틱'],
    palette: {
      paper: '#fffaf8',
      paperAlt: '#fdeee9',
      ink: '#4a2230',
      muted: '#96707b',
      accent: '#c25b70',
      accentSoft: '#f7d9dd',
      line: '#eec9cd',
      band: '#c25b70',
      bandInk: '#fff6f4',
    },
    fonts: { display: SERIF_SOFT, body: SANS },
    ornament: 'floral',
    frame: 'rounded',
    texture: 'none',
    logo: { shape: 'circle', height: 64 },
    photo: { shape: 'rounded' },
  },
  {
    id: 'forest-calm',
    name: '포레스트 캄',
    tagline: '차분한 초록. 작은 음악회, 정원·카페 공연에.',
    mood: ['차분', '자연', '단정'],
    palette: {
      paper: '#fbfcf8',
      paperAlt: '#eef2e7',
      ink: '#1e3025',
      muted: '#5f7566',
      accent: '#3f6b4a',
      accentSoft: '#d8e5d5',
      line: '#c3d2be',
      band: '#274634',
      bandInk: '#f4f8f0',
    },
    fonts: { display: SERIF_SOFT, body: SANS },
    ornament: 'leaf',
    frame: 'thin',
    texture: 'none',
    logo: { shape: 'circle', height: 60 },
    photo: { shape: 'rounded' },
  },
  {
    id: 'modern-mono',
    name: '모던 미니멀',
    tagline: '큰 타이포와 흑백. 세련된 인상을 원하는 학원에.',
    mood: ['모던', '심플', '대담'],
    palette: {
      paper: '#ffffff',
      paperAlt: '#f2f2f2',
      ink: '#111111',
      muted: '#6b6b6b',
      accent: '#111111',
      accentSoft: '#e6e6e6',
      line: '#d4d4d4',
      band: '#111111',
      bandInk: '#ffffff',
    },
    fonts: { display: SANS, body: SANS },
    ornament: 'wave',
    frame: 'none',
    texture: 'none',
    logo: { shape: 'plain', height: 52 },
    photo: { shape: 'rect' },
  },
  {
    id: 'pastel-kids',
    name: '파스텔 키즈',
    tagline: '민트와 살구빛. 유아·저학년 발표회에.',
    mood: ['귀여움', '밝음', '아이'],
    palette: {
      paper: '#fdfdfb',
      paperAlt: '#e9f6f2',
      ink: '#28453f',
      muted: '#6f8b85',
      accent: '#ef9a7a',
      accentSoft: '#ffe3d5',
      line: '#c9e4dc',
      band: '#63bfae',
      bandInk: '#ffffff',
    },
    fonts: { display: ROUND, body: SANS },
    ornament: 'stars',
    frame: 'rounded',
    texture: 'none',
    logo: { shape: 'circle', height: 68 },
    photo: { shape: 'circle' },
  },
  {
    id: 'crayon-play',
    name: '크레용 놀이',
    tagline: '손글씨 느낌. 시즌 특강 발표, 놀이형 미니 콘서트에.',
    mood: ['활발', '손글씨', '놀이'],
    palette: {
      paper: '#fffdf5',
      paperAlt: '#fff3d6',
      ink: '#3a2f1d',
      muted: '#8a7a58',
      accent: '#e8873b',
      accentSoft: '#ffe0bd',
      line: '#f0d9a8',
      band: '#f4b63f',
      bandInk: '#3a2f1d',
    },
    fonts: { display: HAND, body: SANS },
    ornament: 'stars',
    frame: 'rounded',
    texture: 'none',
    logo: { shape: 'circle', height: 68 },
    photo: { shape: 'circle' },
  },
  {
    id: 'midnight-stage',
    name: '미드나잇 스테이지',
    tagline: '어두운 무대와 스포트라이트. 고학년·콩쿠르 입상자 무대에.',
    mood: ['드라마틱', '무대', '집중'],
    palette: {
      paper: '#171922',
      paperAlt: '#1f2330',
      ink: '#f1efe9',
      muted: '#a2a7b8',
      accent: '#d8c07a',
      accentSoft: '#39405a',
      line: '#39405a',
      band: '#d8c07a',
      bandInk: '#171922',
    },
    fonts: { display: SERIF_NOTO, body: SANS },
    ornament: 'spotlight',
    frame: 'thin',
    texture: 'glow',
    logo: { shape: 'plate', height: 60 },
    photo: { shape: 'rect' },
  },
  {
    id: 'noir-gold',
    name: '느와르 골드',
    tagline: '검정 바탕에 금박. 정기 연주회를 가장 격식 있게 보이게 합니다.',
    mood: ['고급', '격식', '드라마틱'],
    palette: {
      paper: '#12100f',
      paperAlt: '#1c1917',
      ink: '#f5eee1',
      muted: '#a99e8c',
      accent: '#d4af5f',
      accentSoft: '#3a3226',
      line: '#3f382c',
      band: '#d4af5f',
      bandInk: '#12100f',
    },
    fonts: { display: SERIF_NOTO, body: SANS },
    ornament: 'foil',
    frame: 'double',
    texture: 'glow',
    logo: { shape: 'plate', height: 62 },
    photo: { shape: 'rect' },
  },
  {
    id: 'burgundy-velvet',
    name: '버건디 벨벳',
    tagline: '무대 커튼 같은 진홍. 큰 홀에서 여는 정기 연주회에.',
    mood: ['고급', '무대', '깊이'],
    palette: {
      paper: '#3a1220',
      paperAlt: '#4a1a2a',
      ink: '#f8ece8',
      muted: '#cfa8ad',
      accent: '#dcae66',
      accentSoft: '#5c2634',
      line: '#5f2a38',
      band: '#dcae66',
      bandInk: '#3a1220',
    },
    fonts: { display: SERIF_CLASSIC, body: SANS },
    ornament: 'lyre',
    frame: 'double',
    texture: 'glow',
    logo: { shape: 'plate', height: 62 },
    photo: { shape: 'rounded' },
  },
  {
    id: 'sepia-archive',
    name: '세피아 아카이브',
    tagline: '오래된 악보 같은 종이결. 정통성을 강조하고 싶을 때.',
    mood: ['고전', '따뜻', '아카이브'],
    palette: {
      paper: '#f6efdf',
      paperAlt: '#ede3cd',
      ink: '#3b3226',
      muted: '#7d7059',
      accent: '#8a6a3b',
      accentSoft: '#e2d5b8',
      line: '#d5c5a3',
      band: '#3b3226',
      bandInk: '#f6efdf',
    },
    fonts: { display: SERIF_CLASSIC, body: SANS },
    ornament: 'lyre',
    frame: 'double',
    texture: 'grain',
    logo: { shape: 'ring', height: 60 },
    photo: { shape: 'rect' },
  },
  {
    id: 'pearl-mint',
    name: '펄 민트',
    tagline: '맑고 산뜻한 청록. 봄·여름 발표회에 잘 맞습니다.',
    mood: ['산뜻', '맑음', '단정'],
    palette: {
      paper: '#f8fbfa',
      paperAlt: '#e8f4f1',
      ink: '#1f3a37',
      muted: '#5f7f7a',
      accent: '#4f9d90',
      accentSoft: '#d5ece6',
      line: '#c6e0da',
      band: '#1f3a37',
      bandInk: '#f8fbfa',
    },
    fonts: { display: SERIF_THIN, body: SANS },
    ornament: 'garland',
    frame: 'thin',
    texture: 'none',
    logo: { shape: 'circle', height: 60 },
    photo: { shape: 'rounded' },
  },
  {
    id: 'moonlit-blue',
    name: '문릿 블루',
    tagline: '달빛 같은 푸른 회색. 야간 공연·녹턴 프로그램에.',
    mood: ['서정', '차분', '밤'],
    palette: {
      paper: '#f0f4fb',
      paperAlt: '#e0e8f5',
      ink: '#1b2a4a',
      muted: '#5d6d8c',
      accent: '#4a6ea9',
      accentSoft: '#d3e0f2',
      line: '#c3d1e8',
      band: '#1b2a4a',
      bandInk: '#f0f4fb',
    },
    fonts: { display: SERIF_SOFT, body: SANS },
    ornament: 'wave',
    frame: 'rounded',
    texture: 'gradient',
    logo: { shape: 'circle', height: 60 },
    photo: { shape: 'arch' },
  },
  {
    id: 'spring-bloom',
    name: '스프링 블룸',
    tagline: '연분홍과 연둣빛. 신입생 발표회·봄 음악회에.',
    mood: ['봄', '화사', '경쾌'],
    palette: {
      paper: '#fffaf7',
      paperAlt: '#fdeee9',
      ink: '#4a3a2e',
      muted: '#8b7466',
      accent: '#e0837e',
      accentSoft: '#e8f0d8',
      line: '#f0dcd2',
      band: '#7fa663',
      bandInk: '#ffffff',
    },
    fonts: { display: SERIF_SOFT, body: SANS },
    ornament: 'confetti',
    frame: 'rounded',
    texture: 'none',
    logo: { shape: 'circle', height: 64 },
    photo: { shape: 'circle' },
  },
  {
    id: 'christmas-warm',
    name: '크리스마스',
    tagline: '겨울 시즌 발표회와 홈 콘서트에.',
    mood: ['시즌', '따뜻', '겨울'],
    palette: {
      paper: '#fdfaf4',
      paperAlt: '#f3eadb',
      ink: '#22372c',
      muted: '#6c7a6c',
      accent: '#a52f38',
      accentSoft: '#f6dcd6',
      line: '#d9c9b4',
      band: '#22372c',
      bandInk: '#fdfaf4',
    },
    fonts: { display: SERIF_SOFT, body: SANS },
    ornament: 'holly',
    frame: 'ribbon',
    texture: 'none',
    logo: { shape: 'ring', height: 62 },
    photo: { shape: 'rounded' },
  },
  {
    id: 'halloween-night',
    name: '할로윈 나이트',
    tagline: '10월 시즌 특강 발표회에.',
    mood: ['시즌', '유쾌', '가을'],
    palette: {
      paper: '#1d1526',
      paperAlt: '#2a1f38',
      ink: '#f7efe2',
      muted: '#b6a2c9',
      accent: '#f08a2e',
      accentSoft: '#42305a',
      line: '#4a3763',
      band: '#f08a2e',
      bandInk: '#1d1526',
    },
    fonts: { display: ROUND, body: SANS },
    ornament: 'moon',
    frame: 'none',
    texture: 'glow',
    logo: { shape: 'plate', height: 62 },
    photo: { shape: 'rounded' },
  },
]

export const DEFAULT_THEME_ID = 'classic-navy'

/** 종이색의 밝기 — 밝은 테마와 어두운 테마를 갈라 보여 주기 위한 판정 */
export function themeLuminance(theme: DesignTheme): number {
  const hex = theme.palette.paper.replace('#', '')
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
  const lin = (c: number) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4)
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
}

export function isDarkTheme(theme: DesignTheme): boolean {
  return themeLuminance(theme) < 0.35
}

export function themesByTone(): { tone: 'light' | 'dark'; label: string; items: DesignTheme[] }[] {
  return [
    { tone: 'light', label: '밝은 테마', items: DESIGN_THEMES.filter((t) => !isDarkTheme(t)) },
    { tone: 'dark', label: '어두운 테마', items: DESIGN_THEMES.filter((t) => isDarkTheme(t)) },
  ]
}

export function getTheme(id: string | null | undefined): DesignTheme {
  return DESIGN_THEMES.find((t) => t.id === id) ?? DESIGN_THEMES[0]
}

/** 테마를 CSS 변수로 — 인쇄물 컴포넌트는 이 변수만 참조한다 */
export function themeVars(theme: DesignTheme): Record<string, string> {
  return {
    '--d-paper': theme.palette.paper,
    '--d-paper-alt': theme.palette.paperAlt,
    '--d-ink': theme.palette.ink,
    '--d-muted': theme.palette.muted,
    '--d-accent': theme.palette.accent,
    '--d-accent-soft': theme.palette.accentSoft,
    '--d-line': theme.palette.line,
    '--d-band': theme.palette.band,
    '--d-band-ink': theme.palette.bandInk,
    '--d-display': theme.fonts.display,
    '--d-body': theme.fonts.body,
  }
}
