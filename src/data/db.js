import Dexie from 'dexie'

// Lite 는 IndexedDB 가 원본, Pro 는 같은 IndexedDB 가 서버 미러 + 오프라인 큐 역할을 한다.
// 어느 플랜이든 화면은 항상 로컬을 읽기 때문에 렌더 성능이 네트워크와 무관하다(local-first).
//
// 인덱스 설계 원칙: 출결/수납은 절대 전체 로드하지 않는다. 월 단위 범위 질의만 허용.
export const DB_NAME = 'academy-note'

export function createDb(name = DB_NAME) {
  const db = new Dexie(name)
  db.version(1).stores({
    settings: 'key',
    users: 'id, role, name',
    subjects: 'id, name',
    classes: 'id, subject_id, teacher_id, status',
    students: 'id, name, status, siblings_group, school, grade, [status+name]',
    enrollments: 'id, student_id, class_id, [class_id+ended_at], [student_id+ended_at]',
    attendance: 'id, date, student_id, [class_id+date], [student_id+date], [date+class_id]',
    payments: 'id, month, student_id, status, [student_id+month], [month+status]',
    expenses: 'id, date, category',
    counselLogs: 'id, student_id, created_at, type, [student_id+created_at]',
    notices: 'id, student_id, sent_at',
    monthlyStats: 'month',
    outbox: '++seq, table, ts'
  })

  // v2 — 피아노 반주에서 되받는 연습 기록.
  //
  // id 는 무작위가 아니라 **그 연습을 가리키는 열쇠**(학생::곡::날짜::기기)다.
  // 그래야 같은 파일을 두 번 넣어도 줄이 안 늘어난다. 이 숫자는 학부모 리포트로
  // 나가기 때문에, 두 번 세는 것이 안 세는 것보다 나쁘다.
  db.version(2).stores({
    practice: 'id, student_id, date, [student_id+date]'
  })

  return db
}

export const db = createDb()
