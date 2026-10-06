// 내 명함 — QR 로 보여 주면 상대가 카메라로 찍어 바로 연락처에 저장, 문자·카톡으로도 보낸다.
import { useEffect, useState } from 'react';
import { Alert, KeyboardAvoidingView, Platform, ScrollView, Share, StyleSheet, Text, View } from 'react-native';
import { toVCard } from '../core/mapping';
import { sanitizeFields } from '../core/normalize';
import { BusinessCard, CardFields } from '../core/types';
import { CardForm } from '../ui/CardForm';
import { Button, C, Section } from '../ui/components';
import { QrCode } from '../ui/QrCode';
import { useStore } from '../ui/store';

const asCard = (f: CardFields): BusinessCard => ({ ...f, id: 'me', kind: 'other', createdAt: '', updatedAt: '', extra: [], sync: {} });

export default function MyCardScreen() {
  const { settings, setSettings } = useStore();
  const [form, setForm] = useState<CardFields>(settings.myCard);
  // 설정은 비동기로 불러오므로 "이름이 없으면 입력 화면" 은 렌더할 때마다 판단한다
  const [editRequested, setEditing] = useState(false);
  useEffect(() => setForm(settings.myCard), [settings.myCard]);
  const me = settings.myCard;
  const editing = editRequested || !me.name;

  async function save() {
    const clean = sanitizeFields(form);
    if (!clean.name) return Alert.alert('이름을 입력해 주세요');
    await setSettings({ ...settings, myCard: clean });
    setEditing(false);
  }

  if (editing) {
    return (
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView style={{ flex: 1, backgroundColor: C.bg }} contentContainerStyle={{ padding: 16 }} keyboardShouldPersistTaps="handled">
          <Section title="내 명함 정보">
            <Text style={st.sub}>상대에게 보여 줄 내 정보를 입력하세요. 이 휴대폰에만 저장됩니다.</Text>
            <View style={{ height: 10 }} />
            <CardForm value={form} onChange={setForm} />
          </Section>
          <Button title="저장" onPress={save} />
        </ScrollView>
      </KeyboardAvoidingView>
    );
  }

  const vcard = toVCard(asCard(me));
  return (
    <ScrollView style={{ flex: 1, backgroundColor: C.bg }} contentContainerStyle={{ padding: 16, alignItems: 'stretch' }}>
      <View style={st.card}>
        <Text style={st.name}>
          {me.name} <Text style={st.title}>{me.title}</Text>
        </Text>
        <Text style={st.company}>{[me.company, me.department].filter(Boolean).join(' · ')}</Text>
        <View style={{ alignItems: 'center', marginVertical: 18 }}>
          <QrCode value={vcard} size={240} />
        </View>
        <Text style={[st.sub, { textAlign: 'center' }]}>상대방 휴대폰 카메라로 이 QR 을 찍으면{'\n'}내 연락처가 바로 저장됩니다</Text>
        <View style={{ marginTop: 14, gap: 4 }}>
          {[me.mobile, me.phone, me.email, me.address].filter(Boolean).map((v) => (
            <Text key={v} style={st.line}>{v}</Text>
          ))}
        </View>
      </View>
      <View style={{ gap: 8, marginTop: 14 }}>
        <Button
          title="문자·카톡으로 내 명함 보내기"
          onPress={() =>
            Share.share({
              message: [
                [me.name, me.title].filter(Boolean).join(' '),
                [me.company, me.department].filter(Boolean).join(' '),
                me.mobile && `휴대폰 ${me.mobile}`,
                me.phone && `전화 ${me.phone}`,
                me.email && `이메일 ${me.email}`,
                me.website,
                me.address,
              ]
                .filter(Boolean)
                .join('\n'),
            })
          }
        />
        <Button title="vCard 로 보내기" variant="secondary" onPress={() => Share.share({ message: vcard, title: me.name })} />
        <Button title="내 정보 수정" variant="secondary" onPress={() => setEditing(true)} />
      </View>
    </ScrollView>
  );
}

const st = StyleSheet.create({
  card: { backgroundColor: '#fff', borderRadius: 18, padding: 20 },
  name: { fontSize: 24, fontWeight: '800', color: C.text },
  title: { fontSize: 15, fontWeight: '400', color: C.sub },
  company: { fontSize: 16, color: C.text, marginTop: 4 },
  sub: { fontSize: 13, color: C.sub, lineHeight: 19 },
  line: { fontSize: 15, color: C.text, textAlign: 'center' },
});
