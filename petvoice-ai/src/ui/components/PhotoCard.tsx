import React, { forwardRef } from 'react';
import { Image, StyleSheet, Text, View } from 'react-native';
import { layoutPhotoCard } from '../../core/photocard';
import type { EmotionKey } from '../../core/types';
import { useT } from '../../i18n/useT';
import { font, radius, space } from '../theme';

/**
 * 포토카드는 **밖으로 나가는 이미지**라 앱 테마를 따르지 않는다.
 * 보내는 사람이 다크 모드든 아니든 받는 사람에게 같은 카드로 보여야 한다.
 */
const CARD_BG = '#FFF2E6';
const CARD_PLACEHOLDER_BG = '#FFE7D3';
const CARD_WATERMARK_DARK = 'rgba(60,40,24,0.55)';

interface Props {
  width: number;
  photoUri?: string;
  message: string;
  emotion: EmotionKey;
  themeKey: string;
  isPro: boolean;
  petName?: string;
}

/**
 * SNS 공유용 포토카드.
 * 좌표 계산은 전부 `core/photocard.ts` 가 하고, 여기서는 그리기만 한다.
 * 부모가 `react-native-view-shot` 의 captureRef 로 이 View 를 그대로 캡처한다.
 */
export const PhotoCard = forwardRef<View, Props>(function PhotoCard(
  { width, photoUri, message, emotion, themeKey, isPro, petName },
  ref,
) {
  const { t } = useT();
  const layout = layoutPhotoCard({ width, message, emotion, themeKey, isPro, petName });
  const { theme, bubble, tail, badge } = layout;
  const hasPhoto = Boolean(photoUri);

  return (
    <View ref={ref} collapsable={false} style={[styles.card, { width: layout.width, height: layout.height }]}>
      {hasPhoto ? (
        <>
          <Image source={{ uri: photoUri }} style={StyleSheet.absoluteFill} resizeMode="cover" />
          {/* 사진 위 글자 가독성용 스크림. 사진이 없으면 배경만 탁해지므로 걸지 않는다. */}
          <View style={[StyleSheet.absoluteFill, { backgroundColor: `rgba(0,0,0,${theme.scrim})` }]} />
        </>
      ) : (
        <View style={[StyleSheet.absoluteFill, styles.placeholder]}>
          <Text style={{ fontSize: 64 }}>🐾</Text>
        </View>
      )}

      <View style={[styles.badge, { left: badge.x, top: badge.y, backgroundColor: badge.color }]}>
        <Text style={[font.tiny, { color: '#FFFFFF' }]}>
          {badge.emoji} {t(badge.labelKey)}
        </Text>
      </View>

      <View
        style={[
          styles.bubble,
          {
            left: bubble.x,
            top: bubble.y,
            width: bubble.width,
            height: bubble.height,
            borderRadius: bubble.radius,
            backgroundColor: theme.bubbleBg,
            borderColor: theme.shape === 'sharp' ? theme.accent : 'transparent',
            borderWidth: theme.shape === 'sharp' ? 2 : 0,
          },
        ]}
      >
        {layout.lines.map((line, index) => (
          <Text
            key={`${line}-${index}`}
            style={{
              fontSize: layout.fontSize,
              lineHeight: layout.lineHeight,
              color: theme.bubbleText,
              fontWeight: '700',
            }}
          >
            {line}
          </Text>
        ))}
      </View>

      {/* 말풍선 꼬리 */}
      <View
        style={[
          styles.tail,
          {
            left: tail.x,
            top: tail.y - 1,
            borderLeftWidth: tail.size,
            borderRightWidth: tail.size,
            borderTopWidth: tail.size,
            borderTopColor: theme.bubbleBg,
          },
        ]}
      />

      <Text
        style={[
          font.tiny,
          styles.watermark,
          {
            left: layout.watermark.x,
            top: layout.watermark.y,
            color: hasPhoto ? 'rgba(255,255,255,0.8)' : CARD_WATERMARK_DARK,
          },
        ]}
      >
        {layout.watermark.text}
      </Text>
    </View>
  );
});

const styles = StyleSheet.create({
  card: { borderRadius: radius.lg, overflow: 'hidden', backgroundColor: CARD_BG },
  placeholder: { alignItems: 'center', justifyContent: 'center', backgroundColor: CARD_PLACEHOLDER_BG },
  badge: { position: 'absolute', paddingHorizontal: space.md, paddingVertical: 5, borderRadius: radius.pill },
  bubble: { position: 'absolute', paddingHorizontal: 14, paddingVertical: 12, justifyContent: 'center' },
  tail: {
    position: 'absolute',
    width: 0,
    height: 0,
    backgroundColor: 'transparent',
    borderLeftColor: 'transparent',
    borderRightColor: 'transparent',
  },
  watermark: { position: 'absolute' },
});
