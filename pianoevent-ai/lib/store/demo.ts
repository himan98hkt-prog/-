import { randomUUID } from 'node:crypto'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { isoAtLocalTime } from '@/lib/format'
import { estimateDurationSec } from '@/lib/program/order'
import type { NewEvent, NewRsvp, NewStudent, ProgramAssignment, Repository } from '@/lib/store/types'
import type { Academy, EventRecord, EventStudent, Rsvp } from '@/lib/types'

/**
 * Supabase 없이도 제품 전체를 돌려 볼 수 있는 데모 드라이버.
 * .data/store.json 에 저장하고, 쓰기가 막힌 환경(서버리스)에서는 메모리로만 동작한다.
 */

interface Db {
  academies: Academy[]
  events: EventRecord[]
  students: EventStudent[]
  rsvps: Rsvp[]
}

/** 데모용 학원 사진 (인라인 SVG 일러스트). 실제 학원은 설정에서 사진 주소를 넣는다 */
const DEMO_PHOTO =
  'data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%201200%20800%22%3E%3Cdefs%3E%3ClinearGradient%20id%3D%22wall%22%20x1%3D%220%22%20y1%3D%220%22%20x2%3D%220%22%20y2%3D%221%22%3E%3Cstop%20offset%3D%220%22%20stop-color%3D%22%23efe6d6%22%2F%3E%3Cstop%20offset%3D%221%22%20stop-color%3D%22%23dbcdb6%22%2F%3E%3C%2FlinearGradient%3E%3ClinearGradient%20id%3D%22floor%22%20x1%3D%220%22%20y1%3D%220%22%20x2%3D%220%22%20y2%3D%221%22%3E%3Cstop%20offset%3D%220%22%20stop-color%3D%22%23c9ab84%22%2F%3E%3Cstop%20offset%3D%221%22%20stop-color%3D%22%23a98963%22%2F%3E%3C%2FlinearGradient%3E%3ClinearGradient%20id%3D%22body%22%20x1%3D%220.1%22%20y1%3D%220%22%20x2%3D%220.9%22%20y2%3D%221%22%3E%3Cstop%20offset%3D%220%22%20stop-color%3D%22%233b4a63%22%2F%3E%3Cstop%20offset%3D%221%22%20stop-color%3D%22%230e1626%22%2F%3E%3C%2FlinearGradient%3E%3ClinearGradient%20id%3D%22lid%22%20x1%3D%220%22%20y1%3D%220%22%20x2%3D%221%22%20y2%3D%221%22%3E%3Cstop%20offset%3D%220%22%20stop-color%3D%22%234a5a78%22%2F%3E%3Cstop%20offset%3D%220.45%22%20stop-color%3D%22%23243349%22%2F%3E%3Cstop%20offset%3D%221%22%20stop-color%3D%22%23101b2c%22%2F%3E%3C%2FlinearGradient%3E%3ClinearGradient%20id%3D%22shaft%22%20x1%3D%220%22%20y1%3D%220%22%20x2%3D%220.4%22%20y2%3D%221%22%3E%3Cstop%20offset%3D%220%22%20stop-color%3D%22%23fff7e2%22%20stop-opacity%3D%220.85%22%2F%3E%3Cstop%20offset%3D%221%22%20stop-color%3D%22%23fff7e2%22%20stop-opacity%3D%220%22%2F%3E%3C%2FlinearGradient%3E%3CradialGradient%20id%3D%22vig%22%20cx%3D%220.5%22%20cy%3D%220.45%22%20r%3D%220.75%22%3E%3Cstop%20offset%3D%220.55%22%20stop-color%3D%22%23000%22%20stop-opacity%3D%220%22%2F%3E%3Cstop%20offset%3D%221%22%20stop-color%3D%22%232a1c0e%22%20stop-opacity%3D%220.42%22%2F%3E%3C%2FradialGradient%3E%3Cfilter%20id%3D%22blur6%22%3E%3CfeGaussianBlur%20stdDeviation%3D%226%22%2F%3E%3C%2Ffilter%3E%3Cfilter%20id%3D%22blur14%22%3E%3CfeGaussianBlur%20stdDeviation%3D%2214%22%2F%3E%3C%2Ffilter%3E%3Cfilter%20id%3D%22soft%22%3E%3CfeGaussianBlur%20stdDeviation%3D%222.2%22%2F%3E%3C%2Ffilter%3E%3C%2Fdefs%3E%3Crect%20width%3D%221200%22%20height%3D%22800%22%20fill%3D%22url%28%23wall%29%22%2F%3E%3Crect%20y%3D%22545%22%20width%3D%221200%22%20height%3D%22255%22%20fill%3D%22url%28%23floor%29%22%2F%3E%3Crect%20y%3D%22540%22%20width%3D%221200%22%20height%3D%2210%22%20fill%3D%22%238f7a5a%22%20opacity%3D%220%22%2F%3E%3Cg%20filter%3D%22url%28%23blur6%29%22%3E%3Crect%20x%3D%22812%22%20y%3D%2270%22%20width%3D%22300%22%20height%3D%22330%22%20rx%3D%228%22%20fill%3D%22%23fdf6e6%22%2F%3E%3Crect%20x%3D%22812%22%20y%3D%2270%22%20width%3D%22300%22%20height%3D%22330%22%20rx%3D%228%22%20fill%3D%22none%22%20stroke%3D%22%23c9b899%22%20stroke-width%3D%2210%22%2F%3E%3Cpath%20d%3D%22M962%2070v330M812%20235h300%22%20stroke%3D%22%23c9b899%22%20stroke-width%3D%2210%22%2F%3E%3C%2Fg%3E%3Cpath%20d%3D%22M812%2090%20L1112%2090%20L720%20620%20L300%20620%20Z%22%20fill%3D%22url%28%23shaft%29%22%20opacity%3D%220.55%22%20filter%3D%22url%28%23blur14%29%22%2F%3E%3Cellipse%20cx%3D%22520%22%20cy%3D%22600%22%20rx%3D%22330%22%20ry%3D%2242%22%20fill%3D%22%236b543a%22%20opacity%3D%220.32%22%20filter%3D%22url%28%23blur14%29%22%2F%3E%3Cpath%20d%3D%22M232%20470c0-70%2092-120%20232-120%20150%200%20262%2040%20312%2096%2031%2034%209%2072-44%2072H274c-25%200-42-19-42-48Z%22%20fill%3D%22url%28%23body%29%22%2F%3E%3Cpath%20d%3D%22M250%20466c6-52%2084-92%20206-92%20138%200%20246%2038%20292%2090-52-40-152-66-266-66-108%200-196%2026-232%2068Z%22%20fill%3D%22%2355647f%22%20opacity%3D%220.55%22%20filter%3D%22url%28%23soft%29%22%2F%3E%3Cpath%20d%3D%22M258%20396c48-46%20138-74%20232-74%20112%200%20210%2032%20268%2084-62-38-160-62-268-62-92%200-176%2020-232%2052Z%22%20fill%3D%22url%28%23lid%29%22%2F%3E%3Cpath%20d%3D%22M262%20392c46-42%20132-68%20224-68%20106%200%20200%2030%20256%2078%22%20fill%3D%22none%22%20stroke%3D%22%23dfe6f2%22%20stroke-opacity%3D%220.5%22%20stroke-width%3D%223%22%2F%3E%3Crect%20x%3D%22272%22%20y%3D%22498%22%20width%3D%22330%22%20height%3D%2240%22%20rx%3D%225%22%20fill%3D%22%23fdfbf5%22%2F%3E%3Crect%20x%3D%22272%22%20y%3D%22498%22%20width%3D%22330%22%20height%3D%228%22%20rx%3D%224%22%20fill%3D%22%23e8e2d4%22%2F%3E%3Cg%20fill%3D%22%23141c2c%22%3E%3Crect%20x%3D%22292%22%20y%3D%22498%22%20width%3D%228%22%20height%3D%2225%22%20rx%3D%221.5%22%2F%3E%3Crect%20x%3D%22321%22%20y%3D%22498%22%20width%3D%228%22%20height%3D%2225%22%20rx%3D%221.5%22%2F%3E%3Crect%20x%3D%22350%22%20y%3D%22498%22%20width%3D%228%22%20height%3D%2225%22%20rx%3D%221.5%22%2F%3E%3Crect%20x%3D%22379%22%20y%3D%22498%22%20width%3D%228%22%20height%3D%2225%22%20rx%3D%221.5%22%2F%3E%3Crect%20x%3D%22408%22%20y%3D%22498%22%20width%3D%228%22%20height%3D%2225%22%20rx%3D%221.5%22%2F%3E%3Crect%20x%3D%22437%22%20y%3D%22498%22%20width%3D%228%22%20height%3D%2225%22%20rx%3D%221.5%22%2F%3E%3Crect%20x%3D%22466%22%20y%3D%22498%22%20width%3D%228%22%20height%3D%2225%22%20rx%3D%221.5%22%2F%3E%3Crect%20x%3D%22495%22%20y%3D%22498%22%20width%3D%228%22%20height%3D%2225%22%20rx%3D%221.5%22%2F%3E%3Crect%20x%3D%22524%22%20y%3D%22498%22%20width%3D%228%22%20height%3D%2225%22%20rx%3D%221.5%22%2F%3E%3Crect%20x%3D%22553%22%20y%3D%22498%22%20width%3D%228%22%20height%3D%2225%22%20rx%3D%221.5%22%2F%3E%3Crect%20x%3D%22582%22%20y%3D%22498%22%20width%3D%228%22%20height%3D%2225%22%20rx%3D%221.5%22%2F%3E%3C%2Fg%3E%3Cg%20stroke%3D%22%23cfc7b6%22%20stroke-width%3D%221%22%3E%3Cline%20x1%3D%22282%22%20y1%3D%22506%22%20x2%3D%22282%22%20y2%3D%22538%22%2F%3E%3Cline%20x1%3D%22311%22%20y1%3D%22506%22%20x2%3D%22311%22%20y2%3D%22538%22%2F%3E%3Cline%20x1%3D%22340%22%20y1%3D%22506%22%20x2%3D%22340%22%20y2%3D%22538%22%2F%3E%3Cline%20x1%3D%22369%22%20y1%3D%22506%22%20x2%3D%22369%22%20y2%3D%22538%22%2F%3E%3Cline%20x1%3D%22398%22%20y1%3D%22506%22%20x2%3D%22398%22%20y2%3D%22538%22%2F%3E%3Cline%20x1%3D%22427%22%20y1%3D%22506%22%20x2%3D%22427%22%20y2%3D%22538%22%2F%3E%3Cline%20x1%3D%22456%22%20y1%3D%22506%22%20x2%3D%22456%22%20y2%3D%22538%22%2F%3E%3Cline%20x1%3D%22485%22%20y1%3D%22506%22%20x2%3D%22485%22%20y2%3D%22538%22%2F%3E%3Cline%20x1%3D%22514%22%20y1%3D%22506%22%20x2%3D%22514%22%20y2%3D%22538%22%2F%3E%3Cline%20x1%3D%22543%22%20y1%3D%22506%22%20x2%3D%22543%22%20y2%3D%22538%22%2F%3E%3Cline%20x1%3D%22572%22%20y1%3D%22506%22%20x2%3D%22572%22%20y2%3D%22538%22%2F%3E%3C%2Fg%3E%3Crect%20x%3D%22300%22%20y%3D%22538%22%20width%3D%2222%22%20height%3D%2266%22%20rx%3D%224%22%20fill%3D%22%23131c2b%22%2F%3E%3Crect%20x%3D%22574%22%20y%3D%22538%22%20width%3D%2222%22%20height%3D%2266%22%20rx%3D%224%22%20fill%3D%22%23131c2b%22%2F%3E%3Crect%20x%3D%22700%22%20y%3D%22518%22%20width%3D%2222%22%20height%3D%2286%22%20rx%3D%224%22%20fill%3D%22%23131c2b%22%2F%3E%3Crect%20x%3D%22352%22%20y%3D%22586%22%20width%3D%22190%22%20height%3D%2218%22%20rx%3D%227%22%20fill%3D%22%237a5a3a%22%2F%3E%3Crect%20x%3D%22352%22%20y%3D%22586%22%20width%3D%22190%22%20height%3D%227%22%20rx%3D%223.5%22%20fill%3D%22%239c774f%22%2F%3E%3Crect%20x%3D%22372%22%20y%3D%22604%22%20width%3D%2212%22%20height%3D%2246%22%20rx%3D%224%22%20fill%3D%22%236b4d31%22%2F%3E%3Crect%20x%3D%22510%22%20y%3D%22604%22%20width%3D%2212%22%20height%3D%2246%22%20rx%3D%224%22%20fill%3D%22%236b4d31%22%2F%3E%3Cpath%20d%3D%22M470%20470h96l-6%2032h-96l6-32Z%22%20fill%3D%22%23fbf6ea%22%2F%3E%3Cpath%20d%3D%22M470%20470h96%22%20stroke%3D%22%23d8cdb6%22%20stroke-width%3D%222%22%2F%3E%3Cg%20filter%3D%22url%28%23blur6%29%22%20opacity%3D%220.95%22%3E%3Cpath%20d%3D%22M60%20640h120l-16%20130H76L60%20640Z%22%20fill%3D%22%239b7c4e%22%2F%3E%3Cpath%20d%3D%22M120%20640c-10-72%2022-116%2074-136-20%2062-34%20100-74%20136Zm0%200c10-64-20-102-64-122%2014%2054%2030%2088%2064%20122Z%22%20fill%3D%22%233f6b4a%22%2F%3E%3C%2Fg%3E%3Cg%20fill%3D%22%23fff3d6%22%3E%3Ccircle%20cx%3D%221010%22%20cy%3D%22180%22%20r%3D%2226%22%20opacity%3D%220.35%22%20filter%3D%22url%28%23blur6%29%22%2F%3E%3Ccircle%20cx%3D%221090%22%20cy%3D%22300%22%20r%3D%2216%22%20opacity%3D%220.28%22%20filter%3D%22url%28%23blur6%29%22%2F%3E%3Ccircle%20cx%3D%22930%22%20cy%3D%22330%22%20r%3D%2211%22%20opacity%3D%220.22%22%20filter%3D%22url%28%23blur6%29%22%2F%3E%3C%2Fg%3E%3Crect%20width%3D%221200%22%20height%3D%22800%22%20fill%3D%22url%28%23vig%29%22%2F%3E%3C%2Fsvg%3E'

