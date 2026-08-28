import { emotionMeta } from './emotions';
import type { AnalysisEntry, AnalysisResult, EmotionKey, HealthAssessment, HealthLevel, PetType } from './types';

/**
 * 경쟁 앱과의 차별점: 재미로 끝내지 않고 이상 징후를 잡아 준다.
 * 여기서는 "진단"을 하지 않는다. 병원에 가 볼 근거를 만들어 줄 뿐이다.
 */

/** 통증 점수가 이 값 이상이면 곧바로 병원 안내 */
export const PAIN_VET_THRESHOLD = 20;
/** 불안 점수가 이 값 이상이고 분리 상황이면 분리불안 경고 */
export const ANXIETY_WATCH_THRESHOLD = 45;

/** 분석 텍스트에서 잡아내는 의학적 신호. 사람이 읽을 라벨을 같이 들고 다닌다. */
const MEDICAL_SIGNS: { label: string; patterns: RegExp }[] = [
  { label: '통증 의심 신호', patterns: /통증|아파|아픈|끙끙|신음|비명|낑낑대며 몸을/ },
  { label: '보행 이상', patterns: /절뚝|파행|다리를 들|잘 걷지 못|일어서기 힘/ },
  { label: '소화기 증상', patterns: /구토|토하|설사|혈변|식욕\s*(부진|저하|없)/ },
  { label: '호흡기 증상', patterns: /기침|재채기|호흡\s*(곤란|이상)|숨을 헐떡|그렁/ },
  { label: '비뇨기 증상', patterns: /배뇨|소변\s*(곤란|을 못)|혈뇨|화장실을 자주/ },
  { label: '피부·자가 손상', patterns: /과도하게 핥|긁는|털을 뽑|자가\s*손상|피부염/ },
  { label: '수의사 상담 권고', patterns: /수의사|동물병원|병원\s*(방문|진료|확인)/ },
];

/** 분리불안 맥락으로 볼 상황 표현 */
const SEPARATION_CONTEXT = /외출|혼자|집을 비|출근|부재|떨어질|이동장/;

const CONTEXT_TIPS: { match: RegExp; tip: string }[] = [
  { match: /외출|출근|혼자|집을 비/, tip: '외출 전 인사를 짧게 하고, 나가기 15분 전부터 노즈워크 등 혼자 하는 놀이를 주면 분리 신호가 약해집니다.' },
  { match: /낯선|손님|방문/, tip: '낯선 사람이 먼저 다가가지 않게 하고, 아이가 스스로 다가올 때 간식을 주면 경계가 빨리 풉니다.' },
  { match: /병원/, tip: '병원 방문 뒤 하루 이틀은 자극을 줄이고, 좋아하는 담요·간식으로 안전한 공간을 만들어 주세요.' },
  { match: /식사|밥|배고/, tip: '식사량과 시간을 기록해 두면 다음 진료 때 큰 단서가 됩니다.' },
  { match: /새벽|밤/, tip: '자기 전 활동량을 늘리고 취침 직전 소량 급여하면 새벽 각성이 줄어듭니다.' },
];

