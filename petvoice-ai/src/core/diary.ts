import { sortedEmotions } from './analysis';
import { DAY_MS, dayKey, startOfDay } from './date';
import { emotionMeta } from './emotions';
import { msg, type Message } from './message';
import type { AnalysisEntry, EmotionKey, EmotionScores, HealthLevel } from './types';

/** "우리 아이 감정 다이어리" — 날짜별 집계와 주간 리포트 계산 */

export interface DaySummary {
  /** `2026-08-28` */
  key: string;
  /** 그 날 자정의 timestamp */
  date: number;
  count: number;
  /** 그 날을 대표하는 감정 (점수 합이 가장 큰 것) */
  dominant: EmotionKey | null;
  /** 그 날 기록 중 가장 높은 이상 징후 단계 */
  level: HealthLevel;
  /** 긍정 감정 비율 0~100 */
  positiveRatio: number;
}

const LEVEL_RANK: Record<HealthLevel, number> = { none: 0, watch: 1, vet: 2 };

function maxLevel(a: HealthLevel, b: HealthLevel): HealthLevel {
  return LEVEL_RANK[b] > LEVEL_RANK[a] ? b : a;
}

/** 여러 분석의 감정 점수를 합산한다 (정규화하지 않은 원시 합) */
export function accumulateScores(entries: AnalysisEntry[]): EmotionScores {
  const total: EmotionScores = {};
  for (const entry of entries) {
    for (const [key, value] of Object.entries(entry.result.emotionScores) as [EmotionKey, number][]) {
      total[key] = (total[key] ?? 0) + value;
    }
  }
  return total;
}

/** 긍정 감정이 차지하는 비율(%) */
export function positiveRatio(scores: EmotionScores): number {
  const entries = Object.entries(scores) as [EmotionKey, number][];
  const sum = entries.reduce((acc, [, v]) => acc + v, 0);
  if (sum <= 0) return 0;
  const positive = entries.reduce(
    (acc, [key, v]) => (emotionMeta(key).tone === 'positive' ? acc + v : acc),
    0,
  );
  return Math.round((positive / sum) * 100);
}

/** 날짜별 요약. 최신 날짜가 앞에 온다. */
export function summarizeDays(entries: AnalysisEntry[]): DaySummary[] {
  const buckets = new Map<string, AnalysisEntry[]>();
  for (const entry of entries) {
    const key = dayKey(entry.createdAt);
    const list = buckets.get(key);
    if (list) list.push(entry);
    else buckets.set(key, [entry]);
  }

  const summaries: DaySummary[] = [];
  for (const [key, list] of buckets) {
    const scores = accumulateScores(list);
    const ranked = sortedEmotions(scores);
    summaries.push({
      key,
      date: startOfDay(list[0].createdAt),
      count: list.length,
      dominant: ranked[0]?.key ?? null,
      level: list.reduce<HealthLevel>((acc, e) => maxLevel(acc, e.health.level), 'none'),
      positiveRatio: positiveRatio(scores),
    });
  }
  return summaries.sort((a, b) => b.date - a.date);
}

export interface CalendarCell {
  /** 이 달에 속하지 않는 빈 칸이면 null */
  day: number | null;
  key: string | null;
  summary: DaySummary | null;
  isToday: boolean;
}

/**
 * 캘린더 화면용 6주 × 7일 격자.
 * `month` 는 1~12.
 */
export function monthGrid(
  year: number,
  month: number,
  entries: AnalysisEntry[],
  now = Date.now(),
): CalendarCell[][] {
  const first = new Date(year, month - 1, 1);
  const daysInMonth = new Date(year, month, 0).getDate();

  // 한 달을 그리는 데 전체 기록을 요약할 이유가 없다.
  // 하루 요약은 그 날 기록에만 달려 있으므로, 이 달 밖은 아예 보지 않는다.
  // (기록 2000건에서 5.4ms → 0.3ms. 달을 넘길 때마다 도는 계산이라 체감 차이가 크다)
  const from = first.getTime();
  const to = new Date(year, month, 1).getTime();
  const inMonth = entries.filter((e) => e.createdAt >= from && e.createdAt < to);

  const byKey = new Map(summarizeDays(inMonth).map((s) => [s.key, s]));
  const leading = first.getDay();
  const todayKey = dayKey(now);

  const cells: CalendarCell[] = [];
  for (let i = 0; i < leading; i += 1) cells.push({ day: null, key: null, summary: null, isToday: false });
  for (let day = 1; day <= daysInMonth; day += 1) {
    const key = dayKey(new Date(year, month - 1, day));
    cells.push({ day, key, summary: byKey.get(key) ?? null, isToday: key === todayKey });
  }
  while (cells.length % 7 !== 0) cells.push({ day: null, key: null, summary: null, isToday: false });

  const weeks: CalendarCell[][] = [];
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7));
  return weeks;
}

