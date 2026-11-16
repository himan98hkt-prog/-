// 시작 가이드 — 처음 쓰는 원장님이 "다음에 뭘 해야 하지?" 에서 멈추지 않게 한다.
//
// 빈 화면에서 시작하면 대부분 여기서 그만둔다. 네 가지만 순서대로 하면 평소처럼 쓸 수 있고,
// 한 가지를 끝낼 때마다 표시가 채워진다. 전부 끝나면(또는 닫으면) 사라진다.

/**
 * @param {{classes:number, students:number, hasAttendance:boolean, hasPayments:boolean}} state
 * @returns {{id:string, title:string, desc:string, cta:string, view:string, done:boolean}[]}
 */
export function setupSteps({ classes = 0, students = 0, hasAttendance = false, hasPayments = false } = {}) {
  return [
    {
      id: 'class', title: '반 만들기', cta: '반 만들러 가기', view: 'timetable',
      desc: '요일과 시간만 정하면 됩니다. 예) 월수 4시반',
      done: classes > 0
    },
    {
      id: 'student', title: '원생 등록하기', cta: '원생 등록하러 가기', view: 'students',
      desc: '이름만 넣어도 됩니다. 엑셀 명단이 있으면 한 번에 가져올 수 있습니다.',
      done: students > 0
    },
    {
      id: 'attendance', title: '출석 체크해 보기', cta: '출석 체크하러 가기', view: 'attendance',
      desc: '학생 이름을 한 번 누르면 출석입니다.',
      done: hasAttendance
    },
    {
      id: 'payment', title: '이번 달 수강료 청구하기', cta: '수강료 청구하러 가기', view: 'payments',
      desc: '버튼 한 번으로 모든 원생의 이번 달 수강료가 만들어집니다.',
      done: hasPayments
    }
  ]
}

/** 지금 해야 할 한 가지와 진행률 */
export function setupProgress(steps = []) {
  const done = steps.filter((s) => s.done).length
  const next = steps.find((s) => !s.done) || null
  return { done, total: steps.length, next, complete: steps.length > 0 && done === steps.length }
}
