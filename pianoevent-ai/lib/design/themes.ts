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
  /** 벚꽃 — 봄, 사랑스러운 분위기 */
  | 'cherry'
  /** 눈꽃 — 겨울 발표회 */
  | 'snow'
  /** 단풍 — 가을 음악회 */
  | 'maple'
  /** 리본 매듭 — 선물 같은 초대장 */
  | 'ribbon'
  /** 하트 — 유아·저학년 학부모 초청 */
  | 'heart'
  /** 진주 줄 — 격식 있는 여백형 */
  | 'pearl'
  /** 여름 햇살 */
  | 'sun'
  /** 촛불 — 저녁 공연, 캔들 콘서트 */
  | 'candle'
  /** 담쟁이 덩굴 — 정원·홀 입구 느낌 */
  | 'ivy'
  /** 음표 흩날림 */
  | 'note'
  /** 고전 아치·기둥 — 콘서트홀 정면 */
  | 'arch'
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

/**
 * 테마 성격. 원장이 40종을 한 줄로 훑지 않고 "우리 학원 분위기"로 바로 찾게 한다.
 */
export type ThemeFamily = 'classic' | 'lovely' | 'season' | 'modern' | 'kids'

export const FAMILY_LABEL: Record<ThemeFamily, string> = {
  classic: '고급 · 클래식',
  lovely: '사랑스러운',
  season: '계절 · 시즌',
  modern: '모던 · 편집',
  kids: '아이들 · 활기',
}

export const FAMILY_HINT: Record<ThemeFamily, string> = {
  classic: '정통 정기 연주회, 격식 있는 홀. 금선·아치·진주 장식으로 무게를 잡습니다.',
  lovely: '유아·초등 학부모 초청. 부드러운 색과 하트·리본·꽃 장식.',
  season: '봄 벚꽃부터 겨울 눈꽃까지. 시즌 특강 발표회와 계절 음악회에.',
  modern: '사진과 큰 타이포가 주인공. 군더더기 없는 편집 디자인.',
  kids: '색이 밝고 서체가 둥급니다. 놀이형 미니 콘서트에.',
}

