import type { AnalysisEntry } from '../core/types';

/**
 * 분석 기록 저장소.
 *
 * 원래는 앱 상태 전체를 JSON 한 덩어리로 AsyncStorage 에 썼다.
 * 기록이 수백 건 쌓이면 한 건을 추가할 때마다 전부 다시 직렬화하게 돼
 * 저장이 눈에 띄게 느려진다. 그래서 기록만 따로 떼어 SQLite 로 옮겼다.
 *
 * SQLite 가 없는 환경(웹 미리보기 등)에서는 예전처럼 AsyncStorage 에 배열로 둔다 —
 * 느리지만 동작은 같고, 그런 환경에는 기록이 수백 건 쌓일 일도 없다.
 *
 * 기기 모듈 두 개(expo-sqlite, AsyncStorage)를 **주입받을 수 있게** 열어 뒀다.
 * 실제 앱에서는 아무것도 넘기지 않고 기본값이 쓰이지만, 그 덕에 노드에서도
 * 이전·폴백·검증 경로를 그대로 돌려 볼 수 있다. 이 저장소에서 한 번
 * 기록을 통째로 잃을 뻔했고, 그때 브라우저로 직접 확인해서야 잡았다.
 */

const FALLBACK_KEY = 'petvoice-entries-v1';
const DB_NAME = 'petvoice.db';

/** expo-sqlite 가 주는 DB 핸들 중 우리가 쓰는 부분만 */
export interface SqliteDatabase {
  execAsync: (sql: string) => Promise<unknown>;
  runAsync: (sql: string, params?: unknown[]) => Promise<unknown>;
  getAllAsync: <T>(sql: string, params?: unknown[]) => Promise<T[]>;
  getFirstAsync: <T>(sql: string, params?: unknown[]) => Promise<T | null>;
}

export interface SqliteModule {
  openDatabaseAsync?: (name: string) => Promise<SqliteDatabase>;
}

/** AsyncStorage 중 우리가 쓰는 부분만 */
export interface KeyValueStore {
  getItem: (key: string) => Promise<string | null>;
  setItem: (key: string, value: string) => Promise<void>;
  removeItem: (key: string) => Promise<void>;
}

export interface EntryStoreDeps {
  /** 없으면 expo-sqlite 를 찾아본다 */
  sqlite?: SqliteModule | null;
  /** 없으면 AsyncStorage 를 찾아본다 */
  storage?: KeyValueStore | null;
}

let db: SqliteDatabase | null = null;
let storage: KeyValueStore | null = null;
let initialized = false;

function defaultSqlite(): SqliteModule | null {
  try {
    return require('expo-sqlite') as SqliteModule;
  } catch {
    return null;
  }
}

function defaultStorage(): KeyValueStore | null {
  try {
    return require('@react-native-async-storage/async-storage').default as KeyValueStore;
  } catch {
    return null;
  }
}

const SCHEMA = `
  CREATE TABLE IF NOT EXISTS entries (
    id         TEXT PRIMARY KEY NOT NULL,
    pet_id     TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    payload    TEXT NOT NULL
  );
  CREATE INDEX IF NOT EXISTS entries_pet_created ON entries (pet_id, created_at DESC);
  CREATE INDEX IF NOT EXISTS entries_created ON entries (created_at DESC);
`;

/**
 * SQLite 를 연다.
 *
 * 모듈이 로드된다고 실제로 동작하는 건 아니다 (웹 빌드가 그렇다).
 * 그래서 열자마자 **쓰고 읽어 보는 검사**를 한 번 하고,
 * 거기서 실패하면 SQLite 를 쓰지 않는다. 반쯤 동작하는 저장소가 제일 위험하다.
 */
