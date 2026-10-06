import Constants from 'expo-constants';
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Alert, KeyboardAvoidingView, Linking, Platform, Pressable, ScrollView, StyleSheet, Switch, Text, View } from 'react-native';
import { CONNECTOR_LABEL, CONNECTOR_ORDER, connectorReady, Settings } from '../../core/settings';
import { BusinessCard, CardKind, ConnectorId, KIND_LABEL } from '../../core/types';
import { checkOcr } from '../../integrations/ocr';
import { HTTP_CONNECTORS } from '../../integrations/sync';
import { Button, C, Field, Icon, KindPicker, Section } from '../../ui/components';
import { IS_WEB, WEB_LIMITS } from '../../ui/platform';
import { CAN_OPEN_VCARD, exportAllVCards } from '../../ui/saveContact';
import { pickBackup, shareBackup, shareCsv } from '../../ui/dataFiles';
import { PRIVACY_URL, SUPPORT_URL } from '../../ui/constants';
import { usePro } from '../../ui/pro';
import { FREE_CARD_LIMIT, isLaunchSale, isProConnector, PRO_REGULAR_PRICE_KRW } from '../../core/pro';
import { LinearGradient } from 'expo-linear-gradient';
import { useStore } from '../../ui/store';
import { RADIUS, T, type } from '../../ui/theme';

const SAMPLE: BusinessCard = {
  id: 'test-0000',
  kind: 'customer',
  name: '홍길동',
  nameEn: 'Gildong Hong',
  company: '명함스캔 테스트',
  department: '영업팀',
  title: '팀장',
  mobile: '010-0000-0000',
  phone: '02-000-0000',
  fax: '',
  email: 'test@example.com',
  website: 'https://example.com',
  address: '서울특별시 중구 세종대로 110',
  memo: '연동 테스트 데이터입니다 — 확인 후 삭제하세요',
  extra: [],
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
  sync: {},
};

const HELP: Record<ConnectorId, string> = {
  contacts: '찍은 명함을 휴대폰 기본 연락처 앱에 저장합니다. 같은 이름·휴대폰 번호가 있으면 새로 만들지 않고 합칩니다.',
  sheets: '구글 시트에 한 줄씩 기록합니다. 시트에 docs/google-sheets.gs 를 붙여 웹 앱으로 배포하고 그 주소를 넣으세요.',
  hubspot: 'HubSpot 비공개 앱(Private App) 토큰 — crm.objects.contacts.write 권한 필요. 같은 이메일이면 기존 연락처를 갱신합니다.',
  webhook: '사내 ERP·그룹웨어·Zapier·Make·n8n 등 JSON 을 받을 수 있는 주소로 명함을 보냅니다 (형식: docs/INTEGRATIONS.md).',
  slack: '새 명함이 등록되면 슬랙 채널에 알립니다 (Incoming Webhook 주소).',
};

