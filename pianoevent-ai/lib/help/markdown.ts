/**
 * 사용설명서를 화면에 띄우기 위한 아주 작은 마크다운 변환기.
 *
 * 설명서는 `docs/MANUAL.md` 한 곳에만 둔다. 같은 글을 두 벌 쓰면 반드시 어긋난다.
 * 그런데 원장님은 GitHub 을 열지 않으신다 — 프로그램 안에서 보셔야 한다.
 * 그래서 그 파일을 그대로 읽어 화면에 그린다.
 *
 * 바깥 라이브러리를 쓰지 않는다. 인터넷 없이 도는 프로그램이고, 설명서 하나 때문에
 * 짐을 늘릴 이유가 없다. 우리가 쓰는 문법만 다룬다 —
 * 제목 · 문단 · 굵게 · 코드 · 목록 · 표 · 인용 · 구분선 · 링크.
 *
 * 들어오는 글은 우리가 쓴 파일이지만, 그래도 **HTML 을 먼저 막고** 시작한다.
 * 나중에 원장님이 손대실 수 있는 자리가 되면 그때 가서 뚫린 채로 두면 늦는다.
 */

export interface HelpSection {
  /** 화면에서 이동할 때 쓰는 자리표 */
  id: string
  /** 몇 번째 단계인가 (## 은 1, ### 은 2) */
  level: number
  title: string
  html: string
}

const ESCAPES: Record<string, string> = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
}

export function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (ch) => ESCAPES[ch])
}

/** 제목에서 자리표를 만든다 — 한글이 그대로 남아야 주소를 봐도 어디인지 안다 */
export function slug(title: string): string {
  return (
    title
      .trim()
      .toLowerCase()
      .replace(/[^\p{Letter}\p{Number}\s-]/gu, '')
      .replace(/\s+/g, '-')
      .replace(/-+/g, '-')
      .replace(/^-|-$/g, '') || 'section'
  )
}

/** 코드 조각을 잠깐 빼 둘 때 쓰는 표 — 설명서 본문에 나올 수 없는 모양이어야 한다 */
const CODE_SLOT = (index: number) => `@@code-${index}@@`

/** 한 줄 안의 꾸밈 — 굵게 · 코드 · 링크. 반드시 HTML 을 막은 뒤에 붙인다 */
export function inline(text: string): string {
  let out = escapeHtml(text)
  // 코드부터 빼 둔다 — 그 안의 별표는 굵게가 아니다
  const codes: string[] = []
  out = out.replace(/`([^`]+)`/g, (_all, body: string) => {
    codes.push(body)
    return CODE_SLOT(codes.length - 1)
  })
  out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  out = out.replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>')
  // 링크 — 우리가 쓴 파일이지만 주소는 http(s) 와 앱 안 경로만 받는다
  out = out.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (all, label: string, href: string) => {
    if (!/^(https?:\/\/|\/|#)/.test(href)) return all
    const external = href.startsWith('http')
    const attrs = external ? ' target="_blank" rel="noopener noreferrer"' : ''
    return `<a href="${escapeHtml(href)}"${attrs}>${label}</a>`
  })
  out = out.replace(/@@code-(\d+)@@/g, (_all, index: string) => `<code>${codes[Number(index)]}</code>`)
  return out
}

function tableRow(line: string): string[] {
  return line
    .replace(/^\||\|$/g, '')
    .split('|')
    .map((cell) => cell.trim())
}

const isDivider = (line: string) => /^\|?[\s:|-]+\|[\s:|-]*$/.test(line) && line.includes('-')

/**
 * 마크다운을 절 단위로 나눠 HTML 로 바꾼다.
 * `##` 마다 새 절이 시작된다 — 화면 왼쪽 차례표가 이 단위로 만들어진다.
 */
