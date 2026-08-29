import { describe, expect, it } from 'vitest';
import { dynamicRange, judgeRecording, normalizeLevels, PEAK_DBFS, SILENCE_DBFS } from '../src/core/audio';

/** 개·고양이 발성처럼 급격히 오르내리는 신호 */
const petSound = [-52, -48, -40, -12, -8, -14, -35, -50, -46, -10, -9, -44];
/** 에어컨 소음처럼 평평한 신호 */
const steadyNoise = [-33, -34, -33, -32, -33, -34, -33, -33, -32, -34];
/** 거의 무음 */
const silence = [-58, -60, -57, -59, -61, -58, -60, -59];

describe('judgeRecording', () => {
  it('반려동물 발성은 통과시킨다', () => {
    expect(judgeRecording(petSound)).toEqual({ ok: true });
  });

  it('무음은 막고 무료 횟수를 지킨다', () => {
    expect(judgeRecording(silence)).toEqual({ ok: false, reason: 'tooQuiet' });
  });

  it('진폭 변화가 거의 없는 배경 소음은 막는다', () => {
    expect(judgeRecording(steadyNoise)).toEqual({ ok: false, reason: 'noPetSound' });
  });

  it('미터링을 못 받는 기기에서는 막지 않는다', () => {
    // 막는 것보다 분석해 주는 편이 낫다
    expect(judgeRecording([])).toEqual({ ok: true });
    expect(judgeRecording([-20, -22])).toEqual({ ok: true });
  });

  it('NaN 이 섞여도 안전하게 판단한다', () => {
    expect(judgeRecording([Number.NaN, -10, -50, -12, -48, Number.NaN, -9, -46])).toEqual({ ok: true });
  });

  it('임계값이 뒤바뀌지 않았다', () => {
    expect(SILENCE_DBFS).toBeLessThan(PEAK_DBFS);
  });
});

describe('dynamicRange', () => {
  it('상하위 10% 차이로 재서 튀는 값 하나에 흔들리지 않는다', () => {
    expect(dynamicRange(steadyNoise)).toBeLessThan(4);
    expect(dynamicRange(petSound)).toBeGreaterThan(20);
    expect(dynamicRange([])).toBe(0);
  });
});

describe('normalizeLevels', () => {
  it('0~1 범위로 눌러 준다', () => {
    const bars = normalizeLevels(petSound, 6);
    expect(bars.length).toBeLessThanOrEqual(6);
    for (const value of bars) {
      expect(value).toBeGreaterThanOrEqual(0);
      expect(value).toBeLessThanOrEqual(1);
    }
  });

  it('큰 소리가 더 높은 막대가 된다', () => {
    const [quiet] = normalizeLevels([-55], 1);
    const [loud] = normalizeLevels([-5], 1);
    expect(loud).toBeGreaterThan(quiet);
  });

  it('값이 없으면 빈 배열', () => {
    expect(normalizeLevels([])).toEqual([]);
    expect(normalizeLevels([Number.NaN])).toEqual([]);
  });
});
