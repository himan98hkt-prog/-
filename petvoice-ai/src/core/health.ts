import { emotionMeta, type ContextTag } from './emotions';
import { msg, raw, type Message } from './message';
import type {
  AnalysisEntry,
  AnalysisResult,
  EmotionKey,
  HealthAssessment,
  HealthLevel,
  PetType,
} from './types';

/**
 * 경쟁 앱과의 차별점: 재미로 끝내지 않고 이상 징후를 잡아 준다.
 * 여기서는 "진단"을 하지 않는다. 병원에 가 볼 근거를 만들어 줄 뿐이다.
 */

/** 통증 점수가 이 값 이상이면 곧바로 병원 안내 */
export const PAIN_VET_THRESHOLD = 20;
/** 불안 점수가 이 값 이상이고 분리 상황이면 분리불안 경고 */
export const ANXIETY_WATCH_THRESHOLD = 45;

/**
 * 분석 텍스트에서 잡아내는 의학적 신호.
 * 모델은 사용자 언어로 답하므로 한국어·영어·일본어 표현을 한 패턴에 모아 둔다.
 */
const MEDICAL_SIGNS: { key: string; patterns: RegExp }[] = [
  {
    key: 'health.sign.pain',
    patterns: /통증|아파|아픈|끙끙|신음|비명|pain(ful)?|whimper|whine in pain|痛み|痛が|うめき/i,
  },
  {
    key: 'health.sign.gait',
    patterns:
      /절뚝|파행|다리를 들|잘 걷지 못|일어서기 힘|limp(ing)?|lame(ness)?|difficulty (standing|walking)|びっこ|歩きにく|立ち上が/i,
  },
  {
    key: 'health.sign.digestive',
    patterns:
      /구토|토하|설사|혈변|식욕\s*(부진|저하|없)|vomit|diarrh|bloody stool|loss of appetite|嘔吐|下痢|食欲/i,
  },
  {
    key: 'health.sign.respiratory',
    patterns:
      /기침|재채기|호흡\s*(곤란|이상)|숨을 헐떡|그렁|cough|sneez|labored breathing|wheez|咳|くしゃみ|呼吸/i,
  },
  {
    key: 'health.sign.urinary',
    patterns:
      /배뇨|소변\s*(곤란|을 못)|혈뇨|화장실을 자주|urinat|blood in urine|frequent litter|排尿|血尿|トイレの回数/i,
  },
  {
    key: 'health.sign.skin',
    patterns:
      /과도하게 핥|긁는|털을 뽑|자가\s*손상|피부염|excessive (licking|scratching)|hair loss|self-?traum|舐め続け|かゆ|脱毛/i,
  },
  {
    key: 'health.sign.vetMentioned',
    patterns: /수의사|동물병원|병원\s*(방문|진료|확인)|veterinarian|see a vet|veterinary|獣医|動物病院/i,
  },
];

/** 상황 태그별 행동 교정 팁 */
const CONTEXT_TIPS: Partial<Record<ContextTag, string>> = {
  separation: 'health.tip.separation',
  stranger: 'health.tip.stranger',
  vet: 'health.tip.vet',
  meal: 'health.tip.meal',
  night: 'health.tip.night',
  carrier: 'health.tip.carrier',
};

const SPECIES_TIPS: Record<PetType, string> = {
  DOG: 'health.tip.dog',
  CAT: 'health.tip.cat',
};

function negativeTotal(result: AnalysisResult): number {
  return Object.entries(result.emotionScores).reduce((sum, [key, value]) => {
    return emotionMeta(key as EmotionKey).tone === 'negative' ? sum + (value ?? 0) : sum;
  }, 0);
}

function score(result: AnalysisResult, key: EmotionKey): number {
  return result.emotionScores[key] ?? 0;
}

/**
 * 분석 한 건에 대한 이상 징후 판정.
 * - `vet`   : 동물병원 방문 권유
 * - `watch` : 며칠 지켜보며 행동 교정
 * - `none`  : 특이사항 없음
 */
