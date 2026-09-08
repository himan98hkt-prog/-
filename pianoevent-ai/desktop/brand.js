/**
 * 상품 이름 — 껍데기(Electron) 쪽 사본.
 *
 * 본체는 `lib/brand.ts` 다. 껍데기는 TypeScript 를 읽지 못해 여기에 한 벌 더 둔다.
 * 둘이 어긋나면 창 제목만 옛 이름으로 남는 일이 생기므로, 같은지 검사로 묶어 두었다
 * (`tests/desktop.test.ts`).
 */
module.exports = {
  name: '연주회 매니저',
  nameEn: 'RECITAL MANAGER',
  maker: '아첼쌤',
  makerEn: 'accelssam',
  full: '연주회 매니저 · 아첼쌤',
  slug: 'RecitalManager',
}
