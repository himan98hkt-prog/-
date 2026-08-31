import { describe, expect, it } from 'vitest'
import {
  BOOK_PER_CATEGORY,
  CATEGORIES,
  guessRegion,
  marketLinks,
  normalizeBook,
  normalizeBookings,
  pastVendors,
  rememberVendor,
  searchLinks,
  smsHref,
  summarize,
  telHref,
  type VendorBooking,
  type VendorMemo,
} from '@/lib/vendors'

const booking = (over: Partial<VendorBooking> = {}): VendorBooking => ({
  name: '하모니홀',
  phone: '031-000-0000',
  fee: 300000,
  status: 'booked',
  memo: '주차 10대',
  updated_at: '2026-09-01T00:00:00.000Z',
  ...over,
})

describe('갈래', () => {
  it('여섯 자리가 서로 다른 id 를 가진다', () => {
    const ids = CATEGORIES.map((c) => c.id)
    expect(new Set(ids).size).toBe(ids.length)
    expect(ids).toHaveLength(6)
  })

  it('지도에서 안 찾아지는 갈래에는 다른 길을 적어 둔다', () => {
    // 「검색해 보세요」만 내놓고 아무것도 안 나오면 프로그램을 탓하시게 된다
    for (const spec of CATEGORIES.filter((c) => !c.findable)) {
      expect(spec.hint.length).toBeGreaterThan(10)
    }
  })
})

describe('지도 검색 주소', () => {
  it('지역과 갈래만 나간다 — 학원 자료는 나가지 않는다', () => {
    const links = searchLinks('photo', '일산동구')
    expect(links).toHaveLength(3)
    for (const link of links) {
      expect(link.url).toContain(encodeURIComponent('일산동구 행사 사진 촬영'))
      expect(link.url.startsWith('https://')).toBe(true)
    }
  })

  it('지역이 비어도 주소가 깨지지 않는다', () => {
    const [naver] = searchLinks('tuner', '   ')
    expect(naver.url).toContain(encodeURIComponent('피아노 조율'))
    expect(naver.url).not.toContain('%20%20')
  })

  it('가장 튼튼한 길이 첫 단추다', () => {
    // 지도 서비스는 주소 모양을 가끔 바꾼다. 네이버 검색은 잘 안 바뀌고
    // 결과 안에 「플레이스」가 함께 떠서 상호·전화·주소가 한 화면에 나온다
    expect(searchLinks('tuner', '일산동구')[0].label).toBe('네이버 검색')
  })

  it('주소에 채워지지 않은 자리가 남지 않는다', () => {
    // 코드의 `${…}` 가 글자 그대로 주소에 들어가면 눌러도 아무 데도 못 간다
    const all = [
      ...CATEGORIES.flatMap((c) => searchLinks(c.id, '일산동구')),
      ...CATEGORIES.flatMap((c) => marketLinks(c.id, '일산동구')),
    ]
    expect(all.length).toBeGreaterThan(0)
    for (const link of all) {
      expect(link.url).not.toContain('${')
      expect(link.url).not.toContain('undefined')
      expect(link.url).toMatch(/^https:\/\/[a-z.]+\/\S*$/)
    }
  })

  it('띄어쓰기와 특수문자를 그대로 붙이지 않는다', () => {
    const [naver] = searchLinks('hall', '중구 & 남구')
    expect(naver.url).not.toContain(' ')
    expect(naver.url).not.toContain('&')
  })
})

describe('재능마켓 길', () => {
  it('사람으로 구하는 갈래에만 길을 낸다 — 없는 곳으로 보내지 않는다', () => {
    // 연주홀 대관과 아동 드레스 대여는 숨고에 공급이 없다
    expect(marketLinks('hall', '일산동구')).toEqual([])
    expect(marketLinks('dress', '일산동구')).toEqual([])
    for (const id of ['accompanist', 'mc', 'photo', 'tuner'] as const) {
      expect(marketLinks(id, '일산동구')).toHaveLength(1)
    }
  })

  it('지도 검색어와 부르는 말이 다르다', () => {
    // 지도에서는 「피아노 반주자」, 숨고에서는 「피아노 반주」로 잡힌다
    const [market] = marketLinks('accompanist', '일산동구')
    expect(market.url).toContain(encodeURIComponent('일산동구 피아노 반주'))
    expect(market.url.startsWith('https://')).toBe(true)
  })

  it('지도에 안 나오는 갈래도 검색 길은 남겨 둔다', () => {
    // 「그래도 한번 찾아보고 싶다」는 마음을 막지 않는다
    expect(searchLinks('accompanist', '일산동구').length).toBeGreaterThan(0)
  })
})

describe('장소에서 지역 짐작', () => {
  it.each([
    ['일산동구 구민회관 소공연장', '일산동구'],
    ['서울특별시 노원문화예술회관', '서울특별시'],
    ['수원시 영통구 아트홀', '수원시'],
  ])('%s → %s', (venue, region) => {
    expect(guessRegion(venue)).toBe(region)
  })

  it('못 찾으면 비워 둔다 — 엉뚱한 지역으로 검색해 드리지 않는다', () => {
    expect(guessRegion('하모니홀')).toBe('')
    expect(guessRegion(null)).toBe('')
  })
})

