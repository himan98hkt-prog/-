// 앱 전역 상태 — 명함 목록·설정과 "저장 → 연동" 흐름을 한곳에서 처리한다.
import { randomUUID } from 'expo-crypto';
import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { AppState } from 'react-native';
import { mergeBackup } from '../core/exportData';
import { findDuplicate } from '../core/mapping';
import { mergeRescan, normalizeTag } from '../core/organize';
import { Settings, DEFAULT_SETTINGS } from '../core/settings';
import { BusinessCard, CardFields, CardKind, ConnectorId } from '../core/types';
import { deviceContactsConnector } from '../integrations/deviceContacts';
import { HTTP_CONNECTORS, pendingTargets, syncCard, ConnectorMap } from '../integrations/sync';
import { loadCards, saveCards } from '../storage/cards';
import { deleteImage, persistImage } from '../storage/images';
import { loadSettings, saveSettings } from '../storage/settings';
import { cancelFollowUp, scheduleFollowUp } from './reminders';

const CONNECTORS: ConnectorMap = { contacts: deviceContactsConnector, ...HTTP_CONNECTORS };

export interface NewCardInput {
  fields: CardFields;
  kind: CardKind;
  extra: string[];
  tempImageUri?: string;
  /** 뒷면 사진 (앞·뒷면 촬영) */
  tempBackUri?: string;
  /** 함께 붙일 그룹 (행사 태그·확인필요 등) — 같은 사람이면 기존 그룹에 더한다 */
  tags?: string[];
}

/** 연동 대상과 무관한 정리용 칸 — 바꿔도 다시 보내지 않는다 */
export type CardMeta = Pick<BusinessCard, 'favorite' | 'tags' | 'followUp'>;

