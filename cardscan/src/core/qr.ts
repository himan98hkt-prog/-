// QR 코드 행렬 — 내 명함/받은 명함을 vCard QR 로 보여 주면 상대가 카메라로 찍어 바로 연락처에 저장한다.
import qrcode from 'qrcode-generator';

/**
 * 문자열 → UTF-8 바이트를 한 글자에 한 바이트씩 담은 문자열.
 * qrcode-generator 의 기본 변환은 글자마다 하위 8비트만 쓰므로, 미리 UTF-8 로 바꿔 넘기면
 * 한글 vCard 도 정확히 인코딩된다 (라이브러리 빌드(ESM/CJS)마다 UTF-8 지원이 달라 직접 처리).
 */
export function utf8ByteString(s: string): string {
  let out = '';
  for (const ch of s) {
    const cp = ch.codePointAt(0)!;
    if (cp < 0x80) out += String.fromCharCode(cp);
    else if (cp < 0x800) out += String.fromCharCode(0xc0 | (cp >> 6), 0x80 | (cp & 0x3f));
    else if (cp < 0x10000) out += String.fromCharCode(0xe0 | (cp >> 12), 0x80 | ((cp >> 6) & 0x3f), 0x80 | (cp & 0x3f));
    else out += String.fromCharCode(0xf0 | (cp >> 18), 0x80 | ((cp >> 12) & 0x3f), 0x80 | ((cp >> 6) & 0x3f), 0x80 | (cp & 0x3f));
  }
  return out;
}

/** 한글이 들어간 vCard 도 읽히도록 UTF-8 바이트로 인코딩한 QR 행렬 */
export function qrMatrix(text: string): boolean[][] {
  const qr = qrcode(0, 'M');
  qr.addData(utf8ByteString(text), 'Byte');
  qr.make();
  const n = qr.getModuleCount();
  return Array.from({ length: n }, (_, r) => Array.from({ length: n }, (_, c) => qr.isDark(r, c)));
}

/** 한 줄의 연속된 검은 칸을 [시작, 길이] 묶음으로 — 화면에 그릴 View 수를 줄인다 */
export function darkRuns(row: boolean[]): [number, number][] {
  const runs: [number, number][] = [];
  let start = -1;
  row.forEach((dark, i) => {
    if (dark && start < 0) start = i;
    if (!dark && start >= 0) {
      runs.push([start, i - start]);
      start = -1;
    }
  });
  if (start >= 0) runs.push([start, row.length - start]);
  return runs;
}
