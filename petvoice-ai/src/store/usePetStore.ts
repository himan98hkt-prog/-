import AsyncStorage from '@react-native-async-storage/async-storage';
import { useMemo } from 'react';
import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';
import { createId } from '../core/id';
import { DEFAULT_THEME_KEY } from '../core/photocard';
import { canAddPet, isProActive, quotaState, type QuotaState } from '../core/quota';
import type { ContextTag } from '../core/emotions';
import type { AnalysisEntry, Locale, PetProfile, Subscription } from '../core/types';
import { DEFAULT_LOCALE } from '../i18n';
import type { ThemeMode } from '../ui/useTheme';

/**
 * 연결이 없을 때 저장해 두는 분석 대기 건.
 * 산책 중에 가장 재미있는 소리가 나오는데 하필 신호가 약한 경우가 많다.
 */
export interface PendingAnalysis {
  id: string;
  petId: string;
  uri: string;
  mediaKind: 'audio' | 'image';
  context: string;
  contextKey?: string;
  contextTags: ContextTag[];
  levels?: number[];
  createdAt: number;
}

/** 알림 설정 */
export interface NotificationSettings {
  /** 저녁 기록 리마인더 */
  daily: boolean;
  /** 주간 리포트 알림 */
  weekly: boolean;
  /** 저녁 알림 시각 (0~23) */
  hour: number;
}

/** 앱 전역 상태. 전부 기기 로컬(AsyncStorage)에 저장된다. */
interface PetState {
  pets: PetProfile[];
  activePetId: string | null;
  entries: AnalysisEntry[];
  subscription: Subscription;
  cardThemeKey: string;
  onboarded: boolean;
  hydrated: boolean;

  locale: Locale;
  themeMode: ThemeMode;
  notifications: NotificationSettings;
  /** 크래시·오류 보고 전송 동의 (기본 꺼짐) */
  diagnostics: boolean;
  /** 마지막으로 서버에 백업한 시각 */
  lastBackupAt?: number;
  /** 연결이 돌아오면 처리할 분석 대기열 */
  queue: PendingAnalysis[];

  addPet: (input: Omit<PetProfile, 'id' | 'createdAt'>) => PetProfile | null;
  updatePet: (id: string, patch: Partial<Omit<PetProfile, 'id' | 'createdAt'>>) => void;
  removePet: (id: string) => void;
  setActivePet: (id: string) => void;

  addEntry: (entry: Omit<AnalysisEntry, 'id'>) => AnalysisEntry;
  removeEntry: (id: string) => void;
  /** 결과가 맞았는지 표시 (프롬프트 개선의 근거가 된다) */
  setEntryFeedback: (id: string, feedback: 'up' | 'down') => void;

  setSubscription: (sub: Subscription) => void;
  setCardTheme: (key: string) => void;
  completeOnboarding: () => void;

  setLocale: (locale: Locale) => void;
  setThemeMode: (mode: ThemeMode) => void;
  setNotifications: (patch: Partial<NotificationSettings>) => void;
  setDiagnostics: (on: boolean) => void;
  setLastBackupAt: (ts: number) => void;
  /** 백업에서 복원한 기록으로 교체(중복은 id 기준으로 합침) */
  mergeEntries: (incoming: AnalysisEntry[]) => number;

  enqueueAnalysis: (item: Omit<PendingAnalysis, 'id' | 'createdAt'>) => void;
  dequeueAnalysis: (id: string) => void;

  /** 설정 ▸ 모든 데이터 초기화 (Play 정책 요건) */
  resetAll: () => void;
}