interface Store {
  ready: boolean;
  cards: BusinessCard[];
  settings: Settings;
  /** 저장 후 연동까지 진행. 같은 사람(휴대폰/이메일 동일) 명함이 있으면 그 명함을 갱신한다. */
  addCard(input: NewCardInput): Promise<{ card: BusinessCard; merged: boolean; careerChanged: boolean }>;
  updateCard(id: string, fields: Partial<CardFields> & { kind?: CardKind }): Promise<void>;
  deleteCard(id: string): Promise<void>;
  resync(id: string, only?: ConnectorId[]): Promise<void>;
  setSettings(next: Settings): Promise<void>;
  syncingIds: Set<string>;
  /** 즐겨찾기·그룹·팔로업 (연동 재전송 없음, 팔로업은 알림 예약) */
  setMeta(id: string, meta: Partial<CardMeta>): void;
  addNote(id: string, text: string): void;
  deleteNote(id: string, noteId: string): void;
  /** 백업 파일 복원 */
  restoreCards(incoming: BusinessCard[]): { added: number; updated: number };
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
    async ({ fields, kind, extra, tempImageUri, tempBackUri, tags }) => {
      const now = new Date().toISOString();
      const draft: BusinessCard = { ...fields, id: randomUUID(), kind, extra, createdAt: now, updatedAt: now, sync: {} };
      const dup = findDuplicate(cardsRef.current, draft);
      const id = dup ? dup.id : draft.id;
      const stamp = Date.now();
      const imageUri = tempImageUri ? await persistImage(tempImageUri, `${id}-${stamp}`) : undefined;
      const backImageUri = tempBackUri ? await persistImage(tempBackUri, `${id}-${stamp}-back`) : undefined;

      let card: BusinessCard;
      let careerChanged = false;
      const withTags = (c: BusinessCard): BusinessCard => {
        const merged = [...new Set([...(c.tags ?? []), ...(tags ?? []).map(normalizeTag)].filter(Boolean))];
        return merged.length ? { ...c, tags: merged } : c;
      };
      if (dup) {
        // 같은 사람 — 이번에 읽힌 칸만 새 값으로, 회사·직책이 바뀌었으면 이전 소속을 경력 이력에 남긴다
        const { card: merged, changed } = mergeRescan(dup, fields, now, randomUUID);
        careerChanged = !!changed;
        card = withTags({
          ...merged,
          kind,
          extra: extra.length ? extra : dup.extra,
          imageUri: imageUri ?? dup.imageUri,
          backImageUri: backImageUri ?? (imageUri ? undefined : dup.backImageUri),
        });
        if (imageUri && dup.imageUri) deleteImage(dup.imageUri);
        if ((imageUri || backImageUri) && dup.backImageUri && dup.backImageUri !== card.backImageUri) deleteImage(dup.backImageUri);
        commit((prev) => prev.map((c) => (c.id === dup.id ? card : c)));
      } else {
        card = withTags({ ...draft, imageUri, backImageUri });
        commit((prev) => [card, ...prev]);
      }
      runSync(card.id);
      return { card, merged: !!dup, careerChanged };
    },
    [commit, runSync],
  );

  const setMeta = useCallback<Store['setMeta']>(
    (id, meta) => {
      const clean: Partial<CardMeta> = { ...meta };
      if (meta.tags) clean.tags = [...new Set(meta.tags.map(normalizeTag).filter(Boolean))];
      commit((prev) => prev.map((c) => (c.id === id ? { ...c, ...clean } : c)));
      if ('followUp' in meta) {
        const card = cardsRef.current.find((c) => c.id === id);
        if (card && settingsRef.current.followUpNotify) scheduleFollowUp(card).catch(() => {});
        else cancelFollowUp(id);
      }
    },
    [commit],
  );

  const addNote = useCallback<Store['addNote']>(
    (id, text) => {
      const t = text.trim();
      if (!t) return;
      const note = { id: randomUUID(), at: new Date().toISOString(), text: t };
      commit((prev) => prev.map((c) => (c.id === id ? { ...c, notes: [note, ...(c.notes ?? [])] } : c)));
    },
    [commit],
  );

  const deleteNote = useCallback<Store['deleteNote']>(
    (id, noteId) => commit((prev) => prev.map((c) => (c.id === id ? { ...c, notes: (c.notes ?? []).filter((n) => n.id !== noteId) } : c))),
    [commit],
  );

  const restoreCards = useCallback<Store['restoreCards']>(
    (incoming) => {
      const { cards: merged, added, updated } = mergeBackup(cardsRef.current, incoming);
      commit(() => merged);
      // 복원된 명함의 팔로업 알림 다시 걸기, 연동은 다음 앱 복귀 때 재전송
      if (settingsRef.current.followUpNotify) for (const c of merged) if (c.followUp) scheduleFollowUp(c).catch(() => {});
      return { added, updated };
    },
    [commit],
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
      deleteImage(card?.backImageUri);
      cancelFollowUp(id);
      commit((prev) => prev.filter((c) => c.id !== id));
    },
    [commit],
  );

  const setSettings = useCallback<Store['setSettings']>(
    async (next) => {
      const notifyChanged = next.followUpNotify !== settingsRef.current.followUpNotify;
      settingsRef.current = next;
      setSettingsState(next);
      await saveSettings(next);
      // 팔로업 알림을 켜고 끄면 이미 정해 둔 날짜들의 알림도 맞춰 건다/지운다
      if (notifyChanged) {
        for (const c of cardsRef.current) {
          if (!c.followUp) continue;
          if (next.followUpNotify) scheduleFollowUp(c).catch(() => {});
          else cancelFollowUp(c.id);
        }
      }
    },
    [],
  );

  const value = useMemo<Store>(
    () => ({
      ready, cards, settings, addCard, updateCard, deleteCard, resync: runSync, setSettings, syncingIds,
      setMeta, addNote, deleteNote, restoreCards,
    }),
    [ready, cards, settings, addCard, updateCard, deleteCard, runSync, setSettings, syncingIds, setMeta, addNote, deleteNote, restoreCards],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useStore(): Store {
  const s = useContext(Ctx);
  if (!s) throw new Error('StoreProvider 밖에서 useStore 를 호출했습니다');
  return s;
}
