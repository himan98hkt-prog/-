import { describe, expect, it } from 'vitest';
import { decodeBase64 } from '../src/core/base64';

/** 노드의 Buffer 를 정답지로 삼는다 */
function expected(text: string): Uint8Array {
  return new Uint8Array(Buffer.from(text, 'base64'));
}

describe('decodeBase64', () => {
  it.each([
    ['빈 문자열', ''],
    ['패딩 하나', 'aGVsbG8='],
    ['패딩 둘', 'aGVsbG8gd28='],
    ['패딩 없음', 'aGVsbG8gd29y'],
    ['+ 와 / 포함', '++//++//'],
  ])('%s', (_name, input) => {
    expect(decodeBase64(input)).toEqual(expected(input));
  });

  it('임의의 바이트를 왕복시켜도 같다', () => {
    for (let len = 0; len < 40; len += 1) {
      const bytes = Uint8Array.from({ length: len }, (_, i) => (i * 37 + len * 11) % 256);
      const text = Buffer.from(bytes).toString('base64');
      expect(decodeBase64(text)).toEqual(bytes);
    }
  });

  it('줄바꿈이 섞여 있어도 읽는다', () => {
    const bytes = Uint8Array.from({ length: 200 }, (_, i) => i % 256);
    const wrapped = Buffer.from(bytes)
      .toString('base64')
      .replace(/(.{20})/g, '$1\n');
    expect(decodeBase64(wrapped)).toEqual(bytes);
  });

  it('알 수 없는 문자는 건너뛴다', () => {
    expect(decodeBase64('aGVs*bG8=')).toEqual(expected('aGVsbG8='));
  });
});
