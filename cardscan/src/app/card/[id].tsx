import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useMemo, useState } from 'react';
import { Alert, KeyboardAvoidingView, Linking, Modal, Platform, Pressable, ScrollView, Share, StyleSheet, Text, TextInput, View } from 'react-native';
import { toVCard } from '../../core/mapping';
import { phoneDigits, sanitizeFields } from '../../core/normalize';
import { addDays, allTags, colleaguesOf, normalizeTag, todayStr } from '../../core/organize';
import { connectorTargets, CONNECTOR_LABEL } from '../../core/settings';
import { BusinessCard, CardFields, CardKind, FIELD_LABEL } from '../../core/types';
import { CardForm } from '../../ui/CardForm';
import { ActionButton, Avatar, Button, C, Field, Icon, IconName, KindBadge, KindPicker, Section, SyncDot, tap } from '../../ui/components';
import { DigitalCard } from '../../ui/DigitalCard';
import { QrCode } from '../../ui/QrCode';
import { CAN_OPEN_VCARD, openVCard } from '../../ui/saveContact';
import { useStore } from '../../ui/store';
import { FONT, RADIUS, T, type } from '../../ui/theme';

function localTime(iso: string): string {
  const d = new Date(iso);
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

const FIELD_ICON: Partial<Record<keyof CardFields, IconName>> = {
  mobile: 'phone-portrait-outline',
  phone: 'call-outline',
  fax: 'print-outline',
  email: 'mail-outline',
  website: 'globe-outline',
  address: 'location-outline',
  nameEn: 'text-outline',
  memo: 'document-text-outline',
};

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
              <Pressable
                hitSlop={12}
                onPress={() => {
                  tap('select');
                  setMeta(card.id, { favorite: !card.favorite });
                }}
                accessibilityLabel="VIP 즐겨찾기"
              >
                <Icon name={card.favorite ? 'star' : 'star-outline'} size={24} color={card.favorite ? T.gold : T.faint} />
              </Pressable>
            ),
          }}
        />
        <DigitalCard
          card={card}
          imageUri={card.imageUri}
          backImageUri={card.backImageUri}
          favorite={card.favorite}
          caption={card.imageUri ? '카드를 누르면 원본 명함 사진으로 뒤집힙니다' : undefined}
        />
        <View style={st.metaRow}>
          <KindBadge kind={card.kind} />
          {tags.slice(0, 3).map((t) => (
            <Text key={t} style={st.metaTag}>#{t}</Text>
          ))}
          <View style={{ flex: 1 }} />
          <Text style={st.metaDate}>{card.createdAt.slice(0, 10)} 등록</Text>
        </View>
        <View style={st.actions}>
          {card.mobile || card.phone ? <ActionButton icon="call" label="전화" tone={T.ok} onPress={() => action(card.mobile ? 'mobile' : 'phone')} /> : null}
          {card.mobile ? <ActionButton icon="chatbubble-ellipses" label="문자" onPress={() => Linking.openURL(`sms:${phoneDigits(card.mobile)}`)} /> : null}
          {card.email ? <ActionButton icon="mail" label="메일" tone={T.kind.partner} onPress={() => action('email')} /> : null}
          {card.address ? <ActionButton icon="navigate" label="지도" tone={T.warn} onPress={() => action('address')} /> : null}
          <ActionButton icon="qr-code" label="QR" tone={T.ink} onPress={() => setQrOpen(true)} />
          <ActionButton icon="share-social" label="공유" tone={T.goldDeep} onPress={() => Share.share({ message: shareText(card), title: card.name })} />
        </View>

        <Section title="연락처 정보" icon="id-card-outline">
          {SHOW.filter((k) => card[k]).map((k) => (
            <Pressable key={k} onPress={() => action(k)} style={st.row}>
              <View style={st.rowIcon}>
                <Icon name={FIELD_ICON[k] ?? 'ellipse-outline'} size={16} color={T.goldDeep} />
              </View>
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

        <Section title="그룹" icon="pricetags-outline">
          <View style={st.tagWrap}>
            {tags.map((t) => (
              <Pressable key={t} style={st.tag} onPress={() => setMeta(card.id, { tags: tags.filter((x) => x !== t) })}>
                <Text style={st.tagText}>#{t}</Text>
                <Icon name="close" size={13} color={T.primary} />
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
          icon="alarm-outline"
          right={card.followUp ? <Pressable onPress={() => setFollow(undefined)}><Text style={{ ...type(14, '700', C.err) }}>해제</Text></Pressable> : undefined}
        >
          {card.followUp ? (
            <Text style={[st.followNow, card.followUp <= today && { color: C.err }]}>
              {card.followUp}
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

        <Section title="메모·미팅 기록" icon="chatbox-ellipses-outline">
          <TextInput
            value={noteText}
            onChangeText={setNoteText}
            placeholder="예: 견적 요청 받음, 다음 주 미팅 / 골프 좋아함"
            placeholderTextColor={T.faint}
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
          <Section title="경력 이력" icon="trending-up-outline">
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
          <Section title={`같은 회사 사람 ${colleagues.length}명`} icon="people-outline">
            {colleagues.slice(0, 10).map((c) => (
              <Pressable key={c.id} style={[st.row, { alignItems: 'center', gap: 12 }]} onPress={() => router.push({ pathname: '/card/[id]', params: { id: c.id } })}>
                <Avatar name={c.name} company={c.company} size={36} favorite={c.favorite} />
                <Text style={st.value}>
                  {c.name} <Text style={st.sub}>{[c.department, c.title].filter(Boolean).join(' ')}</Text>
                </Text>
              </Pressable>
            ))}
          </Section>
        ) : null}

        <Section
          title="연동 상태"
          icon="git-network-outline"
          right={
            <Pressable onPress={() => resync(card.id)} disabled={syncing}>
              <Text style={{ ...type(14, '700', C.primary) }}>{syncing ? '전송 중…' : '전체 다시 보내기'}</Text>
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
                    <Text style={{ ...type(14, '700', C.primary) }}>재시도</Text>
                  </Pressable>
                ) : null}
              </View>
            );
          })}
        </Section>

        <View style={{ gap: 8 }}>
          <Button title="정보 수정" icon="create-outline" variant="dark" onPress={startEdit} />
          {CAN_OPEN_VCARD ? <Button title="아이폰 연락처에 저장" icon="person-add" onPress={() => openVCard(card)} /> : null}
          <Button title="vCard 파일로 공유" icon="document-attach-outline" variant="secondary" onPress={() => Share.share({ message: toVCard(card), title: card.name })} />
          <Button title="삭제" icon="trash-outline" variant="danger" onPress={confirmDelete} />
        </View>
        <Text style={[st.sub, { textAlign: 'center', marginTop: 12 }]}>
          등록 {card.createdAt.slice(0, 10)} · 수정 {card.updatedAt.slice(0, 10)}
        </Text>

        <Modal visible={qrOpen} transparent animationType="fade" onRequestClose={() => setQrOpen(false)}>
          <Pressable style={st.modalBg} onPress={() => setQrOpen(false)}>
            <View style={st.modalBox}>
              <Text style={st.modalBrand}>CARDSCAN</Text>
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
  name: { ...type(24, '800') },
  company: { ...type(16, '500'), marginTop: 4 },
  sub: { ...type(13, '400', T.sub) },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 14 },
  metaTag: { ...type(12, '700', T.primary) },
  metaDate: { ...type(12, '500', T.faint) },
  actions: { flexDirection: 'row', justifyContent: 'space-between', backgroundColor: T.surface, borderRadius: RADIUS.lg, paddingVertical: 16, paddingHorizontal: 10, marginTop: 14, marginBottom: 14 },
  row: { flexDirection: 'row', alignItems: 'flex-start', paddingVertical: 11, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: T.line },
  rowIcon: { width: 28, paddingTop: 2 },
  label: { width: 64, ...type(13, '600', T.sub), lineHeight: 21 },
  value: { flex: 1, ...type(15, '500'), lineHeight: 21 },
  syncRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 8 },
  tagWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 6 },
  tag: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: T.primarySoft, borderRadius: 14, paddingHorizontal: 11, paddingVertical: 6 },
  tagText: { ...type(13, '700', T.primary), lineHeight: 17 },
  tagGhost: { borderWidth: 1, borderColor: T.line, borderRadius: 14, paddingHorizontal: 11, paddingVertical: 6, backgroundColor: '#fff' },
  tagGhostText: { ...type(13, '600'), lineHeight: 17 },
  followNow: { ...type(18, '800', T.goldDeep), marginBottom: 4 },
  noteInput: { fontFamily: FONT, backgroundColor: '#F8F9FC', borderWidth: 1, borderColor: T.line, borderRadius: 12, padding: 12, minHeight: 64, fontSize: 15, color: T.text, textAlignVertical: 'top' },
  noteRow: { paddingVertical: 10, paddingLeft: 12, borderLeftWidth: 2, borderLeftColor: T.gold, marginTop: 10 },
  noteAt: { ...type(12, '600', T.faint), marginBottom: 2 },
  careerRow: { flexDirection: 'row', gap: 8, paddingVertical: 6 },
  careerDot: { color: T.gold, fontSize: 12, marginTop: 4 },
  modalBg: { flex: 1, backgroundColor: 'rgba(11,21,48,0.82)', alignItems: 'center', justifyContent: 'center' },
  modalBox: { backgroundColor: '#fff', borderRadius: RADIUS.xl, padding: 26, alignItems: 'center', borderWidth: 2, borderColor: T.gold },
  modalBrand: { fontFamily: FONT, fontSize: 10, fontWeight: '800', letterSpacing: 3, color: T.goldDeep },
  modalTitle: { ...type(19, '800'), marginBottom: 16, marginTop: 2 },
});
