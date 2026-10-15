import type { KeyValueStore, SqliteDatabase, SqliteModule } from '../../src/data/entries';

/**
 * 노드에서 도는 저장소 대역(代役).
 *
 * SQLite 를 흉내 내는 게 목적이 아니다 — **우리 코드가 내는 문장만** 해석한다.
 * 알아듣지 못하는 문장이 오면 던져서, 저장소 코드가 조용히 새 쿼리를 추가하면
 * 여기가 먼저 깨지도록 했다. (조용히 통과하는 대역이 제일 쓸모없다)
 */

interface Row {
  id: string;
  pet_id: string;
  created_at: number;
  payload: string;
}

export interface FakeSqliteOptions {
  /** 왕복 검사에서 읽기가 실패하는 기기를 흉내 낸다 (웹 빌드가 이랬다) */
  probeFails?: boolean;
  /** openDatabaseAsync 자체가 터지는 경우 */
  openThrows?: boolean;
  /** 쓰기가 조용히 무시되는 반쯤 동작하는 저장소 */
  writesAreLost?: boolean;
}

export class FakeSqlite implements SqliteDatabase {
  rows = new Map<string, Row>();
  statements: string[] = [];

  constructor(private readonly options: FakeSqliteOptions = {}) {}

  async execAsync(sql: string): Promise<void> {
    this.statements.push(norm(sql));
    if (!/CREATE TABLE/i.test(sql)) throw new Error(`알 수 없는 exec: ${sql}`);
  }

  async runAsync(sql: string, params: unknown[] = []): Promise<void> {
    const q = norm(sql);
    this.statements.push(q);

    if (q.startsWith('INSERT OR REPLACE INTO entries')) {
      const [id, petId, createdAt, payload] = params as [string, string, number, string];
      // 왕복 검사는 통과시킨다 — "열리기는 했는데 그 뒤 쓰기가 새는" 저장소를 흉내 내는 게 목적
      if (this.options.writesAreLost && !id.startsWith('__probe_')) return;
      this.rows.set(id, { id, pet_id: petId, created_at: createdAt, payload });
      return;
    }
    if (q === 'DELETE FROM entries WHERE id = ?') {
      this.rows.delete(params[0] as string);
      return;
    }
    if (q === 'DELETE FROM entries WHERE pet_id = ?') {
      for (const [id, row] of this.rows) if (row.pet_id === params[0]) this.rows.delete(id);
      return;
    }
    if (q === 'DELETE FROM entries WHERE created_at < ?') {
      const cutoff = params[0] as number;
      for (const [id, row] of this.rows) if (row.created_at < cutoff) this.rows.delete(id);
      return;
    }
    if (q === 'DELETE FROM entries') {
      this.rows.clear();
      return;
    }
    throw new Error(`알 수 없는 run: ${q}`);
  }

  async getAllAsync<T>(sql: string, params: unknown[] = []): Promise<T[]> {
    const q = norm(sql);
    this.statements.push(q);
    if (q === 'SELECT payload FROM entries ORDER BY created_at DESC LIMIT ?') {
      return this.sorted()
        .slice(0, params[0] as number)
        .map((row) => ({ payload: row.payload }) as T);
    }
    throw new Error(`알 수 없는 getAll: ${q}`);
  }

  async getFirstAsync<T>(sql: string, params: unknown[] = []): Promise<T | null> {
    const q = norm(sql);
    this.statements.push(q);
    if (q === 'SELECT id FROM entries WHERE id = ?') {
      if (this.options.probeFails) return null;
      const row = this.rows.get(params[0] as string);
      return row ? ({ id: row.id } as T) : null;
    }
    if (q === 'SELECT COUNT(*) AS n FROM entries') {
      return { n: this.rows.size } as T;
    }
    throw new Error(`알 수 없는 getFirst: ${q}`);
  }

  private sorted(): Row[] {
    return [...this.rows.values()].sort((a, b) => b.created_at - a.created_at);
  }
}

export function fakeSqliteModule(options: FakeSqliteOptions = {}): {
  module: SqliteModule;
  db: FakeSqlite;
} {
  const db = new FakeSqlite(options);
  return {
    db,
    module: {
      openDatabaseAsync: async () => {
        if (options.openThrows) throw new Error('네이티브 모듈 없음');
        return db;
      },
    },
  };
}

/** AsyncStorage 대역 */
export function memoryStorage(initial: Record<string, string> = {}): KeyValueStore & {
  data: Map<string, string>;
} {
  const data = new Map(Object.entries(initial));
  return {
    data,
    async getItem(key) {
      return data.get(key) ?? null;
    },
    async setItem(key, value) {
      data.set(key, value);
    },
    async removeItem(key) {
      data.delete(key);
    },
  };
}

function norm(sql: string): string {
  return sql.replace(/\s+/g, ' ').trim();
}
