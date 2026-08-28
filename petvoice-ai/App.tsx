import { StatusBar } from 'expo-status-bar';
import React, { useEffect } from 'react';
import { ActivityIndicator, Pressable, SafeAreaView, StyleSheet, Text, View } from 'react-native';
import { isConfigured } from './src/api';
import { assertNoAiKeyInClient } from './src/api/config';
import { ensureSession } from './src/api/supabase';
import { syncSubscriptionFromServer } from './src/billing/useBilling';
import { usePetStore } from './src/store/usePetStore';
import { CaptureScreen } from './src/ui/screens/CaptureScreen';
import { HistoryScreen } from './src/ui/screens/HistoryScreen';
import { HomeScreen } from './src/ui/screens/HomeScreen';
import { OnboardingScreen } from './src/ui/screens/OnboardingScreen';
import { PaywallScreen } from './src/ui/screens/PaywallScreen';
import { PetFormScreen } from './src/ui/screens/PetFormScreen';
import { ResultScreen } from './src/ui/screens/ResultScreen';
import { SettingsScreen } from './src/ui/screens/SettingsScreen';
import { NavigationProvider, TAB_ROUTES, isTabRoute, useNavigation } from './src/ui/navigation';
import { colors, font, space } from './src/ui/theme';

// 클라이언트 번들에 AI 키가 섞여 들어오면 개발 단계에서 즉시 알아채도록.
if (__DEV__) assertNoAiKeyInClient();

export default function App() {
  useEffect(() => {
    if (!isConfigured) return;
    void (async () => {
      // 익명 세션을 미리 만들어 첫 분석에서 로그인 지연이 없도록 한다.
      await ensureSession();
      // 해지·환불·결제 실패는 앱 밖에서 일어난다. 로컬 값만 믿지 않고 서버와 맞춘다.
      await syncSubscriptionFromServer().catch(() => undefined);
    })();
  }, []);

  return (
    <NavigationProvider>
      <SafeAreaView style={styles.root}>
        <StatusBar style="dark" />
        <Router />
      </SafeAreaView>
    </NavigationProvider>
  );
}

function Router() {
  const nav = useNavigation();
  const hydrated = usePetStore((s) => s.hydrated);
  const onboarded = usePetStore((s) => s.onboarded);
  const petCount = usePetStore((s) => s.pets.length);

  if (!hydrated) {
    return (
      <View style={styles.loading}>
        <ActivityIndicator color={colors.primary} />
      </View>
    );
  }

  // 첫 실행: 온보딩이 모든 화면보다 앞선다. (등록 화면은 온보딩에서 열린다)
  if (!onboarded && petCount === 0 && nav.current.route !== 'petForm') {
    return <OnboardingScreen />;
  }

  const screen = {
    home: <HomeScreen />,
    history: <HistoryScreen />,
    settings: <SettingsScreen />,
    capture: <CaptureScreen />,
    result: <ResultScreen />,
    paywall: <PaywallScreen />,
    petForm: <PetFormScreen />,
  }[nav.current.route];

  const showTabs = isTabRoute(nav.current.route) && !nav.canGoBack;

  return (
    <View style={{ flex: 1 }}>
      {nav.canGoBack ? (
        <Pressable accessibilityRole="button" accessibilityLabel="뒤로" onPress={nav.back} style={styles.back}>
          <Text style={font.h3}>‹ 뒤로</Text>
        </Pressable>
      ) : null}

      <View style={{ flex: 1 }}>{screen}</View>

      {showTabs ? <TabBar /> : null}
    </View>
  );
}

function TabBar() {
  const nav = useNavigation();
  return (
    <View style={styles.tabBar}>
      {TAB_ROUTES.map((tab) => {
        const active = nav.current.route === tab.route;
        return (
          <Pressable
            key={tab.route}
            accessibilityRole="tab"
            accessibilityState={{ selected: active }}
            accessibilityLabel={tab.label}
            onPress={() => nav.switchTab(tab.route)}
            style={styles.tab}
          >
            <Text style={{ fontSize: 20, opacity: active ? 1 : 0.45 }}>{tab.emoji}</Text>
            <Text style={[font.tiny, { color: active ? colors.primaryDark : colors.textFaint }]}>{tab.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  loading: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  back: { paddingHorizontal: space.lg, paddingVertical: space.sm },
  tabBar: {
    flexDirection: 'row',
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: colors.surface,
    paddingVertical: space.sm,
  },
  tab: { flex: 1, alignItems: 'center', gap: 2 },
});