export interface WeeklyStats {
  from: number;
  to: number;
  count: number;
  /** 이번 주 감정 분포 (합 100 으로 정규화) */
  distribution: { key: EmotionKey; share: number }[];
  dominant: EmotionKey | null;
  positiveRatio: number;
  /** 지난주 대비 긍정 비율 변화 (%p). 지난주 기록이 없으면 null */
  positiveDelta: number | null;
  vetCount: number;
  watchCount: number;
  /** 가장 자주 기록한 상황 */
  topContext: string | null;
  /** 활동한 날 수 */
  activeDays: number;
}

function windowStats(entries: AnalysisEntry[], from: number, to: number) {
  const list = entries.filter((e) => e.createdAt >= from && e.createdAt < to);
  return { list, scores: accumulateScores(list) };
}

/** 최근 7일(오늘 포함) 통계. Pro 주간 행동 리포트의 입력. */
export function weeklyStats(entries: AnalysisEntry[], now = Date.now()): WeeklyStats {
  const to = startOfDay(now) + DAY_MS;
  const from = to - 7 * DAY_MS;
  const prevFrom = from - 7 * DAY_MS;

  const { list, scores } = windowStats(entries, from, to);
  const prev = windowStats(entries, prevFrom, from);

  const totalScore = Object.values(scores).reduce<number>((a, b) => a + (b ?? 0), 0);
  const distribution = sortedEmotions(scores).map(({ key, score }) => ({
    key,
    share: totalScore > 0 ? Math.round((score / totalScore) * 100) : 0,
  }));

  const contextCount = new Map<string, number>();
  for (const entry of list) {
    const ctx = entry.context.trim();
    if (ctx) contextCount.set(ctx, (contextCount.get(ctx) ?? 0) + 1);
  }
  const topContext = [...contextCount.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? null;

  const current = positiveRatio(scores);

  return {
    from,
    to,
    count: list.length,
    distribution,
    dominant: distribution[0]?.key ?? null,
    positiveRatio: current,
    positiveDelta: prev.list.length > 0 ? current - positiveRatio(prev.scores) : null,
    vetCount: list.filter((e) => e.health.level === 'vet').length,
    watchCount: list.filter((e) => e.health.level === 'watch').length,
    topContext,
    activeDays: new Set(list.map((e) => dayKey(e.createdAt))).size,
  };
}

/** 통계를 한 줄로 요약한 번역 참조. (모델 호출 없이도 리포트 상단에 바로 쓴다) */
export function weeklyHeadline(stats: WeeklyStats): Message {
  if (stats.count === 0) return msg('diary.headline.empty');
  if (!stats.dominant) return msg('diary.headline.plain');

  const meta = emotionMeta(stats.dominant);
  const params = { emoji: meta.emoji, emotion: `@${meta.labelKey}` };

  if (stats.positiveDelta == null) return msg('diary.headline.noCompare', params);
  if (stats.positiveDelta > 0) return msg('diary.headline.up', { ...params, delta: stats.positiveDelta });
  if (stats.positiveDelta < 0)
    return msg('diary.headline.down', { ...params, delta: Math.abs(stats.positiveDelta) });
  return msg('diary.headline.flat', params);
}

/**
 * 주간 리포트 프롬프트에 넣을 요약 텍스트.
 * 모델에게 주는 입력이라 사용자 화면이 아니고, 감정 이름은 호출부가 번역해 넘긴다.
 */
export function buildWeeklyDigest(
  entries: AnalysisEntry[],
  labelOf: (key: string) => string,
  now = Date.now(),
): string {
  const stats = weeklyStats(entries, now);
  if (stats.count === 0) return '기록 없음';

  const lines: string[] = [
    `- 총 분석 ${stats.count}회 / 기록한 날 ${stats.activeDays}일`,
    `- 감정 분포: ${stats.distribution.map((d) => `${labelOf(emotionMeta(d.key).labelKey)} ${d.share}%`).join(', ')}`,
    `- 긍정 감정 비율 ${stats.positiveRatio}%${stats.positiveDelta == null ? '' : ` (지난주 대비 ${stats.positiveDelta >= 0 ? '+' : ''}${stats.positiveDelta}%p)`}`,
    `- 이상 징후: 병원 권고 ${stats.vetCount}회, 관찰 필요 ${stats.watchCount}회`,
  ];
  if (stats.topContext) lines.push(`- 가장 자주 기록한 상황: ${stats.topContext}`);

  const recent = entries
    .filter((e) => e.createdAt >= stats.from && e.createdAt < stats.to)
    .sort((a, b) => a.createdAt - b.createdAt)
    .slice(-10)
    .map(
      (e) =>
        `  · ${dayKey(e.createdAt)} [${e.context || '-'}] ${labelOf(emotionMeta(e.result.primaryEmotion).labelKey)} — ${e.result.behaviorAnalysis}`,
    );
  if (recent.length) lines.push('- 최근 기록:', ...recent);

  return lines.join('\n');
}
