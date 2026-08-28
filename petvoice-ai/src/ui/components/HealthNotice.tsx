import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import type { HealthAssessment } from '../../core/types';
import { colors, font, radius, space } from '../theme';

/**
 * 이상 징후 안내. "재미로 끝나지 않는다"는 제품의 핵심 차별점이라
 * 결과 화면에서 가장 눈에 띄는 위치에 둔다.
 */
export function HealthNotice({ health }: { health: HealthAssessment }) {
  if (health.level === 'none') return null;

  const vet = health.level === 'vet';
  return (
    <View
      accessibilityRole="alert"
      style={[styles.box, { backgroundColor: vet ? colors.dangerSoft : colors.warnSoft, borderColor: vet ? colors.danger : colors.warn }]}
    >
      <Text style={[font.h3, { color: vet ? colors.danger : '#8A6D00' }]}>
        {vet ? '🏥 동물병원 확인이 필요해요' : '👀 며칠 지켜봐 주세요'}
      </Text>

      {health.reasons.map((reason) => (
        <Text key={reason} style={[font.small, styles.line]}>
          · {reason}
        </Text>
      ))}

      {health.tips.length > 0 ? (
        <View style={styles.tips}>
          <Text style={[font.tiny, { color: colors.textSoft, marginBottom: space.xs }]}>지금 할 수 있는 것</Text>
          {health.tips.map((tip) => (
            <Text key={tip} style={[font.small, styles.line]}>
              · {tip}
            </Text>
          ))}
        </View>
      ) : null}

      <Text style={[font.tiny, { color: colors.textFaint, marginTop: space.md }]}>
        본 분석은 참고용이며 수의학적 진단이 아닙니다.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  box: { borderRadius: radius.md, borderWidth: 1, padding: space.lg, gap: space.xs },
  line: { color: colors.text },
  tips: { marginTop: space.sm, paddingTop: space.sm, borderTopWidth: 1, borderTopColor: 'rgba(0,0,0,0.06)' },
});
