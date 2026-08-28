import { useCallback, useMemo, useState } from 'react';
import { Alert } from 'react-native';
import { analyze } from '../api';
import { aggregateResults } from '../core/aggregate';
import { assessHealth } from '../core/health';
import { ApiError, userMessageKey } from '../api/errors';
import type { ParseFallbacks } from '../core/analysis';
import { judgeRecording } from '../core/audio';
import type { ContextTag } from '../core/emotions';
import type { EmotionKey } from '../core/types';
import { useT } from '../i18n/useT';
import { usePetStore, useActivePet } from '../store/usePetStore';
import { fileTooLarge, toBase64 } from './media';
import { useNavigation } from './navigation';

/** 화면이 넘겨 주는 상황 맥락 */
export interface AnalysisContext {
  /** 사용자 언어로 된 문구 (모델에게도 이 문장이 간다) */
  text: string;
  /** 프리셋에서 골랐다면 번역 키 */
  key?: string;
  tags: ContextTag[];
}

export const EMPTY_CONTEXT: AnalysisContext = { text: '', tags: [] };

/**
 * 녹음/촬영 어느 쪽에서 들어와도 분석 흐름은 같다.
 * (용량 검사 → base64 → 프록시 호출 → 히스토리 저장 → 결과 화면)
 */
export function useAnalyzeMedia() {
  const nav = useNavigation();
  const pet = useActivePet();
  const addEntry = usePetStore((s) => s.addEntry);
  const enqueueAnalysis = usePetStore((s) => s.enqueueAnalysis);
  const tr = useT();
  const [analyzing, setAnalyzing] = useState(false);

  // 모델이 문장을 비워 보냈을 때 채울 문구 — 코어는 언어를 모르니 여기서 만든다
  const fallbacks = useMemo<ParseFallbacks>(
    () => ({
      messageFor: (emotion: EmotionKey) => tr.t(`voice.fallback.${emotion}`),
      behavior: tr.t('analysis.fallback.behavior'),
      action: tr.t('analysis.fallback.action'),
    }),
    [tr],
  );

  const run = useCallback(
    async (uri: string, mediaKind: 'audio' | 'image', context: AnalysisContext, levels?: number[]) => {
      if (!pet || analyzing) return;

      // 서버로 보내기 전에 거른다 — 무음이나 사람 목소리뿐인 녹음으로
      // 무료 3회를 태우지 않게 하는 게 목적이다.
      if (mediaKind === 'audio' && levels) {
        const verdict = judgeRecording(levels);
        if (!verdict.ok) {
          Alert.alert(tr.t(`record.${verdict.reason}`), tr.t(`record.${verdict.reason}Desc`));
          return;
        }
      }

      setAnalyzing(true);
      try {
        if (await fileTooLarge(uri)) {
          Alert.alert(tr.t('errors.tooLarge'), tr.t('errors.tooLargeDesc'));
          return;
        }
        const { result, health } = await analyze({
          pet,
          mediaBase64: await toBase64(uri),
          mediaType: mediaKind === 'audio' ? 'audio/m4a' : 'image/jpeg',
          context: context.text,
          contextTags: context.tags,
          locale: tr.locale,
          fallbacks,
        });
        const entry = addEntry({
          petId: pet.id,
          createdAt: Date.now(),
          mediaKind,
          context: context.text,
          contextKey: context.key,
          contextTags: context.tags,
          mediaUri: mediaKind === 'image' ? uri : pet.photoUri,
          audioUri: mediaKind === 'audio' ? uri : undefined,
          levels,
          result,
          health,
        });
        nav.navigate('result', { entryId: entry.id });
      } catch (error) {
        // 연결 문제라면 버리지 않고 대기열에 넣는다 — 산책 중 신호가 약한 상황이 잦다.
        const offline = error instanceof ApiError && (error.code === 'network' || error.code === 'timeout');
        if (offline) {
          enqueueAnalysis({
            petId: pet.id,
            uri,
            mediaKind,
            context: context.text,
            contextKey: context.key,
            contextTags: context.tags,
            levels,
          });
          Alert.alert(tr.t('home.queued'));
        } else {
          Alert.alert(tr.t('errors.analyzeFailed'), tr.t(userMessageKey(error)));
        }
      } finally {
        setAnalyzing(false);
      }
    },
    [pet, analyzing, addEntry, enqueueAnalysis, nav, tr, fallbacks],
  );

  /**
   * 정밀 분석 — 연속으로 녹음한 여러 회차를 하나로 합친다.
   * 회차가 하나라도 성공하면 결과를 낸다. 전부 실패하면 일반 분석과 같은 오류 처리.
   */
  const runPrecise = useCallback(
    async (shots: { uri: string; levels?: number[] }[], context: AnalysisContext) => {
      if (!pet || analyzing || shots.length === 0) return;
      setAnalyzing(true);
      try {
        const results = [];
        for (const shot of shots) {
          const { result } = await analyze({
            pet,
            mediaBase64: await toBase64(shot.uri),
            mediaType: 'audio/m4a',
            context: context.text,
            contextTags: context.tags,
            locale: tr.locale,
            fallbacks,
          });
          results.push(result);
        }

        const merged = aggregateResults(results);
        const entry = addEntry({
          petId: pet.id,
          createdAt: Date.now(),
          mediaKind: 'audio',
          context: context.text,
          contextKey: context.key,
          contextTags: context.tags,
          mediaUri: pet.photoUri,
          audioUri: shots[0].uri,
          levels: shots[0].levels,
          shotCount: results.length,
          result: merged,
          health: assessHealth(merged, pet.type, context.tags),
        });
        nav.navigate('result', { entryId: entry.id });
      } catch (error) {
        Alert.alert(tr.t('errors.analyzeFailed'), tr.t(userMessageKey(error)));
      } finally {
        setAnalyzing(false);
      }
    },
    [pet, analyzing, addEntry, nav, tr, fallbacks],
  );

  return { analyzing, run, runPrecise };
}