export const usePetStore = create<PetState>()(
  persist(
    (set, get) => ({
      pets: [],
      activePetId: null,
      entries: [],
      subscription: { pro: false },
      cardThemeKey: DEFAULT_THEME_KEY,
      onboarded: false,
      hydrated: false,

      locale: DEFAULT_LOCALE,
      themeMode: 'system',
      notifications: { daily: false, weekly: false, hour: 20 },
      diagnostics: false,
      queue: [],

      addPet: (input) => {
        const state = get();
        if (!canAddPet(state.pets.length, state.subscription)) return null;
        const pet: PetProfile = { ...input, id: createId('pet_'), createdAt: Date.now() };
        set({ pets: [...state.pets, pet], activePetId: pet.id });
        return pet;
      },

      updatePet: (id, patch) =>
        set((state) => ({ pets: state.pets.map((p) => (p.id === id ? { ...p, ...patch } : p)) })),

      removePet: (id) =>
        set((state) => {
          const pets = state.pets.filter((p) => p.id !== id);
          return {
            pets,
            entries: state.entries.filter((e) => e.petId !== id),
            activePetId: state.activePetId === id ? (pets[0]?.id ?? null) : state.activePetId,
          };
        }),

      setActivePet: (id) => set({ activePetId: id }),

      addEntry: (entry) => {
        const saved: AnalysisEntry = { ...entry, id: createId('an_') };
        set((state) => ({ entries: [saved, ...state.entries] }));
        return saved;
      },

      removeEntry: (id) => set((state) => ({ entries: state.entries.filter((e) => e.id !== id) })),

      setEntryFeedback: (id, feedback) =>
        set((state) => ({ entries: state.entries.map((e) => (e.id === id ? { ...e, feedback } : e)) })),

      setSubscription: (subscription) => set({ subscription }),
      setCardTheme: (cardThemeKey) => set({ cardThemeKey }),
      completeOnboarding: () => set({ onboarded: true }),

      setLocale: (locale) => set({ locale }),
      setThemeMode: (themeMode) => set({ themeMode }),
      setNotifications: (patch) => set((state) => ({ notifications: { ...state.notifications, ...patch } })),
      setDiagnostics: (diagnostics) => set({ diagnostics }),
      setLastBackupAt: (lastBackupAt) => set({ lastBackupAt }),

      enqueueAnalysis: (item) =>
        set((state) => ({
          queue: [...state.queue, { ...item, id: createId('q_'), createdAt: Date.now() }],
        })),

      dequeueAnalysis: (id) => set((state) => ({ queue: state.queue.filter((q) => q.id !== id) })),

      mergeEntries: (incoming) => {
        const state = get();
        const known = new Set(state.entries.map((e) => e.id));
        const added = incoming.filter((e) => !known.has(e.id));
        if (added.length === 0) return 0;
        set({ entries: [...state.entries, ...added].sort((a, b) => b.createdAt - a.createdAt) });
        return added.length;
      },

      resetAll: () =>
        set({
          pets: [],
          activePetId: null,
          entries: [],
          subscription: { pro: false },
          cardThemeKey: DEFAULT_THEME_KEY,
          onboarded: false,
          lastBackupAt: undefined,
          queue: [],
        }),
    }),
    {
      name: 'petvoice-store-v1',
      storage: createJSONStorage(() => AsyncStorage),
      // 액션 함수까지 통째로 넘기면 직렬화 때 버려지며 잡음만 남는다. 데이터만 저장한다.
      partialize: (state) => ({
        pets: state.pets,
        activePetId: state.activePetId,
        entries: state.entries,
        subscription: state.subscription,
        cardThemeKey: state.cardThemeKey,
        onboarded: state.onboarded,
        locale: state.locale,
        themeMode: state.themeMode,
        notifications: state.notifications,
        diagnostics: state.diagnostics,
        lastBackupAt: state.lastBackupAt,
        queue: state.queue,
      }),
    },
  ),
);

// AsyncStorage 복원이 끝나기 전에는 "반려동물 없음" 화면이 잠깐 스쳐 지나간다.
// hydrated 플래그로 그 깜빡임을 막는다.
usePetStore.persist.onFinishHydration(() => usePetStore.setState({ hydrated: true }));
if (usePetStore.persist.hasHydrated()) usePetStore.setState({ hydrated: true });

/* ---------- 파생 셀렉터 ---------- */

export function useActivePet(): PetProfile | null {
  return usePetStore((s) => s.pets.find((p) => p.id === s.activePetId) ?? s.pets[0] ?? null);
}

export function useEntriesForActivePet(): AnalysisEntry[] {
  const entries = usePetStore((s) => s.entries);
  const petId = usePetStore((s) => s.activePetId ?? s.pets[0]?.id ?? null);
  // 셀렉터 안에서 filter 하면 매 렌더 새 배열이 나와 리렌더가 멈추지 않는다.
  return useMemo(() => (petId ? entries.filter((e) => e.petId === petId) : []), [entries, petId]);
}

/** 무료 3회 제한은 반려동물별이 아니라 계정 전체 기준 */
export function useQuota(now = Date.now()): QuotaState {
  const entries = usePetStore((s) => s.entries);
  const subscription = usePetStore((s) => s.subscription);
  return useMemo(
    () => quotaState(entries.map((e) => e.createdAt), subscription, now),
    [entries, subscription, now],
  );
}

export function useIsPro(): boolean {
  return usePetStore((s) => isProActive(s.subscription));
}
