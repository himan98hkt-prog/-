import * as FileSystem from 'expo-file-system';
import * as Sharing from 'expo-sharing';
import React, { useMemo, useState } from 'react';
import { Alert, ScrollView, StyleSheet, Text, View } from 'react-native';
import {
  buildFeedbackExport,
  MIN_SAMPLES,
  summarizeFeedback,
  summarizeQuality,
  type RatingBucket,
} from '../../core/insights';
import { useT } from '../../i18n/useT';
import { usePetStore } from '../../store/usePetStore';
import { Button, Card, Empty, SectionTitle } from '../components/Basics';
import { font, radius, space } from '../theme';
import { useStyles, useTheme, type Theme } from '../useTheme';

/**
 * 모아 둔 피드백과 품질 지표를 보는 화면.
 *
 * 자랑용 대시보드가 아니다. "어떤 상황에서 어떤 감정을 틀리는가"에 답하는 게 전부라
 * 정확도가 낮은 항목이 위에 온다.
 *
 * 여기 숫자는 **사용자의 자기 보고**다. 정답지가 아니다 —
 * 그 한계를 화면에도 적어 둔다. 안 적어 두면 이 숫자가 "정확도"로 인용된다.
 */
export function InsightsScreen() {
  const styles = useStyles(makeStyles);
  const { colors } = useTheme();
  const { t } = useT();

  const entries = usePetStore((s) => s.entries);
  const attempts = usePetStore((s) => s.attempts);

  const feedback = useMemo(() => summarizeFeedback(entries), [entries]);
  const quality = useMemo(() => summarizeQuality(attempts), [attempts]);
  const [exporting, setExporting] = useState(false);

  /**
   * 집계된 숫자만 파일로 내보낸다 — 평가 도구(`npm run eval -- --felt`)가
   * 라벨로 잰 정확도와 나란히 놓고 볼 수 있게.
   *
   * 말풍선·사진 경로·상황 문구·아이 이름은 하나도 들어가지 않는다.
   * 정확도를 맞대 보려고 개인 기록을 넘길 이유는 없다.
   */
  const runExport = async () => {
    setExporting(true);
    try {
      const payload = buildFeedbackExport(feedback, quality);
      const path = `${FileSystem.cacheDirectory}petvoice-feedback.json`;
      await FileSystem.writeAsStringAsync(path, JSON.stringify(payload, null, 2));

      if (await Sharing.isAvailableAsync()) {
        await Sharing.shareAsync(path, { mimeType: 'application/json', UTI: 'public.json' });
      } else {
        Alert.alert(t('insights.exportSaved'), path);
      }
    } catch {
      Alert.alert(t('insights.exportFailed'));
    } finally {
      setExporting(false);
    }
  };

  if (feedback.analyses === 0) {
    return (
      <ScrollView contentContainerStyle={styles.page}>
        <Text style={[font.h2, { color: colors.text }]}>{t('insights.title')}</Text>
        <Empty emoji="📊" title={t('insights.emptyTitle')} desc={t('insights.emptyDesc')} />
      </ScrollView>
    );
  }

  return (
    <ScrollView contentContainerStyle={styles.page}>
      <Text style={[font.h2, { color: colors.text }]}>{t('insights.title')}</Text>

      <Card style={{ gap: space.sm }}>
        <SectionTitle>{t('insights.overall')}</SectionTitle>
        <View style={styles.statRow}>
          <Stat label={t('insights.analyses')} value={String(feedback.analyses)} />
          <Stat label={t('insights.rated')} value={String(feedback.rated)} />
          <Stat label={t('insights.agreeRate')} value={feedback.rate === null ? '—' : `${feedback.rate}%`} />
        </View>
        <Text style={[font.tiny, { color: colors.textFaint }]}>
          {feedback.rated === 0 ? t('insights.noRatings') : t('insights.selfReported')}
        </Text>
      </Card>

      {feedback.rated > 0 ? (
        <>
          <Buckets title={t('insights.byEmotion')} buckets={feedback.byEmotion} translate={t} />
          {feedback.byContext.length > 0 ? (
            <Buckets title={t('insights.byContext')} buckets={feedback.byContext} translate={t} />
          ) : null}
          <Buckets title={t('insights.byMedia')} buckets={feedback.byMedia} translate={t} />
        </>
      ) : null}

      <Card style={{ gap: space.sm }}>
        <SectionTitle>{t('insights.quality')}</SectionTitle>
        {quality.attempts === 0 ? (
          <Text style={[font.small, { color: colors.textSoft }]}>{t('insights.noAttempts')}</Text>
        ) : (
          <>
            <View style={styles.statRow}>
              <Stat label={t('insights.attempts')} value={String(quality.attempts)} />
              <Stat
                label={t('insights.failureRate')}
                value={quality.failureRate === null ? '—' : `${quality.failureRate}%`}
              />
              <Stat
                label={t('insights.medianTime')}
                value={quality.medianMs === null ? '—' : `${(quality.medianMs / 1000).toFixed(1)}s`}
              />
            </View>
            {quality.topCodes.map((row) => (
              <View key={row.code} style={styles.codeRow}>
                <Text style={[font.small, { color: colors.textSoft }]}>{t(`errors.${row.code}`)}</Text>
                <Text style={[font.small, { color: colors.text }]}>{row.count}</Text>
              </View>
            ))}
            <Text style={[font.tiny, { color: colors.textFaint }]}>{t('insights.qualityNote')}</Text>
          </>
        )}
      </Card>

      <Card style={{ backgroundColor: colors.warnSoft, borderColor: colors.warnLine, gap: space.xs }}>
        <Text style={[font.bodyStrong, { color: colors.text }]}>{t('insights.limitTitle')}</Text>
        <Text style={[font.small, { color: colors.textSoft }]}>{t('insights.limitDesc')}</Text>
      </Card>

      <Card style={{ gap: space.sm }}>
        <SectionTitle>{t('insights.exportTitle')}</SectionTitle>
        <Text style={[font.small, { color: colors.textSoft }]}>{t('insights.exportDesc')}</Text>
        <Button
          label={t('insights.export')}
          variant="ghost"
          loading={exporting}
          onPress={() => void runExport()}
        />
      </Card>
    </ScrollView>
  );
}

