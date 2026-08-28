import AsyncStorage from '@react-native-async-storage/async-storage';
import { useMemo } from 'react';
import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';
import { createId } from '../core/id';
import { DEFAULT_THEME_KEY } from '../core/photocard';
import { canAddPet, isProActive, quotaState, type QuotaState } from '../core/quota';
import type { AnalysisEntry, PetProfile, Subscription } from '../core/types';

/** 앱 전역 상태. 전부 기기 로컬(AsyncStorage)에 저장된다. */
interface PetState {
  pets: PetProfile[];
  activePetId: string | null;
  entries: AnalysisEntry[];
  subscription: Subscription;
  cardThemeKey: string;
  onboarded: boolean;
  hydrated: boolean;

  addPet: (input: Omit<PetProfile, 'id' | 'createdAt'>) => PetProfile | null;
  updatePet: (id: string, patch: Partial<Omit<PetProfile, 'id' | 'createdAt'>>) => void;
  removePet: (id: string) => void;
  setActivePet: (id: string) => void;

  addEntry: (entry: Omit<AnalysisEntry, 'id'>) => AnalysisEntry;
  removeEntry: (id: string) => void;

  setSubscription: (sub: Subscription) => void;
  setCardTheme: (key: string) => void;
  completeOnboarding: () => void;

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

      setSubscription: (subscription) => set({ subscription }),
      setCardTheme: (cardThemeKey) => set({ cardThemeKey }),
      completeOnboarding: () => set({ onboarded: true }),

      resetAll: () =>
        set({
          pets: [],
          activePetId: null,
          entries: [],
          subscription: { pro: false },
          cardThemeKey: DEFAULT_THEME_KEY,
          onboarded: false,
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
