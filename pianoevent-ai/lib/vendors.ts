/**
 * 함께할 분들 — 연주회에 부르는 바깥 사람들을 적어 두는 수첩.
 *
 * 연주회 준비에서 프로그램이 못 해 주던 자리가 하나 있었다. 종이는 다 만들어
 * 드리는데 **연주홀·반주자·사회자·드레스·사진사·조율사는 원장님이 직접 알아보셔야**
 * 했다. 그런데 원장님의 진짜 고통은 처음 찾는 것보다 **매년 처음부터 다시 찾는 것**이다.
 * 작년에 쓴 사진사 연락처가 어느 카톡방에 있는지 기억이 안 난다.
 *
 * 그래서 이 파일이 하는 일은 셋이다.
 *   ① 갈래를 미리 정해 둔다 — 빈칸이 곧 「아직 안 정한 것」이 된다
 *   ② 지역을 붙인 지도 검색 주소를 만들어 준다 (찾는 수고를 던다)
 *   ③ 한 번 적은 곳을 학원 수첩에 쌓아 두었다가 내년에 그대로 꺼내 준다
 *
 * 밖으로 나가는 것은 **검색어뿐**이다. 아이 이름도 명단도 나가지 않는다.
 * 수첩은 원장님 컴퓨터 안에만 있다.
 */

export type VendorCategory = 'hall' | 'accompanist' | 'mc' | 'dress' | 'photo' | 'tuner'

export interface CategorySpec {
  id: VendorCategory
  label: string
  /** 지역 뒤에 붙일 검색어 */
  query: string
  /** 이 갈래가 왜 필요한지 한 줄 */
  detail: string
  /**
   * 지도 검색으로 찾아지는 갈래인가.
   *
   * 반주자와 사회자는 대개 개인이라 사업자 등록이 없다 — 지도에서 안 나온다.
   * 「검색해 보세요」만 내놓고 아무것도 안 나오면 원장님은 프로그램을 탓하신다.
   * 그래서 이 둘은 처음부터 다른 길을 안내한다.
   */
  findable: boolean
  /** 찾아지지 않는 갈래에 드리는 안내 */
  hint: string
  /**
   * 재능마켓(숨고)에서 사람이 실제로 구해지는 갈래인가.
   *
   * **공급이 없는 곳으로 보내 드리면 안 된다.** 연주홀 대관과 아동 드레스 대여는
   * 숨고에서 거의 안 나온다 — 그쪽은 지도로만 보낸다.
   */
  market: boolean
  /** 재능마켓에서 쓸 검색어 (지도 검색어와 부르는 말이 다르다) */
  marketQuery: string
}

export const CATEGORIES: CategorySpec[] = [
  {
    id: 'hall',
    label: '연주홀 · 대관',
    query: '소공연장 대관',
    detail: '가장 먼저 잠가야 하는 것. 날짜가 여기서 정해집니다.',
    findable: true,
    hint: '구민회관·문화의집·아트홀은 대개 지자체 누리집에서 예약합니다.',
    market: false,
    marketQuery: '',
  },
  {
    id: 'accompanist',
    label: '반주자',
    query: '피아노 반주자',
    detail: '연탄·협주 순서가 있으면 미리 잡아 두십시오.',
    findable: false,
    hint: '개인이라 지도에는 잘 안 나옵니다. 가까운 음대 학과 사무실, 지역 음악 선생님 모임, 반주자 구인 카페 쪽이 빠릅니다.',
    market: true,
    marketQuery: '피아노 반주',
  },
  {
    id: 'mc',
    label: '사회자',
    query: '행사 사회자',
    detail: '대본은 프로그램이 만들어 드립니다. 읽어 주실 분만 정하시면 됩니다.',
    findable: false,
    hint: '개인이라 지도에는 잘 안 나옵니다. 학부모·고학년 학생·선생님이 맡는 경우가 가장 많습니다.',
    market: true,
    marketQuery: '행사 사회자',
  },
  {
    id: 'dress',
    label: '드레스 대여',
    query: '아동 드레스 대여',
    detail: '치수와 반납일을 함께 적어 두십시오.',
    findable: true,
    hint: '',
    market: false,
    marketQuery: '',
  },
  {
    id: 'photo',
    label: '사진 · 영상',
    query: '행사 사진 촬영',
    detail: '감동영상에 쓸 사진도 이분께 부탁드리면 됩니다.',
    findable: true,
    hint: '',
    market: true,
    marketQuery: '행사 스냅 촬영',
  },
  {
    id: 'tuner',
    label: '조율사',
    query: '피아노 조율',
    detail: '행사 1~2일 전으로. 당일 조율은 리허설과 겹칩니다.',
    findable: true,
    hint: '',
    market: true,
    marketQuery: '피아노 조율',
  },
]

