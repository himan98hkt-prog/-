import React, { useEffect, useMemo, useState } from 'react';
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { weeklyReport } from '../../api';
import { backupEntries, restoreEntries } from '../../api/backup';
import { userMessageKey } from '../../api/errors';
import type { WeeklyReport } from '../../api/proxy';
import { relativeTime } from '../../core/date';
import { buildWeeklyDigest, monthGrid, weeklyHeadline, weeklyStats } from '../../core/diary';
import { emotionMeta } from '../../core/emotions';
import { reportCacheKey } from '../../core/reportCache';
import { assessHistoryRisk } from '../../core/health';
import { useT } from '../../i18n/useT';
import { useActivePet, useEntriesForActivePet, useIsPro, usePetStore } from '../../store/usePetStore';
import { Badge, Button, Card, Empty, SectionTitle } from '../components/Basics';
import { useNavigation } from '../navigation';
import { font, HIT_SIZE, radius, space } from '../theme';
import { useStyles, useTheme, type Theme } from '../useTheme';

/** "우리 아이 감정 다이어리" — 캘린더 + 주간 리포트 + 기록 목록 */
export function HistoryScreen() {
  const nav = useNavigation();
  const styles = useStyles(makeStyles);
  const { colors } = useTheme();
  const tr = useT();
  const { t } = tr;

  const pet = useActivePet();
  const entries = useEntriesForActivePet();
  const allEntries = usePetStore((s) => s.entries);
  const mergeEntries = usePetStore((s) => s.mergeEntries);
  const lastBackupAt = usePetStore((s) => s.lastBackupAt);
  const setLastBackupAt = usePetStore((s) => s.setLastBackupAt);
  const isPro = useIsPro();
  const cachedReport = usePetStore((s) => s.cachedReport);
  const putCachedReport = usePetStore((s) => s.putCachedReport);

  const today = new Date();
  const [cursor, setCursor] = useState({ year: today.getFullYear(), month: today.getMonth() + 1 });
  const [report, setReport] = useState<WeeklyReport | null>(null);
  const [loadingReport, setLoadingReport] = useState(false);
  const [syncing, setSyncing] = useState(false);

  const grid = useMemo(() => monthGrid(cursor.year, cursor.month, entries), [cursor, entries]);
  const stats = useMemo(() => weeklyStats(entries), [entries]);
  const risk = useMemo(() => assessHistoryRisk(entries), [entries]);

  const shiftMonth = (delta: number) => {
    setCursor((prev) => {
      const d = new Date(prev.year, prev.month - 1 + delta, 1);
      return { year: d.getFullYear(), month: d.getMonth() + 1 };
    });
  };

  /**
   * 리포트 캐시 키는 **모델에게 주는 입력 그대로**다.
   * 새 기록이 없으면 입력이 같고, 입력이 같으면 답도 같다 — 부를 이유가 없다.
   */
  const cacheKey = useMemo(
    () =>
      pet
        ? reportCacheKey(
            pet.id,
            tr.locale,
            buildWeeklyDigest(entries, (key) => t(key)),
          )
        : null,
    // t 는 매 렌더 새로 만들어지므로 의존성에서 뺀다. 언어가 바뀌면 tr.locale 이 바뀐다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [pet?.id, tr.locale, entries],
  );

  // 화면에 들어올 때 지난번 리포트가 그대로 유효하면 바로 보여 준다.
  useEffect(() => {
    if (!cacheKey) return;
    setReport(cachedReport(cacheKey));
  }, [cacheKey, cachedReport]);

  const loadReport = async () => {
    if (!pet || !cacheKey) return;
    if (!isPro) {
      nav.navigate('paywall');
      return;
    }

    const hit = cachedReport(cacheKey);
    if (hit) {
      setReport(hit);
      return;
    }

    setLoadingReport(true);
    try {
      const digest = buildWeeklyDigest(entries, (key) => t(key));
      const result = await weeklyReport(pet, digest, tr.locale);
      if (result) {
        setReport(result);
        putCachedReport(cacheKey, result);
      } else Alert.alert(t('history.reportUnavailable'), t('history.reportUnavailableDesc'));
    } catch (error) {
      Alert.alert(t('history.reportFailTitle'), t(userMessageKey(error)));
    } finally {
      setLoadingReport(false);
    }
  };

  const runBackup = async () => {
    if (!isPro) {
      nav.navigate('paywall');
      return;
    }
    setSyncing(true);
    try {
      const count = await backupEntries(allEntries);
      setLastBackupAt(Date.now());
      Alert.alert(t('history.backupDone', { count }));
    } catch (error) {
      Alert.alert(t('history.backupFailed'), t(userMessageKey(error)));
    } finally {
      setSyncing(false);
    }
  };

  const runRestore = async () => {
    if (!isPro) {
      nav.navigate('paywall');
      return;
    }
    setSyncing(true);
    try {
      const restored = await restoreEntries();
      const added = mergeEntries(restored);
      Alert.alert(t('history.restoreDone', { count: added }));
    } catch (error) {
      Alert.alert(t('history.backupFailed'), t(userMessageKey(error)));
    } finally {
      setSyncing(false);
    }
  };

  if (entries.length === 0) {
    return (
      <ScrollView contentContainerStyle={styles.page}>
        <Empty emoji="📔" title={t('history.emptyTitle')} desc={t('history.emptyDesc')} />
        <Button label={t('history.goAnalyze')} onPress={() => nav.switchTab('home')} />
      </ScrollView>
    );
  }

  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Text accessibilityRole="header" style={[font.h1, { color: colors.text }]}>
        {pet ? t('history.title', { name: pet.name }) : t('history.titlePlain')}
      </Text>

      {risk ? (
        <View
          accessibilityRole="alert"
          style={[
            styles.riskBanner,
            { backgroundColor: risk.level === 'vet' ? colors.dangerSoft : colors.warnSoft },
          ]}
        >
          <Text style={[font.bodyStrong, { color: risk.level === 'vet' ? colors.danger : colors.warnText }]}>
            {risk.level === 'vet' ? '🏥 ' : '👀 '}
            {tr.m(risk.message)}
          </Text>
        </View>
      ) : null}

      <Card style={{ gap: space.md }}>
        <View style={styles.monthHeader}>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={t('history.prevMonth')}
            onPress={() => shiftMonth(-1)}
            hitSlop={12}
            style={styles.monthButton}
          >
            <Text style={[font.h3, { color: colors.text }]}>‹</Text>
          </Pressable>
          <Text accessibilityRole="header" style={[font.h3, { color: colors.text }]}>
            {t('history.monthLabel', { year: cursor.year, month: cursor.month })}
          </Text>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={t('history.nextMonth')}
            onPress={() => shiftMonth(1)}
            hitSlop={12}
            style={styles.monthButton}
          >
            <Text style={[font.h3, { color: colors.text }]}>›</Text>
          </Pressable>
        </View>

        <View style={styles.weekRow}>
          {[0, 1, 2, 3, 4, 5, 6].map((index) => (
            <Text key={index} style={[font.tiny, styles.weekLabel]}>
              {t(`weekday.${index}`)}
            </Text>
          ))}
        </View>

        {grid.map((week, wi) => (
          <View key={wi} style={styles.weekRow}>
            {week.map((cell, ci) => {
              const meta = cell.summary?.dominant ? emotionMeta(cell.summary.dominant) : null;
              return (
                <View key={ci} style={styles.cell}>
                  {cell.day ? (
                    <View
                      accessible
                      accessibilityLabel={meta ? `${cell.day} ${t(meta.labelKey)}` : String(cell.day)}
                      style={[styles.dayBox, cell.isToday && { backgroundColor: colors.primarySoft }]}
                    >
                      <Text style={[font.tiny, { color: colors.textSoft }]}>{cell.day}</Text>
                      <Text style={{ fontSize: 15 }}>{meta ? meta.emoji : ' '}</Text>
                      {cell.summary && cell.summary.level !== 'none' ? (
                        <View
                          style={[
                            styles.dot,
                            {
                              backgroundColor: cell.summary.level === 'vet' ? colors.danger : colors.warnLine,
                            },
                          ]}
                        />
                      ) : null}
                    </View>
                  ) : null}
                </View>
              );
            })}
          </View>
        ))}
      </Card>

      <Card style={{ gap: space.md }}>
        <SectionTitle
          right={<Badge text={isPro ? 'PRO' : '🔒 PRO'} bg={colors.proSoft} fg={colors.proText} />}
        >
          {t('history.weeklyTitle')}
        </SectionTitle>
        <Text style={[font.body, { color: colors.text }]}>{tr.m(weeklyHeadline(stats))}</Text>
        <View style={styles.statRow}>
          <Stat label={t('history.statAnalyses')} value={t('history.countTimes', { count: stats.count })} />
          <Stat label={t('history.statDays')} value={t('history.countDays', { count: stats.activeDays })} />
          <Stat
            label={t('history.statPositive')}
            value={t('history.percent', { value: stats.positiveRatio })}
          />
          <Stat label={t('history.statVet')} value={t('history.countTimes', { count: stats.vetCount })} />
        </View>

        {report ? (
          <View style={{ gap: space.sm }}>
            <Text style={[font.h3, { color: colors.text }]}>{report.headline}</Text>
            <Text style={[font.body, { color: colors.text }]}>{report.trend}</Text>
            {report.concern ? (
              <Text style={[font.body, { color: colors.danger }]}>⚠️ {report.concern}</Text>
            ) : null}
            {report.todo.map((todo) => (
              <Text key={todo} style={[font.body, { color: colors.text }]}>
                ✅ {todo}
              </Text>
            ))}
          </View>
        ) : (
          <Button
            label={t(isPro ? 'history.reportCta' : 'history.reportProCta')}
            variant={isPro ? 'primary' : 'pro'}
            loading={loadingReport}
            onPress={() => void loadReport()}
          />
        )}
      </Card>

      <Card style={{ gap: space.sm }}>
        <SectionTitle
          right={isPro ? undefined : <Badge text="🔒 PRO" bg={colors.proSoft} fg={colors.proText} />}
        >
          {t('history.backupTitle')}
        </SectionTitle>
        <Text style={[font.small, { color: colors.textSoft }]}>{t('history.backupDesc')}</Text>
        {lastBackupAt ? (
          <Text style={[font.tiny, { color: colors.textFaint }]}>
            {t('history.lastBackup', { when: lastBackupAt })}
          </Text>
        ) : null}
        <Button
          label={t('history.backupNow')}
          variant="ghost"
          loading={syncing}
          onPress={() => void runBackup()}
        />
        <Button
          label={t('history.restoreNow')}
          variant="ghost"
          loading={syncing}
          onPress={() => void runRestore()}
        />
      </Card>

      <View>
        <SectionTitle>{t('history.allRecords', { count: entries.length })}</SectionTitle>
        <View style={{ gap: space.sm }}>
          {entries.map((entry) => {
            const meta = emotionMeta(entry.result.primaryEmotion);
            return (
              <Pressable
                key={entry.id}
                accessibilityRole="button"
                accessibilityLabel={`${entry.result.petVoiceMessage}, ${t(meta.labelKey)}`}
                onPress={() => nav.navigate('result', { entryId: entry.id })}
                style={styles.row}
              >
                <View style={[styles.rowDot, { backgroundColor: meta.color }]}>
                  <Text>{meta.emoji}</Text>
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={[font.bodyStrong, { color: colors.text }]} numberOfLines={1}>
                    {entry.result.petVoiceMessage}
                  </Text>
                  <Text style={[font.tiny, { color: colors.textFaint }]}>
                    {tr.relative(relativeTime(entry.createdAt))} · {t(meta.labelKey)}
                    {entry.context ? ` · ${entry.context}` : ''}
                  </Text>
                </View>
                {entry.health.level === 'vet' ? (
                  <Text>🏥</Text>
                ) : entry.health.level === 'watch' ? (
                  <Text>👀</Text>
                ) : null}
              </Pressable>
            );
          })}
        </View>
      </View>
    </ScrollView>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  const styles = useStyles(makeStyles);
  const { colors } = useTheme();
  return (
    <View accessible accessibilityLabel={`${label} ${value}`} style={styles.stat}>
      <Text style={[font.tiny, { color: colors.textFaint }]}>{label}</Text>
      <Text style={[font.bodyStrong, { color: colors.text }]}>{value}</Text>
    </View>
  );
}