async function openDatabase(mod: SqliteModule | null): Promise<SqliteDatabase | null> {
  try {
    if (!mod || typeof mod.openDatabaseAsync !== 'function') return null;

    const opened = await mod.openDatabaseAsync(DB_NAME);
    await opened.execAsync(SCHEMA);

    // 왕복 검사: 넣고, 읽고, 지운다
    const probeId = `__probe_${Date.now()}`;
    await opened.runAsync(
      'INSERT OR REPLACE INTO entries (id, pet_id, created_at, payload) VALUES (?, ?, ?, ?)',
      [probeId, '__probe', 0, '{}'],
    );
    const found = await opened.getFirstAsync<{ id: string }>('SELECT id FROM entries WHERE id = ?', [
      probeId,
    ]);
    await opened.runAsync('DELETE FROM entries WHERE id = ?', [probeId]);
    if (!found) return null;

    return opened;
  } catch {
    return null;
  }
}

/** 앱 시작 시 한 번. 저장소를 열고(가능하면 SQLite) 준비한다. */
export async function initEntryStore(deps: EntryStoreDeps = {}): Promise<void> {
  if (initialized) return;
  initialized = true;
  storage = deps.storage !== undefined ? deps.storage : defaultStorage();
  db = await openDatabase(deps.sqlite !== undefined ? deps.sqlite : defaultSqlite());
}

/** 테스트에서 모듈 상태를 비운다. 앱 코드는 부르지 않는다. */
export function resetEntryStore(): void {
  db = null;
  storage = null;
  initialized = false;
}

/**
 * 예전 버전이 앱 상태 블롭 안에 넣어 두던 기록을 새 저장소로 옮긴다.
 *
 * 스토리지를 다시 읽지 않고 **이미 복원된 메모리 값**을 받는다.
 * 스토리지에서 다시 읽으려 하면 그 사이 상태 저장이 한 번만 일어나도
 * 원본이 사라져 버린다 (실제로 그렇게 잃을 뻔했다).
 *
 * 옮긴 뒤 다시 읽어 확인하고, 누락이 있으면 실패로 보고 호출부가 메모리 값을 유지하게 한다.
 */
export async function migrateLegacyEntries(legacy: AnalysisEntry[]): Promise<{ moved: number; ok: boolean }> {
  if (legacy.length === 0) return { moved: 0, ok: true };

  const existing = await loadAllEntries();
  const known = new Set(existing.map((e) => e.id));
  const missing = legacy.filter((e) => e?.id && !known.has(e.id));
  if (missing.length === 0) return { moved: 0, ok: true };

  await saveEntries(missing);

  const after = await loadAllEntries();
  const afterIds = new Set(after.map((e) => e.id));
  const lost = missing.filter((e) => !afterIds.has(e.id));
  if (lost.length > 0) {
    console.warn(`기록 이전 중 ${lost.length}건이 확인되지 않았습니다. 메모리 값을 유지합니다.`);
    return { moved: missing.length - lost.length, ok: false };
  }
  return { moved: missing.length, ok: true };
}

async function insertRow(entry: AnalysisEntry): Promise<void> {
  if (!db) return;
  await db.runAsync('INSERT OR REPLACE INTO entries (id, pet_id, created_at, payload) VALUES (?, ?, ?, ?)', [
    entry.id,
    entry.petId,
    entry.createdAt,
    JSON.stringify(entry),
  ]);
}

/* ---------- 공개 API (백엔드와 무관하게 같은 모양) ---------- */

/**
 * 화면이 쓰는 메모리 거울의 상한.
 * 다이어리·통계는 전부 최근 기록만 보므로, 아주 오래된 것까지 메모리에 올릴 필요가 없다.
 * (오래된 기록도 DB 에는 그대로 남아 있고 백업에도 포함된다)
 */
export const MEMORY_LIMIT = 2000;

export async function loadAllEntries(limit = MEMORY_LIMIT): Promise<AnalysisEntry[]> {
  if (db) {
    const rows = await db.getAllAsync<{ payload: string }>(
      'SELECT payload FROM entries ORDER BY created_at DESC LIMIT ?',
      [limit],
    );
    return rows
      .map((row) => {
        try {
          return JSON.parse(row.payload) as AnalysisEntry;
        } catch {
          return null;
        }
      })
      .filter((entry): entry is AnalysisEntry => entry !== null);
  }
  return (await readFallback()).slice(0, limit);
}

