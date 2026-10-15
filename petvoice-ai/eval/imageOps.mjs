/**
 * 평가·테스트에서 쓰는 이미지 연산.
 *
 * 앱에서는 ImageManipulator 가 축소를 맡지만, 노드에는 그게 없다.
 * 판정 폭(320px)을 맞추는 게 목적이라 알고리즘의 미세한 차이는 감수한다.
 *
 * 측정 도구와 테스트가 **같은 구현**을 쓰게 하려고 여기 한 곳에 둔다 —
 * 축소 방식이 갈리면 두 곳의 숫자가 달라져 어느 쪽을 믿을지 알 수 없게 된다.
 */

/**
 * 상자 평균으로 줄인다.
 * 최근접 이웃으로 줄이면 픽셀을 건너뛰며 가져와 선명도가 실제보다 높게 나온다 —
 * 흔들린 사진이 선명하다고 나오는 방향이라 여기서는 특히 위험하다.
 */
export function downscaleRgba(rgba, width, height, targetWidth) {
  if (width <= targetWidth) return { data: rgba, width, height };

  const scale = width / targetWidth;
  const outWidth = targetWidth;
  const outHeight = Math.max(1, Math.round(height / scale));
  const out = new Uint8Array(outWidth * outHeight * 4);

  for (let y = 0; y < outHeight; y += 1) {
    const y0 = Math.floor(y * scale);
    const y1 = Math.max(Math.min(height, Math.floor((y + 1) * scale)), y0 + 1);
    for (let x = 0; x < outWidth; x += 1) {
      const x0 = Math.floor(x * scale);
      const x1 = Math.max(Math.min(width, Math.floor((x + 1) * scale)), x0 + 1);
      let r = 0;
      let g = 0;
      let b = 0;
      let n = 0;
      for (let sy = y0; sy < y1; sy += 1) {
        for (let sx = x0; sx < x1; sx += 1) {
          const o = (sy * width + sx) * 4;
          r += rgba[o];
          g += rgba[o + 1];
          b += rgba[o + 2];
          n += 1;
        }
      }
      const o = (y * outWidth + x) * 4;
      out[o] = r / n;
      out[o + 1] = g / n;
      out[o + 2] = b / n;
      out[o + 3] = 255;
    }
  }
  return { data: out, width: outWidth, height: outHeight };
}
