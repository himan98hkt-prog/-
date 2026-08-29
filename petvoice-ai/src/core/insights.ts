import { emotionMeta } from './emotions';
import type { AnalysisEntry, EmotionKey } from './types';

/**
 * 모아 둔 것을 볼 수 있게 만든다.
 *
 * "맞아요 / 아니에요"는 수집만 하고 있었고, 분석 품질 지표도 서버에 쌓이기만 했다.
 * 쌓기만 하고 보지 않는 데이터는 없는 것과 같다.
 *
 * 여기서 답하고 싶은 질문은 하나다 — **어떤 상황에서 어떤 감정을 틀리는가.**
 * 그래서 정렬을 "정확도가 낮은 순"으로 둔다. 잘 맞는 항목을 위에 세우면
 * 기분은 좋지만 고칠 곳은 보이지 않는다.
 *
 * 표본이 적은 항목은 숫자를 믿을 수 없다. 지우지는 않고 `enough: false` 로
 * 표시만 해서 화면이 흐리게 그리도록 한다 — 3건 중 1건 틀린 걸 33% 라고
 * 크게 써 두면 없는 문제를 쫓게 된다.
 */

/** 이 정도는 모여야 비율을 읽을 만하다 */
export const MIN_SAMPLES = 5;

export interface RatingBucket {
  /** 감정 키, 상황 번역 키, 또는 매체 종류 */
  id: string;
  up: number;
  down: number;
  total: number;
  /** 맞았다고 한 비율 0~100. 표본이 없으면 null */
  rate: number | null;
  enough: boolean;
}

export interface FeedbackSummary {
  /** 전체 분석 수 */
  analyses: number;
  /** 그중 평가를 남긴 수 */
  rated: number;
  up: number;
  down: number;
  /** 전체 정확도(자기 보고) 0~100. 평가가 없으면 null */
  rate: number | null;
  byEmotion: RatingBucket[];
  byContext: RatingBucket[];
  byMedia: RatingBucket[];
}

function bucketize(rows: { id: string; feedback: 'up' | 'down' }[]): RatingBucket[] {
  const map = new Map<string, { up: number; down: number }>();
  for (const row of rows) {
    const bucket = map.get(row.id) ?? { up: 0, down: 0 };
    bucket[row.feedback] += 1;
    map.set(row.id, bucket);
  }

  return [...map.entries()]
    .map(([id, { up, down }]) => {
      const total = up + down;
      return {
        id,
        up,
        down,
        total,
        rate: total > 0 ? Math.round((up / total) * 100) : null,
        enough: total >= MIN_SAMPLES,
      };
    })
    .sort((a, b) => {
      // 표본이 충분한 것부터, 그중에서도 정확도가 낮은 것부터
      if (a.enough !== b.enough) return a.enough ? -1 : 1;
      if (a.rate !== b.rate) return (a.rate ?? 100) - (b.rate ?? 100);
      return b.total - a.total;
    });
}

export function summarizeFeedback(entries: readonly AnalysisEntry[]): FeedbackSummary {
  const rated = entries.filter((e): e is AnalysisEntry & { feedback: 'up' | 'down' } => Boolean(e.feedback));

  const up = rated.filter((e) => e.feedback === 'up').length;
  const down = rated.length - up;

  return {
    analyses: entries.length,
    rated: rated.length,
    up,
    down,
    rate: rated.length > 0 ? Math.round((up / rated.length) * 100) : null,
    byEmotion: bucketize(
      rated.map((e) => ({
        id: emotionMeta(e.result.primaryEmotion as EmotionKey).labelKey,
        feedback: e.feedback,
      })),
    ),
    // 프리셋으로 고른 상황만 센다. 직접 입력한 문구는 사람마다 달라 묶이지 않는다.
    byContext: bucketize(
      rated.filter((e) => e.contextKey).map((e) => ({ id: e.contextKey as string, feedback: e.feedback })),
    ),
    byMedia: bucketize(rated.map((e) => ({ id: `media.${e.mediaKind}`, feedback: e.feedback }))),
  };
}

/* ---------- 분석 품질 지표 (S1 의 기기 쪽 거울) ---------- */

/**
 * 서버에도 같은 지표를 보내지만, 그건 우리가 보는 것이고
 * 사용자는 자기 기기에서 무슨 일이 있었는지 볼 방법이 없었다.
 * 최근 것만 들고 있으면 충분하다 — 평생 누적은 아무것도 말해 주지 않는다.
 */
export const METRIC_WINDOW = 50;

export interface AnalysisAttempt {
  at: number;
  ok: boolean;
  /** 걸린 시간(ms) */
  ms: number;
  /** 실패했다면 ApiError 코드 */
  code?: string;
}

export interface QualitySummary {
  attempts: number;
  failures: number;
  /** 실패율 0~100 */
  failureRate: number | null;
  /** 성공한 요청의 중앙값 소요 시간(ms). 평균은 한 번의 45초 타임아웃에 끌려간다 */
  medianMs: number | null;
  /** 많이 난 실패부터 */
  topCodes: { code: string; count: number }[];
}

export function summarizeQuality(attempts: readonly AnalysisAttempt[]): QualitySummary {
  if (attempts.length === 0) {
    return { attempts: 0, failures: 0, failureRate: null, medianMs: null, topCodes: [] };
  }

  const failures = attempts.filter((a) => !a.ok);
  const durations = attempts
    .filter((a) => a.ok)
    .map((a) => a.ms)
    .sort((a, b) => a - b);

  const counts = new Map<string, number>();
  for (const failure of failures) {
    const code = failure.code ?? 'unknown';
    counts.set(code, (counts.get(code) ?? 0) + 1);
  }

  return {
    attempts: attempts.length,
    failures: failures.length,
    failureRate: Math.round((failures.length / attempts.length) * 100),
    medianMs: durations.length > 0 ? durations[Math.floor(durations.length / 2)] : null,
    topCodes: [...counts.entries()]
      .map(([code, count]) => ({ code, count }))
      .sort((a, b) => b.count - a.count),
  };
}

/** 새 시도를 넣고 창을 유지한다 */
export function pushAttempt(
  history: readonly AnalysisAttempt[],
  attempt: AnalysisAttempt,
  window = METRIC_WINDOW,
): AnalysisAttempt[] {
  return [attempt, ...history].slice(0, window);
}
