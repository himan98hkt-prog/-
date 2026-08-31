/**
 * QR 코드 만들기 — 붙여 쓰는 꾸러미 없이.
 *
 * 종이에 뽑은 세 장 중 하나에 동그라미를 치신 뒤, 그것을 화면에서 다시 찾아 고르셔야 한다.
 * 종이에서 화면으로 돌아오는 길이 손밖에 없었다. QR 하나면 그 길이 없어진다.
 *
 * **왜 직접 쓰는가.** 이 프로그램은 인터넷 없이 도는 것이 약속이다. 인터넷에 있는
 * QR 만들어 주는 자리(api.qrserver.com 같은 것)를 쓰면 연주회장에서 안 뜬다.
 * 게다가 그 주소에는 학원 이름과 행사 이름이 실려 나간다 — 밖으로 나가면 안 되는 것들이다.
 *
 * 담는 것은 **바이트 방식 · 오류정정 M · 1~10판**까지다. 우리가 담을 것은 주소 한 줄이라
 * 그 안에서 넉넉히 들어간다. 넘치면 지어내지 않고 `null` 을 준다.
 *
 * 맞게 만들어졌는지는 짐작하지 않는다 — `tests/qr.test.ts` 에서 **실제 QR 읽는 도구로
 * 되읽어** 같은 글자가 나오는지 본다.
 */

/* ── GF(256) — 오류정정 부호가 사는 셈판 ────────────────────────────────── */

const EXP = new Uint8Array(512)
const LOG = new Uint8Array(256)

;(() => {
  let x = 1
  for (let i = 0; i < 255; i += 1) {
    EXP[i] = x
    LOG[x] = i
    x <<= 1
    if (x & 0x100) x ^= 0x11d
  }
  for (let i = 255; i < 512; i += 1) EXP[i] = EXP[i - 255]
})()

function mul(a: number, b: number): number {
  return a === 0 || b === 0 ? 0 : EXP[LOG[a] + LOG[b]]
}

/** (x - α⁰)(x - α¹)… — 오류정정 부호를 만드는 뼈대 */
function generatorPoly(degree: number): Uint8Array {
  let poly = new Uint8Array([1])
  for (let i = 0; i < degree; i += 1) {
    const next = new Uint8Array(poly.length + 1)
    for (let j = 0; j < poly.length; j += 1) {
      next[j] ^= poly[j]
      next[j + 1] ^= mul(poly[j], EXP[i])
    }
    poly = next
  }
  return poly
}

/** 자료 뒤에 붙는 오류정정 부호 */
export function rsEncode(data: Uint8Array, ecLen: number): Uint8Array {
  const gen = generatorPoly(ecLen)
  const res = new Uint8Array(data.length + ecLen)
  res.set(data)
  for (let i = 0; i < data.length; i += 1) {
    const factor = res[i]
    if (factor === 0) continue
    for (let j = 0; j < gen.length; j += 1) res[i + j] ^= mul(gen[j], factor)
  }
  return res.slice(data.length)
}

/* ── 판(version)마다 정해진 값들 — 오류정정 M ──────────────────────────── */

interface VersionSpec {
  /** 이 판에 담기는 글자 수 (바이트 방식) */
  capacity: number
  /** 묶음 하나에 붙는 오류정정 부호 개수 */
  ecPerBlock: number
  /** [묶음 수, 묶음 하나의 자료 개수] 두 벌 */
  blocks: [number, number][]
  /** 자리 맞춤 무늬 가운데 좌표 */
  align: number[]
}

const VERSIONS: Record<number, VersionSpec> = {
  1: { capacity: 14, ecPerBlock: 10, blocks: [[1, 16]], align: [] },
  2: { capacity: 26, ecPerBlock: 16, blocks: [[1, 28]], align: [6, 18] },
  3: { capacity: 42, ecPerBlock: 26, blocks: [[1, 44]], align: [6, 22] },
  4: { capacity: 62, ecPerBlock: 18, blocks: [[2, 32]], align: [6, 26] },
  5: { capacity: 84, ecPerBlock: 24, blocks: [[2, 43]], align: [6, 30] },
  6: { capacity: 106, ecPerBlock: 16, blocks: [[4, 27]], align: [6, 34] },
  7: { capacity: 122, ecPerBlock: 18, blocks: [[4, 31]], align: [6, 22, 38] },
  8: { capacity: 152, ecPerBlock: 22, blocks: [[2, 38], [2, 39]], align: [6, 24, 42] },
  9: { capacity: 180, ecPerBlock: 22, blocks: [[3, 36], [2, 37]], align: [6, 26, 46] },
  10: { capacity: 213, ecPerBlock: 26, blocks: [[4, 43], [1, 44]], align: [6, 28, 50] },
}

