// 저장소 파사드 — 화면은 이 모듈만 쓴다.
// Lite/Pro 어느 쪽이든 읽기는 로컬(Dexie), 쓰기는 로컬 + (Pro면) outbox 큐.

import { db } from './db.js'
import { uid } from '../core/id.js'
import { monthRange, toYmd, toMonth } from '../core/date.js'
import { decorate, statusOf, PAY_STATUS } from '../core/fees.js'
import { assignSiblingGroups } from '../core/siblings.js'

const SYNCED_TABLES = new Set([
  'users', 'subjects', 'classes', 'students', 'enrollments',
  'attendance', 'payments', 'expenses', 'counselLogs', 'notices'
])

// ── 변경 알림 ────────────────────────────────────────────────
const listeners = new Map()
export function on(topic, fn) {
  if (!listeners.has(topic)) listeners.set(topic, new Set())
  listeners.get(topic).add(fn)
  return () => listeners.get(topic).delete(fn)
}
export function emit(topic, payload) {
  for (const fn of listeners.get(topic) || []) fn(payload)
  for (const fn of listeners.get('*') || []) fn(topic, payload)
}

// ── 메모리 캐시 (작은 테이블만) ───────────────────────────────
export const cache = {
  settings: new Map(),
  students: [],
  studentById: new Map(),
  classes: [],
  classById: new Map(),
  subjects: [],
  subjectById: new Map(),
  users: [],
  userById: new Map(),
  enrollments: [],
  ready: false
}

let plan = 'lite'
export function setPlan(p) { plan = p === 'pro' ? 'pro' : 'lite' }
export function getPlan() { return plan }

export async function init() {
  const [settings, students, classes, subjects, users, enrollments] = await Promise.all([
    db.settings.toArray(),
    db.students.toArray(),
    db.classes.toArray(),
    db.subjects.toArray(),
    db.users.toArray(),
    db.enrollments.toArray()
  ])
  cache.settings = new Map(settings.map((s) => [s.key, s.value]))
  setStudents(students)
  setSmall('classes', classes)
  setSmall('subjects', subjects)
  setSmall('users', users)
  cache.enrollments = enrollments
  plan = cache.settings.get('license')?.plan || 'lite'
  cache.ready = true
  emit('ready')
  return cache
}

function setStudents(list) {
  cache.students = list.sort((a, b) => String(a.name).localeCompare(String(b.name), 'ko'))
  cache.studentById = new Map(list.map((s) => [s.id, s]))
}
// 'classes' -> 'classById' 처럼 영어 복수형이 규칙적이지 않아 매핑을 명시한다
const INDEX_NAME = { classes: 'classById', subjects: 'subjectById', users: 'userById' }

function setSmall(name, list) {
  cache[name] = list
  cache[INDEX_NAME[name]] = new Map(list.map((x) => [x.id, x]))
}

// ── 설정 ────────────────────────────────────────────────────
export function getSetting(key, fallback = null) {
  const v = cache.settings.get(key)
  return v === undefined ? fallback : v
}
export async function setSetting(key, value) {
  cache.settings.set(key, value)
  await db.settings.put({ key, value })
  emit('settings', { key, value })
  return value
}

// ── 공통 쓰기 ────────────────────────────────────────────────
function stamp(row) {
  return { ...row, id: row.id || uid(), updated_at: new Date().toISOString() }
}

async function queue(table, op, row) {
  if (plan !== 'pro' || !SYNCED_TABLES.has(table)) return
  await db.outbox.add({ table, op, row, ts: Date.now() })
  emit('outbox')
}

export async function put(table, row, opts = {}) {
  const rec = stamp(row)
  await db[table].put(rec)
  if (!opts.fromSync) await queue(table, 'put', rec)
  refreshCacheAfterWrite(table, rec)
  await invalidateStats(table, [rec])
  emit(table, { op: 'put', row: rec })
  return rec
}

// 출결·수납·지출이 바뀌면 그 달의 집계 캐시는 더 이상 사실이 아니다 → 지운다.
// (다시 계산하는 시점은 현황 화면을 열거나 월말 마감을 누를 때)
const STATS_MONTH_OF = {
  attendance: (r) => String(r.date || '').slice(0, 7),
  payments: (r) => r.month,
  expenses: (r) => String(r.date || '').slice(0, 7)
}

