import { describe, expect, it } from 'vitest'
import {
  BACKUP_KEEP_DAYS,
  backupDay,
  describeBackup,
  needsBackup,
  pruneDays,
  safeFileName,
  sortDays,
  uniqueName,
} from '@/lib/events/backup'

describe('하루에 한 번', () => {
  it('날짜를 폴더 이름으로 쓴다', () => {
    expect(backupDay(new Date(2026, 7, 28, 23, 30))).toBe('2026-08-28')
  })

  it('원장님 컴퓨터 날짜로 적는다 — 밤에 만든 것이 어제 폴더로 가면 안 된다', () => {
    // 밤 11시 30분. UTC 로 적으면 다음 날(또는 전날)로 넘어간다.
    expect(backupDay(new Date(2026, 0, 1, 23, 59))).toBe('2026-01-01')
  })

  it('망가진 날짜가 와도 오늘로 적는다 — 멈추는 것보다 낫다', () => {
    expect(backupDay('말도 안 되는 날짜')).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  })

  it('한 번도 안 떴으면 떠야 한다', () => {
    expect(needsBackup(null)).toBe(true)
  })

  it('오늘 이미 떴으면 다시 뜨지 않는다', () => {
    const now = new Date(2026, 7, 28, 18, 0)
    expect(needsBackup(new Date(2026, 7, 28, 9, 0).toISOString(), now)).toBe(false)
  })

  it('날이 바뀌면 다시 뜬다', () => {
    const now = new Date(2026, 7, 29, 9, 0)
    expect(needsBackup(new Date(2026, 7, 28, 23, 0).toISOString(), now)).toBe(true)
  })
})

describe('오래된 것 지우기', () => {
  const days = (n: number) => Array.from({ length: n }, (_, i) => `2026-08-${String(i + 1).padStart(2, '0')}`)

  it('열네 날치만 남긴다', () => {
    const gone = pruneDays(days(20))
    expect(gone).toHaveLength(20 - BACKUP_KEEP_DAYS)
    expect(gone[0]).toBe('2026-08-01')
  })

  it('열네 날 안쪽이면 아무것도 지우지 않는다', () => {
    expect(pruneDays(days(10))).toEqual([])
  })

  it('날짜가 아닌 폴더는 건드리지 않는다 — 원장님이 만드신 것일 수 있다', () => {
    expect(pruneDays([...days(20), '내가만든폴더'])).not.toContain('내가만든폴더')
  })

  it('오래된 것부터 지운다', () => {
    const gone = pruneDays(['2026-08-20', '2026-08-01', '2026-08-10'], 1)
    expect(gone).toEqual(['2026-08-01', '2026-08-10'])
  })
})

describe('파일 이름', () => {
  it('윈도우에서 못 쓰는 글자를 걷어 낸다', () => {
    expect(safeFileName('봄/여름 : 발표회?')).toBe('봄 여름 발표회')
  })

  it('이름이 통째로 사라지면 기본 이름을 쓴다', () => {
    expect(safeFileName('///')).toBe('행사')
  })

  it('같은 이름이 둘이면 번호를 붙인다 — 덮어쓰면 하나를 잃는다', () => {
    const taken = new Set(['정기 연주회'])
    expect(uniqueName('정기 연주회', taken)).toBe('정기 연주회 (2)')
  })

  it('안 겹치면 그대로 둔다', () => {
    expect(uniqueName('정기 연주회', new Set())).toBe('정기 연주회')
  })
})

describe('화면에 보여 드릴 때', () => {
  it('며칠 것에 행사 몇 개인지 한 줄로', () => {
    expect(describeBackup({ day: '2026-08-28', files: [{ name: 'a', bytes: 1 }, { name: 'b', bytes: 2 }] })).toBe(
      '8월 28일 · 행사 2개',
    )
  })

  it('가장 최근 것이 위로 온다', () => {
    const sorted = sortDays([
      { day: '2026-08-01', files: [] },
      { day: '2026-08-28', files: [] },
      { day: '2026-08-10', files: [] },
    ])
    expect(sorted.map((d) => d.day)).toEqual(['2026-08-28', '2026-08-10', '2026-08-01'])
  })
})
