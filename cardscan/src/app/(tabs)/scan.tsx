import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Alert, ScrollView, StyleSheet, Text, View } from 'react-native';
import { isConfidentEnough } from '../../core/normalize';
import { connectorTargets, CONNECTOR_LABEL } from '../../core/settings';
import { BusinessCard, CardKind, EMPTY_FIELDS, KIND_LABEL } from '../../core/types';
import { scanCardImage } from '../../integrations/ocr';
import { recognizeText } from '../../../modules/card-ocr';
import { captureCard } from '../../ui/capture';
import { Button, C, KindPicker, Section, SyncDot } from '../../ui/components';
import { setDraft } from '../../ui/draft';
import { CardImage } from '../../ui/CardImage';
import { CAN_OPEN_VCARD, openVCard } from '../../ui/saveContact';
import { useStore } from '../../ui/store';

type Phase = 'idle' | 'capturing' | 'reading' | 'saving';

const PHASE_TEXT: Record<Phase, string> = {
  idle: '',
  capturing: '사진 준비 중…',
  reading: '명함을 읽는 중…',
  saving: '저장하고 연동하는 중…',
};

export default function ScanScreen() {
  const { settings, addCard, cards, syncingIds } = useStore();
  const [kind, setKind] = useState<CardKind>(settings.defaultKind);
  const [phase, setPhase] = useState<Phase>('idle');
  const [lastId, setLastId] = useState<string | null>(null);
  const [lastMerged, setLastMerged] = useState(false);
  const last: BusinessCard | undefined = cards.find((c) => c.id === lastId);
  const targets = connectorTargets(settings, kind);
  // 설정은 비동기로 불러오므로 기본 구분이 늦게 도착하면 맞춰 준다
  useEffect(() => setKind(settings.defaultKind), [settings.defaultKind]);

  async function run(source: 'camera' | 'library') {
    try {
      setPhase('capturing');
      const img = await captureCard(source);
      if (!img) return setPhase('idle');

      setPhase('reading');
      let result;
      try {
        result = await scanCardImage(img, settings, { recognize: recognizeText });
      } catch (e) {
        // 인식 실패해도 사진은 살려서 직접 입력할 수 있게 한다
        setDraft({ fields: { ...EMPTY_FIELDS }, kind, extra: [], imageUri: img.uri, error: (e as Error).message });
        setPhase('idle');
        return router.push('/review');
      }

      if (settings.autoSave && isConfidentEnough(result.fields)) {
        setPhase('saving');
        const { card, merged } = await addCard({ fields: result.fields, kind, extra: result.extra, tempImageUri: img.uri });
        setLastId(card.id);
        setLastMerged(merged);
        setPhase('idle');
        return;
      }
      setDraft({ fields: result.fields, kind, extra: result.extra, imageUri: img.uri, note: result.note });
      setPhase('idle');
      router.push('/review');
    } catch (e) {
      setPhase('idle');
      Alert.alert('오류', (e as Error).message);
    }
  }

  const busy = phase !== 'idle';

  return (
    <ScrollView style={{ flex: 1, backgroundColor: C.bg }} contentContainerStyle={{ padding: 16 }}>
      <Section title="이 명함은">
        <KindPicker value={kind} onChange={setKind} />
        <Text style={[st.hint, { marginTop: 10 }]}>
          {targets.length
            ? `저장 위치: ${targets.map((t) => CONNECTOR_LABEL[t].split(' (')[0]).join(', ')}`
            : `${KIND_LABEL[kind]} 명함을 보낼 연동이 꺼져 있습니다 — 앱에만 저장됩니다`}
        </Text>
      </Section>

      <Button title="📷  카메라로 명함 촬영" onPress={() => run('camera')} loading={phase === 'capturing'} disabled={busy} style={{ minHeight: 64 }} />
      <Button title="앨범에서 명함 사진 선택" variant="secondary" onPress={() => run('library')} disabled={busy} style={{ marginTop: 10 }} />
      {busy ? <Text style={[st.hint, { textAlign: 'center', marginTop: 16, fontSize: 15 }]}>{PHASE_TEXT[phase]}</Text> : null}
      <View style={{ height: 16 }} />

      {last ? (
        <Section title={lastMerged ? '기존 명함을 최신 정보로 갱신했습니다' : '저장 완료'}>
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
            <Button title="내용 확인·수정" variant="secondary" style={{ flex: 1 }} onPress={() => router.push({ pathname: '/card/[id]', params: { id: last.id } })} />
            <Button title="다음 명함 촬영" style={{ flex: 1 }} onPress={() => run('camera')} disabled={busy} />
          </View>
        </Section>
      ) : (
        <Section title="촬영 요령">
          <Text style={st.hint}>• 어두운 바탕 위에 명함을 놓고 정면에서 찍으면 가장 정확합니다.</Text>
          <Text style={st.hint}>• 촬영 후 자르기 화면에서 명함 테두리에 맞춰 주세요.</Text>
          <Text style={st.hint}>
            • {settings.autoSave ? '이름과 연락처가 읽히면 확인 없이 바로 저장·연동됩니다.' : '인식 결과를 확인한 뒤 저장합니다.'} (설정에서 변경)
          </Text>
          <Text style={st.hint}>• 같은 사람(휴대폰·이메일 동일)의 명함은 새로 만들지 않고 최신 정보로 갱신합니다.</Text>
        </Section>
      )}
    </ScrollView>
  );
}

const st = StyleSheet.create({
  hint: { fontSize: 14, color: C.sub, lineHeight: 21 },
  name: { fontSize: 18, fontWeight: '700', color: C.text },
  thumb: { width: 110, height: 66, borderRadius: 8 },
});