const FILE = join(process.cwd(), '.data', 'store.json')
const globalRef = globalThis as unknown as { __pianoeventDemoDb?: Db }

const nowIso = () => new Date().toISOString()

function seed(): Db {
  const academyId = 'demo-academy'
  const eventId = 'demo-event'
  const created = nowIso()
  const eventAt = isoAtLocalTime(21, 15)

  const roster: [string, string, string, number, EventStudent['level'], string | null][] = [
    ['김서연', '엘리제를 위하여', '베토벤', 210, 'intermediate', '올해로 세 번째 무대에 서는 학생입니다'],
    ['박지호', '즐거운 나의 집', '비숍', 70, 'beginner', '피아노를 시작한 지 다섯 달 되었습니다'],
    ['이하윤', '소녀의 기도', '바다르체프스카', 260, 'intermediate', '가장 좋아하는 곡을 직접 골랐습니다'],
    ['최은우', '작은 별 변주곡', '모차르트', 150, 'beginner', '변주가 나올 때마다 표정이 달라집니다'],
    ['정예린', '아라베스크', '부르크뮐러', 105, 'beginner', null],
    ['한도윤', '미뉴에트 G장조', '바흐', 130, 'beginner', '왼손 반주를 특히 열심히 연습했습니다'],
    ['오수아', '인벤션 1번', '바흐', 165, 'intermediate', null],
    ['강민준', '터키 행진곡', '모차르트', 205, 'intermediate', '빠른 패시지를 매일 느리게 연습했습니다'],
    ['윤채원', '녹턴 op.9 no.2', '쇼팽', 285, 'advanced', '올해 콩쿠르 준비를 함께 해 온 학생입니다'],
    ['배시우', '즉흥환상곡', '쇼팽', 320, 'advanced', '가장 긴 시간을 준비한 무대입니다'],
    ['임가온', '젓가락 행진곡 (연탄)', '전래', 120, 'ensemble', '동생과 함께 연주합니다'],
    ['임하람', '젓가락 행진곡 (연탄)', '전래', 120, 'ensemble', '누나와 함께 연주합니다'],
  ]

  return {
    academies: [
      {
        id: academyId,
        name: '하모니 피아노학원',
        director_name: '김보람',
        // 데모용 로고 (인라인 SVG). 실제 학원은 설정에서 이미지 주소를 넣는다
        logo_url:
          'data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2064%2064%22%3E%3Ccircle%20cx%3D%2232%22%20cy%3D%2232%22%20r%3D%2231%22%20fill%3D%22%231f2a44%22%2F%3E%3Cg%20fill%3D%22%23f5efe0%22%3E%3Crect%20x%3D%2217%22%20y%3D%2219%22%20width%3D%226.4%22%20height%3D%2226%22%20rx%3D%221.2%22%2F%3E%3Crect%20x%3D%2225%22%20y%3D%2219%22%20width%3D%226.4%22%20height%3D%2226%22%20rx%3D%221.2%22%2F%3E%3Crect%20x%3D%2233%22%20y%3D%2219%22%20width%3D%226.4%22%20height%3D%2226%22%20rx%3D%221.2%22%2F%3E%3Crect%20x%3D%2241%22%20y%3D%2219%22%20width%3D%226%22%20height%3D%2226%22%20rx%3D%221.2%22%2F%3E%3C%2Fg%3E%3Cg%20fill%3D%22%23b3892f%22%3E%3Crect%20x%3D%2221.4%22%20y%3D%2219%22%20width%3D%224%22%20height%3D%2215%22%20rx%3D%221%22%2F%3E%3Crect%20x%3D%2229.4%22%20y%3D%2219%22%20width%3D%224%22%20height%3D%2215%22%20rx%3D%221%22%2F%3E%3Crect%20x%3D%2237.4%22%20y%3D%2219%22%20width%3D%224%22%20height%3D%2215%22%20rx%3D%221%22%2F%3E%3C%2Fg%3E%3C%2Fsvg%3E',
        theme_color: '#1f2a44',
        design_theme: 'classic-navy',
        photo_url: DEMO_PHOTO,
        assets: [],
        created_at: created,
      },
    ],
    events: [
      {
        id: eventId,
        academy_id: academyId,
        title: '제12회 정기 연주회',
        type: 'recital',
        event_at: eventAt,
        venue: '구민회관 소공연장',
        status: 'draft',
        theme: null,
        greeting:
          '한 해 동안 아이들이 쌓아 온 시간을 부모님께 들려드리는 자리입니다. 서툰 소리에도 따뜻한 박수 부탁드립니다.',
        mc_opening: null,
        mc_closing: null,
        program_source: null,
        program_generated_at: null,
        design_theme: null,
        design_template: null,
        design_copy: null,
        photo_url: null,
        image_map: null,
        created_at: created,
      },
    ],
    students: roster.map(([name, piece, composer, duration, level, note]) => ({
      id: randomUUID(),
      event_id: eventId,
      student_name: name,
      piece_title: piece,
      composer,
      duration_sec: duration,
      level,
      order_no: null,
      mc_script: null,
      photo_asset_id: null,
      note,
      created_at: created,
    })),
    rsvps: [],
  }
}

