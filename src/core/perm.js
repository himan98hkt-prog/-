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

export const NAV = [
  { id: 'today', label: '오늘', icon: '🏠', perm: 'attendance:read' },
  { id: 'attendance', label: '출결', icon: '✓', perm: 'attendance:read' },
  { id: 'students', label: '원생', icon: '👤', perm: 'students:read' },
  { id: 'payments', label: '수납', icon: '₩', perm: 'payments:read' },
  { id: 'timetable', label: '시간표', icon: '🗓', perm: 'timetable:read' },
  { id: 'counsel', label: '상담', icon: '💬', perm: 'counsel:read' },
  { id: 'expenses', label: '지출', icon: '📉', perm: 'expenses:read' },
  { id: 'dashboard', label: '현황', icon: '📊', perm: 'stats:read' },
  { id: 'settings', label: '설정', icon: '⚙', perm: 'settings:read' }
]

export function navFor(role) {
  return NAV.filter((n) => can(role, n.perm))
}
