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
})
