import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  clearEntries,
  countEntries,
  deleteEntriesForPet,
  deleteEntry,
  initEntryStore,
  isSqliteActive,
  loadAllEntries,
  migrateLegacyEntries,
  pruneEntriesBefore,
  resetEntryStore,
  saveEntries,
  saveEntry,
} from '../src/data/entries';
import type { AnalysisEntry } from '../src/core/types';
import { fakeSqliteModule, memoryStorage } from './helpers/fakeSqlite';

/**
 * 저장소 계층 테스트.
 *
 * 여기서 한 번 기록을 통째로 잃을 뻔했고, 그때는 브라우저로 직접 눌러 보다가 잡았다.
 * 그 방식으로는 다음에 또 놓친다 — 그래서 이전·폴백·검증 경로를 테스트로 못 박는다.
 */

const FALLBACK_KEY = 'petvoice-entries-v1';

function entry(id: string, createdAt: number, petId = 'p1'): AnalysisEntry {
  return {
    id,
    petId,
    createdAt,
    mediaKind: 'audio',
    context: '',
    result: {
      petVoiceMessage: '메시지',
      primaryEmotion: 'happy',
      emotionScores: { happy: 100 },
      behaviorAnalysis: '분석',
      actionGuide: '가이드',
    },
    health: { level: 'none', reasons: [], tips: [] },
  };
}

beforeEach(() => {
  resetEntryStore();
});

describe('저장소 선택', () => {
  it('SQLite 가 왕복 검사를 통과하면 그걸 쓴다', async () => {
    const { module } = fakeSqliteModule();
    await initEntryStore({ sqlite: module, storage: memoryStorage() });
    expect(isSqliteActive()).toBe(true);
  });

  it('왕복 검사에서 읽기가 실패하면 SQLite 를 쓰지 않는다', async () => {
    // 반쯤 동작하는 저장소가 제일 위험하다 — 열렸다고 믿으면 조용히 다 잃는다
    const { module } = fakeSqliteModule({ probeFails: true });
    await initEntryStore({ sqlite: module, storage: memoryStorage() });
    expect(isSqliteActive()).toBe(false);
  });

  it('네이티브 모듈이 없으면 폴백으로 내려간다', async () => {
    await initEntryStore({ sqlite: null, storage: memoryStorage() });
    expect(isSqliteActive()).toBe(false);
  });

  it('여는 도중 예외가 나도 앱을 세우지 않는다', async () => {
    const { module } = fakeSqliteModule({ openThrows: true });
    await initEntryStore({ sqlite: module, storage: memoryStorage() });
    expect(isSqliteActive()).toBe(false);
  });

  it('두 번 불러도 한 번만 연다', async () => {
    const { module } = fakeSqliteModule();
    const open = vi.spyOn(module, 'openDatabaseAsync' as never);
    await initEntryStore({ sqlite: module, storage: memoryStorage() });
    await initEntryStore({ sqlite: module, storage: memoryStorage() });
    expect(open).toHaveBeenCalledTimes(1);
  });
});

describe.each([
  ['SQLite', () => ({ sqlite: fakeSqliteModule().module, storage: memoryStorage() })],
  ['폴백(AsyncStorage)', () => ({ sqlite: null, storage: memoryStorage() })],
])('기본 동작 — %s', (_name, deps) => {
  it('저장한 순서와 무관하게 최신 기록이 앞에 온다', async () => {
    await initEntryStore(deps());
    await saveEntry(entry('a', 100));
    await saveEntry(entry('c', 300));
    await saveEntry(entry('b', 200));

    const all = await loadAllEntries();
    expect(all.map((e) => e.id)).toEqual(['c', 'b', 'a']);
  });

  it('같은 id 를 다시 저장하면 덮어쓴다 (피드백 표시가 이 경로다)', async () => {
    await initEntryStore(deps());
    await saveEntry(entry('a', 100));
    await saveEntry({ ...entry('a', 100), feedback: 'up' });

    const all = await loadAllEntries();
    expect(all).toHaveLength(1);
    expect(all[0].feedback).toBe('up');
  });

  it('limit 을 넘겨 받은 만큼만 읽는다', async () => {
    await initEntryStore(deps());
    await saveEntries([entry('a', 100), entry('b', 200), entry('c', 300)]);
    expect(await loadAllEntries(2)).toHaveLength(2);
  });

  it('한 건 삭제', async () => {
    await initEntryStore(deps());
    await saveEntries([entry('a', 100), entry('b', 200)]);
    await deleteEntry('a');
    expect((await loadAllEntries()).map((e) => e.id)).toEqual(['b']);
  });

  it('반려동물을 지우면 그 아이 기록만 사라진다', async () => {
    await initEntryStore(deps());
    await saveEntries([entry('a', 100, 'p1'), entry('b', 200, 'p2')]);
    await deleteEntriesForPet('p1');
    expect((await loadAllEntries()).map((e) => e.id)).toEqual(['b']);
  });

  it('전체 초기화', async () => {
    await initEntryStore(deps());
    await saveEntries([entry('a', 100), entry('b', 200)]);
    await clearEntries();
    expect(await loadAllEntries()).toEqual([]);
    expect(await countEntries()).toBe(0);
  });

  it('보관 기간이 지난 기록만 지운다', async () => {
    await initEntryStore(deps());
    await saveEntries([entry('old', 1_000), entry('edge', 2_000), entry('new', 3_000)]);

    const removed = await pruneEntriesBefore(2_000);

    expect(removed).toBe(1);
    // 경계값은 남긴다 — "1년 보관"이 364일째 기록을 지우면 안 된다
    expect((await loadAllEntries()).map((e) => e.id)).toEqual(['new', 'edge']);
  });

  it('지울 게 없으면 0 을 돌려준다', async () => {
    await initEntryStore(deps());
    await saveEntries([entry('a', 5_000)]);
    expect(await pruneEntriesBefore(1_000)).toBe(0);
  });
});

