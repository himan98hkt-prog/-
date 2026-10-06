import { router } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Alert, Animated, Easing, Pressable, ScrollView, StyleSheet, Switch, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { isConfidentEnough } from '../../core/normalize';
import { connectorTargets, CONNECTOR_LABEL } from '../../core/settings';
import { BusinessCard, CardKind, EMPTY_FIELDS, KIND_LABEL } from '../../core/types';
import { scanCardImage } from '../../integrations/ocr';
import { isDocumentScannerAvailable, recognizeText } from '../../../modules/card-ocr';
import { CapturedCard, captureCard, pickManyCards, prepareImage } from '../../ui/capture';
import { Button, Icon, KindPicker, PressableScale, SyncDot, tap } from '../../ui/components';
import { DigitalCard } from '../../ui/DigitalCard';
import { setDraft } from '../../ui/draft';
import { REVIEW_TAG } from '../../ui/constants';
import { CAN_OPEN_VCARD, openVCard } from '../../ui/saveContact';
import { useLightStatusBar } from '../../ui/statusBar';
import { useStore } from '../../ui/store';
import { FONT, RADIUS, T, type } from '../../ui/theme';

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
  const insets = useSafeAreaInsets();
  useLightStatusBar();
  const last: BusinessCard | undefined = cards.find((c) => c.id === lastId);
  const targets = connectorTargets(settings, kind);
  // 설정은 비동기로 불러오므로 기본 구분이 늦게 도착하면 맞춰 준다
  useEffect(() => setKind(settings.defaultKind), [settings.defaultKind]);

  async function readCard(shot: CapturedCard) {
    const front = await scanCardImage(shot.front, settings, {
      recognize: recognizeText,
    });
    if (!shot.back) return front;
    // 뒷면(영문면 등)은 앞면에서 못 읽은 칸만 채운다
    try {
      const back = await scanCardImage(shot.back, settings, {
        recognize: recognizeText,
      });
      const fields = { ...front.fields };
      for (const k of Object.keys(fields) as (keyof typeof fields)[]) if (!fields[k] && back.fields[k]) fields[k] = back.fields[k];
      if (!fields.nameEn && /^[A-Za-z]/.test(back.fields.name)) fields.nameEn = back.fields.name;
      return {
        ...front,
        fields,
        extra: [...front.extra, ...back.extra].slice(0, 20),
      };
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
        setDraft({
          fields: { ...EMPTY_FIELDS },
          kind,
          extra: [],
          imageUri: shot.front.uri,
          backImageUri: shot.back?.uri,
          error: (e as Error).message,
        });
        setPhase('idle');
        return router.push('/review');
      }

      if (settings.autoSave && isConfidentEnough(result.fields)) {
        setPhase('saving');
        const { card, merged, careerChanged } = await addCard({
          fields: result.fields,
          kind,
          extra: result.extra,
          tempImageUri: shot.front.uri,
          tempBackUri: shot.back?.uri,
        });
        tap('success');
        setLastId(card.id);
        setLastNote(careerChanged ? '소속이 바뀌어 이전 회사·직책을 경력 이력에 남겼습니다' : merged ? '같은 사람의 명함을 최신 정보로 갱신했습니다' : '');
        setPhase('idle');
        return;
      }
      setDraft({
        fields: result.fields,
        kind,
        extra: result.extra,
        imageUri: shot.front.uri,
        backImageUri: shot.back?.uri,
        note: result.note,
      });
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
    const b: Batch = {
      total: uris.length,
      done: 0,
      saved: 0,
      merged: 0,
      needsReview: 0,
      failed: 0,
      running: true,
    };
    setBatch({ ...b });
    for (const uri of uris) {
      if (stopRef.current) break;
      try {
        const img = await prepareImage(uri);
        const r = await scanCardImage(img, settings, {
          recognize: recognizeText,
        });
        if (!r.fields.name && !r.fields.company && !r.fields.mobile && !r.fields.email) throw new Error('글자 없음');
        const confident = isConfidentEnough(r.fields);
        const { card, merged } = await addCard({
          fields: r.fields,
          kind,
          extra: r.extra,
          tempImageUri: img.uri,
        });
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
    <View style={{ flex: 1, backgroundColor: T.ink }}>
      <ScrollView
        contentContainerStyle={{
          paddingTop: insets.top + 12,
          paddingBottom: 40,
        }}
      >
        <View style={st.head}>
          <Text style={st.brand}>SCAN</Text>
          <Text style={st.headTitle}>명함 촬영</Text>
          <Text style={st.headSub}>
            {targets.length ? `저장 → ${targets.map((t) => CONNECTOR_LABEL[t].split(' (')[0]).join(' · ')}` : `${KIND_LABEL[kind]} 명함은 앱에만 저장됩니다`}
          </Text>
        </View>

        <View style={{ paddingHorizontal: 20 }}>
          <KindPicker value={kind} onChange={setKind} dark />
        </View>

        <ScanOrb
          busy={busy}
          label={phase !== 'idle' ? PHASE_TEXT[phase] : isDocumentScannerAvailable ? '눌러서 촬영 · 테두리 자동 인식' : '눌러서 촬영'}
          onPress={() => run('camera')}
        />

        <View style={st.row2}>
          <PressableScale style={st.ghost} onPress={() => run('library')} disabled={busy}>
            <Icon name="image-outline" size={18} color="#fff" />
            <Text style={st.ghostText}>앨범 1장</Text>
          </PressableScale>
          <PressableScale style={st.ghost} onPress={runBatch} disabled={busy}>
            <Icon name="images-outline" size={18} color="#fff" />
            <Text style={st.ghostText}>여러 장 한 번에</Text>
          </PressableScale>
        </View>
        {isDocumentScannerAvailable ? (
          <View style={st.switchRow}>
            <Icon name="copy-outline" size={16} color={T.gold} />
            <Text style={st.switchText}>앞·뒷면 함께 찍기</Text>
            <Switch
              value={withBack}
              onValueChange={(v) => {
                tap('select');
                setWithBack(v);
              }}
              trackColor={{ true: T.gold, false: 'rgba(255,255,255,0.2)' }}
              thumbColor="#fff"
            />
          </View>
        ) : null}

        {batch ? (
          <View style={st.panel}>
            <Text style={st.panelTitle}>{batch.running ? `여러 장 등록 중 ${batch.done}/${batch.total}` : `${batch.total}장 등록 완료`}</Text>
            <View style={st.progressTrack}>
              <LinearGradient
                colors={['#E9CB8C', T.gold]}
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 0 }}
                style={[
                  st.progressBar,
                  {
                    width: `${Math.round((batch.done / Math.max(1, batch.total)) * 100)}%`,
                  },
                ]}
              />
            </View>
            <View style={st.batchStats}>
              <BatchStat n={batch.saved} label="저장" />
              <BatchStat n={batch.merged} label="갱신" />
              <BatchStat n={batch.needsReview} label="확인 필요" gold />
              <BatchStat n={batch.failed} label="못 읽음" />
            </View>
            {batch.running ? (
              <Button title="그만하기" variant="dark" onPress={() => (stopRef.current = true)} style={{ marginTop: 12 }} />
            ) : batch.needsReview ? (
              <Button
                title={`'${REVIEW_TAG}' ${batch.needsReview}장 확인하기`}
                variant="gold"
                icon="checkmark-done"
                style={{ marginTop: 12 }}
                onPress={() =>
                  router.navigate({
                    pathname: '/',
                    params: { tag: REVIEW_TAG },
                  })
                }
              />
            ) : null}
          </View>
        ) : null}

        {last ? (
          <View style={st.result}>
            <View style={st.resultHead}>
              <Icon name="checkmark-circle" size={20} color={T.gold} />
              <Text style={st.resultTitle}>{lastNote ? '기존 명함을 갱신했어요' : '저장했어요'}</Text>
            </View>
            {lastNote ? <Text style={st.resultNote}>{lastNote}</Text> : null}
            <DigitalCard card={last} imageUri={last.imageUri} backImageUri={last.backImageUri} favorite={last.favorite} />
            <View style={st.syncList}>
              {connectorTargets(settings, last.kind).map((t) => (
                <View key={t} style={st.syncItem}>
                  <SyncDot status={last.sync[t]} />
                  <Text style={st.syncText} numberOfLines={1}>
                    {CONNECTOR_LABEL[t].split(' (')[0]} ·{' '}
                    {last.sync[t]?.state === 'ok'
                      ? (last.sync[t]?.message ?? '완료')
                      : last.sync[t]?.state === 'error'
                        ? `실패: ${last.sync[t]?.message}`
                        : syncingIds.has(last.id)
                          ? '전송 중…'
                          : '대기'}
                  </Text>
                </View>
              ))}
            </View>
            {CAN_OPEN_VCARD ? <Button title="아이폰 연락처에 저장" icon="person-add" onPress={() => openVCard(last)} style={{ marginTop: 12 }} /> : null}
            <View style={{ flexDirection: 'row', gap: 10, marginTop: 12 }}>
              <Button
                title="메모·상세"
                icon="create-outline"
                variant="dark"
                style={{ flex: 1 }}
                onPress={() =>
                  router.push({
                    pathname: '/card/[id]',
                    params: { id: last.id },
                  })
                }
              />
              <Button title="다음 명함" icon="scan" variant="gold" style={{ flex: 1 }} onPress={() => run('camera')} disabled={busy} />
            </View>
          </View>
        ) : !batch ? (
          <View style={st.tips}>
            {[
              ['sparkles-outline', '테두리를 자동으로 찾아 반듯하게 펴고 그림자를 지웁니다'],
              ['flash-outline', settings.autoSave ? '이름과 연락처가 읽히면 확인 없이 바로 저장·연동' : '인식 결과를 확인한 뒤 저장'],
              ['git-compare-outline', '같은 사람을 다시 찍으면 최신 정보로, 이직·승진은 경력 이력에'],
              ['albums-outline', '쌓여 있던 명함 사진은 "여러 장 한 번에"로 (최대 50장)'],
            ].map(([icon, text]) => (
              <View key={text} style={st.tip}>
                <Icon name={icon as never} size={16} color={T.gold} />
                <Text style={st.tipText}>{text}</Text>
              </View>
            ))}
          </View>
        ) : null}
      </ScrollView>
    </View>
  );
}

