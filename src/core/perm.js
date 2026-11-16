// 강사별 권한 — owner(전체) / teacher(담당 반의 출결·상담) / desk(수납·원생 조회)

export const ROLES = {
  owner: { label: '원장', desc: '모든 기능' },
  teacher: { label: '강사', desc: '담당 반 출결·상담·리포트' },
  desk: { label: '데스크', desc: '수납·원생 조회·출결 확인' }
}

const MATRIX = {
  owner: ['*'],
  teacher: ['attendance:write', 'attendance:read', 'students:read', 'students:write', 'counsel:read', 'counsel:write', 'timetable:read', 'report:make', 'notice:make', 'payments:read'],
  desk: ['payments:read', 'payments:write', 'students:read', 'students:write', 'attendance:read', 'expenses:read', 'timetable:read', 'notice:make', 'counsel:read']
}

export function can(role, action) {
  const list = MATRIX[role] || []
  return list.includes('*') || list.includes(action)
}

/** 강사는 자기 담당 반만 다룬다 */
export function visibleClasses(user, classes = []) {
  if (!user || user.role === 'owner' || user.role === 'desk') return classes
  return classes.filter((c) => c.teacher_id === user.id)
}

// primary: 휴대폰 하단 탭에 놓을 다섯 개. 나머지는 '더보기' 로 들어간다.
// (탭이 아홉 개면 아무것도 눈에 들어오지 않는다)
export const NAV = [
  { id: 'today', label: '오늘', icon: 'home', perm: 'attendance:read', primary: true, desc: '오늘 처리할 일' },
  { id: 'attendance', label: '출결', icon: 'checkCircle', perm: 'attendance:read', primary: true, desc: '반별 출석 체크' },
  { id: 'students', label: '원생', icon: 'users', perm: 'students:read', primary: true, desc: '원생 등록·검색' },
  { id: 'payments', label: '수납', icon: 'won', perm: 'payments:read', primary: true, desc: '청구·수납·미납' },
  { id: 'timetable', label: '시간표', icon: 'calendar', perm: 'timetable:read', desc: '반 만들기 · 요일과 시간' },
  { id: 'counsel', label: '상담', icon: 'chat', perm: 'counsel:read', desc: '학부모 상담 적어 두기' },
  { id: 'expenses', label: '지출', icon: 'wallet', perm: 'expenses:read', desc: '월세·교재비처럼 나간 돈' },
  { id: 'dashboard', label: '현황', icon: 'chart', perm: 'stats:read', desc: '들어온 돈 · 출석률 한눈에' },
  { id: 'settings', label: '설정', icon: 'settings', perm: 'settings:read', desc: '글씨 크기 · 학원 이름 · 백업' }
]

export function navFor(role) {
  return NAV.filter((n) => can(role, n.perm))
}