function load(): Db {
  if (globalRef.__pianoeventDemoDb) return globalRef.__pianoeventDemoDb
  let db: Db
  try {
    db = JSON.parse(readFileSync(FILE, 'utf8')) as Db
    if (!Array.isArray(db.academies)) throw new Error('malformed')
  } catch {
    db = seed()
  }
  globalRef.__pianoeventDemoDb = db
  return db
}

function persist(db: Db) {
  globalRef.__pianoeventDemoDb = db
  try {
    mkdirSync(dirname(FILE), { recursive: true })
    writeFileSync(FILE, JSON.stringify(db, null, 2), 'utf8')
  } catch {
    // 읽기 전용 파일시스템(서버리스)에서는 메모리 상태만 유지한다
  }
}

const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v)) as T

export class DemoRepository implements Repository {
  readonly driver = 'demo' as const

  async getAcademy(id: string) {
    return clone(load().academies.find((a) => a.id === id) ?? null)
  }

  async ensureAcademy(id?: string) {
    const db = load()
    // 데모는 단일 학원으로 동작한다. 쿠키의 id 가 달라도 기존 데모 데이터를 잃지 않도록 첫 학원을 돌려준다.
    const found = (id ? db.academies.find((a) => a.id === id) : undefined) ?? db.academies[0]
    if (found) return clone(found)

    const academy: Academy = {
      id: id ?? randomUUID(),
      name: '내 피아노학원',
      director_name: '원장',
      logo_url: null,
      theme_color: '#1f2a44',
      design_theme: null,
      photo_url: null,
      assets: [],
      created_at: nowIso(),
    }
    db.academies.push(academy)
    persist(db)
    return clone(academy)
  }

