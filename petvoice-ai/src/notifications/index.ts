import { Platform } from 'react-native';
import type { Translator } from '../i18n/useT';
import type { NotificationSettings } from '../store/usePetStore';
import { requestWithRationale } from '../ui/permissions';

/**
 * 저녁 기록 리마인더 + 주간 리포트 알림.
 *
 * 리텐션을 가장 크게 움직이는 기능이지만, 알림은 잘못 쓰면 바로 삭제로 이어진다.
 * 그래서 **로컬 알림 두 개**만 쓴다. 서버 푸시도, 마케팅 알림도 없다.
 *
 * expo-notifications 도 네이티브 모듈이라 없는 환경(웹 등)에서는 조용히 물러난다.
 */

type NotificationsModule = typeof import('expo-notifications');

let moduleCache: NotificationsModule | null | undefined;

function notifications(): NotificationsModule | null {
  if (moduleCache !== undefined) return moduleCache;
  if (Platform.OS !== 'android' && Platform.OS !== 'ios') {
    moduleCache = null;
    return null;
  }
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const mod = require('expo-notifications') as Partial<NotificationsModule> | undefined;
    moduleCache = typeof mod?.scheduleNotificationAsync === 'function' ? (mod as NotificationsModule) : null;
  } catch {
    moduleCache = null;
  }
  return moduleCache;
}

export function isNotificationsAvailable(): boolean {
  return notifications() !== null;
}

const DAILY_ID = 'petvoice-daily-reminder';
const WEEKLY_ID = 'petvoice-weekly-report';

async function cancel(identifier: string): Promise<void> {
  const mod = notifications();
  if (!mod) return;
  await mod.cancelScheduledNotificationAsync(identifier).catch(() => undefined);
}

/**
 * 설정을 실제 예약 상태와 맞춘다.
 * 권한을 거부당하면 **끈 상태로 되돌려** 돌려준다 — 화면이 켜져 있다고 거짓말하지 않도록.
 */
export async function syncReminders(
  settings: NotificationSettings,
  tr: Translator,
  petName?: string,
): Promise<NotificationSettings> {
  const mod = notifications();
  if (!mod) return { ...settings, daily: false, weekly: false };

  const wantsAny = settings.daily || settings.weekly;
  if (wantsAny) {
    const granted = await requestWithRationale(
      'notifications',
      async () => {
        const res = await mod.requestPermissionsAsync();
        return { granted: res.granted, canAskAgain: res.canAskAgain };
      },
      tr,
    );
    if (!granted) return { ...settings, daily: false, weekly: false };
  }

  const name = petName?.trim() || tr.t('notify.petFallback');

  await cancel(DAILY_ID);
  if (settings.daily) {
    await mod.scheduleNotificationAsync({
      identifier: DAILY_ID,
      content: {
        title: tr.t('notify.daily.title', { name }),
        body: tr.t('notify.daily.body'),
      },
      trigger: { hour: settings.hour, minute: 0, repeats: true },
    });
  }

  await cancel(WEEKLY_ID);
  if (settings.weekly) {
    await mod.scheduleNotificationAsync({
      identifier: WEEKLY_ID,
      content: {
        title: tr.t('notify.weekly.title'),
        body: tr.t('notify.weekly.body', { name }),
      },
      // 월요일 아침 9시 (expo 는 일요일이 1)
      trigger: { weekday: 2, hour: 9, minute: 0, repeats: true },
    });
  }

  return settings;
}

/** 데이터 초기화·계정 삭제 때 예약도 함께 지운다 */
export async function cancelAllReminders(): Promise<void> {
  await cancel(DAILY_ID);
  await cancel(WEEKLY_ID);
}
