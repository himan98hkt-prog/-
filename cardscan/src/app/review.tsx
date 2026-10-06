import { router } from 'expo-router';
import { useState } from 'react';
import { Alert, Image, KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Text } from 'react-native';
import { sanitizeFields } from '../core/normalize';
import { CardFields, CardKind, EMPTY_FIELDS } from '../core/types';
import { CardForm } from '../ui/CardForm';
import { Button, C, KindPicker, Section } from '../ui/components';
import { clearDraft, takeDraft } from '../ui/draft';
import { useStore } from '../ui/store';
import { RADIUS, T, type } from '../ui/theme';

export default function ReviewScreen() {
  const { addCard } = useStore();
  const [draft] = useState(() => takeDraft());
  const [fields, setFields] = useState<CardFields>(draft?.fields ?? { ...EMPTY_FIELDS });
  const [kind, setKind] = useState<CardKind>(draft?.kind ?? 'customer');
  const [saving, setSaving] = useState(false);

  async function save() {
    // 손으로 고친 값도 같은 규칙(전화번호 하이픈, 이메일 소문자 등)으로 정리
    const clean = sanitizeFields(fields);
    if (!clean.name && !clean.company) return Alert.alert('이름이나 회사 중 하나는 입력해 주세요');
    setSaving(true);
    try {
      const { card, merged } = await addCard({ fields: clean, kind, extra: draft?.extra ?? [], tempImageUri: draft?.imageUri, tempBackUri: draft?.backImageUri });
      clearDraft();
      if (merged) Alert.alert('기존 명함 갱신', '휴대폰 번호나 이메일이 같은 명함이 있어 최신 정보로 갱신했습니다.');
      router.replace({ pathname: '/card/[id]', params: { id: card.id } });
    } catch (e) {
      Alert.alert('저장 실패', (e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView style={{ flex: 1, backgroundColor: T.bg }} contentContainerStyle={{ padding: 16 }} keyboardShouldPersistTaps="handled">
        {draft?.imageUri ? <Image source={{ uri: draft.imageUri }} style={st.image} resizeMode="contain" /> : null}
        {draft?.error ? <Text style={st.error}>자동 인식 실패: {draft.error}{'\n'}직접 입력해 주세요.</Text> : null}
        {draft?.note ? <Text style={st.note}>{draft.note}</Text> : null}
        <Section title="구분" icon="pricetag-outline">
          <KindPicker value={kind} onChange={setKind} />
        </Section>
        <Section title="명함 정보" icon="id-card-outline">
          <CardForm value={fields} onChange={setFields} />
        </Section>
        {draft?.extra?.length ? (
          <Section title="기타 문구">
            <Text style={st.note}>{draft.extra.join('\n')}</Text>
          </Section>
        ) : null}
        <Button title="저장하고 연동하기" icon="checkmark-circle" variant="gold" onPress={save} loading={saving} />
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const st = StyleSheet.create({
  image: { width: '100%', height: 200, borderRadius: RADIUS.lg, backgroundColor: T.ink, marginBottom: 12 },
  error: { ...type(14, '600', T.err), marginBottom: 12, backgroundColor: T.errSoft, padding: 12, borderRadius: RADIUS.md },
  note: { ...type(14, '500', T.sub), marginBottom: 8 },
});
