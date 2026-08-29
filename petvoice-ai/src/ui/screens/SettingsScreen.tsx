import Constants from 'expo-constants';
import React, { useEffect, useState } from 'react';
import { Alert, Linking, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { isConfigured } from '../../api';
import { pruneBackupBefore } from '../../api/backup';
import { deleteAccount } from '../../api/supabase';
import { useBilling } from '../../billing/useBilling';
import { describeSubscription } from '../../core/billing';
import { PET_LABEL_KEY } from '../../core/emotions';
import { PRO_PRICE_KRW } from '../../core/quota';
import {
  countExpiring,
  RETENTION_POLICIES,
  retentionCutoff,
  type RetentionPolicy,
} from '../../core/retention';
import type { Locale } from '../../core/types';
import { LOCALES } from '../../i18n';
import { useT } from '../../i18n/useT';
import { cancelAllReminders, syncReminders } from '../../notifications';
import { useActivePet, usePetStore, useIsPro, useQuota } from '../../store/usePetStore';
import { Badge, Button, Card, Chip, SectionTitle, ToggleRow } from '../components/Basics';
import { TestModeCard } from '../components/TestModeCard';
import { LINKS } from '../links';
import { useNavigation } from '../navigation';
import { font, HIT_SIZE, radius, space } from '../theme';
import { useStyles, useTheme, type Theme, type ThemeMode } from '../useTheme';

const THEME_MODES: { mode: ThemeMode; key: string }[] = [
  { mode: 'system', key: 'settings.themeSystem' },
  { mode: 'light', key: 'settings.themeLight' },
  { mode: 'dark', key: 'settings.themeDark' },
];

const RETENTION_LABEL: Record<RetentionPolicy, string> = {
  forever: 'settings.retentionForever',
  '2y': 'settings.retention2y',
  '1y': 'settings.retention1y',
  '6m': 'settings.retention6m',
};

export function SettingsScreen() {
  const nav = useNavigation();
  const styles = useStyles(makeStyles);
  const { colors } = useTheme();
  const tr = useT();
  const { t } = tr;

  const pets = usePetStore((s) => s.pets);
  const removePet = usePetStore((s) => s.removePet);
  const resetAll = usePetStore((s) => s.resetAll);
  const entries = usePetStore((s) => s.entries);
  const subscription = usePetStore((s) => s.subscription);
  const locale = usePetStore((s) => s.locale);
  const setLocale = usePetStore((s) => s.setLocale);
  const themeMode = usePetStore((s) => s.themeMode);
  const setThemeMode = usePetStore((s) => s.setThemeMode);
  const notifications = usePetStore((s) => s.notifications);
  const setNotifications = usePetStore((s) => s.setNotifications);
  const diagnostics = usePetStore((s) => s.diagnostics);
  const setDiagnostics = usePetStore((s) => s.setDiagnostics);
  const retention = usePetStore((s) => s.retention);
  const setRetention = usePetStore((s) => s.setRetention);
  const applyRetention = usePetStore((s) => s.applyRetention);

  const activePet = useActivePet();
  const isPro = useIsPro();
  const quota = useQuota();
  const billing = useBilling();
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (!billing.notice) return;
    Alert.alert(t('paywall.subscriptionTitle'), tr.m(billing.notice), [
      { text: t('common.confirm'), onPress: billing.clearNotice },
    ]);
  }, [billing.notice, billing.clearNotice, t, tr]);

  const toggleNotification = async (patch: { daily?: boolean; weekly?: boolean }) => {
    const next = { ...notifications, ...patch };
    const applied = await syncReminders(next, tr, activePet?.name);
    setNotifications(applied);
  };

  /**
   * 보관 기간을 줄이면 그 자리에서 기록이 사라진다.
   * 몇 건이 지워지는지 **먼저 세어 보여 주고** 확인을 받는다 —
   * 되돌릴 수 없는 삭제를 칩 한 번으로 실행하면 안 된다.
   */
  const changeRetention = (next: RetentionPolicy) => {
    if (next === retention) return;

    const doomed = countExpiring(
      entries.map((e) => e.createdAt),
      next,
    );
    const apply = () => {
      setRetention(next);
      void applyRetention();

      // 서버 백업도 같은 규칙으로 정리한다. 기기만 지우면 두 곳의 규칙이 갈라지고,
      // 폰을 바꿔 복원하는 순간 지운 기록이 되돌아온다.
      const cutoff = retentionCutoff(next);
      if (cutoff !== null && isConfigured) {
        void pruneBackupBefore(cutoff).catch(() =>
          // 네트워크가 없을 수 있다. 조용히 넘기지 말고 알린다 —
          // 사용자는 서버에서도 지워졌다고 믿게 되기 때문이다.
          Alert.alert(t('settings.retentionServerFailed'), t('settings.retentionServerFailedDesc')),
        );
      }
    };

    if (doomed === 0) {
      apply();
      return;
    }
    Alert.alert(t('settings.retentionConfirmTitle'), t('settings.retentionConfirmDesc', { count: doomed }), [
      { text: t('common.cancel'), style: 'cancel' },
      { text: t('common.delete'), style: 'destructive', onPress: apply },
    ]);
  };

  /** Play 정책: 로그인 없는 로컬 앱은 "모든 데이터 초기화"를 반드시 제공해야 한다. */
  const confirmReset = () => {
    Alert.alert(
      t('settings.resetTitle'),
      t('settings.resetDesc', { pets: pets.length, entries: entries.length }),
      [
        { text: t('common.cancel'), style: 'cancel' },
        {
          text: t('settings.resetConfirm'),
          style: 'destructive',
          onPress: () => {
            resetAll();
            void cancelAllReminders(); // 데이터를 지웠는데 알림만 계속 오면 안 된다
            Alert.alert(t('settings.resetDone'), t('settings.resetDoneDesc'));
            nav.switchTab('home');
          },
        },
      ],
    );
  };

  /**
   * Alert 의 onPress 에 async 함수를 그대로 꽂으면 거부(rejection)를 아무도 받지 않는다.
   * 이름 붙인 함수로 빼고 `void` 로 부른다 — "일부러 안 기다린다"는 표시다.
   */
  const runAccountDelete = async () => {
    setDeleting(true);
    try {
      await deleteAccount();
      resetAll();
      void cancelAllReminders();
      Alert.alert(t('settings.deleteAccountDone'), t('settings.deleteAccountDoneDesc'));
      nav.switchTab('home');
    } catch {
      Alert.alert(t('settings.deleteAccountFail'), t('settings.deleteAccountFailDesc'));
    } finally {
      setDeleting(false);
    }
  };

  /** Play 정책: 계정을 만드는 앱은 앱 안에서 계정 삭제를 제공해야 한다. */
  const confirmAccountDelete = () => {
    Alert.alert(t('settings.deleteAccountTitle'), t('settings.deleteAccountDesc'), [
      { text: t('common.cancel'), style: 'cancel' },
      {
        text: t('settings.deleteAccount'),
        style: 'destructive',
        onPress: () => void runAccountDelete(),
      },
    ]);
  };

  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Text accessibilityRole="header" style={[font.h1, { color: colors.text }]}>
        {t('settings.title')}
      </Text>

      <Card style={{ gap: space.md }}>
        <SectionTitle
          right={
            <Badge
              text={isPro ? 'PRO' : 'FREE'}
              bg={isPro ? colors.proSoft : colors.surfaceAlt}
              fg={isPro ? colors.proText : colors.textSoft}
            />
          }
        >
          {t('settings.subscription')}
        </SectionTitle>
        <Text style={[font.body, { color: colors.text }]}>{tr.m(describeSubscription(subscription))}</Text>
        <Text style={[font.small, { color: colors.textSoft }]}>{tr.m(quota.label)}</Text>
        {isPro ? (
          <Button label={t('settings.manageSub')} variant="ghost" onPress={() => void billing.openManage()} />
        ) : (
          <Button
            label={`${t('settings.subscribeCta')} · ${t('paywall.perMonth', {
              price: `${PRO_PRICE_KRW.toLocaleString(locale)}${locale === 'en' ? ' KRW' : '원'}`,
            })}`}
            variant="pro"
            onPress={() => nav.navigate('paywall')}
          />
        )}
        <Button
          label={t('settings.restore')}
          variant="ghost"
          loading={billing.busy}
          disabled={!billing.available}
          onPress={() => void billing.restore()}
        />
        {!billing.available ? (
          <Text style={[font.tiny, { color: colors.textFaint }]}>{t('settings.billingUnavailable')}</Text>
        ) : null}
      </Card>

      <Card style={{ gap: space.md }}>
        <SectionTitle
          right={
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={t('settings.addPet')}
              onPress={() => nav.navigate('petForm')}
              hitSlop={8}
            >
              <Text style={[font.small, { color: colors.primaryText }]}>{t('settings.addPet')}</Text>
            </Pressable>
          }
        >
          {t('settings.myPets')}
        </SectionTitle>
        {pets.length === 0 ? (
          <Text style={[font.small, { color: colors.textSoft }]}>{t('settings.noPets')}</Text>
        ) : (
          pets.map((pet) => (
            <View key={pet.id} style={styles.petRow}>
              <View style={{ flex: 1 }}>
                <Text style={[font.bodyStrong, { color: colors.text }]}>{pet.name}</Text>
                <Text style={[font.tiny, { color: colors.textFaint }]}>
                  {t(PET_LABEL_KEY[pet.type])}
                  {pet.breed ? ` · ${pet.breed}` : ''}
                </Text>
              </View>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={`${pet.name} ${t('common.edit')}`}
                onPress={() => nav.navigate('petForm', { petId: pet.id })}
                hitSlop={8}
                style={styles.rowAction}
              >
                <Text style={[font.small, { color: colors.primaryText }]}>{t('common.edit')}</Text>
              </Pressable>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={`${pet.name} ${t('common.delete')}`}
                hitSlop={8}
                style={styles.rowAction}
                onPress={() =>
                  Alert.alert(t('settings.deletePetTitle', { name: pet.name }), t('settings.deletePetDesc'), [
                    { text: t('common.cancel'), style: 'cancel' },
                    { text: t('common.delete'), style: 'destructive', onPress: () => removePet(pet.id) },
                  ])
                }
              >
                <Text style={[font.small, { color: colors.danger }]}>{t('common.delete')}</Text>
              </Pressable>
            </View>
          ))
        )}
      </Card>

      <Card style={{ gap: space.lg }}>
        <SectionTitle>{t('settings.appearance')}</SectionTitle>

        <View style={{ gap: space.sm }}>
          <Text style={[font.bodyStrong, { color: colors.text }]}>{t('settings.theme')}</Text>
          <View style={styles.chipRow}>
            {THEME_MODES.map((item) => (
              <Chip
                key={item.mode}
                label={t(item.key)}
                selected={themeMode === item.mode}
                onPress={() => setThemeMode(item.mode)}
              />
            ))}
          </View>
        </View>

        <View style={{ gap: space.sm }}>
          <Text style={[font.bodyStrong, { color: colors.text }]}>{t('settings.language')}</Text>
          <View style={styles.chipRow}>
            {LOCALES.map((item) => (
              <Chip
                key={item.key}
                label={item.label}
                selected={locale === item.key}
                onPress={() => setLocale(item.key as Locale)}
              />
            ))}
          </View>
        </View>
      </Card>

      <Card style={{ gap: space.sm }}>
        <SectionTitle>{t('settings.notifications')}</SectionTitle>
        <ToggleRow
          label={t('settings.dailyReminder')}
          desc={t('settings.dailyReminderDesc', { time: `${notifications.hour}:00` })}
          value={notifications.daily}
          onChange={(next) => void toggleNotification({ daily: next })}
        />
        <ToggleRow
          label={t('settings.weeklyReport')}
          desc={t('settings.weeklyReportDesc')}
          value={notifications.weekly}
          onChange={(next) => void toggleNotification({ weekly: next })}
        />
      </Card>

      <Card style={{ gap: space.md }}>
        <SectionTitle>{t('settings.privacyData')}</SectionTitle>
        <LinkRow label={t('settings.privacyPolicy')} onPress={() => void Linking.openURL(LINKS.privacy)} />
        <LinkRow label={t('settings.terms')} onPress={() => void Linking.openURL(LINKS.terms)} />
        <LinkRow label={t('settings.contact')} onPress={() => void Linking.openURL(LINKS.support)} />
        <ToggleRow
          label={t('settings.diagnostics')}
          desc={t('settings.diagnosticsDesc')}
          value={diagnostics}
          onChange={setDiagnostics}
        />

        <View style={{ gap: space.sm }}>
          <Text style={[font.bodyStrong, { color: colors.text }]}>{t('settings.retention')}</Text>
          <Text style={[font.tiny, { color: colors.textFaint }]}>{t('settings.retentionDesc')}</Text>
          <View style={styles.chipRow}>
            {RETENTION_POLICIES.map((policy) => (
              <Chip
                key={policy}
                label={t(RETENTION_LABEL[policy])}
                selected={retention === policy}
                onPress={() => changeRetention(policy)}
              />
            ))}
          </View>
        </View>
        <LinkRow label={t('settings.insights')} onPress={() => nav.navigate('insights')} />
        <Button label={t('settings.resetAll')} variant="danger" onPress={confirmReset} />
        {isConfigured ? (
          <Button
            label={t('settings.deleteAccount')}
            variant="danger"
            loading={deleting}
            onPress={confirmAccountDelete}
          />
        ) : null}
      </Card>

      <TestModeCard />

      <Card style={{ gap: space.sm }}>
        <SectionTitle>{t('settings.appInfo')}</SectionTitle>
        <Row label={t('settings.version')} value={String(Constants.expoConfig?.version ?? '1.0.0')} />
        <Row
          label={t('settings.server')}
          value={t(isConfigured ? 'settings.serverConnected' : 'settings.serverDemo')}
        />
        <Text style={[font.tiny, { color: colors.textFaint, marginTop: space.sm }]}>
          {t('settings.disclaimer')}
        </Text>
      </Card>
    </ScrollView>
  );
}

