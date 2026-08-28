import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { sortedEmotions } from '../../core/analysis';
import { emotionMeta } from '../../core/emotions';
import type { EmotionScores } from '../../core/types';
import { useT } from '../../i18n/useT';
import { font, radius, space } from '../theme';
import { useStyles, useTheme, type Theme } from '../useTheme';

/** 감정 3종 확률 막대. 결과 화면과 히스토리 상세가 함께 쓴다. */
export function EmotionBars({ scores }: { scores: EmotionScores }) {
  const styles = useStyles(makeStyles);
  const { colors } = useTheme();
  const { t } = useT();
  const ranked = sortedEmotions(scores);

  return (
    <View style={{ gap: space.md }}>
      {ranked.map(({ key, score }) => {
        const meta = emotionMeta(key);
        const label = t(meta.labelKey);
        return (
          <View key={key} accessible accessibilityLabel={`${label} ${score}%`}>
            <View style={styles.row}>
              <Text style={[font.bodyStrong, { color: colors.text }]}>
                {meta.emoji} {label}
              </Text>
              <Text style={[font.bodyStrong, { color: colors.text }]}>{score}%</Text>
            </View>
            <View style={styles.track}>
              <View style={[styles.fill, { width: `${Math.max(2, score)}%`, backgroundColor: meta.color }]} />
            </View>
          </View>
        );
      })}
    </View>
  );
}

const makeStyles = ({ colors }: Theme) =>
  StyleSheet.create({
    row: { flexDirection: 'row', justifyContent: 'space-between', gap: space.sm, marginBottom: space.xs },
    track: { height: 10, borderRadius: radius.pill, backgroundColor: colors.surfaceAlt, overflow: 'hidden' },
    fill: { height: '100%', borderRadius: radius.pill },
  });
