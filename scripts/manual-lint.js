// 설명서 HTML 을 **글자 단위로** 훑는 검사. 브라우저가 필요 없어서 CI 가 늘 돌립니다.
//
// 설명서는 사람이 읽다가 틀린 걸 알아채는 물건이라, 틀린 채로 나가면 원장님이
// 한참 헤매신 뒤에야 우리한테 연락이 옵니다. 그래서 만들 때 잡습니다.
//
// 진짜로 그려지는지(그림이 뜨는지·목차를 누르면 움직이는지·A4 로 뽑히는지)는
// `scripts/manual-verify.mjs` 가 브라우저를 띄워서 봅니다. 여기는 그 전 단계입니다.

/**
 * @param {string} doc  만들어진 설명서 HTML 전체
 * @param {{figures?: number}} expect  원고가 부른 그림 수 (넘기면 실제와 대조한다)
 * @returns {string[]} 사람이 읽을 수 있는 문제 목록. 비어 있으면 통과.
 */
export function lintManual(doc, expect = {}) {
  const bad = []

  // 1) 목차가 없는 곳을 가리키면 눌러도 안 움직인다
  const ids = new Set([...doc.matchAll(/\sid="([^"]+)"/g)].map((m) => m[1]))
  for (const m of doc.matchAll(/<a href="#([^"]+)"/g)) {
    if (!ids.has(m[1])) bad.push(`목차가 없는 곳을 가리킵니다: #${m[1]}`)
  }

  // 2) 그림을 미뤄 받으면 **종이로 뽑을 때 빈칸으로 나온다.** 문서 안에 이미
  //    들어 있는 그림이라 미룰 통신도 없다 — 손해만 있고 이득이 없다.
  for (const m of doc.matchAll(/<img\b[^>]*>/g)) {
    if (/\bloading=/.test(m[0])) bad.push('그림에 loading= 이 붙어 있습니다 (인쇄하면 빈칸)')
    if (!/\bsrc="data:image\//.test(m[0])) bad.push('그림이 문서 밖 파일을 가리킵니다')
  }

  // 3) 원고가 부른 그림 수와 실제로 들어간 수가 같은지
  if (typeof expect.figures === 'number') {
    const drawn = [...doc.matchAll(/<figure>/g)].length
    if (drawn !== expect.figures) {
      bad.push(`그림 수가 맞지 않습니다: 원고 ${expect.figures} · 문서 ${drawn}`)
    }
  }

  return [...new Set(bad)]   // 같은 말을 스무 번 하지 않는다
}
