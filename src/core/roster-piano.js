// 피아노 반주(MR) 연동 — 학생 명단만 내보낸다. (지시서 9장 5단계 "학생 정보 공유")
//
// **왜 명단을 통째로 주지 않는가.**
// 학생 레코드에는 학생·학부모 연락처, 메모, 수납 할인 사유가 들어 있다. 반주를 만드는
// 데는 하나도 쓰이지 않는다. 그걸 같이 넘기면 개인정보가 두 시스템에 흩어지고, 반주
// 쪽이 털리면 연락처까지 같이 털린다. 그래서 내보내는 건 **id·이름·반·재원여부**뿐이다.
//
// **왜 이름이 아니라 id 로 연결하는가.**
// 반주 쪽에서 학생을 이름으로 들고 있으면, 관리노트에서 개명하거나 동명이인이 들어오는
// 순간 연결이 끊긴다. 발표회 전날 "김지우가 두 명인데 누구 반주죠" 가 되지 않게
// 관리노트의 학생 id 를 그대로 물고 간다.

export const ROSTER_FORMAT = 'academy-note-piano-roster'
export const ROSTER_VERSION = 1

/** 반주 쪽으로 넘어가도 되는 항목. 이 목록에 없는 건 넘어가지 않는다. */
export const ROSTER_FIELDS = ['id', 'name', 'class', 'active']

/** 절대 넘기지 않는 항목 — 실수로 추가되면 테스트가 잡는다. */
export const NEVER_EXPORT = [
  'phone', 'parent_phone', 'memo', 'custom', 'discount',
  'school', 'grade', 'joined_at', 'siblings_group'
]

/**
 * 학생 한 명을 반주 쪽이 받을 모양으로 줄인다.
 *
 * @param {object} student  관리노트 학생 레코드
 * @param {string} className  지금 다니는 반 이름 ('' 이면 미배정)
 */
export function toRosterEntry(student, className = '') {
  return {
    id: String(student.id),
    name: String(student.name || '').trim(),
    class: String(className || ''),
    active: student.status !== '휴원' && student.status !== '퇴원'
  }
}

/**
 * 내보낼 명단을 만든다.
 *
 * @param {object[]} students
 * @param {object[]} enrollments  student_id · class_id · ended_at
 * @param {object[]} classes      id · name
 * @param {object} meta           academy(학원명) 등
 */
export function buildRoster(students, enrollments = [], classes = [], meta = {}) {
  const classNameById = new Map(classes.map((c) => [c.id, c.name || '']))
  // 지금 다니는 반만 본다 (ended_at 이 있으면 끝난 등록이다)
  const classOf = new Map()
  for (const e of enrollments) {
    if (e.ended_at) continue
    const name = classNameById.get(e.class_id)
    if (name) classOf.set(e.student_id, name)
  }
  const entries = students
    .map((s) => toRosterEntry(s, classOf.get(s.id) || ''))
    .filter((r) => r.name)
    .sort((a, b) => a.name.localeCompare(b.name, 'ko'))
  return {
    format: ROSTER_FORMAT,
    version: ROSTER_VERSION,
    academy: String(meta.academy || ''),
    exported_at: new Date().toISOString(),
    students: entries
  }
}

/** 반주 쪽에서 읽을 때 쓰는 검사 — 형식이 아니면 일찍 거절한다. */
export function parseRoster(text) {
  let json
  try {
    json = typeof text === 'string' ? JSON.parse(text) : text
  } catch (e) {
    throw new Error('명단 파일을 읽을 수 없습니다 (JSON 형식이 아닙니다)')
  }
  if (json?.format !== ROSTER_FORMAT) {
    throw new Error('피아노 반주 연동 명단 파일이 아닙니다')
  }
  if (Number(json.version) > ROSTER_VERSION) {
    throw new Error('더 최신 버전에서 만든 명단입니다. 반주 쪽을 업데이트해 주세요')
  }
  if (!Array.isArray(json.students)) throw new Error('명단이 비어 있습니다')
  return json
}

/** 파일 이름 — 학원명과 날짜가 들어가야 여러 벌이 섞이지 않는다. */
export function rosterFilename(academy = '') {
  const day = new Date().toISOString().slice(0, 10)
  const name = String(academy || '학원').replace(/[\\/:*?"<>|]/g, '').trim() || '학원'
  return `${name}-반주명단-${day}.json`
}
