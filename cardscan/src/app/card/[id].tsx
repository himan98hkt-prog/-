import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useMemo, useState } from 'react';
import { Alert, KeyboardAvoidingView, Linking, Modal, Platform, Pressable, ScrollView, Share, StyleSheet, Text, TextInput, View } from 'react-native';
import { toVCard } from '../../core/mapping';
import { phoneDigits, sanitizeFields } from '../../core/normalize';
import { addDays, allTags, colleaguesOf, normalizeTag, todayStr } from '../../core/organize';
import { connectorTargets, CONNECTOR_LABEL } from '../../core/settings';
import { BusinessCard, CardFields, CardKind, FIELD_LABEL } from '../../core/types';
import { CardForm } from '../../ui/CardForm';
import { CardImage } from '../../ui/CardImage';
import { Button, C, Field, KindBadge, KindPicker, Section, SyncDot } from '../../ui/components';
import { QrCode } from '../../ui/QrCode';
import { CAN_OPEN_VCARD, openVCard } from '../../ui/saveContact';
import { useStore } from '../../ui/store';

function localTime(iso: string): string {
  const d = new Date(iso);
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

const SHOW: (keyof CardFields)[] = ['mobile', 'phone', 'fax', 'email', 'website', 'address', 'nameEn', 'memo'];

const FOLLOW_PRESETS: [string, number][] = [
  ['내일', 1],
  ['3일 뒤', 3],
  ['1주 뒤', 7],
  ['2주 뒤', 14],
  ['한 달 뒤', 30],
];

/** 문자·카톡으로 보내기 좋은 명함 요약 */
function shareText(c: BusinessCard): string {
  return [
    [c.name, c.title].filter(Boolean).join(' '),
    [c.company, c.department].filter(Boolean).join(' '),
    c.mobile && `휴대폰 ${c.mobile}`,
    c.phone && `전화 ${c.phone}`,
    c.email && `이메일 ${c.email}`,
    c.address && `주소 ${c.address}`,
  ]
    .filter(Boolean)
    .join('\n');
}

export default function CardDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { cards, settings, updateCard, deleteCard, resync, syncingIds, setMeta, addNote, deleteNote } = useStore();
  const card = cards.find((c) => c.id === id);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<CardFields | null>(null);
  const [kind, setKind] = useState<CardKind>(card?.kind ?? 'customer');
  const [showBack, setShowBack] = useState(false);
  const [noteText, setNoteText] = useState('');
  const [tagText, setTagText] = useState('');
  const [customDate, setCustomDate] = useState('');
  const [qrOpen, setQrOpen] = useState(false);
  const colleagues = useMemo(() => (card ? colleaguesOf(card, cards) : []), [card, cards]);
  const knownTags = useMemo(() => allTags(cards).map((t) => t.tag), [cards]);

  if (!card) {
    return (
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
        <Text style={st.sub}>삭제되었거나 없는 명함입니다</Text>
      </View>
    );
  }

  const targets = connectorTargets(settings, card.kind);
  const syncing = syncingIds.has(card.id);
  const today = todayStr();
  const tags = card.tags ?? [];

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

  function addTag(t: string) {
    const tag = normalizeTag(t);
    if (!tag || tags.includes(tag)) return;
    setMeta(card!.id, { tags: [...tags, tag] });
    setTagText('');
  }

  function setFollow(date: string | undefined) {
    setMeta(card!.id, { followUp: date });
    if (date) addNote(card!.id, `팔로업 예정: ${date}`);
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
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView style={{ flex: 1, backgroundColor: C.bg }} contentContainerStyle={{ padding: 16 }} keyboardShouldPersistTaps="handled">
        <Stack.Screen
          options={{
            title: card.name || '명함 상세',
            headerRight: () => (
              <Pressable hitSlop={12} onPress={() => setMeta(card.id, { favorite: !card.favorite })} accessibilityLabel="즐겨찾기">
                <Text style={{ fontSize: 26, color: card.favorite ? '#F5A524' : '#CBD5E1' }}>{card.favorite ? '★' : '☆'}</Text>
              </Pressable>
            ),
          }}
        />
        {card.imageUri ? (
          <Pressable onPress={() => card.backImageUri && setShowBack((v) => !v)}>
            <CardImage uri={showBack && card.backImageUri ? card.backImageUri : card.imageUri} style={st.image} contain />
            {card.backImageUri ? <Text style={st.flipHint}>{showBack ? '뒷면 · 눌러서 앞면 보기' : '앞면 · 눌러서 뒷면 보기'}</Text> : null}
          </Pressable>
        ) : null}

        <Section title="" right={<KindBadge kind={card.kind} />}>
          <Text style={st.name}>
            {card.name || card.nameEn} <Text style={st.sub}>{card.title}</Text>
          </Text>
          <Text style={st.company}>{[card.company, card.department].filter(Boolean).join(' · ')}</Text>
          <View style={{ flexDirection: 'row', gap: 8, marginTop: 14 }}>
            {card.mobile || card.phone ? <Button title="전화" style={{ flex: 1 }} onPress={() => action(card.mobile ? 'mobile' : 'phone')} /> : null}
            {card.mobile ? <Button title="문자" variant="secondary" style={{ flex: 1 }} onPress={() => Linking.openURL(`sms:${phoneDigits(card.mobile)}`)} /> : null}
            {card.email ? <Button title="메일" variant="secondary" style={{ flex: 1 }} onPress={() => action('email')} /> : null}
            {card.address ? <Button title="지도" variant="secondary" style={{ flex: 1 }} onPress={() => action('address')} /> : null}
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

        <Section title="그룹">
          <View style={st.tagWrap}>
            {tags.map((t) => (
              <Pressable key={t} style={st.tag} onPress={() => setMeta(card.id, { tags: tags.filter((x) => x !== t) })}>
                <Text style={st.tagText}>#{t} ✕</Text>
              </Pressable>
            ))}
            {!tags.length ? <Text style={st.sub}>그룹을 붙이면 명함첩에서 모아 볼 수 있습니다 (예: 2026 전시회, VIP)</Text> : null}
          </View>
          <View style={{ flexDirection: 'row', gap: 8, marginTop: 10 }}>
            <View style={{ flex: 1 }}>
              <Field label="" value={tagText} onChangeText={setTagText} placeholder="새 그룹 이름" onSubmitEditing={() => addTag(tagText)} returnKeyType="done" />
            </View>
            <Button title="추가" variant="secondary" onPress={() => addTag(tagText)} style={{ marginTop: 4, minHeight: 44 }} />
          </View>
          {knownTags.filter((t) => !tags.includes(t)).length ? (
            <View style={st.tagWrap}>
              {knownTags
                .filter((t) => !tags.includes(t))
                .slice(0, 8)
                .map((t) => (
                  <Pressable key={t} style={st.tagGhost} onPress={() => addTag(t)}>
                    <Text style={st.tagGhostText}>+ {t}</Text>
                  </Pressable>
                ))}
            </View>
          ) : null}
        </Section>

        <Section
          title="팔로업 (다시 연락하기)"
          right={card.followUp ? <Pressable onPress={() => setFollow(undefined)}><Text style={{ color: C.err, fontWeight: '600' }}>해제</Text></Pressable> : undefined}
        >
          {card.followUp ? (
            <Text style={[st.followNow, card.followUp <= today && { color: C.err }]}>
              📞 {card.followUp}
              {card.followUp < today ? ' (지남)' : card.followUp === today ? ' (오늘)' : ''}
              {settings.followUpNotify ? '  · 그날 아침 9시 알림' : ''}
            </Text>
          ) : (
            <Text style={st.sub}>언제 다시 연락할지 정해 두면 그날 알림을 보내고 명함첩 맨 위에 보여 줍니다.</Text>
          )}
          <View style={st.tagWrap}>
            {FOLLOW_PRESETS.map(([label, days]) => (
              <Pressable key={label} style={st.tagGhost} onPress={() => setFollow(addDays(today, days))}>
                <Text style={st.tagGhostText}>{label}</Text>
              </Pressable>
            ))}
          </View>
          <View style={{ flexDirection: 'row', gap: 8, marginTop: 8 }}>
            <View style={{ flex: 1 }}>
              <Field label="" value={customDate} onChangeText={setCustomDate} placeholder="날짜 직접 (예: 2026-11-20)" keyboardType="numbers-and-punctuation" />
            </View>
            <Button
              title="지정"
              variant="secondary"
              style={{ marginTop: 4, minHeight: 44 }}
              onPress={() => {
                if (!/^\d{4}-\d{2}-\d{2}$/.test(customDate.trim())) return Alert.alert('날짜 형식', '2026-11-20 처럼 입력해 주세요');
                setFollow(customDate.trim());
                setCustomDate('');
              }}
            />
          </View>
        </Section>

        <Section title="메모·미팅 기록">
          <TextInput
            value={noteText}
            onChangeText={setNoteText}
            placeholder="예: 견적 요청 받음, 다음 주 미팅 / 골프 좋아함"
            placeholderTextColor="#9CA3AF"
            multiline
            style={st.noteInput}
          />
          <Button
            title="기록 추가"
            variant="secondary"
            disabled={!noteText.trim()}
            style={{ marginTop: 8 }}
            onPress={() => {
              addNote(card.id, noteText);
              setNoteText('');
            }}
          />
          {(card.notes ?? []).map((n) => (
            <Pressable
              key={n.id}
              style={st.noteRow}
              onLongPress={() =>
                Alert.alert('기록 삭제', n.text, [
                  { text: '취소', style: 'cancel' },
                  { text: '삭제', style: 'destructive', onPress: () => deleteNote(card.id, n.id) },
                ])
              }
            >
              <Text style={st.noteAt}>{localTime(n.at)}</Text>
              <Text style={st.value}>{n.text}</Text>
            </Pressable>
          ))}
          {(card.notes ?? []).length ? <Text style={[st.sub, { marginTop: 6 }]}>기록을 길게 누르면 지울 수 있습니다</Text> : null}
        </Section>

        {(card.history ?? []).length ? (
          <Section title="경력 이력">
            <View style={st.careerRow}>
              <Text style={st.careerDot}>●</Text>
              <Text style={st.value}>
                {[card.company, card.department, card.title].filter(Boolean).join(' · ')} <Text style={st.sub}>(현재)</Text>
              </Text>
            </View>
            {card.history!.map((h, i) => (
              <View key={i} style={st.careerRow}>
                <Text style={[st.careerDot, { color: C.sub }]}>○</Text>
                <Text style={[st.value, { color: C.sub }]}>
                  {[h.company, h.department, h.title].filter(Boolean).join(' · ')} <Text style={st.sub}>(~{h.until.slice(0, 10)})</Text>
                </Text>
              </View>
            ))}
          </Section>
        ) : null}

        {colleagues.length ? (
          <Section title={`같은 회사 사람 ${colleagues.length}명`}>
            {colleagues.slice(0, 10).map((c) => (
              <Pressable key={c.id} style={st.row} onPress={() => router.push({ pathname: '/card/[id]', params: { id: c.id } })}>
                <Text style={st.value}>
                  {c.name} <Text style={st.sub}>{[c.department, c.title].filter(Boolean).join(' ')}</Text>
                </Text>
              </Pressable>
            ))}
          </Section>
        ) : null}

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
          {CAN_OPEN_VCARD ? <Button title="📇 아이폰 연락처에 저장" onPress={() => openVCard(card)} /> : null}
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <Button title="QR 로 전달" variant="secondary" style={{ flex: 1 }} onPress={() => setQrOpen(true)} />
            <Button title="문자·카톡 공유" variant="secondary" style={{ flex: 1 }} onPress={() => Share.share({ message: shareText(card), title: card.name })} />
          </View>
          <Button title="vCard 공유" variant="secondary" onPress={() => Share.share({ message: toVCard(card), title: card.name })} />
          <Button title="삭제" variant="danger" onPress={confirmDelete} />
        </View>
        <Text style={[st.sub, { textAlign: 'center', marginTop: 12 }]}>
          등록 {card.createdAt.slice(0, 10)} · 수정 {card.updatedAt.slice(0, 10)}
        </Text>

        <Modal visible={qrOpen} transparent animationType="fade" onRequestClose={() => setQrOpen(false)}>
          <Pressable style={st.modalBg} onPress={() => setQrOpen(false)}>
            <View style={st.modalBox}>
              <Text style={st.modalTitle}>{card.name} 명함</Text>
              <QrCode value={toVCard(card)} size={260} />
              <Text style={[st.sub, { textAlign: 'center', marginTop: 12 }]}>상대방 휴대폰 카메라로 찍으면{'\n'}연락처에 바로 저장할 수 있습니다</Text>
            </View>
          </Pressable>
        </Modal>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const st = StyleSheet.create({
  image: { width: '100%', height: 210, borderRadius: 12, backgroundColor: '#000', marginBottom: 4 },
  flipHint: { textAlign: 'center', fontSize: 12, color: C.sub, marginBottom: 10 },
  name: { fontSize: 24, fontWeight: '800', color: C.text },
  company: { fontSize: 16, color: C.text, marginTop: 4 },
  sub: { fontSize: 13, color: C.sub, lineHeight: 19 },
  row: { flexDirection: 'row', paddingVertical: 10, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: C.line },
  label: { width: 76, fontSize: 14, color: C.sub },
  value: { flex: 1, fontSize: 15, color: C.text },
  syncRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 8 },
  tagWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 6 },
  tag: { backgroundColor: '#EEF2FF', borderRadius: 14, paddingHorizontal: 10, paddingVertical: 6 },
  tagText: { color: '#4338CA', fontWeight: '600', fontSize: 13 },
  tagGhost: { borderWidth: 1, borderColor: C.line, borderRadius: 14, paddingHorizontal: 10, paddingVertical: 6, backgroundColor: '#fff' },
  tagGhostText: { color: C.text, fontSize: 13 },
  followNow: { fontSize: 17, fontWeight: '700', color: C.primary, marginBottom: 4 },
  noteInput: { backgroundColor: '#fff', borderWidth: 1, borderColor: C.line, borderRadius: 10, padding: 12, minHeight: 64, fontSize: 15, color: C.text, textAlignVertical: 'top' },
  noteRow: { paddingVertical: 10, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: C.line },
  noteAt: { fontSize: 12, color: C.sub, marginBottom: 2 },
  careerRow: { flexDirection: 'row', gap: 8, paddingVertical: 6 },
  careerDot: { color: C.primary, fontSize: 12, marginTop: 3 },
  modalBg: { flex: 1, backgroundColor: 'rgba(0,0,0,0.55)', alignItems: 'center', justifyContent: 'center' },
  modalBox: { backgroundColor: '#fff', borderRadius: 18, padding: 22, alignItems: 'center' },
  modalTitle: { fontSize: 18, fontWeight: '700', color: C.text, marginBottom: 14 },
});
