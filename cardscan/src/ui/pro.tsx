// Pro 평생 이용권 상태 + 결제 화면. 앱 어디서든 requirePro('csv') 처럼 물어보면 된다.
import AsyncStorage from '@react-native-async-storage/async-storage';
import { getLang, t } from '../i18n';
import { LinearGradient } from 'expo-linear-gradient';
import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, Alert, Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { FREE_CARD_LIMIT, isLaunchSale, PRO_BENEFITS, PRO_REASON, ProFeature, regularPriceLabel } from '../core/pro';
import { BILLING_ENABLED, buyPro, checkOwned, loadProduct, ProProduct, watchPurchases } from './billing';
import { Icon, tap } from './components';
import { FONT, RADIUS, T, type } from './theme';

const KEY = 'cardscan:pro:v1';

interface ProState {
  /** Pro 기능을 쓸 수 있는지 (개인용 빌드·웹은 항상 true) */
  isPro: boolean;
  /** 결제가 있는 빌드인지 — false 면 Pro 안내를 숨긴다 */
  billing: boolean;
  /** 결제 대기 중 (편의점 결제 등) */
  pending: boolean;
  product: ProProduct | null;
  /** 허용되면 true, 아니면 결제 화면을 띄우고 false */
  requirePro(feature: ProFeature): boolean;
  openPaywall(): void;
  restore(): Promise<void>;
}

const Ctx = createContext<ProState | null>(null);

export function usePro(): ProState {
  const v = useContext(Ctx);
  if (!v) throw new Error('ProProvider 안에서만 쓸 수 있습니다');
  return v;
}

export function ProProvider({ children }: { children: ReactNode }) {
  const [owned, setOwned] = useState(!BILLING_ENABLED);
  const [pending, setPending] = useState(false);
  const [product, setProduct] = useState<ProProduct | null>(null);
  const [paywall, setPaywall] = useState<ProFeature | 'upgrade' | null>(null);
  const [busy, setBusy] = useState(false);
  const paywallOpen = useRef(false);
  paywallOpen.current = !!paywall;

  const apply = useCallback((s: 'owned' | 'pending' | 'none') => {
    setPending(s === 'pending');
    const isOwned = s === 'owned';
    setOwned(isOwned);
    AsyncStorage.setItem(KEY, isOwned ? '1' : '0').catch(() => {});
    if (isOwned) {
      setBusy(false);
      // 결제 화면에서 막 산 경우에만 축하 (앱 시작 때 확인은 조용히)
      if (paywallOpen.current) {
        tap('success');
        Alert.alert(t('명함스캔 Pro'), t('평생 이용권이 적용되었습니다. 감사합니다!'));
      }
      setPaywall(null);
    }
  }, []);

  useEffect(() => {
    if (!BILLING_ENABLED) return;
    // 저장해 둔 상태로 먼저 열고(오프라인에서도), 스토어에 확인해 바로잡는다 (환불·다른 기기 구매 반영)
    AsyncStorage.getItem(KEY)
      .then((v) => v === '1' && setOwned(true))
      .catch(() => {});
    const stop = watchPurchases(apply, (message) => {
      setBusy(false);
      Alert.alert(t('결제 실패'), message);
    });
    checkOwned().then((s) => s && apply(s));
    loadProduct().then(setProduct);
    return stop;
  }, [apply]);

  const requirePro = useCallback(
    (feature: ProFeature) => {
      if (owned) return true;
      tap('select');
      setPaywall(feature);
      return false;
    },
    [owned],
  );

  const restore = useCallback(async () => {
    setBusy(true);
    const s = await checkOwned();
    setBusy(false);
    if (s) apply(s);
    if (s === 'owned') return;
    Alert.alert(t('구매 복원'), s === 'pending' ? t('결제가 아직 처리 중입니다. 완료되면 자동으로 적용됩니다.') : s === 'none' ? t('이 구글 계정으로 구매한 Pro 이용권을 찾지 못했습니다.') : t('구글 플레이에 연결하지 못했습니다. 잠시 뒤 다시 시도해 주세요.'));
  }, [apply]);

  const value = useMemo<ProState>(
    () => ({ isPro: owned, billing: BILLING_ENABLED, pending, product, requirePro, openPaywall: () => setPaywall('upgrade'), restore }),
    [owned, pending, product, requirePro, restore],
  );

  async function buy() {
    setBusy(true);
    try {
      await buyPro();
    } catch (e) {
      Alert.alert(t('결제'), (e as Error).message);
    } finally {
      // 결제 창이 열리면 결과는 리스너로 온다 — 버튼만 다시 살린다
      setTimeout(() => setBusy(false), 1500);
    }
  }

  return (
    <Ctx.Provider value={value}>
      {children}
      {BILLING_ENABLED ? (
        <Paywall
          visible={!!paywall && !owned}
          reason={paywall && paywall !== 'upgrade' ? t(PRO_REASON[paywall]) : undefined}
          product={product}
          pending={pending}
          busy={busy}
          onBuy={buy}
          onRestore={restore}
          onClose={() => setPaywall(null)}
        />
      ) : null}
    </Ctx.Provider>
  );
}

