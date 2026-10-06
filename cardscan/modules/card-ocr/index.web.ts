// 웹(아이폰 홈 화면 웹앱) 용 무료 문자 인식 — Tesseract.js (브라우저 안 WASM, 한국어+영어).
// 안드로이드 앱의 ML Kit 모듈(index.ts)과 같은 모양(줄 + 위치·크기)으로 돌려준다.
// 처음 한 번 인식 엔진·한국어 데이터(수 MB)를 내려받고, 이후에는 브라우저에 캐시된다.
import { createWorker, PSM, type Worker } from 'tesseract.js';
import { joinSpacedHangul } from '../../src/core/cardParser';
import type { OcrLine, OcrResult } from './index';

export type { OcrLine, OcrResult } from './index';

export const isOnDeviceOcrAvailable = typeof window !== 'undefined' && typeof Worker !== 'undefined';

let workerPromise: Promise<Worker> | null = null;
let korWorkerPromise: Promise<Worker> | null = null;

/** 웹앱이 올라간 기본 경로 (예: https://…github.io/-/) — 번들 스크립트 주소에서 알아낸다 */
function appBase(): string {
  const src = document.querySelector<HTMLScriptElement>('script[src*="/_expo/static/js/"]')?.src;
  return src ? src.slice(0, src.indexOf('_expo/')) : `${location.origin}/`;
}

const workerOptions = () => {
  // 엔진·언어 데이터는 scripts/pwa.mjs 가 같은 사이트의 tesseract/ 에 넣어 둔다 (외부 CDN 없이 동작)
  const base = `${appBase()}tesseract/`;
  return { workerPath: `${base}worker.min.js`, corePath: `${base}core`, langPath: `${base}lang`, gzip: true };
};

function makeWorker(langs: string[]): Promise<Worker> {
  return createWorker(langs, 1 /* LSTM_ONLY */, workerOptions()).then(async (w) => {
    // 견본 명함 비교 결과 '한 덩어리 문단' 모드가 회사·이름·주소까지 가장 잘 읽었다
    // (흩어진 텍스트 모드는 주소 줄을, 자동 모드는 윗부분을 놓쳤다)
    await w.setParameters({ tessedit_pageseg_mode: PSM.SINGLE_BLOCK, preserve_interword_spaces: '1' });
    return w;
  });
}

function getWorker(): Promise<Worker> {
  if (!workerPromise) {
    workerPromise = makeWorker(['kor', 'eng']);
    workerPromise.catch(() => {
      workerPromise = null; // 네트워크 실패 등 — 다음 촬영 때 다시 시도
    });
  }
  return workerPromise;
}

/** 한국어 전용 인식기 — 크고 굵은 한글 이름이 영문으로 잘못 읽힌 줄을 다시 읽는 데만 쓴다 */
function getKorWorker(): Promise<Worker> {
  if (!korWorkerPromise) {
    korWorkerPromise = makeWorker(['kor']).then(async (w) => {
      await w.setParameters({ tessedit_pageseg_mode: PSM.SINGLE_LINE });
      return w;
    });
    korWorkerPromise.catch(() => {
      korWorkerPromise = null;
    });
  }
  return korWorkerPromise;
}

/** 앱이 열릴 때 미리 엔진을 내려받아 첫 촬영을 빠르게 */
export function warmUpOcr(): void {
  getWorker().catch(() => {});
}

export async function recognizeText(uri: string): Promise<OcrResult> {
  const worker = await getWorker();
  const { data } = await worker.recognize(uri, {}, { blocks: true, text: true });
  const lines: (OcrLine & { confidence: number })[] = [];
  (data.blocks ?? []).forEach((block, bi) => {
    for (const para of block.paragraphs) {
      for (const line of para.lines) {
        // Tesseract 는 한글을 한 글자씩 띄어 읽기도 한다 ("홍 길 동 팀 장")
        const text = joinSpacedHangul(line.text.replace(/\s+/g, ' ').trim());
        if (!text || line.confidence < 30) continue;
        lines.push({
          text,
          confidence: line.confidence,
          block: bi,
          left: line.bbox.x0,
          top: line.bbox.y0,
          width: line.bbox.x1 - line.bbox.x0,
          height: line.bbox.y1 - line.bbox.y0,
        });
      }
    }
  });
  lines.sort((a, b) => a.top - b.top || a.left - b.left);

  // 한글+영어 모델은 크고 굵은 한글(주로 이름)을 "SUS 영업팀장" 처럼 영문으로 읽곤 한다.
  // 글자가 큰 줄 가운데 짧은 영문 단어가 있고 숫자·@ 가 없는 줄만 한국어 전용 모델로 그 영역을
  // 다시 읽어, 한글이 더 많이 나오고 신뢰도가 더 높으면 바꾼다 (영문 명함의 이름은 그대로 남는다).
  const heights = lines.map((l) => l.height).sort((a, b) => a - b);
  const median = heights[Math.floor(heights.length / 2)] ?? 0;
  const hangulCount = (t: string) => (t.match(/[가-힣]/g) ?? []).length;
  const suspicious = lines.filter(
    (l) => l.height >= median * 1.15 && !/[\d@]/.test(l.text) && /(^|\s)[A-Za-z]{2,5}(\s|$)/.test(l.text) && l.text.split(' ').length <= 4,
  );
  if (suspicious.length) {
    const kor = await getKorWorker();
    for (const l of suspicious) {
      const pad = Math.round(l.height * 0.25);
      const rectangle = { left: Math.max(0, l.left - pad), top: Math.max(0, l.top - pad), width: l.width + pad * 2, height: l.height + pad * 2 };
      const { data: again } = await kor.recognize(uri, { rectangle });
      const text = joinSpacedHangul(again.text.replace(/\s+/g, ' ').trim());
      if (hangulCount(text) >= hangulCount(l.text) + 2 && again.confidence > l.confidence) l.text = text;
    }
  }
  const maxX = Math.max(0, ...lines.map((l) => l.left + l.width));
  const maxY = Math.max(0, ...lines.map((l) => l.top + l.height));
  return { text: data.text, lines: lines.map(({ confidence: _c, ...l }) => l), width: maxX, height: maxY };
}
