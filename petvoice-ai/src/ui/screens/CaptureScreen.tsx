import { CameraView, useCameraPermissions } from 'expo-camera';
import React, { useRef, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { CONTEXT_PRESETS } from '../../core/emotions';
import { useActivePet } from '../../store/usePetStore';
import { Button, Card, Chip } from '../components/Basics';
import { pickPhoto } from '../media';
import { useNavigation } from '../navigation';
import { explainPermission } from '../permissions';
import { colors, font, radius, space } from '../theme';
import { useAnalyzeMedia } from '../useAnalyze';

/**
 * 카메라 탭. 전신/표정이 잘 담기도록 가이드라인 오버레이를 얹는다.
 * 촬영 즉시 분석으로 넘어간다.
 */
export function CaptureScreen() {
  const nav = useNavigation();
  const pet = useActivePet();
  const [permission, requestPermission] = useCameraPermissions();
  const [context, setContext] = useState('');
  const { analyzing, run } = useAnalyzeMedia();
  const cameraRef = useRef<CameraView | null>(null);
  const [busy, setBusy] = useState(false);

  const askPermission = async () => {
    const proceed = await explainPermission('camera');
    if (proceed) await requestPermission();
  };

  const shoot = async () => {
    if (!cameraRef.current || busy || analyzing) return;
    setBusy(true);
    try {
      const photo = await cameraRef.current.takePictureAsync({ quality: 0.7 });
      if (photo?.uri) await run(photo.uri, 'image', context);
    } finally {
      setBusy(false);
    }
  };

  const fromGallery = async () => {
    const uri = await pickPhoto();
    if (uri) await run(uri, 'image', context);
  };

  const presets = pet ? CONTEXT_PRESETS[pet.type] : [];

  return (
    <View style={styles.page}>
      <View style={styles.viewport}>
        {permission?.granted ? (
          <CameraView ref={cameraRef} style={StyleSheet.absoluteFill} facing="back" />
        ) : (
          <View style={[StyleSheet.absoluteFill, styles.permissionBox]}>
            <Text style={{ fontSize: 44 }}>📷</Text>
            <Text style={[font.h3, { color: '#FFFFFF', marginTop: space.md }]}>카메라로 행동을 분석해요</Text>
            <Text style={[font.small, styles.permissionText]}>
              자세와 표정은 소리만큼 많은 걸 알려 줍니다.{'\n'}촬영한 사진은 분석과 포토카드에만 사용돼요.
            </Text>
            <Button label="카메라 켜기" onPress={() => void askPermission()} style={{ marginTop: space.lg }} />
          </View>
        )}

        {/* 촬영 가이드라인 */}
        {permission?.granted ? (
          <View pointerEvents="none" style={styles.guideWrap}>
            <View style={styles.guideFrame} />
            <Text style={styles.guideText}>전신과 얼굴이 함께 보이게 담아 주세요</Text>
          </View>
        ) : null}

        {analyzing || busy ? (
          <View style={[StyleSheet.absoluteFill, styles.loading]}>
            <ActivityIndicator size="large" color="#FFFFFF" />
            <Text style={[font.bodyStrong, { color: '#FFFFFF', marginTop: space.md }]}>행동을 읽는 중…</Text>
          </View>
        ) : null}
      </View>

      <ScrollView contentContainerStyle={styles.panel}>
        <Card style={{ gap: space.sm }}>
          <Text style={font.h3}>지금 상황은요? (선택)</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: space.sm }}>
            {presets.map((preset) => (
              <Chip
                key={preset}
                label={preset}
                selected={context === preset}
                onPress={() => setContext((prev) => (prev === preset ? '' : preset))}
              />
            ))}
          </ScrollView>
        </Card>

        <View style={styles.actions}>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="갤러리에서 사진 고르기"
            onPress={() => void fromGallery()}
            style={styles.sideButton}
          >
            <Text style={{ fontSize: 22 }}>🖼</Text>
          </Pressable>

          <Pressable
            accessibilityRole="button"
            accessibilityLabel="사진 촬영"
            onPress={() => void shoot()}
            disabled={!permission?.granted || busy || analyzing}
            style={[styles.shutter, (!permission?.granted || busy || analyzing) && { opacity: 0.4 }]}
          >
            <View style={styles.shutterInner} />
          </Pressable>

          <Pressable accessibilityRole="button" accessibilityLabel="닫기" onPress={nav.back} style={styles.sideButton}>
            <Text style={{ fontSize: 22 }}>✕</Text>
          </Pressable>
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: colors.bg },
  viewport: { flex: 1, backgroundColor: '#15110E', overflow: 'hidden' },
  permissionBox: { alignItems: 'center', justifyContent: 'center', padding: space.xl },
  permissionText: { color: 'rgba(255,255,255,0.75)', textAlign: 'center', marginTop: space.sm },
  guideWrap: { ...StyleSheet.absoluteFillObject, alignItems: 'center', justifyContent: 'center' },
  guideFrame: {
    width: '78%',
    height: '68%',
    borderWidth: 2,
    borderColor: 'rgba(255,255,255,0.85)',
    borderStyle: 'dashed',
    borderRadius: radius.lg,
  },
  guideText: {
    marginTop: space.md,
    color: '#FFFFFF',
    fontSize: 13,
    backgroundColor: 'rgba(0,0,0,0.45)',
    paddingHorizontal: space.md,
    paddingVertical: 6,
    borderRadius: radius.pill,
    overflow: 'hidden',
  },
  loading: { alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(0,0,0,0.55)' },
  panel: { padding: space.lg, gap: space.lg },
  actions: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: space.xl },
  sideButton: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  shutter: {
    width: 76,
    height: 76,
    borderRadius: 38,
    backgroundColor: colors.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  shutterInner: { width: 58, height: 58, borderRadius: 29, backgroundColor: colors.primary },
});