async function invalidateStats(table, rows) {
  const pick = STATS_MONTH_OF[table]
  if (!pick) return
  const months = new Set()
  for (const r of rows) {
    const m = pick(r)
    if (m) months.add(m)
  }
  if (months.size) await db.monthlyStats.bulkDelete([...months])
}

export async function putMany(table, rows, opts = {}) {
  const recs = rows.map(stamp)
  await db[table].bulkPut(recs)
  if (!opts.fromSync && plan === 'pro') {
    await db.outbox.bulkAdd(recs.map((row) => ({ table, op: 'put', row, ts: Date.now() })))
    emit('outbox')
  }
  for (const r of recs) refreshCacheAfterWrite(table, r)
  await invalidateStats(table, recs)
  emit(table, { op: 'putMany', rows: recs })
  return recs
}

export async function remove(table, id, opts = {}) {
  const doomed = STATS_MONTH_OF[table] ? await db[table].get(id) : null
  await db[table].delete(id)
  if (doomed) await invalidateStats(table, [doomed])
  if (!opts.fromSync) await queue(table, 'del', { id })
  removeFromCache(table, id)
  emit(table, { op: 'del', id })
}

function refreshCacheAfterWrite(table, row) {
  if (table === 'students') {
    const idx = cache.students.findIndex((s) => s.id === row.id)
    if (idx >= 0) cache.students[idx] = row
    else cache.students.push(row)
    cache.students.sort((a, b) => String(a.name).localeCompare(String(b.name), 'ko'))
    cache.studentById.set(row.id, row)
  } else if (table === 'classes' || table === 'subjects' || table === 'users') {
    const list = cache[table]
    const idx = list.findIndex((x) => x.id === row.id)
    if (idx >= 0) list[idx] = row
    else list.push(row)
    setSmall(table, list)
  } else if (table === 'enrollments') {
    const idx = cache.enrollments.findIndex((e) => e.id === row.id)
    if (idx >= 0) cache.enrollments[idx] = row
    else cache.enrollments.push(row)
  }
}

function removeFromCache(table, id) {
  if (table === 'students') {
    cache.students = cache.students.filter((s) => s.id !== id)
    cache.studentById.delete(id)
  } else if (table === 'classes' || table === 'subjects' || table === 'users') {
    setSmall(table, cache[table].filter((x) => x.id !== id))
  } else if (table === 'enrollments') {
    cache.enrollments = cache.enrollments.filter((e) => e.id !== id)
  }
}

// ── 원생 ────────────────────────────────────────────────────
export const STUDENT_STATUS = ['재원', '휴원', '퇴원']

/** 이름/학교/반/상태 즉시 검색. 1,000명 기준 메모리 필터가 가장 빠르다(인덱스 왕복 없음). */
export function searchStudents(query = '', filters = {}) {
  const q = query.trim().toLowerCase()
  const { status, classId, subjectId } = filters
  let classStudentIds = null
  if (classId) classStudentIds = new Set(activeEnrollments({ classId }).map((e) => e.student_id))
  else if (subjectId) {
    const ids = new Set(cache.classes.filter((c) => c.subject_id === subjectId).map((c) => c.id))
    classStudentIds = new Set(cache.enrollments.filter((e) => ids.has(e.class_id) && !e.ended_at).map((e) => e.student_id))
  }
  const out = []
  for (const s of cache.students) {
    if (status && s.status !== status) continue
    if (classStudentIds && !classStudentIds.has(s.id)) continue
    if (q) {
      const hay = `${s.name || ''} ${s.school || ''} ${s.grade || ''} ${s.phone || ''} ${s.parent_phone || ''}`.toLowerCase()
      if (!hay.includes(q)) continue
    }
    out.push(s)
  }
  return out
}

export function studentClasses(studentId) {
  return activeEnrollments({ studentId })
    .map((e) => cache.classById.get(e.class_id))
    .filter(Boolean)
}

export async function saveStudent(data) {
  const row = await put('students', {
    status: '재원',
    custom: {},
    joined_at: toYmd(),
    ...data
  })
  await syncSiblingGroups()
  return row
}

/** 학부모 번호 매칭으로 형제 그룹 재계산 — 변경된 원생만 저장 */
export async function syncSiblingGroups() {
  const changed = assignSiblingGroups(cache.students)
  if (!changed.length) return []
  await putMany('students', changed)
  return changed
}

export function siblingsOf(student) {
  if (!student?.siblings_group) return []
  return cache.students.filter((s) => s.siblings_group === student.siblings_group && s.id !== student.id)
}

