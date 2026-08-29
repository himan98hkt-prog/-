import { Audio, InterruptionModeAndroid, InterruptionModeIOS } from 'expo-av';
import * as FileSystem from 'expo-file-system';
import * as ImageManipulator from 'expo-image-manipulator';
import * as ImagePicker from 'expo-image-picker';
import { useCallback, useEffect, useRef, useState } from 'react';
import { judgeJpegBase64, PHOTO_PROBE_WIDTH, type PhotoVerdict } from '../core/photo';
import type { Translator } from '../i18n/useT';
import { requestWithRationale } from './permissions';

/** 지시서의 '3초 소리 녹음' */
export const RECORD_SECONDS = 3;

/** 5MB 넘는 파일은 프록시에서 거절되므로 미리 막는다. */
export const MAX_BASE64_BYTES = 5 * 1024 * 1024;

/** 분석에 필요한 최대 해상도. 이보다 크면 보내기 전에 줄인다. */
const MAX_IMAGE_EDGE = 1280;

export async function toBase64(uri: string): Promise<string> {
  return FileSystem.readAsStringAsync(uri, { encoding: FileSystem.EncodingType.Base64 });
}

export async function fileTooLarge(uri: string): Promise<boolean> {
  const info = await FileSystem.getInfoAsync(uri, { size: true });
  return info.exists && typeof info.size === 'number' && info.size > MAX_BASE64_BYTES;
}

/**
 * 보내기 전에 사진을 줄인다.
 * 요즘 폰 사진은 4MB 를 훌쩍 넘는데, 행동 분석에는 그 해상도가 전혀 필요 없다.
 * 업로드 시간·통신비·서버 비용이 모두 줄고 "파일이 너무 큽니다" 거절도 사라진다.
 */
export async function compressImage(uri: string): Promise<string> {
  try {
    const result = await ImageManipulator.manipulateAsync(uri, [{ resize: { width: MAX_IMAGE_EDGE } }], {
      compress: 0.6,
      format: ImageManipulator.SaveFormat.JPEG,
    });
    return result.uri;
  } catch {
    return uri; // 줄이지 못해도 원본으로 계속 간다
  }
}

/**
 * 보내기 전에 사진이 쓸 만한지 본다.
 *
 * 판정용으로 가로 320px 짜리를 따로 한 장 만든다. 원본(1280px)으로 재면
 * 디코딩이 무겁고, 무엇보다 임계값이 해상도에 따라 달라져 기기마다 다르게 걸린다.
 * 폭을 고정하면 어느 기기에서 찍었든 같은 잣대로 잰다.
 *
 * 실패하면 통과시킨다 — 사전 필터가 분석을 못 하게 만드는 원인이 되면 안 된다.
 */
export async function judgePhotoFile(uri: string): Promise<PhotoVerdict> {
  try {
    const probe = await ImageManipulator.manipulateAsync(uri, [{ resize: { width: PHOTO_PROBE_WIDTH } }], {
      compress: 0.8,
      format: ImageManipulator.SaveFormat.JPEG,
      base64: true,
    });
    return probe.base64 ? judgeJpegBase64(probe.base64) : { ok: true };
  } catch {
    return { ok: true };
  }
}

/**
 * 녹음 설정.
 * 감정 분석에 고음질은 필요 없다 — 모노 22kHz 64kbps 면 3초에 약 25KB 다.
 * `isMeteringEnabled` 를 켜야 음량을 받아 무음 여부를 판단할 수 있다.
 */