const SPECIES_TIPS: Record<PetType, string> = {
  DOG: '산책 코스를 바꿔 냄새 맡을 거리를 늘려 주면 스트레스 해소에 효과가 큽니다.',
  CAT: '높이 올라갈 수 있는 캣타워나 숨을 공간을 하나 더 만들어 주면 불안이 눈에 띄게 줄어듭니다.',
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
export function assessHealth(result: AnalysisResult, petType: PetType, context = ''): HealthAssessment {
  const reasons: string[] = [];
  const tips: string[] = [];

  // 단계는 숫자로 누적한 뒤 마지막에 한 번 이름으로 바꾼다.
  // (여러 규칙이 각자 단계를 올리므로 "가장 높은 단계"만 남으면 된다)
  const RANK: Record<HealthLevel, number> = { none: 0, watch: 1, vet: 2 };
  let rank = RANK.none;
  const bump = (next: HealthLevel) => {
    if (RANK[next] > rank) rank = RANK[next];
  };

  const pain = score(result, 'pain');
  if (pain >= PAIN_VET_THRESHOLD) {
    reasons.push(`통증 호소 신호가 ${pain}% 로 감지됐어요.`);
    bump('vet');
  } else if (pain > 0) {
    reasons.push(`약한 통증 신호(${pain}%)가 섞여 있어요.`);
    bump('watch');
  }

  if (result.healthAlert) {
    reasons.push(result.healthAlert);
    bump('vet');
  }

  const haystack = `${result.behaviorAnalysis} ${result.actionGuide} ${result.healthAlert ?? ''}`;
  for (const sign of MEDICAL_SIGNS) {
    if (sign.patterns.test(haystack)) {
      reasons.push(`${sign.label}이(가) 분석 내용에 언급됐어요.`);
      bump('vet');
    }
  }

  const anxiety = score(result, 'anxiety');
  if (anxiety >= ANXIETY_WATCH_THRESHOLD) {
    const separation = SEPARATION_CONTEXT.test(context);
    reasons.push(
      separation
        ? `혼자 남는 상황에서 불안이 ${anxiety}% 로 높아요. 분리불안 초기 신호일 수 있어요.`
        : `불안 감정이 ${anxiety}% 로 높게 나왔어요.`,
    );
    bump('watch');
  }

  const tension = score(result, 'fear') + score(result, 'anger') + score(result, 'alert') + score(result, 'territorial');
  if (tension >= 55) {
    reasons.push(`두려움·경계·분노가 합쳐 ${tension}% 로, 지금은 스트레스가 큰 상태예요.`);
    bump('watch');
  }

  if (score(result, 'sad') >= 45) {
    reasons.push(`무기력·외로움 신호가 ${score(result, 'sad')}% 로 나타났어요.`);
    bump('watch');
  }

  if (rank === RANK.none && negativeTotal(result) >= 70) {
    reasons.push('부정적인 감정이 전체의 70% 를 넘었어요.');
    bump('watch');
  }

  const level: HealthLevel = rank === RANK.vet ? 'vet' : rank === RANK.watch ? 'watch' : 'none';

  if (level === 'vet') {
    tips.push('가능한 24시간 안에 동물병원에서 신체검사를 받아 보세요.');
    tips.push('언제·어떤 상황에서 이 소리가 났는지 기록과 녹음을 함께 보여주면 진료에 큰 도움이 됩니다.');
  }
  if (level !== 'none') {
    for (const rule of CONTEXT_TIPS) {
      if (rule.match.test(context)) tips.push(rule.tip);
    }
    tips.push(SPECIES_TIPS[petType]);
  }

  return { level, reasons, tips: [...new Set(tips)] };
}

export interface HistoryRisk {
  level: HealthLevel;
  message: string;
  /** 근거가 된 기록 수 */
  count: number;
}

/**
 * 한 건은 우연일 수 있다. 최근 기록에서 같은 신호가 반복되면 강도를 올린다.
 * (히스토리 화면 상단 배너에 사용)
 */
export function assessHistoryRisk(entries: AnalysisEntry[], now = Date.now(), windowDays = 7): HistoryRisk | null {
  const since = now - windowDays * 24 * 60 * 60 * 1000;
  const recent = entries.filter((e) => e.createdAt >= since && e.createdAt <= now);
  if (recent.length === 0) return null;

  const vetCount = recent.filter((e) => e.health.level === 'vet').length;
  if (vetCount >= 2) {
    return {
      level: 'vet',
      count: vetCount,
      message: `최근 ${windowDays}일간 병원 확인이 필요한 신호가 ${vetCount}번 감지됐어요. 진료를 미루지 마세요.`,
    };
  }

  const anxious = recent.filter((e) => (e.result.emotionScores.anxiety ?? 0) >= ANXIETY_WATCH_THRESHOLD).length;
  if (anxious >= 3) {
    return {
      level: 'watch',
      count: anxious,
      message: `최근 ${windowDays}일간 불안 신호가 ${anxious}번 나왔어요. 분리불안 행동 교정을 시작할 시점입니다.`,
    };
  }

  if (vetCount === 1) {
    return {
      level: 'watch',
      count: 1,
      message: '최근에 병원 확인이 권장된 기록이 있어요. 증상이 이어지는지 지켜봐 주세요.',
    };
  }

  return null;
}
