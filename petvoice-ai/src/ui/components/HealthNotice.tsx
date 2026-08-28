import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import type { HealthAssessment } from '../../core/types';
import { useT } from '../../i18n/useT';
import { font, radius, space } from '../theme';
import { useStyles, useTheme, type Theme } from '../useTheme';

/**
 * 이상 징후 안내. "재미로 끝나지 않는다"는 제품의 핵심 차별점이라
 * 결과 화면에서 가장 눈에 띄는 위치에 둔다.
 */
export function HealthNotice({ health }: { health: HealthAssessment }) {
  const styles = useStyles(makeStyles);
  const { colors } = useTheme();
  const { t, m } = useT();

  if (health.level === 'none') return null;
  const vet = health.level === 'vet';

  return (
    <View
      accessibilityRole="alert"
      style={[
        styles.box,
        {
          backgroundColor: vet ? colors.dangerSoft : colors.warnSoft,
          borderColor: vet ? colors.danger : colors.warnLine,
        },
      ]}
    >
      <Text accessibilityRole="header" style={[font.h3, { color: vet ? colors.danger : colors.warnText }]}>
        {t(vet ? 'health.vetTitle' : 'health.watchTitle')}
      </Text>

      {health.reasons.map((reason, index) => (
        <Text key={index} style={[font.small, { color: colors.text }]}>
          · {m(reason)}
        </Text>
      ))}

      {health.tips.length > 0 ? (
        <View style={styles.tips}>
          <Text style={[font.tiny, { color: colors.textSoft, marginBottom: space.xs }]}>{t('health.nowTitle')}</Text>
          {health.tips.map((tip, index) => (
            <Text key={index} style={[font.small, { color: colors.text }]}>
              · {m(tip)}
            </Text>
          ))}
        </View>
      ) : null}

      <Text style={[font.tiny, { color: colors.textFaint, marginTop: space.md }]}>{t('health.disclaimer')}</Text>
    </View>
  );
}

const makeStyles = ({ colors }: Theme) =>
  StyleSheet.create({
    box: { borderRadius: radius.md, borderWidth: 1, padding: space.lg, gap: space.xs },
    tips: { marginTop: space.sm, paddingTop: space.sm, borderTopWidth: 1, borderTopColor: colors.border },
  });
