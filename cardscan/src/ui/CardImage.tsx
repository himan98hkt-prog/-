import { Image, ImageStyle, StyleProp, View } from 'react-native';
import { useImageUri } from '../storage/images';
import { Avatar } from './components';
import { T } from './theme';

/** 명함 사진 — 앱은 파일, 웹은 IndexedDB 에 있어 주소를 풀어서 보여준다 */
export function CardImage({ uri, style, contain, thumb }: { uri?: string; style: StyleProp<ImageStyle>; contain?: boolean; thumb?: boolean }) {
  const resolved = useImageUri(uri);
  if (!resolved) return <View style={[style as object, { backgroundColor: T.line }]} />;
  // thumb: 목록용 — 안드로이드가 원본 해상도 대신 작게 디코딩해 수백 장도 가볍게
  return <Image source={{ uri: resolved }} style={style} resizeMode={contain ? 'contain' : 'cover'} resizeMethod={thumb ? 'resize' : 'auto'} />;
}

/** 목록의 명함 썸네일 — 실제 명함 사진을 그대로 (회사 로고·색으로 바로 알아본다). 사진이 없으면 이니셜 */
export function CardThumb({ card, width = 64 }: { card: { name: string; nameEn?: string; company: string; imageUri?: string; favorite?: boolean }; width?: number }) {
  const height = Math.round(width / 1.6);
  if (!card.imageUri) {
    return (
      <View style={{ width, height, alignItems: 'center', justifyContent: 'center' }}>
        <Avatar name={card.name || card.nameEn || ''} company={card.company} size={height} favorite={card.favorite} />
      </View>
    );
  }
  return (
    <View style={[{ width, height, borderRadius: 7, overflow: 'hidden', backgroundColor: T.line, borderWidth: 1, borderColor: T.line }, card.favorite && { borderWidth: 2, borderColor: T.gold }]}>
      <CardImage uri={card.imageUri} style={{ width: '100%', height: '100%' }} thumb />
    </View>
  );
}