export async function saveEntry(entry: AnalysisEntry): Promise<void> {
  if (db) return insertRow(entry);
  const all = await readFallback();
  await writeFallback([entry, ...all.filter((e) => e.id !== entry.id)]);
}

export async function saveEntries(entries: AnalysisEntry[]): Promise<void> {
  if (db) {
    for (const entry of entries) await insertRow(entry);
    return;
  }
  const all = await readFallback();
  const incoming = new Set(entries.map((e) => e.id));
  await writeFallback([...entries, ...all.filter((e) => !incoming.has(e.id))]);
}

export async function deleteEntry(id: string): Promise<void> {
  if (db) {
    await db.runAsync('DELETE FROM entries WHERE id = ?', [id]);
    return;
  }
  await writeFallback((await readFallback()).filter((e) => e.id !== id));
}

export async function deleteEntriesForPet(petId: string): Promise<void> {
  if (db) {
    await db.runAsync('DELETE FROM entries WHERE pet_id = ?', [petId]);
    return;
  }
  await writeFallback((await readFallback()).filter((e) => e.petId !== petId));
}

export async function clearEntries(): Promise<void> {
  if (db) {
    await db.runAsync('DELETE FROM entries');
    return;
  }
  await writeFallback([]);
}

/** 지금 저장소에 들어 있는 기록 수 (메모리 상한과 무관한 실제 개수) */
export async function countEntries(): Promise<number> {
  if (db) {
    const row = await db.getFirstAsync<{ n: number }>('SELECT COUNT(*) AS n FROM entries');
    return row?.n ?? 0;
  }
  return (await readFallback()).length;
}

/**
 * 기준 시각보다 오래된 기록을 지운다 (보관 정책).
 * 지운 건수를 돌려준다 — 화면에서 "몇 건을 정리했다"를 보여 주려면 필요하다.
 */
export async function pruneEntriesBefore(cutoff: number): Promise<number> {
  if (db) {
    const before = await countEntries();
    await db.runAsync('DELETE FROM entries WHERE created_at < ?', [cutoff]);
    const after = await countEntries();
    return Math.max(0, before - after);
  }
  const all = await readFallback();
  const kept = all.filter((e) => e.createdAt >= cutoff);
  if (kept.length === all.length) return 0;
  await writeFallback(kept);
  return all.length - kept.length;
}

async function readFallback(): Promise<AnalysisEntry[]> {
  if (!storage) return [];
  try {
    const raw = await storage.getItem(FALLBACK_KEY);
    const parsed = raw ? (JSON.parse(raw) as AnalysisEntry[]) : [];
    // 읽을 때 정렬한다. SQLite 쪽은 ORDER BY 로 최신순이 보장되는데
    // 폴백은 넣은 순서 그대로였다 — `limit` 을 걸면 두 저장소가 서로 다른 기록을 잘랐다.
    // (백업 복원처럼 오래된 기록을 뒤늦게 넣는 경로가 있어서 쓰기 순서는 믿을 수 없다)
    return parsed.sort((a, b) => b.createdAt - a.createdAt);
  } catch {
    return [];
  }
}

async function writeFallback(entries: AnalysisEntry[]): Promise<void> {
  if (!storage) return;
  try {
    if (entries.length === 0) await storage.removeItem(FALLBACK_KEY);
    else await storage.setItem(FALLBACK_KEY, JSON.stringify(entries));
  } catch {
    // 저장 실패로 앱을 멈추지는 않는다 — 메모리 값은 그대로 남아 있다
  }
}

/** 테스트·진단용: 지금 SQLite 를 쓰고 있는지 */
export function isSqliteActive(): boolean {
  return db !== null;
}