export function assessHealth(
  result: AnalysisResult,
  petType: PetType,
  contextTags: ContextTag[] = [],
): HealthAssessment {
  const reasons: Message[] = [];
  const tipKeys: string[] = [];

  // 단계는 숫자로 누적한 뒤 마지막에 한 번 이름으로 바꾼다.
  const RANK: Record<HealthLevel, number> = { none: 0, watch: 1, vet: 2 };
  let rank = RANK.none;
  const bump = (next: HealthLevel) => {
    if (RANK[next] > rank) rank = RANK[next];
  };

  const pain = score(result, 'pain');
  if (pain >= PAIN_VET_THRESHOLD) {
    reasons.push(msg('health.reason.pain', { score: pain }));
    bump('vet');
  } else if (pain > 0) {
    reasons.push(msg('health.reason.painMild', { score: pain }));
    bump('watch');
  }

  if (result.healthAlert) {
    // 모델이 사용자 언어로 쓴 문장이라 번역하지 않고 그대로 보여 준다.
    reasons.push(raw(result.healthAlert));
    bump('vet');
  }

  const haystack = `${result.behaviorAnalysis} ${result.actionGuide} ${result.healthAlert ?? ''}`;
  for (const sign of MEDICAL_SIGNS) {
    if (sign.patterns.test(haystack)) {
      reasons.push(msg('health.reason.sign', { sign: `@${sign.key}` }));
      bump('vet');
    }
  }

  const anxiety = score(result, 'anxiety');
  if (anxiety >= ANXIETY_WATCH_THRESHOLD) {
    const separation = contextTags.includes('separation');
    reasons.push(
      separation
        ? msg('health.reason.separationAnxiety', { score: anxiety })
        : msg('health.reason.anxiety', { score: anxiety }),
    );
    bump('watch');
  }

  const tension =
    score(result, 'fear') + score(result, 'anger') + score(result, 'alert') + score(result, 'territorial');
  if (tension >= 55) {
    reasons.push(msg('health.reason.tension', { score: tension }));
    bump('watch');
  }

  if (score(result, 'sad') >= 45) {
    reasons.push(msg('health.reason.sad', { score: score(result, 'sad') }));
    bump('watch');
  }

  if (rank === RANK.none && negativeTotal(result) >= 70) {
    reasons.push(msg('health.reason.negativeMajority'));
    bump('watch');
  }

  const level: HealthLevel = rank === RANK.vet ? 'vet' : rank === RANK.watch ? 'watch' : 'none';

  if (level === 'vet') {
    tipKeys.push('health.tip.visitSoon', 'health.tip.bringRecording');
  }
  if (level !== 'none') {
    for (const tag of contextTags) {
      const tip = CONTEXT_TIPS[tag];
      if (tip) tipKeys.push(tip);
    }
    tipKeys.push(SPECIES_TIPS[petType]);
  }

  return { level, reasons, tips: [...new Set(tipKeys)].map((key) => msg(key)) };
}

export interface HistoryRisk {
  level: HealthLevel;
  message: Message;
  /** 근거가 된 기록 수 */
  count: number;
}

/**
 * 한 건은 우연일 수 있다. 최근 기록에서 같은 신호가 반복되면 강도를 올린다.
 * (히스토리 화면 상단 배너에 사용)
 */
export function assessHistoryRisk(
  entries: AnalysisEntry[],
  now = Date.now(),
  windowDays = 7,
): HistoryRisk | null {
  const since = now - windowDays * 24 * 60 * 60 * 1000;
  const recent = entries.filter((e) => e.createdAt >= since && e.createdAt <= now);
  if (recent.length === 0) return null;

  const vetCount = recent.filter((e) => e.health.level === 'vet').length;
  if (vetCount >= 2) {
    return {
      level: 'vet',
      count: vetCount,
      message: msg('health.risk.repeatedVet', { days: windowDays, count: vetCount }),
    };
  }

  const anxious = recent.filter(
    (e) => (e.result.emotionScores.anxiety ?? 0) >= ANXIETY_WATCH_THRESHOLD,
  ).length;
  if (anxious >= 3) {
    return {
      level: 'watch',
      count: anxious,
      message: msg('health.risk.repeatedAnxiety', { days: windowDays, count: anxious }),
    };
  }

  if (vetCount === 1) {
    return { level: 'watch', count: 1, message: msg('health.risk.singleVet') };
  }

  return null;
}
