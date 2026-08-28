/**
 * 초대장에 붙이는 영상 주소.
 *
 * 감동영상은 원장님 컴퓨터에서 만들어진다 — 아이들 얼굴이 우리 서버로
 * 올라오지 않는다는 약속이 그 뿌리다. 그래서 만든 파일을 여기에 올려 드릴 수는 없다.
 *
 * 대신 **원장님이 올려 둔 곳의 주소**를 받는다. 유튜브 일부공개(미등록),
 * 구글 드라이브, 학원 홈페이지 — 어디든 좋다. 학부모는 초대장 링크 하나만
 * 받으면 순서표도 보고 영상도 본다.
 *
 * 어디에 올릴지는 원장님이 정하신다. 우리는 그 주소를 어떻게 보여 줄지만 안다.
 */

export type EmbedKind =
  /** 화면 안에서 바로 재생된다 */
  | 'youtube'
  | 'vimeo'
  /** mp4 처럼 파일을 그대로 가리키는 주소 */
  | 'file'
  /** 무엇인지 알 수 없다 — 눌러서 새 창으로 여는 단추만 보여 준다 */
  | 'link'

export interface VideoEmbed {
  kind: EmbedKind
  /** iframe · video 에 넣을 주소 */
  src: string
  /** 원래 주소 (새 창으로 열기) */
  href: string
}

const YOUTUBE_ID = /^[\w-]{11}$/

function youtubeId(url: URL): string | null {
  const host = url.hostname.replace(/^www\./, '')
  if (host === 'youtu.be') {
    const id = url.pathname.slice(1)
    return YOUTUBE_ID.test(id) ? id : null
  }
  if (host !== 'youtube.com' && host !== 'm.youtube.com' && host !== 'youtube-nocookie.com') return null
  const v = url.searchParams.get('v')
  if (v && YOUTUBE_ID.test(v)) return v
  const match = /^\/(?:embed|shorts|live|v)\/([\w-]{11})/.exec(url.pathname)
  return match ? match[1] : null
}

function vimeoId(url: URL): string | null {
  if (!url.hostname.replace(/^www\./, '').endsWith('vimeo.com')) return null
  const match = /^\/(?:video\/)?(\d{6,12})/.exec(url.pathname)
  return match ? match[1] : null
}

/**
 * 주소를 보고 어떻게 보여 줄지 정한다.
 * http(s) 가 아니면 아무것도 돌려주지 않는다 — 초대장은 학부모가 여는 공개 화면이다.
 */
export function videoEmbed(raw: string | null | undefined): VideoEmbed | null {
  const text = (raw ?? '').trim()
  if (!text) return null
  let url: URL
  try {
    url = new URL(text)
  } catch {
    return null
  }
  if (url.protocol !== 'http:' && url.protocol !== 'https:') return null
  const href = url.toString()

  const yt = youtubeId(url)
  if (yt) {
    // nocookie 로 보낸다 — 학부모 휴대폰에 광고 추적을 덜 남긴다
    const start = Number(url.searchParams.get('t')?.replace(/s$/, '') ?? '')
    const query = Number.isFinite(start) && start > 0 ? `?start=${Math.floor(start)}` : ''
    return { kind: 'youtube', src: `https://www.youtube-nocookie.com/embed/${yt}${query}`, href }
  }

  const vm = vimeoId(url)
  if (vm) return { kind: 'vimeo', src: `https://player.vimeo.com/video/${vm}`, href }

  if (/\.(mp4|webm|mov|m4v)$/i.test(url.pathname)) return { kind: 'file', src: href, href }

  return { kind: 'link', src: href, href }
}

/** 원장님 화면에 "이렇게 보입니다" 라고 알려 주는 한 줄 */
export function embedHint(embed: VideoEmbed | null): string {
  if (!embed) return '아직 주소가 없습니다.'
  switch (embed.kind) {
    case 'youtube':
      return '유튜브 영상이 초대장 안에서 바로 재생됩니다.'
    case 'vimeo':
      return 'Vimeo 영상이 초대장 안에서 바로 재생됩니다.'
    case 'file':
      return '영상 파일이 초대장 안에서 바로 재생됩니다.'
    case 'link':
      return '초대장에 "영상 보기" 단추가 생깁니다. 눌러야 새 창에서 열립니다.'
  }
}
