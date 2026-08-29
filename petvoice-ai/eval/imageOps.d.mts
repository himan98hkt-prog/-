/** `imageOps.mjs` 는 평가 도구라 순수 JS 로 두되, 쓰는 쪽에서는 타입이 보이게 한다. */

export function downscaleRgba(
  rgba: Uint8Array,
  width: number,
  height: number,
  targetWidth: number,
): { data: Uint8Array; width: number; height: number };
