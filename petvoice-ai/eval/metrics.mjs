/**
 * 평가 지표.
 *
 * 앱 코드가 아니라 개발 도구다. 다만 여기서 숫자를 잘못 세면
 * "정확하다/부정확하다"는 판단 자체가 틀어지므로 순수 함수로 두고 테스트한다.
 */

/**
 * 자기 일관성 — 같은 클립을 여러 번 분석했을 때 같은 답이 나오는가.
 *
 * 라벨이 하나도 없어도 오늘 당장 잴 수 있고, 여기서 낮으면
 * 정확도를 논하는 것 자체가 무의미하다. 모델이 매번 다른 말을 한다는 뜻이니까.
 */
export function selfConsistency(runsPerClip) {
  const perClip = runsPerClip
    .filter((runs) => runs.length >= 2)
    .map((runs) => {
      const counts = new Map();
      for (const run of runs) counts.set(run.primaryEmotion, (counts.get(run.primaryEmotion) ?? 0) + 1);
      const top = Math.max(...counts.values());

      // 1위 감정 점수가 회차마다 얼마나 흔들리는지
      const scores = runs.map((run) => run.emotionScores?.[run.primaryEmotion] ?? 0);
      const mean = scores.reduce((a, b) => a + b, 0) / scores.length;
      const variance = scores.reduce((sum, v) => sum + (v - mean) ** 2, 0) / scores.length;

      return { agreement: top / runs.length, spread: Math.sqrt(variance) };
    });

  if (perClip.length === 0) return { clips: 0, agreement: null, scoreSpread: null };

  return {
    clips: perClip.length,
    agreement: round(perClip.reduce((sum, c) => sum + c.agreement, 0) / perClip.length),
    scoreSpread: round(perClip.reduce((sum, c) => sum + c.spread, 0) / perClip.length),
  };
}

/**
 * 분류 정확도와 혼동 행렬.
 * `chance` 는 무작위로 찍었을 때의 기대 정확도 — 이걸 못 넘으면 아무 의미가 없다.
 */
export function classification(pairs, classes) {
  const labels = classes ?? [...new Set(pairs.flatMap((p) => [p.expected, p.actual]))].sort();
  const matrix = {};
  for (const row of labels) {
    matrix[row] = Object.fromEntries(labels.map((col) => [col, 0]));
  }

  let correct = 0;
  for (const { expected, actual } of pairs) {
    if (matrix[expected] && actual in matrix[expected]) matrix[expected][actual] += 1;
    if (expected === actual) correct += 1;
  }

  const n = pairs.length;
  const chance = labels.length > 0 ? 1 / labels.length : 0;
  const accuracy = n > 0 ? correct / n : 0;

  return {
    n,
    accuracy: round(accuracy),
    chance: round(chance),
    // 우연을 넘어선 정도. 0 이면 찍는 것과 같고, 1 이면 완벽.
    aboveChance: n > 0 && chance < 1 ? round((accuracy - chance) / (1 - chance)) : null,
    matrix,
    classes: labels,
  };
}

/**
 * 이상 징후 플래그의 민감도·특이도.
 *
 * 정확도 하나로 보면 안 된다. 아픈 개가 드물기 때문에
 * "전부 괜찮다"고만 답해도 정확도는 높게 나온다.
 */
export function flagPerformance(cases) {
  let tp = 0;
  let fp = 0;
  let tn = 0;
  let fn = 0;
  for (const { flagged, actuallySick } of cases) {
    if (flagged && actuallySick) tp += 1;
    else if (flagged && !actuallySick) fp += 1;
    else if (!flagged && !actuallySick) tn += 1;
    else fn += 1;
  }

  return {
    n: cases.length,
    // 아픈 아이를 놓치지 않는 비율 — 이 앱에서 가장 중요하다
    sensitivity: tp + fn > 0 ? round(tp / (tp + fn)) : null,
    // 멀쩡한 아이를 병원에 보내지 않는 비율 — 낮으면 사용자가 앱을 믿지 않게 된다
    specificity: tn + fp > 0 ? round(tn / (tn + fp)) : null,
    // 병원 가라고 했을 때 실제로 문제가 있을 확률
    precision: tp + fp > 0 ? round(tp / (tp + fp)) : null,
    counts: { tp, fp, tn, fn },
  };
}

/**
 * 대조군 반응 — 분석할 것이 없는 입력에 모델이 어떻게 답하는가.
 *
 * 무음·사람 목소리·TV 소리를 넣었는데 확신에 찬 감정을 내놓는다면,
 * 진짜 짖는 소리에 대한 답도 같은 방식으로 지어낸 것일 수 있다.
 * **정답이 없어도 잴 수 있는 가장 강력한 검사다.**
 */
export function controlBehavior(results) {
  const total = results.length;
  if (total === 0) return { n: 0, refused: null, confident: null, meanTopScore: null };

  const refused = results.filter((r) => r.refused).length;
  const answered = results.filter((r) => !r.refused);
  const topScores = answered.map((r) => r.emotionScores?.[r.primaryEmotion] ?? 0);
  const confident = topScores.filter((score) => score >= 60).length;

  return {
    n: total,
    // 판단할 수 없다고 물러선 비율 (높을수록 정직하다)
    refused: round(refused / total),
    // 대조군인데도 60% 이상 확신한 비율 (높을수록 지어낸다)
    confident: round(confident / total),
    meanTopScore:
      topScores.length > 0 ? round(topScores.reduce((a, b) => a + b, 0) / topScores.length, 1) : null,
  };
}

function round(value, digits = 3) {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}
