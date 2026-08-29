/**
 * 디자인 토큰.
 *
 * 라이트/다크 두 벌을 같은 키로 정의하고, 화면은 `useTheme()` 이 준 팔레트만 쓴다.
 * 색은 눈대중이 아니라 WCAG 명암비를 계산해서 골랐다. 괄호 안이 배경 대비 비율이다.
 * (본문 4.5:1, 큰 글씨 3:1 기준)
 */

export interface Colors {
  bg: string;
  surface: string;
  surfaceAlt: string;
  border: string;

  text: string;
  textSoft: string;
  textFaint: string;

  /** 흰/검은 글씨를 얹는 채움 버튼 배경 */
  primary: string;
  /** primary 위에 올라가는 글자색 */
  onPrimary: string;
  /** 배경 위에 그냥 얹는 강조 글자색 (링크 등) */
  primaryText: string;
  /** 글자가 올라가지 않는 장식용 원색 (펄스 링, 막대 채움) */
  primaryVivid: string;
  primarySoft: string;

  accent: string;

  danger: string;
  dangerSoft: string;

  warnText: string;
  warnLine: string;
  warnSoft: string;

  success: string;

  pro: string;
  onPro: string;
  proText: string;
  proSoft: string;

  shadow: string;
}

/** 라이트 — 배경 #FFF9F4 기준 */
export const lightColors: Colors = {
  bg: '#FFF9F4',
  surface: '#FFFFFF',
  surfaceAlt: '#FFF2E6',
  border: '#F0E2D4',

  text: '#26201B', // 15.4:1
  textSoft: '#5E5147', // 7.3:1
  textFaint: '#7C6C5E', // 4.8:1

  // 브랜드 주황을 그대로 쓰되 글자는 어둡게 얹는다.
  // 흰 글씨는 2.35:1 로 기준 미달이었고, 주황을 어둡게 낮추면 브랜드색이 탁해진다.
  primary: '#FF8A3D', // 어두운 글씨 7.1:1
  onPrimary: '#2B1A0C',
  primaryText: '#A34509', // 5.9:1
  primaryVivid: '#FF8A3D',
  primarySoft: '#FFE7D3',

  accent: '#2F7F7D',

  danger: '#C4342F', // 5.2:1
  dangerSoft: '#FDECEC',

  warnText: '#7A5F00', // 5.8:1
  warnLine: '#E0A800',
  warnSoft: '#FFF6DA',

  success: '#3F8F68',

  pro: '#5B3FE0', // 흰 글씨 6.5:1
  onPro: '#FFFFFF',
  proText: '#5B3FE0', // 6.2:1
  proSoft: '#EFEAFF',

  shadow: '#3B2A1C',
};

/** 다크 — 배경 #14100D 기준. 채도 높은 색 위에는 흰 글씨가 아니라 어두운 글씨를 올린다. */
export const darkColors: Colors = {
  bg: '#14100D',
  surface: '#1E1813',
  surfaceAlt: '#2A2119',
  border: '#3A2E23',

  text: '#F5ECE3', // 16.2:1
  textSoft: '#B5A597', // 7.9:1
  textFaint: '#8F8073', // 5.0:1

  primary: '#FF9A54', // 어두운 글씨 8.8:1
  onPrimary: '#1A1208',
  primaryText: '#FFB177', // 10.6:1
  primaryVivid: '#FF9A54',
  primarySoft: '#3A2617',

  accent: '#5BC0BE',

  danger: '#F07A70', // 7.0:1
  dangerSoft: '#3A1E1C',

  warnText: '#E8B84B', // 10.3:1
  warnLine: '#B98B1F',
  warnSoft: '#362A13',

  success: '#6FBF92',

  pro: '#A996FF', // 어두운 글씨 7.5:1
  onPro: '#1A1208',
  proText: '#A996FF', // 7.7:1
  proSoft: '#2A2340',

  shadow: '#000000',
};

export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 };

export const radius = { sm: 8, md: 14, lg: 20, xl: 28, pill: 999 };

/**
 * 글자 크기는 시스템 설정을 그대로 따른다(allowFontScaling 기본값 유지).
 * 그래서 높이를 고정하지 않고 최소 높이 + 여백으로 잡는다 — 큰 글씨에서 잘리지 않게.
 */
export const font = {
  h1: { fontSize: 26, fontWeight: '800' as const, letterSpacing: -0.5 },
  h2: { fontSize: 20, fontWeight: '700' as const, letterSpacing: -0.3 },
  h3: { fontSize: 17, fontWeight: '700' as const },
  body: { fontSize: 15, fontWeight: '400' as const, lineHeight: 22 },
  bodyStrong: { fontSize: 15, fontWeight: '600' as const, lineHeight: 22 },
  small: { fontSize: 13, fontWeight: '400' as const, lineHeight: 19 },
  tiny: { fontSize: 11, fontWeight: '600' as const },
};

/** 손가락으로 누르는 것은 최소 44pt (iOS HIG / Material 권장) */
export const HIT_SIZE = 44;

export function shadowFor(colors: Colors) {
  return {
    shadowColor: colors.shadow,
    shadowOpacity: 0.1,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
    elevation: 3,
  };
}
