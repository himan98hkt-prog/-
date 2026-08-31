// custom 필드 — "전 계열 범용"의 핵심 메커니즘.
// 원장이 설정에서 항목을 직접 정의하면 원생 카드/리포트에 자동 노출된다.
//   예) 피아노 → 진도 교재 / 태권도 → 띠 급수 / 영어 → 레벨 테스트 점수

export const FIELD_TYPES = [
  { type: 'text', label: '짧은 글' },
  { type: 'number', label: '숫자' },
  { type: 'select', label: '선택 목록' },
  { type: 'date', label: '날짜' },
  { type: 'textarea', label: '여러 줄 메모' }
]

/** 계열별 프리셋 — 시작 마법사에서 한 번에 깔아준다 */
export const PRESETS = {
  교과: [
    { key: 'textbook', label: '진도 교재', type: 'text', onCard: true, onReport: true },
    { key: 'progress', label: '진도(단원)', type: 'text', onCard: true, onReport: true },
    { key: 'last_score', label: '최근 시험 점수', type: 'number', onCard: false, onReport: true }
  ],
  어학: [
    { key: 'level', label: '레벨', type: 'select', options: ['Starter', 'Basic', 'Inter', 'Advanced'], onCard: true, onReport: true },
    { key: 'level_test', label: '레벨 테스트 점수', type: 'number', onCard: false, onReport: true },
    { key: 'book', label: '교재', type: 'text', onCard: true, onReport: true }
  ],
  예체능: [
    { key: 'piece', label: '진도 곡/작품', type: 'text', onCard: true, onReport: true },
    { key: 'book', label: '교재', type: 'text', onCard: true, onReport: true },
    { key: 'contest', label: '대회/발표회', type: 'text', onCard: false, onReport: true }
  ],
  체육: [
    { key: 'belt', label: '띠 급수', type: 'select', options: ['흰띠', '노란띠', '파란띠', '빨간띠', '검은띠'], onCard: true, onReport: true },
    { key: 'promo_at', label: '최근 승급일', type: 'date', onCard: false, onReport: true },
    { key: 'goal', label: '목표', type: 'text', onCard: false, onReport: true }
  ],
  공부방: [
    { key: 'subjectFocus', label: '집중 과목', type: 'text', onCard: true, onReport: true },
    { key: 'homework', label: '숙제 관리', type: 'select', options: ['우수', '보통', '미흡'], onCard: false, onReport: true }
  ]
}

const KEY_RE = /^[a-zA-Z][a-zA-Z0-9_]{0,23}$/

export function validateField(field, existing = []) {
  const errors = []
  if (!field?.label?.trim()) errors.push('항목 이름을 입력해 주세요')
  if (!KEY_RE.test(field?.key || '')) errors.push('저장 키는 영문으로 시작하는 24자 이내 영문/숫자/_ 여야 합니다')
  if (!FIELD_TYPES.some((t) => t.type === field?.type)) errors.push('항목 종류를 선택해 주세요')
  if (field?.type === 'select' && !(field.options || []).filter(Boolean).length) errors.push('선택 목록에는 항목이 1개 이상 필요합니다')
  if (existing.some((f) => f.key === field?.key)) errors.push('이미 같은 저장 키가 있습니다')
  return errors
}

/** 저장 전 값 정규화 — 정의되지 않은 키는 버린다(스키마 오염 방지) */
export function normalizeValues(fields = [], values = {}) {
  const out = {}
  for (const f of fields) {
    let v = values[f.key]
    if (v === undefined || v === null || v === '') continue
    if (f.type === 'number') {
      const n = Number(v)
      if (Number.isNaN(n)) continue
      v = n
    } else if (f.type === 'select') {
      if (!(f.options || []).includes(String(v))) continue
      v = String(v)
    } else {
      v = String(v)
    }
    out[f.key] = v
  }
  return out
}

export function displayPairs(fields = [], values = {}, where = 'card') {
  const flag = where === 'report' ? 'onReport' : 'onCard'
  return fields
    .filter((f) => f[flag])
    .map((f) => ({ key: f.key, label: f.label, value: values?.[f.key] ?? '' }))
    .filter((p) => p.value !== '')
}
