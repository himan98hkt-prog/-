import { describe, expect, it } from 'vitest';
import { classification, controlBehavior, flagPerformance, selfConsistency } from '../eval/metrics.mjs';

describe('selfConsistency', () => {
  it('매번 같은 답이면 1.0', () => {
    const result = selfConsistency([
      [
        { primaryEmotion: 'playful', emotionScores: { playful: 70 } },
        { primaryEmotion: 'playful', emotionScores: { playful: 70 } },
        { primaryEmotion: 'playful', emotionScores: { playful: 70 } },
      ],
    ]);
    expect(result.agreement).toBe(1);
    expect(result.scoreSpread).toBe(0);
  });

  it('답이 갈리면 낮아지고, 점수 흔들림도 잡아낸다', () => {
    const result = selfConsistency([
      [
        { primaryEmotion: 'playful', emotionScores: { playful: 80 } },
        { primaryEmotion: 'anxiety', emotionScores: { anxiety: 40 } },
      ],
    ]);
    expect(result.agreement).toBe(0.5);
    expect(result.scoreSpread).toBe(20);
  });

  it('한 번만 돌린 클립은 비교 대상이 아니라 제외한다', () => {
    expect(selfConsistency([[{ primaryEmotion: 'playful', emotionScores: {} }]])).toMatchObject({ clips: 0 });
  });
});

describe('classification', () => {
  const classes = ['separation', 'stranger', 'meal', 'play'];

  it('정확도와 우연 수준을 함께 낸다', () => {
    const result = classification(
      [
        { expected: 'separation', actual: 'separation' },
        { expected: 'stranger', actual: 'stranger' },
        { expected: 'meal', actual: 'play' },
        { expected: 'play', actual: 'play' },
      ],
      classes,
    );
    expect(result.accuracy).toBe(0.75);
    expect(result.chance).toBe(0.25);
    expect(result.aboveChance).toBeCloseTo(0.667, 2);
  });

  it('찍는 것과 같으면 우연 초과가 0 이다', () => {
    const result = classification(
      [
        { expected: 'separation', actual: 'separation' },
        { expected: 'stranger', actual: 'meal' },
        { expected: 'meal', actual: 'play' },
        { expected: 'play', actual: 'stranger' },
      ],
      classes,
    );
    expect(result.accuracy).toBe(0.25);
    expect(result.aboveChance).toBe(0);
  });

  it('혼동 행렬로 어디서 헷갈리는지 볼 수 있다', () => {
    const result = classification(
      [
        { expected: 'separation', actual: 'stranger' },
        { expected: 'separation', actual: 'stranger' },
      ],
      classes,
    );
    expect(result.matrix.separation.stranger).toBe(2);
    expect(result.matrix.separation.separation).toBe(0);
  });
});

describe('flagPerformance', () => {
  it('놓친 것과 헛다리를 나눠서 본다', () => {
    const result = flagPerformance([
      { flagged: true, actuallySick: true },
      { flagged: true, actuallySick: true },
      { flagged: false, actuallySick: true },
      { flagged: true, actuallySick: false },
      { flagged: false, actuallySick: false },
      { flagged: false, actuallySick: false },
    ]);
    expect(result.sensitivity).toBeCloseTo(0.667, 2);
    expect(result.specificity).toBeCloseTo(0.667, 2);
    expect(result.precision).toBeCloseTo(0.667, 2);
  });

  it('전부 괜찮다고만 답해도 특이도는 1 이지만 민감도가 0 이라 드러난다', () => {
    const result = flagPerformance([
      { flagged: false, actuallySick: true },
      { flagged: false, actuallySick: false },
      { flagged: false, actuallySick: false },
      { flagged: false, actuallySick: false },
    ]);
    expect(result.sensitivity).toBe(0);
    expect(result.specificity).toBe(1);
  });
});

describe('controlBehavior', () => {
  it('대조군에 확신할수록 나쁜 신호로 잡힌다', () => {
    const result = controlBehavior([
      { refused: false, primaryEmotion: 'playful', emotionScores: { playful: 80 } },
      { refused: false, primaryEmotion: 'anxiety', emotionScores: { anxiety: 75 } },
      { refused: true },
      { refused: false, primaryEmotion: 'curious', emotionScores: { curious: 30 } },
    ]);
    expect(result.refused).toBe(0.25);
    expect(result.confident).toBe(0.5);
    expect(result.meanTopScore).toBeCloseTo(61.7, 1);
  });

  it('전부 물러서면 refused 가 1', () => {
    expect(controlBehavior([{ refused: true }, { refused: true }])).toMatchObject({ refused: 1, confident: 0 });
  });
});
