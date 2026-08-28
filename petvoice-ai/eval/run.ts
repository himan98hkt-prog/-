/**
 * 분석 정확도 평가기.
 *
 * 앱이 쓰는 **바로 그 프롬프트와 파서, 이상 징후 판정**을 그대로 불러 쓴다.
 * 평가용으로 따로 구현하면 "평가에서는 잘 나오는데 앱에서는 다르다"가 된다.
 *
 *   npx vite-node eval/run.ts -- --provider mock          # 도구가 도는지 확인
 *   npx vite-node eval/run.ts -- --provider gemini --repeat 3
 *
 * gemini 로 돌리려면 개발자 기기에 GEMINI_API_KEY 가 있어야 한다.
 * (앱에는 절대 넣지 않는다 — 이건 평가 도구다)
 */
import { readFileSync, existsSync } from 'node:fs';
import { basename, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { AnalysisParseError, parseAnalysis } from '../src/core/analysis';
import { assessHealth } from '../src/core/health';
import { MODEL_CHAIN } from '../src/core/models';
import { buildPrompt, RESPONSE_SCHEMA } from '../src/core/prompt';
import type { AnalysisResult, ContextTag, PetProfile } from './types';
import { classification, controlBehavior, flagPerformance, selfConsistency } from './metrics.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));

interface Clip {
  file: string;
  /** 이 소리가 난 실제 상황 (보호자가 라벨) */
  contextTag?: ContextTag;
  /** 대조군이면 true — 정답이 없고, "지어내는지"만 본다 */
  control?: boolean;
  /** 수의사 확인 결과 (있으면 이상 징후 플래그 성능을 잴 수 있다) */
  actuallySick?: boolean;
  pet?: Partial<PetProfile>;
  note?: string;
}

interface Run {
  clip: Clip;
  result: AnalysisResult | null;
  health: ReturnType<typeof assessHealth> | null;
  refused: boolean;
  error?: string;
}

const args = process.argv.slice(2);
const provider = valueOf('--provider') ?? 'mock';
const repeat = Number(valueOf('--repeat') ?? '1');
const manifestPath = valueOf('--manifest') ?? join(HERE, 'dataset', 'manifest.json');

function valueOf(flag: string): string | undefined {
  const index = args.indexOf(flag);
  return index >= 0 ? args[index + 1] : undefined;
}

const DEFAULT_PET: PetProfile = {
  id: 'eval',
  name: '평가용',
  type: 'DOG',
  createdAt: 0,
};

async function askGemini(prompt: string, base64: string, mime: string): Promise<string> {
  const key = process.env.GEMINI_API_KEY;
  if (!key) throw new Error('GEMINI_API_KEY 가 없습니다. 평가는 개발자 기기에서 돌립니다.');

  let lastError = '';
  for (const model of MODEL_CHAIN) {
    const response = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${key}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents: [{ role: 'user', parts: [{ inline_data: { mime_type: mime, data: base64 } }, { text: prompt }] }],
          generationConfig: {
            responseMimeType: 'application/json',
            responseSchema: RESPONSE_SCHEMA,
            // 평가는 모델의 기본 성향을 봐야 하므로 앱과 같은 온도를 쓴다
            temperature: 0.4,
          },
        }),
      },
    );
    if (response.ok) {
      const body = await response.json();
      return (
        body?.candidates?.[0]?.content?.parts?.map((p: { text?: string }) => p.text ?? '').join('') ?? ''
      );
    }
    lastError = `${model}: HTTP ${response.status}`;
    if (response.status !== 404 && response.status !== 400) break;
  }
  throw new Error(lastError);
}

/** 도구 자체가 도는지 확인하기 위한 가짜 응답. 모델 성능과는 무관하다. */
function mockAnswer(): string {
  const pool = ['playful', 'anxiety', 'alert', 'hungry'];
  const primary = pool[Math.floor(Math.random() * pool.length)];
  return JSON.stringify({
    petVoiceMessage: '(mock)',
    primaryEmotion: primary,
    emotionScores: { [primary]: 70, curious: 20, happy: 10 },
    behaviorAnalysis: '(mock) 평가 도구 점검용 응답입니다.',
    actionGuide: '(mock)',
  });
}

async function analyzeOnce(clip: Clip): Promise<Run> {
  const pet = { ...DEFAULT_PET, ...clip.pet } as PetProfile;
  const path = join(HERE, 'dataset', clip.file);
  const mime = clip.file.endsWith('.wav') ? 'audio/wav' : clip.file.endsWith('.mp3') ? 'audio/mpeg' : 'audio/m4a';

  const prompt = buildPrompt({ pet, mediaType: 'audio/m4a', context: '', locale: 'ko' });

  try {
    const raw =
      provider === 'gemini' ? await askGemini(prompt, readFileSync(path).toString('base64'), mime) : mockAnswer();
    const result = parseAnalysis(raw);
    return {
      clip,
      result,
      health: assessHealth(result, pet.type, []),
      refused: false,
    };
  } catch (error) {
    // 모델이 "판단할 수 없다"고 물러선 경우와 진짜 오류를 구분한다
    const refused = error instanceof AnalysisParseError;
    return { clip, result: null, health: null, refused, error: String(error) };
  }
}

