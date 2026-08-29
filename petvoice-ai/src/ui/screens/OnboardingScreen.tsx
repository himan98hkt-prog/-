import React from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { FREE_DAILY_LIMIT } from '../../core/quota';
import { useT } from '../../i18n/useT';
import { usePetStore } from '../../store/usePetStore';
import { Button, Card } from '../components/Basics';
import { useNavigation } from '../navigation';
import { font, space } from '../theme';
import { useStyles, useTheme, type Theme } from '../useTheme';

const STEPS = [
  { emoji: '🎙', key: 'step1' },
  { emoji: '📷', key: 'step2' },
  { emoji: '💬', key: 'step3' },
  { emoji: '🏥', key: 'step4' },
];

/** 첫 실행 안내 → 반려동물 등록으로 이어진다. */
export function OnboardingScreen() {
  const nav = useNavigation();
  const styles = useStyles(makeStyles);
  const { colors } = useTheme();
  const { t } = useT();
  const completeOnboarding = usePetStore((s) => s.completeOnboarding);

  const start = () => {
    completeOnboarding();
    nav.navigate('petForm');
  };

  return (
    <ScrollView contentContainerStyle={styles.page}>
      <View style={styles.hero}>
        <Text style={{ fontSize: 56 }} accessibilityElementsHidden importantForAccessibility="no">
          🐶🐱
        </Text>
        <Text accessibilityRole="header" style={[font.h1, { color: colors.text, textAlign: 'center' }]}>
          {t('onboarding.title')}
        </Text>
        <Text style={[font.body, { color: colors.textSoft, textAlign: 'center' }]}>
          {t('onboarding.subtitle')}
        </Text>
      </View>

      <Card style={{ gap: space.lg }}>
        {STEPS.map((step) => (
          <View key={step.key} style={styles.step}>
            <Text style={{ fontSize: 26 }} accessibilityElementsHidden importantForAccessibility="no">
              {step.emoji}
            </Text>
            <View style={{ flex: 1 }}>
              <Text style={[font.bodyStrong, { color: colors.text }]}>
                {t(`onboarding.${step.key}.title`)}
              </Text>
              <Text style={[font.small, { color: colors.textSoft }]}>{t(`onboarding.${step.key}.desc`)}</Text>
            </View>
          </View>
        ))}
      </Card>

      <Button label={t('onboarding.cta')} onPress={start} />
      <Text style={[font.tiny, { color: colors.textFaint, textAlign: 'center', lineHeight: 17 }]}>
        {t('onboarding.note', { limit: FREE_DAILY_LIMIT })}
      </Text>
    </ScrollView>
  );
}

const makeStyles = (_theme: Theme) =>
  StyleSheet.create({
    page: {
      padding: space.lg,
      gap: space.xl,
      paddingBottom: space.xxl,
      justifyContent: 'center',
      flexGrow: 1,
    },
    hero: { alignItems: 'center', gap: space.md },
    step: { flexDirection: 'row', gap: space.md, alignItems: 'flex-start' },
  });