  async updateAcademy(id: string, patch: Partial<Omit<Academy, 'id' | 'created_at'>>) {
    const db = load()
    const found = db.academies.find((a) => a.id === id)
    if (!found) throw new Error('학원을 찾을 수 없습니다.')
    Object.assign(found, patch)
    persist(db)
    return clone(found)
  }

  async deleteAcademy(id: string) {
    const db = load()
    const eventIds = db.events.filter((e) => e.academy_id === id).map((e) => e.id)
    db.students = db.students.filter((s) => !eventIds.includes(s.event_id))
    db.rsvps = db.rsvps.filter((r) => !eventIds.includes(r.event_id))
    db.events = db.events.filter((e) => e.academy_id !== id)
    db.academies = db.academies.filter((a) => a.id !== id)
    persist(db)
  }

  async listEvents(academyId: string) {
    return clone(
      load()
        .events.filter((e) => e.academy_id === academyId)
        .sort((a, b) => b.event_at.localeCompare(a.event_at)),
    )
  }

  async getEvent(id: string) {
    return clone(load().events.find((e) => e.id === id) ?? null)
  }

  async createEvent(academyId: string, input: NewEvent) {
    const db = load()
    const event: EventRecord = {
      id: randomUUID(),
      academy_id: academyId,
      title: input.title,
      type: input.type,
      event_at: input.event_at,
      venue: input.venue,
      status: 'draft',
      theme: input.theme ?? null,
      greeting: input.greeting ?? null,
      mc_opening: null,
      mc_closing: null,
      program_source: null,
      program_generated_at: null,
      design_theme: null,
      design_template: null,
      design_copy: null,
      photo_url: null,
      image_map: null,
      created_at: nowIso(),
    }
    db.events.push(event)
    persist(db)
    return clone(event)
  }

