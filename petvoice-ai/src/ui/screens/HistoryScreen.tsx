import React, { useMemo, useState } from 'react';
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { weeklyReport } from '../../api';
import { userMessage } from '../../api/errors';
import { relativeKo } from '../../core/date';
import { buildWeeklyDigest, monthGrid, weeklyHeadline, weeklyStats } from '../../core/diary';
import { emotionMeta } from '../../core/emotions';
import { assessHistoryRisk } from '../../core/health';
import type { WeeklyReport } from '../../api/proxy';
import { useActivePet, useEntriesForActivePet, useIsPro } from '../../store/usePetStore';
import { Badge, Button, Card, Empty, SectionTitle } from '../components/Basics';
import { useNavigation } from '../navigation';
import { colors, font, radius, space } from '../theme';

const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토'];

/** "우리 아이 감정 다이어리" — 캘린더 + 주간 리포트 + 기록 목록 */
export function HistoryScreen() {
  const nav = useNavigation();
  const pet = useActivePet();
  const entries = useEntriesForActivePet();
  const isPro = useIsPro();

  const today = new Date();
  const [cursor, setCursor] = useState({ year: today.getFullYear(), month: today.getMonth() + 1 });
  const [report, setReport] = useState<WeeklyReport | null>(null);
  const [loadingReport, setLoadingReport] = useState(false);

  const grid = useMemo(() => monthGrid(cursor.year, cursor.month, entries), [cursor, entries]);
  const stats = useMemo(() => weeklyStats(entries), [entries]);
  const risk = useMemo(() => assessHistoryRisk(entries), [entries]);

  const shiftMonth = (delta: number) => {
    setCursor((prev) => {
      const d = new Date(prev.year, prev.month - 1 + delta, 1);
      return { year: d.getFullYear(), month: d.getMonth() + 1 };
    });
  };

  const loadReport = async () => {
    if (!pet) return;
    if (!isPro) {
      nav.navigate('paywall');
      return;
    }
    setLoadingReport(true);
    try {
      const result = await weeklyReport(pet, buildWeeklyDigest(entries));
      if (result) setReport(result);
      else Alert.alert('리포트를 만들 수 없어요', '서버 설정이 아직 안 돼 있어요. (데모 모드)');
    } catch (error) {
      Alert.alert('리포트 생성 실패', userMessage(error));
    } finally {
      setLoadingReport(false);
    }
  };

  if (entries.length === 0) {
    return (
      <ScrollView contentContainerStyle={styles.page}>
        <Empty emoji="📔" title="감정 다이어리가 비어 있어요" desc="분석을 하면 날짜별로 감정이 쌓여요." />
        <Button label="분석하러 가기" onPress={() => nav.switchTab('home')} />
      </ScrollView>
    );
  }

  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Text style={font.h1}>{pet ? `${pet.name} 감정 다이어리` : '감정 다이어리'}</Text>

      {risk ? (
        <View
          accessibilityRole="alert"
          style={[
            styles.riskBanner,
            { backgroundColor: risk.level === 'vet' ? colors.dangerSoft : colors.warnSoft },
          ]}
        >
          <Text style={[font.bodyStrong, { color: risk.level === 'vet' ? colors.danger : '#8A6D00' }]}>
            {risk.level === 'vet' ? '🏥 ' : '👀 '}
            {risk.message}
          </Text>
        </View>
      ) : null}

      <Card style={{ gap: space.md }}>
        <View style={styles.monthHeader}>
          <Pressable accessibilityRole="button" accessibilityLabel="이전 달" onPress={() => shiftMonth(-1)} hitSlop={12}>
            <Text style={font.h3}>‹</Text>
          </Pressable>
          <Text style={font.h3}>
            {cursor.year}년 {cursor.month}월
          </Text>
          <Pressable accessibilityRole="button" accessibilityLabel="다음 달" onPress={() => shiftMonth(1)} hitSlop={12}>
            <Text style={font.h3}>›</Text>
          </Pressable>
        </View>

        <View style={styles.weekRow}>
          {WEEKDAYS.map((w) => (
            <Text key={w} style={[font.tiny, styles.weekLabel]}>
              {w}
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
                    <View style={[styles.dayBox, cell.isToday && styles.dayToday]}>
                      <Text style={[font.tiny, { color: colors.textSoft }]}>{cell.day}</Text>
                      <Text style={{ fontSize: 15 }}>{meta ? meta.emoji : ' '}</Text>
                      {cell.summary && cell.summary.level !== 'none' ? (
                        <View
                          style={[
                            styles.dot,
                            { backgroundColor: cell.summary.level === 'vet' ? colors.danger : colors.warn },
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
        <SectionTitle right={<Badge text={isPro ? 'PRO' : '🔒 PRO'} bg={colors.proSoft} fg={colors.pro} />}>
          이번 주 리포트
        </SectionTitle>
        <Text style={font.body}>{weeklyHeadline(stats)}</Text>
        <View style={styles.statRow}>
          <Stat label="분석" value={`${stats.count}회`} />
          <Stat label="기록한 날" value={`${stats.activeDays}일`} />
          <Stat label="긍정 비율" value={`${stats.positiveRatio}%`} />
          <Stat label="병원 권고" value={`${stats.vetCount}회`} />
        </View>

        {report ? (
          <View style={{ gap: space.sm }}>
            <Text style={font.h3}>{report.headline}</Text>
            <Text style={font.body}>{report.trend}</Text>
            {report.concern ? (
              <Text style={[font.body, { color: colors.danger }]}>⚠️ {report.concern}</Text>
            ) : null}
            {report.todo.map((todo) => (
              <Text key={todo} style={font.body}>
                ✅ {todo}
              </Text>
            ))}
          </View>
        ) : (
          <Button
            label={isPro ? 'AI 주간 행동 리포트 받기' : '프로로 주간 리포트 열기'}
            variant={isPro ? 'primary' : 'pro'}
            loading={loadingReport}
            onPress={() => void loadReport()}
          />
        )}
      </Card>

      <View>
        <SectionTitle>전체 기록 {entries.length}건</SectionTitle>
        <View style={{ gap: space.sm }}>
          {entries.map((entry) => {
            const meta = emotionMeta(entry.result.primaryEmotion);
            return (
              <Pressable
                key={entry.id}
                accessibilityRole="button"
                onPress={() => nav.navigate('result', { entryId: entry.id })}
                style={styles.row}
              >
                <View style={[styles.rowDot, { backgroundColor: meta.color }]}>
                  <Text>{meta.emoji}</Text>
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={font.bodyStrong} numberOfLines={1}>
                    {entry.result.petVoiceMessage}
                  </Text>
                  <Text style={[font.tiny, { color: colors.textFaint }]}>
                    {relativeKo(entry.createdAt)} · {meta.label}
                    {entry.context ? ` · ${entry.context}` : ''}
                  </Text>
                </View>
                {entry.health.level === 'vet' ? <Text>🏥</Text> : entry.health.level === 'watch' ? <Text>👀</Text> : null}
              </Pressable>
            );
          })}
        </View>
      </View>
    </ScrollView>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.stat}>
      <Text style={[font.tiny, { color: colors.textFaint }]}>{label}</Text>
      <Text style={font.bodyStrong}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  page: { padding: space.lg, gap: space.lg, paddingBottom: space.xxl },
  riskBanner: { padding: space.md, borderRadius: radius.md },
  monthHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  weekRow: { flexDirection: 'row' },
  weekLabel: { flex: 1, textAlign: 'center', color: colors.textFaint },
  cell: { flex: 1, aspectRatio: 0.92, padding: 2 },
  dayBox: { flex: 1, alignItems: 'center', justifyContent: 'center', borderRadius: radius.sm },
  dayToday: { backgroundColor: colors.primarySoft },
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
