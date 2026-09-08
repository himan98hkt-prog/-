import { describe, expect, it } from 'vitest'
import { buildStoryboard, CLIP_MAX_SEC, clipWindow } from '@/lib/video/storyboard'

/**
 * 동영상 **구간 자르기**.
 *
 * 휴대폰으로 찍은 영상은 앞이 흔들리고 「자, 시작」 같은 말이 들어 있다.
 * 그 앞을 잘라 내는 규칙이 미리보기·녹화·화면 세 곳에서 **같아야** 한다 —
 * 하나라도 다르면 원장님이 보신 자리와 뽑힌 영상의 자리가 어긋난다.
 */
describe('clipWindow', () => {
  it('적지 않으시면 처음부터', () => {
    expect(clipWindow({ seconds: 4 }, 10)).toEqual({ start: 0, maxStart: 6, short: 0 })
  })

  it('앞을 잘라 내면 그 자리에서 시작한다', () => {
    const w = clipWindow({ seconds: 4, clipStart: 2.5 }, 10)
    expect(w.start).toBe(2.5)
    expect(w.short).toBe(0)
  })

  it('끝까지 밀 수 있는 자리는 길이에서 머무는 시간을 뺀 만큼', () => {
    expect(clipWindow({ seconds: 4 }, 10).maxStart).toBe(6)
    expect(clipWindow({ seconds: 9 }, 10).maxStart).toBe(1)
  })

  it('너무 뒤로 미시면 끝이 넘치지 않도록 당겨 쓴다', () => {
    // 10초 영상에 4초 장면 — 8초부터 쓰면 2초가 빈다. 6초로 당긴다.
    const w = clipWindow({ seconds: 4, clipStart: 8 }, 10)
    expect(w.start).toBe(6)
    expect(w.short).toBe(0)
  })

  it('적으신 값 자체는 건드리지 않는다 — 되돌리실 수 있어야 하니까', () => {
    const scene = { seconds: 4, clipStart: 8 }
    clipWindow(scene, 10)
    expect(scene.clipStart).toBe(8)
  })

  it('장면이 동영상보다 길면 모자란 만큼을 알려 준다', () => {
    const w = clipWindow({ seconds: 6, clipStart: 3 }, 4)
    expect(w.start).toBe(0) // 밀 자리가 없다
    expect(w.maxStart).toBe(0)
    expect(w.short).toBeCloseTo(2, 5) // 마지막 2초는 멈춘 화면
  })

  it('길이를 아직 못 쟀으면 적으신 값을 그대로 둔다', () => {
    // 재는 중에 0으로 당겨 버리면 화면에서 슬라이더가 튄다
    expect(clipWindow({ seconds: 4, clipStart: 3 }, 0)).toEqual({ start: 3, maxStart: 0, short: 0 })
    expect(clipWindow({ seconds: 4, clipStart: 3 }, Number.NaN).start).toBe(3)
  })

  it('뒤로 적으신 값은 처음으로 본다', () => {
    expect(clipWindow({ seconds: 4, clipStart: -2 }, 10).start).toBe(0)
  })

  it('딱 맞는 길이는 남는 것도 모자란 것도 없다', () => {
    const w = clipWindow({ seconds: 10 }, 10)
    expect(w).toEqual({ start: 0, maxStart: 0, short: 0 })
  })
})

describe('올린 동영상이 처음 차지하는 시간', () => {
  const base = {
    event: { id: 'e1', title: '제1회 발표회', date: '2026-01-01', venue: '홀' },
    plan: { items: [] },
  } as unknown as Parameters<typeof buildStoryboard>[0]

  function clipScene(duration: number) {
    const scenes = buildStoryboard({
      ...base,
      extras: [{ id: 'v1', kind: 'video', url: 'blob:v1', label: '연습 영상', duration }],
    })
    return scenes.find((scene) => scene.kind === 'clip')
  }

  it('짧은 것은 통째로 쓴다', () => {
    expect(clipScene(5)?.seconds).toBeCloseTo(5, 5)
  })

  it('긴 것은 앞머리만 — 한 아이가 영상 절반을 먹지 않게', () => {
    expect(clipScene(40)?.seconds).toBe(CLIP_MAX_SEC)
  })

  it('긴 동영상에는 밀어 볼 자리가 남는다 — 안 남으면 자르기 칸이 무용지물이다', () => {
    const scene = clipScene(40)
    expect(scene).toBeDefined()
    expect(clipWindow(scene!, 40).maxStart).toBeGreaterThan(0)
  })
})

describe('장면 시간은 사람이 읽을 수 있는 숫자여야 한다', () => {
  it('셈으로 나온 시간도 0.1초로 끊어 준다', () => {
    // 응원 글은 「글자 수에 따라 조금 늘린다」로 계산된다 —
    // 그대로 두면 3.6666666666666666 이 콘티에 그대로 찍힌다(실제로 그렇게 나왔다)
    const scenes = buildStoryboard({
      event: { id: 'e1', title: '제1회 발표회', date: '2026-01-01', venue: '홀' },
      plan: { items: [] },
      messages: [
        { name: '김○○', message: '가'.repeat(16) },
        { name: '박○○', message: '나'.repeat(40) },
        { name: '윤○○', message: '다'.repeat(7) },
      ],
    } as unknown as Parameters<typeof buildStoryboard>[0])
    // 응원 장면이 실제로 만들어졌는지부터 본다 — 안 만들어졌으면 이 검사는 아무것도 안 잰다
    expect(scenes.filter((scene) => scene.kind === 'message').length).toBe(3)
    expect(scenes.length).toBeGreaterThan(0)
    for (const scene of scenes) {
      const tenths = scene.seconds * 10
      expect(Math.abs(tenths - Math.round(tenths))).toBeLessThan(1e-9)
      expect(String(scene.seconds).replace('.', '').length).toBeLessThanOrEqual(3)
    }
  })
})
