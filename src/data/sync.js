// Pro 동기화 — Supabase(PostgreSQL + Realtime).
//
// 설계: local-first. 화면은 언제나 Dexie 를 읽고, 이 모듈이 백그라운드에서
//   1) outbox 를 서버로 밀고(push)  2) 서버 변경을 당겨(pull)  3) Realtime 으로 즉시 반영한다.
// 오프라인이면 outbox 에 쌓였다가 온라인 복귀 시 자동 전송된다.
// 충돌은 updated_at 기준 last-write-wins (출결 체크는 마지막 사람이 맞다는 현장 규칙과 일치).

import { createClient } from '@supabase/supabase-js'
import { db } from './db.js'
import * as repo from './repo.js'

const TABLES = ['users', 'subjects', 'classes', 'students', 'enrollments', 'attendance', 'payments', 'expenses', 'counselLogs', 'notices']
// Dexie 테이블명 ↔ Postgres 테이블명
const PG = {
  users: 'users', subjects: 'subjects', classes: 'classes', students: 'students',
  enrollments: 'enrollments', attendance: 'attendance', payments: 'payments',
  expenses: 'expenses', counselLogs: 'counsel_logs', notices: 'notices'
}
const DEXIE_OF = Object.fromEntries(Object.entries(PG).map(([k, v]) => [v, k]))

let client = null
let channel = null
let academyId = null
let timer = null
let pushing = false
const state = { online: false, pending: 0, lastSync: null, error: null }
let onStatus = () => {}

export function status() {
  return { ...state }
}

// 테스트용 주입구 — 실제 Supabase 없이 push/pull/충돌 규칙을 검증한다
export function __setTestHarness({ client: c, academyId: a }) {
  client = c
  academyId = a
}
export { applyRemote as __applyRemote, toPg as __toPg, fromPg as __fromPg }

export function config() {
  const s = repo.getSetting('supabase') || {}
  return {
    url: s.url || import.meta.env?.VITE_SUPABASE_URL || '',
    anonKey: s.anonKey || import.meta.env?.VITE_SUPABASE_ANON_KEY || ''
  }
}

export function getClient() {
  if (client) return client
  const { url, anonKey } = config()
  if (!url || !anonKey) throw new Error('Supabase 접속 정보가 없습니다. 설정에서 URL/anon key 를 입력하세요.')
  client = createClient(url, anonKey, {
    auth: { persistSession: true, autoRefreshToken: true },
    realtime: { params: { eventsPerSecond: 20 } }
  })
  return client
}

async function ensureAuth() {
  const sb = getClient()
  const { data } = await sb.auth.getSession()
  if (data?.session) return data.session
  const { data: anon, error } = await sb.auth.signInAnonymously()
  if (error) throw error
  return anon.session
}

/** 라이선스 키로 학원 생성 (최초 1회). 초대 코드로 강사 기기를 연결한다. */
export async function createAcademy({ name, licenseHash, brandColor }) {
  const sb = getClient()
  await ensureAuth()
  const { data, error } = await sb.rpc('create_academy', {
    p_name: name, p_license_hash: licenseHash, p_brand_color: brandColor || '#2563eb'
  })
  if (error) throw error
  await repo.setSetting('academy', data)
  academyId = data.id
  return data
}

/** 초대 코드로 기존 학원에 합류 */
export async function joinAcademy(inviteCode, { name, role = 'teacher', pin }) {
  const sb = getClient()
  await ensureAuth()
  const { data, error } = await sb.rpc('join_academy', {
    p_invite_code: String(inviteCode).toUpperCase(), p_name: name, p_role: role, p_pin: pin
  })
  if (error) throw error
  await repo.setSetting('academy', data)
  academyId = data.id
  return data
}

export async function start(opts = {}) {
  onStatus = opts.onStatus || (() => {})
  const academy = repo.getSetting('academy')
  if (!academy?.id) throw new Error('연결된 학원이 없습니다. 라이선스 활성화 또는 초대 코드 입력이 필요합니다.')
  academyId = academy.id
  await ensureAuth()

  window.addEventListener('online', () => { state.online = true; report(); syncNow() })
  window.addEventListener('offline', () => { state.online = false; report() })
  state.online = navigator.onLine

  await subscribeRealtime()
  await syncNow()
  timer = setInterval(syncNow, 30000) // Realtime 이 놓친 변경을 주기적으로 보정
  return { status }
}

export function stop() {
  clearInterval(timer)
  channel?.unsubscribe()
  channel = null
}

