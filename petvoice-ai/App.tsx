import { StatusBar } from 'expo-status-bar';
import React, { useEffect } from 'react';
import { ActivityIndicator, AppState, Pressable, SafeAreaView, StyleSheet, Text, View } from 'react-native';
import { isConfigured } from './src/api';
import { assertNoAiKeyInClient } from './src/api/config';
import { ensureSession } from './src/api/supabase';
import { syncSubscriptionFromServer } from './src/billing/useBilling';
import { detectDeviceLocale } from './src/i18n/detect';
import { useT } from './src/i18n/useT';
import { initErrorReporting } from './src/diagnostics';
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
import { font, HIT_SIZE, space } from './src/ui/theme';
import { useQueueDrain } from './src/ui/useAnalyze';
import { useStyles, useTheme, type Theme } from './src/ui/useTheme';

// 클라이언트 번들에 AI 키가 섞여 들어오면 개발 단계에서 즉시 알아채도록.
if (__DEV__) assertNoAiKeyInClient();

export default function App() {
  return (
    <NavigationProvider>
      <Root />
    </NavigationProvider>
  );
}

function Root() {
  const { colors, scheme } = useTheme();
  return (
    <SafeAreaView style={[styles.root, { backgroundColor: colors.bg }]}>
      <StatusBar style={scheme === 'dark' ? 'light' : 'dark'} />
      <Router />
    </SafeAreaView>
  );
}

function Router() {
  const nav = useNavigation();
  const themed = useStyles(makeStyles);
  const { colors } = useTheme();
  const { t } = useT();

  const hydrated = usePetStore((s) => s.hydrated);
  const entriesLoaded = usePetStore((s) => s.entriesLoaded);
  const onboarded = usePetStore((s) => s.onboarded);
  const petCount = usePetStore((s) => s.pets.length);
  const diagnostics = usePetStore((s) => s.diagnostics);
  const queue = useQueueDrain();

  useEffect(() => {
    if (!hydrated) return;
    const state = usePetStore.getState();
    // 첫 실행이면 기기 언어를 따라간다. 이후에는 사용자의 선택을 존중한다.
    // (기록 불러오기는 스토어가 복원 직후에 스스로 처리한다)
    if (!state.onboarded) state.setLocale(detectDeviceLocale());
  }, [hydrated]);

  useEffect(() => {
    initErrorReporting(diagnostics);
  }, [diagnostics]);

  useEffect(() => {
    if (!isConfigured) return;
    void (async () => {
      // 익명 세션을 미리 만들어 첫 분석에서 로그인 지연이 없도록 한다.
      await ensureSession();
      // 해지·환불·결제 실패는 앱 밖에서 일어난다. 로컬 값만 믿지 않고 서버와 맞춘다.
      await syncSubscriptionFromServer().catch(() => undefined);
    })();
  }, []);

  // 앱으로 돌아올 때마다 대기 중인 분석을 처리해 본다.
  useEffect(() => {
    if (!entriesLoaded) return;
    void queue.drain();
    const sub = AppState.addEventListener('change', (state) => {
      if (state === 'active') void queue.drain();
    });
    return () => sub.remove();
  }, [entriesLoaded, queue]);

  if (!hydrated || !entriesLoaded) {
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
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={t('common.back')}
          onPress={nav.back}
          style={themed.back}
        >
          <Text style={[font.h3, { color: colors.text }]}>‹ {t('common.back')}</Text>
        </Pressable>
      ) : null}

      <View style={{ flex: 1 }}>{screen}</View>

      {showTabs ? <TabBar /> : null}
    </View>
  );
}

function TabBar() {
  const nav = useNavigation();
  const themed = useStyles(makeStyles);
  const { colors } = useTheme();
  const { t } = useT();

  return (
    <View style={themed.tabBar} accessibilityRole="tablist">
      {TAB_ROUTES.map((tab) => {
        const active = nav.current.route === tab.route;
        const label = t(tab.labelKey);
        return (
          <Pressable
            key={tab.route}
            accessibilityRole="tab"
            accessibilityState={{ selected: active }}
            accessibilityLabel={label}
            onPress={() => nav.switchTab(tab.route)}
            style={themed.tab}
          >
            <Text style={{ fontSize: 20, opacity: active ? 1 : 0.45 }}>{tab.emoji}</Text>
            <Text style={[font.tiny, { color: active ? colors.primaryText : colors.textFaint }]}>{label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  loading: { flex: 1, alignItems: 'center', justifyContent: 'center' },
});

const makeStyles = ({ colors }: Theme) =>
  StyleSheet.create({
    back: { paddingHorizontal: space.lg, paddingVertical: space.sm, minHeight: HIT_SIZE, justifyContent: 'center' },
    tabBar: {
      flexDirection: 'row',
      borderTopWidth: 1,
      borderTopColor: colors.border,
      backgroundColor: colors.surface,
      paddingVertical: space.sm,
    },
    tab: { flex: 1, alignItems: 'center', gap: 2, minHeight: HIT_SIZE, justifyContent: 'center' },
  });