const RECORDING_OPTIONS: Audio.RecordingOptions = {
  isMeteringEnabled: true,
  android: {
    extension: '.m4a',
    outputFormat: Audio.AndroidOutputFormat.MPEG_4,
    audioEncoder: Audio.AndroidAudioEncoder.AAC,
    sampleRate: 22050,
    numberOfChannels: 1,
    bitRate: 64000,
  },
  ios: {
    extension: '.m4a',
    outputFormat: Audio.IOSOutputFormat.MPEG4AAC,
    audioQuality: Audio.IOSAudioQuality.MEDIUM,
    sampleRate: 22050,
    numberOfChannels: 1,
    bitRate: 64000,
    linearPCMBitDepth: 16,
    linearPCMIsBigEndian: false,
    linearPCMIsFloat: false,
  },
  web: { mimeType: 'audio/webm', bitsPerSecond: 64000 },
};

/** 녹음 세션 핸들 */
export interface RecordingHandle {
  stop: () => Promise<{ uri: string | null; levels: number[] }>;
}

/** 마이크 권한 설명 → 요청 → 녹음 시작 */
export async function startRecording(tr: Translator): Promise<RecordingHandle | null> {
  const ok = await requestWithRationale(
    'mic',
    async () => {
      const res = await Audio.requestPermissionsAsync();
      return { granted: res.granted, canAskAgain: res.canAskAgain };
    },
    tr,
  );
  if (!ok) return null;

  await Audio.setAudioModeAsync({
    allowsRecordingIOS: true,
    playsInSilentModeIOS: true,
    interruptionModeIOS: InterruptionModeIOS.DoNotMix,
    interruptionModeAndroid: InterruptionModeAndroid.DoNotMix,
  });

  const levels: number[] = [];
  const { recording } = await Audio.Recording.createAsync(
    RECORDING_OPTIONS,
    (status) => {
      if (status.isRecording && typeof status.metering === 'number') levels.push(status.metering);
    },
    100, // 0.1초마다 → 3초에 약 30개 샘플
  );

  let stopped = false;
  return {
    stop: async () => {
      if (stopped) return { uri: null, levels };
      stopped = true;
      try {
        await recording.stopAndUnloadAsync();
      } catch {
        // 이미 정지된 경우는 무시
      }
      await Audio.setAudioModeAsync({ allowsRecordingIOS: false });
      return { uri: recording.getURI(), levels };
    },
  };
}

/** 갤러리에서 반려동물 사진 고르기 (고른 뒤 바로 줄인다) */
export async function pickPhoto(tr: Translator): Promise<string | null> {
  const ok = await requestWithRationale(
    'photos',
    async () => {
      const res = await ImagePicker.requestMediaLibraryPermissionsAsync();
      return { granted: res.granted, canAskAgain: res.canAskAgain };
    },
    tr,
  );
  if (!ok) return null;

  const result = await ImagePicker.launchImageLibraryAsync({
    mediaTypes: ImagePicker.MediaTypeOptions.Images,
    quality: 0.7,
    // 포토카드가 4:5 라 자를 때부터 맞춰 둔다
    allowsEditing: true,
    aspect: [4, 5],
  });
  if (result.canceled) return null;
  const uri = result.assets[0]?.uri;
  return uri ? compressImage(uri) : null;
}

/** 결과 화면에서 녹음을 다시 들려주는 재생기 */
export function useAudioPlayback(uri?: string) {
  const soundRef = useRef<Audio.Sound | null>(null);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    return () => {
      void soundRef.current?.unloadAsync();
      soundRef.current = null;
    };
  }, [uri]);

  const toggle = useCallback(async () => {
    if (!uri) return;
    try {
      if (playing) {
        await soundRef.current?.stopAsync();
        setPlaying(false);
        return;
      }
      if (!soundRef.current) {
        await Audio.setAudioModeAsync({ allowsRecordingIOS: false, playsInSilentModeIOS: true });
        const { sound } = await Audio.Sound.createAsync({ uri });
        sound.setOnPlaybackStatusUpdate((status) => {
          if (status.isLoaded && status.didJustFinish) setPlaying(false);
        });
        soundRef.current = sound;
      }
      await soundRef.current.replayAsync();
      setPlaying(true);
    } catch {
      setPlaying(false);
    }
  }, [uri, playing]);

  return { playing, toggle };
}