export const MAX_QR_VERSION = 10

/* ── 비트 담기 ──────────────────────────────────────────────────────────── */

class Bits {
  private out: number[] = []

  push(value: number, length: number) {
    for (let i = length - 1; i >= 0; i -= 1) this.out.push((value >>> i) & 1)
  }

  get length(): number {
    return this.out.length
  }

  /** 8개씩 묶어 바이트로 */
  toBytes(): Uint8Array {
    const bytes = new Uint8Array(Math.ceil(this.out.length / 8))
    for (let i = 0; i < this.out.length; i += 1) {
      if (this.out[i]) bytes[i >>> 3] |= 0x80 >>> (i & 7)
    }
    return bytes
  }
}

/* ── 무늬 놓기 ──────────────────────────────────────────────────────────── */

/** 켜진 칸이 true 인 정사각 판 */
export type QrMatrix = boolean[][]

function newGrid(size: number): { dark: boolean[][]; fixed: boolean[][] } {
  const dark: boolean[][] = []
  const fixed: boolean[][] = []
  for (let r = 0; r < size; r += 1) {
    dark.push(new Array(size).fill(false))
    fixed.push(new Array(size).fill(false))
  }
  return { dark, fixed }
}

function drawFinder(dark: boolean[][], fixed: boolean[][], size: number, r0: number, c0: number) {
  for (let dr = -1; dr <= 7; dr += 1) {
    for (let dc = -1; dc <= 7; dc += 1) {
      const r = r0 + dr
      const c = c0 + dc
      if (r < 0 || r >= size || c < 0 || c >= size) continue
      const ring = Math.max(Math.abs(dr - 3), Math.abs(dc - 3))
      dark[r][c] = ring !== 2 && ring !== 4
      fixed[r][c] = true
    }
  }
}

function drawAlignment(dark: boolean[][], fixed: boolean[][], r0: number, c0: number) {
  for (let dr = -2; dr <= 2; dr += 1) {
    for (let dc = -2; dc <= 2; dc += 1) {
      dark[r0 + dr][c0 + dc] = Math.max(Math.abs(dr), Math.abs(dc)) !== 1
      fixed[r0 + dr][c0 + dc] = true
    }
  }
}

/** 15비트 형식 정보 — 오류정정 등급과 무늬 번호 */
function formatBits(ecBits: number, mask: number): number {
  const data = (ecBits << 3) | mask
  let rem = data
  for (let i = 0; i < 10; i += 1) rem = (rem << 1) ^ ((rem >>> 9) * 0x537)
  return ((data << 10) | rem) ^ 0x5412
}

/** 18비트 판 정보 (7판부터) */
function versionBits(version: number): number {
  let rem = version
  for (let i = 0; i < 12; i += 1) rem = (rem << 1) ^ ((rem >>> 11) * 0x1f25)
  return (version << 12) | rem
}

function maskAt(mask: number, r: number, c: number): boolean {
  switch (mask) {
    case 0:
      return (r + c) % 2 === 0
    case 1:
      return r % 2 === 0
    case 2:
      return c % 3 === 0
    case 3:
      return (r + c) % 3 === 0
    case 4:
      return (Math.floor(r / 2) + Math.floor(c / 3)) % 2 === 0
    case 5:
      return ((r * c) % 2) + ((r * c) % 3) === 0
    case 6:
      return (((r * c) % 2) + ((r * c) % 3)) % 2 === 0
    default:
      return (((r + c) % 2) + ((r * c) % 3)) % 2 === 0
  }
}

