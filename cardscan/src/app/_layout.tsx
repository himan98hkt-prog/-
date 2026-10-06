import '../ui/platform';
import { router, Stack } from 'expo-router';
import { useEffect } from 'react';
import { warmUpOcr } from '../../modules/card-ocr';
import { StatusBar } from 'expo-status-bar';
import { onFollowUpTapped } from '../ui/reminders';
import { StoreProvider } from '../ui/store';

export default function RootLayout() {
  // 웹(아이폰)은 문자 인식 엔진을 미리 받아 둔다 — 앱은 내장이라 아무 일 없음
  useEffect(() => warmUpOcr(), []);
  // 팔로업 알림을 누르면 그 명함으로
  useEffect(() => onFollowUpTapped((id) => router.push({ pathname: '/card/[id]', params: { id } })), []);
  return (
    <StoreProvider>
      <StatusBar style="dark" />
      <Stack screenOptions={{ headerBackTitle: '뒤로' }}>
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="review" options={{ title: '인식 결과 확인' }} />
        <Stack.Screen name="card/[id]" options={{ title: '명함 상세' }} />
        <Stack.Screen name="mycard" options={{ title: '내 명함' }} />
      </Stack>
    </StoreProvider>
  );
}
