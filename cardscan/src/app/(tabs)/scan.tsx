import { router } from 'expo-router';
import { t } from '../../i18n';
import { LinearGradient } from 'expo-linear-gradient';
import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Alert, Animated, Easing, Pressable, ScrollView, StyleSheet, Switch, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { isConfidentEnough } from '../../core/normalize';
import { allTags, normalizeTag } from '../../core/organize';
import { connectorTargets, CONNECTOR_LABEL } from '../../core/settings';
import { BusinessCard, CardKind, EMPTY_FIELDS, KIND_LABEL } from '../../core/types';
import { scanCardImage } from '../../integrations/ocr';
import { isDocumentScannerAvailable, recognizeText } from '../../../modules/card-ocr';
import { CapturedCard, captureCard, pickManyCards, prepareImage } from '../../ui/capture';
import { Button, Icon, KindPicker, PressableScale, SyncDot, tap } from '../../ui/components';
import { CardHero } from '../../ui/DigitalCard';
import { setDraft } from '../../ui/draft';
import { isReviewTag, reviewTag } from '../../ui/constants';
import { CAN_OPEN_VCARD, openVCard } from '../../ui/saveContact';
import { useLightStatusBar } from '../../ui/statusBar';
import { usePro } from '../../ui/pro';
import { ProLimitError, useStore } from '../../ui/store';
import { effectiveSettings } from '../../core/pro';
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
  const { settings, setSettings, addCard, cards, syncingIds } = useStore();
  const { isPro, requirePro } = usePro();
  const sendable = effectiveSettings(settings, isPro);
  const [tagEditing, setTagEditing] = useState(false);
  const [tagText, setTagText] = useState('');
  const [streak, setStreak] = useState(0);
  const eventTags = settings.scanTag ? [settings.scanTag] : [];
  const recentTags = allTags(cards)
    .map((ct) => ct.tag)
    .filter((ct) => !isReviewTag(ct) && ct !== settings.scanTag)
    .slice(0, 4);

  function setScanTag(tag: string) {
    setTagEditing(false);
    setTagText('');
    setSettings({ ...settings, scanTag: normalizeTag(tag) });
  }
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
  const targets = connectorTargets(sendable, kind);
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
      if (!shot) {
        setStreak(0);
        return setPhase('idle');
      }

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

      const toReview = () => {
        setDraft({ fields: result.fields, kind, extra: result.extra, imageUri: shot.front.uri, backImageUri: shot.back?.uri, note: result.note });
        setPhase('idle');
        router.push('/review');
      };
      if (settings.autoSave && isConfidentEnough(result.fields)) {
        setPhase('saving');
        let saved;
        try {
          saved = await addCard({
            fields: result.fields,
            kind,
            extra: result.extra,
            tempImageUri: shot.front.uri,
            tempBackUri: shot.back?.uri,
            tags: eventTags,
          });
        } catch (e) {
          if (!(e instanceof ProLimitError)) throw e;
          // 무료 한도 — 읽은 결과는 확인 화면에 살려 두고 Pro 안내. 구매하면 그 화면에서 바로 저장
          setStreak(0);
          toReview();
          requirePro('cards');
          return;
        }
        const { card, merged, careerChanged } = saved;
        tap('success');
        setLastId(card.id);
        setLastNote(careerChanged ? t('소속이 바뀌어 이전 회사·직책을 경력 이력에 남겼습니다') : merged ? t('같은 사람의 명함을 최신 정보로 갱신했습니다') : '');
        setPhase('idle');
        // 연속 촬영: 행사장에서 받은 명함 더미를 손 안 대고 차례로
        if (sendable.continuousScan && source === 'camera') {
          setStreak((n) => n + 1);
          setTimeout(() => run('camera'), 700);
        }
        return;
      }
      toReview();
    } catch (e) {
      setPhase('idle');
      Alert.alert(t('오류'), (e as Error).message);
    }
  }

  /** 앨범에서 여러 장을 골라 차례로 인식·저장 — 애매한 명함은 '확인필요' 그룹으로 */
  async function runBatch() {
    if (!requirePro('batch')) return;
    let uris: string[];
    try {
      uris = await pickManyCards();
    } catch (e) {
      return Alert.alert(t('오류'), (e as Error).message);
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
        if (!r.fields.name && !r.fields.company && !r.fields.mobile && !r.fields.email) throw new Error(t('글자 없음'));
        const confident = isConfidentEnough(r.fields);
        const { card, merged } = await addCard({
          fields: r.fields,
          kind,
          extra: r.extra,
          tempImageUri: img.uri,
          tags: confident ? eventTags : [...eventTags, reviewTag()],
        });
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
          <Text style={st.headTitle}>{t('명함 촬영')}</Text>
          <Text style={st.headSub}>
            {targets.length ? t('저장 → {1}', { 1: targets.map((ct) => t(CONNECTOR_LABEL[ct]).split(' (')[0]).join(' · ') }) : t('{1} 명함은 앱에만 저장됩니다', { 1: t(KIND_LABEL[kind]) })}
          </Text>
        </View>

        <View style={{ paddingHorizontal: 20 }}>
          <KindPicker value={kind} onChange={setKind} dark />
        </View>

        {/* 행사·모임 태그 — 켜 두면 이후 찍는 명함마다 자동으로 붙는다 */}
        {tagEditing ? (
          <View style={st.tagBox}>
            <View style={st.tagInputRow}>
              <Icon name="pricetag" size={16} color={T.gold} />
              <TextInput
                value={tagText}
                onChangeText={setTagText}
                autoFocus
                placeholder={t('예: 2026 코엑스 전시회, 3월 협력사 모임')}
                placeholderTextColor="rgba(255,255,255,0.35)"
                style={st.tagInput}
                returnKeyType="done"
                onSubmitEditing={() => setScanTag(tagText)}
              />
              <Pressable hitSlop={10} onPress={() => setScanTag(tagText)}>
                <Text style={st.tagOk}>{t('확인')}</Text>
              </Pressable>
            </View>
            {recentTags.length ? (
              <View style={st.tagSuggest}>
                {recentTags.map((ct) => (
                  <Pressable key={ct} onPress={() => setScanTag(ct)} style={st.tagChip}>
                    <Text style={st.tagChipText}>#{ct}</Text>
                  </Pressable>
                ))}
              </View>
            ) : null}
          </View>
        ) : (
          <Pressable style={[st.tagBox, st.tagRow]} onPress={() => setTagEditing(true)}>
            <Icon name={settings.scanTag ? 'pricetag' : 'pricetag-outline'} size={16} color={T.gold} />
            <Text style={[st.tagRowText, settings.scanTag && { color: '#fff' }]} numberOfLines={1}>
              {settings.scanTag ? `#${settings.scanTag}` : t('행사·모임 태그 붙이기 (전시회·세미나에서 편해요)')}
            </Text>
            {settings.scanTag ? <Text style={st.tagAuto}>{t('자동 태그 중')}</Text> : null}
            {settings.scanTag ? (
              <Pressable hitSlop={12} onPress={() => setScanTag('')} accessibilityLabel={t('행사 태그 끄기')}>
                <Icon name="close-circle" size={18} color="rgba(255,255,255,0.5)" />
              </Pressable>
            ) : null}
          </Pressable>
        )}

        <ScanOrb
          busy={busy}
          label={phase !== 'idle' ? t(PHASE_TEXT[phase]) : isDocumentScannerAvailable ? t('눌러서 촬영 · 테두리 자동 인식') : t('눌러서 촬영')}
          onPress={() => run('camera')}
        />

        <View style={st.row2}>
          <PressableScale style={st.ghost} onPress={() => run('library')} disabled={busy}>
            <Icon name="image-outline" size={18} color="#fff" />
            <Text style={st.ghostText}>{t('앨범 1장')}</Text>
          </PressableScale>
          <PressableScale style={st.ghost} onPress={runBatch} disabled={busy}>
            <Icon name="images-outline" size={18} color="#fff" />
            <Text style={st.ghostText}>{t('여러 장 한 번에')}</Text>
          </PressableScale>
        </View>
        {isDocumentScannerAvailable ? (
          <View style={st.switchRow}>
            <Icon name="copy-outline" size={16} color={T.gold} />
            <Text style={st.switchText}>{t('앞·뒷면 함께 찍기')}</Text>
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
        <View style={st.switchRow}>
          <Icon name="repeat" size={16} color={T.gold} />
          <Text style={st.switchText}>{t('연속 촬영 (저장하면 바로 다음 명함)')}</Text>
          <Switch
            value={sendable.continuousScan}
            onValueChange={(v) => {
              if (v && !requirePro('continuous')) return;
              tap('select');
              setSettings({ ...settings, continuousScan: v });
            }}
            trackColor={{ true: T.gold, false: 'rgba(255,255,255,0.2)' }}
            thumbColor="#fff"
          />
        </View>

        {batch ? (
          <View style={st.panel}>
            <Text style={st.panelTitle}>{batch.running ? t('여러 장 등록 중 {1}/{2}', { 1: batch.done, 2: batch.total }) : t('{1}장 등록 완료', { 1: batch.total })}</Text>
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
              <BatchStat n={batch.saved} label={t('저장')} />
              <BatchStat n={batch.merged} label={t('갱신')} />
              <BatchStat n={batch.needsReview} label={t('확인 필요')} gold />
              <BatchStat n={batch.failed} label={t('못 읽음')} />
            </View>
            {batch.running ? (
              <Button title={t('그만하기')} variant="dark" onPress={() => (stopRef.current = true)} style={{ marginTop: 12 }} />
            ) : batch.needsReview ? (
              <Button
                title={t('\'{1}\' {2}장 확인하기', { 1: reviewTag(), 2: batch.needsReview })}
                variant="gold"
                icon="checkmark-done"
                style={{ marginTop: 12 }}
                onPress={() =>
                  router.navigate({
                    pathname: '/',
                    params: { tag: reviewTag() },
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
              {streak > 1 ? <Text style={st.streak}>{t('연속 {1}장째', { 1: streak })}</Text> : null}
              <Text style={st.resultTitle}>{lastNote ? t('기존 명함을 갱신했어요') : t('저장했어요')}</Text>
            </View>
            {lastNote ? <Text style={st.resultNote}>{lastNote}</Text> : null}
            <CardHero card={last} imageUri={last.imageUri} backImageUri={last.backImageUri} favorite={last.favorite} />
            <View style={st.syncList}>
              {connectorTargets(sendable, last.kind).map((ct) => (
                <View key={ct} style={st.syncItem}>
                  <SyncDot status={last.sync[ct]} />
                  <Text style={st.syncText} numberOfLines={1}>
                    {t(CONNECTOR_LABEL[ct]).split(' (')[0]} ·{' '}
                    {last.sync[ct]?.state === 'ok'
                      ? (last.sync[ct]?.message ?? t('완료'))
                      : last.sync[ct]?.state === 'error'
                        ? t('실패: {1}', { 1: last.sync[ct]?.message ?? '' })
                        : syncingIds.has(last.id)
                          ? t('전송 중…')
                          : t('대기')}
                  </Text>
                </View>
              ))}
            </View>
            {CAN_OPEN_VCARD ? <Button title={t('아이폰 연락처에 저장')} icon="person-add" onPress={() => openVCard(last)} style={{ marginTop: 12 }} /> : null}
            <View style={{ flexDirection: 'row', gap: 10, marginTop: 12 }}>
              <Button
                title={t('메모·상세')}
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
              <Button title={t('다음 명함')} icon="scan" variant="gold" style={{ flex: 1 }} onPress={() => run('camera')} disabled={busy} />
            </View>
          </View>
        ) : !batch ? (
          <View style={st.tips}>
            {[
              ['sparkles-outline', t('테두리를 자동으로 찾아 반듯하게 펴고 그림자를 지웁니다')],
              ['flash-outline', settings.autoSave ? t('이름과 연락처가 읽히면 확인 없이 바로 저장·연동') : t('인식 결과를 확인한 뒤 저장')],
              ['git-compare-outline', t('같은 사람을 다시 찍으면 최신 정보로, 이직·승진은 경력 이력에')],
              ['albums-outline', t('쌓여 있던 명함 사진은 "여러 장 한 번에"로 (최대 50장)')],
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
          accessibilityLabel={t('명함 촬영')}
        >
          <LinearGradient colors={['#F1D9A3', T.gold, T.goldDeep]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={st.orbOuter}>
            <LinearGradient colors={[T.ink3, T.ink]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={st.orb}>
              {busy ? <ActivityIndicator color={T.gold} size="large" /> : <Icon name="scan" size={46} color={T.gold} />}
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
  orbArea: { alignItems: 'center', justifyContent: 'center', width: 300, height: 240 },
  orbRing: { position: 'absolute', top: 45, left: 75, width: 150, height: 150, borderRadius: 75, borderWidth: 2, borderColor: T.gold },
  orbOuter: { width: 150, height: 150, borderRadius: 75, padding: 4 },
  orb: { flex: 1, borderRadius: 73, alignItems: 'center', justifyContent: 'center' },
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
  tagBox: { marginHorizontal: 20, marginTop: 12, borderRadius: RADIUS.md, backgroundColor: 'rgba(255,255,255,0.06)', borderWidth: 1, borderColor: 'rgba(212,175,106,0.35)' },
  tagRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 14, paddingVertical: 12 },
  tagRowText: { ...type(13, '600', 'rgba(255,255,255,0.65)'), flex: 1 },
  tagInputRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 14 },
  tagInput: { flex: 1, fontFamily: FONT, fontSize: 15, color: '#fff', paddingVertical: 12 },
  tagAuto: { ...type(11, '800', T.ink), backgroundColor: T.gold, borderRadius: 8, paddingHorizontal: 7, overflow: 'hidden' },
  tagOk: { ...type(14, '800', T.gold) },
  tagSuggest: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, paddingHorizontal: 12, paddingBottom: 12 },
  tagChip: { borderRadius: 14, paddingHorizontal: 10, paddingVertical: 5, backgroundColor: 'rgba(255,255,255,0.08)' },
  tagChipText: { ...type(12, '700', 'rgba(255,255,255,0.8)') },
  streak: { ...type(12, '800', T.ink), backgroundColor: T.gold, borderRadius: 10, paddingHorizontal: 8, overflow: 'hidden', marginLeft: 2 },
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
