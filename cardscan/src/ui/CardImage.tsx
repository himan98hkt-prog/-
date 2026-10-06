import { Image, ImageStyle, StyleProp, View } from 'react-native';
import { useImageUri } from '../storage/images';
import { C } from './components';

/** 명함 사진 — 앱은 파일, 웹은 IndexedDB 에 있어 주소를 풀어서 보여준다 */
export function CardImage({ uri, style, contain }: { uri?: string; style: StyleProp<ImageStyle>; contain?: boolean }) {
  const resolved = useImageUri(uri);
  if (!resolved) return <View style={[style as object, { backgroundColor: C.line }]} />;
  return <Image source={{ uri: resolved }} style={style} resizeMode={contain ? 'contain' : 'cover'} />;
}