export const CATEGORY_LABEL: Record<VendorCategory, string> = Object.fromEntries(
  CATEGORIES.map((c) => [c.id, c.label]),
) as Record<VendorCategory, string>

export function categorySpec(id: string): CategorySpec | null {
  return CATEGORIES.find((c) => c.id === id) ?? null
}

/** 어디까지 진행됐는지. 원장님이 「이거 했나?」를 안 떠올리시게 */
export type BookingStatus = 'asking' | 'booked' | 'paid' | 'done'

export const STATUS_LABEL: Record<BookingStatus, string> = {
  asking: '알아보는 중',
  booked: '예약함',
  paid: '계약금 냄',
  done: '끝났음',
}

export const STATUS_ORDER: BookingStatus[] = ['asking', 'booked', 'paid', 'done']

export interface VendorBooking {
  name: string
  phone: string
  /** 원 단위 정수. 모르면 null */
  fee: number | null
  status: BookingStatus
  memo: string
  updated_at: string
}

export type VendorBookings = Partial<Record<VendorCategory, VendorBooking>>

/** 학원 수첩 한 줄 — 행사가 끝나도 남아 내년에 다시 꺼내진다 */
export interface VendorMemo {
  category: VendorCategory
  name: string
  phone: string
  fee: number | null
  memo: string
  /** 몇 번 쓰셨는지 — 많이 쓴 곳이 위로 온다 */
  used_count: number
  last_used_at: string
}

const NAME_MAX = 40
const MEMO_MAX = 200
const PHONE_MAX = 30
/** 갈래마다 이만큼만 쌓아 둔다. 목록이 길면 고르기가 오히려 어려워진다 */
export const BOOK_PER_CATEGORY = 6
/** 1원 ~ 1억. 이 밖은 잘못 치신 것으로 본다 */
export const FEE_MIN = 0
export const FEE_MAX = 100_000_000

const trim = (v: unknown, max: number): string =>
  typeof v === 'string' ? v.trim().slice(0, max) : ''

function fee(v: unknown): number | null {
  const n = typeof v === 'number' ? v : Number(String(v ?? '').replace(/[^\d]/g, ''))
  if (!Number.isFinite(n) || n < FEE_MIN || n > FEE_MAX) return null
  return Math.round(n)
}

function status(v: unknown): BookingStatus {
  return STATUS_ORDER.includes(v as BookingStatus) ? (v as BookingStatus) : 'asking'
}

/**
 * 저장된 것을 읽어 온다.
 *
 * 손으로 고친 파일이나 옛 판에서 온 자료가 들어와도 화면이 깨지면 안 된다 —
 * 모르는 갈래와 이상한 값은 조용히 버린다.
 */
export function normalizeBookings(raw: unknown): VendorBookings {
  if (!raw || typeof raw !== 'object') return {}
  const out: VendorBookings = {}
  for (const spec of CATEGORIES) {
    const item = (raw as Record<string, unknown>)[spec.id]
    if (!item || typeof item !== 'object') continue
    const row = item as Record<string, unknown>
    const name = trim(row.name, NAME_MAX)
    const phone = trim(row.phone, PHONE_MAX)
    const memo = trim(row.memo, MEMO_MAX)
    // 이름도 연락처도 메모도 없으면 빈 자리다
    if (!name && !phone && !memo) continue
    out[spec.id] = {
      name,
      phone,
      fee: fee(row.fee),
      status: status(row.status),
      memo,
      updated_at: trim(row.updated_at, 40) || new Date().toISOString(),
    }
  }
  return out
}