/** 읽기 어려운 무늬에 벌점을 매긴다 — 가장 낮은 것을 고른다 */
function penalty(dark: boolean[][], size: number): number {
  let score = 0

  // 1) 같은 색이 다섯 칸 넘게 이어짐
  for (let i = 0; i < size; i += 1) {
    for (const line of [
      (j: number) => dark[i][j],
      (j: number) => dark[j][i],
    ]) {
      let run = 1
      for (let j = 1; j < size; j += 1) {
        if (line(j) === line(j - 1)) {
          run += 1
          if (run === 5) score += 3
          else if (run > 5) score += 1
        } else run = 1
      }
    }
  }

  // 2) 2×2 같은 색
  for (let r = 0; r < size - 1; r += 1) {
    for (let c = 0; c < size - 1; c += 1) {
      const v = dark[r][c]
      if (v === dark[r][c + 1] && v === dark[r + 1][c] && v === dark[r + 1][c + 1]) score += 3
    }
  }

  // 3) 찾기 무늬를 닮은 줄 (1:1:3:1:1)
  const pattern = [true, false, true, true, true, false, true, false, false, false, false]
  const rev = [...pattern].reverse()
  const matches = (get: (i: number) => boolean, start: number, want: boolean[]) => {
    for (let i = 0; i < want.length; i += 1) if (get(start + i) !== want[i]) return false
    return true
  }
  for (let i = 0; i < size; i += 1) {
    for (let j = 0; j + pattern.length <= size; j += 1) {
      if (matches((k) => dark[i][k], j, pattern)) score += 40
      if (matches((k) => dark[i][k], j, rev)) score += 40
      if (matches((k) => dark[k][i], j, pattern)) score += 40
      if (matches((k) => dark[k][i], j, rev)) score += 40
    }
  }

  // 4) 검은 칸이 너무 많거나 적음
  let darkCount = 0
  for (let r = 0; r < size; r += 1) for (let c = 0; c < size; c += 1) if (dark[r][c]) darkCount += 1
  const ratio = (darkCount * 100) / (size * size)
  score += Math.floor(Math.abs(ratio - 50) / 5) * 10

  return score
}

/* ── 만들기 ─────────────────────────────────────────────────────────────── */

/** 오류정정 M 의 형식 비트 */
const EC_LEVEL_M = 0

/**
 * 글을 QR 판으로. 담기지 않으면 `null`.
 *
 * 우리가 담는 것은 주소 한 줄이라 한글이 들어갈 일이 거의 없지만,
 * 들어가도 UTF-8 바이트로 그대로 담긴다.
 */
export function makeQr(text: string): QrMatrix | null {
  const data = new TextEncoder().encode(text)

  let version = 0
  for (let v = 1; v <= MAX_QR_VERSION; v += 1) {
    if (data.length <= VERSIONS[v].capacity) {
      version = v
      break
    }
  }
  if (version === 0) return null

  const spec = VERSIONS[version]
  const size = 17 + 4 * version
  const totalData = spec.blocks.reduce((sum, [count, len]) => sum + count * len, 0)

  // 1) 비트로 — 방식(0100) · 글자 수 · 글자 · 마침 · 채움
  const bits = new Bits()
  bits.push(0b0100, 4)
  bits.push(data.length, version <= 9 ? 8 : 16)
  for (const byte of data) bits.push(byte, 8)
  const capacityBits = totalData * 8
  bits.push(0, Math.min(4, capacityBits - bits.length))
  while (bits.length % 8 !== 0) bits.push(0, 1)
  const body = new Uint8Array(totalData)
  body.set(bits.toBytes())
  for (let i = bits.toBytes().length, pad = 0; i < totalData; i += 1, pad += 1) {
    body[i] = pad % 2 === 0 ? 0xec : 0x11
  }

  // 2) 묶음으로 나눠 오류정정 부호를 붙이고, 번갈아 섞는다
  const dataBlocks: Uint8Array[] = []
  const ecBlocks: Uint8Array[] = []
  let at = 0
  for (const [count, len] of spec.blocks) {
    for (let i = 0; i < count; i += 1) {
      const block = body.slice(at, at + len)
      at += len
      dataBlocks.push(block)
      ecBlocks.push(rsEncode(block, spec.ecPerBlock))
    }
  }
  const stream: number[] = []
  const maxData = Math.max(...dataBlocks.map((b) => b.length))
  for (let i = 0; i < maxData; i += 1) {
    for (const block of dataBlocks) if (i < block.length) stream.push(block[i])
  }
  for (let i = 0; i < spec.ecPerBlock; i += 1) {
    for (const block of ecBlocks) stream.push(block[i])
  }

  // 3) 고정 무늬
  const { dark, fixed } = newGrid(size)
  drawFinder(dark, fixed, size, 0, 0)
  drawFinder(dark, fixed, size, 0, size - 7)
  drawFinder(dark, fixed, size, size - 7, 0)

  for (const r of spec.align) {
    for (const c of spec.align) {
      // 찾기 무늬와 겹치는 세 귀퉁이는 건너뛴다
      if ((r === 6 && c === 6) || (r === 6 && c === size - 7) || (r === size - 7 && c === 6)) continue
      drawAlignment(dark, fixed, r, c)
    }
  }

  for (let i = 8; i < size - 8; i += 1) {
    dark[6][i] = i % 2 === 0
    fixed[6][i] = true
    dark[i][6] = i % 2 === 0
    fixed[i][6] = true
  }

  // 늘 켜져 있는 한 칸
  dark[4 * version + 9][8] = true
  fixed[4 * version + 9][8] = true

  // 형식 정보 자리를 비워 둔다 (값은 무늬를 고른 뒤에)
  for (let i = 0; i <= 8; i += 1) {
    if (i !== 6) {
      fixed[8][i] = true
      fixed[i][8] = true
    }
  }
  for (let i = 0; i < 8; i += 1) {
    fixed[8][size - 1 - i] = true
    fixed[size - 1 - i][8] = true
  }

  if (version >= 7) {
    const vb = versionBits(version)
    for (let i = 0; i < 18; i += 1) {
      const bit = ((vb >>> i) & 1) === 1
      const a = Math.floor(i / 3)
      const b = (i % 3) + size - 11
      dark[b][a] = bit
      fixed[b][a] = true
      dark[a][b] = bit
      fixed[a][b] = true
    }
  }

  // 4) 자료를 지그재그로 놓는다 (오른쪽 아래에서 위로)
  const place = (grid: boolean[][], mask: number) => {
    let i = 0
    let upward = true
    for (let right = size - 1; right >= 1; right -= 2) {
      const col = right <= 6 ? right - 1 : right // 6번 세로줄은 시간 무늬라 건너뛴다
      for (let step = 0; step < size; step += 1) {
        const r = upward ? size - 1 - step : step
        for (const c of [col, col - 1]) {
          if (fixed[r][c]) continue
          const bit = i < stream.length * 8 ? ((stream[i >>> 3] >>> (7 - (i & 7))) & 1) === 1 : false
          grid[r][c] = bit !== maskAt(mask, r, c)
          i += 1
        }
      }
      upward = !upward
    }
  }

  // 5) 여덟 가지 무늬 중 가장 읽기 쉬운 것
  let best: boolean[][] | null = null
  let bestScore = Number.POSITIVE_INFINITY
  for (let mask = 0; mask < 8; mask += 1) {
    const grid = dark.map((row) => [...row])
    place(grid, mask)
    // 형식 정보도 넣고 나서 벌점을 매겨야 실제와 같다
    const fb = formatBits(EC_LEVEL_M, mask)
    writeFormat(grid, size, fb)
    const score = penalty(grid, size)
    if (score < bestScore) {
      bestScore = score
      best = grid
    }
  }

  return best
}

