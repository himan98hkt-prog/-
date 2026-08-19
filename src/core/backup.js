// 백업/복원 — Lite(IndexedDB) 내보내기 파일이 그대로 Pro 마이그레이션 입력이 된다.

export const BACKUP_FORMAT = 'academy-note-backup'
export const BACKUP_VERSION = 1

export const BACKUP_TABLES = [
  'settings', 'users', 'subjects', 'classes', 'students',
  'enrollments', 'attendance', 'payments', 'expenses',
  'counselLogs', 'notices', 'monthlyStats'
]

export function buildBackup(tables, meta = {}) {
  return {
    format: BACKUP_FORMAT,
    version: BACKUP_VERSION,
    exported_at: new Date().toISOString(),
    app: meta.app || '학원 관리노트',
    plan: meta.plan || 'lite',
    academy: meta.academy || null,
    counts: Object.fromEntries(BACKUP_TABLES.map((t) => [t, (tables[t] || []).length])),
    data: Object.fromEntries(BACKUP_TABLES.map((t) => [t, tables[t] || []]))
  }
}

export function parseBackup(text) {
  let json
  try {
    json = typeof text === 'string' ? JSON.parse(text) : text
  } catch {
    throw new Error('백업 파일을 읽을 수 없습니다 (JSON 형식이 아닙니다)')
  }
  if (json?.format !== BACKUP_FORMAT) throw new Error('이 앱의 백업 파일이 아닙니다')
  if (Number(json.version) > BACKUP_VERSION) {
    throw new Error('더 최신 버전에서 만든 백업입니다. 앱을 업데이트한 뒤 복원해 주세요')
  }
  return migrate(json)
}

/** 과거 버전 백업을 현재 스키마로 올린다 */
function migrate(json) {
  const data = json.data || {}
  for (const t of BACKUP_TABLES) if (!Array.isArray(data[t])) data[t] = []
  // v0 -> v1: 출결 status 한글화, 원생 custom 필드 기본값
  if (Number(json.version || 0) < 1) {
    const map = { present: '출석', late: '지각', absent: '결석', makeup: '보강', early: '조퇴' }
    for (const a of data.attendance) if (map[a.status]) a.status = map[a.status]
    for (const s of data.students) if (!s.custom) s.custom = {}
  }
  return { ...json, version: BACKUP_VERSION, data }
}

/**
 * Lite 백업 -> Pro(Supabase) 업로드 페이로드.
 * 모든 레코드에 academy_id 를 채우고, Pro 에서 서버가 관리하는 컬럼은 제거한다.
 */
export function toProPayload(backup, academyId) {
  if (!academyId) throw new Error('academy_id 가 필요합니다')
  const out = {}
  for (const t of BACKUP_TABLES) {
    if (t === 'settings' || t === 'monthlyStats') continue
    out[t] = (backup.data[t] || []).map((row) => {
      const { _dirty, _deleted, ...rest } = row
      return { ...rest, academy_id: academyId }
    })
  }
  return out
}