/** 가운데 큰 촬영 버튼 — 금빛 고리가 숨 쉬듯 퍼진다 */
function ScanOrb({ onPress, busy, label }: { onPress: () => void; busy: boolean; label: string }) {
  const pulse = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    const loop = Animated.loop(
      Animated.timing(pulse, {
        toValue: 1,
        duration: 2200,
        easing: Easing.out(Easing.quad),
        useNativeDriver: true,
      }),
    );
    loop.start();
    return () => loop.stop();
  }, [pulse]);
  const ring = (delay: number) => {
    const p = Animated.modulo(Animated.add(pulse, delay), 1);
    return {
      opacity: p.interpolate({
        inputRange: [0, 0.7, 1],
        outputRange: [0.55, 0.12, 0],
      }),
      transform: [
        {
          scale: p.interpolate({ inputRange: [0, 1], outputRange: [1, 1.55] }),
        },
      ],
    };
  };
  return (
    <View style={{ alignItems: 'center', marginVertical: 8 }}>
      <View style={st.orbArea}>
        {!busy ? <Animated.View style={[st.orbRing, ring(0)]} /> : null}
        {!busy ? <Animated.View style={[st.orbRing, ring(0.5)]} /> : null}
        <Pressable
          onPress={() => {
            tap();
            onPress();
          }}
          disabled={busy}
          accessibilityRole="button"
          accessibilityLabel="명함 촬영"
        >
          <LinearGradient colors={['#F1D9A3', T.gold, T.goldDeep]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={st.orbOuter}>
            <LinearGradient colors={[T.ink3, T.ink]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={st.orb}>
              {busy ? <ActivityIndicator color={T.gold} size="large" /> : <Icon name="scan" size={54} color={T.gold} />}
            </LinearGradient>
          </LinearGradient>
        </Pressable>
      </View>
      <Text style={st.orbLabel}>{label}</Text>
    </View>
  );
}

function BatchStat({ n, label, gold }: { n: number; label: string; gold?: boolean }) {
  return (
    <View style={{ alignItems: 'center', flex: 1 }}>
      <Text style={[st.batchN, gold && n > 0 && { color: T.gold }]}>{n}</Text>
      <Text style={st.batchLabel}>{label}</Text>
    </View>
  );
}

const st = StyleSheet.create({
  head: { paddingHorizontal: 20, marginBottom: 18 },
  brand: {
    fontFamily: FONT,
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 3,
    color: T.gold,
  },
  headTitle: {
    fontFamily: FONT,
    fontSize: 30,
    fontWeight: '800',
    color: '#fff',
    letterSpacing: -0.6,
    marginTop: 2,
  },
  headSub: { ...type(13, '500', 'rgba(255,255,255,0.55)'), marginTop: 4 },
  orbArea: {
    alignItems: 'center',
    justifyContent: 'center',
    width: 300,
    height: 290,
  },
  orbRing: {
    position: 'absolute',
    top: 55,
    left: 60,
    width: 180,
    height: 180,
    borderRadius: 90,
    borderWidth: 2,
    borderColor: T.gold,
  },
  orbOuter: { width: 180, height: 180, borderRadius: 90, padding: 4 },
  orb: {
    flex: 1,
    borderRadius: 88,
    alignItems: 'center',
    justifyContent: 'center',
  },
  orbLabel: {
    ...type(13, '600', 'rgba(255,255,255,0.7)'),
    marginTop: -4,
    marginBottom: 18,
  },
  row2: { flexDirection: 'row', gap: 10, paddingHorizontal: 20 },
  ghost: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 15,
    borderRadius: RADIUS.md,
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.12)',
  },
  ghostText: { ...type(14, '700', '#fff') },
  switchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginHorizontal: 20,
    marginTop: 12,
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: RADIUS.md,
    backgroundColor: 'rgba(255,255,255,0.05)',
  },
  switchText: { ...type(14, '600', 'rgba(255,255,255,0.85)'), flex: 1 },
  panel: {
    marginHorizontal: 20,
    marginTop: 18,
    padding: 18,
    borderRadius: RADIUS.lg,
    backgroundColor: 'rgba(255,255,255,0.06)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.1)',
  },
  panelTitle: { ...type(16, '800', '#fff'), marginBottom: 12 },
  progressTrack: {
    height: 8,
    borderRadius: 4,
    backgroundColor: 'rgba(255,255,255,0.1)',
    overflow: 'hidden',
  },
  progressBar: { height: 8, borderRadius: 4 },
  batchStats: { flexDirection: 'row', marginTop: 14 },
  batchN: { fontFamily: FONT, fontSize: 22, fontWeight: '800', color: '#fff' },
  batchLabel: { ...type(11, '600', 'rgba(255,255,255,0.5)') },
  result: { marginHorizontal: 20, marginTop: 22 },
  resultHead: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 6,
  },
  resultTitle: { ...type(17, '800', '#fff') },
  resultNote: { ...type(13, '600', T.gold), marginBottom: 10 },
  syncList: { marginTop: 14, gap: 6 },
  syncItem: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  syncText: { ...type(13, '500', 'rgba(255,255,255,0.7)'), flex: 1 },
  tips: {
    marginHorizontal: 20,
    marginTop: 22,
    gap: 12,
    padding: 18,
    borderRadius: RADIUS.lg,
    backgroundColor: 'rgba(255,255,255,0.04)',
  },
  tip: { flexDirection: 'row', gap: 10, alignItems: 'flex-start' },
  tipText: { ...type(13, '500', 'rgba(255,255,255,0.7)'), flex: 1 },
});
