// 알림 문구 템플릿 — 자동 발송은 범위 밖. 문구를 만들어 클립보드/Web Share 로 넘기는 것까지가 이 모듈의 일.

export const TEMPLATE_VARS = [
  { key: '{원생명}', desc: '원생 이름' },
  { key: '{학원명}', desc: '브랜딩에 설정한 학원명' },
  { key: '{반}', desc: '반 이름' },
  { key: '{과목}', desc: '과목명' },
  { key: '{금액}', desc: '청구/미납 금액' },
  { key: '{월}', desc: '대상 월 (예: 3월)' },
  { key: '{날짜}', desc: '대상 날짜' },
  { key: '{출석률}', desc: '해당 월 출석률' },
  { key: '{강사}', desc: '담당 강사명' }
]

export const DEFAULT_TEMPLATES = [
  {
    id: 'absent',
    name: '결석 안내',
    body: '안녕하세요, {학원명}입니다.\n{날짜} {반} 수업에 {원생명} 학생이 결석하였습니다.\n확인 부탁드립니다. 감사합니다.'
  },
  {
    id: 'payment',
    name: '수납 안내',
    body: '안녕하세요, {학원명}입니다.\n{원생명} 학생 {월} 수강료 {금액} 안내드립니다.\n납부 관련 문의는 언제든 연락 주세요. 감사합니다.'
  },
  {
    id: 'report',
    name: '리포트 발송',
    body: '{학원명}에서 {원생명} 학생의 {월} 학습 리포트를 보내드립니다.\n출석률 {출석률}%, 담당 강사 {강사}.\n자세한 내용은 첨부 이미지를 확인해 주세요.'
  },
  {
    id: 'recruit',
    name: '공석 안내',
    body: '{학원명} {반}({과목}) 수업에 자리가 생겼습니다.\n관심 있는 분은 편하게 문의 주세요!'
  }
]

/** 템플릿 문자열의 변수를 치환한다. 값이 없는 변수는 그대로 남겨 원장이 눈으로 확인할 수 있게 한다. */
export function renderTemplate(body, vars = {}) {
  return String(body || '').replace(/\{[^{}]+\}/g, (token) => {
    const v = vars[token] ?? vars[token.slice(1, -1)]
    return v === undefined || v === null || v === '' ? token : String(v)
  })
}

/** 치환되지 않고 남은 변수 목록 — 발송 전 경고용 */
export function missingVars(rendered) {
  return [...new Set(String(rendered || '').match(/\{[^{}]+\}/g) || [])]
}

/** 정의되지 않은 변수를 쓴 템플릿인지 검사 (설정 화면 유효성 검사) */
export function unknownVars(body) {
  const known = new Set(TEMPLATE_VARS.map((v) => v.key))
  return [...new Set(String(body || '').match(/\{[^{}]+\}/g) || [])].filter((v) => !known.has(v))
}
