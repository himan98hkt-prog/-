import { describe, expect, it } from 'vitest'
import {
  CHIME_LEAD_SEC,
  CHIME_SOUNDS,
  DEFAULT_CHIME_PREFS,
  chimeAtSec,
  chimeDue,
  chimeStorageKey,
  getChimeSound,
  parseChimePrefs,
  serializeChimePrefs,
} from '@/lib/ops/chime'

describe('다음 차례 알림음', () => {
  it('보통 곡은 끝나기 1분 전에 울린다', () => {
    expect(chimeAtSec(210)).toBe(210 - CHIME_LEAD_SEC)
  })

  it('알림보다 짧은 곡은 절반쯤에서 한 번 울린다 — 아예 안 울리면 유아부는 알림이 하나도 없다', () => {
    expect(chimeAtSec(60)).toBe(30)
    expect(chimeAtSec(40)).toBe(20)
  })

  it('너무 짧으면 울리지 않는다 — 시작하자마자 울리면 뜻이 없다', () => {
    expect(chimeAtSec(10)).toBeNull()
    expect(chimeAtSec(0)).toBeNull()
    expect(chimeAtSec(Number.NaN)).toBeNull()
  })

  it('울릴 자리는 늘 그 순서 안이다', () => {
    for (const sec of [12, 30, 60, 95, 210, 600]) {
      const at = chimeAtSec(sec)
      if (at === null) continue
      expect(at, `${sec}초`).toBeGreaterThan(0)
      expect(at, `${sec}초`).toBeLessThan(sec)
    }
  })

  it('때가 되면 울릴 때라고 한다', () => {
    expect(chimeDue(0, 210)).toBe(false)
    expect(chimeDue(149, 210)).toBe(false)
    expect(chimeDue(150, 210)).toBe(true)
    expect(chimeDue(400, 210)).toBe(true)
  })

  it('울릴 자리가 없는 순서는 언제 봐도 울리지 않는다', () => {
    expect(chimeDue(5, 8)).toBe(false)
    expect(chimeDue(999, 8)).toBe(false)
  })

  it('행사마다 따로 담는다 — 한 행사에서 켜면 다른 행사도 켜지면 안 된다', () => {
    expect(chimeStorageKey('a')).not.toBe(chimeStorageKey('b'))
    expect(chimeStorageKey('a')).toContain('a')
  })
})

describe('알림 소리 고르기', () => {
  it('세 가지를 준다 — 홀마다 묻히는 소리가 다르다', () => {
    expect(CHIME_SOUNDS.length).toBe(3)
  })

  it('소리마다 어떤 자리에 맞는지 적혀 있다 — 들어 보기 전에 감이 와야 한다', () => {
    for (const sound of CHIME_SOUNDS) {
      expect(sound.name.length, sound.id).toBeGreaterThan(1)
      expect(sound.hint.length, sound.id).toBeGreaterThan(4)
      expect(sound.notes.length, sound.id).toBeGreaterThan(0)
    }
  })

  it('셋 다 0.7초 안에 끝난다 — 길면 객석이 듣는다', () => {
    for (const sound of CHIME_SOUNDS) {
      const end = Math.max(...sound.notes.map((n) => n.start + n.span))
      expect(end, sound.id).toBeLessThanOrEqual(0.7)
    }
  })

  it('셋 다 작은 소리다', () => {
    for (const sound of CHIME_SOUNDS) {
      for (const note of sound.notes) expect(note.gain ?? 0.22, sound.id).toBeLessThanOrEqual(0.3)
    }
  })

  it('모르는 소리를 부르면 첫 번째로 준다 — 멈추는 것보다 낫다', () => {
    expect(getChimeSound('없는소리').id).toBe(CHIME_SOUNDS[0].id)
    expect(getChimeSound(null).id).toBe(CHIME_SOUNDS[0].id)
  })
})

describe('알림 설정 담아 두기', () => {
  it('처음에는 꺼져 있다 — 묻지 않고 소리를 내지 않는다', () => {
    expect(DEFAULT_CHIME_PREFS.on).toBe(false)
    expect(DEFAULT_CHIME_PREFS.buzz).toBe(false)
  })

  it('담았다 되읽으면 그대로다', () => {
    const prefs = { on: true, soundId: CHIME_SOUNDS[2].id, buzz: true }
    expect(parseChimePrefs(serializeChimePrefs(prefs))).toEqual(prefs)
  })

  it('예전 판에서 켜 두신 것도 그대로 읽는다 — 설정이 사라지면 안 된다', () => {
    expect(parseChimePrefs('on').on).toBe(true)
    expect(parseChimePrefs('off').on).toBe(false)
  })

  it('담긴 것이 망가졌어도 멈추지 않는다', () => {
    expect(parseChimePrefs('{망가짐').on).toBe(false)
    expect(parseChimePrefs(null)).toEqual(DEFAULT_CHIME_PREFS)
  })

  it('없어진 소리를 담아 두셨으면 있는 것으로 바꿔 준다', () => {
    expect(parseChimePrefs('{"on":true,"soundId":"없어진것"}').soundId).toBe(CHIME_SOUNDS[0].id)
  })

  it('소리는 꺼도 진동만 켜 두실 수 있다 — 객석에 소리가 나면 안 되는 홀도 있다', () => {
    const prefs = parseChimePrefs('{"on":false,"buzz":true}')
    expect(prefs.on).toBe(false)
    expect(prefs.buzz).toBe(true)
  })
})