function Paywall(props: {
  visible: boolean;
  reason?: string;
  product: ProProduct | null;
  pending: boolean;
  busy: boolean;
  onBuy(): void;
  onRestore(): void;
  onClose(): void;
}) {
  const { visible, reason, product, pending, busy, onBuy, onRestore, onClose } = props;
  const insets = useSafeAreaInsets();
  const sale = isLaunchSale(product?.price, product?.currency);
  const price = product?.displayPrice;
  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose} statusBarTranslucent>
      <View style={st.backdrop}>
        <LinearGradient colors={[T.ink3, T.ink]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={[st.sheet, { paddingBottom: 20 + insets.bottom }]}>
          <ScrollView bounces={false} contentContainerStyle={{ padding: 24 }}>
            <Pressable onPress={onClose} hitSlop={14} style={st.close} accessibilityLabel={t('닫기')}>
              <Icon name="close" size={22} color="rgba(255,255,255,0.6)" />
            </Pressable>
            <Text style={st.brand}>CARDSCAN PRO</Text>
            <Text style={st.title}>{t('평생 이용권')}</Text>
            <Text style={st.sub}>{t('구독 없이 한 번만 결제하면 계속 씁니다')}</Text>
            {reason ? (
              <View style={st.reason}>
                <Icon name="information-circle" size={16} color={T.gold} />
                <Text style={st.reasonText}>{reason}</Text>
              </View>
            ) : null}
            <View style={{ gap: 12, marginTop: 20 }}>
              {PRO_BENEFITS.map((b) => (
                <View key={b} style={st.benefit}>
                  <View style={st.check}>
                    <Icon name="checkmark" size={14} color={T.ink} />
                  </View>
                  <Text style={st.benefitText}>{t(b)}</Text>
                </View>
              ))}
            </View>
            <Text style={st.keep}>{t('무료로도 명함 {1}장 저장·연락처 자동 저장·검색·메모·팔로업을 쓸 수 있고, 이미 저장한 명함은 언제나 보고·고치고·백업할 수 있습니다.', { 1: FREE_CARD_LIMIT })}</Text>

            {pending ? (
              <View style={st.pending}>
                <ActivityIndicator color={T.gold} />
                <Text style={st.pendingText}>{t('결제가 처리 중입니다. 완료되면 자동으로 적용됩니다.')}</Text>
              </View>
            ) : (
              <Pressable onPress={onBuy} disabled={busy || !price} style={({ pressed }) => [{ marginTop: 22, opacity: pressed || busy || !price ? 0.7 : 1 }]}>
                <LinearGradient colors={['#F1D9A3', T.gold, T.goldDeep]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={st.buy}>
                  {busy ? (
                    <ActivityIndicator color={T.ink} />
                  ) : (
                    <>
                      {sale ? <Text style={st.saleTag}>{t('출시 기념가 · 정가 {1}', { 1: regularPriceLabel(product?.currency, getLang() === 'ko' ? 'ko-KR' : 'en-US') })}</Text> : null}
                      <Text style={st.buyText}>{price ? t('{1} · 평생 이용', { 1: price }) : t('가격 불러오는 중…')}</Text>
                    </>
                  )}
                </LinearGradient>
              </Pressable>
            )}
            <Pressable onPress={onRestore} hitSlop={8} style={{ alignSelf: 'center', marginTop: 16 }}>
              <Text style={st.restore}>{t('이미 구매했어요 · 구매 복원')}</Text>
            </Pressable>
            <Text style={st.fine}>{t('결제는 구글 플레이로 처리되며 이 구글 계정의 다른 안드로이드 기기에서도 복원할 수 있습니다. 환불은 구글 플레이 정책을 따릅니다.')}</Text>
          </ScrollView>
        </LinearGradient>
      </View>
    </Modal>
  );
}

const st = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(5,10,25,0.6)', justifyContent: 'flex-end' },
  sheet: { borderTopLeftRadius: RADIUS.xl, borderTopRightRadius: RADIUS.xl, maxHeight: '92%', borderTopWidth: 1, borderColor: 'rgba(212,175,106,0.5)' },
  close: { position: 'absolute', right: 0, top: 0, padding: 6, zIndex: 2 },
  brand: { fontFamily: FONT, fontSize: 11, fontWeight: '800', letterSpacing: 3, color: T.gold },
  title: { fontFamily: FONT, fontSize: 30, fontWeight: '800', color: '#fff', letterSpacing: -0.6, marginTop: 4 },
  sub: { ...type(14, '500', 'rgba(255,255,255,0.65)'), marginTop: 4 },
  reason: { flexDirection: 'row', gap: 8, alignItems: 'center', marginTop: 16, padding: 12, borderRadius: RADIUS.md, backgroundColor: 'rgba(212,175,106,0.12)' },
  reasonText: { ...type(14, '700', '#fff'), flex: 1 },
  benefit: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  check: { width: 22, height: 22, borderRadius: 11, backgroundColor: T.gold, alignItems: 'center', justifyContent: 'center' },
  benefitText: { ...type(15, '600', '#fff'), flex: 1 },
  keep: { ...type(12, '500', 'rgba(255,255,255,0.5)'), marginTop: 18 },
  buy: { borderRadius: RADIUS.lg, minHeight: 60, alignItems: 'center', justifyContent: 'center', paddingVertical: 10 },
  saleTag: { ...type(12, '800', T.ink), opacity: 0.75 },
  buyText: { fontFamily: FONT, fontSize: 18, fontWeight: '800', color: T.ink },
  restore: { ...type(14, '700', 'rgba(255,255,255,0.75)'), textDecorationLine: 'underline' },
  fine: { ...type(11, '400', 'rgba(255,255,255,0.4)'), marginTop: 14, textAlign: 'center' },
  pending: { flexDirection: 'row', gap: 10, alignItems: 'center', marginTop: 22, padding: 16, borderRadius: RADIUS.lg, backgroundColor: 'rgba(255,255,255,0.06)' },
  pendingText: { ...type(14, '600', '#fff'), flex: 1 },
});
