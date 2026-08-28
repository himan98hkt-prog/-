import React, { useEffect } from 'react';
import { Alert, Linking, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useBilling } from '../../billing/useBilling';
import { PRO_FEATURES, PRO_PRICE_KRW } from '../../core/quota';
import { usePetStore, useIsPro } from '../../store/usePetStore';
import { Button, Card } from '../components/Basics';
import { LINKS } from '../links';
import { useNavigation } from '../navigation';
import { colors, font, radius, space } from '../theme';

/**
 * 프로 구독 안내 + 결제.
 *
 * 결제 자체는 스토어가, 검증은 서버가 한다. 이 화면은 상태를 보여 주고 방아쇠만 당긴다.
 * 스토어 결제를 쓸 수 없는 환경(Expo Go·웹·데모 모드)에서는 그 사실을 숨기지 않고 알린다.
 */
export function PaywallScreen() {
  const nav = useNavigation();
  const isPro = useIsPro();
  const setSubscription = usePetStore((s) => s.setSubscription);
  const billing = useBilling();

  const product = billing.products[0];
  const priceLabel = product?.localizedPrice || `${PRO_PRICE_KRW.toLocaleString('ko-KR')}원`;

  useEffect(() => {
    if (!billing.notice) return;
    Alert.alert('구독', billing.notice, [{ text: '확인', onPress: billing.clearNotice }]);
  }, [billing.notice, billing.clearNotice]);

  /** 개발 빌드에서 결제 없이 프로 화면을 확인하기 위한 우회로. 릴리스에는 없다. */
  const devUnlock = () => {
    setSubscription({
      pro: true,
      expiresAt: Date.now() + 30 * 24 * 60 * 60 * 1000,
      store: 'dev',
      state: 'active',
      autoRenewing: true,
      verifiedAt: Date.now(),
    });
    nav.back();
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
        {product?.freeTrial ? (
          <Text style={[font.tiny, { color: colors.pro }]}>{product.freeTrial} 무료 체험</Text>
        ) : null}
        <Text style={font.h2}>월 {priceLabel}</Text>
        <Text style={[font.small, { color: colors.textSoft }]}>언제든 스토어에서 해지할 수 있어요.</Text>
      </Card>

      {isPro ? (
        <Card style={{ alignItems: 'center', gap: space.sm }}>
          <Text style={font.h3}>이미 프로 이용 중이에요 🎉</Text>
          <Button
            label="구독 관리 (해지·결제수단)"
            variant="ghost"
            onPress={() => void billing.openManage()}
            style={{ alignSelf: 'stretch' }}
          />
          <Button label="돌아가기" variant="ghost" onPress={nav.back} style={{ alignSelf: 'stretch' }} />
        </Card>
      ) : (
        <>
          <Button
            label={billing.loading ? '스토어 확인 중…' : product?.freeTrial ? `${product.freeTrial} 무료로 시작하기` : '프로 시작하기'}
            variant="pro"
            loading={billing.busy || billing.loading}
            disabled={!billing.available}
            onPress={() => void billing.buy()}
          />
          <Button label="구매 복원" variant="ghost" disabled={!billing.available} onPress={() => void billing.restore()} />

          {!billing.available ? (
            <Card style={{ backgroundColor: colors.warnSoft, borderColor: colors.warn, gap: space.xs }}>
              <Text style={font.bodyStrong}>이 환경에서는 결제를 할 수 없어요</Text>
              <Text style={[font.small, { color: colors.textSoft }]}>
                스토어 결제는 EAS 개발 빌드 또는 스토어에서 내려받은 앱에서만 동작합니다.
                {'\n'}(Expo Go·웹 미리보기에는 결제 네이티브 모듈이 없습니다.)
              </Text>
              {__DEV__ ? (
                <Button label="개발용: 프로 상태로 전환" variant="ghost" onPress={devUnlock} style={{ marginTop: space.sm }} />
              ) : null}
            </Card>
          ) : null}

          <Button label="나중에 할게요" variant="ghost" onPress={nav.back} />
        </>
      )}

      <Text style={[font.tiny, styles.legal]}>
        구독은 매월 자동 갱신되며, 해지하지 않으면 다음 결제일에 갱신됩니다.{'\n'}
        해지는 구독 만료 24시간 전까지 스토어의 구독 관리에서 할 수 있습니다.{'\n'}
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