/**
 * 대기열을 처리한다. 앱을 다시 열었을 때와 사용자가 직접 눌렀을 때 호출한다.
 * 실패하면 그대로 남겨 두고 다음 기회를 노린다.
 */
export function useQueueDrain() {
  const queue = usePetStore((s) => s.queue);
  const pets = usePetStore((s) => s.pets);
  const addEntry = usePetStore((s) => s.addEntry);
  const dequeueAnalysis = usePetStore((s) => s.dequeueAnalysis);
  const tr = useT();
  const [draining, setDraining] = useState(false);

  const fallbacks = useMemo<ParseFallbacks>(
    () => ({
      messageFor: (emotion: EmotionKey) => tr.t(`voice.fallback.${emotion}`),
      behavior: tr.t('analysis.fallback.behavior'),
      action: tr.t('analysis.fallback.action'),
    }),
    [tr],
  );

  const drain = useCallback(async () => {
    if (draining || queue.length === 0) return;
    setDraining(true);
    try {
      for (const item of queue) {
        const pet = pets.find((p) => p.id === item.petId);
        if (!pet) {
          dequeueAnalysis(item.id); // 프로필이 지워졌으면 대기 건도 의미가 없다
          continue;
        }
        try {
          const { result, health } = await analyze({
            pet,
            mediaBase64: await toBase64(item.uri),
            mediaType: item.mediaKind === 'audio' ? 'audio/m4a' : 'image/jpeg',
            context: item.context,
            contextTags: item.contextTags,
            locale: tr.locale,
            fallbacks,
          });
          addEntry({
            petId: pet.id,
            createdAt: item.createdAt,
            mediaKind: item.mediaKind,
            context: item.context,
            contextKey: item.contextKey,
            contextTags: item.contextTags,
            mediaUri: item.mediaKind === 'image' ? item.uri : pet.photoUri,
            audioUri: item.mediaKind === 'audio' ? item.uri : undefined,
            levels: item.levels,
            result,
            health,
          });
          dequeueAnalysis(item.id);
        } catch {
          break; // 아직 연결이 안 됐다면 나머지도 실패한다
        }
      }
    } finally {
      setDraining(false);
    }
  }, [draining, queue, pets, addEntry, dequeueAnalysis, tr, fallbacks]);

  return { pending: queue.length, draining, drain };
}
