import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { CONTEXT_PRESETS, PET_LABEL, emotionMeta } from '../../core/emotions';
import { relativeKo } from '../../core/date';
import { useActivePet, useEntriesForActivePet, usePetStore, useQuota } from '../../store/usePetStore';
import { Badge, Button, Card, Chip, Empty, SectionTitle } from '../components/Basics';
import { PulseRecordButton } from '../components/PulseRecordButton';
import { RECORD_SECONDS, startRecording, type RecordingHandle } from '../media';
import { useNavigation } from '../navigation';
import { useAnalyzeMedia } from '../useAnalyze';
import { colors, font, radius, space } from '../theme';

export function HomeScreen() {
  const nav = useNavigation();
  const pet = useActivePet();
  const pets = usePetStore((s) => s.pets);
  const setActivePet = usePetStore((s) => s.setActivePet);
  const entries = useEntriesForActivePet();
  const quota = useQuota();

  const [context, setContext] = useState('');
  const [recording, setRecording] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState(RECORD_SECONDS);
  const { analyzing, run } = useAnalyzeMedia();

  const handleRef = useRef<RecordingHandle | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const stoppingRef = useRef(false);

  const clearTimer = () => {
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = null;
  };

  useEffect(() => () => clearTimer(), []);

  const stopRecording = useCallback(async () => {
    if (stoppingRef.current) return;
    stoppingRef.current = true;
    clearTimer();
    setRecording(false);
    const uri = await handleRef.current?.stop();
    handleRef.current = null;
    stoppingRef.current = false;
    if (uri) await run(uri, 'audio', context);
  }, [run, context]);

  const onRecordPress = useCallback(async () => {
    if (recording) {
      await stopRecording();
      return;
    }
    if (!quota.canAnalyze) {
      nav.navigate('paywall');
      return;
    }
    const handle = await startRecording();
    if (!handle) return;

    handleRef.current = handle;
    stoppingRef.current = false;
    setSecondsLeft(RECORD_SECONDS);
    setRecording(true);

    // 3초가 지나면 자동으로 멈추고 바로 분석에 들어간다
    timerRef.current = setInterval(() => {
      setSecondsLeft((prev) => {
        if (prev <= 1) {
          void stopRecording();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  }, [recording, quota.canAnalyze, nav, stopRecording]);

  if (!pet) {
    return (
      <ScrollView contentContainerStyle={styles.page}>
        <Empty emoji="🐶" title="아직 등록한 아이가 없어요" desc="먼저 반려동물을 등록하면 분석을 시작할 수 있어요." />
        <Button label="반려동물 등록하기" onPress={() => nav.navigate('petForm')} />
      </ScrollView>
    );
  }

  const presets = CONTEXT_PRESETS[pet.type];

  return (
    <ScrollView contentContainerStyle={styles.page} keyboardShouldPersistTaps="handled">
      <View style={styles.header}>
        <View style={{ flex: 1 }}>
          <Text style={font.h1}>{pet.name}</Text>
          <Text style={[font.small, { color: colors.textSoft }]}>
            {PET_LABEL[pet.type]}
            {pet.breed ? ` · ${pet.breed}` : ''}
          </Text>
        </View>
        <Badge
          text={quota.label}
          bg={quota.isPro ? colors.proSoft : quota.canAnalyze ? colors.primarySoft : colors.dangerSoft}
          fg={quota.isPro ? colors.pro : quota.canAnalyze ? colors.primaryDark : colors.danger}
        />
      </View>

      {pets.length > 1 ? (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipRow}>
          {pets.map((p) => (
            <Chip key={p.id} label={p.name} selected={p.id === pet.id} onPress={() => setActivePet(p.id)} />
          ))}
        </ScrollView>
      ) : null}

      <Card style={{ alignItems: 'center', gap: space.md }}>
        <Text style={[font.h2, { textAlign: 'center' }]}>
          {recording ? '듣고 있어요…' : analyzing ? '분석하는 중이에요' : '지금 무슨 말을 하는 걸까요?'}
        </Text>
        <Text style={[font.small, { color: colors.textSoft, textAlign: 'center' }]}>
          {recording
            ? `${RECORD_SECONDS}초가 지나면 자동으로 분석해요`
            : '소리를 3초만 들려주면 감정을 읽어 드려요'}
        </Text>

        <PulseRecordButton
          recording={recording}
          disabled={analyzing}
          secondsLeft={secondsLeft}
          onPress={() => void onRecordPress()}
        />

        <Button
          label="📷 사진·행동으로 분석하기"
          variant="ghost"
          disabled={recording || analyzing}
          onPress={() => (quota.canAnalyze ? nav.navigate('capture') : nav.navigate('paywall'))}
          style={{ alignSelf: 'stretch' }}
        />
      </Card>

      <View>
        <SectionTitle right={context ? <Text style={[font.tiny, { color: colors.primaryDark }]}>선택됨</Text> : undefined}>
          지금 상황은요?
        </SectionTitle>
        <Text style={[font.small, { color: colors.textSoft, marginBottom: space.sm }]}>
          상황을 알려 주면 훨씬 정확해져요. (선택)
        </Text>
        <View style={styles.wrapChips}>
          {presets.map((preset) => (
            <Chip
              key={preset}
              label={preset}
              selected={context === preset}
              onPress={() => setContext((prev) => (prev === preset ? '' : preset))}
            />
          ))}
        </View>
      </View>

      <View>
        <SectionTitle
          right={
            entries.length > 0 ? (
              <Pressable onPress={() => nav.switchTab('history')} accessibilityRole="button">
                <Text style={[font.small, { color: colors.primaryDark }]}>전체 보기</Text>
              </Pressable>
            ) : undefined
          }
        >
          최근 기록
        </SectionTitle>
        {entries.length === 0 ? (
          <Card>
            <Text style={[font.small, { color: colors.textSoft }]}>
              아직 기록이 없어요. 첫 분석을 하면 여기에 쌓입니다.
            </Text>
          </Card>
        ) : (
          <View style={{ gap: space.sm }}>
            {entries.slice(0, 3).map((entry) => {
              const meta = emotionMeta(entry.result.primaryEmotion);
              return (
                <Pressable
                  key={entry.id}
                  accessibilityRole="button"
                  onPress={() => nav.navigate('result', { entryId: entry.id })}
                  style={styles.recentRow}
                >
                  <View style={[styles.recentDot, { backgroundColor: meta.color }]}>
                    <Text>{meta.emoji}</Text>
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={font.bodyStrong} numberOfLines={1}>
                      {entry.result.petVoiceMessage}
                    </Text>
                    <Text style={[font.tiny, { color: colors.textFaint }]}>
                      {relativeKo(entry.createdAt)} · {meta.label}
                      {entry.context ? ` · ${entry.context}` : ''}
                    </Text>
                  </View>
                  {entry.health.level === 'vet' ? <Text>🏥</Text> : null}
                </Pressable>
              );
            })}
          </View>
        )}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: space.lg, gap: space.xl, paddingBottom: space.xxl },
  header: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  chipRow: { gap: space.sm, paddingVertical: space.xs },
  wrapChips: { flexDirection: 'row', flexWrap: 'wrap', gap: space.sm },
  recentRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.md,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: space.md,
  },
  recentDot: { width: 38, height: 38, borderRadius: 19, alignItems: 'center', justifyContent: 'center' },
});
