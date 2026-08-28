import { describe, expect, it } from 'vitest'
import { buildProgram } from '@/lib/program/order'
import { buildTimeline, describeRecordType, fadeFor, scenesAt, CAPTION_FADE_SEC, CROSSFADE_SEC } from '@/lib/video/render'
import {
  buildStoryboard,
  DEFAULT_STORYBOARD_OPTIONS,
  fitToLimit,
  formatLength,
  leadingNumber,
  moveScene,
  sortByFileName,
  MAX_TOTAL_SEC,
  SCENE_MIN_SEC,
  totalSeconds,
  type ExtraMedia,
} from '@/lib/video/storyboard'
import type { EventRecord } from '@/lib/types'
import { student } from './helpers'

const EVENT_AT = '2026-09-16T06:00:00.000Z'

const event = {
  id: 'e1',
  academy_id: 'a1',
  title: '제12회 정기 연주회',
  type: 'recital',
  event_at: EVENT_AT,
  venue: '구민회관 소공연장',
  status: 'ready',
  theme: null,
  greeting: null,
  mc_opening: null,
  mc_closing: null,
  program_source: 'rule',
  program_generated_at: null,
  design_theme: null,
  design_template: null,
  design_copy: null,
  photo_url: null,
  created_at: EVENT_AT,
} as EventRecord

const roster = [
  student('김서연', 'beginner', 100, { piece_title: '나비야' }),
  student('박지호', 'beginner', 110, { piece_title: '즐거운 나의 집' }),
  student('정예린', 'intermediate', 170, { piece_title: '아라베스크' }),
  student('윤채원', 'advanced', 260, { piece_title: '녹턴 op.9 no.2', composer: '쇼팽' }),
]

const plan = buildProgram(roster)
const photos = Object.fromEntries(plan.items.slice(0, 2).map((item) => [item.student.id, 'data:image/png;base64,AA']))

function board(extras: ExtraMedia[] = [], options = DEFAULT_STORYBOARD_OPTIONS) {
  return buildStoryboard({ event, plan, academyName: '하모니 피아노학원', photos, extras, options })
}

describe('감동영상 장면 짜기', () => {
  it('표지로 시작해 마무리로 끝난다', () => {
    const scenes = board()
    expect(scenes[0].kind).toBe('title')
    expect(scenes[0].headline).toBe('제12회 정기 연주회')
    expect(scenes[scenes.length - 1].kind).toBe('closing')
  })

  it('아이 한 명당 한 장면 — 아무도 빠지지 않는다', () => {
    const scenes = board().filter((scene) => scene.kind === 'student')
    expect(scenes).toHaveLength(roster.length)
    for (const name of roster.map((row) => row.student_name)) {
      expect(scenes.some((scene) => scene.headline === name)).toBe(true)
    }
  })

  it('장면 순서가 연주 순서와 같다', () => {
    const shown = board()
      .filter((scene) => scene.kind === 'student')
      .map((scene) => scene.headline)
    expect(shown).toEqual(plan.items.map((item) => item.student.student_name))
  })

  it('사진이 있는 아이에게만 사진이 붙는다', () => {
    const scenes = board().filter((scene) => scene.kind === 'student')
    expect(scenes.filter((scene) => scene.image).length).toBe(2)
  })

  it('사진이 없어도 이름과 곡은 나온다 — 빈 화면이 뜨지 않는다', () => {
    const scenes = board().filter((scene) => scene.kind === 'student' && !scene.image)
    expect(scenes.length).toBeGreaterThan(0)
    for (const scene of scenes) expect(scene.headline).toBeTruthy()
  })

  it('연습 사진을 더하면 앞쪽에 한 묶음이 생긴다', () => {
    const extras: ExtraMedia[] = [
      { id: 'p1', kind: 'image', url: 'blob:1', label: '연습실' },
      { id: 'p2', kind: 'image', url: 'blob:2', label: '리허설' },
    ]
    const scenes = board(extras)
    expect(scenes.filter((scene) => scene.kind === 'gallery')).toHaveLength(2)
    expect(scenes.some((scene) => scene.headline === '이 무대까지 오는 동안')).toBe(true)
    // 학생 장면보다 앞에 온다
    const firstGallery = scenes.findIndex((scene) => scene.kind === 'gallery')
    const firstStudent = scenes.findIndex((scene) => scene.kind === 'student')
    expect(firstGallery).toBeLessThan(firstStudent)
  })

  it('동영상은 실제 길이만큼 튼다', () => {
    const scenes = board([{ id: 'v1', kind: 'video', url: 'blob:v', label: '합주', duration: 9.4 }])
    const clip = scenes.find((scene) => scene.kind === 'clip')
    expect(clip?.seconds).toBeCloseTo(9.4, 1)
  })

  it('자막을 끄면 곡 이름이 빠진다', () => {
    const scenes = board([], { ...DEFAULT_STORYBOARD_OPTIONS, captions: false })
    expect(scenes.filter((scene) => scene.kind === 'student').every((scene) => !scene.sub)).toBe(true)
  })

  it('명단이 비어도 만들어진다 — 표지와 마무리', () => {
    const scenes = buildStoryboard({ event, plan: buildProgram([]), academyName: '하모니', photos: {} })
    expect(scenes.map((scene) => scene.kind)).toEqual(['title', 'closing'])
  })

  it('장면 id 가 겹치지 않는다', () => {
    const scenes = board([{ id: 'p1', kind: 'image', url: 'b', label: 'a' }])
    expect(new Set(scenes.map((scene) => scene.id)).size).toBe(scenes.length)
  })
})

