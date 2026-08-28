import { describe, expect, it } from 'vitest'
import { buildProgram } from '@/lib/program/order'
import { getTheme } from '@/lib/design/themes'
import {
  buildTimeline,
  describeRecordType,
  drawLogo,
  fadeFor,
  getLogoPlace,
  LOGO_PLACES,
  renderFrame,
  scenesAt,
  CAPTION_FADE_SEC,
  CROSSFADE_SEC,
  type LogoMark,
} from '@/lib/video/render'
import {
  DEFAULT_VIDEO_TEMPLATE,
  getVideoTemplate,
  VIDEO_TEMPLATES,
} from '@/lib/video/templates'
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
  type VideoScene,
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

describe('영상 템플릿', () => {
  it('열 가지가 준비돼 있다', () => {
    expect(VIDEO_TEMPLATES).toHaveLength(10)
    expect(new Set(VIDEO_TEMPLATES.map((t) => t.id)).size).toBe(10)
  })

  it('사진을 꽉 채우는 것과 배경 위에 얹는 것이 모두 있다', () => {
    const fits = new Set(VIDEO_TEMPLATES.map((t) => t.fit))
    expect(fits.has('full')).toBe(true)
    expect(fits.has('frame')).toBe(true)
    expect(fits.has('half')).toBe(true)
    expect(fits.has('polaroid')).toBe(true)
  })

  it('배경도 여러 가지를 쓴다 — 단색만 있지 않다', () => {
    const backdrops = new Set(VIDEO_TEMPLATES.map((t) => t.backdrop))
    expect(backdrops.size).toBeGreaterThanOrEqual(6)
    expect([...backdrops].some((id) => id !== 'plain')).toBe(true)
  })

  it('움직임이 서로 다르다 — 모두 같으면 지겹다', () => {
    expect(new Set(VIDEO_TEMPLATES.map((t) => t.motion)).size).toBeGreaterThanOrEqual(4)
  })

  it('이름과 설명이 모두 있다', () => {
    for (const item of VIDEO_TEMPLATES) {
      expect(item.name.length).toBeGreaterThan(1)
      expect(item.hint.length).toBeGreaterThan(10)
    }
  })

  it('없는 이름을 주면 기본 템플릿으로', () => {
    expect(getVideoTemplate('없는것').id).toBe(DEFAULT_VIDEO_TEMPLATE.id)
    expect(getVideoTemplate(null).id).toBe(DEFAULT_VIDEO_TEMPLATE.id)
    expect(getVideoTemplate('frame-keys').id).toBe('frame-keys')
  })
})

describe('멈춘 화면 그리기', () => {
  /** 캔버스가 없는 곳에서도 돌도록 그리기 명령만 받아 적는 가짜 붓 */
  function stub() {
    const texts: string[] = []
    const alphas: number[] = []
    const ctx = {
      canvas: { width: 1280, height: 720 },
      globalAlpha: 1,
      fillStyle: '',
      strokeStyle: '',
      lineWidth: 1,
      font: '',
      textAlign: '',
      textBaseline: '',
      shadowColor: '',
      shadowBlur: 0,
      shadowOffsetY: 0,
      save() {}, restore() {}, beginPath() {}, closePath() {}, clip() {}, fill() {}, stroke() {},
      moveTo() {}, lineTo() {}, quadraticCurveTo() {}, arc() {}, arcTo() {}, ellipse() {}, rect() {},
      fillRect() {}, drawImage() {}, translate() {}, rotate() {}, scale() {},
      fillText(text: string) {
        texts.push(text)
        alphas.push((ctx as unknown as { globalAlpha: number }).globalAlpha)
      },
      measureText(text: string) {
        return { width: text.length * 20 }
      },
      createLinearGradient() {
        return { addColorStop() {} }
      },
      createRadialGradient() {
        return { addColorStop() {} }
      },
    }
    return { ctx: ctx as unknown as CanvasRenderingContext2D, texts, alphas }
  }

  const line: VideoScene[] = [
    { id: 'a', kind: 'title', seconds: 4, eyebrow: '하모니', headline: '제12회 정기 연주회', sub: '2026' },
    { id: 'b', kind: 'student', seconds: 3.5, eyebrow: '1번째 무대', headline: '오수아', sub: '인벤션 1번' },
  ]
  const timeline = buildTimeline(line)
  const options = { width: 1280, height: 720, theme: getTheme('classic-navy'), academyName: '하모니' }
  const empty = { images: new Map(), videos: new Map() }

  it('장면이 시작하는 바로 그 순간에도 글자가 보인다', () => {
    // 콘티에서 장면을 누르면 딱 이 지점이 된다.
    // 겹쳐 넘어가는 중이라 들어오는 장면이 투명해, 예전에는 빈 화면이 떴다.
    const { ctx, texts, alphas } = stub()
    renderFrame(ctx, timeline, timeline.starts[1], empty, options, true)
    expect(texts.join(' ')).toContain('오수아')
    expect(Math.max(...alphas)).toBe(1)
  })

  it('멈춘 화면에는 앞 장면이 겹쳐 나오지 않는다', () => {
    const { ctx, texts } = stub()
    renderFrame(ctx, timeline, timeline.starts[1], empty, options, true)
    expect(texts.join(' ')).not.toContain('제12회')
  })

  it('재생 중에는 겹치는 그대로 그린다', () => {
    const { ctx, alphas } = stub()
    renderFrame(ctx, timeline, timeline.starts[1] + 0.05, empty, options, false)
    // 들어오는 장면은 아직 옅다
    expect(Math.min(...alphas, 1)).toBeLessThanOrEqual(1)
  })

  it('템플릿을 바꾸면 그리는 내용도 바뀐다', () => {
    const plain = stub()
    renderFrame(plain.ctx, timeline, 1, empty, { ...options, template: getVideoTemplate('full-classic') }, true)
    const keys = stub()
    renderFrame(keys.ctx, timeline, 1, empty, { ...options, template: getVideoTemplate('frame-keys') }, true)
    expect(plain.texts.join(' ')).toBe(keys.texts.join(' '))
  })
})