describe('예전 기록 이전', () => {
  it('앱 상태 블롭에 있던 기록을 저장소로 옮긴다', async () => {
    const { module, db } = fakeSqliteModule();
    await initEntryStore({ sqlite: module, storage: memoryStorage() });

    const result = await migrateLegacyEntries([entry('a', 100), entry('b', 200)]);

    expect(result).toEqual({ moved: 2, ok: true });
    expect(db.rows.size).toBe(2);
  });

  it('이미 옮긴 건은 다시 쓰지 않는다', async () => {
    const { module } = fakeSqliteModule();
    await initEntryStore({ sqlite: module, storage: memoryStorage() });
    await saveEntry(entry('a', 100));

    expect(await migrateLegacyEntries([entry('a', 100)])).toEqual({ moved: 0, ok: true });
  });

  it('옮길 게 없으면 저장소를 건드리지 않는다', async () => {
    const { module, db } = fakeSqliteModule();
    await initEntryStore({ sqlite: module, storage: memoryStorage() });
    db.statements.length = 0;

    expect(await migrateLegacyEntries([])).toEqual({ moved: 0, ok: true });
    expect(db.statements).toEqual([]);
  });

  it('쓴 뒤 다시 읽어 확인한다 — 조용히 사라지면 실패로 보고한다', async () => {
    // 이게 핵심이다. 쓰기가 무시되는 저장소에서 ok:true 를 돌려주면
    // 호출부가 메모리의 원본을 버리고, 그 순간 기록이 전부 사라진다.
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const { module } = fakeSqliteModule({ writesAreLost: true });
    await initEntryStore({ sqlite: module, storage: memoryStorage() });

    const result = await migrateLegacyEntries([entry('a', 100), entry('b', 200)]);

    expect(result).toEqual({ moved: 0, ok: false });
    warn.mockRestore();
  });

  it('폴백 저장소에서도 같은 계약을 지킨다', async () => {
    const storage = memoryStorage();
    await initEntryStore({ sqlite: null, storage });

    const result = await migrateLegacyEntries([entry('a', 100)]);

    expect(result).toEqual({ moved: 1, ok: true });
    expect(JSON.parse(storage.data.get(FALLBACK_KEY) ?? '[]')).toHaveLength(1);
  });
});

describe('망가진 데이터', () => {
  it('읽을 수 없는 행은 건너뛰고 나머지를 살린다', async () => {
    const { module, db } = fakeSqliteModule();
    await initEntryStore({ sqlite: module, storage: memoryStorage() });
    await saveEntry(entry('good', 200));
    db.rows.set('broken', { id: 'broken', pet_id: 'p1', created_at: 300, payload: '{not json' });

    const all = await loadAllEntries();
    expect(all.map((e) => e.id)).toEqual(['good']);
  });

  it('폴백 값이 JSON 이 아니면 빈 목록으로 시작한다', async () => {
    const storage = memoryStorage({ [FALLBACK_KEY]: '{깨진 값' });
    await initEntryStore({ sqlite: null, storage });
    expect(await loadAllEntries()).toEqual([]);
  });

  it('저장소가 아예 없으면 조용히 빈 목록', async () => {
    await initEntryStore({ sqlite: null, storage: null });
    await saveEntry(entry('a', 100));
    expect(await loadAllEntries()).toEqual([]);
  });
});