  async updateEvent(id: string, patch: Partial<Omit<EventRecord, 'id' | 'academy_id' | 'created_at'>>) {
    const db = load()
    const found = db.events.find((e) => e.id === id)
    if (!found) throw new Error('행사를 찾을 수 없습니다.')
    Object.assign(found, patch)
    persist(db)
    return clone(found)
  }

  async deleteEvent(id: string) {
    const db = load()
    db.students = db.students.filter((s) => s.event_id !== id)
    db.rsvps = db.rsvps.filter((r) => r.event_id !== id)
    db.events = db.events.filter((e) => e.id !== id)
    persist(db)
  }

  async listStudents(eventId: string) {
    return clone(
      load()
        .students.filter((s) => s.event_id === eventId)
        .sort((a, b) => {
          if (a.order_no !== null && b.order_no !== null) return a.order_no - b.order_no
          if (a.order_no !== null) return -1
          if (b.order_no !== null) return 1
          return a.created_at.localeCompare(b.created_at)
        }),
    )
  }

  async getStudent(id: string) {
    const found = load().students.find((s) => s.id === id)
    return found ? clone(found) : null
  }

  async addStudents(eventId: string, rows: NewStudent[]) {
    const db = load()
    const created = rows.map((row) => toStudent(eventId, row))
    db.students.push(...created)
    persist(db)
    return clone(created)
  }