function Buckets({
  title,
  buckets,
  translate,
}: {
  title: string;
  buckets: RatingBucket[];
  translate: (key: string, params?: Record<string, string | number>) => string;
}) {
  const styles = useStyles(makeStyles);
  const { colors } = useTheme();

  return (
    <Card style={{ gap: space.sm }}>
      <SectionTitle>{title}</SectionTitle>
      {buckets.map((bucket) => {
        const rate = bucket.rate ?? 0;
        // 표본이 적은 줄은 흐리게. 지우지는 않는다 — 없는 것과 "아직 모르는 것"은 다르다.
        const tone = !bucket.enough ? colors.textFaint : rate >= 70 ? colors.success : colors.danger;
        return (
          <View key={bucket.id} style={{ gap: 4 }}>
            <View style={styles.bucketRow}>
              <Text style={[font.small, { color: colors.text, flex: 1 }]} numberOfLines={1}>
                {translate(bucket.id)}
              </Text>
              <Text style={[font.small, { color: tone }]}>
                {bucket.rate === null ? '—' : `${bucket.rate}%`}
              </Text>
              <Text style={[font.tiny, { color: colors.textFaint, width: 64, textAlign: 'right' }]}>
                {bucket.enough
                  ? translate('insights.count', { count: bucket.total })
                  : translate('insights.tooFew', { min: MIN_SAMPLES })}
              </Text>
            </View>
            <View style={[styles.track, { backgroundColor: colors.border }]}>
              <View style={[styles.fill, { width: `${rate}%`, backgroundColor: tone }]} />
            </View>
          </View>
        );
      })}
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  const { colors } = useTheme();
  return (
    <View style={{ flex: 1, gap: 2 }}>
      <Text style={[font.tiny, { color: colors.textFaint }]}>{label}</Text>
      <Text style={[font.h3, { color: colors.text }]}>{value}</Text>
    </View>
  );
}

const makeStyles = (theme: Theme) =>
  StyleSheet.create({
    page: { padding: space.lg, gap: space.md, paddingBottom: space.xl },
    statRow: { flexDirection: 'row', gap: space.md },
    bucketRow: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
    codeRow: { flexDirection: 'row', justifyContent: 'space-between' },
    track: { height: 6, borderRadius: radius.sm, overflow: 'hidden' },
    fill: { height: 6, borderRadius: radius.sm, backgroundColor: theme.colors.primary },
  });
