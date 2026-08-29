import React, { useEffect, useMemo, useState } from 'react';
import { Alert, Linking, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useBilling } from '../../billing/useBilling';
import { PRO_MONTHLY_SKU, PRO_YEARLY_SKU, savingsPercent, type TrialPeriod } from '../../core/billing';
import { FREE_DAILY_LIMIT, PRO_PRICE_KRW, PRO_YEARLY_PRICE_KRW, PRO_FEATURES } from '../../core/quota';
import { useT, type Translator } from '../../i18n/useT';
import { usePetStore, useIsPro } from '../../store/usePetStore';
import { Button, Card } from '../components/Basics';
import { LINKS } from '../links';
import { useNavigation } from '../navigation';
import { font, radius, space } from '../theme';
import { useStyles, useTheme, type Theme } from '../useTheme';

/** 체험 기간을 사람이 읽는 문구로 (1주는 파싱 단계에서 7일로 환산돼 있다) */
function trialLabel(trial: TrialPeriod | null, tr: Translator): string | null {
  if (!trial) return null;
  const key = { day: 'duration.days', month: 'duration.months', year: 'duration.years' }[trial.unit];
  return tr.t(key, { count: trial.count });
}

/**
 * 프로 구독 안내 + 결제.
 *
 * 결제 자체는 스토어가, 검증은 서버가 한다. 이 화면은 상태를 보여 주고 방아쇠만 당긴다.
 */
export function PaywallScreen() {
  const nav = useNavigation();
  const styles = useStyles(makeStyles);
  const { colors } = useTheme();
  const tr = useT();
  const { t } = tr;
  const isPro = useIsPro();
  const setSubscription = usePetStore((s) => s.setSubscription);
  const billing = useBilling();

  const [selectedSku, setSelectedSku] = useState<string>(PRO_YEARLY_SKU);

  const monthly = billing.products.find((p) => p.productId === PRO_MONTHLY_SKU);
  const yearly = billing.products.find((p) => p.productId === PRO_YEARLY_SKU);
  const selected = billing.products.find((p) => p.productId === selectedSku);
  const trial = trialLabel(selected?.freeTrial ?? null, tr);

  const savings = useMemo(() => {
    if (monthly?.priceMicros && yearly?.priceMicros)
      return savingsPercent(monthly.priceMicros, yearly.priceMicros);
    return savingsPercent(PRO_PRICE_KRW * 1_000_000, PRO_YEARLY_PRICE_KRW * 1_000_000);
  }, [monthly?.priceMicros, yearly?.priceMicros]);

  useEffect(() => {
    if (!billing.notice) return;
    Alert.alert(t('paywall.subscriptionTitle'), tr.m(billing.notice), [
      { text: t('common.confirm'), onPress: billing.clearNotice },
    ]);
  }, [billing.notice, billing.clearNotice, t, tr]);

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

  const priceOf = (sku: string) => {
    const product = billing.products.find((p) => p.productId === sku);
    if (product?.localizedPrice) return product.localizedPrice;
    const fallback = sku === PRO_YEARLY_SKU ? PRO_YEARLY_PRICE_KRW : PRO_PRICE_KRW;
    return `${fallback.toLocaleString(tr.locale)}${tr.locale === 'en' ? ' KRW' : '원'}`;
  };

  return (
    <ScrollView contentContainerStyle={styles.page}>
      <View style={styles.hero}>
        <Text style={{ fontSize: 46 }} accessibilityElementsHidden importantForAccessibility="no">
          🐾
        </Text>
        <Text accessibilityRole="header" style={[font.h1, { color: colors.text, textAlign: 'center' }]}>
          {t('paywall.title')}
        </Text>
        <Text style={[font.body, { color: colors.textSoft, textAlign: 'center' }]}>
          {t('paywall.subtitle', { limit: FREE_DAILY_LIMIT })}
        </Text>
      </View>

      <Card style={{ gap: space.lg }}>
        {PRO_FEATURES.map((feature) => (
          <View key={feature} style={styles.feature}>
            <Text style={[styles.check, { color: colors.proText }]}>✓</Text>
            <View style={{ flex: 1 }}>
              <Text style={[font.bodyStrong, { color: colors.text }]}>
                {t(`paywall.feature.${feature}.title`)}
              </Text>
              <Text style={[font.small, { color: colors.textSoft }]}>
                {t(`paywall.feature.${feature}.desc`, { limit: FREE_DAILY_LIMIT })}
              </Text>
            </View>
          </View>
        ))}
      </Card>

      {!isPro ? (
        <View style={{ gap: space.sm }}>
          <PlanOption
            selected={selectedSku === PRO_YEARLY_SKU}
            onPress={() => setSelectedSku(PRO_YEARLY_SKU)}
            title={t('paywall.planYearly')}
            price={t('paywall.perYear', { price: priceOf(PRO_YEARLY_SKU) })}
            note={savings ? t('paywall.saveBadge', { percent: savings }) : undefined}
          />
          <PlanOption
            selected={selectedSku === PRO_MONTHLY_SKU}
            onPress={() => setSelectedSku(PRO_MONTHLY_SKU)}
            title={t('paywall.planMonthly')}
            price={t('paywall.perMonth', { price: priceOf(PRO_MONTHLY_SKU) })}
          />
          <Text style={[font.tiny, { color: colors.textFaint, textAlign: 'center' }]}>
            {t('paywall.cancelAnytime')}
          </Text>
        </View>
      ) : null}

      {isPro ? (
        <Card style={{ alignItems: 'center', gap: space.sm }}>
          <Text accessibilityRole="header" style={[font.h3, { color: colors.text }]}>
            {t('paywall.alreadyPro')}
          </Text>
          <Button
            label={t('settings.manageSub')}
            variant="ghost"
            onPress={() => void billing.openManage()}
            style={{ alignSelf: 'stretch' }}
          />
          <Button
            label={t('result.goBack')}
            variant="ghost"
            onPress={nav.back}
            style={{ alignSelf: 'stretch' }}
          />
        </Card>
      ) : (
        <>
          <Button
            label={
              billing.loading
                ? t('paywall.checking')
                : trial
                  ? t('paywall.startTrial', { period: trial })
                  : t('paywall.start')
            }
            variant="pro"
            loading={billing.busy || billing.loading}
            disabled={!billing.available}
            onPress={() => void billing.buy(selectedSku)}
          />
          <Button
            label={t('paywall.restore')}
            variant="ghost"
            disabled={!billing.available}
            onPress={() => void billing.restore()}
          />

          {!billing.available ? (
            <Card style={{ backgroundColor: colors.warnSoft, borderColor: colors.warnLine, gap: space.xs }}>
              <Text style={[font.bodyStrong, { color: colors.text }]}>{t('paywall.unavailableTitle')}</Text>
              <Text style={[font.small, { color: colors.textSoft }]}>{t('paywall.unavailableDesc')}</Text>
              {__DEV__ ? (
                <Button
                  label={t('paywall.devUnlock')}
                  variant="ghost"
                  onPress={devUnlock}
                  style={{ marginTop: space.sm }}
                />
              ) : null}
            </Card>
          ) : null}

          <Button label={t('paywall.later')} variant="ghost" onPress={nav.back} />
        </>
      )}

      <Text style={[font.tiny, { color: colors.textFaint, textAlign: 'center', lineHeight: 17 }]}>
        {t('paywall.legal')}
      </Text>
      <View style={styles.legalLinks}>
        <Text
          accessibilityRole="link"
          style={[font.tiny, styles.link, { color: colors.textSoft }]}
          onPress={() => void Linking.openURL(LINKS.terms)}
        >
          {t('settings.terms')}
        </Text>
        <Text
          accessibilityRole="link"
          style={[font.tiny, styles.link, { color: colors.textSoft }]}
          onPress={() => void Linking.openURL(LINKS.privacy)}
        >
          {t('settings.privacyPolicy')}
        </Text>
      </View>
    </ScrollView>
  );
}

