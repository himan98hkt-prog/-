import { Platform } from 'react-native';

/** 앱 전역 디자인 토큰. 색·간격·타이포를 화면마다 다시 정의하지 않는다. */
export const colors = {
  bg: '#FFF9F4',
  surface: '#FFFFFF',
  surfaceAlt: '#FFF2E6',
  border: '#F0E2D4',
  text: '#26201B',
  textSoft: '#7A6A5D',
  textFaint: '#A99A8D',
  primary: '#FF8A3D',
  primaryDark: '#E8722A',
  primarySoft: '#FFE7D3',
  accent: '#5BC0BE',
  danger: '#D64545',
  dangerSoft: '#FDECEC',
  warn: '#E0A800',
  warnSoft: '#FFF6DA',
  success: '#4C9F70',
  pro: '#7B61FF',
  proSoft: '#EFEAFF',
  shadow: '#3B2A1C',
};

export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 };

export const radius = { sm: 8, md: 14, lg: 20, xl: 28, pill: 999 };

export const font = {
  h1: { fontSize: 26, fontWeight: '800' as const, letterSpacing: -0.5 },
  h2: { fontSize: 20, fontWeight: '700' as const, letterSpacing: -0.3 },
  h3: { fontSize: 17, fontWeight: '700' as const },
  body: { fontSize: 15, fontWeight: '400' as const, lineHeight: 22 },
  bodyStrong: { fontSize: 15, fontWeight: '600' as const, lineHeight: 22 },
  small: { fontSize: 13, fontWeight: '400' as const, lineHeight: 19 },
  tiny: { fontSize: 11, fontWeight: '600' as const },
};

export const shadow = Platform.select({
  ios: {
    shadowColor: colors.shadow,
    shadowOpacity: 0.1,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
  },
  android: { elevation: 3 },
  default: {},
}) as object;
