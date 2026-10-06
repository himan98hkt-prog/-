import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Alert, Image, KeyboardAvoidingView, Linking, Platform, Pressable, ScrollView, Share, StyleSheet, Text, View } from 'react-native';
import { toVCard } from '../../core/mapping';
import { phoneDigits, sanitizeFields } from '../../core/normalize';
import { connectorTargets, CONNECTOR_LABEL } from '../../core/settings';
import { CardFields, CardKind, FIELD_LABEL } from '../../core/types';
import { CardForm } from '../../ui/CardForm';
import { Button, C, KindBadge, KindPicker, Section, SyncDot } from '../../ui/components';
import { useStore } from '../../ui/store';

function localTime(iso: string): string {
  const d = new Date(iso);
  const p = (n: number) => String(n).padStart(2, '0');
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

const SHOW: (keyof CardFields)[] = ['mobile', 'phone', 'fax', 'email', 'website', 'address', 'nameEn', 'memo'];

export default function CardDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { cards, settings, updateCard, deleteCard, resync, syncingIds } = useStore();
  const card = cards.find((c) => c.id === id);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<CardFields | null>(null);
  const [kind, setKind] = useState<CardKind>(card?.kind ?? 'customer');

  if (!card) {
    return (
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
        <Text style={st.sub}>삭제되었거나 없는 명함입니다</Text>
      </View>
    );
  }

  const targets = connectorTargets(settings, card.kind);
  const syncing = syncingIds.has(card.id);

  function startEdit() {
    const { name, nameEn, company, department, title, mobile, phone, fax, email, website, address, memo } = card!;
    setForm({ name, nameEn, company, department, title, mobile, phone, fax, email, website, address, memo });
    setKind(card!.kind);
    setEditing(true);
  }

  async function saveEdit() {
    if (!form) return;
    setEditing(false);
    await updateCard(card!.id, { ...sanitizeFields(form), kind });
  }

  function confirmDelete() {
    Alert.alert('명함 삭제', '앱에서 이 명함을 지웁니다.\n휴대폰 연락처·연동 시스템에 이미 저장된 정보는 그대로 남습니다.', [
      { text: '취소', style: 'cancel' },
      {
        text: '삭제',
        style: 'destructive',
        onPress: async () => {
          await deleteCard(card!.id);
          router.back();
        },
      },
    ]);
  }

  function action(k: keyof CardFields) {
    const v = card![k];
    if (k === 'mobile' || k === 'phone') return Linking.openURL(`tel:${phoneDigits(v)}`);
    if (k === 'email') return Linking.openURL(`mailto:${v}`);
    if (k === 'website') return Linking.openURL(v);
    if (k === 'address') return Linking.openURL(`https://map.naver.com/p/search/${encodeURIComponent(v)}`);
  }

  if (editing && form) {
    return (
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <Stack.Screen options={{ title: '명함 수정' }} />
        <ScrollView style={{ flex: 1, backgroundColor: C.bg }} contentContainerStyle={{ padding: 16 }} keyboardShouldPersistTaps="handled">
          <Section title="구분">
            <KindPicker value={kind} onChange={setKind} />
          </Section>
          <Section title="명함 정보">
            <CardForm value={form} onChange={setForm} />
          </Section>
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <Button title="취소" variant="secondary" style={{ flex: 1 }} onPress={() => setEditing(false)} />
            <Button title="저장 후 다시 연동" style={{ flex: 2 }} onPress={saveEdit} />
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    );
  }

  return (
    <ScrollView style={{ flex: 1, backgroundColor: C.bg }} contentContainerStyle={{ padding: 16 }}>
      <Stack.Screen options={{ title: card.name || '명함 상세' }} />
      {card.imageUri ? <Image source={{ uri: card.imageUri }} style={st.image} resizeMode="contain" /> : null}

      <Section title="" right={<KindBadge kind={card.kind} />}>
        <Text style={st.name}>
          {card.name || card.nameEn} <Text style={st.sub}>{card.title}</Text>
        </Text>
        <Text style={st.company}>{[card.company, card.department].filter(Boolean).join(' · ')}</Text>
        <View style={{ flexDirection: 'row', gap: 8, marginTop: 14 }}>
          {card.mobile ? <Button title="전화" style={{ flex: 1 }} onPress={() => action('mobile')} /> : null}
          {card.mobile ? <Button title="문자" variant="secondary" style={{ flex: 1 }} onPress={() => Linking.openURL(`sms:${phoneDigits(card.mobile)}`)} /> : null}
          {card.email ? <Button title="메일" variant="secondary" style={{ flex: 1 }} onPress={() => action('email')} /> : null}
        </View>
      </Section>

      <Section title="연락처 정보">
        {SHOW.filter((k) => card[k]).map((k) => (
          <Pressable key={k} onPress={() => action(k)} style={st.row}>
            <Text style={st.label}>{FIELD_LABEL[k]}</Text>
            <Text style={st.value} selectable>
              {card[k]}
            </Text>
          </Pressable>
        ))}
        {card.extra.length ? (
          <View style={st.row}>
            <Text style={st.label}>기타</Text>
            <Text style={st.value}>{card.extra.join('\n')}</Text>
          </View>
        ) : null}
      </Section>

      <Section
        title="연동 상태"
        right={
          <Pressable onPress={() => resync(card.id)} disabled={syncing}>
            <Text style={{ color: C.primary, fontWeight: '600' }}>{syncing ? '전송 중…' : '전체 다시 보내기'}</Text>
          </Pressable>
        }
      >
        {targets.length === 0 ? <Text style={st.sub}>켜진 연동이 없습니다. 설정·연동 탭에서 켤 수 있습니다.</Text> : null}
        {targets.map((t) => {
          const sync = card.sync[t];
          return (
            <View key={t} style={st.syncRow}>
              <SyncDot status={sync} />
              <View style={{ flex: 1 }}>
                <Text style={st.value}>{CONNECTOR_LABEL[t].split(' (')[0]}</Text>
                <Text style={[st.sub, sync?.state === 'error' && { color: C.err }]}>
                  {sync ? `${sync.state === 'ok' ? '완료' : '실패'}${sync.message ? ` · ${sync.message}` : ''} · ${localTime(sync.at)}` : '아직 보내지 않음'}
                </Text>
              </View>
              {sync?.state !== 'ok' ? (
                <Pressable onPress={() => resync(card.id, [t])} disabled={syncing}>
                  <Text style={{ color: C.primary, fontWeight: '600' }}>재시도</Text>
                </Pressable>
              ) : null}
            </View>
          );
        })}
      </Section>

      <View style={{ gap: 8 }}>
        <Button title="수정" variant="secondary" onPress={startEdit} />
        <Button title="명함 공유 (vCard)" variant="secondary" onPress={() => Share.share({ message: toVCard(card), title: card.name })} />
        <Button title="삭제" variant="danger" onPress={confirmDelete} />
      </View>
      <Text style={[st.sub, { textAlign: 'center', marginTop: 12 }]}>
        등록 {card.createdAt.slice(0, 10)} · 수정 {card.updatedAt.slice(0, 10)}
      </Text>
    </ScrollView>
  );
}

const st = StyleSheet.create({
  image: { width: '100%', height: 210, borderRadius: 12, backgroundColor: '#000', marginBottom: 12 },
  name: { fontSize: 24, fontWeight: '800', color: C.text },
  company: { fontSize: 16, color: C.text, marginTop: 4 },
  sub: { fontSize: 13, color: C.sub },
  row: { flexDirection: 'row', paddingVertical: 10, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: C.line },
  label: { width: 76, fontSize: 14, color: C.sub },
  value: { flex: 1, fontSize: 15, color: C.text },
  syncRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 8 },
});
