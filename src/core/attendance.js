// 출결 집계 — 리포트/현황/이탈위험이 전부 이 함수들을 공유한다.

export const ATT = {
  PRESENT: '출석',
  LATE: '지각',
  ABSENT: '결석',
  MAKEUP: '보강',
  EARLY: '조퇴'
}
export const ATT_LIST = [ATT.PRESENT, ATT.LATE, ATT.ABSENT, ATT.MAKEUP, ATT.EARLY]

// 결석 사유 태그 (설정에서 추가 가능, 기본값)
export const DEFAULT_REASON_TAGS = ['질병', '가족행사', '학교일정', '무단', '기타']

/** 결석만 미출석으로 본다. 지각·조퇴·보강은 출석으로 카운트(현장 관행). */
export function isPresent(status) {
  return status !== ATT.ABSENT
}

export function summarize(records = []) {
  const counts = { [ATT.PRESENT]: 0, [ATT.LATE]: 0, [ATT.ABSENT]: 0, [ATT.MAKEUP]: 0, [ATT.EARLY]: 0 }
  for (const r of records) {
    if (counts[r.status] === undefined) continue
    counts[r.status]++
  }
  const total = ATT_LIST.reduce((s, k) => s + counts[k], 0)
  const present = total - counts[ATT.ABSENT]
  return {
    counts,
    total,
    present,
    absent: counts[ATT.ABSENT],
    rate: total ? Math.round((present / total) * 1000) / 10 : 0,
    absentRate: total ? Math.round((counts[ATT.ABSENT] / total) * 1000) / 10 : 0
  }
}

/** key(student_id 등)별 집계 Map */
export function groupBy(records = [], keyFn) {
  const map = new Map()
  for (const r of records) {
    const k = keyFn(r)
    if (!map.has(k)) map.set(k, [])
    map.get(k).push(r)
  }
  return map
}

export function summarizeBy(records, keyFn) {
  const out = new Map()
  for (const [k, list] of groupBy(records, keyFn)) out.set(k, summarize(list))
  return out
}

/** 최근 연속 결석 횟수 (날짜 내림차순으로 훑는다) */
export function currentAbsentStreak(records = []) {
  const sorted = records.slice().sort((a, b) => String(b.date).localeCompare(String(a.date)))
  let n = 0
  for (const r of sorted) {
    if (r.status === ATT.ABSENT) n++
    else break
  }
  return n
}

/** 반 x 날짜 보드용: student_id -> record */
export function indexByStudent(records = []) {
  const m = new Map()
  for (const r of records) m.set(r.student_id, r)
  return m
}
