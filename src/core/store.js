// 판매 정보 — 앱 안의 "구매하기" 버튼이 여는 곳.
//
// 체험판을 써 본 원장님이 "사야겠다" 고 마음먹은 그 자리에서 결제 화면으로 갈 수 있어야 한다.
// 주소는 빌드할 때 환경 변수로 바꾼다(코드를 고칠 필요 없음):
//
//   VITE_BUY_URL=https://내사이트.com/product/note  npm run build
//   VITE_SUPPORT_URL=https://pf.kakao.com/_xxxx     (카카오톡 채널 등 문의 창구 — 없으면 버튼이 숨는다)
//   VITE_SUPPORT_LABEL=카카오톡으로 문의하기

const env = import.meta.env || {}

export const STORE = {
  productName: '학원 관리노트',
  buyUrl: env.VITE_BUY_URL || 'https://accelssam.com/',
  supportUrl: env.VITE_SUPPORT_URL || '',
  supportLabel: env.VITE_SUPPORT_LABEL || '문의하기'
}

/** 새 창으로 구매 화면을 연다. 어느 화면에서 눌렀는지 주소에 남겨 판매자가 유입 경로를 볼 수 있게 한다. */
export function buyUrl(from = '') {
  try {
    const url = new URL(STORE.buyUrl)
    if (from) url.searchParams.set('from', `app-${from}`)
    return url.toString()
  } catch {
    return STORE.buyUrl
  }
}

/**
 * 체험 안내 문구 (순수 함수).
 * 남은 날이 줄수록 말투가 분명해진다 — 마지막 날 갑자기 잠기는 일이 없도록 미리 알린다.
 * @returns {{tone:'info'|'warn'|'danger', text:string, short:string}}
 */
export function trialNotice(daysLeft) {
  const d = Math.max(0, Number(daysLeft) || 0)
  if (d <= 1) {
    return { tone: 'danger', text: '무료 체험이 오늘 끝납니다. 넣어 두신 자료는 구매 후에도 그대로 이어집니다.', short: '체험 오늘 종료' }
  }
  if (d <= 3) {
    return { tone: 'warn', text: `무료 체험이 ${d}일 남았습니다. 넣어 두신 자료는 구매 후에도 그대로 이어집니다.`, short: `체험 ${d}일 남음` }
  }
  return { tone: 'info', text: `무료 체험 중입니다 · ${d}일 남음. 지금 넣는 자료는 구매 후에도 그대로 이어집니다.`, short: `체험 ${d}일 남음` }
}
