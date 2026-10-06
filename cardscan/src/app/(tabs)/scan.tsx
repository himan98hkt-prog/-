import { router } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { Alert, ScrollView, StyleSheet, Switch, Text, View } from 'react-native';
import { isConfidentEnough } from '../../core/normalize';
import { connectorTargets, CONNECTOR_LABEL } from '../../core/settings';
import { BusinessCard, CardKind, EMPTY_FIELDS, KIND_LABEL } from '../../core/types';
import { scanCardImage } from '../../integrations/ocr';
import { isDocumentScannerAvailable, recognizeText } from '../../../modules/card-ocr';
import { CapturedCard, captureCard, pickManyCards, prepareImage } from '../../ui/capture';
import { CardImage } from '../../ui/CardImage';
import { Button, C, KindPicker, Section, SyncDot } from '../../ui/components';
import { setDraft } from '../../ui/draft';
import { REVIEW_TAG } from '../../ui/constants';
import { CAN_OPEN_VCARD, openVCard } from '../../ui/saveContact';
import { useStore } from '../../ui/store';

type Phase = 'idle' | 'capturing' | 'reading' | 'saving';

const PHASE_TEXT: Record<Phase, string> = {
  idle: '',
  capturing: '사진 준비 중…',
  reading: '명함을 읽는 중…',
  saving: '저장하고 연동하는 중…',
};

/** 여러 장 등록 중 진행 상황 */
interface Batch {
  total: number;
  done: number;
  saved: number;
  merged: number;
  needsReview: number;
  failed: number;
  running: boolean;
}