/**
 * 형식 정보 15비트를 **두 군데**에 적는다.
 *
 * 한 군데가 가려지거나 지워져도 읽히게 규격이 두 벌을 요구한다.
 * 자리는 규격에 못 박혀 있어 하나만 틀려도 읽는 기계가 통째로 못 읽는다 —
 * 그래서 `tests/qr.test.ts` 에서 실제로 되읽어 본다.
 */
function writeFormat(grid: boolean[][], size: number, fb: number) {
  const bit = (i: number) => ((fb >>> i) & 1) === 1

  // 왼쪽 위 — 세로로 여섯 칸, 꺾어서 가로로
  for (let i = 0; i <= 5; i += 1) grid[i][8] = bit(i)
  grid[7][8] = bit(6)
  grid[8][8] = bit(7)
  grid[8][7] = bit(8)
  for (let i = 9; i < 15; i += 1) grid[8][14 - i] = bit(i)

  // 오른쪽 위 · 왼쪽 아래
  for (let i = 0; i < 8; i += 1) grid[8][size - 1 - i] = bit(i)
  for (let i = 8; i < 15; i += 1) grid[size - 15 + i][8] = bit(i)
  grid[size - 8][8] = true
}

/**
 * QR 판을 SVG 글로. 화면에도, 종이에도 같은 것이 나온다.
 *
 * `quiet` 는 둘레의 빈 자리다 — 이게 없으면 읽는 기계가 QR 의 끝을 못 찾는다.
 * 규격은 4칸을 요구한다.
 */
export function qrSvgPath(matrix: QrMatrix): string {
  const parts: string[] = []
  for (let r = 0; r < matrix.length; r += 1) {
    for (let c = 0; c < matrix.length; c += 1) {
      if (matrix[r][c]) parts.push(`M${c} ${r}h1v1h-1z`)
    }
  }
  return parts.join('')
}

export const QR_QUIET = 4
