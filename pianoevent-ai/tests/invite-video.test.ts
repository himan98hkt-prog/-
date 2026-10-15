import { describe, expect, it } from 'vitest'
import { embedHint, videoEmbed } from '@/lib/video/embed'

describe('초대장에 붙이는 영상 주소', () => {
  it('유튜브의 여러 주소 모양을 모두 알아본다', () => {
    const wanted = 'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ'
    for (const url of [
      'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
      'https://youtube.com/watch?v=dQw4w9WgXcQ&feature=share',
      'https://m.youtube.com/watch?v=dQw4w9WgXcQ',
      'https://youtu.be/dQw4w9WgXcQ',
      'https://www.youtube.com/embed/dQw4w9WgXcQ',
      'https://www.youtube.com/shorts/dQw4w9WgXcQ',
      'https://www.youtube.com/live/dQw4w9WgXcQ',
    ]) {
      const embed = videoEmbed(url)
      expect(embed?.kind, url).toBe('youtube')
      expect(embed?.src, url).toBe(wanted)
    }
  })

  it('유튜브는 광고 추적이 덜한 nocookie 주소로 바꿔 보낸다', () => {
    // 초대장은 학부모 휴대폰에서 열린다. 우리가 고를 수 있는 쪽을 고른다
    expect(videoEmbed('https://www.youtube.com/watch?v=dQw4w9WgXcQ')?.src).toContain('youtube-nocookie.com')
  })

  it('시작 시각이 붙어 있으면 그 자리에서 시작한다', () => {
    expect(videoEmbed('https://youtu.be/dQw4w9WgXcQ?t=90s')?.src).toBe(
      'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ?start=90',
    )
  })

  it('Vimeo 도 화면 안에서 재생된다', () => {
    expect(videoEmbed('https://vimeo.com/123456789')?.src).toBe('https://player.vimeo.com/video/123456789')
  })

  it('mp4 주소는 그대로 재생한다', () => {
    const embed = videoEmbed('https://cdn.example.com/2026/recital.mp4')
    expect(embed?.kind).toBe('file')
    expect(embed?.src).toBe('https://cdn.example.com/2026/recital.mp4')
  })

  it('모르는 주소는 "영상 보기" 단추로만 — 남의 화면을 우리 초대장 안에 끼우지 않는다', () => {
    const embed = videoEmbed('https://drive.google.com/file/d/abc/view')
    expect(embed?.kind).toBe('link')
  })

  it('http(s) 가 아니면 붙이지 않는다', () => {
    expect(videoEmbed('javascript:alert(1)')).toBeNull()
    expect(videoEmbed('data:text/html,<script>')).toBeNull()
    expect(videoEmbed('file:///C:/영상.mp4')).toBeNull()
    expect(videoEmbed('그냥 글자')).toBeNull()
    expect(videoEmbed('')).toBeNull()
    expect(videoEmbed(null)).toBeNull()
  })

  it('유튜브를 흉내 낸 주소에 속지 않는다', () => {
    // youtube.com.evil.kr 은 유튜브가 아니다
    expect(videoEmbed('https://youtube.com.evil.kr/watch?v=dQw4w9WgXcQ')?.kind).toBe('link')
    // 영상 id 는 11 글자다
    expect(videoEmbed('https://youtu.be/짧음')?.kind).toBe('link')
  })

  it('원장님께 어떻게 보일지 한 줄로 알려 준다', () => {
    expect(embedHint(videoEmbed('https://youtu.be/dQw4w9WgXcQ'))).toContain('바로 재생')
    expect(embedHint(videoEmbed('https://drive.google.com/file/d/abc/view'))).toContain('단추')
    expect(embedHint(null)).toContain('주소가 없습니다')
  })
})
