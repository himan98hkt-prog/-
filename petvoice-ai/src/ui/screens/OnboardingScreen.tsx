import React from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { FREE_DAILY_LIMIT } from '../../core/quota';
import { usePetStore } from '../../store/usePetStore';
import { Button, Card } from '../components/Basics';
import { useNavigation } from '../navigation';
import { colors, font, space } from '../theme';

const STEPS = [
  { emoji: '🎙', title: '3초만 들려주세요', desc: '울음소리·짖는 소리를 3초 녹음하면 감정을 읽어 드려요.' },
  { emoji: '📷', title: '자세도 함께 봅니다', desc: '소리 + 행동 + 상황을 같이 보기 때문에 훨씬 정확해요.' },
  { emoji: '💬', title: '포토카드로 자랑하기', desc: '사진 위에 말풍선이 얹힌 카드를 1초 만에 공유해요.' },
  { emoji: '🏥', title: '이상 신호는 짚어 드려요', desc: '분리불안·통증 신호가 보이면 병원 방문을 권해 드립니다.' },
];

/** 첫 실행 안내 → 반려동물 등록으로 이어진다. */
export function OnboardingScreen() {
  const nav = useNavigation();
  const completeOnboarding = usePetStore((s) => s.completeOnboarding);

  const start = () => {
    completeOnboarding();
    nav.navigate('petForm');
  };

  return (
    <ScrollView contentContainerStyle={styles.page}>
      <View style={styles.hero}>
        <Text style={{ fontSize: 56 }}>🐶🐱</Text>
        <Text style={[font.h1, { textAlign: 'center' }]}>우리 아이가 하는 말,{'\n'}이제 알아들어요</Text>
        <Text style={[font.body, { color: colors.textSoft, textAlign: 'center' }]}>
          소리와 행동을 함께 분석하는 멀티모달 통역기
        </Text>
      </View>

      <Card style={{ gap: space.lg }}>
        {STEPS.map((step) => (
          <View key={step.title} style={styles.step}>
            <Text style={{ fontSize: 26 }}>{step.emoji}</Text>
            <View style={{ flex: 1 }}>
              <Text style={font.bodyStrong}>{step.title}</Text>
              <Text style={[font.small, { color: colors.textSoft }]}>{step.desc}</Text>
            </View>
          </View>
        ))}
      </Card>

      <Button label="시작하기" onPress={start} />
      <Text style={[font.tiny, styles.note]}>
        하루 {FREE_DAILY_LIMIT}회까지 무료로 분석할 수 있어요.{'\n'}
        분석 결과는 참고용이며 수의학적 진단이 아닙니다.
      </Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: space.lg, gap: space.xl, paddingBottom: space.xxl, justifyContent: 'center', flexGrow: 1 },
  hero: { alignItems: 'center', gap: space.md },
  step: { flexDirection: 'row', gap: space.md, alignItems: 'flex-start' },
  note: { color: colors.textFaint, textAlign: 'center', lineHeight: 17 },
});
