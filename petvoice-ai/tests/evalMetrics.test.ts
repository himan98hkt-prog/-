import { describe, expect, it } from 'vitest';
import {
  classification,
  compareFeltVsMeasured,
  controlBehavior,
  flagPerformance,
  perClassAccuracy,
  selfConsistency,
} from '../eval/metrics.mjs';

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
    expect(controlBehavior([{ refused: true }, { refused: true }])).toMatchObject({
      refused: 1,
      confident: 0,
    });
  });
});

describe('perClassAccuracy', () => {
  it('혼동 행렬에서 상황별 정확도를 뽑는다', () => {
    const report = classification([
      { expected: 'separation', actual: 'separation' },
      { expected: 'separation', actual: 'separation' },
      { expected: 'separation', actual: 'meal' },
      { expected: 'meal', actual: 'separation' },
    ]);

    const rows = perClassAccuracy(report);
    expect(rows.find((r) => r.id === 'separation')).toEqual({ id: 'separation', rate: 67, total: 3 });
    expect(rows.find((r) => r.id === 'meal')).toEqual({ id: 'meal', rate: 0, total: 1 });
  });

  it('표본이 없는 분류는 빼고 준다', () => {
    const report = classification([{ expected: 'meal', actual: 'meal' }], ['meal', 'walk']);
    expect(perClassAccuracy(report).map((r) => r.id)).toEqual(['meal']);
  });
});

describe('compareFeltVsMeasured', () => {
  const felt = [
    { id: 'separation', rate: 90, total: 10 },
    { id: 'meal', rate: 60, total: 8 },
    { id: 'walk', rate: 100, total: 2 },
  ];
  const measured = [
    { id: 'separation', rate: 40, total: 12 },
    { id: 'meal', rate: 55, total: 9 },
    { id: 'walk', rate: 30, total: 3 },
  ];

  it('체감이 측정보다 많이 앞선 것부터 보여 준다', () => {
    // 이게 가장 위험한 상태다 — 사용자는 맞다고 느끼는데 실제로는 못 맞히고 있다
    const rows = compareFeltVsMeasured(felt, measured);
    expect(rows[0].id).toBe('separation');
    expect(rows[0].gap).toBe(50);
  });

  it('표본이 적은 쪽은 뒤로 밀고 표시만 한다', () => {
    const rows = compareFeltVsMeasured(felt, measured);
    const walk = rows.find((r) => r.id === 'walk');
    expect(walk?.enough).toBe(false);
    expect(rows.filter((r) => r.enough).every((r) => rows.indexOf(r) < rows.indexOf(walk!))).toBe(true);
  });

  it('한쪽에만 있는 항목도 빠뜨리지 않는다', () => {
    const rows = compareFeltVsMeasured([{ id: 'vet', rate: 80, total: 9 }], []);
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({ id: 'vet', measuredRate: null, gap: null, enough: false });
  });

  it('양쪽이 비어 있으면 빈 목록', () => {
    expect(compareFeltVsMeasured([], [])).toEqual([]);
  });
});
