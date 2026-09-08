import { describe, expect, it } from 'vitest'
import {
  applyCaptionAnim,
  applyTransition,
  drawSceneIcon,
  scenesAt,
  buildTimeline,
  typeCut,
} from '@/lib/video/render'
import { SCENE_ICONS, isCalmScene, type VideoScene } from '@/lib/video/storyboard'
import {
  CAPTION_ANIMS,
  ICON_ANIMS,
  TRANSITIONS,
  resolveCaptionAnim,
  resolveTransition,
  type TransitionKind,
} from '@/lib/video/templates'

/**
 * 전환 효과가 **실제로 무언가를 한다**는 것을 잰다.
 *
 * 종류를 늘어놓기만 하고 그리는 쪽을 안 고치면, 화면에서는 전부 똑같이 겹쳐 사라진다 —
 * 목록만 화려해지고 영상은 그대로인 셈이다. 그래서 붓에 실제로 어떤 명령이 갔는지 센다.
 */
/**
 * Path2D 는 브라우저에만 있다. 그림이 **명령을 내리는지**만 보면 되므로
 * 받은 것을 세어 두는 대역을 세운다.
 */
const paths: FakePath2D[] = []

class FakePath2D {
  ops: string[] = []
  constructor() { paths.push(this) }
  moveTo() { this.ops.push('moveTo') }
  lineTo() { this.ops.push('lineTo') }
  rect() { this.ops.push('rect') }
  arc() { this.ops.push('arc') }
  ellipse() { this.ops.push('ellipse') }
  closePath() { this.ops.push('closePath') }
  bezierCurveTo() { this.ops.push('bezierCurveTo') }
  quadraticCurveTo() { this.ops.push('quadraticCurveTo') }
}
;(globalThis as unknown as { Path2D: unknown }).Path2D = FakePath2D

function fakeCtx() {
  const calls: string[] = []
  const ctx = {
    translate: (x: number, y: number) => calls.push(`translate ${Math.round(x)} ${Math.round(y)}`),
    scale: (x: number, y: number) => calls.push(`scale ${x.toFixed(2)} ${y.toFixed(2)}`),
    rotate: (a: number) => calls.push(`rotate ${a.toFixed(3)}`),
    beginPath: () => calls.push('beginPath'),
    arc: () => calls.push('arc'),
    rect: () => calls.push('rect'),
    ellipse: () => calls.push('ellipse'),
    moveTo: () => calls.push('moveTo'),
    lineTo: () => calls.push('lineTo'),
    clip: () => calls.push('clip'),
    save: () => calls.push('save'),
    restore: () => calls.push('restore'),
    fill: () => calls.push('fill'),
    stroke: () => calls.push('stroke'),
    globalAlpha: 1,
    lineWidth: 0,
    lineJoin: '',
    lineCap: '',
    strokeStyle: '',
    fillStyle: '',
  }
  return { ctx: ctx as unknown as CanvasRenderingContext2D, calls }
}

const W = 1280
const H = 720

describe('전환 효과', () => {
  it('열한 가지가 서로 다른 id 를 가진다', () => {
    const ids = TRANSITIONS.map((t) => t.id)
    expect(new Set(ids).size).toBe(ids.length)
    expect(ids).toContain('auto')
  })

  it('다 들어온 뒤에는 아무것도 건드리지 않는다', () => {
    // enter 가 1 이면 제자리다. 여기서 붓을 옮기면 화면이 미세하게 떨린다
    for (const t of TRANSITIONS) {
      const { ctx, calls } = fakeCtx()
      expect(applyTransition(ctx, t.id, 1, 1, W, H)).toBe(1)
      expect(calls).toEqual([])
    }
  })

  it.each([
    ['slide-left', 'translate'],
    ['slide-right', 'translate'],
    ['slide-up', 'translate'],
    ['slide-down', 'translate'],
    ['zoom-in', 'scale'],
    ['zoom-out', 'scale'],
    ['circle', 'clip'],
    ['wipe', 'clip'],
    ['blinds', 'clip'],
  ] as [TransitionKind, string][])('%s 는 %s 를 실제로 한다', (kind, wanted) => {
    const { ctx, calls } = fakeCtx()
    applyTransition(ctx, kind, 0.4, 1, W, H)
    expect(calls.some((c) => c.startsWith(wanted))).toBe(true)
  })

  it('네 방향 밀기가 서로 다른 쪽으로 간다', () => {
    const move = (kind: TransitionKind) => {
      const { ctx, calls } = fakeCtx()
      applyTransition(ctx, kind, 0.4, 1, W, H)
      return calls.find((c) => c.startsWith('translate'))
    }
    const four = [move('slide-left'), move('slide-right'), move('slide-up'), move('slide-down')]
    expect(new Set(four).size).toBe(4)
  })

  it('자리로 보여 주는 전환은 반투명하게 겹치지 않는다', () => {
    // 밀기·오려내기를 반투명으로 겹치면 두 장면이 비쳐 지저분해진다
    for (const kind of ['slide-left', 'circle', 'wipe', 'blinds'] as TransitionKind[]) {
      const { ctx } = fakeCtx()
      expect(applyTransition(ctx, kind, 0.4, 0.4, W, H)).toBe(1)
    }
  })

  it('겹쳐 사라지기는 받은 진하기를 그대로 쓴다', () => {
    const { ctx, calls } = fakeCtx()
    expect(applyTransition(ctx, 'fade', 0.4, 0.4, W, H)).toBe(0.4)
    expect(calls).toEqual([])
  })
})

