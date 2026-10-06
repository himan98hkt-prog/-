// 디지털 명함 — 회사 색 그라데이션의 프리미엄 카드. 누르면 3D 로 뒤집혀 원본 명함 사진을 보여 준다.
import { LinearGradient } from 'expo-linear-gradient';
import { useRef, useState } from 'react';
import { Animated, Pressable, StyleSheet, Text, View } from 'react-native';
import { companyShort } from '../core/mapping';
import { CardFields } from '../core/types';
import { CardImage } from './CardImage';
import { Icon, tap } from './components';
import { FONT, gradientFor, monogram, RADIUS, shadow, T } from './theme';

type Props = {
  card: Pick<CardFields, 'name' | 'nameEn' | 'company' | 'department' | 'title' | 'mobile' | 'phone' | 'email'>;
  imageUri?: string;
  backImageUri?: string;
  favorite?: boolean;
  /** 아래 작은 안내 문구 */
  caption?: string;
};

export function DigitalCard({ card, imageUri, backImageUri, favorite, caption }: Props) {
  const [a, b] = gradientFor(card.company || card.name);
  const flip = useRef(new Animated.Value(0)).current;
  const [side, setSide] = useState<0 | 1 | 2>(0); // 0 디지털, 1 앞면 사진, 2 뒷면 사진
  const photos = [imageUri, backImageUri].filter(Boolean) as string[];

  function turn() {
    if (!photos.length) return;
    tap();
    const next = ((side + 1) % (photos.length + 1)) as 0 | 1 | 2;
    Animated.timing(flip, { toValue: 0.5, duration: 160, useNativeDriver: true }).start(() => {
      setSide(next);
      flip.setValue(-0.5);
      Animated.timing(flip, { toValue: 0, duration: 180, useNativeDriver: true }).start();
    });
  }

  const rotateY = flip.interpolate({ inputRange: [-0.5, 0, 0.5], outputRange: ['-90deg', '0deg', '90deg'] });
  const org = companyShort(card.company);

  return (
    <View>
      <Pressable onPress={turn} accessibilityLabel={photos.length ? '눌러서 명함 사진 보기' : undefined}>
        <Animated.View style={[st.wrap, shadow(3), { transform: [{ perspective: 1000 }, { rotateY }] }]}>
          {side === 0 ? (
            <LinearGradient colors={[a, b]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={st.card}>
              {/* 은은한 광택 */}
              <LinearGradient colors={['rgba(255,255,255,0.18)', 'rgba(255,255,255,0)']} start={{ x: 0, y: 0 }} end={{ x: 0.6, y: 0.6 }} style={StyleSheet.absoluteFill} />
              <View style={st.ringA} />
              <View style={st.ringB} />
              <View style={st.top}>
                <Text style={st.company} numberOfLines={1}>
                  {org || ' '}
                </Text>
                {favorite ? (
                  <View style={st.goldPill}>
                    <Icon name="star" size={11} color={T.ink} />
                    <Text style={st.goldText}>VIP</Text>
                  </View>
                ) : (
                  <Text style={st.mono}>{monogram(card.name, card.company)}</Text>
                )}
              </View>
              <View>
                <Text style={st.name} numberOfLines={1}>
                  {card.name || card.nameEn || '이름 없음'}
                </Text>
                <Text style={st.title} numberOfLines={1}>
                  {[card.department, card.title].filter(Boolean).join(' · ') || card.nameEn || ' '}
                </Text>
                <View style={st.goldLine} />
                <Text style={st.contact} numberOfLines={1}>
                  {card.mobile || card.phone || ' '}
                </Text>
                <Text style={st.contact} numberOfLines={1}>
                  {card.email || ' '}
                </Text>
              </View>
              {photos.length ? (
                <View style={st.flipHint}>
                  <Icon name="sync" size={12} color="rgba(255,255,255,0.75)" />
                  <Text style={st.flipText}>명함 사진</Text>
                </View>
              ) : null}
            </LinearGradient>
          ) : (
            <View style={[st.card, { padding: 0, backgroundColor: '#000' }]}>
              <CardImage uri={photos[side - 1]} style={StyleSheet.absoluteFill as object} contain />
              <View style={[st.flipHint, { backgroundColor: 'rgba(0,0,0,0.45)', borderRadius: 10, paddingHorizontal: 8 }]}>
                <Text style={st.flipText}>{side === 1 ? '앞면' : '뒷면'} · 눌러서 넘기기</Text>
              </View>
            </View>
          )}
        </Animated.View>
      </Pressable>
      {caption ? <Text style={st.caption}>{caption}</Text> : null}
    </View>
  );
}

const st = StyleSheet.create({
  wrap: { borderRadius: RADIUS.xl, backgroundColor: T.ink },
  card: { aspectRatio: 1.62, borderRadius: RADIUS.xl, padding: 22, justifyContent: 'space-between', overflow: 'hidden' },
  ringA: { position: 'absolute', width: 260, height: 260, borderRadius: 130, borderWidth: 1, borderColor: 'rgba(255,255,255,0.10)', right: -90, top: -110 },
  ringB: { position: 'absolute', width: 180, height: 180, borderRadius: 90, borderWidth: 1, borderColor: 'rgba(212,175,106,0.35)', right: -40, top: -60 },
  top: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  company: { fontFamily: FONT, fontSize: 14, fontWeight: '700', color: 'rgba(255,255,255,0.85)', letterSpacing: 0.5, flex: 1, marginRight: 12 },
  mono: { fontFamily: FONT, fontSize: 18, fontWeight: '800', color: 'rgba(255,255,255,0.35)' },
  goldPill: { flexDirection: 'row', alignItems: 'center', gap: 3, backgroundColor: T.gold, borderRadius: 10, paddingHorizontal: 8, paddingVertical: 3 },
  goldText: { fontFamily: FONT, fontSize: 11, fontWeight: '800', color: T.ink, letterSpacing: 1 },
  name: { fontFamily: FONT, fontSize: 30, fontWeight: '800', color: '#fff', letterSpacing: -0.5 },
  title: { fontFamily: FONT, fontSize: 14, fontWeight: '600', color: 'rgba(255,255,255,0.8)', marginTop: 2 },
  goldLine: { width: 28, height: 2, backgroundColor: T.gold, borderRadius: 1, marginVertical: 12 },
  contact: { fontFamily: FONT, fontSize: 13, fontWeight: '600', color: 'rgba(255,255,255,0.9)', letterSpacing: 0.3 },
  flipHint: { position: 'absolute', right: 16, bottom: 14, flexDirection: 'row', alignItems: 'center', gap: 4 },
  flipText: { fontFamily: FONT, fontSize: 11, fontWeight: '600', color: 'rgba(255,255,255,0.75)' },
  caption: { fontFamily: FONT, fontSize: 12, color: T.sub, textAlign: 'center', marginTop: 10 },
});