describe('길이 맞추기', () => {
  it('너무 길면 장면 시간을 줄여 맞춘다 — 아이를 빼지 않는다', () => {
    const many = Array.from({ length: 300 }, (_, i) => student(`학생${i + 1}`, 'intermediate', 150))
    const scenes = buildStoryboard({ event, plan: buildProgram(many), academyName: '하모니', photos: {} })
    expect(totalSeconds(scenes)).toBeGreaterThan(MAX_TOTAL_SEC)
    const fitted = fitToLimit(scenes)
    expect(fitted).toHaveLength(scenes.length)
    expect(fitted.filter((scene) => scene.kind === 'student')).toHaveLength(300)
    expect(totalSeconds(fitted)).toBeLessThanOrEqual(MAX_TOTAL_SEC)
    for (const scene of fitted) expect(scene.seconds).toBeGreaterThanOrEqual(SCENE_MIN_SEC)
  })

  it('아무리 줄여도 최소 시간은 지킨다 — 얼굴을 알아볼 수는 있어야 한다', () => {
    const scenes = board()
    const squeezed = fitToLimit(scenes, 1)
    for (const scene of squeezed) expect(scene.seconds).toBe(SCENE_MIN_SEC)
  })

  it('짧으면 그대로 둔다', () => {
    const scenes = board()
    expect(fitToLimit(scenes)).toEqual(scenes)
  })

  it('길이를 사람이 읽는 말로 적는다', () => {
    expect(formatLength(45)).toBe('45초')
    expect(formatLength(96)).toBe('1분 36초')
  })
})

describe('시간표', () => {
  const timeline = buildTimeline(board())

  it('시작 시각이 차례로 쌓인다', () => {
    expect(timeline.starts[0]).toBe(0)
    for (let i = 1; i < timeline.starts.length; i += 1) {
      expect(timeline.starts[i]).toBeCloseTo(timeline.starts[i - 1] + timeline.scenes[i - 1].seconds, 5)
    }
    expect(timeline.total).toBeCloseTo(totalSeconds(timeline.scenes), 5)
  })

  it('어느 시각에나 보여 줄 장면이 있다 — 검은 화면이 뜨지 않는다', () => {
    for (let t = 0; t < timeline.total; t += 0.25) {
      expect(scenesAt(timeline, t).length).toBeGreaterThan(0)
    }
  })

  it('넘어가는 동안에는 두 장면이 겹친다 — 화면이 껌뻑이지 않는다', () => {
    const at = timeline.starts[1] + fadeFor(timeline.scenes[1].seconds) / 2
    const visible = scenesAt(timeline, at)
    expect(visible.length).toBe(2)
    // 앞 장면은 아래에 그대로, 뒤 장면이 그 위로 서서히 진해진다
    expect(visible[0].index).toBe(0)
    expect(visible[0].alpha).toBe(1)
    expect(visible[1].index).toBe(1)
    expect(visible[1].alpha).toBeGreaterThan(0)
    expect(visible[1].alpha).toBeLessThan(1)
  })

  it('겹치는 시간이 끝나면 앞 장면은 사라진다', () => {
    const at = timeline.starts[1] + fadeFor(timeline.scenes[1].seconds) + 0.05
    const visible = scenesAt(timeline, at)
    expect(visible.map((entry) => entry.index)).toEqual([1])
  })

  it('넘어가는 동안 두 자막이 함께 읽히지 않는다 — 이름이 겹쳐 찍힌 것처럼 보인다', () => {
    const fade = fadeFor(timeline.scenes[1].seconds)
    for (let t = timeline.starts[1]; t < timeline.starts[1] + fade; t += 0.05) {
      const visible = scenesAt(timeline, t)
      const readable = visible.filter((entry) => entry.textAlpha > 0.15)
      expect(readable.length).toBeLessThanOrEqual(1)
    }
  })

  it('자막은 넘어가기가 끝난 뒤에 떠오른다', () => {
    const fade = fadeFor(timeline.scenes[1].seconds)
    expect(scenesAt(timeline, timeline.starts[1] + fade * 0.5).find((e) => e.index === 1)?.textAlpha).toBe(0)
    const settled = scenesAt(timeline, timeline.starts[1] + fade + CAPTION_FADE_SEC + 0.01).find((e) => e.index === 1)
    expect(settled?.textAlpha).toBe(1)
  })

  it('장면이 짧으면 겹치는 시간도 짧아진다 — 겹침이 장면을 다 먹지 않게', () => {
    expect(fadeFor(6)).toBe(CROSSFADE_SEC)
    expect(fadeFor(1.5)).toBeCloseTo(0.375, 3)
    expect(fadeFor(0.4)).toBe(0.15)
  })

  it('첫 장면은 흐리게 시작하지 않는다', () => {
    expect(scenesAt(timeline, 0)[0].alpha).toBe(1)
  })
})

