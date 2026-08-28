import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { relativeTime } from '../../core/date';
import { CONTEXT_PRESETS, PET_LABEL_KEY, emotionMeta, type ContextPreset } from '../../core/emotions';
import { useT } from '../../i18n/useT';
import { useActivePet, useEntriesForActivePet, usePetStore, useQuota } from '../../store/usePetStore';
import { Badge, Button, Card, Chip, Empty, SectionTitle } from '../components/Basics';
import { PulseRecordButton } from '../components/PulseRecordButton';
import { RECORD_SECONDS, startRecording, type RecordingHandle } from '../media';
import { useNavigation } from '../navigation';
import { font, radius, space } from '../theme';
import { useStyles, useTheme, type Theme } from '../useTheme';
import { EMPTY_CONTEXT, useAnalyzeMedia, useQueueDrain, type AnalysisContext } from '../useAnalyze';

export function HomeScreen() {
  const nav = useNavigation();
  const styles = useStyles(makeStyles);
  const { colors } = useTheme();
  const tr = useT();
  const { t } = tr;

  const pet = useActivePet();
  const pets = usePetStore((s) => s.pets);
  const setActivePet = usePetStore((s) => s.setActivePet);
  const entries = useEntriesForActivePet();
  const quota = useQuota();

  const [context, setContext] = useState<AnalysisContext>(EMPTY_CONTEXT);
  const [recording, setRecording] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState(RECORD_SECONDS);
  const { analyzing, run } = useAnalyzeMedia();
  const queue = useQueueDrain();

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
    const result = await handleRef.current?.stop();
    handleRef.current = null;
    stoppingRef.current = false;
    if (result?.uri) await run(result.uri, 'audio', context, result.levels);
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
    const handle = await startRecording(tr);
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
  }, [recording, quota.canAnalyze, nav, stopRecording, tr]);

  const toggleContext = (preset: ContextPreset) => {
    setContext((prev) =>
      prev.key === preset.key ? EMPTY_CONTEXT : { text: t(preset.key), key: preset.key, tags: preset.tags },
    );
  };

  if (!pet) {
    return (
      <ScrollView contentContainerStyle={styles.page}>
        <Empty emoji="🐶" title={t('home.emptyTitle')} desc={t('home.emptyDesc')} />
        <Button label={t('home.registerCta')} onPress={() => nav.navigate('petForm')} />
      </ScrollView>
    );
  }

  const presets = CONTEXT_PRESETS[pet.type];

  return (
    <ScrollView contentContainerStyle={styles.page} keyboardShouldPersistTaps="handled">
      <View style={styles.header}>
        <View style={{ flex: 1 }}>
          <Text accessibilityRole="header" style={[font.h1, { color: colors.text }]}>
            {pet.name}
          </Text>
          <Text style={[font.small, { color: colors.textSoft }]}>
            {t(PET_LABEL_KEY[pet.type])}
            {pet.breed ? ` · ${pet.breed}` : ''}
          </Text>
        </View>
        <Badge
          text={tr.m(quota.label)}
          bg={quota.isPro ? colors.proSoft : quota.canAnalyze ? colors.primarySoft : colors.dangerSoft}
          fg={quota.isPro ? colors.proText : quota.canAnalyze ? colors.primaryText : colors.danger}
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
        <Text accessibilityRole="header" style={[font.h2, { color: colors.text, textAlign: 'center' }]}>
          {t(recording ? 'home.listening' : analyzing ? 'home.analyzing' : 'home.prompt')}
        </Text>
        <Text style={[font.small, { color: colors.textSoft, textAlign: 'center' }]}>
          {t(recording ? 'home.recordingSub' : 'home.promptSub', { seconds: RECORD_SECONDS })}
        </Text>

        <PulseRecordButton
          recording={recording}
          disabled={analyzing}
          secondsLeft={secondsLeft}
          idleLabel={t('home.recordLabel', { seconds: RECORD_SECONDS })}
          a11yLabel={recording ? t('home.stopA11y') : t('home.recordA11y', { seconds: RECORD_SECONDS })}
          onPress={() => void onRecordPress()}
        />

        <Button
          label={t('home.photoCta')}
          variant="ghost"
          disabled={recording || analyzing}
          onPress={() => (quota.canAnalyze ? nav.navigate('capture') : nav.navigate('paywall'))}
          style={{ alignSelf: 'stretch' }}
        />
      </Card>

      {queue.pending > 0 ? (
        <Card style={{ gap: space.sm, backgroundColor: colors.warnSoft, borderColor: colors.warnLine }}>
          <Text style={[font.bodyStrong, { color: colors.text }]}>{t('home.queuedCount', { count: queue.pending })}</Text>
          <Text style={[font.small, { color: colors.textSoft }]}>{t('home.queued')}</Text>
          <Button label={t('home.retryQueue')} variant="ghost" loading={queue.draining} onPress={() => void queue.drain()} />
        </Card>
      ) : null}

      <View>
        <SectionTitle
          right={
            context.key ? <Text style={[font.tiny, { color: colors.primaryText }]}>{t('home.contextSelected')}</Text> : undefined
          }
        >
          {t('home.contextTitle')}
        </SectionTitle>
        <Text style={[font.small, { color: colors.textSoft, marginBottom: space.sm }]}>{t('home.contextSub')}</Text>
        <View style={styles.wrapChips}>
          {presets.map((preset) => (
            <Chip
              key={preset.key}
              label={t(preset.key)}
              selected={context.key === preset.key}
              onPress={() => toggleContext(preset)}
            />
          ))}
        </View>
      </View>

      <View>
        <SectionTitle
          right={
            entries.length > 0 ? (
              <Pressable
                onPress={() => nav.switchTab('history')}
                accessibilityRole="button"
                accessibilityLabel={t('home.seeAll')}
                hitSlop={8}
              >
                <Text style={[font.small, { color: colors.primaryText }]}>{t('home.seeAll')}</Text>
              </Pressable>
            ) : undefined
          }
        >
          {t('home.recentTitle')}
        </SectionTitle>
        {entries.length === 0 ? (
          <Card>
            <Text style={[font.small, { color: colors.textSoft }]}>{t('home.recentEmpty')}</Text>
          </Card>
        ) : (
          <View style={{ gap: space.sm }}>
            {entries.slice(0, 3).map((entry) => {
              const meta = emotionMeta(entry.result.primaryEmotion);
              return (
                <Pressable
                  key={entry.id}
                  accessibilityRole="button"
                  accessibilityLabel={`${entry.result.petVoiceMessage}, ${t(meta.labelKey)}`}
                  onPress={() => nav.navigate('result', { entryId: entry.id })}
                  style={styles.recentRow}
                >
                  <View style={[styles.recentDot, { backgroundColor: meta.color }]}>
                    <Text>{meta.emoji}</Text>
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={[font.bodyStrong, { color: colors.text }]} numberOfLines={1}>
                      {entry.result.petVoiceMessage}
                    </Text>
                    <Text style={[font.tiny, { color: colors.textFaint }]}>
                      {tr.relative(relativeTime(entry.createdAt))} · {t(meta.labelKey)}
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

const makeStyles = ({ colors }: Theme) =>
  StyleSheet.create({
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
