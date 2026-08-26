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
  | 'none'

export type FrameId = 'deco' | 'thin' | 'double' | 'rounded' | 'ribbon' | 'none'

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
  },
]

export const DEFAULT_THEME_ID = 'classic-navy'

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