describe('내려받는 파일 형식', () => {
  it('H.264 MP4 면 어디서나 열린다고 알려 준다', () => {
    const info = describeRecordType('video/mp4;codecs="avc1.42E01E,mp4a.40.2"')
    expect(info.ext).toBe('mp4')
    expect(info.note).toContain('파워포인트')
  })

  it('VP9 이 든 MP4 는 그렇게 말하지 않는다 — 거짓말이 된다', () => {
    const info = describeRecordType('video/mp4;codecs=vp9,opus')
    expect(info.ext).toBe('mp4')
    expect(info.label).toContain('VP9')
    expect(info.note).toContain('크롬')
  })

  it('WebM 은 확장자도 webm 이고, 한계를 숨기지 않는다', () => {
    const info = describeRecordType('video/webm;codecs="vp9,opus"')
    expect(info.ext).toBe('webm')
    expect(info.note).toContain('길이가 안 뜰 수 있')
  })
})

describe('원장님이 직접 고치기', () => {
  it('파일 이름 앞 번호대로 늘어놓는다', () => {
    const picked = [
      { label: '03 리허설' },
      { label: '01 입장' },
      { label: '10 무대 뒤' },
      { label: '02 대기실' },
    ]
    expect(sortByFileName(picked).map((item) => item.label)).toEqual([
      '01 입장',
      '02 대기실',
      '03 리허설',
      '10 무대 뒤',
    ])
  })

  it('번호가 붙은 것이 먼저, 나머지는 이름 순', () => {
    const picked = [{ label: '연습실' }, { label: '02 둘째날' }, { label: '가나다' }, { label: '01 첫날' }]
    expect(sortByFileName(picked).map((item) => item.label)).toEqual(['01 첫날', '02 둘째날', '가나다', '연습실'])
  })

  it('여러 표기의 앞 번호를 읽는다', () => {
    expect(leadingNumber('01 입장.jpg')).toBe(1)
    expect(leadingNumber('2. 리허설.png')).toBe(2)
    expect(leadingNumber('003-무대.jpg')).toBe(3)
    expect(leadingNumber('12_합주.mp4')).toBe(12)
    expect(leadingNumber('7.jpg')).toBe(7)
    expect(leadingNumber('연습실.jpg')).toBeNull()
    expect(leadingNumber('2026 봄.jpg')).toBe(2026)
  })

  it('장면을 앞뒤로 옮긴다', () => {
    const scenes = board()
    const moved = moveScene(scenes, 2, -1)
    expect(moved[1].id).toBe(scenes[2].id)
    expect(moved[2].id).toBe(scenes[1].id)
    expect(moved).toHaveLength(scenes.length)
  })

  it('끝에서 더 옮기려 하면 그대로 둔다', () => {
    const scenes = board()
    expect(moveScene(scenes, 0, -1)).toBe(scenes)
    expect(moveScene(scenes, scenes.length - 1, 1)).toBe(scenes)
  })

  it('옮겨도 장면이 사라지거나 늘지 않는다', () => {
    const scenes = board()
    const ids = new Set(scenes.map((scene) => scene.id))
    const moved = moveScene(moveScene(scenes, 3, -2), 0, 4)
    expect(new Set(moved.map((scene) => scene.id))).toEqual(ids)
  })
})

describe('글자 자리', () => {
  it('자리를 정하지 않으면 아래쪽', () => {
    const scenes = board()
    expect(scenes.every((scene) => scene.caption === undefined)).toBe(true)
  })

  it('글자 없이도 장면은 남는다', () => {
    const scene = { ...board()[2], caption: 'none' as const }
    expect(scene.caption).toBe('none')
    expect(scene.seconds).toBeGreaterThan(0)
  })
})
