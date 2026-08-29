import * as Sharing from 'expo-sharing';
import React, { useRef, useState } from 'react';
import { Alert, ScrollView, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { captureRef } from 'react-native-view-shot';
import { sendFeedback } from '../../api/feedback';
import { emotionMeta } from '../../core/emotions';
import { themesFor } from '../../core/photocard';
import { useT } from '../../i18n/useT';
import { usePetStore, useIsPro } from '../../store/usePetStore';
import { Badge, Button, Card, Chip, Empty, SectionTitle } from '../components/Basics';
import { EmotionBars } from '../components/EmotionBars';
import { HealthNotice } from '../components/HealthNotice';
import { PhotoCard } from '../components/PhotoCard';
import { Waveform } from '../components/Waveform';
import { LINKS } from '../links';
import { useAudioPlayback } from '../media';
import { useNavigation } from '../navigation';
import { font, space } from '../theme';
import { useStyles, useTheme, type Theme } from '../useTheme';

/** 분석 결과 + 인스타 공유용 포토카드 */
export function ResultScreen() {
  const nav = useNavigation();
  const styles = useStyles(makeStyles);
  const { colors } = useTheme();
  const tr = useT();
  const { t } = tr;
  const isPro = useIsPro();
  const { width } = useWindowDimensions();

  const entryId = nav.current.params?.entryId as string | undefined;
  const entry = usePetStore((s) => s.entries.find((e) => e.id === entryId));
  const pet = usePetStore((s) => s.pets.find((p) => p.id === entry?.petId));
  const cardThemeKey = usePetStore((s) => s.cardThemeKey);
  const setCardTheme = usePetStore((s) => s.setCardTheme);
  const removeEntry = usePetStore((s) => s.removeEntry);
  const setEntryFeedback = usePetStore((s) => s.setEntryFeedback);

  const submitFeedback = (verdict: 'up' | 'down') => {
    if (!entry) return;
    setEntryFeedback(entry.id, verdict);
    void sendFeedback(entry, verdict, tr.locale);
  };

  const cardRef = useRef<View>(null);
  const [sharing, setSharing] = useState(false);
  const playback = useAudioPlayback(entry?.audioUri);

  if (!entry) {
    return (
      <ScrollView contentContainerStyle={styles.page}>
        <Empty emoji="🔍" title={t('result.notFound')} />
        <Button label={t('result.goBack')} onPress={nav.back} />
      </ScrollView>
    );
  }

  const meta = emotionMeta(entry.result.primaryEmotion);
  const cardWidth = Math.min(width - space.lg * 2, 380);

  const share = async () => {
    setSharing(true);
    try {
      if (!(await Sharing.isAvailableAsync())) {
        Alert.alert(t('result.shareUnavailable'), t('result.shareUnavailableDesc'));
        return;
      }
      const uri = await captureRef(cardRef, { format: 'png', quality: 1, result: 'tmpfile' });
      await Sharing.shareAsync(uri, {
        mimeType: 'image/png',
        dialogTitle: t('result.shareText', { name: pet?.name ?? '', link: LINKS.share }),
      });
    } catch {
      Alert.alert(t('result.shareFailed'), t('result.shareFailedDesc'));
    } finally {
      setSharing(false);
    }
  };

  const confirmDelete = () => {
    Alert.alert(t('result.deleteTitle'), t('result.deleteDesc'), [
      { text: t('common.cancel'), style: 'cancel' },
      {
        text: t('common.delete'),
        style: 'destructive',
        onPress: () => {
          removeEntry(entry.id);
          nav.back();
        },
      },
    ]);
  };

  const mediaLabel =
    entry.shotCount && entry.shotCount > 1
      ? t('result.mediaPrecise', { count: entry.shotCount })
      : t(entry.mediaKind === 'audio' ? 'result.mediaAudio' : 'result.mediaImage');

  return (
    <ScrollView contentContainerStyle={styles.page}>
      <View>
        <Text accessibilityRole="header" style={[font.h1, { color: colors.text }]}>
          {meta.emoji} {t(meta.labelKey)}
        </Text>
        <Text style={[font.small, { color: colors.textSoft }]}>
          {tr.dateTime(entry.createdAt)} · {mediaLabel}
          {entry.context ? ` · ${entry.context}` : ''}
        </Text>
      </View>

      <View style={{ alignItems: 'center' }}>
        <PhotoCard
          ref={cardRef}
          width={cardWidth}
          photoUri={entry.mediaUri ?? pet?.photoUri}
          message={entry.result.petVoiceMessage}
          emotion={entry.result.primaryEmotion}
          themeKey={cardThemeKey}
          isPro={isPro}
          petName={pet?.name}
        />
      </View>

      <Button
        label={sharing ? t('result.sharing') : t('result.share')}
        loading={sharing}
        onPress={() => void share()}
      />

      {entry.audioUri ? (
        <Card style={{ gap: space.sm }}>
          <Waveform levels={entry.levels ?? []} active={playback.playing} />
          <Button
            label={t(playback.playing ? 'result.stopRecording' : 'result.playRecording')}
            variant="ghost"
            onPress={() => void playback.toggle()}
          />
        </Card>
      ) : null}

      <View>
        <SectionTitle
          right={
            isPro ? undefined : (
              <Badge text={t('result.themePartlyLocked')} bg={colors.proSoft} fg={colors.proText} />
            )
          }
        >
          {t('result.themeTitle')}
        </SectionTitle>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={{ gap: space.sm }}
        >
          {themesFor(isPro).map(({ theme, locked }) => (
            <Chip
              key={theme.key}
              label={t(theme.nameKey)}
              locked={locked}
              selected={theme.key === cardThemeKey && !locked}
              onPress={() => (locked ? nav.navigate('paywall') : setCardTheme(theme.key))}
            />
          ))}
        </ScrollView>
      </View>

      <Card style={{ gap: space.lg }}>
        <SectionTitle>{t('result.emotionTitle')}</SectionTitle>
        <EmotionBars scores={entry.result.emotionScores} />
      </Card>

      <Card style={{ gap: space.sm }}>
        <SectionTitle>{t('result.whyTitle')}</SectionTitle>
        <Text style={[font.body, { color: colors.text }]}>{entry.result.behaviorAnalysis}</Text>
      </Card>

      <Card style={{ gap: space.sm, backgroundColor: colors.surfaceAlt }}>
        <SectionTitle>{t('result.actionTitle')}</SectionTitle>
        <Text style={[font.body, { color: colors.text }]}>{entry.result.actionGuide}</Text>
      </Card>

      <HealthNotice health={entry.health} />

      {/* 정확도 피드백 — 쌓이면 프롬프트를 고칠 근거가 된다 */}
      <Card style={{ gap: space.md }}>
        <SectionTitle>{t('result.feedbackTitle')}</SectionTitle>
        {entry.feedback ? (
          <Text style={[font.small, { color: colors.textSoft }]}>{t('result.feedbackThanks')}</Text>
        ) : (
          <View style={{ flexDirection: 'row', gap: space.sm }}>
            <Button
              label={`👍 ${t('result.feedbackYes')}`}
              variant="ghost"
              onPress={() => submitFeedback('up')}
              style={{ flex: 1 }}
            />
            <Button
              label={`👎 ${t('result.feedbackNo')}`}
              variant="ghost"
              onPress={() => submitFeedback('down')}
              style={{ flex: 1 }}
            />
          </View>
        )}
      </Card>

      {!isPro ? (
        <Card style={{ gap: space.sm, backgroundColor: colors.proSoft, borderColor: colors.proSoft }}>
          <Text style={[font.bodyStrong, { color: colors.text }]}>{t('result.proTeaser')}</Text>
          <Button label={t('result.proTeaserCta')} variant="pro" onPress={() => nav.navigate('paywall')} />
        </Card>
      ) : null}

      <View style={{ gap: space.sm }}>
        <Button label={t('result.again')} variant="ghost" onPress={() => nav.switchTab('home')} />
        <Button label={t('result.deleteEntry')} variant="danger" onPress={confirmDelete} />
      </View>
    </ScrollView>
  );
}

const makeStyles = (_theme: Theme) =>
  StyleSheet.create({
    page: { padding: space.lg, gap: space.lg, paddingBottom: space.xxl },
  });
