// 형제 자동 묶기 — 학부모 전화번호 매칭.
// 번호 표기가 제각각(010-1234-5678 / 01012345678 / +82 10-1234-5678)이라 정규화가 핵심이다.

export function normalizePhone(raw) {
  let d = String(raw || '').replace(/[^0-9]/g, '')
  if (!d) return ''
  if (d.startsWith('82')) d = '0' + d.slice(2) // +82 10... -> 010...
  return d
}

export function samePhone(a, b) {
  const na = normalizePhone(a)
  return !!na && na === normalizePhone(b)
}

/**
 * 학부모 번호가 같은 원생을 한 그룹으로 묶는다.
 * 학부모 번호가 없으면 본인 번호로 보조 매칭한다(공부방에서 흔한 케이스).
 * 반환: Map<groupKey, student[]> — 2명 이상인 그룹만 담긴다.
 */
export function groupSiblings(students = []) {
  const buckets = new Map()
  for (const s of students) {
    const key = normalizePhone(s.parent_phone) || normalizePhone(s.phone)
    if (!key) continue
    if (!buckets.has(key)) buckets.set(key, [])
    buckets.get(key).push(s)
  }
  const groups = new Map()
  for (const [key, list] of buckets) {
    if (list.length > 1) groups.set(key, list.slice().sort((a, b) => String(a.name).localeCompare(String(b.name), 'ko')))
  }
  return groups
}

/** 원생 목록에 siblings_group 값을 채워 돌려준다 (변경된 원생만 반환) */
export function assignSiblingGroups(students = []) {
  const groups = groupSiblings(students)
  const changed = []
  const byId = new Map(students.map((s) => [s.id, s]))
  const assigned = new Set()
  for (const [key, list] of groups) {
    for (const s of list) {
      assigned.add(s.id)
      if (s.siblings_group !== key) changed.push({ ...byId.get(s.id), siblings_group: key })
    }
  }
  for (const s of students) {
    if (!assigned.has(s.id) && s.siblings_group) changed.push({ ...s, siblings_group: null })
  }
  return changed
}