describe('영상에 학원 로고 넣기', () => {
  function logoStub() {
    const drawn: { source: unknown; x: number; y: number; w: number; h: number; alpha: number }[] = []
    const ctx = {
      canvas: { width: 1280, height: 720 },
      globalAlpha: 1,
      fillStyle: '',
      strokeStyle: '',
      lineWidth: 1,
      font: '',
      textAlign: '',
      textBaseline: '',
      shadowColor: '',
      shadowBlur: 0,
      shadowOffsetY: 0,
      save() {}, restore() {}, beginPath() {}, closePath() {}, clip() {}, fill() {}, stroke() {},
      moveTo() {}, lineTo() {}, quadraticCurveTo() {}, arc() {}, arcTo() {}, ellipse() {}, rect() {},
      fillRect() {}, translate() {}, rotate() {}, scale() {}, fillText() {},
      drawImage(source: unknown, x: number, y: number, w: number, h: number) {
        drawn.push({ source, x, y, w, h, alpha: (ctx as unknown as { globalAlpha: number }).globalAlpha })
      },
      measureText(text: string) {
        return { width: text.length * 20 }
      },
      createLinearGradient() {
        return { addColorStop() {} }
      },
      createRadialGradient() {
        return { addColorStop() {} }
      },
    }
    return { ctx: ctx as unknown as CanvasRenderingContext2D, drawn }
  }

  const mark = (place: LogoMark['place']): LogoMark => ({
    image: {} as CanvasImageSource,
    width: 200,
    height: 100,
    place,
  })

  const line: VideoScene[] = [
    { id: 'a', kind: 'title', seconds: 4, headline: '제12회 정기 연주회' },
    { id: 'b', kind: 'student', seconds: 3.5, headline: '오수아' },
  ]
  const timeline = buildTimeline(line)
  const base = { width: 1280, height: 720, theme: getTheme('classic-navy'), academyName: '하모니' }
  const empty = { images: new Map(), videos: new Map() }

  it('넣지 않기를 고르면 그리지 않는다', () => {
    const { ctx, drawn } = logoStub()
    renderFrame(ctx, timeline, 1, empty, { ...base, logo: mark('none') }, true)
    expect(drawn).toHaveLength(0)
  })

  it('네 귀퉁이 모두 화면 안에 들어간다', () => {
    for (const place of ['top-left', 'top-right', 'bottom-left', 'bottom-right'] as const) {
      const { ctx, drawn } = logoStub()
      renderFrame(ctx, timeline, 1, empty, { ...base, logo: mark(place) }, true)
      expect(drawn, place).toHaveLength(1)
      const box = drawn[0]
      expect(box.x, place).toBeGreaterThanOrEqual(0)
      expect(box.y, place).toBeGreaterThanOrEqual(0)
      expect(box.x + box.w, place).toBeLessThanOrEqual(1280)
      expect(box.y + box.h, place).toBeLessThanOrEqual(720)
    }
  })

  it('가로세로 비율이 찌그러지지 않는다', () => {
    const { ctx, drawn } = logoStub()
    renderFrame(ctx, timeline, 1, empty, { ...base, logo: mark('bottom-right') }, true)
    expect(drawn[0].w / drawn[0].h).toBeCloseTo(200 / 100, 5)
  })

  it('화면을 가릴 만큼 크지 않다', () => {
    const { ctx, drawn } = logoStub()
    renderFrame(ctx, timeline, 1, empty, { ...base, logo: mark('top-left') }, true)
    expect(drawn[0].h).toBeLessThan(720 * 0.1)
  })

  it('장면이 겹쳐 넘어가는 동안에도 로고는 한 번만, 같은 진하기로 그려진다', () => {
    // 로고까지 함께 깜빡이면 눈에 거슬린다 — 장면의 진하기를 물려받지 않는다
    const mid = logoStub()
    renderFrame(mid.ctx, timeline, 1, empty, { ...base, logo: mark('bottom-right') }, false)
    const fading = logoStub()
    renderFrame(fading.ctx, timeline, timeline.starts[1] + 0.05, empty, { ...base, logo: mark('bottom-right') }, false)
    expect(fading.drawn).toHaveLength(1)
    expect(fading.drawn[0].alpha).toBe(mid.drawn[0].alpha)
  })

  it('크기를 모르는 로고는 그리지 않는다 — 0 으로 나눠 화면이 깨지지 않게', () => {
    const { ctx, drawn } = logoStub()
    drawLogo(ctx, { image: {} as CanvasImageSource, width: 0, height: 0, place: 'top-left' }, 1280, 720)
    expect(drawn).toHaveLength(0)
  })

  it('저장된 자리 값이 이상하면 넣지 않는 쪽으로 돌아간다', () => {
    expect(getLogoPlace('bottom-right')).toBe('bottom-right')
    expect(getLogoPlace('가운데')).toBe('none')
    expect(getLogoPlace(null)).toBe('none')
    expect(LOGO_PLACES.map((item) => item.id)).toContain('none')
  })
})

