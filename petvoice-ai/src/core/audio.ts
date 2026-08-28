/**
 * 녹음 음량(미터링) 분석.
 *
 * 오디오를 디코딩하지 않고 `expo-av` 가 녹음 중에 주는 dBFS 값만 본다.
 * 가볍고, 무엇보다 **서버로 보내기 전에** 판단할 수 있다 —
 * 무음이나 사람 목소리뿐인 녹음으로 무료 3회를 태우지 않게 하는 게 목적이다.
 */

/** 이 아래면 사실상 무음 (dBFS) */
export const SILENCE_DBFS = -45;
/** 반려동물 소리로 볼 만한 최소 피크 */
export const PEAK_DBFS = -30;

export type RecordingVerdict =
  | { ok: true }
  | { ok: false; reason: 'tooQuiet' | 'noPetSound' };

/**
 * 녹음이 분석할 만한지 판단한다.
 *
 * 두 가지만 본다.
 * 1. 피크가 너무 낮으면 → 아무것도 안 잡힌 것 (`tooQuiet`)
 * 2. 소리는 있는데 **변화가 거의 없으면** → 에어컨·차량 소음 같은 정상 소음이거나
 *    일정한 말소리일 가능성이 크다 (`noPetSound`).
 *    개·고양이 발성은 짧고 급격한 진폭 변화를 만든다.
 */
export function judgeRecording(levels: number[]): RecordingVerdict {
  const usable = levels.filter((v) => Number.isFinite(v));
  if (usable.length < 3) {
    // 미터링을 못 받은 기기에서는 막지 않는다 — 막는 것보다 분석하는 편이 낫다
    return { ok: true };
  }

  const peak = Math.max(...usable);
  const range = dynamicRange(usable);

  // 1) 아무것도 안 잡혔다
  if (peak < SILENCE_DBFS) return { ok: false, reason: 'tooQuiet' };

  // 2) 소리는 있는데 진폭이 거의 일정하다 → 에어컨·차량 소음 같은 배경음
  if (range < 4) return { ok: false, reason: 'noPetSound' };

  // 3) 들리긴 하지만 너무 작고 변화도 미미하다 → 너무 멀리서 녹음했을 가능성
  if (peak < PEAK_DBFS && range < 6) return { ok: false, reason: 'tooQuiet' };

  return { ok: true };
}

/** 상위 10% 와 하위 10% 의 차이 — 튀는 값 하나에 흔들리지 않게 */
export function dynamicRange(levels: number[]): number {
  if (levels.length === 0) return 0;
  const sorted = [...levels].sort((a, b) => a - b);
  const low = sorted[Math.floor(sorted.length * 0.1)];
  const high = sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * 0.9))];
  return high - low;
}

/**
 * dBFS 배열을 0~1 로 눌러 파형 막대 높이로 만든다.
 * `buckets` 개로 균등하게 묶어 길이와 무관하게 같은 폭으로 그린다.
 */
export function normalizeLevels(levels: number[], buckets = 40): number[] {
  const usable = levels.filter((v) => Number.isFinite(v));
  if (usable.length === 0) return [];

  const floor = SILENCE_DBFS - 15; // -60 dBFS 를 바닥으로
  const scale = (v: number) => Math.max(0, Math.min(1, (v - floor) / (0 - floor)));

  const size = Math.max(1, Math.ceil(usable.length / buckets));
  const out: number[] = [];
  for (let i = 0; i < usable.length; i += size) {
    const slice = usable.slice(i, i + size);
    out.push(scale(Math.max(...slice)));
  }
  return out;
}
