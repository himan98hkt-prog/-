import { execFileSync } from 'node:child_process'
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'

/**
 * 묶음 파일의 한글 이름이 윈도우에서 깨지지 않는지.
 *
 * 리눅스의 `zip` 명령은 이름을 UTF-8 로 넣으면서 **"이건 UTF-8 이다" 는 표시를
 * 켜 주지 않는다.** 윈도우는 그 바이트를 옛 코드페이지로 읽으려다 실패하고,
 * 원장님 화면에는 "압축을 풀었는데 아무것도 없다" 로 나타난다.
 *
 * 파일 이름이 전부 한글인 묶음이라 표시 하나가 묶음 전체를 못 쓰게 만든다.
 * 눈으로는 절대 못 잡는 자리라 검사로 박아 둔다.
 */
const UTF8_FLAG = 0x0800
const EOCD_SIGNATURE = 0x06054b50

let work: string
let zipPath: string

beforeAll(async () => {
  work = mkdtempSync(join(tmpdir(), 'pianoevent-zip-'))
  const root = join(work, '묶음')
  mkdirSync(join(root, '연습용-명단'), { recursive: true })
  writeFileSync(join(root, '먼저-읽어주세요.txt'), '안녕하세요', 'utf8')
  writeFileSync(join(root, '시작하기.bat'), 'echo hi', 'utf8')
  writeFileSync(join(root, '연습용-명단', '학생명단-예시.txt'), '김서연', 'utf8')

  zipPath = join(work, '결과.zip')
  // 묶음을 실제로 만드는 그 코드를 그대로 부른다 — 다른 길로 만들면 검사가 헛돈다
  const { zipFolder } = await import('../scripts/zip-utf8.mjs')
  await zipFolder(work, zipPath)
})

afterAll(() => rmSync(work, { recursive: true, force: true }))

/** 중앙 목록을 읽어 항목별 이름과 플래그를 낸다 */
function entries(file: string): { name: string; flag: number }[] {
  const data = readFileSync(file)
  let eocd = -1
  for (let i = data.length - 22; i >= 0; i -= 1) {
    if (data.readUInt32LE(i) === EOCD_SIGNATURE) {
      eocd = i
      break
    }
  }
  if (eocd < 0) throw new Error('ZIP 끝 표시를 찾지 못했습니다.')

  const count = data.readUInt16LE(eocd + 10)
  let at = data.readUInt32LE(eocd + 16)
  const out: { name: string; flag: number }[] = []
  for (let i = 0; i < count; i += 1) {
    const flag = data.readUInt16LE(at + 8)
    const nameLen = data.readUInt16LE(at + 28)
    const extraLen = data.readUInt16LE(at + 30)
    const commentLen = data.readUInt16LE(at + 32)
    out.push({ name: data.subarray(at + 46, at + 46 + nameLen).toString('utf8'), flag })
    at += 46 + nameLen + extraLen + commentLen
  }
  return out
}

describe('한글 이름이 깨지지 않는 묶음', () => {
  it('모든 항목에 "이름은 UTF-8" 표시가 켜져 있다', () => {
    const all = entries(zipPath)
    expect(all.length).toBeGreaterThan(0)
    expect(all.filter((e) => (e.flag & UTF8_FLAG) === 0)).toEqual([])
  })

  it('한글 이름이 그대로 들어간다', () => {
    const names = entries(zipPath).map((e) => e.name)
    expect(names).toContain('묶음/먼저-읽어주세요.txt')
    expect(names).toContain('묶음/연습용-명단/학생명단-예시.txt')
  })

  it('폴더 이름에 빈칸을 쓰지 않는다 — 배치 파일과 경로에서 또 사고가 난다', () => {
    expect(entries(zipPath).filter((e) => e.name.includes(' '))).toEqual([])
  })

  it('압축이 깨지지 않았다 — 실제로 풀어서 확인한다', () => {
    const out = join(work, '풀기')
    mkdirSync(out, { recursive: true })
    execFileSync('unzip', ['-q', '-o', zipPath, '-d', out])
    expect(readFileSync(join(out, '묶음', '먼저-읽어주세요.txt'), 'utf8')).toBe('안녕하세요')
    expect(readFileSync(join(out, '묶음', '연습용-명단', '학생명단-예시.txt'), 'utf8')).toBe('김서연')
  })

  it('폴더도 항목으로 넣는다 — 빈 폴더가 사라지지 않게', () => {
    expect(entries(zipPath).some((e) => e.name.endsWith('/'))).toBe(true)
  })
})
