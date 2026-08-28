import type { Academy, EventRecord, EventStudent, Rsvp } from '@/lib/types'

export interface NewEvent {
  title: string
  type: EventRecord['type']
  event_at: string
  venue: string
  theme?: EventRecord['theme']
  greeting?: string | null
}

export interface NewStudent {
  student_name: string
  piece_title: string
  composer: string
  duration_sec: number | null
  level: EventStudent['level']
  note?: string | null
  photo_asset_id?: string | null
  /** 이 아이의 사진 여러 장 (대표 사진 포함) */
  photo_asset_ids?: string[] | null
}

export interface ProgramAssignment {
  id: string
  order_no: number
  mc_script: string | null
}

export interface NewRsvp {
  parent_name: string
  student_name: string
  headcount: number
  message: string | null
  attending: boolean
}

export interface RsvpSummary {
  responses: number
  attending: number
  declined: number
  headcount: number
  messages: { name: string; message: string; created_at: string }[]
}

/** 화면·API 는 이 인터페이스만 본다. 드라이버(데모 파일 / Supabase)는 갈아 끼운다. */
export interface Repository {
  readonly driver: 'demo' | 'supabase'

  getAcademy(id: string): Promise<Academy | null>
  ensureAcademy(id?: string): Promise<Academy>
  updateAcademy(id: string, patch: Partial<Omit<Academy, 'id' | 'created_at'>>): Promise<Academy>
  /** 계정·데이터 완전 삭제 (Google Play 계정 삭제 요건) */
  deleteAcademy(id: string): Promise<void>

  listEvents(academyId: string): Promise<EventRecord[]>
  getEvent(id: string): Promise<EventRecord | null>
  createEvent(academyId: string, input: NewEvent): Promise<EventRecord>
  updateEvent(id: string, patch: Partial<Omit<EventRecord, 'id' | 'academy_id' | 'created_at'>>): Promise<EventRecord>
  deleteEvent(id: string): Promise<void>

  listStudents(eventId: string): Promise<EventStudent[]>
  getStudent(id: string): Promise<EventStudent | null>
  addStudents(eventId: string, rows: NewStudent[]): Promise<EventStudent[]>
  replaceStudents(eventId: string, rows: NewStudent[]): Promise<EventStudent[]>
  updateStudent(id: string, patch: Partial<NewStudent>): Promise<EventStudent>
  deleteStudent(id: string): Promise<void>
  saveProgram(eventId: string, assignments: ProgramAssignment[]): Promise<void>

  listRsvps(eventId: string): Promise<Rsvp[]>
  createRsvp(eventId: string, input: NewRsvp): Promise<Rsvp>
  deleteRsvp(id: string): Promise<void>
}

export function summarizeRsvps(rsvps: Rsvp[]): RsvpSummary {
  const attending = rsvps.filter((r) => r.attending)
  return {
    responses: rsvps.length,
    attending: attending.length,
    declined: rsvps.length - attending.length,
    headcount: attending.reduce((sum, r) => sum + (Number.isFinite(r.headcount) ? r.headcount : 0), 0),
    messages: rsvps
      .filter((r) => r.message && r.message.trim())
      .map((r) => ({ name: r.parent_name, message: r.message!.trim(), created_at: r.created_at })),
  }
}
