import React, { useState } from 'react';
import { Alert, Linking, ScrollView, StyleSheet, Text, View } from 'react-native';
import { PRO_FEATURES, PRO_PRICE_KRW } from '../../core/quota';
import { usePetStore, useIsPro } from '../../store/usePetStore';
import { Button, Card } from '../components/Basics';
import { LINKS } from '../links';
import { useNavigation } from '../navigation';
import { colors, font, radius, space } from '../theme';

/**
 * 프로 구독 안내.
 *
 * 결제는 스토어 인앱 결제(Google Play Billing / StoreKit)로 붙여야 한다.
 * 지금은 결제 모듈이 없는 상태라 "구독 처리" 자리를 명확히 비워 두고,
 * 개발 빌드에서만 상태를 전환할 수 있게 한다. (`__DEV__`)
 */
export function PaywallScreen() {
  const nav = useNavigation();
  const isPro = useIsPro();
  const setSubscription = usePetStore((s) => s.setSubscription);
  const [busy, setBusy] = useState(false);

  const subscribe = async () => {
    setBusy(true);
    try {
      // TODO(결제): react-native-iap 또는 expo-in-app-purchases 로 교체.
      //   1) 상품 조회 → 2) 구매 요청 → 3) 영수증을 Edge Function 으로 검증
      //   4) 검증 성공 시에만 setSubscription({ pro: true, expiresAt })
      if (__DEV__) {
        setSubscription({ pro: true, expiresAt: Date.now() + 30 * 24 * 60 * 60 * 1000 });
        Alert.alert('개발 모드', '프로 상태로 전환했어요. (실제 결제 아님)');
        nav.back();
        return;
      }
      Alert.alert('준비 중이에요', '스토어 결제 연동 후 이용할 수 있습니다.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScrollView contentContainerStyle={styles.page}>
      <View style={styles.hero}>
        <Text style={{ fontSize: 46 }}>🐾</Text>
        <Text style={[font.h1, { textAlign: 'center' }]}>PetVoice 프로</Text>
        <Text style={[font.body, { color: colors.textSoft, textAlign: 'center' }]}>
          하루 3회 제한 없이, 우리 아이 이야기를 마음껏 들어 보세요.
        </Text>
      </View>

      <Card style={{ gap: space.lg }}>
        {PRO_FEATURES.map((feature) => (
          <View key={feature.key} style={styles.feature}>
            <Text style={styles.check}>✓</Text>
            <View style={{ flex: 1 }}>
              <Text style={font.bodyStrong}>{feature.title}</Text>
              <Text style={[font.small, { color: colors.textSoft }]}>{feature.desc}</Text>
            </View>
          </View>
        ))}
      </Card>

      <Card style={styles.price}>
        <Text style={font.h2}>월 {PRO_PRICE_KRW.toLocaleString('ko-KR')}원</Text>
        <Text style={[font.small, { color: colors.textSoft }]}>언제든 스토어에서 해지할 수 있어요.</Text>
      </Card>

      {isPro ? (
        <Card style={{ alignItems: 'center', gap: space.sm }}>
          <Text style={font.h3}>이미 프로 이용 중이에요 🎉</Text>
          <Button label="돌아가기" variant="ghost" onPress={nav.back} style={{ alignSelf: 'stretch' }} />
        </Card>
      ) : (
        <>
          <Button label="프로 시작하기" variant="pro" loading={busy} onPress={() => void subscribe()} />
          <Button label="나중에 할게요" variant="ghost" onPress={nav.back} />
        </>
      )}

      <Text style={[font.tiny, styles.legal]}>
        구독은 매월 자동 갱신되며, 해지하지 않으면 다음 결제일에 갱신됩니다.{'\n'}
        결제·환불은 각 스토어 정책을 따릅니다.
      </Text>
      <View style={styles.legalLinks}>
        <Text style={[font.tiny, styles.link]} onPress={() => void Linking.openURL(LINKS.terms)}>
          이용약관
        </Text>
        <Text style={[font.tiny, styles.link]} onPress={() => void Linking.openURL(LINKS.privacy)}>
          개인정보처리방침
        </Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: space.lg, gap: space.lg, paddingBottom: space.xxl },
  hero: { alignItems: 'center', gap: space.sm, paddingTop: space.lg },
  feature: { flexDirection: 'row', gap: space.md, alignItems: 'flex-start' },
  check: { color: colors.pro, fontSize: 18, fontWeight: '800' },
  price: { alignItems: 'center', gap: space.xs, backgroundColor: colors.proSoft, borderColor: colors.proSoft, borderRadius: radius.lg },
  legal: { color: colors.textFaint, textAlign: 'center', lineHeight: 17 },
  legalLinks: { flexDirection: 'row', justifyContent: 'center', gap: space.lg },
  link: { color: colors.textSoft, textDecorationLine: 'underline' },
});