const makeStyles = ({ colors }: Theme) =>
  StyleSheet.create({
    page: { padding: space.lg, gap: space.lg, paddingBottom: space.xxl },
    riskBanner: { padding: space.md, borderRadius: radius.md },
    monthHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
    monthButton: { minWidth: HIT_SIZE, minHeight: HIT_SIZE, alignItems: 'center', justifyContent: 'center' },
    weekRow: { flexDirection: 'row' },
    weekLabel: { flex: 1, textAlign: 'center', color: colors.textFaint },
    cell: { flex: 1, aspectRatio: 0.92, padding: 2 },
    dayBox: { flex: 1, alignItems: 'center', justifyContent: 'center', borderRadius: radius.sm },
    dot: { position: 'absolute', bottom: 4, width: 5, height: 5, borderRadius: 3 },
    statRow: { flexDirection: 'row', gap: space.sm },
    stat: {
      flex: 1,
      backgroundColor: colors.surfaceAlt,
      borderRadius: radius.sm,
      paddingVertical: space.sm,
      alignItems: 'center',
      gap: 2,
    },
    row: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: space.md,
      backgroundColor: colors.surface,
      borderRadius: radius.md,
      borderWidth: 1,
      borderColor: colors.border,
      padding: space.md,
    },
    rowDot: { width: 38, height: 38, borderRadius: 19, alignItems: 'center', justifyContent: 'center' },
  });