describe('「어울리게」가 고르는 것', () => {
  it('표지·마무리처럼 무게 있는 자리는 얌전하다', () => {
    for (const kind of ['title', 'closing', 'message'] as const) {
      expect(isCalmScene(kind)).toBe(true)
      expect(resolveTransition('auto', 3, isCalmScene(kind))).toBe('fade')
    }
  })

  it('아이들 사진은 조금 움직인다', () => {
    expect(resolveTransition('auto', 1, false)).not.toBe('fade')
  })

  it('같은 영상은 늘 같게 나온다 — 다시 뽑을 때마다 달라지면 되돌릴 수 없다', () => {
    const once = [0, 1, 2, 3, 4, 5, 6].map((i) => resolveTransition('auto', i, false))
    const twice = [0, 1, 2, 3, 4, 5, 6].map((i) => resolveTransition('auto', i, false))
    expect(once).toEqual(twice)
    // 여섯 가지를 돌려 쓰므로 이웃한 장면끼리 겹치지 않는다
    expect(new Set(once.slice(0, 6)).size).toBe(6)
  })

  it('원장님이 고르신 것은 그대로 쓴다', () => {
    expect(resolveTransition('circle', 0, true)).toBe('circle')
  })
})

describe('장면이 넘어오는 정도', () => {
  const scene = (id: string, kind: VideoScene['kind'], seconds: number): VideoScene => ({
    id, kind, seconds,
  })

  it('첫 장면은 넘어옴이 없다', () => {
    const line = buildTimeline([scene('a', 'title', 4), scene('b', 'student', 4)])
    const at = scenesAt(line, 0.1)
    expect(at[0].enter).toBe(1)
  })

  it('넘어오는 중에는 0 과 1 사이다', () => {
    const line = buildTimeline([scene('a', 'title', 4), scene('b', 'student', 4)])
    const at = scenesAt(line, 4.05)
    const incoming = at.find((v) => v.index === 1)
    expect(incoming).toBeDefined()
    expect(incoming!.enter).toBeGreaterThan(0)
    expect(incoming!.enter).toBeLessThan(1)
  })

  it('장면마다 어떤 전환인지 함께 알려 준다', () => {
    const line = buildTimeline([scene('a', 'title', 4), { ...scene('b', 'student', 4), transition: 'wipe' }])
    const at = scenesAt(line, 4.05)
    expect(at.find((v) => v.index === 1)?.transition).toBe('wipe')
  })
})

