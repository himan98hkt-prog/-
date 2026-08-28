/**
 * `scripts/zip-utf8.mjs` 의 모양.
 *
 * 검사(tests/zip-utf8.test.ts)가 이 파일을 그대로 불러 쓴다 — 실제 묶음을 만드는
 * 그 코드를 검사해야 의미가 있기 때문이다. 그래서 모양만 여기 적어 둔다.
 */

/** `root` 안의 모든 것을 `out` 으로 묶는다. 파일 이름은 UTF-8 표시를 켜서 넣는다 */
export function zipFolder(root: string, out: string): Promise<number>
