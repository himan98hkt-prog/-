import { CameraView, useCameraPermissions } from 'expo-camera';
import React, { useRef, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { CONTEXT_PRESETS, type ContextPreset } from '../../core/emotions';
import { useT } from '../../i18n/useT';
import { useActivePet } from '../../store/usePetStore';
import { Button, Card, Chip } from '../components/Basics';
import { pickPhoto } from '../media';
import { useNavigation } from '../navigation';
import { explainPermission } from '../permissions';
import { font, HIT_SIZE, radius, space } from '../theme';
import { useStyles, useTheme, type Theme } from '../useTheme';
import { EMPTY_CONTEXT, useAnalyzeMedia, type AnalysisContext } from '../useAnalyze';

/**
 * 카메라 탭. 전신/표정이 잘 담기도록 가이드라인 오버레이를 얹는다.
 * 촬영 즉시 분석으로 넘어간다.
 */
export function CaptureScreen() {
  const nav = useNavigation();
  const styles = useStyles(makeStyles);
  const { colors } = useTheme();
  const tr = useT();
  const { t } = tr;

  const pet = useActivePet();
  const [permission, requestPermission] = useCameraPermissions();
  const [context, setContext] = useState<AnalysisContext>(EMPTY_CONTEXT);
  const { analyzing, run } = useAnalyzeMedia();
  const cameraRef = useRef<CameraView | null>(null);
  const [busy, setBusy] = useState(false);

  const askPermission = async () => {
    if (await explainPermission('camera', tr)) await requestPermission();
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
    const uri = await pickPhoto(tr);
    if (uri) await run(uri, 'image', context);
  };

  const toggleContext = (preset: ContextPreset) => {
    setContext((prev) =>
      prev.key === preset.key ? EMPTY_CONTEXT : { text: t(preset.key), key: preset.key, tags: preset.tags },
    );
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
            <Text accessibilityRole="header" style={[font.h3, { color: '#FFFFFF', marginTop: space.md }]}>
              {t('capture.permTitle')}
            </Text>
            <Text style={[font.small, styles.permissionText]}>{t('capture.permDesc')}</Text>
            <Button label={t('capture.enable')} onPress={() => void askPermission()} style={{ marginTop: space.lg }} />
          </View>
        )}

        {permission?.granted ? (
          <View pointerEvents="none" style={styles.guideWrap}>
            <View style={styles.guideFrame} />
            <Text style={styles.guideText}>{t('capture.guide')}</Text>
          </View>
        ) : null}

        {analyzing || busy ? (
          <View style={[StyleSheet.absoluteFill, styles.loading]} accessibilityRole="progressbar">
            <ActivityIndicator size="large" color="#FFFFFF" />
            <Text style={[font.bodyStrong, { color: '#FFFFFF', marginTop: space.md }]}>{t('capture.analyzing')}</Text>
          </View>
        ) : null}
      </View>

      <ScrollView contentContainerStyle={styles.panel}>
        <Card style={{ gap: space.sm }}>
          <Text accessibilityRole="header" style={[font.h3, { color: colors.text }]}>
            {t('capture.contextTitle')}
          </Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: space.sm }}>
            {presets.map((preset) => (
              <Chip
                key={preset.key}
                label={t(preset.key)}
                selected={context.key === preset.key}
                onPress={() => toggleContext(preset)}
              />
            ))}
          </ScrollView>
        </Card>

        <View style={styles.actions}>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={t('capture.gallery')}
            onPress={() => void fromGallery()}
            style={styles.sideButton}
          >
            <Text style={{ fontSize: 22 }}>🖼</Text>
          </Pressable>

          <Pressable
            accessibilityRole="button"
            accessibilityLabel={t('capture.shutter')}
            accessibilityState={{ disabled: !permission?.granted || busy || analyzing }}
            onPress={() => void shoot()}
            disabled={!permission?.granted || busy || analyzing}
            style={[styles.shutter, (!permission?.granted || busy || analyzing) && { opacity: 0.4 }]}
          >
            <View style={styles.shutterInner} />
          </Pressable>

          <Pressable
            accessibilityRole="button"
            accessibilityLabel={t('common.close')}
            onPress={nav.back}
            style={styles.sideButton}
          >
            <Text style={{ fontSize: 22 }}>✕</Text>
          </Pressable>
        </View>
      </ScrollView>
    </View>
  );
}

const makeStyles = ({ colors }: Theme) =>
  StyleSheet.create({
    page: { flex: 1, backgroundColor: colors.bg },
    viewport: { flex: 1, backgroundColor: '#15110E', overflow: 'hidden' },
    permissionBox: { alignItems: 'center', justifyContent: 'center', padding: space.xl },
    permissionText: { color: 'rgba(255,255,255,0.8)', textAlign: 'center', marginTop: space.sm },
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
      backgroundColor: 'rgba(0,0,0,0.5)',
      paddingHorizontal: space.md,
      paddingVertical: 6,
      borderRadius: radius.pill,
      overflow: 'hidden',
    },
    loading: { alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(0,0,0,0.55)' },
    panel: { padding: space.lg, gap: space.lg },
    actions: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: space.xl },
    sideButton: {
      width: HIT_SIZE + 8,
      height: HIT_SIZE + 8,
      borderRadius: (HIT_SIZE + 8) / 2,
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