describe('작은 그림', () => {
  it('열 가지가 모두 실제로 그려진다 — 빠뜨린 것이 없다', () => {
    for (const icon of SCENE_ICONS) {
      const { ctx, calls } = fakeCtx()
      drawSceneIcon(ctx, { id: icon.id, size: 0.11, color: '#A07C2C' }, W, H, 1)
      expect(calls.filter((c) => c === 'fill' || c === 'stroke')).toHaveLength(2)
      // 빈 그림을 칠하고 있지 않은지 — 갈래를 빠뜨리면 아무것도 안 그려진다
      expect(paths.at(-1)!.ops.length).toBeGreaterThan(0)
      expect(calls[0]).toBe('save')
      expect(calls[calls.length - 1]).toBe('restore')
    }
  })

  it('자막처럼 늦게 떠오르도록 진하기를 따른다', () => {
    // 넘어오는 동안 두 장면의 그림이 함께 뜨면 화면 구석이 어수선해진다
    const { ctx } = fakeCtx()
    drawSceneIcon(ctx, { id: 'heart', size: 0.11, color: '#A07C2C' }, W, H, 0.3)
    expect(ctx.globalAlpha).toBe(0.3)
  })

  it('화면 크기에 따라 굵기가 함께 커진다 — 큰 화면에서 실처럼 가늘어지지 않게', () => {
    const small = fakeCtx()
    drawSceneIcon(small.ctx, { id: 'star', size: 0.11, color: '#A07C2C' }, 640, 360, 1)
    const big = fakeCtx()
    drawSceneIcon(big.ctx, { id: 'star', size: 0.11, color: '#A07C2C' }, 1920, 1080, 1)
    expect(big.ctx.lineWidth).toBeGreaterThan(small.ctx.lineWidth)
  })
})

describe('자막 등장', () => {
  it('여섯 가지가 서로 다른 id 를 가진다', () => {
    const ids = CAPTION_ANIMS.map((a) => a.id)
    expect(new Set(ids).size).toBe(ids.length)
    expect(ids).toContain('auto')
  })

  it('다 떠오른 뒤에는 붓을 건드리지 않는다', () => {
    // 장면의 대부분은 「다 뜬」 상태다. 여기서 옮기거나 키우면 자막이 미세하게 떤다
    for (const a of CAPTION_ANIMS) {
      const { ctx, calls } = fakeCtx()
      applyCaptionAnim(ctx, a.id, 1, H, H * 0.72)
      expect(calls).toEqual([])
    }
  })

  it('올라오기는 실제로 아래에서 위로 옮긴다', () => {
    const { ctx, calls } = fakeCtx()
    applyCaptionAnim(ctx, 'rise', 0, H, H * 0.72)
    const moved = calls.find((c) => c.startsWith('translate'))
    expect(moved).toBeDefined()
    // 아래(양수 y)에서 시작해 제자리로 올라온다
    expect(Number(moved!.split(' ')[2])).toBeGreaterThan(0)
  })

  it('올라오는 거리는 뜰수록 줄어든다', () => {
    const early = fakeCtx()
    applyCaptionAnim(early.ctx, 'rise', 0.2, H, H * 0.72)
    const late = fakeCtx()
    applyCaptionAnim(late.ctx, 'rise', 0.8, H, H * 0.72)
    const y = (c: { calls: string[] }) => Number(c.calls.find((x) => x.startsWith('translate'))!.split(' ')[2])
    expect(y(late)).toBeLessThan(y(early))
  })

  it('톡 튀어나오기는 작게 시작해 제 크기가 된다', () => {
    const { ctx, calls } = fakeCtx()
    applyCaptionAnim(ctx, 'pop', 0, H, H * 0.72)
    const scaled = calls.find((c) => c.startsWith('scale'))
    expect(scaled).toBeDefined()
    expect(Number(scaled!.split(' ')[1])).toBeLessThan(1)
  })

  it('톡 튀어나오기는 자막 자리를 붙잡고 키운다 — 아래 자막이 위로 솟지 않게', () => {
    const { ctx, calls } = fakeCtx()
    const anchorY = Math.round(H * 0.72)
    applyCaptionAnim(ctx, 'pop', 0.5, H, H * 0.72)
    expect(calls.filter((c) => c.startsWith('translate'))).toEqual([
      `translate 0 ${anchorY}`,
      `translate 0 ${-anchorY}`,
    ])
  })

  it('그냥 켜기와 스르르는 붓을 건드리지 않는다 — 진하기만으로 뜬다', () => {
    for (const kind of ['none', 'fade'] as const) {
      const { ctx, calls } = fakeCtx()
      applyCaptionAnim(ctx, kind, 0.3, H, H * 0.72)
      expect(calls).toEqual([])
    }
  })

  it('「어울리게」는 조용한 장면에만 얌전한 것을 준다', () => {
    expect(resolveCaptionAnim('auto', true)).toBe('fade')
    expect(resolveCaptionAnim('auto', false)).toBe('rise')
    expect(resolveCaptionAnim(undefined, false)).toBe('rise')
    // 골라 두신 것은 장면 성격보다 앞선다
    expect(resolveCaptionAnim('type', true)).toBe('type')
  })
})

