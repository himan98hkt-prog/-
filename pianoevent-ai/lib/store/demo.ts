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
    created_at: nowIso(),
  }
}
