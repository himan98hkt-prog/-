import { useMemo } from 'react';
import { useColorScheme } from 'react-native';
import { usePetStore } from '../store/usePetStore';
import { darkColors, lightColors, shadowFor, type Colors } from './theme';

export type ThemeMode = 'system' | 'light' | 'dark';

export interface Theme {
  colors: Colors;
  scheme: 'light' | 'dark';
  shadow: object;
}

const themes: Record<'light' | 'dark', Theme> = {
  light: { colors: lightColors, scheme: 'light', shadow: shadowFor(lightColors) },
  dark: { colors: darkColors, scheme: 'dark', shadow: shadowFor(darkColors) },
};

/**
 * 기기 설정(system)을 따르되, 사용자가 설정에서 고정할 수도 있다.
 * 테마 객체는 스킴당 하나로 고정돼 있어서 참조가 바뀌지 않는다 —
 * 그래야 `useStyles` 의 메모가 매 렌더 깨지지 않는다.
 */
export function useTheme(): Theme {
  const mode = usePetStore((s) => s.themeMode);
  const systemScheme = useColorScheme();
  const scheme = mode === 'system' ? (systemScheme === 'dark' ? 'dark' : 'light') : mode;
  return themes[scheme];
}

/**
 * 스타일시트를 테마에서 만든다.
 * `factory` 는 반드시 모듈 최상단에 선언해야 한다 (렌더마다 새 함수가 되면 메모가 무의미).
 */
export function useStyles<T>(factory: (theme: Theme) => T): T {
  const theme = useTheme();
  return useMemo(() => factory(theme), [factory, theme]);
}