describe('작은 그림 움직임', () => {
  it('네 가지가 서로 다른 id 를 가진다', () => {
    const ids = ICON_ANIMS.map((a) => a.id)
    expect(new Set(ids).size).toBe(ids.length)
  })

  it('나타날 때는 작게 시작한다', () => {
    const { ctx, calls } = fakeCtx()
    drawSceneIcon(ctx, { id: 'star', size: 0.11, color: '#A07C2C' }, W, H, 1, 'pop', 0, 0)
    const scaled = calls.find((c) => c.startsWith('scale'))
    expect(scaled).toBeDefined()
    expect(Number(scaled!.split(' ')[1])).toBeLessThan(1)
  })

  it('가만히는 아무 움직임도 걸지 않는다', () => {
    const { ctx, calls } = fakeCtx()
    drawSceneIcon(ctx, { id: 'star', size: 0.11, color: '#A07C2C' }, W, H, 1, 'none', 0, 3)
    expect(calls.some((c) => c.startsWith('scale') || c.startsWith('rotate'))).toBe(false)
  })

  it('살랑살랑은 시간이 흐르면 자리가 바뀐다 — 다 뜬 뒤에도 움직인다', () => {
    const y = (local: number) => {
      const { ctx, calls } = fakeCtx()
      drawSceneIcon(ctx, { id: 'star', size: 0.11, color: '#A07C2C' }, W, H, 1, 'bounce', 1, local)
      return calls.filter((c) => c.startsWith('translate')).map((c) => Number(c.split(' ')[2]))
    }
    // 1.6초에 한 번 오르내린다 — 4분의 1 지점이 가장 높다
    expect(y(0.4)).not.toEqual(y(1.2))
  })

  it('반짝이기는 좌우로 기운다', () => {
    const { ctx, calls } = fakeCtx()
    drawSceneIcon(ctx, { id: 'star', size: 0.11, color: '#A07C2C' }, W, H, 1, 'twinkle', 1, 0.55)
    expect(calls.some((c) => c.startsWith('rotate'))).toBe(true)
  })

  it('움직여도 붓은 제자리로 돌려놓는다 — 다음 장면이 기울지 않게', () => {
    for (const a of ICON_ANIMS) {
      const { ctx, calls } = fakeCtx()
      drawSceneIcon(ctx, { id: 'star', size: 0.11, color: '#A07C2C' }, W, H, 1, a.id, 0.3, 1.1)
      expect(calls[0]).toBe('save')
      expect(calls[calls.length - 1]).toBe('restore')
    }
  })
})

describe('한 글자씩 찍는 자막', () => {
  it('막 뜰 때는 아무것도 안 보이고, 다 뜨면 전부 보인다', () => {
    expect(typeCut(['김유진'], 0)).toEqual([''])
    expect(typeCut(['김유진'], 1)).toEqual(['김유진'])
  })

  it('앞에서부터 차례로 찍힌다', () => {
    expect(typeCut(['가나다라'], 0.5)).toEqual(['가나'])
  })

  it('줄 나눔은 그대로 둔다 — 찍히는 대로 줄을 다시 나누면 글줄이 튄다', () => {
    // 두 줄(3자 + 3자) 의 절반이면 첫 줄은 다 찍히고 둘째 줄이 시작된다
    const out = typeCut(['가나다', '라마바'], 0.5)
    expect(out).toHaveLength(2)
    expect(out[0]).toBe('가나다')
    expect(out[1]).toBe('')
  })

  it('둘째 줄은 첫 줄이 다 찍힌 뒤에 이어 찍힌다', () => {
    expect(typeCut(['가나다', '라마바'], 5 / 6)).toEqual(['가나다', '라마'])
  })

  it('범위를 벗어난 값에도 글자가 깨지지 않는다', () => {
    expect(typeCut(['가나다'], -1)).toEqual([''])
    expect(typeCut(['가나다'], 2)).toEqual(['가나다'])
  })

  it('빈 자막에도 줄 수는 그대로', () => {
    expect(typeCut([''], 0.5)).toEqual([''])
  })
})
