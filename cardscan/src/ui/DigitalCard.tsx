// 디지털 명함 — 회사 색 그라데이션의 프리미엄 카드. 누르면 3D 로 뒤집혀 원본 명함 사진을 보여 준다.
import { LinearGradient } from 'expo-linear-gradient';
import { t } from '../i18n';
import { useRef, useState } from 'react';
import { Animated, Modal, Pressable, StyleSheet, Text, View } from 'react-native';
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
      <Pressable onPress={turn} accessibilityLabel={photos.length ? t('눌러서 명함 사진 보기') : undefined}>
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
                  {card.name || card.nameEn || t('이름 없음')}
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
                  <Text style={st.flipText}>{t('명함 사진')}</Text>
                </View>
              ) : null}
            </LinearGradient>
          ) : (
            <View style={[st.card, { padding: 0, backgroundColor: '#000' }]}>
              <CardImage uri={photos[side - 1]} style={StyleSheet.absoluteFill as object} contain />
              <View style={[st.flipHint, { backgroundColor: 'rgba(0,0,0,0.45)', borderRadius: 10, paddingHorizontal: 8 }]}>
                <Text style={st.flipText}>{side === 1 ? t('앞면 · 눌러서 넘기기') : t('뒷면 · 눌러서 넘기기')}</Text>
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
  photoWrap: { aspectRatio: 1.62, borderRadius: RADIUS.lg, backgroundColor: '#E9EBF1', overflow: 'hidden' },
  photoBar: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 8, paddingHorizontal: 4 },
  photoHint: { fontFamily: FONT, fontSize: 12, fontWeight: '600', color: T.sub },
  zoomBtn: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  photoPill: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: 'rgba(0,0,0,0.5)', borderRadius: 10, paddingHorizontal: 8, paddingVertical: 4 },
  photoPillText: { fontFamily: FONT, fontSize: 11, fontWeight: '700', color: '#fff' },
  pinned: { height: 150, backgroundColor: '#1A1F2E', padding: 8 },
  zoomBg: { flex: 1, backgroundColor: 'rgba(0,0,0,0.94)', alignItems: 'center', justifyContent: 'center', padding: 12 },
  zoomImg: { width: '100%', height: '80%' },
  zoomHint: { fontFamily: FONT, fontSize: 12, color: 'rgba(255,255,255,0.6)', marginTop: 12 },
});

/**
 * 명함 보기 — 실제 명함 사진이 있으면 원본을 그대로 보여 준다 (명함 디자인만 봐도 어느 회사인지 알 수 있으므로 꾸미지 않는다).
 * 사진이 없을 때(직접 입력·내 명함)만 디지털 명함으로 대신한다.
 */
export function CardHero(props: Props) {
  if (!props.imageUri) return <DigitalCard {...props} />;
  return <PhotoCard {...props} />;
}

function PhotoCard({ imageUri, backImageUri, caption }: Props) {
  const photos = [imageUri, backImageUri].filter(Boolean) as string[];
  const [side, setSide] = useState(0);
  const [zoom, setZoom] = useState(false);
  const flip = useRef(new Animated.Value(0)).current;
  const rotateY = flip.interpolate({ inputRange: [-0.5, 0, 0.5], outputRange: ['-90deg', '0deg', '90deg'] });

  function turn() {
    if (photos.length < 2) return setZoom(true);
    tap();
    Animated.timing(flip, { toValue: 0.5, duration: 150, useNativeDriver: true }).start(() => {
      setSide((v) => (v + 1) % photos.length);
      flip.setValue(-0.5);
      Animated.timing(flip, { toValue: 0, duration: 170, useNativeDriver: true }).start();
    });
  }

  return (
    <View>
      <Pressable onPress={turn} onLongPress={() => setZoom(true)} accessibilityLabel={photos.length > 1 ? t('눌러서 앞·뒷면 넘기기') : t('눌러서 크게 보기')}>
        <Animated.View style={[st.photoWrap, shadow(2), { transform: [{ perspective: 1000 }, { rotateY }] }]}>
          <CardImage uri={photos[side]} style={StyleSheet.absoluteFill as object} contain />
        </Animated.View>
      </Pressable>
      {/* 안내는 사진 밖에 — 명함 글자를 가리지 않게 */}
      <View style={st.photoBar}>
        <Text style={st.photoHint}>
          {photos.length > 1 ? side === 0 ? t('원본 앞면 · 눌러서 뒷면') : t('원본 뒷면 · 눌러서 앞면') : t('원본 명함')}
        </Text>
        <Pressable hitSlop={10} onPress={() => setZoom(true)} style={st.zoomBtn} accessibilityLabel={t('크게 보기')}>
          <Icon name="expand" size={12} color={T.sub} />
          <Text style={st.photoHint}>{t('크게 보기')}</Text>
        </Pressable>
      </View>
      {caption ? <Text style={st.caption}>{caption}</Text> : null}
      <Modal visible={zoom} transparent animationType="fade" onRequestClose={() => setZoom(false)} statusBarTranslucent>
        <Pressable style={st.zoomBg} onPress={() => setZoom(false)}>
          <CardImage uri={photos[side]} style={st.zoomImg} contain />
          <Text style={st.zoomHint}>{photos.length > 1 ? t('아무 곳이나 누르면 닫힙니다 · 카드를 누르면 앞·뒷면') : t('아무 곳이나 누르면 닫힙니다')}</Text>
        </Pressable>
      </Modal>
    </View>
  );
}

/** 수정·확인 화면 위에 고정되는 원본 명함 — 보면서 고칠 수 있게. 누르면 앞·뒷면 */
export function PinnedPhoto({ imageUri, backImageUri }: { imageUri?: string; backImageUri?: string }) {
  const [back, setBack] = useState(false);
  if (!imageUri) return null;
  return (
    <Pressable onPress={() => backImageUri && setBack((v) => !v)} style={st.pinned} accessibilityLabel={t('원본 명함')}>
      <CardImage uri={back && backImageUri ? backImageUri : imageUri} style={{ width: '100%', height: '100%' }} contain />
      <View style={[st.photoPill, { position: 'absolute', right: 10, bottom: 8 }]}>
        <Icon name="image" size={11} color="#fff" />
        <Text style={st.photoPillText}>{backImageUri ? (back ? t('원본 · 뒷면') : t('원본 · 앞면 (눌러서 뒷면)')) : t('원본')}</Text>
      </View>
    </Pressable>
  );
}
