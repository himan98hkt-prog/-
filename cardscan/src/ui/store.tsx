// 앱 전역 상태 — 명함 목록·설정과 "저장 → 연동" 흐름을 한곳에서 처리한다.
import { randomUUID } from 'expo-crypto';
import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { AppState } from 'react-native';
import { findDuplicate } from '../core/mapping';
import { Settings, DEFAULT_SETTINGS } from '../core/settings';
import { BusinessCard, CardFields, CardKind, ConnectorId } from '../core/types';
import { deviceContactsConnector } from '../integrations/deviceContacts';
import { HTTP_CONNECTORS, pendingTargets, syncCard, ConnectorMap } from '../integrations/sync';
import { loadCards, saveCards } from '../storage/cards';
import { deleteImage, persistImage } from '../storage/images';
import { loadSettings, saveSettings } from '../storage/settings';

const CONNECTORS: ConnectorMap = { contacts: deviceContactsConnector, ...HTTP_CONNECTORS };

export interface NewCardInput {
  fields: CardFields;
  kind: CardKind;
  extra: string[];
  tempImageUri?: string;
}

interface Store {
  ready: boolean;
  cards: BusinessCard[];
  settings: Settings;
  /** 저장 후 연동까지 진행. 같은 사람(휴대폰/이메일 동일) 명함이 있으면 그 명함을 갱신한다. */
  addCard(input: NewCardInput): Promise<{ card: BusinessCard; merged: boolean }>;
  updateCard(id: string, fields: Partial<CardFields> & { kind?: CardKind }): Promise<void>;
  deleteCard(id: string): Promise<void>;
  resync(id: string, only?: ConnectorId[]): Promise<void>;
  setSettings(next: Settings): Promise<void>;
  syncingIds: Set<string>;
}

const Ctx = createContext<Store | null>(null);

export function StoreProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [cards, setCards] = useState<BusinessCard[]>([]);
  const [settings, setSettingsState] = useState<Settings>(DEFAULT_SETTINGS);
  const [syncingIds, setSyncingIds] = useState<Set<string>>(new Set());
  const cardsRef = useRef<BusinessCard[]>([]);
  const settingsRef = useRef<Settings>(DEFAULT_SETTINGS);

  const commit = useCallback((updater: (prev: BusinessCard[]) => BusinessCard[]) => {
    const next = updater(cardsRef.current);
    cardsRef.current = next;
    setCards(next);
    saveCards(next).catch(() => {});
  }, []);

  const runSync = useCallback(
    async (id: string, only?: ConnectorId[]) => {
      const card = cardsRef.current.find((c) => c.id === id);
      if (!card) return;
      setSyncingIds((s) => new Set(s).add(id));
      try {
        const sync = await syncCard(card, { settings: settingsRef.current, connectors: CONNECTORS, fetch, only });
        commit((prev) => prev.map((c) => (c.id === id ? { ...c, sync } : c)));
      } finally {
        setSyncingIds((s) => {
          const n = new Set(s);
          n.delete(id);
          return n;
        });
      }
    },
    [commit],
  );

  /** 실패·미전송 연동을 다시 보낸다 (앱 시작/복귀 시) */
  const retryPending = useCallback(async () => {
    for (const card of cardsRef.current) {
      const targets = pendingTargets(card, settingsRef.current);
      if (targets.length) await runSync(card.id, targets);
    }
  }, [runSync]);

  useEffect(() => {
    (async () => {
      const [c, s] = await Promise.all([loadCards(), loadSettings()]);
      cardsRef.current = c;
      settingsRef.current = s;
      setCards(c);
      setSettingsState(s);
      setReady(true);
      retryPending();
    })();
    const sub = AppState.addEventListener('change', (st) => {
      if (st === 'active') retryPending();
    });
    return () => sub.remove();
  }, [retryPending]);

  const addCard = useCallback<Store['addCard']>(
    async ({ fields, kind, extra, tempImageUri }) => {
      const now = new Date().toISOString();
      const draft: BusinessCard = { ...fields, id: randomUUID(), kind, extra, createdAt: now, updatedAt: now, sync: {} };
      const dup = findDuplicate(cardsRef.current, draft);
      const id = dup ? dup.id : draft.id;
      const imageUri = tempImageUri ? await persistImage(tempImageUri, `${id}-${Date.now()}`) : undefined;

      let card: BusinessCard;
      if (dup) {
        // 새 명함(이직·승진 등)의 값으로 덮되, 이번에 못 읽은 칸은 기존 값을 유지한다
        const mergedFields = { ...dup } as BusinessCard;
        for (const k of Object.keys(fields) as (keyof CardFields)[]) if (fields[k]) mergedFields[k] = fields[k];
        card = { ...mergedFields, kind, extra, updatedAt: now, imageUri: imageUri ?? dup.imageUri };
        if (imageUri && dup.imageUri) deleteImage(dup.imageUri);
        commit((prev) => prev.map((c) => (c.id === dup.id ? card : c)));
      } else {
        card = { ...draft, imageUri };
        commit((prev) => [card, ...prev]);
      }
      runSync(card.id);
      return { card, merged: !!dup };
    },
    [commit, runSync],
  );

  const updateCard = useCallback<Store['updateCard']>(
    async (id, patch) => {
      commit((prev) => prev.map((c) => (c.id === id ? { ...c, ...patch, updatedAt: new Date().toISOString() } : c)));
      await runSync(id);
    },
    [commit, runSync],
  );

  const deleteCard = useCallback<Store['deleteCard']>(
    async (id) => {
      const card = cardsRef.current.find((c) => c.id === id);
      deleteImage(card?.imageUri);
      commit((prev) => prev.filter((c) => c.id !== id));
    },
    [commit],
  );

  const setSettings = useCallback<Store['setSettings']>(
    async (next) => {
      settingsRef.current = next;
      setSettingsState(next);
      await saveSettings(next);
    },
    [],
  );

  const value = useMemo<Store>(
    () => ({ ready, cards, settings, addCard, updateCard, deleteCard, resync: runSync, setSettings, syncingIds }),
    [ready, cards, settings, addCard, updateCard, deleteCard, runSync, setSettings, syncingIds],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useStore(): Store {
  const s = useContext(Ctx);
  if (!s) throw new Error('StoreProvider 밖에서 useStore 를 호출했습니다');
  return s;
}
