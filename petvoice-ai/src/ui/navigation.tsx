import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';

/**
 * 화면 수가 적어 react-navigation 대신 최소한의 스택 라우터를 직접 둔다.
 * 의존성이 줄어 Expo SDK 업그레이드 때 깨질 지점도 줄어든다.
 */
export type RouteName =
  'home' | 'history' | 'settings' | 'capture' | 'result' | 'paywall' | 'petForm' | 'insights';

export const TAB_ROUTES: { route: RouteName; labelKey: string; emoji: string }[] = [
  { route: 'home', labelKey: 'tab.analyze', emoji: '🎙' },
  { route: 'history', labelKey: 'tab.diary', emoji: '📔' },
  { route: 'settings', labelKey: 'tab.settings', emoji: '⚙️' },
];

export interface RouteEntry {
  route: RouteName;
  params?: Record<string, unknown>;
}

interface NavContext {
  current: RouteEntry;
  stack: RouteEntry[];
  navigate: (route: RouteName, params?: Record<string, unknown>) => void;
  /** 탭 전환 — 스택을 비우고 해당 탭으로 */
  switchTab: (route: RouteName) => void;
  back: () => void;
  canGoBack: boolean;
}

const Ctx = createContext<NavContext | null>(null);

export function NavigationProvider({ children }: { children: React.ReactNode }) {
  const [stack, setStack] = useState<RouteEntry[]>([{ route: 'home' }]);

  const navigate = useCallback((route: RouteName, params?: Record<string, unknown>) => {
    setStack((prev) => [...prev, { route, params }]);
  }, []);

  const switchTab = useCallback((route: RouteName) => {
    setStack([{ route }]);
  }, []);

  const back = useCallback(() => {
    setStack((prev) => (prev.length > 1 ? prev.slice(0, -1) : prev));
  }, []);

  const value = useMemo<NavContext>(
    () => ({
      current: stack[stack.length - 1],
      stack,
      navigate,
      switchTab,
      back,
      canGoBack: stack.length > 1,
    }),
    [stack, navigate, switchTab, back],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useNavigation(): NavContext {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('NavigationProvider 안에서만 useNavigation 을 쓸 수 있습니다.');
  return ctx;
}

export function isTabRoute(route: RouteName): boolean {
  return TAB_ROUTES.some((t) => t.route === route);
}