async function main() {
  if (!existsSync(manifestPath)) {
    console.error(`manifest 가 없습니다: ${manifestPath}`);
    console.error('eval/dataset/manifest.example.json 을 복사해서 시작하세요.');
    process.exit(1);
  }

  const clips = JSON.parse(readFileSync(manifestPath, 'utf8')) as Clip[];
  console.log(`클립 ${clips.length}개 · ${repeat}회 반복 · provider=${provider}\n`);

  const runsPerClip: Run[][] = [];
  for (const clip of clips) {
    const runs: Run[] = [];
    for (let i = 0; i < repeat; i += 1) {
      runs.push(await analyzeOnce(clip));
      process.stdout.write('.');
    }
    runsPerClip.push(runs);
  }
  console.log('\n');

  const labelled = runsPerClip.filter((runs) => runs[0].clip.contextTag && !runs[0].clip.control);
  const controls = runsPerClip.filter((runs) => runs[0].clip.control);
  const withVerdict = runsPerClip.filter((runs) => typeof runs[0].clip.actuallySick === 'boolean');

  console.log('── 자기 일관성 ' + '─'.repeat(46));
  if (repeat < 2) {
    console.log('  --repeat 2 이상으로 돌려야 잴 수 있습니다.\n');
  } else {
    const consistency = selfConsistency(
      runsPerClip.map((runs) => runs.filter((r) => r.result).map((r) => r.result)),
    );
    console.log(`  같은 클립 재분석 시 1위 감정 일치율 : ${pct(consistency.agreement)}`);
    console.log(`  1위 감정 점수의 회차 간 표준편차     : ${consistency.scoreSpread ?? '-'}`);
    console.log('  → 여기가 낮으면 정확도를 논하는 것 자체가 무의미합니다.\n');
  }

  console.log('── 대조군 반응 ' + '─'.repeat(46));
  if (controls.length === 0) {
    console.log('  대조군 클립이 없습니다. node eval/make-controls.mjs 로 만드세요.\n');
  } else {
    const behavior = controlBehavior(
      controls.flatMap((runs) =>
        runs.map((r) => ({ refused: r.refused, primaryEmotion: r.result?.primaryEmotion, emotionScores: r.result?.emotionScores })),
      ),
    );
    console.log(`  판단 불가로 물러선 비율 : ${pct(behavior.refused)}  (높을수록 정직)`);
    console.log(`  60% 이상 확신한 비율    : ${pct(behavior.confident)}  (높을수록 지어냄)`);
    console.log(`  평균 1위 감정 점수      : ${behavior.meanTopScore ?? '-'}`);
    console.log('  → 무음·소음에 확신할수록, 진짜 짖는 소리의 답도 믿기 어렵습니다.\n');
  }

  console.log('── 상황 분류 정확도 ' + '─'.repeat(41));
  if (labelled.length === 0) {
    console.log('  라벨된 클립이 없습니다. 실제 녹음과 상황 라벨이 필요합니다.\n');
  } else {
    // 감정 → 상황 태그로 옮겨 비교한다 (완벽한 대응은 아니지만 방향성은 본다)
    const pairs = labelled.map((runs) => ({
      expected: runs[0].clip.contextTag,
      actual: emotionToContext(runs[0].result?.primaryEmotion),
    }));
    const stats = classification(pairs);
    console.log(`  표본 ${stats.n}건 · 정확도 ${pct(stats.accuracy)} · 우연 수준 ${pct(stats.chance)}`);
    console.log(`  우연 초과 정도 : ${stats.aboveChance ?? '-'}  (0 이면 찍는 것과 같음)`);
    console.log('  혼동 행렬 (행=실제, 열=예측):');
    console.table(stats.matrix);
    console.log('');
  }

  console.log('── 이상 징후 플래그 ' + '─'.repeat(41));
  if (withVerdict.length === 0) {
    console.log('  수의사 확인 라벨이 없습니다. 이 앱에서 가장 중요한 지표인데 아직 잴 수 없습니다.\n');
  } else {
    const flags = flagPerformance(
      withVerdict.map((runs) => ({
        flagged: runs[0].health?.level === 'vet',
        actuallySick: Boolean(runs[0].clip.actuallySick),
      })),
    );
    console.log(`  민감도(놓치지 않는 비율) : ${pct(flags.sensitivity)}`);
    console.log(`  특이도(헛다리 안 짚는 비율) : ${pct(flags.specificity)}`);
    console.log(`  정밀도(병원 권고가 맞을 확률) : ${pct(flags.precision)}`);
    console.log(`  ${JSON.stringify(flags.counts)}\n`);
  }

  const failures = runsPerClip.flat().filter((r) => r.error && !r.refused);
  if (failures.length > 0) {
    console.log(`── 오류 ${failures.length}건 ` + '─'.repeat(46));
    for (const f of failures.slice(0, 5)) console.log(`  ${basename(f.clip.file)}: ${f.error}`);
  }
}

/** 감정 1위를 상황 태그로 옮기는 대략적 대응 — 분류 정확도를 보기 위한 근사다 */
function emotionToContext(emotion?: string): string {
  const map: Record<string, ContextTag> = {
    anxiety: 'separation',
    sad: 'separation',
    alert: 'stranger',
    territorial: 'stranger',
    anger: 'stranger',
    fear: 'vet',
    pain: 'vet',
    hungry: 'meal',
    playful: 'walk',
    happy: 'walk',
    affection: 'petting',
    relaxed: 'petting',
    curious: 'window',
    attentionSeeking: 'meal',
  };
  return emotion ? (map[emotion] ?? 'unknown') : 'unknown';
}

function pct(value: number | null): string {
  return value == null ? '-' : `${Math.round(value * 100)}%`;
}

void main();