describe('한 아이가 여러 곡을 맡을 때의 영상', () => {
  const twice = [
    student('김서연', 'beginner', 90, { id: 'a1', piece_title: '나비야' }),
    student('박지호', 'beginner', 100, { id: 'b1', piece_title: '즐거운 나의 집' }),
    student('김서연', 'ensemble', 140, { id: 'a2', piece_title: '왕벌의 비행' }),
    student('정예린', 'intermediate', 170, { id: 'c1', piece_title: '아라베스크' }),
  ]
  const twicePlan = buildProgram(twice)
  const scenes = buildStoryboard({
    event,
    plan: twicePlan,
    academyName: '하모니 피아노학원',
    photos: { a2: 'data:image/png;base64,AA' },
  })
  const students = scenes.filter((scene) => scene.kind === 'student')

  it('같은 얼굴이 두 번 지나가지 않는다', () => {
    expect(students).toHaveLength(3)
    expect(students.filter((scene) => scene.headline === '김서연')).toHaveLength(1)
  })

  it('맡은 곡을 한 장면에 함께 적는다', () => {
    const seoyeon = students.find((scene) => scene.headline === '김서연')
    expect(seoyeon?.sub).toContain('나비야')
    expect(seoyeon?.sub).toContain('왕벌의 비행')
  })

  it('두 번 오르는 순번을 함께 적는다', () => {
    const seoyeon = students.find((scene) => scene.headline === '김서연')
    expect(seoyeon?.eyebrow).toMatch(/\d+ · \d+번째 무대/)
  })

  it('사진은 어느 줄에 붙어 있든 찾아 쓴다', () => {
    expect(students.find((scene) => scene.headline === '김서연')?.image).toBe('data:image/png;base64,AA')
  })

  it('두 곡을 맡은 아이는 화면에 조금 더 머문다 — 읽을 것이 많다', () => {
    const seoyeon = students.find((scene) => scene.headline === '김서연')
    const jiho = students.find((scene) => scene.headline === '박지호')
    expect(seoyeon!.seconds).toBeGreaterThan(jiho!.seconds)
  })

  it('머릿말에 사람 수와 곡 수를 함께 적는다', () => {
    const intro = scenes.find((scene) => scene.id === 'roster-intro')
    expect(intro?.sub).toBe('3명 · 4곡')
  })
})
