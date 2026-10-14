// 팔로업 알림 — 정한 날 아침 9시에 "○○○님께 연락할 날" 로컬 알림 (서버·요금 없음).
import * as Notifications from 'expo-notifications';
import { t } from '../i18n';
import { Platform } from 'react-native';
import { BusinessCard } from '../core/types';

const CHANNEL = 'followup';
const idFor = (cardId: string) => `followup-${cardId}`;
let ready: Promise<boolean> | null = null;

/** 알림 채널·권한 준비 (Android 13+ 는 알림 권한 필요) */
function prepare(): Promise<boolean> {
  if (Platform.OS === 'web') return Promise.resolve(false);
  ready ??= (async () => {
    Notifications.setNotificationHandler({
      handleNotification: async () => ({ shouldShowBanner: true, shouldShowList: true, shouldPlaySound: false, shouldSetBadge: false }),
    });
    if (Platform.OS === 'android') {
      await Notifications.setNotificationChannelAsync(CHANNEL, {
        name: t('팔로업 알림'),
        importance: Notifications.AndroidImportance.HIGH,
      });
    }
    const current = await Notifications.getPermissionsAsync();
    if (current.granted) return true;
    const asked = await Notifications.requestPermissionsAsync();
    return asked.granted;
  })().catch(() => false);
  return ready;
}

/** 명함의 팔로업 날짜에 맞춰 알림을 다시 건다 (날짜가 없거나 지났으면 취소만) */
export async function scheduleFollowUp(card: BusinessCard): Promise<void> {
  if (Platform.OS === 'web') return;
  await Notifications.cancelScheduledNotificationAsync(idFor(card.id)).catch(() => {});
  if (!card.followUp) return;
  const [y, m, d] = card.followUp.split('-').map(Number);
  const when = new Date(y, m - 1, d, 9, 0, 0);
  if (when.getTime() <= Date.now()) return; // 이미 지난 시각 — 명함첩 위 "오늘 연락할 사람"에 보인다
  if (!(await prepare())) return;
  const who = [card.name, card.title].filter(Boolean).join(' ');
  await Notifications.scheduleNotificationAsync({
    identifier: idFor(card.id),
    content: {
      title: t('📞 {1}님께 연락할 날', { 1: who || t('명함') }),
      body: [card.company, card.notes?.[0]?.text].filter(Boolean).join(' · ') || t('명함을 열어 연락해 보세요'),
      data: { cardId: card.id },
    },
    trigger: { type: Notifications.SchedulableTriggerInputTypes.DATE, date: when, channelId: CHANNEL },
  });
}

export function cancelFollowUp(cardId: string): void {
  if (Platform.OS === 'web') return;
  Notifications.cancelScheduledNotificationAsync(idFor(cardId)).catch(() => {});
}

/** 알림을 누르면 그 명함을 연다 */
export function onFollowUpTapped(open: (cardId: string) => void): () => void {
  if (Platform.OS === 'web') return () => {};
  const sub = Notifications.addNotificationResponseReceivedListener((res) => {
    const id = res.notification.request.content.data?.cardId;
    if (typeof id === 'string') open(id);
  });
  return () => sub.remove();
}