export default function SettingsScreen() {
  const { settings, setSettings, cards, restoreCards } = useStore();
  const { isPro, billing, product, requirePro, openPaywall, restore: restorePurchase } = usePro();
  const [draft, setDraft] = useState<Settings>(settings);
  const [testing, setTesting] = useState<string | null>(null);
  useEffect(() => setDraft(settings), [settings]);
  const dirty = JSON.stringify(draft) !== JSON.stringify(settings);

  const conn = <K extends ConnectorId>(id: K, patch: Partial<Settings['connectors'][K]>) =>
    setDraft((d) => ({ ...d, connectors: { ...d.connectors, [id]: { ...d.connectors[id], ...patch } } }));

  function toggleKind(id: ConnectorId, k: CardKind) {
    const kinds = draft.connectors[id].kinds;
    conn(id, { kinds: kinds.includes(k) ? kinds.filter((x) => x !== k) : [...kinds, k] });
  }

  async function run(task: () => Promise<void>) {
    try {
      await task();
    } catch (e) {
      Alert.alert('실패', (e as Error).message);
    }
  }

  async function restore() {
    try {
      const incoming = await pickBackup();
      if (!incoming) return;
      Alert.alert('백업 복원', `백업의 명함 ${incoming.length}장을 지금 명함첩과 합칩니다.`, [
        { text: '취소', style: 'cancel' },
        {
          text: '복원',
          onPress: () => {
            const { added, updated } = restoreCards(incoming);
            Alert.alert('복원 완료', `새로 추가 ${added}장 · 최신으로 갱신 ${updated}장`);
          },
        },
      ]);
    } catch (e) {
      Alert.alert('복원 실패', (e as Error).message);
    }
  }

  async function save() {
    await setSettings(draft);
    Alert.alert('저장됨', '설정을 저장했습니다. 실패했던 연동은 앱을 다시 열 때 자동으로 재전송됩니다.');
  }

  async function testConnector(id: Exclude<ConnectorId, 'contacts'>) {
    if (!connectorReady(draft, id)) return Alert.alert('설정 확인', '주소/토큰을 올바르게 입력하고 사용을 켜 주세요.');
    setTesting(id);
    try {
      const r = await HTTP_CONNECTORS[id](SAMPLE, { settings: draft, fetch });
      Alert.alert('연결 성공', `${CONNECTOR_LABEL[id]}에 테스트 명함(홍길동)을 보냈습니다.${r.message ? `\n${r.message}` : ''}`);
    } catch (e) {
      Alert.alert('연결 실패', (e as Error).message);
    } finally {
      setTesting(null);
    }
  }

  async function testOcr() {
    setTesting('ocr');
    try {
      await checkOcr(draft);
      Alert.alert('연결 성공', draft.ocr.mode === 'direct' ? 'API 키가 확인되었습니다. 이제 명함을 찍어 보세요.' : '명함 인식 서버가 응답했습니다.');
    } catch (e) {
      Alert.alert('연결 실패', (e as Error).message);
    } finally {
      setTesting(null);
    }
  }

  const ocr = (patch: Partial<Settings['ocr']>) => setDraft((d) => ({ ...d, ocr: { ...d.ocr, ...patch } }));

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView style={{ flex: 1, backgroundColor: T.bg }} contentContainerStyle={{ padding: 16, paddingBottom: 40 }} keyboardShouldPersistTaps="handled">
        {billing ? (
          isPro ? (
            <LinearGradient colors={[T.ink3, T.ink]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={st.proCard}>
              <Icon name="ribbon" size={22} color={T.gold} />
              <View style={{ flex: 1 }}>
                <Text style={st.proTitle}>Pro 평생 이용권 사용 중</Text>
                <Text style={st.proSub}>모든 기능이 열려 있습니다. 감사합니다!</Text>
              </View>
            </LinearGradient>
          ) : (
            <Pressable onPress={openPaywall}>
              <LinearGradient colors={[T.ink3, T.ink]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={st.proCard}>
                <View style={{ flex: 1 }}>
                  <Text style={st.proBrand}>CARDSCAN PRO</Text>
                  <Text style={st.proTitle}>평생 이용권{product ? ` ${product.displayPrice}` : ''}</Text>
                  <Text style={st.proSub}>
                    {isLaunchSale(product?.price, product?.currency) ? `출시 기념가 (정가 ${PRO_REGULAR_PRICE_KRW.toLocaleString('ko-KR')}원) · ` : ''}명함 무제한 · 시트·CRM 연동 · 엑셀
                  </Text>
                  <View style={st.meter}>
                    <View style={[st.meterFill, { width: `${Math.min(100, Math.round((cards.length / FREE_CARD_LIMIT) * 100))}%` }]} />
                  </View>
                  <Text style={st.proSub}>무료 사용량 {Math.min(cards.length, FREE_CARD_LIMIT)}/{FREE_CARD_LIMIT}장</Text>
                </View>
                <Icon name="chevron-forward" size={20} color={T.gold} />
              </LinearGradient>
            </Pressable>
          )
        ) : null}
        {billing && !isPro ? (
          <Pressable onPress={restorePurchase} hitSlop={8} style={{ alignSelf: 'flex-end', marginTop: -6, marginBottom: 12 }}>
            <Text style={st.restoreLink}>구매 복원</Text>
          </Pressable>
        ) : null}

        <Section title="명함 인식" icon="scan-outline">
          <View style={[st.segment, { marginBottom: 10 }]}>
            {(['device', 'direct', 'server'] as const).map((m) => (
              <Pressable key={m} onPress={() => ocr({ mode: m })} style={[st.segItem, draft.ocr.mode === m && st.segOn]}>
                <Text style={[st.segText, draft.ocr.mode === m && { color: '#fff' }]}>{m === 'device' ? '무료' : m === 'direct' ? 'Claude' : '내 서버'}</Text>
              </Pressable>
            ))}
          </View>
          {draft.ocr.mode === 'device' ? (
            <Text style={st.help}>
              {IS_WEB
                ? '이 아이폰 안에서 글자를 읽어 이름·회사·연락처를 나눕니다 (Tesseract). 요금이 들지 않고 사진이 밖으로 나가지 않습니다. 처음 한 번 인식 엔진(약 10MB)을 내려받습니다.'
                : '휴대폰 안에서 글자를 읽어 이름·회사·연락처를 나눕니다 (Google ML Kit). 요금이 들지 않고 인터넷 없이도 동작하며, 사진이 밖으로 나가지 않습니다.'}
              인식이 틀린 칸은 저장 후 상세 화면의 "수정"으로 고치면 연락처·연동에도 다시 반영됩니다.
            </Text>
          ) : draft.ocr.mode === 'direct' ? (
            <>
              <Text style={st.help}>
                (선택·유료) 흐리거나 디자인이 복잡한 명함을 더 정확히 읽습니다. 장당 약 30~50원의 Anthropic API 요금이 들고, 사진이 Anthropic 으로 전송됩니다. 키가 없으면 무료 인식으로 동작합니다.
              </Text>
              <Field label="Anthropic API 키" value={draft.ocr.apiKey} onChangeText={(t) => ocr({ apiKey: t.trim() })} placeholder="sk-ant-..." autoCapitalize="none" autoCorrect={false} secureTextEntry />
            </>
          ) : (
            <>
              <Text style={st.help}>(선택·유료) Claude 인식을 내 서버(supabase/functions/scan-card) 경유로 씁니다 — 직원 여럿이 키 공유 없이 쓸 때. 설정이 비어 있으면 무료 인식으로 동작합니다.</Text>
              <Field label="서버 주소" value={draft.ocr.endpoint} onChangeText={(t) => ocr({ endpoint: t.trim() })} placeholder="https://xxxx.supabase.co/functions/v1/scan-card" autoCapitalize="none" keyboardType="url" />
              <Field label="앱 비밀키 (서버의 APP_SHARED_SECRET)" value={draft.ocr.appSecret} onChangeText={(t) => ocr({ appSecret: t.trim() })} autoCapitalize="none" secureTextEntry />
              <Field label="Supabase anon/publishable key (선택)" value={draft.ocr.anonKey} onChangeText={(t) => ocr({ anonKey: t.trim() })} autoCapitalize="none" secureTextEntry />
            </>
          )}
          {draft.ocr.mode !== 'device' ? (
            <Button title="연결 확인" variant="secondary" onPress={testOcr} loading={testing === 'ocr'} disabled={draft.ocr.mode === 'direct' ? !draft.ocr.apiKey : !draft.ocr.endpoint} />
          ) : null}
        </Section>

        <Section title="내 명함" icon="id-card-outline">
          <Text style={st.help}>내 명함을 QR 로 보여 주면 상대가 카메라로 찍어 바로 연락처에 저장합니다.</Text>
          <Button title={settings.myCard.name ? `내 명함 (${settings.myCard.name})` : '내 명함 만들기'} icon="qr-code" variant="gold" onPress={() => router.push('/mycard')} />
        </Section>

        <Section title="촬영" icon="camera-outline">
          <View style={st.switchRow}>
            <View style={{ flex: 1 }}>
              <Text style={st.label}>자동 저장</Text>
              <Text style={st.help}>이름과 연락처가 읽히면 확인 화면 없이 바로 저장·연동</Text>
            </View>
            <Switch value={draft.autoSave} onValueChange={(v) => setDraft({ ...draft, autoSave: v })} />
          </View>
          <Text style={[st.label, { marginTop: 12, marginBottom: 6 }]}>기본 구분</Text>
          <KindPicker value={draft.defaultKind} onChange={(k) => setDraft({ ...draft, defaultKind: k })} />
        </Section>

        {!IS_WEB ? (
          <Section title="전화 올 때 회사명 보기" icon="call-outline">
            <Text style={st.help}>
              휴대폰 연락처에 저장할 이름 모양입니다. 회사·직책을 붙여 두면 전화가 올 때 기본 전화 앱에 "홍길동 (한빛상사 팀장)" 처럼 보입니다. (이 앱이 새로 만들거나 갱신하는 연락처에 적용)
            </Text>
            <View style={st.segment}>
              {(
                [
                  ['name', '이름만'],
                  ['company', '이름+회사'],
                  ['companyTitle', '이름+회사+직책'],
                ] as const
              ).map(([v, label]) => (
                <Pressable key={v} onPress={() => setDraft({ ...draft, contactName: v })} style={[st.segItem, draft.contactName === v && st.segOn]}>
                  <Text style={[st.segText, { fontSize: 13 }, draft.contactName === v && { color: '#fff' }]}>{label}</Text>
                </Pressable>
              ))}
            </View>
          </Section>
        ) : null}

        <Section title="팔로업 알림" icon="alarm-outline">
          <View style={st.switchRow}>
            <View style={{ flex: 1 }}>
              <Text style={st.label}>연락할 날 아침 9시에 알림</Text>
              <Text style={st.help}>명함 상세에서 "3일 뒤·1주 뒤" 처럼 다시 연락할 날을 정하면 알려 드립니다.</Text>
            </View>
            <Switch value={draft.followUpNotify} onValueChange={(v) => setDraft({ ...draft, followUpNotify: v })} />
          </View>
        </Section>

        {CONNECTOR_ORDER.map((id) => {
          const c = draft.connectors[id];
          return (
            <Section
              key={id}
              title={CONNECTOR_LABEL[id]}
              right={
                WEB_LIMITS[id] ? undefined : (
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                    {billing && !isPro && isProConnector(id) ? <Text style={st.proBadge}>PRO</Text> : null}
                    <Switch
                      value={c.enabled}
                      onValueChange={(v) => {
                        if (v && isProConnector(id) && !requirePro('connectors')) return;
                        conn(id, { enabled: v });
                      }}
                    />
                  </View>
                )
              }
            >
              <Text style={st.help}>{WEB_LIMITS[id] ?? HELP[id]}</Text>
              {c.enabled && !WEB_LIMITS[id] ? (
                <>
                  <Text style={[st.label, { marginTop: 10, marginBottom: 6 }]}>보낼 명함</Text>
                  <View style={{ flexDirection: 'row', gap: 6, marginBottom: 10 }}>
                    {(Object.keys(KIND_LABEL) as CardKind[]).map((k) => {
                      const on = c.kinds.includes(k);
                      return (
                        <Pressable key={k} onPress={() => toggleKind(id, k)} style={[st.chip, on && { backgroundColor: C.kind[k], borderColor: C.kind[k] }]}>
                          <Text style={[st.chipText, on && { color: '#fff' }]}>{on ? '✓ ' : ''}{KIND_LABEL[k]}</Text>
                        </Pressable>
                      );
                    })}
                  </View>
                  {id === 'webhook' ? (
                    <>
                      <Field label="웹훅 주소 (https)" value={draft.connectors.webhook.url} onChangeText={(t) => conn('webhook', { url: t.trim() })} autoCapitalize="none" keyboardType="url" />
                      <Field label="X-CardScan-Secret 헤더 값 (선택)" value={draft.connectors.webhook.secret} onChangeText={(t) => conn('webhook', { secret: t.trim() })} autoCapitalize="none" secureTextEntry />
                    </>
                  ) : null}
                  {id === 'sheets' ? (
                    <>
                      <Field label="Apps Script 웹 앱 주소" value={draft.connectors.sheets.url} onChangeText={(t) => conn('sheets', { url: t.trim() })} placeholder="https://script.google.com/macros/s/…/exec" autoCapitalize="none" keyboardType="url" />
                      <Field label="공유 비밀키 (스크립트의 SECRET 과 같게)" value={draft.connectors.sheets.secret} onChangeText={(t) => conn('sheets', { secret: t.trim() })} autoCapitalize="none" secureTextEntry />
                    </>
                  ) : null}
                  {id === 'hubspot' ? (
                    <Field label="Private App 액세스 토큰" value={draft.connectors.hubspot.token} onChangeText={(t) => conn('hubspot', { token: t.trim() })} placeholder="pat-na1-…" autoCapitalize="none" secureTextEntry />
                  ) : null}
                  {id === 'slack' ? (
                    <Field label="Incoming Webhook 주소" value={draft.connectors.slack.url} onChangeText={(t) => conn('slack', { url: t.trim() })} placeholder="https://hooks.slack.com/services/…" autoCapitalize="none" secureTextEntry />
                  ) : null}
                  {id !== 'contacts' ? (
                    <Button title="테스트 전송" variant="secondary" onPress={() => testConnector(id)} loading={testing === id} />
                  ) : null}
                </>
              ) : null}
            </Section>
          );
        })}

        {!IS_WEB ? (
          <Section title="데이터 내보내기·백업" icon="cloud-download-outline">
            <Text style={st.help}>{billing && !isPro ? '백업 파일은 언제나 무료입니다. 엑셀(CSV) 내보내기는 Pro 기능입니다.' : '카톡·메일·드라이브 등 원하는 곳으로 바로 보낼 수 있습니다.'}</Text>
            <View style={{ gap: 8 }}>
              <Button title={`엑셀(CSV)로 내보내기 (${cards.length}명)`} icon="grid-outline" variant="secondary" disabled={!cards.length} onPress={() => requirePro('csv') && run(() => shareCsv(cards))} />
              <Button title="백업 파일 만들기" icon="save-outline" variant="secondary" disabled={!cards.length} onPress={() => run(() => shareBackup(cards))} />
              <Button title="백업에서 복원" icon="folder-open-outline" variant="secondary" onPress={restore} />
            </View>
            <Text style={[st.help, { marginTop: 8 }]}>백업에는 명함 정보·그룹·메모·팔로업·경력 이력이 들어가고 사진은 빠집니다. 같은 명함은 더 최근 것으로 합쳐집니다.</Text>
          </Section>
        ) : null}

        {CAN_OPEN_VCARD && cards.length ? (
          <Section title="아이폰 연락처로 한꺼번에 옮기기" icon="phone-portrait-outline">
            <Text style={st.help}>저장된 명함 {cards.length}장을 연락처 파일 하나로 엽니다 → "연락처 {cards.length}개 모두 추가".</Text>
            <Button title="전체 명함을 연락처로" icon="people-outline" variant="secondary" onPress={() => exportAllVCards(cards)} />
          </Section>
        ) : null}
        <Button title={dirty ? '설정 저장' : '저장됨'} icon={dirty ? 'save' : 'checkmark'} variant="dark" onPress={save} disabled={!dirty} />
        <Text style={[st.help, { textAlign: 'center', marginTop: 10 }]}>토큰·비밀키는 기기의 보안 저장소(Keychain/Keystore)에 보관됩니다.</Text>

        <Section title="앱 정보" icon="information-circle-outline">
          <Text style={st.help}>
            명함 사진과 정보는 이 휴대폰 안에만 저장됩니다. 직접 켠 연동(구글 시트·HubSpot·웹훅·슬랙)과 선택 기능인 Claude 인식만 해당 서비스로 보냅니다.
          </Text>
          <View style={{ flexDirection: 'row', gap: 10 }}>
            <Button title="개인정보처리방침" icon="shield-checkmark-outline" variant="secondary" style={{ flex: 1 }} onPress={() => Linking.openURL(PRIVACY_URL)} />
            <Button title="문의하기" icon="chatbubbles-outline" variant="secondary" style={{ flex: 1 }} onPress={() => Linking.openURL(SUPPORT_URL)} />
          </View>
          <Text style={[st.help, { textAlign: 'center', marginTop: 10, marginBottom: 0 }]}>명함스캔 v{Constants.expoConfig?.version ?? ''}</Text>
        </Section>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const st = StyleSheet.create({
  segment: { flexDirection: 'row', backgroundColor: '#ECEEF4', borderRadius: RADIUS.md, padding: 4, gap: 4 },
  segItem: { flex: 1, paddingVertical: 10, borderRadius: 11, alignItems: 'center' },
  segOn: { backgroundColor: T.ink },
  segText: { ...type(15, '700'), lineHeight: 20 },
  help: { ...type(13, '400', T.sub), marginBottom: 8 },
  label: { ...type(15, '700'), lineHeight: 21 },
  switchRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  chip: { paddingHorizontal: 12, paddingVertical: 7, borderRadius: 16, borderWidth: 1, borderColor: T.line, backgroundColor: '#fff' },
  proCard: { flexDirection: 'row', alignItems: 'center', gap: 12, borderRadius: RADIUS.lg, padding: 18, marginBottom: 14, borderWidth: 1, borderColor: 'rgba(212,175,106,0.45)' },
  proBrand: { ...type(10, '800', T.gold), letterSpacing: 3 },
  proTitle: { ...type(17, '800', '#fff'), marginTop: 2 },
  proSub: { ...type(12, '600', 'rgba(255,255,255,0.65)'), marginTop: 3 },
  meter: { height: 6, borderRadius: 3, backgroundColor: 'rgba(255,255,255,0.12)', marginTop: 10, overflow: 'hidden' },
  meterFill: { height: 6, borderRadius: 3, backgroundColor: T.gold },
  restoreLink: { ...type(12, '700', T.sub), textDecorationLine: 'underline' },
  proBadge: { ...type(10, '800', T.ink), backgroundColor: T.gold, borderRadius: 6, paddingHorizontal: 6, overflow: 'hidden', letterSpacing: 1 },
  chipText: { ...type(13, '600'), lineHeight: 17 },
});
