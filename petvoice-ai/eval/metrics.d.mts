/** `metrics.mjs` 는 평가 도구라 순수 JS 로 두되, 쓰는 쪽에서는 타입이 보이게 한다. */

export interface ConsistencyReport {
  clips: number;
  agreement: number | null;
  scoreSpread: number | null;
}

export interface ClassificationReport {
  n: number;
  accuracy: number;
  chance: number;
  aboveChance: number | null;
  matrix: Record<string, Record<string, number>>;
  classes: string[];
}

export interface FlagReport {
  n: number;
  sensitivity: number | null;
  specificity: number | null;
  precision: number | null;
  counts: { tp: number; fp: number; tn: number; fn: number };
}

export interface ControlReport {
  n: number;
  refused: number | null;
  confident: number | null;
  meanTopScore: number | null;
}

export function selfConsistency(
  runsPerClip: { primaryEmotion: string; emotionScores?: Record<string, number> }[][],
): ConsistencyReport;

export function classification(
  pairs: { expected: string; actual: string }[],
  classes?: string[],
): ClassificationReport;

export function flagPerformance(cases: { flagged: boolean; actuallySick: boolean }[]): FlagReport;

export function controlBehavior(
  results: { refused: boolean; primaryEmotion?: string; emotionScores?: Record<string, number> }[],
): ControlReport;