export interface DesignTheme {
  id: string
  name: string
  /** 어떤 학원·행사에 어울리는지 한 줄 */
  tagline: string
  mood: string[]
  family: ThemeFamily
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

/**
 * 서체 스택.
 *
 * 웹폰트는 인터넷이 있을 때만 내려온다. 없으면 윈도우·맥에 이미 깔린 글꼴로 떨어지는데,
 * 그 폴백까지 손으로 지정해 둬야 인터넷 없는 학원에서도 인쇄물이 제 모양으로 나온다.
 * 윈도우: 바탕(Batang) · 궁서(Gungsuh) · 맑은 고딕(Malgun Gothic)
 * 맥: Apple SD Gothic Neo · AppleMyungjo
 */
const SERIF_CLASSIC =
  "'Nanum Myeongjo', 'Apple SD Gothic Neo', AppleMyungjo, Batang, '바탕', serif"
const SERIF_SOFT = "'Gowun Batang', 'Nanum Myeongjo', AppleMyungjo, Batang, '바탕', serif"
const SERIF_THIN = "'Song Myung', 'Nanum Myeongjo', AppleMyungjo, Batang, '바탕', serif"
const SERIF_NOTO = "'Noto Serif KR', 'Nanum Myeongjo', AppleMyungjo, Batang, '바탕', serif"
const SANS =
  "'Noto Sans KR', Pretendard, 'Apple SD Gothic Neo', 'Malgun Gothic', '맑은 고딕', sans-serif"
// 둥근 글꼴이 없으면 고딕으로 — 각진 명조보다 아이들 인쇄물에 가깝다
const ROUND = "'Jua', 'Noto Sans KR', 'Apple SD Gothic Neo', 'Malgun Gothic', '맑은 고딕', sans-serif"
// 손글씨가 없으면 궁서로 — 붓 느낌이 남는다
const HAND = "'Gaegu', 'Noto Sans KR', Gungsuh, '궁서', 'Malgun Gothic', cursive"

export const DESIGN_THEMES: DesignTheme[] = [
  {
    id: 'daylight-studio',
    name: '데이라이트 스튜디오',
    tagline: '흰 바탕에 사진이 주인공. 실제 사진을 크게 쓰고 싶을 때 가장 잘 맞습니다.',
    mood: ['밝음', '사진', '깨끗'],
    family: 'modern',
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
    family: 'lovely',
    palette: {
      paper: '#fffdf8',
      paperAlt: '#fdf4e5',
      ink: '#403528',
      muted: '#8b7c66',
      accent: '#bc892c',
      accentSoft: '#f7e9cd',
      line: '#eadcc2',
      band: '#946c23',
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
    family: 'lovely',
    palette: {
      paper: '#ffffff',
      paperAlt: '#fdf3f4',
      ink: '#3d2f33',
      muted: '#8a757b',
      accent: '#c96b7a',
      accentSoft: '#fbe4e7',
      line: '#f0dde1',
      band: '#bf5062',
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
    family: 'modern',
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
    family: 'classic',
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
    family: 'classic',
    palette: {
      paper: '#fdfcf8',
      paperAlt: '#f6f1e4',
      ink: '#3c3527',
      muted: '#8a8069',
      accent: '#ae8d41',
      accentSoft: '#efe5cd',
      line: '#ddd2b6',
      band: '#8c7134',
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
    family: 'lovely',
    palette: {
      paper: '#fffaf8',
      paperAlt: '#fdeee9',
      ink: '#4a2230',
      muted: '#96707b',
      accent: '#c25b70',
      accentSoft: '#f7d9dd',
      line: '#eec9cd',
      band: '#bc4b62',
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
    family: 'modern',
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
    family: 'modern',
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
    family: 'kids',
    palette: {
      paper: '#fdfdfb',
      paperAlt: '#e9f6f2',
      ink: '#28453f',
      muted: '#6f8b85',
      accent: '#e86e40',
      accentSoft: '#ffe3d5',
      line: '#c9e4dc',
      band: '#368274',
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
    family: 'kids',
    palette: {
      paper: '#fffdf5',
      paperAlt: '#fff3d6',
      ink: '#3a2f1d',
      muted: '#8a7a58',
      accent: '#e2721a',
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
    family: 'classic',
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
    family: 'classic',
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
    family: 'classic',
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
    family: 'classic',
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
    family: 'season',
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
    family: 'classic',
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
    family: 'season',
    palette: {
      paper: '#fffaf7',
      paperAlt: '#fdeee9',
      ink: '#4a3a2e',
      muted: '#8b7466',
      accent: '#db706a',
      accentSoft: '#e8f0d8',
      line: '#f0dcd2',
      band: '#5e7e48',
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
    family: 'season',
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
    family: 'season',
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

  // ─────────────────────────────────────────────────────────────
  // 고급 · 클래식 — 정통 정기 연주회와 격식 있는 홀
  // ─────────────────────────────────────────────────────────────
  {
    id: 'royal-emerald',
    name: '로열 에메랄드',
    tagline: '깊은 초록과 담쟁이 장식. 격조를 지키면서도 무겁지 않습니다.',
    mood: ['고급', '차분', '격식'],
    family: 'classic',
    palette: {
      paper: '#f7faf7',
      paperAlt: '#e8f1eb',
      ink: '#10261c',
      muted: '#4f6b5c',
      accent: '#1c6b4a',
      accentSoft: '#d5e8dc',
      line: '#c6dbcf',
      band: '#10261c',
      bandInk: '#f7faf7',
    },
    fonts: { display: SERIF_CLASSIC, body: SANS },
    ornament: 'ivy',
    frame: 'double',
    texture: 'grain',
    logo: { shape: 'ring', height: 62 },
    photo: { shape: 'arch', treatment: 'natural' },
  },
  {
    id: 'marble-white',
    name: '마블 화이트',
    tagline: '대리석 같은 흰 바탕에 진주 장식. 여백으로 격을 만듭니다.',
    mood: ['고급', '여백', '단정'],
    family: 'classic',
    palette: {
      paper: '#fcfcfd',
      paperAlt: '#f1f0ed',
      ink: '#22242a',
      muted: '#757a85',
      accent: '#8f7f5d',
      accentSoft: '#ece7db',
      line: '#e0dfda',
      band: '#22242a',
      bandInk: '#fcfcfd',
    },
    fonts: { display: SERIF_THIN, body: SANS },
    ornament: 'pearl',
    frame: 'thin',
    texture: 'grain',
    logo: { shape: 'plain', height: 56 },
    photo: { shape: 'rect', treatment: 'natural' },
  },
  {
    id: 'vienna-hall',
    name: '비엔나 홀',
    tagline: '크림빛 종이에 진홍과 리라. 유럽 연주회장 프로그램의 인상.',
    mood: ['정통', '고전', '격식'],
    family: 'classic',
    palette: {
      paper: '#fbf6ec',
      paperAlt: '#f3e9d5',
      ink: '#2a1a18',
      muted: '#7a6157',
      accent: '#8c2f39',
      accentSoft: '#f0dcd6',
      line: '#ded0b8',
      band: '#8c2f39',
      bandInk: '#fdf8ef',
    },
    fonts: { display: SERIF_CLASSIC, body: SANS },
    ornament: 'lyre',
    frame: 'double',
    texture: 'grain',
    logo: { shape: 'ring', height: 64 },
    photo: { shape: 'arch', treatment: 'warm' },
  },
  {
    id: 'platinum-grey',
    name: '플래티넘 그레이',
    tagline: '차가운 회색과 고전 아치. 콩쿠르 입상 발표회처럼 절제된 자리에.',
    mood: ['절제', '격식', '모던'],
    family: 'classic',
    palette: {
      paper: '#f8f9fa',
      paperAlt: '#eceef1',
      ink: '#1f2329',
      muted: '#6b7280',
      accent: '#4d5865',
      accentSoft: '#e2e6ea',
      line: '#d7dbe0',
      band: '#1f2329',
      bandInk: '#f8f9fa',
    },
    fonts: { display: SERIF_NOTO, body: SANS },
    ornament: 'arch',
    frame: 'thin',
    texture: 'none',
    logo: { shape: 'plain', height: 56 },
    photo: { shape: 'rect', treatment: 'mono' },
  },
  {
    id: 'antique-rose',
    name: '앤티크 로즈골드',
    tagline: '바랜 장밋빛과 진주. 오래된 살롱 연주회 같은 온기.',
    mood: ['우아', '따뜻', '고전'],
    family: 'classic',
    palette: {
      paper: '#fdf8f5',
      paperAlt: '#f5e8e0',
      ink: '#3a2a26',
      muted: '#8a6f66',
      accent: '#ad6f5c',
      accentSoft: '#f3e0d7',
      line: '#e6d3c8',
      band: '#8f5645',
      bandInk: '#fffaf7',
    },
    fonts: { display: SERIF_SOFT, body: SANS },
    ornament: 'pearl',
    frame: 'thin',
    texture: 'grain',
    logo: { shape: 'ring', height: 60 },
    photo: { shape: 'arch', treatment: 'soft' },
  },
  {
    id: 'steinway-black',
    name: '스타인웨이 블랙',
    tagline: '피아노 옻칠 같은 검정에 건반 장식. 고학년 독주회에.',
    mood: ['고급', '집중', '무대'],
    family: 'classic',
    palette: {
      paper: '#0f1114',
      paperAlt: '#191c21',
      ink: '#f3f0ea',
      muted: '#a2a7b0',
      accent: '#c9a86a',
      accentSoft: '#2b2820',
      line: '#33383f',
      band: '#c9a86a',
      bandInk: '#0f1114',
    },
    fonts: { display: SERIF_THIN, body: SANS },
    ornament: 'keys',
    frame: 'thin',
    texture: 'glow',
    logo: { shape: 'plate', height: 60 },
    photo: { shape: 'rect', treatment: 'mono' },
  },
  {
    id: 'opera-crimson',
    name: '오페라 크림슨',
    tagline: '진홍 벨벳과 촛불. 저녁 시간 캔들 콘서트에.',
    mood: ['드라마틱', '따뜻', '저녁'],
    family: 'classic',
    palette: {
      paper: '#2a0f16',
      paperAlt: '#3a1620',
      ink: '#f7ece4',
      muted: '#c9a5a7',
      accent: '#d9a441',
      accentSoft: '#4a1f28',
      line: '#55242f',
      band: '#d9a441',
      bandInk: '#2a0f16',
    },
    fonts: { display: SERIF_CLASSIC, body: SANS },
    ornament: 'candle',
    frame: 'double',
    texture: 'glow',
    logo: { shape: 'plate', height: 62 },
    photo: { shape: 'arch', treatment: 'warm' },
  },

  // ─────────────────────────────────────────────────────────────
  // 사랑스러운 — 유아·초등 학부모 초청
  // ─────────────────────────────────────────────────────────────
  {
    id: 'cotton-candy',
    name: '코튼 캔디',
    tagline: '솜사탕 같은 분홍. 첫 발표회 초대장에 반응이 가장 좋습니다.',
    mood: ['사랑스러움', '부드러움', '밝음'],
    family: 'lovely',
    palette: {
      paper: '#fffafc',
      paperAlt: '#fdeef4',
      ink: '#3f2c35',
      muted: '#8d707c',
      accent: '#d76d9a',
      accentSoft: '#fce1eb',
      line: '#f4dbe4',
      band: '#b45179',
      bandInk: '#fffafc',
    },
    fonts: { display: SERIF_SOFT, body: SANS },
    ornament: 'heart',
    frame: 'rounded',
    texture: 'gradient',
    logo: { shape: 'circle', height: 62 },
    photo: { shape: 'rounded', treatment: 'bright' },
  },
  {
    id: 'lavender-dream',
    name: '라벤더 드림',
    tagline: '연보라와 잔별. 조용하고 사랑스러운 저녁 발표회에.',
    mood: ['사랑스러움', '서정', '차분'],
    family: 'lovely',
    palette: {
      paper: '#fbfaff',
      paperAlt: '#efecfa',
      ink: '#2e2942',
      muted: '#6f6890',
      accent: '#7a68bd',
      accentSoft: '#e6e1f7',
      line: '#ddd7ee',
      band: '#5f4f9e',
      bandInk: '#fbfaff',
    },
    fonts: { display: SERIF_SOFT, body: SANS },
    ornament: 'stars',
    frame: 'rounded',
    texture: 'gradient',
    logo: { shape: 'circle', height: 60 },
    photo: { shape: 'rounded', treatment: 'soft' },
  },
  {
    id: 'peach-blossom',
    name: '피치 블라썸',
    tagline: '복숭아빛과 꽃잎. 사진을 넣으면 얼굴이 화사하게 삽니다.',
    mood: ['사랑스러움', '화사', '따뜻'],
    family: 'lovely',
    palette: {
      paper: '#fffaf6',
      paperAlt: '#fceee2',
      ink: '#3d2b22',
      muted: '#8b6c58',
      accent: '#d4753f',
      accentSoft: '#fbe3d2',
      line: '#f0dbc9',
      band: '#a85628',
      bandInk: '#fffaf6',
    },
    fonts: { display: SERIF_SOFT, body: SANS },
    ornament: 'cherry',
    frame: 'rounded',
    texture: 'none',
    logo: { shape: 'circle', height: 60 },
    photo: { shape: 'rounded', treatment: 'warm' },
  },
  {
    id: 'ribbon-cream',
    name: '리본 크림',
    tagline: '선물 상자를 여는 기분. 리본 띠가 위아래를 감쌉니다.',
    mood: ['사랑스러움', '선물', '단정'],
    family: 'lovely',
    palette: {
      paper: '#fffdf6',
      paperAlt: '#f8efdc',
      ink: '#3b3225',
      muted: '#857662',
      accent: '#c17d95',
      accentSoft: '#f8e6ea',
      line: '#ecdfc9',
      band: '#a65f75',
      bandInk: '#fffdf6',
    },
    fonts: { display: SERIF_THIN, body: SANS },
    ornament: 'ribbon',
    frame: 'ribbon',
    texture: 'none',
    logo: { shape: 'ring', height: 58 },
    photo: { shape: 'rounded', treatment: 'soft' },
  },
  {
    id: 'bonbon-mint',
    name: '봉봉 민트',
    tagline: '맑은 민트에 색종이. 가볍고 즐거운 미니 콘서트에.',
    mood: ['경쾌', '맑음', '축하'],
    family: 'lovely',
    palette: {
      paper: '#f7fdfb',
      paperAlt: '#e5f6f0',
      ink: '#23342f',
      muted: '#5f7a72',
      accent: '#2f9c81',
      accentSoft: '#d6f0e8',
      line: '#cbe7de',
      band: '#1f7660',
      bandInk: '#f7fdfb',
    },
    fonts: { display: ROUND, body: SANS },
    ornament: 'confetti',
    frame: 'rounded',
    texture: 'none',
    logo: { shape: 'circle', height: 60 },
    photo: { shape: 'rounded', treatment: 'bright' },
  },

  // ─────────────────────────────────────────────────────────────
  // 아이들 · 활기
  // ─────────────────────────────────────────────────────────────
  {
    id: 'milky-bear',
    name: '밀키 베어',
    tagline: '둥근 글씨와 우유빛. 유아 발표회 안내문이 딱딱해 보이지 않습니다.',
    mood: ['아이', '포근', '둥금'],
    family: 'kids',
    palette: {
      paper: '#fffdf7',
      paperAlt: '#f9f0e2',
      ink: '#453727',
      muted: '#8d7a62',
      accent: '#be8740',
      accentSoft: '#f7e7cd',
      line: '#ecdcc3',
      band: '#9a6b32',
      bandInk: '#fffdf7',
    },
    fonts: { display: ROUND, body: ROUND },
    ornament: 'heart',
    frame: 'rounded',
    texture: 'none',
    logo: { shape: 'circle', height: 64 },
    photo: { shape: 'circle', treatment: 'warm' },
  },

  // ─────────────────────────────────────────────────────────────
  // 계절 · 시즌
  // ─────────────────────────────────────────────────────────────
  {
    id: 'cherry-spring',
    name: '벚꽃 스프링',
    tagline: '흩날리는 벚꽃. 3~4월 신입생 발표회와 봄 음악회에.',
    mood: ['봄', '화사', '사랑스러움'],
    family: 'season',
    palette: {
      paper: '#fffafb',
      paperAlt: '#fdedf1',
      ink: '#3b2b31',
      muted: '#8a6d76',
      accent: '#d2748d',
      accentSoft: '#fbe2e9',
      line: '#f2dbe2',
      band: '#b1566f',
      bandInk: '#fffafb',
    },
    fonts: { display: SERIF_SOFT, body: SANS },
    ornament: 'cherry',
    frame: 'thin',
    texture: 'none',
    logo: { shape: 'circle', height: 60 },
    photo: { shape: 'arch', treatment: 'bright' },
  },
  {
    id: 'summer-marine',
    name: '서머 마린',
    tagline: '여름 바다빛과 햇살. 7~8월 방학 특강 발표회에.',
    mood: ['여름', '시원', '산뜻'],
    family: 'season',
    palette: {
      paper: '#f6fbfe',
      paperAlt: '#e4f1f9',
      ink: '#12303f',
      muted: '#55748a',
      accent: '#1e7fa8',
      accentSoft: '#d5eaf5',
      line: '#cbe0ed',
      band: '#12303f',
      bandInk: '#f6fbfe',
    },
    fonts: { display: SANS, body: SANS },
    ornament: 'sun',
    frame: 'thin',
    texture: 'none',
    logo: { shape: 'plain', height: 56 },
    photo: { shape: 'rect', treatment: 'bright' },
  },
  {
    id: 'autumn-maple',
    name: '어텀 메이플',
    tagline: '단풍빛 종이결. 10~11월 가을 정기 연주회에.',
    mood: ['가을', '따뜻', '차분'],
    family: 'season',
    palette: {
      paper: '#fdf8f1',
      paperAlt: '#f5e9d5',
      ink: '#3a2a1c',
      muted: '#85705a',
      accent: '#b0561f',
      accentSoft: '#f4dcc4',
      line: '#e5d2b6',
      band: '#8e4a1e',
      bandInk: '#fdf8f1',
    },
    fonts: { display: SERIF_CLASSIC, body: SANS },
    ornament: 'maple',
    frame: 'thin',
    texture: 'grain',
    logo: { shape: 'ring', height: 60 },
    photo: { shape: 'arch', treatment: 'warm' },
  },
  {
    id: 'winter-snow',
    name: '윈터 스노우',
    tagline: '눈 내리는 밝은 겨울. 12~2월 발표회를 산뜻하게.',
    mood: ['겨울', '맑음', '조용'],
    family: 'season',
    palette: {
      paper: '#f8fbfe',
      paperAlt: '#e9f1f8',
      ink: '#1e2c3a',
      muted: '#647688',
      accent: '#5b83ad',
      accentSoft: '#dfeaf5',
      line: '#d3e0ec',
      band: '#1e2c3a',
      bandInk: '#f8fbfe',
    },
    fonts: { display: SERIF_THIN, body: SANS },
    ornament: 'snow',
    frame: 'thin',
    texture: 'none',
    logo: { shape: 'circle', height: 58 },
    photo: { shape: 'rounded', treatment: 'soft' },
  },
  {
    id: 'newyear-red',
    name: '새해 홍백',
    tagline: '붉은 금선. 신년 음악회와 설 명절 특강 발표에.',
    mood: ['새해', '경사', '격식'],
    family: 'season',
    palette: {
      paper: '#fffcf7',
      paperAlt: '#f8ede0',
      ink: '#2e1c17',
      muted: '#7d6154',
      accent: '#c8352f',
      accentSoft: '#f7ded9',
      line: '#ead9c8',
      band: '#a52a26',
      bandInk: '#fffcf7',
    },
    fonts: { display: SERIF_CLASSIC, body: SANS },
    ornament: 'foil',
    frame: 'double',
    texture: 'grain',
    logo: { shape: 'ring', height: 62 },
    photo: { shape: 'arch', treatment: 'warm' },
  },
  {
    id: 'graduation-day',
    name: '졸업의 날',
    tagline: '남보라 화환. 수료식·졸업 연주회와 시상이 있는 자리에.',
    mood: ['졸업', '격식', '축하'],
    family: 'season',
    palette: {
      paper: '#f9f8fc',
      paperAlt: '#edebf6',
      ink: '#23214a',
      muted: '#63618c',
      accent: '#4b4a8f',
      accentSoft: '#e2e0f2',
      line: '#d6d3ea',
      band: '#23214a',
      bandInk: '#f9f8fc',
    },
    fonts: { display: SERIF_CLASSIC, body: SANS },
    ornament: 'garland',
    frame: 'double',
    texture: 'grain',
    logo: { shape: 'ring', height: 62 },
    photo: { shape: 'arch', treatment: 'natural' },
  },

  // ─────────────────────────────────────────────────────────────
  // 모던 · 편집
  // ─────────────────────────────────────────────────────────────
  {
    id: 'gallery-white',
    name: '갤러리 화이트',
    tagline: '장식을 걷어낸 흰 벽. 사진과 글씨만으로 승부합니다.',
    mood: ['모던', '미니멀', '깨끗'],
    family: 'modern',
    palette: {
      paper: '#ffffff',
      paperAlt: '#f4f4f5',
      ink: '#0f0f10',
      muted: '#6e6e73',
      accent: '#0f0f10',
      accentSoft: '#ebebec',
      line: '#dedee0',
      band: '#0f0f10',
      bandInk: '#ffffff',
    },
    fonts: { display: SANS, body: SANS },
    ornament: 'note',
    frame: 'none',
    texture: 'none',
    logo: { shape: 'plain', height: 50 },
    photo: { shape: 'rect', treatment: 'natural' },
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

export const FAMILY_ORDER: ThemeFamily[] = ['classic', 'lovely', 'season', 'modern', 'kids']

/**
 * 성격별 묶음 — 40종을 한 줄로 늘어놓으면 고를 수가 없다.
 * 원장이 "우리 학원은 이런 분위기" 한 번으로 후보를 5~14종으로 좁히게 한다.
 */
export function themesByFamily(): {
  family: ThemeFamily
  label: string
  hint: string
  items: DesignTheme[]
}[] {
  return FAMILY_ORDER.map((family) => ({
    family,
    label: FAMILY_LABEL[family],
    hint: FAMILY_HINT[family],
    items: DESIGN_THEMES.filter((t) => t.family === family),
  })).filter((g) => g.items.length > 0)
}

/**
 * 행사 날짜로 계절 테마를 추천한다.
 * 원장이 40종을 다 훑지 않아도 "지금 시기에 맞는 것"이 먼저 보이게 하기 위한 것.
 */
export function seasonalThemeIds(month: number): string[] {
  if (month >= 3 && month <= 5) return ['cherry-spring', 'spring-bloom', 'peach-blossom', 'sunlit-ivory']
  if (month >= 6 && month <= 8) return ['summer-marine', 'pearl-mint', 'sky-linen', 'bonbon-mint']
  if (month >= 9 && month <= 11) return ['autumn-maple', 'sepia-archive', 'halloween-night', 'vienna-hall']
  return ['winter-snow', 'christmas-warm', 'newyear-red', 'graduation-day']
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
