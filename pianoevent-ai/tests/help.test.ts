import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { escapeHtml, inline, manualImage, renderManual, slug } from '@/lib/help/markdown'

describe('설명서를 화면에 그리기', () => {
  it('HTML 을 먼저 막는다', () => {
    expect(escapeHtml('<script>alert(1)</script>')).toBe('&lt;script&gt;alert(1)&lt;/script&gt;')
    expect(inline('<b>굵게</b>')).toBe('&lt;b&gt;굵게&lt;/b&gt;')
  })

  it('굵게와 코드를 알아본다', () => {
    expect(inline('**중요**합니다')).toBe('<strong>중요</strong>합니다')
    expect(inline('`3:30` 처럼')).toBe('<code>3:30</code> 처럼')
  })

  it('코드 안의 별표는 굵게가 아니다', () => {
    expect(inline('`**별표**`')).toBe('<code>**별표**</code>')
  })

  it('앱 안 주소와 http 주소만 링크가 된다', () => {
    expect(inline('[도움말](/help)')).toBe('<a href="/help">도움말</a>')
    expect(inline('[밖](https://a.kr)')).toContain('target="_blank"')
    expect(inline('[나쁜](javascript:alert(1))')).toBe('[나쁜](javascript:alert(1))')
  })

  it('한글 제목이 자리표에 그대로 남는다', () => {
    expect(slug('학생 명단 넣기')).toBe('학생-명단-넣기')
    expect(slug('4-3. 무대 화면!')).toBe('4-3-무대-화면')
    expect(slug('***')).toBe('section')
  })

  it('## 마다 절이 나뉜다', () => {
    const { title, sections } = renderManual('# 사용설명서\n\n## 첫째\n글\n\n## 둘째\n글')
    expect(title).toBe('사용설명서')
    expect(sections.map((row) => row.title)).toEqual(['첫째', '둘째'])
  })

  it('### 는 절 안에 남는다', () => {
    const { sections } = renderManual('## 첫째\n\n### 안쪽\n글')
    expect(sections).toHaveLength(1)
    expect(sections[0].html).toContain('<h3')
    expect(sections[0].html).toContain('안쪽')
  })

  it('제목이 겹쳐도 자리표는 하나씩만', () => {
    const { sections } = renderManual('## 같은 이름\n글\n\n## 같은 이름\n글')
    expect(sections[0].id).not.toBe(sections[1].id)
  })

  it('표를 그린다', () => {
    const { sections } = renderManual('## 표\n\n| 무엇 | 어떻게 |\n|---|---|\n| 이름 | 적으세요 |')
    expect(sections[0].html).toContain('<table>')
    expect(sections[0].html).toContain('<th>무엇</th>')
    expect(sections[0].html).toContain('<td>적으세요</td>')
  })

  it('목록·인용·구분선·코드덩이를 그린다', () => {
    const { sections } = renderManual(
      '## 여러 가지\n\n- 하나\n- 둘\n\n1. 첫째\n2. 둘째\n\n> 알아 두실 것\n\n---\n\n```\n김서연\n```',
    )
    const html = sections[0].html
    expect(html).toContain('<ul><li>하나</li><li>둘</li></ul>')
    expect(html).toContain('<ol><li>첫째</li><li>둘째</li></ol>')
    expect(html).toContain('<blockquote><p>알아 두실 것</p></blockquote>')
    expect(html).toContain('<hr />')
    expect(html).toContain('<pre><code>김서연</code></pre>')
  })

  it('여러 줄 문단은 한 덩이로 묶는다', () => {
    const { sections } = renderManual('## 글\n첫 줄\n둘째 줄\n\n다음 문단')
    expect(sections[0].html).toContain('<p>첫 줄 둘째 줄</p>')
    expect(sections[0].html).toContain('<p>다음 문단</p>')
  })

  it('제목이 없는 글도 무너지지 않는다', () => {
    expect(renderManual('그냥 글').sections).toHaveLength(0)
    expect(renderManual('').sections).toEqual([])
  })
})

