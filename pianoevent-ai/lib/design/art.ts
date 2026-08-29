/**
 * 연주회 그림.
 *
 * 인쇄물에 쓰는 그림은 **밖에서 만들어 넣는다.** 코드로 그린 피아노는 화면에서는
 * 그럴듯해도 A4 로 뽑으면 어설프다. 원장님이 파실 물건에 그런 그림을 둘 수 없다.
 *
 * 지금 들어 있는 것은 미드저니로 만들어 고른 그림이고, 만든 분이 쓰실 권리를 가진다.
 * 프로그램과 함께 깔리므로 인터넷 없이 뜨고, 학원 밖으로 나가지 않는다.
 * 만드는 법과 프롬프트는 `docs/ART-PROMPTS.md`.
 */

/** 그림의 밝기 — 글씨 색을 여기서 가른다 */
export type ArtTone = 'dark' | 'light'

/** 글이 앉을 자리. 그림마다 비어 있는 쪽이 다르다 */
export type ArtAnchor = 'top-left' | 'top-right' | 'top-center'

export interface PosterArt {
  id: string
  /** public 아래 주소 */
  src: string
  /** 화면에 적을 이름 */
  name: string
  tone: ArtTone
  anchor: ArtAnchor
  /**
   * 글 뒤에 까는 검은(또는 흰) 막의 진하기 0~1.
   * 0 이면 막을 깔지 않는다 — 그림이 이미 비어 있다는 뜻이다.
   * 막은 얇을수록 좋다. 두꺼우면 그림을 고른 이유가 사라진다.
   */
  scrim: number
  /**
   * 밝은 그림만 쓴다. 그림이 시작하는 높이(%)와 아래 여백(%).
   *
   * 수채는 흰 여백을 넉넉히 두고 그려져 있어 25% 부터 담아도 글씨와 안 겹친다.
   * 그런데 벚꽃처럼 **그림 가장자리까지 그려진 것**은 같은 값으로 담으면 날짜를 덮는다.
   * 그림마다 그려진 자리가 다르므로 여기서 따로 준다.
   */
  inset?: { top: number; bottom: number }
  /**
   * 밝은 그림은 보통 흰 종이에 그린 수채라 담아서(contain) 넣는다.
   * 그런데 **밝은 사진**(여름 창가처럼)은 담으면 흰 여백만 커지고 사진이 작아진다.
   * 그런 것만 가득 채우게(cover) 표시해 둔다.
   */
  fill?: 'cover' | 'contain'
  /**
   * 막의 색.
   *
   * 어두운 사진에는 검은 막을 깔고 흰 글씨를 얹는다(기본).
   * 그런데 **밝은 사진**에 검은 막을 깔면 사진을 고른 이유가 사라진다.
   * 그런 것에는 **흰 막**을 깔고 테마의 어두운 글씨를 그대로 쓴다 — 잉크도 덜 든다.
   */
  scrimTone?: 'dark' | 'light'
}

export const POSTER_ART: PosterArt[] = [
  {
    id: 'stage-piano',
    src: '/art/poster/stage-piano.jpg',
    name: '무대 위 그랜드피아노',
    tone: 'dark',
    anchor: 'top-left',
    scrim: 0.3,
  },
  {
    id: 'oil-hall',
    src: '/art/poster/oil-hall.jpg',
    name: '유화 무대',
    tone: 'dark',
    anchor: 'top-center',
    scrim: 0.34,
  },
  {
    id: 'keys-close',
    src: '/art/poster/keys-close.jpg',
    name: '건반',
    tone: 'dark',
    anchor: 'top-left',
    scrim: 0.24,
  },
  {
    id: 'child-hands',
    src: '/art/poster/child-hands.jpg',
    name: '아이의 손',
    tone: 'dark',
    anchor: 'top-left',
    scrim: 0.38,
  },
  {
    id: 'gala-bokeh',
    src: '/art/poster/gala-bokeh.jpg',
    name: '빛과 실루엣',
    tone: 'dark',
    anchor: 'top-center',
    scrim: 0.18,
  },
  {
    id: 'light-field',
    src: '/art/poster/light-field.jpg',
    name: '빛의 들판',
    tone: 'dark',
    anchor: 'top-center',
    scrim: 0.16,
  },
  // 밝은 그림은 흰 종이에 그린 수채다. 종이색과 곱하기로 겹쳐 테마 종이색이 그대로 비친다
  {
    id: 'watercolor-piano',
    src: '/art/poster/watercolor-piano.jpg',
    name: '수채 피아노',
    tone: 'light',
    anchor: 'top-center',
    scrim: 0,
  },
  {
    id: 'blossom-piano',
    src: '/art/poster/blossom-piano.jpg',
    name: '꽃과 피아노',
    tone: 'light',
    anchor: 'top-right',
    scrim: 0,
    // 벚꽃이 그림 위쪽 끝까지 그려져 있어 더 내려 담는다
    inset: { top: 33, bottom: 12 },
  },
  {
    id: 'summer-window',
    src: '/art/poster/summer-window.jpg',
    name: '여름 창가',
    tone: 'light',
    anchor: 'top-left',
    // 창과 커튼이 위쪽까지 밝게 이어져 흰 글씨로는 묻힌다.
    // 흰 막을 얇게 깔고 테마의 어두운 글씨를 얹는다
    scrim: 0.5,
    scrimTone: 'light',
    fill: 'cover',
  },
  {
    id: 'autumn-leaves',
    src: '/art/poster/autumn-leaves.jpg',
    name: '가을 낙엽',
    tone: 'dark',
    anchor: 'top-right',
    scrim: 0.3,
  },
  {
    id: 'christmas-pine',
    src: '/art/poster/christmas-pine.jpg',
    name: '크리스마스',
    tone: 'dark',
    anchor: 'top-left',
    scrim: 0.34,
  },
  {
    id: 'confetti-night',
    src: '/art/poster/confetti-night.jpg',
    name: '금빛 축하',
    tone: 'dark',
    anchor: 'top-left',
    scrim: 0.24,
  },
]