export function normalizeBook(raw: unknown): VendorMemo[] {
  if (!Array.isArray(raw)) return []
  const out: VendorMemo[] = []
  for (const item of raw) {
    if (!item || typeof item !== 'object') continue
    const row = item as Record<string, unknown>
    const spec = categorySpec(trim(row.category, 20))
    const name = trim(row.name, NAME_MAX)
    if (!spec || !name) continue
    const count = Number(row.used_count)
    out.push({
      category: spec.id,
      name,
      phone: trim(row.phone, PHONE_MAX),
      fee: fee(row.fee),
      memo: trim(row.memo, MEMO_MAX),
      used_count: Number.isFinite(count) && count > 0 ? Math.min(Math.round(count), 999) : 1,
      last_used_at: trim(row.last_used_at, 40) || new Date().toISOString(),
    })
  }
  return out
}

/** 같은 곳인지 — 띄어쓰기와 대소문자는 무시한다 */
const key = (category: VendorCategory, name: string) =>
  `${category}|${name.replace(/\s+/g, '').toLowerCase()}`

/**
 * 수첩에 적어 둔다(이미 있으면 갱신).
 *
 * 「내년엔 이름만 바꿔 다시」가 이 제품의 약속이다. 업체도 같아야 한다 —
 * 한 번 적으신 곳은 다음 연주회에서 단추 하나로 돌아온다.
 */
export function rememberVendor(
  book: VendorMemo[],
  category: VendorCategory,
  booking: VendorBooking,
  now = new Date().toISOString(),
): VendorMemo[] {
  if (!booking.name.trim()) return book
  const k = key(category, booking.name)
  const rest = book.filter((m) => key(m.category, m.name) !== k)
  const found = book.find((m) => key(m.category, m.name) === k)
  const merged: VendorMemo = {
    category,
    name: booking.name.trim(),
    // 새로 적으신 것이 비어 있으면 예전 것을 지키지 않고 비운다 —
    // 「지웠는데 다시 살아난다」가 더 나쁜 놀람이다
    phone: booking.phone,
    fee: booking.fee,
    memo: booking.memo,
    used_count: (found?.used_count ?? 0) + 1,
    last_used_at: now,
  }
  const sameCategory = [merged, ...rest.filter((m) => m.category === category)]
    .sort((a, b) => b.used_count - a.used_count || b.last_used_at.localeCompare(a.last_used_at))
    .slice(0, BOOK_PER_CATEGORY)
  return [...sameCategory, ...rest.filter((m) => m.category !== category)]
}

/** 이 갈래에서 지난번에 쓰신 곳들 — 많이 쓴 것부터 */
export function pastVendors(book: VendorMemo[], category: VendorCategory): VendorMemo[] {
  return book
    .filter((m) => m.category === category)
    .sort((a, b) => b.used_count - a.used_count || b.last_used_at.localeCompare(a.last_used_at))
}

/**
 * 행사 장소에서 지역을 짐작한다.
 *
 * 「일산동구 구민회관 소공연장」 → 「일산동구」.
 * 못 찾으면 빈 값을 준다 — 엉뚱한 지역으로 검색해 드리는 것보다 여쭤보는 편이 낫다.
 */
export function guessRegion(venue: string | null | undefined): string {
  const text = (venue ?? '').trim()
  if (!text) return ''
  const hit = text.match(/[가-힣]{2,10}(?:특별시|광역시|[시군구읍면동])(?![가-힣])/)
  return hit ? hit[0] : ''
}

export interface SearchLink {
  label: string
  url: string
}

/**
 * 찾으러 보내는 곳.
 *
 * ⚠️ **주소 모양이 바뀌면 이 표 한 곳만 고치면 됩니다.**
 * 지도·검색 서비스는 가끔 주소 모양을 바꾼다. 화면 여기저기에 흩어 두면 그때
 * 몇 군데를 고쳐야 할지 알 수 없게 되므로 한 곳에 모아 둔다.
 */
const PLACES = {
  naverMap: (q: string) => `https://map.naver.com/p/search/${encodeURIComponent(q)}`,
  kakaoMap: (q: string) => `https://map.kakao.com/?q=${encodeURIComponent(q)}`,
  naver: (q: string) => `https://search.naver.com/search.naver?query=${encodeURIComponent(q)}`,
  /*
   * 숨고는 **첫 화면으로만** 보낸다.
   *
   * 검색 주소를 `/search?q=…` 로 짐작해 봤더니 도메인은 열리는데 화면이 하얗게
   * 비었다(직접 눌러 확인). 눌러도 아무것도 안 나오는 단추는 안 만드느니만 못하다.
   * 안쪽 주소는 사이트 사정으로 바뀌므로, 확실한 첫 화면으로 보내고 **검색어는
   * 화면에 글로 적어** 드린다. 맞는 검색 주소를 알게 되면 이 한 줄만 고치면 된다.
   */
  soomgo: () => 'https://soomgo.com/',
} as const

