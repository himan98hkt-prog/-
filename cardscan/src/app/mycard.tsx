// 내 명함 — QR 로 보여 주면 상대가 카메라로 찍어 바로 연락처에 저장, 문자·카톡으로도 보낸다.
import { useEffect, useState } from 'react';
import { t } from '../i18n';
import { Alert, KeyboardAvoidingView, Platform, ScrollView, Share, StyleSheet, Text, View } from 'react-native';
import { toVCard } from '../core/mapping';
import { sanitizeFields } from '../core/normalize';
import { BusinessCard, CardFields } from '../core/types';
import { CardForm } from '../ui/CardForm';
import { Button, Section } from '../ui/components';
import { DigitalCard } from '../ui/DigitalCard';
import { QrCode } from '../ui/QrCode';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useStore } from '../ui/store';
import { FONT, RADIUS, shadow, T, type } from '../ui/theme';

const asCard = (f: CardFields): BusinessCard => ({ ...f, id: 'me', kind: 'other', createdAt: '', updatedAt: '', extra: [], sync: {} });

export default function MyCardScreen() {
  const bottom = useSafeAreaInsets().bottom;
  const { settings, setSettings } = useStore();
  const [form, setForm] = useState<CardFields>(settings.myCard);
  // 설정은 비동기로 불러오므로 "이름이 없으면 입력 화면" 은 렌더할 때마다 판단한다
  const [editRequested, setEditing] = useState(false);
  useEffect(() => setForm(settings.myCard), [settings.myCard]);
  const me = settings.myCard;
  const editing = editRequested || !me.name;

  async function save() {
    const clean = sanitizeFields(form);
    if (!clean.name) return Alert.alert(t('이름을 입력해 주세요'));
    await setSettings({ ...settings, myCard: clean });
    setEditing(false);
  }

  if (editing) {
    return (
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView style={{ flex: 1, backgroundColor: T.bg }} contentContainerStyle={{ padding: 16, paddingBottom: 32 + bottom }} keyboardShouldPersistTaps="handled">
          <Section title={t('내 명함 정보')}>
            <Text style={[st.sub, { textAlign: 'left' }]}>{t('상대에게 보여 줄 내 정보를 입력하세요. 이 휴대폰에만 저장됩니다.')}</Text>
            <View style={{ height: 10 }} />
            <CardForm value={form} onChange={setForm} />
          </Section>
          <Button title={t('저장')} icon="checkmark" variant="gold" onPress={save} />
        </ScrollView>
      </KeyboardAvoidingView>
    );
  }

  const vcard = toVCard(asCard(me));
  const shareMessage = [
    [me.name, me.title].filter(Boolean).join(' '),
    [me.company, me.department].filter(Boolean).join(' '),
    me.mobile && t('휴대폰 {1}', { 1: me.mobile }),
    me.phone && t('전화 {1}', { 1: me.phone }),
    me.email && t('이메일 {1}', { 1: me.email }),
    me.website,
    me.address,
  ]
    .filter(Boolean)
    .join('\n');
  return (
    <ScrollView style={{ flex: 1, backgroundColor: T.bg }} contentContainerStyle={{ padding: 16, paddingBottom: 32 + bottom }}>
      <DigitalCard card={me} favorite />
      <View style={st.qrBox}>
        <Text style={st.brand}>CARDSCAN · MY CARD</Text>
        <View style={st.qrFrame}>
          <QrCode value={vcard} size={220} />
        </View>
        <Text style={st.sub}>{t('상대방 휴대폰 카메라로 이 QR 을 찍으면\n내 연락처가 바로 저장됩니다')}</Text>
      </View>
      <View style={{ gap: 10, marginTop: 14 }}>
        <Button title={t('문자·카톡으로 내 명함 보내기')} icon="paper-plane" variant="gold" onPress={() => Share.share({ message: shareMessage })} />
        <View style={{ flexDirection: 'row', gap: 10 }}>
          <Button title="vCard" icon="document-attach-outline" variant="secondary" style={{ flex: 1 }} onPress={() => Share.share({ message: vcard, title: me.name })} />
          <Button title={t('수정')} icon="create-outline" variant="dark" style={{ flex: 1 }} onPress={() => setEditing(true)} />
        </View>
      </View>
    </ScrollView>
  );
}

const st = StyleSheet.create({
  sub: { ...type(13, '500', T.sub), textAlign: 'center' },
  brand: { fontFamily: FONT, fontSize: 10, fontWeight: '800', letterSpacing: 3, color: T.goldDeep },
  qrBox: { marginTop: 18, backgroundColor: T.surface, borderRadius: RADIUS.xl, padding: 22, alignItems: 'center', ...shadow(1) },
  qrFrame: { marginVertical: 16, padding: 12, borderRadius: RADIUS.lg, borderWidth: 2, borderColor: T.goldSoft },
});
