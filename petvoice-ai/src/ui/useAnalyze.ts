import { useCallback, useState } from 'react';
import { Alert } from 'react-native';
import { analyze } from '../api';
import { userMessage } from '../api/errors';
import { usePetStore, useActivePet } from '../store/usePetStore';
import { fileTooLarge, toBase64 } from './media';
import { useNavigation } from './navigation';

/**
 * 녹음/촬영 어느 쪽에서 들어와도 분석 흐름은 같다.
 * (용량 검사 → base64 → 프록시 호출 → 히스토리 저장 → 결과 화면)
 */
export function useAnalyzeMedia() {
  const nav = useNavigation();
  const pet = useActivePet();
  const addEntry = usePetStore((s) => s.addEntry);
  const [analyzing, setAnalyzing] = useState(false);

  const run = useCallback(
    async (uri: string, mediaKind: 'audio' | 'image', context: string) => {
      if (!pet || analyzing) return;
      setAnalyzing(true);
      try {
        if (await fileTooLarge(uri)) {
          Alert.alert('파일이 너무 커요', '조금 더 짧게 녹음하거나 사진 화질을 낮춰 주세요.');
          return;
        }
        const { result, health } = await analyze({
          pet,
          mediaBase64: await toBase64(uri),
          mediaType: mediaKind === 'audio' ? 'audio/m4a' : 'image/jpeg',
          context,
        });
        const entry = addEntry({
          petId: pet.id,
          createdAt: Date.now(),
          mediaKind,
          context,
          mediaUri: mediaKind === 'image' ? uri : pet.photoUri,
          result,
          health,
        });
        nav.navigate('result', { entryId: entry.id });
      } catch (error) {
        Alert.alert('분석에 실패했어요', userMessage(error));
      } finally {
        setAnalyzing(false);
      }
    },
    [pet, analyzing, addEntry, nav],
  );

  return { analyzing, run };
}
