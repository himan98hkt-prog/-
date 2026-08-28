import * as Sharing from 'expo-sharing';
import React, { useRef, useState } from 'react';
import { Alert, ScrollView, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { captureRef } from 'react-native-view-shot';
import { formatKo } from '../../core/date';
import { emotionMeta } from '../../core/emotions';
import { themesFor } from '../../core/photocard';
import { usePetStore, useIsPro } from '../../store/usePetStore';
import { Badge, Button, Card, Chip, Empty, SectionTitle } from '../components/Basics';
import { EmotionBars } from '../components/EmotionBars';
import { HealthNotice } from '../components/HealthNotice';
import { PhotoCard } from '../components/PhotoCard';
import { useNavigation } from '../navigation';
import { colors, font, space } from '../theme';

/** 분석 결과 + 인스타 공유용 포토카드 */
export function ResultScreen() {
  const nav = useNavigation();
  const isPro = useIsPro();
  const { width } = useWindowDimensions();

  const entryId = nav.current.params?.entryId as string | undefined;
  const entry = usePetStore((s) => s.entries.find((e) => e.id === entryId));
  const pet = usePetStore((s) => s.pets.find((p) => p.id === entry?.petId));
  const cardThemeKey = usePetStore((s) => s.cardThemeKey);
  const setCardTheme = usePetStore((s) => s.setCardTheme);
  const removeEntry = usePetStore((s) => s.removeEntry);

  const cardRef = useRef<View>(null);
  const [sharing, setSharing] = useState(false);

  if (!entry) {
    return (
      <ScrollView contentContainerStyle={styles.page}>
        <Empty emoji="🔍" title="기록을 찾을 수 없어요" />
        <Button label="돌아가기" onPress={nav.back} />
      </ScrollView>
    );
  }

  const meta = emotionMeta(entry.result.primaryEmotion);
  const cardWidth = Math.min(width - space.lg * 2, 380);

  const share = async () => {
    setSharing(true);
    try {
      if (!(await Sharing.isAvailableAsync())) {
        Alert.alert('공유할 수 없어요', '이 기기에서는 공유 기능을 쓸 수 없습니다.');
        return;
      }
      const uri = await captureRef(cardRef, { format: 'png', quality: 1, result: 'tmpfile' });
      await Sharing.shareAsync(uri, { mimeType: 'image/png', dialogTitle: '포토카드 공유' });
    } catch {
      Alert.alert('공유에 실패했어요', '잠시 후 다시 시도해 주세요.');
    } finally {
      setSharing(false);
    }
  };

  const confirmDelete = () => {
    Alert.alert('이 기록을 삭제할까요?', '삭제하면 되돌릴 수 없어요.', [
      { text: '취소', style: 'cancel' },
      {
        text: '삭제',
        style: 'destructive',
        onPress: () => {
          removeEntry(entry.id);
          nav.back();
        },
      },
    ]);
  };

  return (
    <ScrollView contentContainerStyle={styles.page}>
      <View>
        <Text style={font.h1}>
          {meta.emoji} {meta.label}
        </Text>
        <Text style={[font.small, { color: colors.textSoft }]}>
          {formatKo(entry.createdAt)} · {entry.mediaKind === 'audio' ? '소리 분석' : '행동 분석'}
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

      <Button label={sharing ? '카드 만드는 중…' : '📤 포토카드 공유하기'} loading={sharing} onPress={() => void share()} />

      <View>
        <SectionTitle right={isPro ? undefined : <Badge text="일부 잠김" bg={colors.proSoft} fg={colors.pro} />}>
          말풍선 테마
        </SectionTitle>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: space.sm }}>
          {themesFor(isPro).map(({ theme, locked }) => (
            <Chip
              key={theme.key}
              label={theme.name}
              locked={locked}
              selected={theme.key === cardThemeKey && !locked}
              onPress={() => (locked ? nav.navigate('paywall') : setCardTheme(theme.key))}
            />
          ))}
        </ScrollView>
      </View>

      <Card style={{ gap: space.lg }}>
        <SectionTitle>감정 분석</SectionTitle>
        <EmotionBars scores={entry.result.emotionScores} />
      </Card>

      <Card style={{ gap: space.sm }}>
        <SectionTitle>왜 이렇게 판단했나요</SectionTitle>
        <Text style={font.body}>{entry.result.behaviorAnalysis}</Text>
      </Card>

      <Card style={{ gap: space.sm, backgroundColor: colors.surfaceAlt }}>
        <SectionTitle>지금 이렇게 해 주세요</SectionTitle>
        <Text style={font.body}>{entry.result.actionGuide}</Text>
      </Card>

      <HealthNotice health={entry.health} />

      <View style={{ gap: space.sm }}>
        <Button label="한 번 더 분석하기" variant="ghost" onPress={() => nav.switchTab('home')} />
        <Button label="이 기록 삭제" variant="danger" onPress={confirmDelete} />
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { padding: space.lg, gap: space.lg, paddingBottom: space.xxl },
});