export default function ScanScreen() {
  const { settings, addCard, setMeta, cards, syncingIds } = useStore();
  const [kind, setKind] = useState<CardKind>(settings.defaultKind);
  const [withBack, setWithBack] = useState(false);
  const [phase, setPhase] = useState<Phase>('idle');
  const [lastId, setLastId] = useState<string | null>(null);
  const [lastNote, setLastNote] = useState('');
  const [batch, setBatch] = useState<Batch | null>(null);
  const stopRef = useRef(false);
  const last: BusinessCard | undefined = cards.find((c) => c.id === lastId);
  const targets = connectorTargets(settings, kind);
  // 설정은 비동기로 불러오므로 기본 구분이 늦게 도착하면 맞춰 준다
  useEffect(() => setKind(settings.defaultKind), [settings.defaultKind]);

  async function readCard(shot: CapturedCard) {
    const front = await scanCardImage(shot.front, settings, { recognize: recognizeText });
    if (!shot.back) return front;
    // 뒷면(영문면 등)은 앞면에서 못 읽은 칸만 채운다
    try {
      const back = await scanCardImage(shot.back, settings, { recognize: recognizeText });
      const fields = { ...front.fields };
      for (const k of Object.keys(fields) as (keyof typeof fields)[]) if (!fields[k] && back.fields[k]) fields[k] = back.fields[k];
      if (!fields.nameEn && /^[A-Za-z]/.test(back.fields.name)) fields.nameEn = back.fields.name;
      return { ...front, fields, extra: [...front.extra, ...back.extra].slice(0, 20) };
    } catch {
      return front;
    }
  }

  async function run(source: 'camera' | 'library') {
    try {
      setPhase('capturing');
      const shot = await captureCard(source, withBack);
      if (!shot) return setPhase('idle');

      setPhase('reading');
      let result;
      try {
        result = await readCard(shot);
      } catch (e) {
        // 인식 실패해도 사진은 살려서 직접 입력할 수 있게 한다
        setDraft({ fields: { ...EMPTY_FIELDS }, kind, extra: [], imageUri: shot.front.uri, backImageUri: shot.back?.uri, error: (e as Error).message });
        setPhase('idle');
        return router.push('/review');
      }

      if (settings.autoSave && isConfidentEnough(result.fields)) {
        setPhase('saving');
        const { card, merged, careerChanged } = await addCard({
          fields: result.fields, kind, extra: result.extra, tempImageUri: shot.front.uri, tempBackUri: shot.back?.uri,
        });
        setLastId(card.id);
        setLastNote(careerChanged ? '소속이 바뀌어 이전 회사·직책을 경력 이력에 남겼습니다' : merged ? '같은 사람의 명함을 최신 정보로 갱신했습니다' : '');
        setPhase('idle');
        return;
      }
      setDraft({ fields: result.fields, kind, extra: result.extra, imageUri: shot.front.uri, backImageUri: shot.back?.uri, note: result.note });
      setPhase('idle');
      router.push('/review');
    } catch (e) {
      setPhase('idle');
      Alert.alert('오류', (e as Error).message);
    }
  }

  /** 앨범에서 여러 장을 골라 차례로 인식·저장 — 애매한 명함은 '확인필요' 그룹으로 */
  async function runBatch() {
    let uris: string[];
    try {
      uris = await pickManyCards();
    } catch (e) {
      return Alert.alert('오류', (e as Error).message);
    }
    if (!uris.length) return;
    stopRef.current = false;
    const b: Batch = { total: uris.length, done: 0, saved: 0, merged: 0, needsReview: 0, failed: 0, running: true };
    setBatch({ ...b });
    for (const uri of uris) {
      if (stopRef.current) break;
      try {
        const img = await prepareImage(uri);
        const r = await scanCardImage(img, settings, { recognize: recognizeText });
        if (!r.fields.name && !r.fields.company && !r.fields.mobile && !r.fields.email) throw new Error('글자 없음');
        const confident = isConfidentEnough(r.fields);
        const { card, merged } = await addCard({ fields: r.fields, kind, extra: r.extra, tempImageUri: img.uri });
        if (!confident) setMeta(card.id, { tags: [...(card.tags ?? []), REVIEW_TAG] });
        b.saved++;
        if (merged) b.merged++;
        if (!confident) b.needsReview++;
      } catch {
        b.failed++;
      }
      b.done++;
      setBatch({ ...b });
    }
    b.running = false;
    setBatch({ ...b });
  }

  const busy = phase !== 'idle' || !!batch?.running;

  return (
    <ScrollView style={{ flex: 1, backgroundColor: C.bg }} contentContainerStyle={{ padding: 16 }}>
      <Section title="이 명함은">
        <KindPicker value={kind} onChange={setKind} />
        <Text style={[st.hint, { marginTop: 10 }]}>
          {targets.length
            ? `저장 위치: ${targets.map((t) => CONNECTOR_LABEL[t].split(' (')[0]).join(', ')}`
            : `${KIND_LABEL[kind]} 명함을 보낼 연동이 꺼져 있습니다 — 앱에만 저장됩니다`}
        </Text>
        {isDocumentScannerAvailable ? (
          <View style={st.switchRow}>
            <Text style={st.label}>앞·뒷면 함께 찍기</Text>
            <Switch value={withBack} onValueChange={setWithBack} />
          </View>
        ) : null}
      </Section>

      <Button
        title={isDocumentScannerAvailable ? '📷  명함 촬영 (자동 테두리 인식)' : '📷  카메라로 명함 촬영'}
        onPress={() => run('camera')}
        loading={phase === 'capturing'}
        disabled={busy}
        style={{ minHeight: 64 }}
      />
      <View style={{ flexDirection: 'row', gap: 8, marginTop: 10 }}>
        <Button title="앨범에서 1장" variant="secondary" onPress={() => run('library')} disabled={busy} style={{ flex: 1 }} />
        <Button title="앨범에서 여러 장" variant="secondary" onPress={runBatch} disabled={busy} style={{ flex: 1 }} />
      </View>
      {phase !== 'idle' ? <Text style={[st.hint, { textAlign: 'center', marginTop: 16, fontSize: 15 }]}>{PHASE_TEXT[phase]}</Text> : null}
      <View style={{ height: 16 }} />

      {batch ? (
        <Section title={batch.running ? `여러 장 등록 중… ${batch.done}/${batch.total}` : `여러 장 등록 완료 (${batch.total}장)`}>
          <View style={st.progressTrack}>
            <View style={[st.progressBar, { width: `${Math.round((batch.done / Math.max(1, batch.total)) * 100)}%` }]} />
          </View>
          <Text style={[st.hint, { marginTop: 8 }]}>
            저장 {batch.saved}장{batch.merged ? ` (기존 명함 갱신 ${batch.merged})` : ''} · 확인 필요 {batch.needsReview}장 · 읽지 못함 {batch.failed}장
          </Text>
          {batch.running ? (
            <Button title="그만하기" variant="secondary" style={{ marginTop: 10 }} onPress={() => (stopRef.current = true)} />
          ) : batch.needsReview ? (
            <Button
              title={`'${REVIEW_TAG}' 명함 ${batch.needsReview}장 보기`}
              variant="secondary"
              style={{ marginTop: 10 }}
              onPress={() => router.navigate({ pathname: '/', params: { tag: REVIEW_TAG } })}
            />
          ) : null}
        </Section>
      ) : null}

      {last ? (
        <Section title={lastNote ? '기존 명함 갱신' : '저장 완료'}>
          {lastNote ? <Text style={[st.hint, { color: C.primary, marginBottom: 8 }]}>{lastNote}</Text> : null}
          <View style={{ flexDirection: 'row', gap: 12 }}>
            {last.imageUri ? <CardImage uri={last.imageUri} style={st.thumb} /> : null}
            <View style={{ flex: 1 }}>
              <Text style={st.name}>
                {last.name} <Text style={st.hint}>{last.title}</Text>
              </Text>
              <Text style={st.hint}>{[last.company, last.department].filter(Boolean).join(' · ')}</Text>
              <Text style={st.hint}>{last.mobile || last.phone || last.email}</Text>
            </View>
          </View>
          <View style={{ marginTop: 12, gap: 6 }}>
            {connectorTargets(settings, last.kind).map((t) => (
              <View key={t} style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <SyncDot status={last.sync[t]} />
                <Text style={st.hint}>
                  {CONNECTOR_LABEL[t].split(' (')[0]} —{' '}
                  {last.sync[t]?.state === 'ok'
                    ? last.sync[t]?.message ?? '완료'
                    : last.sync[t]?.state === 'error'
                      ? `실패: ${last.sync[t]?.message}`
                      : syncingIds.has(last.id)
                        ? '전송 중…'
                        : '대기'}
                </Text>
              </View>
            ))}
          </View>
          {CAN_OPEN_VCARD ? <Button title="📇 아이폰 연락처에 저장" onPress={() => openVCard(last)} style={{ marginTop: 14 }} /> : null}
          <View style={{ flexDirection: 'row', gap: 8, marginTop: 14 }}>
            <Button title="내용 확인·메모" variant="secondary" style={{ flex: 1 }} onPress={() => router.push({ pathname: '/card/[id]', params: { id: last.id } })} />
            <Button title="다음 명함 촬영" style={{ flex: 1 }} onPress={() => run('camera')} disabled={busy} />
          </View>
        </Section>
      ) : !batch ? (
        <Section title="촬영 요령">
          {isDocumentScannerAvailable ? <Text style={st.hint}>• 명함 테두리를 자동으로 찾아 반듯하게 펴고 그림자를 지웁니다.</Text> : null}
          <Text style={st.hint}>• 어두운 바탕 위에 명함을 놓고 찍으면 가장 정확합니다.</Text>
          <Text style={st.hint}>
            • {settings.autoSave ? '이름과 연락처가 읽히면 확인 없이 바로 저장·연동됩니다.' : '인식 결과를 확인한 뒤 저장합니다.'} (설정에서 변경)
          </Text>
          <Text style={st.hint}>• 같은 사람의 명함을 다시 찍으면 최신 정보로 갱신하고, 회사·직책이 바뀌었으면 경력 이력에 남깁니다.</Text>
          <Text style={st.hint}>• 쌓여 있던 명함 사진은 "앨범에서 여러 장"으로 한 번에 등록하세요 (최대 50장).</Text>
        </Section>
      ) : null}
    </ScrollView>
  );
}

const st = StyleSheet.create({
  hint: { fontSize: 14, color: C.sub, lineHeight: 21 },
  label: { fontSize: 15, fontWeight: '600', color: C.text },
  name: { fontSize: 18, fontWeight: '700', color: C.text },
  thumb: { width: 110, height: 66, borderRadius: 8 },
  switchRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 12 },
  progressTrack: { height: 8, borderRadius: 4, backgroundColor: C.line, overflow: 'hidden' },
  progressBar: { height: 8, backgroundColor: C.primary },
});
