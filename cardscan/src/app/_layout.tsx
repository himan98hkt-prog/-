import '../ui/platform';
import { t } from '../i18n';
import { router, Stack } from 'expo-router';
import { Fragment, ReactNode, useEffect, useMemo } from 'react';
import { warmUpOcr } from '../../modules/card-ocr';
import { StatusBar } from 'expo-status-bar';
import { onFollowUpTapped } from '../ui/reminders';
import { ProProvider } from '../ui/pro';
import { StoreProvider, useStore } from '../ui/store';
import { applyLanguage } from '../i18n';
import { FONT, T } from '../ui/theme';

/** 설정의 언어를 적용 — 바뀌면 화면 전체를 새 언어로 다시 그린다 */
function LanguageGate({ children }: { children: ReactNode }) {
  const { settings } = useStore();
  const lang = useMemo(() => applyLanguage(settings.language), [settings.language]);
  return <Fragment key={lang}>{children}</Fragment>;
}

function AppStack() {
  return (
    <>
      <StatusBar style="dark" />
      <Stack
        screenOptions={{
          headerBackTitle: t('뒤로'),
          headerTintColor: T.ink,
          headerTitleStyle: { fontFamily: FONT, fontWeight: '800', fontSize: 18, color: T.text },
          headerShadowVisible: false,
          headerStyle: { backgroundColor: T.bg },
          contentStyle: { backgroundColor: T.bg },
          animation: 'slide_from_right',
        }}
      >
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="review" options={{ title: t('인식 결과 확인') }} />
        <Stack.Screen name="card/[id]" options={{ title: t('명함 상세') }} />
        <Stack.Screen name="mycard" options={{ title: t('내 명함') }} />
      </Stack>
    </>
  );
}

export default function RootLayout() {
  // 웹(아이폰)은 문자 인식 엔진을 미리 받아 둔다 — 앱은 내장이라 아무 일 없음
  useEffect(() => warmUpOcr(), []);
  // 팔로업 알림을 누르면 그 명함으로
  useEffect(() => onFollowUpTapped((id) => router.push({ pathname: '/card/[id]', params: { id } })), []);
  return (
    <ProProvider>
      <StoreProvider>
        <LanguageGate>
          <AppStack />
        </LanguageGate>
      </StoreProvider>
    </ProProvider>
  );
}
