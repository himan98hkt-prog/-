import { estimateDurationSec } from '@/lib/program/order'
import { getServerSupabase } from '@/lib/supabase/server'
import type { NewEvent, NewRsvp, NewStudent, ProgramAssignment, Repository } from '@/lib/store/types'
import type { Academy, EventRecord, EventStudent, Rsvp } from '@/lib/types'

/** Supabase(PostgreSQL) 드라이버. 스키마는 supabase/schema.sql 과 1:1 로 맞춘다. */
export class SupabaseRepository implements Repository {
  readonly driver = 'supabase' as const

  private get db() {
    return getServerSupabase()
  }

  private static unwrap<T>(result: { data: T | null; error: { message: string } | null }, what: string): T {
    if (result.error) throw new Error(`${what} 실패: ${result.error.message}`)
    if (result.data === null) throw new Error(`${what} 실패: 결과가 비어 있습니다.`)
    return result.data
  }

  async getAcademy(id: string) {
    const { data, error } = await this.db.from('academies').select('*').eq('id', id).maybeSingle()
    if (error) throw new Error(`학원 조회 실패: ${error.message}`)
    return (data as Academy) ?? null
  }

  async ensureAcademy(id?: string) {
    if (id) {
      const found = await this.getAcademy(id)
      if (found) return found
    }
    const { data, error } = await this.db
      .from('academies')
      .insert({
        ...(id ? { id } : {}),
        name: '내 피아노학원',
        director_name: '원장',
        theme_color: '#1f2a44',
      })
      .select()
      .single()
    if (error) throw new Error(`학원 생성 실패: ${error.message}`)
    return data as Academy
  }

  async updateAcademy(id: string, patch: Partial<Omit<Academy, 'id' | 'created_at'>>) {
    const result = await this.db.from('academies').update(patch).eq('id', id).select().single()
    return SupabaseRepository.unwrap(result, '학원 수정') as Academy
  }

  async deleteAcademy(id: string) {
    // events → event_students / rsvps 는 스키마의 ON DELETE CASCADE 로 함께 지워진다
    const { error } = await this.db.from('academies').delete().eq('id', id)
    if (error) throw new Error(`계정 삭제 실패: ${error.message}`)
  }

  async listEvents(academyId: string) {
    const result = await this.db
      .from('events')
      .select('*')
      .eq('academy_id', academyId)
      .order('event_at', { ascending: false })
    return SupabaseRepository.unwrap(result, '행사 목록 조회') as EventRecord[]
  }

  async getEvent(id: string) {
    const { data, error } = await this.db.from('events').select('*').eq('id', id).maybeSingle()
    if (error) throw new Error(`행사 조회 실패: ${error.message}`)
    return (data as EventRecord) ?? null
  }

  async createEvent(academyId: string, input: NewEvent) {
    const result = await this.db
      .from('events')
      .insert({
        academy_id: academyId,
        title: input.title,
        type: input.type,
        event_at: input.event_at,
        venue: input.venue,
        theme: input.theme ?? null,
        greeting: input.greeting ?? null,
        status: 'draft',
      })
      .select()
      .single()
    return SupabaseRepository.unwrap(result, '행사 생성') as EventRecord
  }

  async updateEvent(id: string, patch: Partial<Omit<EventRecord, 'id' | 'academy_id' | 'created_at'>>) {
    const result = await this.db.from('events').update(patch).eq('id', id).select().single()
    return SupabaseRepository.unwrap(result, '행사 수정') as EventRecord
  }

  async deleteEvent(id: string) {
    const { error } = await this.db.from('events').delete().eq('id', id)
    if (error) throw new Error(`행사 삭제 실패: ${error.message}`)
  }

  async listStudents(eventId: string) {
    const result = await this.db
      .from('event_students')
      .select('*')
      .eq('event_id', eventId)
      .order('order_no', { ascending: true, nullsFirst: false })
      .order('created_at', { ascending: true })
    return SupabaseRepository.unwrap(result, '학생 목록 조회') as EventStudent[]
  }

  async addStudents(eventId: string, rows: NewStudent[]) {
    if (rows.length === 0) return []
    const result = await this.db.from('event_students').insert(rows.map((r) => toRow(eventId, r))).select()
    return SupabaseRepository.unwrap(result, '학생 추가') as EventStudent[]
  }

  async replaceStudents(eventId: string, rows: NewStudent[]) {
    const { error } = await this.db.from('event_students').delete().eq('event_id', eventId)
    if (error) throw new Error(`기존 명단 삭제 실패: ${error.message}`)
    return this.addStudents(eventId, rows)
  }

  async updateStudent(id: string, patch: Partial<NewStudent>) {
    const payload: Record<string, unknown> = { ...patch }
    if (patch.duration_sec !== undefined && patch.level) {
      payload.duration_sec = estimateDurationSec(patch.level, patch.duration_sec)
    }
    const result = await this.db.from('event_students').update(payload).eq('id', id).select().single()
    return SupabaseRepository.unwrap(result, '학생 수정') as EventStudent
  }

  async deleteStudent(id: string) {
    const { error } = await this.db.from('event_students').delete().eq('id', id)
    if (error) throw new Error(`학생 삭제 실패: ${error.message}`)
  }

  async saveProgram(eventId: string, assignments: ProgramAssignment[]) {
    // 행마다 순서·멘트가 다르므로 개별 update 를 병렬로 보낸다 (연주회 규모는 최대 수십 명)
    const results = await Promise.all(
      assignments.map((a) =>
        this.db
          .from('event_students')
          .update({ order_no: a.order_no, mc_script: a.mc_script })
          .eq('id', a.id)
          .eq('event_id', eventId),
      ),
    )
    const failed = results.find((r) => r.error)
    if (failed?.error) throw new Error(`순서표 저장 실패: ${failed.error.message}`)
  }

  async listRsvps(eventId: string) {
    const result = await this.db
      .from('rsvps')
      .select('*')
      .eq('event_id', eventId)
      .order('created_at', { ascending: false })
    return SupabaseRepository.unwrap(result, 'RSVP 조회') as Rsvp[]
  }

  async createRsvp(eventId: string, input: NewRsvp) {
    const result = await this.db
      .from('rsvps')
      .insert({ event_id: eventId, ...input })
      .select()
      .single()
    return SupabaseRepository.unwrap(result, 'RSVP 저장') as Rsvp
  }

  async deleteRsvp(id: string) {
    const { error } = await this.db.from('rsvps').delete().eq('id', id)
    if (error) throw new Error(`RSVP 삭제 실패: ${error.message}`)
  }
}

function toRow(eventId: string, row: NewStudent) {
  return {
    event_id: eventId,
    student_name: row.student_name,
    piece_title: row.piece_title,
    composer: row.composer,
    duration_sec: estimateDurationSec(row.level, row.duration_sec),
    level: row.level,
    note: row.note ?? null,
  }
}
