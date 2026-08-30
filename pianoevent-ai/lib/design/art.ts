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
export type ArtTone =
  | 'dark'
  /** 흰 종이에 그린 것 — 종이색이 비쳐 보이게 곱해서 겹친다 */
  | 'light'
  /**
   * 검은 바탕에 금선으로 그린 것.
   *
   * 색을 그대로 쓰지 않는다. **모양(마스크)으로 써서 테마 강조색으로 칠한다.**
   * 남색 테마에서는 남색 피아노가, 버건디 테마에서는 버건디 피아노가 된다.
   * 한 장이 테마 108종 색으로 다 나오는 셈이다.
   */
  | 'line'

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
  /* ── 테마 색을 입는 선화 ───────────────────────────────────────
     한 장이 테마 108종 색으로 나온다. 종이도 테마 종이색 그대로다. */
  {
    id: 'line-front',
    src: '/art/line/piano-front.png',
    name: '선화 · 피아노',
    tone: 'line',
    anchor: 'top-center',
    scrim: 0,
  },
  {
    id: 'line-keys',
    src: '/art/line/keys-notes.png',
    name: '선화 · 건반과 음표',
    tone: 'line',
    anchor: 'top-left',
    scrim: 0,
  },
  {
    id: 'line-arch',
    src: '/art/line/arch.png',
    name: '선화 · 무대 아치',
    tone: 'line',
    anchor: 'top-center',
    scrim: 0,
  },
  /* ── 일러스트 ─────────────────────────────────────────────── */
  {
    id: 'ill-line',
    src: '/art/poster/line-piano.jpg',
    name: '한 줄 선화',
    tone: 'light',
    anchor: 'top-center',
    // 그림에 제 종이 질감이 있어 담으면 네모 이음매가 보인다. 통째로 채운다 —
    // 그림의 종이가 곧 포스터 종이가 되고, 글 자리는 흰 막으로 눌러 준다
    fill: 'cover',
    scrim: 0.4,
    scrimTone: 'light',
  },
  {
    id: 'ill-engraving',
    src: '/art/poster/engraving.jpg',
    name: '고전 동판화',
    tone: 'light',
    anchor: 'top-center',
    // 그림에 제 종이 질감이 있어 담으면 네모 이음매가 보인다. 통째로 채운다 —
    // 그림의 종이가 곧 포스터 종이가 되고, 글 자리는 흰 막으로 눌러 준다
    fill: 'cover',
    scrim: 0.62,
    scrimTone: 'light',
  },
  {
    id: 'ill-riso',
    src: '/art/poster/riso.jpg',
    name: '2도 인쇄',
    tone: 'light',
    anchor: 'top-left',
    // 그림에 제 종이 질감이 있어 담으면 네모 이음매가 보인다. 통째로 채운다 —
    // 그림의 종이가 곧 포스터 종이가 되고, 글 자리는 흰 막으로 눌러 준다
    fill: 'cover',
    scrim: 0.34,
    scrimTone: 'light',
  },
  {
    id: 'ill-ink',
    src: '/art/poster/ink-wash.jpg',
    name: '수묵',
    tone: 'light',
    anchor: 'top-center',
    // 그림에 제 종이 질감이 있어 담으면 네모 이음매가 보인다. 통째로 채운다 —
    // 그림의 종이가 곧 포스터 종이가 되고, 글 자리는 흰 막으로 눌러 준다
    fill: 'cover',
    scrim: 0.4,
    scrimTone: 'light',
  },
  {
    id: 'ill-deco',
    src: '/art/poster/deco.jpg',
    name: '아르데코',
    tone: 'light',
    anchor: 'top-right',
    // 왼쪽은 그림이 꽉 차 있고 오른쪽 한 칸이 비어 있다. 사진처럼 가득 채운다
    fill: 'cover',
    scrim: 0.42,
    scrimTone: 'light',
  },
  /* ── 실사 ─────────────────────────────────────────────────── */
  {
    id: 'real-stage',
    src: '/art/poster/real-stage.jpg',
    name: '무대 (사진)',
    tone: 'dark',
    anchor: 'top-center',
    scrim: 0.16,
  },
  {
    id: 'real-keys',
    src: '/art/poster/real-keys.jpg',
    name: '건반 (사진)',
    tone: 'dark',
    anchor: 'top-left',
    scrim: 0.34,
  },
  {
    id: 'real-hands',
    src: '/art/poster/real-hands.jpg',
    name: '아이의 손 (사진)',
    tone: 'dark',
    anchor: 'top-left',
    scrim: 0.3,
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
  // 금가루는 질감 폴더에 있지만 쓰는 방식은 장식과 같다 — 검은 바탕이라 모양으로 쓴다
  { id: 'flecks', src: '/art/texture/gold-flecks.png', name: '금가루' },
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

/** 프로그램 화면에 쓰는 그림 — 인쇄물이 아니라 앱 자신을 위한 것 */
export const APP_ART = {
  /** 첫 화면 히어로 (21:9) */
  hero: '/art/app/hero-wide.jpg',
  /** 프로그램 아이콘 */
  icon: '/art/app/icon.png',
  /** 설치 화면 왼쪽 세로 배너 */
  installerSide: '/art/app/installer-side.jpg',
  /** 켜지는 동안 보여 드릴 화면 */
  splash: '/art/app/splash.jpg',
} as const
