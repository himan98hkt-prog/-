import { describe, expect, it } from 'vitest'
import { buildReceipt } from '@/lib/program/receipt'
import { parseRoster } from '@/lib/program/roster'

const receipt = (text: string) => buildReceipt(parseRoster(text))

describe('이렇게 읽었습니다', () => {
  it('몇 명인지 사람 말로 먼저 알려 준다', () => {
    const r = receipt('김서연\t엘리제를 위하여\n박지호\t즐거운 나의 집')
    expect(r.count).toBe(2)
    expect(r.lines[0].text).toContain('2명')
  })

  it('한 아이가 두 곡이면 사람 수와 무대 수를 따로 센다', () => {
    const r = receipt('김서연\t엘리제를 위하여\n김서연\t소나티네\n박지호\t즐거운 나의 집')
    expect(r.people).toBe(2)
    expect(r.count).toBe(3)
    expect(r.lines[0].text).toContain('아이 2명')
    expect(r.lines[0].text).toContain('무대 3번')
  })

  it('머리글을 건너뛰었으면 그렇게 적어 준다', () => {
    const r = receipt('이름\t연주곡\n김서연\t엘리제를 위하여')
    expect(r.lines.some((l) => l.text.includes('머리글'))).toBe(true)
  })

  it('머리글이 없으면 어느 차례로 읽었는지 적어 준다 — 열이 밀렸는지 아셔야 한다', () => {
    const r = receipt('김서연\t엘리제를 위하여\t베토벤')
    expect(r.lines.some((l) => l.text.includes('이름 · 연주곡 · 작곡가'))).toBe(true)
  })

  it('곡이 빈 아이를 이름까지 짚어 준다', () => {
    const r = receipt('이름\t연주곡\n김서연\t\n박지호\t즐거운 나의 집')
    const line = r.lines.find((l) => l.text.includes('연주곡이 빈'))
    expect(line?.text).toContain('김서연')
    expect(line?.tone).toBe('warn')
  })

  it('이름과 곡이 한 칸에 붙어 있으면 짚어 준다 — 가장 흔한 실수다', () => {
    const r = receipt('김서연 엘리제를 위하여\n박지호 즐거운 나의 집')
    const line = r.lines.find((l) => l.text.includes('한 칸에 붙어'))
    expect(line?.tone).toBe('warn')
    expect(r.needsLook).toBe(true)
  })

  it('곡 사전이 채운 것을 알려 준다', () => {
    const r = receipt('이름\t연주곡\n김서연\t엘리제를 위하여')
    expect(r.lines.some((l) => l.text.includes('곡 사전'))).toBe(true)
  })

  it('난이도가 전부 기초로 들어가면 한 번 보시라고 한다', () => {
    const r = receipt('이름\t연주곡\t난이도\n김서연\t없는곡ㄱ\t\n박지호\t없는곡ㄴ\t')
    expect(r.lines.some((l) => l.text.includes('난이도가 전부'))).toBe(true)
  })

  it('난이도가 제대로 들어갔으면 잔소리하지 않는다', () => {
    const r = receipt('이름\t연주곡\t난이도\n김서연\t없는곡ㄱ\t중급\n박지호\t없는곡ㄴ\t고급')
    expect(r.lines.some((l) => l.text.includes('난이도가 전부'))).toBe(false)
  })

  it('이름이 없어 건너뛴 줄을 알려 준다', () => {
    const r = receipt('이름\t연주곡\n\t엘리제를 위하여\n박지호\t즐거운 나의 집')
    expect(r.lines.some((l) => l.text.includes('건너뛰'))).toBe(true)
  })

  it('모두 멀쩡하면 살펴볼 것이 없다고 한다', () => {
    const r = receipt('이름\t연주곡\t난이도\n김서연\t엘리제를 위하여\t중급\n박지호\t즐거운 나의 집\t초급')
    expect(r.needsLook).toBe(false)
  })
})
