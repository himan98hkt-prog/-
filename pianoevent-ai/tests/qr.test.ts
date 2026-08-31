import jsQR from 'jsqr'
import { describe, expect, it } from 'vitest'
import { MAX_QR_VERSION, QR_QUIET, makeQr, qrSvgPath, rsEncode } from '@/lib/qr'

/** QR 판을 읽는 도구가 볼 수 있는 그림으로 (검정 1, 흰색 0) */
function toPixels(matrix: boolean[][], scale = 3) {
  const n = matrix.length + QR_QUIET * 2
  const w = n * scale
  const data = new Uint8ClampedArray(w * w * 4).fill(255)
  for (let y = 0; y < w; y += 1) {
    for (let x = 0; x < w; x += 1) {
      const r = Math.floor(y / scale) - QR_QUIET
      const c = Math.floor(x / scale) - QR_QUIET
      const on = r >= 0 && c >= 0 && r < matrix.length && c < matrix.length && matrix[r][c]
      const at = (y * w + x) * 4
      data[at] = data[at + 1] = data[at + 2] = on ? 0 : 255
      data[at + 3] = 255
    }
  }
  return { data, width: w, height: w }
}

function read(text: string): string | null {
  const matrix = makeQr(text)
  if (!matrix) return null
  const img = toPixels(matrix)
  return jsQR(img.data, img.width, img.height)?.data ?? null
}

describe('오류정정 부호', () => {
  it('규격 예제와 같은 값이 나온다 (1판·M, "01234567")', () => {
    const data = Uint8Array.from([
      0x10, 0x20, 0x0c, 0x56, 0x61, 0x80, 0xec, 0x11, 0xec, 0x11, 0xec, 0x11, 0xec, 0x11, 0xec, 0x11,
    ])
    expect([...rsEncode(data, 10)]).toEqual([0xa5, 0x24, 0xd4, 0xc1, 0xed, 0x36, 0xc7, 0x87, 0x2c, 0x55])
  })
})

describe('QR 만들기 — 실제 읽는 도구로 되읽어 본다', () => {
  it('짧은 주소를 담는다', () => {
    const url = 'http://localhost:3000/events/demo/design?pick=fancy'
    expect(read(url)).toBe(url)
  })

  it('학원 안 주소(공유기 주소)도 담는다', () => {
    const url = 'http://192.168.0.15:3000/events/8f3c1a2b-7d44-4e19-9c02-5b6a1e0f7d31/design?pick=plain'
    expect(read(url)).toBe(url)
  })

  it('아주 짧은 글도 담는다', () => {
    expect(read('가')).toBe('가')
  })

  it('한글이 들어가도 그대로 나온다', () => {
    const text = '피아노이벤트 · 세 장 견주기'
    expect(read(text)).toBe(text)
  })

  it('길이를 늘려 가며 판이 올라가도 계속 읽힌다', () => {
    for (const len of [10, 30, 60, 90, 120, 150, 180, 210]) {
      const text = 'A'.repeat(len)
      expect(read(text), `${len}자`).toBe(text)
    }
  })

  it('담을 수 없을 만큼 길면 지어내지 않고 없다고 한다', () => {
    expect(makeQr('A'.repeat(1000))).toBeNull()
  })

  it('판 크기가 규격대로다 — 17 + 4 × 판', () => {
    const small = makeQr('짧게')
    expect(small!.length).toBe(21)
    const big = makeQr('A'.repeat(200))
    expect(big!.length).toBe(17 + 4 * MAX_QR_VERSION)
  })

  it('세 귀퉁이에 찾기 무늬가 있다', () => {
    const m = makeQr('http://localhost:3000/events/demo/design?pick=season')!
    const n = m.length
    for (const [r0, c0] of [
      [0, 0],
      [0, n - 7],
      [n - 7, 0],
    ]) {
      expect(m[r0][c0], `${r0},${c0}`).toBe(true)
      expect(m[r0 + 1][c0 + 1]).toBe(false)
      expect(m[r0 + 3][c0 + 3]).toBe(true)
    }
  })

  it('그림으로 그릴 수 있다', () => {
    const path = qrSvgPath(makeQr('가')!)
    expect(path.startsWith('M')).toBe(true)
    expect(path).toContain('h1v1h-1z')
  })
})
