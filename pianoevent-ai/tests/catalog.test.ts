import { describe, expect, it } from 'vitest'
import { CATALOG_SIZE, PIECE_CATALOG, completeFromCatalog, findPiece, searchPieces } from '@/lib/program/catalog'
import { parseRoster } from '@/lib/program/roster'
import { buildProgram } from '@/lib/program/order'
import { pieceCommentary } from '@/lib/program/script'
import { student } from './helpers'

describe('곡 사전', () => {
  it('연주회에 실제로 오르는 곡을 충분히 담았다', () => {
    expect(CATALOG_SIZE).toBeGreaterThanOrEqual(70)
  })

  it('항목이 모두 온전하다', () => {
    for (const entry of PIECE_CATALOG) {
      expect(entry.title.length).toBeGreaterThan(0)
      expect(entry.composer.length).toBeGreaterThan(0)
      expect(entry.duration_sec).toBeGreaterThan(20)
      expect(entry.duration_sec).toBeLessThan(20 * 60)
      expect(entry.blurb.length).toBeGreaterThan(10)
    }
  })

  it('대표 표기가 겹치지 않는다', () => {
    const titles = PIECE_CATALOG.map((e) => e.title)
    expect(new Set(titles).size).toBe(titles.length)
  })

  it('정확한 제목을 찾는다', () => {
    expect(findPiece('엘리제를 위하여')?.composer).toBe('베토벤')
    expect(findPiece('녹턴 op.9 no.2')?.composer).toBe('쇼팽')
  })

  it('별칭과 영문 표기도 찾는다', () => {
    expect(findPiece('fur elise')?.title).toBe('엘리제를 위하여')
    expect(findPiece('turkish march')?.composer).toBe('모차르트')
    expect(findPiece('하울의 움직이는 성')?.composer).toBe('히사이시 조')
  })

  it('원장이 덧붙여 적어도 찾는다', () => {
    expect(findPiece('엘리제를 위하여 (베토벤)')?.title).toBe('엘리제를 위하여')
    expect(findPiece('  터키 행진곡  ')?.title).toBe('터키 행진곡')
  })

  it('사전에 없는 곡은 억지로 찾지 않는다', () => {
    expect(findPiece('학원 자작곡 제7번 라단조')).toBeNull()
    expect(findPiece('')).toBeNull()
  })

  it('입력 중 후보를 뽑는다', () => {
    const found = searchPieces('녹턴')
    expect(found.length).toBeGreaterThan(0)
    expect(found[0].title).toContain('녹턴')
    expect(searchPieces('쇼팽').length).toBeGreaterThanOrEqual(3)
  })

  it('빈칸만 채우고 원장이 적은 값은 건드리지 않는다', () => {
    const filled = completeFromCatalog({
      piece_title: '엘리제를 위하여',
      composer: '',
      duration_sec: null,
      level: 'beginner',
      levelGiven: false,
    })
    expect(filled.composer).toBe('베토벤')
    expect(filled.duration_sec).toBe(210)
    expect(filled.level).toBe('intermediate')
    expect(filled.filled).toEqual({ composer: true, duration: true, level: true })

    const kept = completeFromCatalog({
      piece_title: '엘리제를 위하여',
      composer: '우리 학원 편곡',
      duration_sec: 90,
      level: 'beginner',
      levelGiven: true,
    })
    expect(kept.composer).toBe('우리 학원 편곡')
    expect(kept.duration_sec).toBe(90)
    expect(kept.level).toBe('beginner')
    expect(kept.filled).toEqual({ composer: false, duration: false, level: false })
  })
})

describe('붙여넣기에서 곡 사전이 일한다', () => {
  it('이름과 곡만 있어도 작곡가·시간·난이도가 채워진다', () => {
    const parsed = parseRoster('김서연\t엘리제를 위하여\n박지호\t징글벨')
    expect(parsed.rows[0].composer).toBe('베토벤')
    expect(parsed.rows[0].duration_sec).toBe(210)
    expect(parsed.rows[0].level).toBe('intermediate')
    expect(parsed.rows[1].composer).toBe('피어폰트')
  })

  it('무엇이 자동으로 채워졌는지 알려 준다', () => {
    const parsed = parseRoster('김서연\t엘리제를 위하여')
    expect(parsed.autofilled).toHaveLength(1)
    expect(parsed.autofilled[0].fields).toContain('작곡가')
    expect(parsed.autofilled[0].fields).toContain('연주시간')
  })

  it('원장이 적은 값이 있으면 자동 채움이 일어나지 않는다', () => {
    const parsed = parseRoster('김서연\t엘리제를 위하여\t우리 편곡\t1:30\t초급')
    expect(parsed.rows[0].composer).toBe('우리 편곡')
    expect(parsed.rows[0].duration_sec).toBe(90)
    expect(parsed.autofilled).toHaveLength(0)
  })

  it('사전에 없는 곡은 지금까지처럼 동작한다', () => {
    const parsed = parseRoster('김서연\t우리 학원 창작곡')
    expect(parsed.rows[0].composer).toBe('')
    expect(parsed.rows[0].duration_sec).toBeNull()
  })

  it('채워진 시간이 러닝타임 계산에 그대로 쓰인다', () => {
    const parsed = parseRoster('가\t엘리제를 위하여\n나\t징글벨')
    const plan = buildProgram(
      parsed.rows.map((r, i) =>
        student(r.student_name, r.level, r.duration_sec ?? 0, { id: `c${i}`, piece_title: r.piece_title }),
      ),
    )
    expect(plan.play_sec).toBe(210 + 70)
  })
})

describe('곡 해설이 사전을 쓴다', () => {
  it('사전에 있는 곡은 그 곡을 위해 쓰인 해설이 나온다', () => {
    const text = pieceCommentary(student('가', 'intermediate', 200, { piece_title: '인생의 회전목마' }))
    expect(text).toContain('왈츠')
  })

  it('사전에 없어도 해설이 비지 않는다', () => {
    const text = pieceCommentary(student('가', 'advanced', 300, { piece_title: '창작곡', composer: '' }))
    expect(text.length).toBeGreaterThan(10)
  })
})
