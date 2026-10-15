import { afterEach, describe, expect, it } from 'vitest'
import { DATA_DIR_ENV, backupRoot, dataRoot, storeFile } from '@/lib/paths'

const original = process.env[DATA_DIR_ENV]
afterEach(() => {
  if (original === undefined) delete process.env[DATA_DIR_ENV]
  else process.env[DATA_DIR_ENV] = original
})

describe('학원 자료가 놓이는 자리', () => {
  it('정해 주지 않으면 지금까지처럼 프로그램 폴더에 쓴다', () => {
    delete process.env[DATA_DIR_ENV]
    expect(dataRoot()).toBe(process.cwd())
  })

  it('설치판이 정해 주면 그 자리에 쓴다 — Program Files 는 쓰기가 막혀 있다', () => {
    process.env[DATA_DIR_ENV] = '/tmp/피아노이벤트-자료'
    expect(dataRoot()).toBe('/tmp/피아노이벤트-자료')
    expect(storeFile()).toBe('/tmp/피아노이벤트-자료/.data/store.json')
    expect(backupRoot('백업')).toBe('/tmp/피아노이벤트-자료/백업')
  })

  it('빈 값이나 공백만 주면 없는 것으로 본다 — 뿌리(/)에 쓰면 큰일이다', () => {
    process.env[DATA_DIR_ENV] = '   '
    expect(dataRoot()).toBe(process.cwd())
    process.env[DATA_DIR_ENV] = ''
    expect(dataRoot()).toBe(process.cwd())
  })

  it('명단과 자동 저장이 같은 자리 아래 모인다 — 옮기실 때 폴더 하나면 된다', () => {
    process.env[DATA_DIR_ENV] = '/tmp/한자리'
    expect(storeFile().startsWith(dataRoot())).toBe(true)
    expect(backupRoot('백업').startsWith(dataRoot())).toBe(true)
  })
})
