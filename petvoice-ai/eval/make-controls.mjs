/**
 * 대조군 오디오 생성기.
 *
 * "분석할 것이 없는 소리"를 넣었을 때 모델이 어떻게 답하는지 보려고 만든다.
 * 무음에 대고 "지금 신나 보여요 (75%)" 라고 답한다면,
 * 진짜 짖는 소리에 대한 답도 같은 방식으로 지어낸 것일 수 있다.
 *
 * 실행: node eval/make-controls.mjs
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const OUT = join(dirname(fileURLToPath(import.meta.url)), 'dataset', 'controls');
const RATE = 22050;
const SECONDS = 3;
const N = RATE * SECONDS;

/** 16bit PCM 모노 WAV */
function wav(samples) {
  const data = Buffer.alloc(samples.length * 2);
  for (let i = 0; i < samples.length; i += 1) {
    const clamped = Math.max(-1, Math.min(1, samples[i]));
    data.writeInt16LE(Math.round(clamped * 32767), i * 2);
  }

  const header = Buffer.alloc(44);
  header.write('RIFF', 0);
  header.writeUInt32LE(36 + data.length, 4);
  header.write('WAVE', 8);
  header.write('fmt ', 12);
  header.writeUInt32LE(16, 16);
  header.writeUInt16LE(1, 20); // PCM
  header.writeUInt16LE(1, 22); // 모노
  header.writeUInt32LE(RATE, 24);
  header.writeUInt32LE(RATE * 2, 28);
  header.writeUInt16LE(2, 32);
  header.writeUInt16LE(16, 34);
  header.write('data', 36);
  header.writeUInt32LE(data.length, 40);
  return Buffer.concat([header, data]);
}

const build = {
  /** 완전한 무음 — 녹음은 됐지만 아무 일도 없었던 경우 */
  silence: () => new Float32Array(N),

  /** 정상 소음 (에어컨·환풍기) — 소리는 있지만 발성이 아니다 */
  'steady-noise': () => {
    const out = new Float32Array(N);
    for (let i = 0; i < N; i += 1) out[i] = (Math.random() * 2 - 1) * 0.05;
    return out;
  },

  /** 일정한 톤 — 기계음, 알림음 */
  'pure-tone': () => {
    const out = new Float32Array(N);
    for (let i = 0; i < N; i += 1) out[i] = Math.sin((2 * Math.PI * 1000 * i) / RATE) * 0.2;
    return out;
  },

  /**
   * 사람 말소리 흉내 — 음절 리듬(약 4Hz)으로 진폭이 변하는 대역 잡음.
   * 진짜 말은 아니지만 "짖는 소리가 아닌, 리듬 있는 발성"의 자리를 채운다.
   */
  'speech-like': () => {
    const out = new Float32Array(N);
    let prev = 0;
    for (let i = 0; i < N; i += 1) {
      const noise = Math.random() * 2 - 1;
      prev = prev * 0.85 + noise * 0.15; // 저역 통과 → 사람 목소리 대역에 가깝게
      const syllable = Math.max(0, Math.sin((2 * Math.PI * 4 * i) / RATE));
      out[i] = prev * syllable * 0.6;
    }
    return out;
  },

  /** 손뼉·문 닫힘 같은 단발 충격음 — 짧고 크지만 발성이 아니다 */
  impulse: () => {
    const out = new Float32Array(N);
    for (const at of [0.4, 1.5, 2.3]) {
      const start = Math.floor(at * RATE);
      for (let i = 0; i < RATE * 0.05; i += 1) {
        out[start + i] = (Math.random() * 2 - 1) * Math.exp(-i / (RATE * 0.008));
      }
    }
    return out;
  },
};

mkdirSync(OUT, { recursive: true });
for (const [name, make] of Object.entries(build)) {
  const file = join(OUT, `${name}.wav`);
  writeFileSync(file, wav(make()));
  console.log(`${name}.wav`);
}
console.log(`\n${Object.keys(build).length}개 대조군을 ${OUT} 에 만들었습니다.`);