/**
 * 지도에서 찾는 길 — **자리(가게)** 가 있는 갈래.
 *
 * 업체 정보를 우리가 모으지 않는다 — 목록은 썩고, 썩은 목록은 없느니만 못하다.
 * 늘 최신인 지도 서비스로 **검색어만 만들어** 보내 드린다.
 * 나가는 것은 「지역 + 갈래」 뿐이라 학원 자료가 밖으로 나가지 않는다.
 */
export function searchLinks(category: VendorCategory, region: string): SearchLink[] {
  const spec = categorySpec(category)
  if (!spec) return []
  const q = `${region.trim()} ${spec.query}`.trim()
  /*
   * 네이버 검색을 **맨 앞**에 둔다.
   *
   * 주소 모양이 가장 안 바뀌는 길이고, 검색 결과 안에 「플레이스」가 함께 떠서
   * 상호·전화·주소가 한 화면에 나온다. 지도는 그다음이다 — 지도 서비스는 주소
   * 모양을 가끔 바꾸므로, 가장 튼튼한 길을 첫 단추로 둔다.
   */
  return [
    { label: '네이버 검색', url: PLACES.naver(q) },
    { label: '네이버 지도', url: PLACES.naverMap(q) },
    { label: '카카오맵', url: PLACES.kakaoMap(q) },
  ]
}

/**
 * 사람을 구하는 길 — **가게가 아니라 사람**인 갈래.
 *
 * 반주자·사회자는 개인이라 지도에 안 나온다. 대신 재능마켓에는 있다.
 * 공급이 없는 갈래(연주홀 대관·아동 드레스)에는 이 길을 만들지 않는다 —
 * 눌렀는데 아무것도 없으면 안 만드느니만 못하다.
 */
export function marketLinks(category: VendorCategory): SearchLink[] {
  const spec = categorySpec(category)
  if (!spec || !spec.market) return []
  return [{ label: '숨고 열기', url: PLACES.soomgo() }]
}

/** 재능마켓에서 치실 검색어 — 주소에 못 넣으므로 화면에 글로 알려 드린다 */
export function marketTerm(category: VendorCategory): string {
  return categorySpec(category)?.marketQuery ?? ''
}

/**
 * 지도에 안 나오는 갈래에 드리는 **한 가지 길**.
 *
 * 「가장 튼튼한 것 하나만」이다. 여러 개를 늘어놓으면 어느 것을 눌러야 할지
 * 또 고르셔야 한다.
 */
export function fallbackLink(category: VendorCategory, region: string): SearchLink | null {
  return searchLinks(category, region)[0] ?? null
}

/** 태블릿·휴대폰에서 눌러 바로 걸 수 있게. 숫자가 없으면 링크를 만들지 않는다 */
export function telHref(phone: string): string | null {
  const digits = phone.replace(/[^\d+]/g, '')
  return digits.length >= 7 ? `tel:${digits}` : null
}

export function smsHref(phone: string): string | null {
  const digits = phone.replace(/[^\d+]/g, '')
  return digits.length >= 7 ? `sms:${digits}` : null
}

export interface VendorSummary {
  /** 정해진 갈래 수 */
  filled: number
  total: number
  /** 아직 안 정한 갈래 */
  missing: CategorySpec[]
  /** 적어 두신 금액의 합 */
  totalFee: number
  /** 아직 「알아보는 중」에 머문 갈래 */
  pending: CategorySpec[]
}

export function summarize(bookings: VendorBookings): VendorSummary {
  const missing: CategorySpec[] = []
  const pending: CategorySpec[] = []
  let filled = 0
  let totalFee = 0
  for (const spec of CATEGORIES) {
    const row = bookings[spec.id]
    if (!row || !row.name) {
      missing.push(spec)
      continue
    }
    filled += 1
    totalFee += row.fee ?? 0
    if (row.status === 'asking') pending.push(spec)
  }
  return { filled, total: CATEGORIES.length, missing, totalFee, pending }
}