function PlanOption({
  selected,
  onPress,
  title,
  price,
  note,
}: {
  selected: boolean;
  onPress: () => void;
  title: string;
  price: string;
  note?: string;
}) {
  const styles = useStyles(makeStyles);
  const { colors } = useTheme();
  return (
    <Pressable
      accessibilityRole="radio"
      accessibilityState={{ selected, checked: selected }}
      accessibilityLabel={`${title} ${price}${note ? ` ${note}` : ''}`}
      onPress={onPress}
      style={[styles.plan, selected && { borderColor: colors.pro, backgroundColor: colors.proSoft }]}
    >
      <View style={{ flex: 1 }}>
        <Text style={[font.bodyStrong, { color: colors.text }]}>{title}</Text>
        <Text style={[font.small, { color: colors.textSoft }]}>{price}</Text>
      </View>
      {note ? (
        <View style={[styles.saveTag, { backgroundColor: colors.pro }]}>
          <Text style={[font.tiny, { color: colors.onPro }]}>{note}</Text>
        </View>
      ) : null}
    </Pressable>
  );
}

const makeStyles = ({ colors }: Theme) =>
  StyleSheet.create({
    page: { padding: space.lg, gap: space.lg, paddingBottom: space.xxl },
    hero: { alignItems: 'center', gap: space.sm, paddingTop: space.lg },
    feature: { flexDirection: 'row', gap: space.md, alignItems: 'flex-start' },
    check: { fontSize: 18, fontWeight: '800' },
    plan: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: space.md,
      borderWidth: 2,
      borderColor: colors.border,
      borderRadius: radius.md,
      backgroundColor: colors.surface,
      padding: space.lg,
    },
    saveTag: { paddingHorizontal: space.md, paddingVertical: 4, borderRadius: radius.pill },
    legalLinks: { flexDirection: 'row', justifyContent: 'center', gap: space.lg },
    link: { textDecorationLine: 'underline' },
  });