describe('저장된 것 읽기', () => {
  it('모르는 갈래와 빈 자리는 버린다', () => {
    const out = normalizeBookings({
      hall: booking(),
      쓰레기: booking(),
      photo: { name: '', phone: '', memo: '' },
    })
    expect(Object.keys(out)).toEqual(['hall'])
  })

  it('금액이 범위를 벗어나면 비운다 — 잘못 친 0 이 예산을 망친다', () => {
    expect(normalizeBookings({ hall: booking({ fee: -1 }) }).hall?.fee).toBeNull()
    expect(normalizeBookings({ hall: booking({ fee: 999_999_999_999 }) }).hall?.fee).toBeNull()
    expect(normalizeBookings({ hall: booking({ fee: 300000 }) }).hall?.fee).toBe(300000)
  })

  it('이상한 상태는 「알아보는 중」으로 되돌린다', () => {
    expect(normalizeBookings({ hall: booking({ status: 'x' as never }) }).hall?.status).toBe('asking')
  })

  it('손으로 고친 파일이 들어와도 깨지지 않는다', () => {
    expect(normalizeBookings(null)).toEqual({})
    expect(normalizeBookings('망가짐')).toEqual({})
    expect(normalizeBook(null)).toEqual([])
    expect(normalizeBook([{ category: 'hall' }, { name: '이름만' }])).toEqual([])
  })
})

describe('학원 수첩', () => {
  it('같은 곳을 다시 쓰면 횟수만 늘고 줄은 하나로 남는다', () => {
    let book: VendorMemo[] = []
    book = rememberVendor(book, 'hall', booking(), '2026-01-01T00:00:00.000Z')
    book = rememberVendor(book, 'hall', booking({ fee: 320000 }), '2027-01-01T00:00:00.000Z')
    expect(book).toHaveLength(1)
    expect(book[0].used_count).toBe(2)
    expect(book[0].fee).toBe(320000)
    expect(book[0].last_used_at).toBe('2027-01-01T00:00:00.000Z')
  })

  it('띄어쓰기만 다른 이름은 같은 곳으로 본다', () => {
    let book: VendorMemo[] = []
    book = rememberVendor(book, 'hall', booking({ name: '하모니 홀' }))
    book = rememberVendor(book, 'hall', booking({ name: '하모니홀' }))
    expect(book).toHaveLength(1)
  })

  it('갈래가 다르면 같은 이름이라도 따로 쌓인다', () => {
    let book: VendorMemo[] = []
    book = rememberVendor(book, 'hall', booking({ name: '김선생' }))
    book = rememberVendor(book, 'mc', booking({ name: '김선생' }))
    expect(book).toHaveLength(2)
  })

  it('이름이 없으면 수첩에 남기지 않는다', () => {
    expect(rememberVendor([], 'hall', booking({ name: '  ' }))).toEqual([])
  })

  it(`갈래마다 ${BOOK_PER_CATEGORY}개까지만 — 목록이 길면 고르기가 오히려 어렵다`, () => {
    let book: VendorMemo[] = []
    for (let i = 0; i < BOOK_PER_CATEGORY + 4; i += 1) {
      book = rememberVendor(book, 'photo', booking({ name: `사진관${i}` }))
    }
    expect(book).toHaveLength(BOOK_PER_CATEGORY)
  })

  it('다른 갈래를 저장해도 남의 갈래가 사라지지 않는다', () => {
    let book: VendorMemo[] = []
    book = rememberVendor(book, 'hall', booking({ name: '하모니홀' }))
    book = rememberVendor(book, 'photo', booking({ name: '봄스튜디오' }))
    book = rememberVendor(book, 'tuner', booking({ name: '박조율' }))
    expect(book.map((m) => m.category).sort()).toEqual(['hall', 'photo', 'tuner'])
  })

  it('많이 쓴 곳이 먼저 나온다', () => {
    let book: VendorMemo[] = []
    book = rememberVendor(book, 'photo', booking({ name: '가스튜디오' }))
    book = rememberVendor(book, 'photo', booking({ name: '나스튜디오' }))
    book = rememberVendor(book, 'photo', booking({ name: '가스튜디오' }))
    expect(pastVendors(book, 'photo')[0].name).toBe('가스튜디오')
  })
})

describe('한눈에 보기', () => {
  it('빈 자리를 짚어 준다 — 빈칸이 곧 할 일이다', () => {
    const out = summarize({ hall: booking(), photo: booking({ name: '봄스튜디오', fee: 200000 }) })
    expect(out.filled).toBe(2)
    expect(out.total).toBe(6)
    expect(out.totalFee).toBe(500000)
    expect(out.missing.map((m) => m.id).sort()).toEqual(['accompanist', 'dress', 'mc', 'tuner'])
  })

  it('아직 알아보는 중인 것을 따로 센다', () => {
    const out = summarize({ hall: booking({ status: 'asking' }), photo: booking({ status: 'paid' }) })
    expect(out.pending.map((p) => p.id)).toEqual(['hall'])
  })

  it('금액을 안 적으신 곳은 합계에서 0으로 센다', () => {
    expect(summarize({ hall: booking({ fee: null }) }).totalFee).toBe(0)
  })
})

describe('바로 걸기', () => {
  it('숫자만 남겨 링크를 만든다', () => {
    expect(telHref('010-1234-5678')).toBe('tel:01012345678')
    expect(smsHref('031 000 0000')).toBe('sms:0310000000')
  })

  it('번호가 아니면 링크를 만들지 않는다 — 눌러도 아무 일 없는 단추가 더 나쁘다', () => {
    expect(telHref('')).toBeNull()
    expect(telHref('연락처 물어보기')).toBeNull()
    expect(smsHref('123')).toBeNull()
  })
})