export function renderManual(markdown: string): { title: string; sections: HelpSection[] } {
  const lines = markdown.replace(/\r\n/g, '\n').split('\n')
  let title = '사용설명서'
  const sections: HelpSection[] = []
  let current: HelpSection | null = null
  const buffer: string[] = []

  const seen = new Map<string, number>()
  const uniqueId = (text: string) => {
    const base = slug(text)
    const count = (seen.get(base) ?? 0) + 1
    seen.set(base, count)
    return count === 1 ? base : `${base}-${count}`
  }

  const flush = () => {
    if (current) {
      current.html = buffer.join('\n')
      sections.push(current)
    }
    buffer.length = 0
  }

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i]

    if (/^#\s+/.test(line)) {
      title = line.replace(/^#\s+/, '').trim()
      continue
    }
    if (/^####\s+/.test(line)) {
      buffer.push(`<h4>${inline(line.replace(/^####\s+/, '').trim())}</h4>`)
      continue
    }
    if (/^###?\s+/.test(line)) {
      const level = line.startsWith('###') ? 2 : 1
      const text = line.replace(/^#{2,3}\s+/, '').trim()
      if (level === 1) {
        flush()
        current = { id: uniqueId(text), level, title: text, html: '' }
      } else {
        if (!current) current = { id: uniqueId(title), level: 1, title, html: '' }
        buffer.push(`<h3 id="${uniqueId(text)}">${inline(text)}</h3>`)
      }
      continue
    }
    if (/^\s*---+\s*$/.test(line)) {
      buffer.push('<hr />')
      continue
    }
    if (/^```/.test(line)) {
      const code: string[] = []
      i += 1
      while (i < lines.length && !/^```/.test(lines[i])) {
        code.push(lines[i])
        i += 1
      }
      buffer.push(`<pre><code>${escapeHtml(code.join('\n'))}</code></pre>`)
      continue
    }
    // 표 — 머리줄 다음이 구분선이면 표로 본다
    if (line.includes('|') && lines[i + 1] && isDivider(lines[i + 1])) {
      const head = tableRow(line)
      const rows: string[][] = []
      i += 2
      while (i < lines.length && lines[i].includes('|') && lines[i].trim()) {
        rows.push(tableRow(lines[i]))
        i += 1
      }
      i -= 1
      const headHtml = head.map((cell) => `<th>${inline(cell)}</th>`).join('')
      const bodyHtml = rows
        .map((row) => `<tr>${row.map((cell) => `<td>${inline(cell)}</td>`).join('')}</tr>`)
        .join('')
      buffer.push(`<table><thead><tr>${headHtml}</tr></thead><tbody>${bodyHtml}</tbody></table>`)
      continue
    }
    if (/^>\s?/.test(line)) {
      const quote: string[] = []
      while (i < lines.length && /^>\s?/.test(lines[i])) {
        quote.push(lines[i].replace(/^>\s?/, ''))
        i += 1
      }
      i -= 1
      buffer.push(`<blockquote>${quote.map((row) => (row ? `<p>${inline(row)}</p>` : '')).join('')}</blockquote>`)
      continue
    }
    if (/^\s*[-*]\s+/.test(line) || /^\s*\d+\.\s+/.test(line)) {
      const ordered = /^\s*\d+\.\s+/.test(line)
      const items: string[] = []
      while (i < lines.length) {
        if (/^\s*[-*]\s+/.test(lines[i]) || /^\s*\d+\.\s+/.test(lines[i])) {
          items.push(lines[i].replace(/^\s*(?:[-*]|\d+\.)\s+/, ''))
          i += 1
          continue
        }
        // 한 항목이 길어 다음 줄로 넘어간 것 — 들여쓴 채 이어진다.
        // 여기서 목록을 끊으면 번호가 1부터 다시 매겨져 "1. 2. 3." 이 "1. 1. 2." 가 된다.
        if (items.length > 0 && /^\s+\S/.test(lines[i])) {
          items[items.length - 1] += ` ${lines[i].trim()}`
          i += 1
          continue
        }
        break
      }
      i -= 1
      const tag = ordered ? 'ol' : 'ul'
      buffer.push(`<${tag}>${items.map((item) => `<li>${inline(item)}</li>`).join('')}</${tag}>`)
      continue
    }
    if (line.trim()) {
      const para: string[] = []
      while (
        i < lines.length &&
        lines[i].trim() &&
        !/^(#{1,4}\s|>|```|\s*[-*]\s|\s*\d+\.\s|\s*---+\s*$)/.test(lines[i]) &&
        !(lines[i].includes('|') && lines[i + 1] && isDivider(lines[i + 1]))
      ) {
        para.push(lines[i].trim())
        i += 1
      }
      i -= 1
      buffer.push(`<p>${inline(para.join(' '))}</p>`)
      continue
    }
  }
  flush()
  return { title, sections }
}
