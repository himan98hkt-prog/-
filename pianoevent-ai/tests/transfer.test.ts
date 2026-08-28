import { describe, expect, it } from 'vitest'
import {
  BUNDLE_KIND,
  BundleError,
  buildBundle,
  bundleFilename,
  bundleSummary,
  parseBundle,
  usedAssetIds,
} from '@/lib/events/transfer'
import type { AcademyAsset } from '@/lib/assets'
import type { EventRecord, EventStudent } from '@/lib/types'

function student(partial: Partial<EventStudent>): EventStudent {
  return {
    id: 's1',
    event_id: 'e1',
    student_name: '김서연',
    piece_title: '엘리제를 위하여',
    composer: '베토벤',
    duration_sec: 210,
    level: 'intermediate',
    note: null,
    order_no: 1,
    mc_script: null,
    photo_asset_id: null,
    photo_asset_ids: null,
    created_at: '2026-01-01T00:00:00.000Z',
    ...partial,
  } as EventStudent
}

const asset = (id: string): AcademyAsset => ({
  id,
  kind: 'photo',
  label: `사진 ${id}`,
  url: 'data:image/png;base64,AAAA',
  created_at: '2026-01-01T00:00:00.000Z',
})

const event = {
  id: 'e1',
  academy_id: 'a1',
  title: '제12회 정기 연주회',
  type: 'recital',
  event_at: '2026-09-18T06:00:00.000Z',
  venue: '구민회관 소공연장',
  status: 'published',
  theme: null,
  greeting: '어서 오세요',
  mc_opening: '안녕하세요',
  mc_closing: '고맙습니다',
  program_source: 'rule',
  program_generated_at: null,
  design_theme: 'ivory',
  design_template: 'poster-classic',
  design_copy: { subtitle: '봄' },
  photo_url: null,
  image_map: null,
  stage_prefs: null,
  video_prefs: null,
  video_url: null,
  live_state: null,
  created_at: '2026-01-01T00:00:00.000Z',
} as unknown as EventRecord

describe('내보낼 때 사진 고르기', () => {
  it('명단이 실제로 쓰는 사진만 모은다', () => {
    const ids = usedAssetIds([
      student({ id: 's1', photo_asset_id: 'p1' }),
      student({ id: 's2', photo_asset_id: 'p2', photo_asset_ids: ['p2', 'p3'] }),
    ])
    expect(ids.sort()).toEqual(['p1', 'p2', 'p3'])
  })

  it('안 쓰는 보관함 사진은 파일에 넣지 않는다 — 파일만 무거워진다', () => {
    const bundle = buildBundle({
      academyName: '하모니',
      event,
      students: [student({ photo_asset_id: 'p1' })],
      assets: [asset('p1'), asset('안쓰는것')],
    })
    expect(bundle.assets.map((a) => a.id)).toEqual(['p1'])
  })
})

describe('행사 파일 만들기', () => {
  const bundle = buildBundle({
    academyName: '하모니 피아노학원',
    event,
    students: [student({}), student({ id: 's2', student_name: '박지호', piece_title: '즐거운 나의 집' })],
    assets: [],
    now: '2026-08-28T00:00:00.000Z',
  })

  it('행사 정보와 명단이 함께 담긴다', () => {
    expect(bundle.event.title).toBe('제12회 정기 연주회')
    expect(bundle.students).toHaveLength(2)
  })

  it('인쇄물·무대 설정도 함께 담긴다 — 다시 고르실 일이 없게', () => {
    expect(bundle.event.design_theme).toBe('ivory')
    expect(bundle.event.design_template).toBe('poster-classic')
    expect(bundle.event.design_copy).toEqual({ subtitle: '봄' })
  })

  it('학부모 회신은 담지 않는다 — 옮길 물건이 아니다', () => {
    expect(JSON.stringify(bundle)).not.toContain('rsvp')
  })

  it('내보낸 것을 그대로 다시 읽는다', () => {
    const back = parseBundle(JSON.stringify(bundle))
    expect(back.event.title).toBe(bundle.event.title)
    expect(back.students.map((s) => s.student_name)).toEqual(['김서연', '박지호'])
  })
})

describe('남이 준 파일 읽기', () => {
  it('행사 파일이 아니면 무엇을 하시면 되는지 알려 준다', () => {
    expect(() => parseBundle('{"hello":1}')).toThrow(BundleError)
    expect(() => parseBundle('{"hello":1}')).toThrow('내보내기로 받은')
  })

  it('글이 깨져 있어도 프로그램이 멈추지 않는다', () => {
    expect(() => parseBundle('이건 그냥 글')).toThrow('행사 파일이 아닙니다')
  })

  it('더 새 판에서 나온 파일이면 그렇게 말해 준다', () => {
    const text = JSON.stringify({ kind: BUNDLE_KIND, version: 99, event: { title: 'x' } })
    expect(() => parseBundle(text)).toThrow('새 판')
  })

  it('행사 이름이 없으면 거절한다', () => {
    expect(() => parseBundle(JSON.stringify({ kind: BUNDLE_KIND, version: 1, event: {} }))).toThrow('행사 이름')
  })

  it('이름 없는 줄은 조용히 버린다', () => {
    const text = JSON.stringify({
      kind: BUNDLE_KIND,
      version: 1,
      event: { title: '연주회' },
      students: [{ student_name: '김서연' }, { student_name: '  ' }, null],
    })
    expect(parseBundle(text).students).toHaveLength(1)
  })

  it('모르는 난이도는 기초로 본다 — 멈추는 것보다 낫다', () => {
    const text = JSON.stringify({
      kind: BUNDLE_KIND,
      version: 1,
      event: { title: '연주회' },
      students: [{ student_name: '김서연', level: '초고수' }],
    })
    expect(parseBundle(text).students[0].level).toBe('beginner')
  })

  it('사진 칸이 망가진 것은 빼고 읽는다', () => {
    const text = JSON.stringify({
      kind: BUNDLE_KIND,
      version: 1,
      event: { title: '연주회' },
      assets: [asset('p1'), { id: 'p2' }, 'x'],
    })
    expect(parseBundle(text).assets).toHaveLength(1)
  })
})

describe('원장님이 알아보실 이름', () => {
  it('행사 이름과 날짜로 파일 이름을 짓는다', () => {
    expect(bundleFilename('제12회 정기 연주회', '2026-09-18T06:00:00.000Z')).toBe('제12회 정기 연주회 2026-09-18.json')
  })

  it('파일 이름에 못 쓰는 글자는 지운다', () => {
    expect(bundleFilename('봄/여름 : 발표회', '2026-03-01T00:00:00.000Z')).toBe('봄 여름   발표회 2026-03-01.json')
  })

  it('가져오기 전에 무엇이 들었는지 한 줄로 말해 준다', () => {
    const bundle = buildBundle({
      academyName: '하모니',
      event,
      students: [student({}), student({ id: 's2' }), student({ id: 's3', student_name: '박지호', photo_asset_id: 'p1' })],
      assets: [asset('p1')],
    })
    expect(bundleSummary(bundle)).toBe('제12회 정기 연주회 — 아이 2명 · 무대 3번 · 사진 1장')
  })
})