// ── 수강 ────────────────────────────────────────────────────
export function activeEnrollments({ classId, studentId, on: onDate } = {}) {
  const d = onDate || toYmd()
  return cache.enrollments.filter((e) => {
    if (classId && e.class_id !== classId) return false
    if (studentId && e.student_id !== studentId) return false
    if (e.started_at && e.started_at > d) return false
    if (e.ended_at && e.ended_at < d) return false
    return true
  })
}

export function rosterOf(classId, onDate) {
  return activeEnrollments({ classId, on: onDate })
    .map((e) => cache.studentById.get(e.student_id))
    .filter((s) => s && s.status !== '퇴원')
    .sort((a, b) => String(a.name).localeCompare(String(b.name), 'ko'))
}

export function enrolledCount(classId) {
  return activeEnrollments({ classId }).length
}

export async function enroll(studentId, classId, extra = {}) {
  const dup = cache.enrollments.find((e) => e.student_id === studentId && e.class_id === classId && !e.ended_at)
  if (dup) return dup
  return put('enrollments', { student_id: studentId, class_id: classId, started_at: toYmd(), ended_at: null, ...extra })
}

export async function unenroll(enrollmentId, endedAt = toYmd()) {
  const e = cache.enrollments.find((x) => x.id === enrollmentId)
  if (!e) return null
  return put('enrollments', { ...e, ended_at: endedAt })
}

// ── 출결 ────────────────────────────────────────────────────
export function attendanceOfClassDate(classId, date) {
  return db.attendance.where('[class_id+date]').equals([classId, date]).toArray()
}

export function attendanceOfClassMonth(classId, month) {
  const { from, to } = monthRange(month)
  return db.attendance.where('[class_id+date]').between([classId, from], [classId, to], true, true).toArray()
}

export function attendanceOfStudentRange(studentId, from, to) {
  return db.attendance.where('[student_id+date]').between([studentId, from], [studentId, to], true, true).toArray()
}

export function attendanceOfRange(from, to) {
  return db.attendance.where('date').between(from, to, true, true).toArray()
}

export async function markAttendance({ classId, date, studentId, status, reason_tag = null, checked_by = null }) {
  const existing = await db.attendance
    .where('[student_id+date]').equals([studentId, date])
    .filter((r) => r.class_id === classId)
    .first()
  const row = {
    ...(existing || {}),
    class_id: classId,
    date,
    student_id: studentId,
    status,
    reason_tag,
    checked_by,
    checked_at: new Date().toISOString()
  }
  return put('attendance', row)
}

export async function markAttendanceBulk(rows) {
  return putMany('attendance', rows.map((r) => ({ checked_at: new Date().toISOString(), ...r })))
}

/** 보강 예약 — 미래 날짜의 보강 레코드를 미리 만든다 */
export async function bookMakeup({ studentId, classId, date, memo = '' }) {
  return put('attendance', {
    student_id: studentId,
    class_id: classId,
    date,
    status: '보강',
    reason_tag: memo || null,
    checked_by: null,
    checked_at: null,
    booked: true
  })
}

// ── 수납 ────────────────────────────────────────────────────
export async function paymentsOfMonth(month) {
  const rows = await db.payments.where('month').equals(month).toArray()
  return rows.map(decorate)
}

export async function paymentsOfStudent(studentId, limit = 24) {
  const rows = await db.payments.where('student_id').equals(studentId).reverse().limit(limit).toArray()
  return rows.map(decorate).sort((a, b) => String(b.month).localeCompare(String(a.month)))
}

export async function savePayment(p) {
  const row = { ...p, status: statusOf(p) }
  return put('payments', row)
}

/** 월 청구서 일괄 생성 — 이미 있는 원생은 건너뛴다 */
export async function generateMonthlyBills(month, { defaultFee = 0 } = {}) {
  const existing = new Set((await db.payments.where('month').equals(month).toArray()).map((p) => p.student_id))
  const created = []
  for (const s of cache.students) {
    if (s.status !== '재원' || existing.has(s.id)) continue
    const enrolls = activeEnrollments({ studentId: s.id })
    if (!enrolls.length) continue
    const amount = enrolls.reduce((sum, e) => {
      if (e.fee_override != null && e.fee_override !== '') return sum + Number(e.fee_override || 0)
      return sum + Number(cache.classById.get(e.class_id)?.fee || defaultFee || 0)
    }, 0)
    if (!amount) continue
    created.push({
      id: uid(),
      student_id: s.id,
      month,
      amount,
      method: null,
      paid_at: null,
      status: PAY_STATUS.UNPAID,
      installments: []
    })
  }
  if (created.length) await putMany('payments', created)
  return created
}

