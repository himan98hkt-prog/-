import { parseAnalysis, AnalysisParseError } from '../core/analysis';
import { assessHealth } from '../core/health';
import { MODEL_CHAIN } from '../core/models';
import { buildPrompt, RESPONSE_SCHEMA } from '../core/prompt';
import { ApiError, codeFromStatus } from './errors';
import type { AnalyzeInput, AnalyzeOutput } from './proxy';

/**
 * 테스트 모드에서만 쓰는 직접 호출 경로.
 *
 * 서버 프록시(`proxy.ts`)와 **같은 프롬프트·같은 파서·같은 이상징후 판정**을 쓴다.
 * 그래야 여기서 본 결과가 실제 앱에서 볼 결과와 같다.
 * 다른 점은 하나뿐이다 — 키가 서버가 아니라 이 기기에 있다는 것.
 *
 * `testKey.ts` 의 빌드 플래그가 꺼져 있으면 이 함수는 호출되지 않는다.
 */
export async function analyzeDirect(input: AnalyzeInput, apiKey: string): Promise<AnalyzeOutput> {
  const prompt = buildPrompt({
    pet: input.pet,
    mediaType: input.mediaType,
    context: input.context,
    locale: input.locale,
  });

  const body = JSON.stringify({
    contents: [
      {
        role: 'user',
        parts: [{ inline_data: { mime_type: input.mediaType, data: input.mediaBase64 } }, { text: prompt }],
      },
    ],
    generationConfig: {
      responseMimeType: 'application/json',
      responseSchema: RESPONSE_SCHEMA,
      temperature: 0.4,
    },
  });

  let lastStatus = 0;
  for (const model of MODEL_CHAIN) {
    let response: Response;
    try {
      response = await fetch(
        `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`,
        { method: 'POST', headers: { 'Content-Type': 'application/json' }, body },
      );
    } catch {
      throw new ApiError('network', '구글 서버에 연결하지 못했습니다.');
    }

    if (response.ok) {
      const payload = await response.json();
      const text =
        payload?.candidates?.[0]?.content?.parts?.map((p: { text?: string }) => p.text ?? '').join('') ?? '';
      if (!text) throw new ApiError('parse', '빈 응답을 받았습니다.');

      try {
        const result = parseAnalysis(text, input.fallbacks);
        return { result, health: assessHealth(result, input.pet.type, input.contextTags ?? []) };
      } catch (error) {
        if (error instanceof AnalysisParseError) throw new ApiError('parse', error.message);
        throw error;
      }
    }

    lastStatus = response.status;
    // 이 모델을 못 쓰는 경우에만 다음 후보로 내려간다
    if (response.status !== 404 && response.status !== 400) break;
  }

  throw new ApiError(codeFromStatus(lastStatus), `Gemini 호출 실패 (HTTP ${lastStatus})`, lastStatus);
}
