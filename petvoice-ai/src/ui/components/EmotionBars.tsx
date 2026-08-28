import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { sortedEmotions } from '../../core/analysis';
import { emotionMeta } from '../../core/emotions';
import type { EmotionScores } from '../../core/types';
import { colors, font, radius, space } from '../theme';

/** 감정 3종 확률 막대. 결과 화면과 히스토리 상세가 함께 쓴다. */
export function EmotionBars({ scores }: { scores: EmotionScores }) {
  const ranked = sortedEmotions(scores);
  return (
    <View style={{ gap: space.md }}>
      {ranked.map(({ key, score }) => {
        const meta = emotionMeta(key);
        return (
          <View key={key} accessibilityLabel={`${meta.label} ${score}퍼센트`}>
            <View style={styles.row}>
              <Text style={font.bodyStrong}>
                {meta.emoji} {meta.label}
              </Text>
              <Text style={[font.bodyStrong, { color: meta.color }]}>{score}%</Text>
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

const styles = StyleSheet.create({
  row: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: space.xs },
  track: { height: 10, borderRadius: radius.pill, backgroundColor: colors.surfaceAlt, overflow: 'hidden' },
  fill: { height: '100%', borderRadius: radius.pill },
});