// ── 지출 ────────────────────────────────────────────────────
export const EXPENSE_CATEGORIES = ['임대료', '인건비', '교재', '비품', '공과금', '광고', '기타']

export async function expensesOfMonth(month) {
  const { from, to } = monthRange(month)
  return db.expenses.where('date').between(from, to, true, true).toArray()
}

// ── 상담 ────────────────────────────────────────────────────
export const COUNSEL_TYPES = ['전화', '대면', '입회상담']
export const FUNNEL_STAGES = ['상담중', '체험', '등록', '보류']

export async function counselOfStudent(studentId) {
  const rows = await db.counselLogs.where('student_id').equals(studentId).toArray()
  return rows.sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)))
}

export async function counselRecent(limit = 200) {
  return db.counselLogs.orderBy('created_at').reverse().limit(limit).toArray()
}

/** 입회 상담 → 등록 전환 퍼널 */
export async function counselFunnel(month) {
  const all = await db.counselLogs.where('type').equals('입회상담').toArray()
  const rows = month ? all.filter((c) => toMonth(c.created_at) === month) : all
  const counts = Object.fromEntries(FUNNEL_STAGES.map((s) => [s, 0]))
  for (const c of rows) counts[c.stage || '상담중'] = (counts[c.stage || '상담중'] || 0) + 1
  const total = rows.length
  return { total, counts, conversion: total ? Math.round((counts['등록'] / total) * 1000) / 10 : 0 }
}

// ── 월별 집계 캐시 ───────────────────────────────────────────
// 현황 화면이 20만 건을 매번 훑지 않도록, 마감/변경 시 월 단위로 집계해 저장한다.
export async function monthlyStats(month, { refresh = false } = {}) {
  if (!refresh) {
    const hit = await db.monthlyStats.get(month)
    if (hit) return hit
  }
  return recomputeMonth(month)
}

export async function recomputeMonth(month) {
  const { from, to } = monthRange(month)
  // 출결은 20만 건 규모라 배열로 만들지 않고 인덱스 커서로 흘려보내며 센다
  const attCounts = { 출석: 0, 지각: 0, 결석: 0, 보강: 0, 조퇴: 0 }
  const attStream = db.attendance.where('date').between(from, to, true, true)
    .each((r) => { if (attCounts[r.status] !== undefined) attCounts[r.status]++ })
  const [, pays, exps] = await Promise.all([
    attStream,
    db.payments.where('month').equals(month).toArray(),
    db.expenses.where('date').between(from, to, true, true).toArray()
  ])
  const attTotal = Object.values(attCounts).reduce((a, b) => a + b, 0)
  const attSum = {
    total: attTotal,
    absent: attCounts['결석'],
    rate: attTotal ? Math.round(((attTotal - attCounts['결석']) / attTotal) * 1000) / 10 : 0
  }
  let billed = 0
  let collected = 0
  let unpaid = 0
  for (const raw of pays) {
    const p = decorate(raw)
    billed += p.amount
    collected += p.paid
    if (p.status !== PAY_STATUS.FULL) unpaid++
  }
  const expense = exps.reduce((s, e) => s + (Number(e.amount) || 0), 0)
  const active = cache.students.filter((s) => s.status === '재원').length
  const joined = cache.students.filter((s) => (s.joined_at || '').slice(0, 7) === month).length
  const left = cache.students.filter((s) => s.status === '퇴원' && (s.left_at || '').slice(0, 7) === month).length

  const row = {
    month,
    attendanceRate: attSum.rate,
    attendanceTotal: attSum.total,
    absentCount: attSum.absent,
    billed,
    collected,
    outstanding: Math.max(0, billed - collected),
    unpaidCount: unpaid,
    expense,
    net: collected - expense,
    activeStudents: active,
    joined,
    left,
    computed_at: new Date().toISOString()
  }
  await db.monthlyStats.put(row)
  emit('monthlyStats', row)
  return row
}

export async function statsRange(months) {
  return Promise.all(months.map((m) => monthlyStats(m)))
}

/** 캐시에 있는 달만 즉시 반환하고, 없는 달은 null. 현황 화면 첫 페인트에 쓴다. */
export async function cachedStats(months) {
  const rows = await db.monthlyStats.bulkGet(months)
  return months.map((m, i) => rows[i] || null)
}

export { db }