describe('한 항목이 여러 줄로 넘어갈 때', () => {
  it('들여쓴 다음 줄은 그 항목에 이어 붙는다', () => {
    const { sections } = renderManual('## 차례\n\n1. 첫째 줄\n   이어지는 말\n2. 둘째\n')
    expect(sections[0].html).toBe('<ol><li>첫째 줄 이어지는 말</li><li>둘째</li></ol>')
  })

  it('그래서 번호가 1부터 다시 매겨지지 않는다 — 목록이 하나로 남는다', () => {
    const { sections } = renderManual('## 차례\n\n1. 하나\n   이어짐\n2. 둘\n   이어짐\n3. 셋\n')
    expect((sections[0].html.match(/<ol>/g) ?? [])).toHaveLength(1)
    expect((sections[0].html.match(/<li>/g) ?? [])).toHaveLength(3)
  })

  it('들여쓰지 않은 다음 줄은 목록 밖이다', () => {
    const { sections } = renderManual('## 차례\n\n- 하나\n다음 문단\n')
    expect(sections[0].html).toContain('<ul><li>하나</li></ul>')
    expect(sections[0].html).toContain('<p>다음 문단</p>')
  })

  it('점 목록도 같다', () => {
    const { sections } = renderManual('## 차례\n\n- 하나\n  이어짐\n- 둘\n')
    expect(sections[0].html).toBe('<ul><li>하나 이어짐</li><li>둘</li></ul>')
  })
})

describe('설명서 그림', () => {
  it('파일 자리 기준 주소를 화면 주소로 바꾼다 — GitHub 과 프로그램 양쪽에서 보이게', () => {
    expect(manualImage('../public/manual/roster.jpg')).toBe('/manual/roster.jpg')
  })

  it('이미 화면 주소면 그대로 둔다', () => {
    expect(manualImage('/manual/roster.jpg')).toBe('/manual/roster.jpg')
  })

  it('바깥 주소의 그림은 싣지 않는다 — 인터넷 없이 도는 프로그램이다', () => {
    expect(manualImage('https://example.com/x.jpg')).toBeNull()
    expect(manualImage('//example.com/x.jpg')).toBeNull()
  })

  it('그림을 <img> 로 그린다', () => {
    expect(inline('![명단 화면](../public/manual/roster.jpg)')).toBe(
      '<img src="/manual/roster.jpg" alt="명단 화면" loading="lazy" class="help-shot" />',
    )
  })

  it('그림을 링크로 잘못 읽지 않는다', () => {
    expect(inline('![그림](../public/manual/a.jpg)')).not.toContain('<a ')
  })

  it('설명 없는 그림도 그린다', () => {
    expect(inline('![](../public/manual/a.jpg)')).toContain('alt=""')
  })

  it('링크는 그대로 링크다', () => {
    expect(inline('[사용설명서](/help)')).toBe('<a href="/help">사용설명서</a>')
  })
})

describe('진짜 설명서 파일', () => {
  const manual = readFileSync(join(process.cwd(), 'docs', 'MANUAL.md'), 'utf8')
  const rendered = renderManual(manual)

  it('절마다 나뉜다', () => {
    expect(rendered.sections.length).toBeGreaterThan(10)
  })

  it('적어 둔 그림이 하나도 빠짐없이 <img> 로 그려진다', () => {
    // 대괄호가 섞인 설명글 하나면 그림이 통째로 글자로 나온다. 눈으로는 못 잡는다.
    const written = [...manual.matchAll(/!\[[^\]]*\]\([^)\s]+\)/g)].length
    const drawn = rendered.sections.reduce(
      (sum, s) => sum + [...s.html.matchAll(/<img\b/g)].length,
      0,
    )
    expect(written).toBeGreaterThan(5)
    expect(drawn).toBe(written)
  })

  it('그림 주소가 전부 프로그램 안 주소로 바뀐다', () => {
    for (const section of rendered.sections) {
      for (const m of section.html.matchAll(/<img[^>]*src="([^"]+)"/g)) {
        expect(m[1].startsWith('/manual/')).toBe(true)
      }
    }
  })

  it('그림 파일이 실제로 있다 — 설명서에 깨진 그림이 뜨면 안 된다', () => {
    for (const m of manual.matchAll(/!\[[^\]]*\]\(([^)\s]+)\)/g)) {
      const app = manualImage(m[1])
      expect(app).not.toBeNull()
      expect(existsSync(join(process.cwd(), 'public', app!.replace(/^\//, '')))).toBe(true)
    }
  })
})
