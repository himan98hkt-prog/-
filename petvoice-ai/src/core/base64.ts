/**
 * base64 → 바이트.
 *
 * React Native 에는 `atob` 이 있는 런타임도 있고 없는 런타임도 있다.
 * 사진 사전 필터가 그것 때문에 기기마다 켜졌다 꺼졌다 하면 안 되므로
 * 20줄짜리 디코더를 직접 둔다. 노드에서 Buffer 와 대조해 검증한다.
 */

const ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';

const LOOKUP = (() => {
  const table = new Int16Array(128).fill(-1);
  for (let i = 0; i < ALPHABET.length; i += 1) table[ALPHABET.charCodeAt(i)] = i;
  return table;
})();

/** 잘못된 문자는 건너뛴다 (줄바꿈이 섞인 base64 가 흔하다) */
export function decodeBase64(input: string): Uint8Array {
  const clean = input.replace(/=+$/, '');
  const out = new Uint8Array(Math.floor((clean.length * 3) / 4));

  let acc = 0;
  let bits = 0;
  let written = 0;

  for (let i = 0; i < clean.length; i += 1) {
    const code = clean.charCodeAt(i);
    const value = code < 128 ? LOOKUP[code] : -1;
    if (value < 0) continue;

    acc = (acc << 6) | value;
    bits += 6;
    if (bits >= 8) {
      bits -= 8;
      out[written] = (acc >> bits) & 0xff;
      written += 1;
    }
  }

  return written === out.length ? out : out.subarray(0, written);
}