async function subscribeRealtime() {
  const sb = getClient()
  channel = sb.channel(`academy:${academyId}`)
  for (const pgTable of Object.values(PG)) {
    channel.on('postgres_changes',
      { event: '*', schema: 'public', table: pgTable, filter: `academy_id=eq.${academyId}` },
      (payload) => applyRemote(pgTable, payload).catch((e) => console.warn('realtime 적용 실패', e)))
  }
  await channel.subscribe()
}

async function applyRemote(pgTable, payload) {
  const table = DEXIE_OF[pgTable]
  if (!table) return
  if (payload.eventType === 'DELETE') {
    await db[table].delete(payload.old.id)
    repo.emit(table, { op: 'del', id: payload.old.id, remote: true })
    return
  }
  const row = fromPg(payload.new)
  const local = await db[table].get(row.id)
  if (local && local.updated_at && row.updated_at && local.updated_at > row.updated_at) return // 로컬이 더 최신
  await db[table].put(row)
  repo.emit(table, { op: 'put', row, remote: true })
  state.lastSync = new Date().toISOString()
  report()
}

export async function syncNow() {
  if (!academyId) return
  try {
    await push()
    await pull()
    state.error = null
  } catch (err) {
    state.error = err.message
    console.warn('동기화 오류', err)
  }
  report()
}

export async function push() {
  if (pushing) return
  pushing = true
  try {
    const sb = getClient()
    let batch = await db.outbox.orderBy('seq').limit(200).toArray()
    while (batch.length) {
      const byTable = new Map()
      for (const item of batch) {
        const key = `${item.table}:${item.op}`
        if (!byTable.has(key)) byTable.set(key, [])
        byTable.get(key).push(item)
      }
      for (const [key, items] of byTable) {
        const [table, op] = key.split(':')
        const pgTable = PG[table]
        if (!pgTable) continue
        if (op === 'put') {
          const rows = items.map((i) => toPg(table, i.row))
          const { error } = await sb.from(pgTable).upsert(rows, { onConflict: 'id' })
          if (error) throw error
        } else {
          const ids = items.map((i) => i.row.id)
          const { error } = await sb.from(pgTable).delete().in('id', ids)
          if (error) throw error
        }
      }
      await db.outbox.bulkDelete(batch.map((b) => b.seq))
      batch = await db.outbox.orderBy('seq').limit(200).toArray()
    }
  } finally {
    pushing = false
    state.pending = await db.outbox.count()
  }
}

export async function pull() {
  const sb = getClient()
  const since = repo.getSetting('syncCursor') || '1970-01-01T00:00:00.000Z'
  let newest = since
  for (const table of TABLES) {
    const pgTable = PG[table]
    let from = 0
    const PAGE = 1000
    for (;;) {
      const { data, error } = await sb.from(pgTable)
        .select('*')
        .eq('academy_id', academyId)
        .gt('updated_at', since)
        .order('updated_at', { ascending: true })
        .range(from, from + PAGE - 1)
      if (error) throw error
      if (!data?.length) break
      const rows = data.map(fromPg)
      await db[table].bulkPut(rows)
      repo.emit(table, { op: 'putMany', rows, remote: true })
      for (const r of rows) if (r.updated_at > newest) newest = r.updated_at
      if (data.length < PAGE) break
      from += PAGE
    }
  }
  if (newest !== since) {
    await repo.setSetting('syncCursor', newest)
    await repo.init() // 캐시 갱신
  }
  state.lastSync = new Date().toISOString()
  state.pending = await db.outbox.count()
}

function toPg(table, row) {
  const out = { ...row, academy_id: academyId }
  delete out.booked // 로컬 전용 플래그
  if (table === 'counselLogs' && out.stage) out.stage = String(out.stage)
  return out
}

function fromPg(row) {
  const { academy_id, ...rest } = row
  return rest
}

/** Lite 백업 파일을 Pro 로 올린다 (마이그레이션) */
export async function migrateFromBackup(backup) {
  const sb = getClient()
  const { toProPayload } = await import('../core/backup.js')
  const payload = toProPayload(backup, academyId)
  const summary = {}
  for (const [table, rows] of Object.entries(payload)) {
    const pgTable = PG[table]
    if (!pgTable || !rows.length) continue
    for (let i = 0; i < rows.length; i += 500) {
      const { error } = await sb.from(pgTable).upsert(rows.slice(i, i + 500), { onConflict: 'id' })
      if (error) throw error
    }
    summary[table] = rows.length
  }
  await repo.setSetting('syncCursor', '1970-01-01T00:00:00.000Z')
  await pull()
  return summary
}

function report() {
  onStatus(status())
}
