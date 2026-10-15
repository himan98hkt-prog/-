// 설명서 검사기 — 설명서가 틀린 채로 나가지 않게 막는 마지막 문.
//
// CI 에는 스크린샷이 없어서 `npm run manual` 이 건너뛰어집니다. 그러면 빌더 안의
// 검사도 같이 건너뛰어집니다. 그래서 검사 자체를 여기서 따로 돌립니다.

import { describe, expect, it } from 'vitest'
import { lintManual } from '../scripts/manual-lint.js'
import { META, PARTS } from '../scripts/manual-content.js'

const PNG = 'data:image/jpeg;base64,AAAA'
const good = `
<nav><a href="#part1">1부</a><a href="#ch1">1장</a></nav>
<main>
  <div class="part" id="part1"><h2 id="ch1">시작하기</h2>
    <section id="s-a"><figure><img src="${PNG}" alt="화면"><figcaption>가</figcaption></figure></section>
  </div>
</main>`

describe('설명서 검사기', () => {
  it('멀쩡한 문서는 통과시킨다', () => {
    expect(lintManual(good, { figures: 1 })).toEqual([])
  })

  it('목차가 없는 곳을 가리키면 잡는다', () => {
    const doc = good.replace('href="#ch1"', 'href="#ch9"')
    expect(lintManual(doc)).toEqual(['목차가 없는 곳을 가리킵니다: #ch9'])
  })

  // 이게 이 검사기를 만든 이유입니다. 그림이 이미 문서 안에 있어서 미룰 통신이
  // 없는데, 미루면 종이로 뽑을 때 아래쪽 그림이 빈칸으로 나옵니다.
  it('그림에 loading= 이 붙으면 잡는다 (인쇄하면 빈칸이 된다)', () => {
    const doc = good.replace('alt="화면"', 'alt="화면" loading="lazy"')
    expect(lintManual(doc, { figures: 1 })).toEqual([
      '그림에 loading= 이 붙어 있습니다 (인쇄하면 빈칸)'])
  })

  it('그림이 문서 밖 파일을 가리키면 잡는다 (옮기다 빠진다)', () => {
    const doc = good.replace(PNG, 'screenshots/piano-00.png')
    expect(lintManual(doc, { figures: 1 })).toEqual(['그림이 문서 밖 파일을 가리킵니다'])
  })

  it('원고가 부른 그림 수와 실제가 다르면 잡는다', () => {
    expect(lintManual(good, { figures: 20 })).toEqual([
      '그림 수가 맞지 않습니다: 원고 20 · 문서 1'])
  })

  it('같은 문제는 한 번만 말한다', () => {
    const doc = good + good.replace('alt="화면"', 'alt="화면" loading="lazy"')
      .replace('alt="화면"', 'alt="화면" loading="lazy"')
    expect(lintManual(doc).filter((m) => m.includes('loading='))).toHaveLength(1)
  })

  it('그림 수를 안 넘기면 그 검사는 하지 않는다', () => {
    expect(lintManual(good)).toEqual([])
  })
})

describe('설명서 원고', () => {
  const sections = PARTS.flatMap((p) => p.chapters.flatMap((c) => c.sections))

  it('절마다 제목과 내용이 있다', () => {
    const bad = sections.filter((s) => !s.title || (!s.body?.length && !s.table))
    expect(bad.map((s) => s.id)).toEqual([])
  })

  it('id 가 겹치지 않는다 (겹치면 목차가 엉뚱한 곳으로 간다)', () => {
    const ids = sections.map((s) => s.id)
    expect(ids.length).toBe(new Set(ids).size)
  })

  it('같은 그림을 두 번 쓰지 않는다', () => {
    const shots = sections.map((s) => s.shot).filter(Boolean)
    expect(shots.length).toBe(new Set(shots).size)
  })

  it('관리노트와 반주를 모두 다룬다', () => {
    expect(PARTS.length).toBeGreaterThanOrEqual(2)
    expect(META.title).toContain('사용설명서')
  })

  // 빌더(scripts/manual.mjs)가 아는 항목. 여기 없는 이름을 원고에 쓰면 그 내용이
  // **아무 말 없이 사라집니다** — 설명서는 멀쩡하게 만들어지고, 빠진 걸 아무도
  // 모릅니다. 실제로 `body2` 를 쓰면서 빌더에 넣는 걸 잊어 한 번 겪었습니다.
  // 항목을 새로 만들려면 빌더에 렌더링을 넣고 이 목록에도 더하세요.
  // `only` 는 렌더링되는 항목이 아니라 **따로 파는 판**을 위한 표시다
  // (`--product mr`). 빌더가 아는 것이 맞으므로 여기 들어간다.
  const KNOWN = ['id', 'title', 'shot', 'body', 'table', 'body2', 'trap', 'only']

  it('빌더가 모르는 항목을 쓰지 않는다 (쓰면 그 내용이 조용히 빠진다)', () => {
    const strays = sections.flatMap((s) =>
      Object.keys(s).filter((k) => !KNOWN.includes(k)).map((k) => `${s.id}.${k}`))
    expect(strays).toEqual([])
  })

  it('only 표시가 빌더가 아는 값이다 (오타면 그 절이 안 빠진다)', () => {
    // `only: 'note'` 를 `'notes'` 로 쓰면 걸러지지 않고 반주 설명서에 남는다.
    // 빠지는 쪽이 아니라 **남는 쪽**이라 눈에 안 띈다.
    const PRODUCTS = ['mr', 'note']
    const bad = []
    for (const part of PARTS) {
      if (part.only && !PRODUCTS.includes(part.only)) bad.push(`${part.id}=${part.only}`)
      for (const ch of part.chapters || []) {
        if (ch.only && !PRODUCTS.includes(ch.only)) bad.push(`${ch.id}=${ch.only}`)
        for (const s of ch.sections || []) {
          if (s.only && !PRODUCTS.includes(s.only)) bad.push(`${s.id}=${s.only}`)
        }
      }
    }
    expect(bad).toEqual([])
  })

  it('반주만 파는 판에서 관리노트 원고가 빠진다', () => {
    // 이게 안 되면 반주만 사신 분이 받는 책에 출석부·수납 이야기가 실린다.
    const onlyNote = []
    for (const part of PARTS) {
      if (part.only === 'note') { onlyNote.push(part.id); continue }
      for (const ch of part.chapters || []) {
        for (const s of ch.sections || []) if (s.only === 'note') onlyNote.push(s.id)
      }
    }
    expect(onlyNote).toContain('part1')
    expect(onlyNote.length).toBeGreaterThan(5)
  })

  it('표 뒤에 오는 본문(body2)이 실제로 쓰이고 있다', () => {
    // 빌더에서 body2 렌더링이 사라지면 이 절의 두 문단이 조용히 빠집니다.
    // 원고 쪽에서는 그걸 볼 수 없으니, 최소한 쓰이고 있다는 것만 못 박습니다.
    const withBody2 = sections.filter((s) => s.body2?.length)
    expect(withBody2.length).toBeGreaterThan(0)
    for (const s of withBody2) expect(s.table).toBeTruthy()   // 표 없이 쓸 이유가 없다
  })
})