function LinkRow({ label, onPress }: { label: string; onPress: () => void }) {
  const styles = useStyles(makeStyles);
  const { colors } = useTheme();
  return (
    <Pressable accessibilityRole="link" accessibilityLabel={label} onPress={onPress} style={styles.linkRow}>
      <Text style={[font.body, { color: colors.text }]}>{label}</Text>
      <Text style={{ color: colors.textFaint }}>›</Text>
    </Pressable>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  const styles = useStyles(makeStyles);
  const { colors } = useTheme();
  return (
    <View style={styles.infoRow} accessible accessibilityLabel={`${label} ${value}`}>
      <Text style={[font.small, { color: colors.textSoft }]}>{label}</Text>
      <Text style={[font.small, { color: colors.text }]}>{value}</Text>
    </View>
  );
}

const makeStyles = ({ colors }: Theme) =>
  StyleSheet.create({
    page: { padding: space.lg, gap: space.lg, paddingBottom: space.xxl },
    petRow: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: space.md,
      paddingVertical: space.sm,
      borderBottomWidth: 1,
      borderBottomColor: colors.border,
    },
    rowAction: { minHeight: HIT_SIZE, justifyContent: 'center', paddingHorizontal: space.xs },
    chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: space.sm },
    linkRow: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      minHeight: HIT_SIZE,
      paddingVertical: space.sm,
      borderRadius: radius.sm,
    },
    infoRow: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      paddingVertical: space.xs,
    },
  });
