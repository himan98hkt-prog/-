import { performerKey } from '@/lib/program/appearances'

/**
 * 파일 이름으로 아이와 사진을 짝짓는다.
 *
 * 30명 사진을 한 장씩 고르는 일은 명단을 다시 치는 것만큼 지겹다.
 * 파일 이름에 아이 이름만 들어 있으면 알아서 붙여 준다.
 *
 * 이제 한 아이에 **여러 장**을 붙일 수 있으므로 차례도 읽는다 —
 * `김서연-1.jpg` `김서연 2.jpg` `김서연(3).jpg` 는 그 번호대로 들어간다.
 */

export interface PhotoMatch<T> {
  student: T
  /** 이 아이에게 붙을 파일들 — 보여 줄 차례대로 */
  files: string[]
}

export interface PhotoMatchResult<T> {
  matched: PhotoMatch<T>[]
  /** 어느 아이 것인지 알 수 없던 파일 */
  skipped: string[]
}

/** 확장자를 뗀 이름 */
export function baseName(fileName: string): string {
  return fileName.replace(/\.[^.]+$/, '')
}

/**
 * 이름 뒤에 붙은 차례 번호. `김서연-2` `김서연 2` `김서연(2)` `김서연_2` 를 읽는다.
 * 번호가 없으면 null — 고른 차례를 그대로 쓴다.
 */
export function trailingNumber(base: string): number | null {
  const match = /[\s._\-(]\s*(\d{1,3})\s*\)?\s*$/.exec(base)
  return match ? Number(match[1]) : null
}

/**
 * 파일 이름 안에서 아이를 찾는다.
 *
 * 두 번 훑는다.
 *   1. 적힌 그대로 — `김서 연습.jpg` 는 **김서**의 사진이다
 *   2. 띄어쓰기를 지우고 — `김 서 연 무대.jpg` 는 김서연의 사진이다
 *
 * 한 번에 띄어쓰기를 지워 버리면 `김서 연습` 이 `김서연` 으로 붙어 엉뚱한 아이가 된다.
 * 각 훑기 안에서는 **긴 이름부터** 맞춘다 — `김서`와 `김서연`이 함께 있으면 긴 쪽이 맞다.
 */
export function findStudent<T extends { student_name: string }>(base: string, students: T[]): T | null {
  const sorted = [...students].filter((row) => row.student_name.trim()).sort(
    (a, b) => b.student_name.trim().length - a.student_name.trim().length,
  )
  for (const student of sorted) {
    if (base.includes(student.student_name.trim())) return student
  }
  const flat = base.replace(/\s+/g, '').toLowerCase()
  for (const student of sorted) {
    if (flat.includes(performerKey(student.student_name))) return student
  }
  return null
}

/**
 * 파일 목록을 아이별로 묶는다.
 *
 * 한 아이가 여러 장이면 파일 이름의 번호대로, 번호가 없으면 고른 차례대로.
 * 같은 아이가 명단에 두 줄(독주·듀엣)이면 **첫 줄**에 붙인다 —
 * 사진은 사람의 것이지 곡의 것이 아니고, 보여 줄 때는 이름끼리 나눠 쓴다.
 */
export function matchPhotoFiles<T extends { id: string; student_name: string }>(
  fileNames: string[],
  students: T[],
  limitPerStudent = Number.MAX_SAFE_INTEGER,
): PhotoMatchResult<T> {
  const firstRowByName = new Map<string, T>()
  for (const student of students) {
    const key = performerKey(student.student_name)
    if (!firstRowByName.has(key)) firstRowByName.set(key, student)
  }

  const buckets = new Map<string, { student: T; rows: { file: string; no: number | null; at: number }[] }>()
  const skipped: string[] = []

  fileNames.forEach((file, at) => {
    const base = baseName(file)
    const found = findStudent(base, students)
    if (!found) {
      skipped.push(file)
      return
    }
    const student = firstRowByName.get(performerKey(found.student_name)) ?? found
    const bucket = buckets.get(student.id) ?? { student, rows: [] }
    bucket.rows.push({ file, no: trailingNumber(base), at })
    buckets.set(student.id, bucket)
  })

  const matched: PhotoMatch<T>[] = []
  for (const bucket of buckets.values()) {
    const rows = [...bucket.rows].sort((a, b) => {
      if (a.no !== null && b.no !== null) return a.no - b.no || a.at - b.at
      if (a.no !== null) return -1
      if (b.no !== null) return 1
      return a.at - b.at
    })
    const files = rows.map((row) => row.file)
    if (files.length > limitPerStudent) {
      // 넘치는 것은 버리지 않고 알려 준다 — 조용히 사라지면 왜 안 들어갔는지 모른다
      skipped.push(...files.slice(limitPerStudent))
    }
    matched.push({ student: bucket.student, files: files.slice(0, limitPerStudent) })
  }
  return { matched, skipped }
}