  async replaceStudents(eventId: string, rows: NewStudent[]) {
    const db = load()
    db.students = db.students.filter((s) => s.event_id !== eventId)
    const created = rows.map((row) => toStudent(eventId, row))
    db.students.push(...created)
    persist(db)
    return clone(created)
  }

  async updateStudent(id: string, patch: Partial<NewStudent>) {
    const db = load()
    const found = db.students.find((s) => s.id === id)
    if (!found) throw new Error('학생을 찾을 수 없습니다.')
    Object.assign(found, patch)
    if (patch.duration_sec !== undefined) {
      found.duration_sec = estimateDurationSec(found.level, patch.duration_sec)
    }
    persist(db)
    return clone(found)
  }

  async deleteStudent(id: string) {
    const db = load()
    db.students = db.students.filter((s) => s.id !== id)
    persist(db)
  }

  async saveProgram(eventId: string, assignments: ProgramAssignment[]) {
    const db = load()
    const byId = new Map(assignments.map((a) => [a.id, a]))
    for (const student of db.students) {
      if (student.event_id !== eventId) continue
      const assignment = byId.get(student.id)
      if (!assignment) continue
      student.order_no = assignment.order_no
      student.mc_script = assignment.mc_script
    }
    persist(db)
  }

  async listRsvps(eventId: string) {
    return clone(
      load()
        .rsvps.filter((r) => r.event_id === eventId)
        .sort((a, b) => b.created_at.localeCompare(a.created_at)),
    )
  }

  async createRsvp(eventId: string, input: NewRsvp) {
    const db = load()
    const rsvp: Rsvp = {
      id: randomUUID(),
      event_id: eventId,
      parent_name: input.parent_name,
      student_name: input.student_name,
      headcount: input.headcount,
      message: input.message,
      attending: input.attending,
      created_at: nowIso(),
    }
    db.rsvps.push(rsvp)
    persist(db)
    return clone(rsvp)
  }

  async deleteRsvp(id: string) {
    const db = load()
    db.rsvps = db.rsvps.filter((r) => r.id !== id)
    persist(db)
  }
}

function toStudent(eventId: string, row: NewStudent): EventStudent {
  return {
    id: randomUUID(),
    event_id: eventId,
    student_name: row.student_name,
    piece_title: row.piece_title,
    composer: row.composer,
    duration_sec: estimateDurationSec(row.level, row.duration_sec),
    level: row.level,
    order_no: null,
    mc_script: null,
    note: row.note ?? null,
    photo_asset_id: row.photo_asset_id ?? null,
    created_at: nowIso(),
  }
}