export function getPosterArt(id: string): PosterArt {
  return POSTER_ART.find((a) => a.id === id) ?? POSTER_ART[0]
}

/** 무대 화면·감동영상 뒤에 까는 그림 (16:9) */
export const STAGE_ART = [
  { id: 'curtain', src: '/art/stage/curtain.jpg', name: '무대 커튼', tone: 'dark' as ArtTone },
  { id: 'keys-wide', src: '/art/stage/keys-wide.jpg', name: '건반', tone: 'dark' as ArtTone },
  { id: 'bokeh', src: '/art/stage/bokeh.jpg', name: '금빛 조명', tone: 'dark' as ArtTone },
  { id: 'paper', src: '/art/stage/paper.jpg', name: '미색 종이', tone: 'light' as ArtTone },
]

/**
 * 상장·초대장에 얹는 장식.
 *
 * 미드저니는 배경이 비치는 그림을 주지 않아 **검은 바탕**에 그리게 했다.
 * 화면에서는 `mix-blend-mode: screen` 으로 검정을 날린다 — 검정은 screen 에서 사라진다.
 * 잘라 낸 가장자리가 지저분해지지 않아 오려 내기보다 결과가 깨끗하다.
 */
export const ORNAMENT_ART = [
  { id: 'laurel', src: '/art/ornament/laurel.png', name: '월계관' },
  { id: 'corner', src: '/art/ornament/corner.png', name: '금박 모서리' },
  { id: 'staff', src: '/art/ornament/staff.png', name: '오선과 음표' },
  { id: 'ribbon', src: '/art/ornament/ribbon.png', name: '리본 매듭' },
  { id: 'divider', src: '/art/ornament/divider.png', name: '구분선' },
  { id: 'clef', src: '/art/ornament/clef.png', name: '높은음자리표' },
  { id: 'sparkle', src: '/art/ornament/sparkle.png', name: '반짝임' },
  { id: 'cert-border', src: '/art/ornament/cert-border.png', name: '상장 테두리' },
  { id: 'piano-mark', src: '/art/ornament/piano-mark.png', name: '피아노 표식' },
]

/**
 * 바탕 질감.
 *
 * 테마의 종이는 단색이었다. 여기에 **아주 옅은 결**이 들어가면 인쇄물 전체가 한 단계
 * 올라간다. 그림은 양식 하나만 바꾸지만 질감은 **테마 108종 전부**를 바꾼다.
 *
 * 눈에 띄면 실패다 — 글씨를 방해한다. 그래서 옅게(10~18%) 곱하기로만 겹친다.
 */
export const TEXTURE_ART = {
  cotton: '/art/texture/paper-cotton.jpg',
  linen: '/art/texture/paper-linen.jpg',
  marble: '/art/texture/paper-marble.jpg',
  velvet: '/art/texture/velvet.jpg',
} as const

/** 금박. 제목 글씨를 이 질감으로 칠한다 — 진짜 금박으로 찍은 것처럼 보인다 */
export const GOLD_FOIL = '/art/texture/gold-foil.jpg'

/** 금가루. 검은 바탕에 금점이라 마스크로 뿌린다 */
export const GOLD_FLECKS = '/art/texture/gold-flecks.png'
