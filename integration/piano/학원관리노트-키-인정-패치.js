/* ────────────────────────────────────────────────────────────────────────────
   피아노학원 관리노트 앱에 붙여 넣는 패치
   — 학원 관리노트에서 발급한 인증키(A·K 방식)도 이 앱에서 열리게 합니다.

   붙이는 법 (3분)
     1. 피아노 관리노트 앱 HTML 을 엽니다.
     2. 기존 라이선스 코드(licSelfValid / licKey 가 들어 있는 <script>) 바로 아래에
        이 파일 내용을 그대로 붙여 넣습니다.
     3. 키를 확인하는 곳에서 licSelfValid(키) 대신 licAnyValid(키, 학원명) 을 부릅니다.
        (학원명 방식 키를 쓰던 화면이라면 두 번째 인자에 그 학원명을 그대로 넘기면 됩니다)

   붙여도 기존 동작은 하나도 바뀌지 않습니다.
     · 지금까지 판 피아노 키(자기검증 방식·학원명 방식) → 그대로 통과
     · 학원 관리노트에서 발급한 통합키(A로 시작) → 새로 통과
     · 피아노 전용 키(K로 시작) → 통과
     · 학원 전용 키(M으로 시작) → 거부 (학원 관리노트에서만 쓰라고 판 키이므로)

   확인용 키 (붙여 넣은 뒤 그대로 넣어 보세요)
     AL2H-4K7P-KGMK   통합 Lite   → 열려야 함
     AP9R-3TQX-71C3   통합 Pro    → 열려야 함
     KL5M-8VNC-41GX   피아노 전용  → 열려야 함
     ML6Q-2WJD-7PG7   학원 전용    → 거부되어야 함
   ──────────────────────────────────────────────────────────────────────────── */
(function () {
  'use strict'

  // 학원 관리노트 쪽 값 — 한 글자도 바꾸지 마세요. 바꾸면 그쪽 키가 열리지 않습니다.
  var AN_SALT = 'ACADEMY-NOTE::2026::a7f3-kQ9v-Zt2m::v1'
  var AN_CHARS = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'   // I·L·O·U 제외
  var AN_PLANS = { L: 'lite', P: 'pro' }
  var AN_PRODUCTS = {
    A: { label: '통합(피아노+학원)', accepts: ['M', 'K'] },
    M: { label: '학원 관리노트 전용', accepts: ['M'] },
    K: { label: '피아노 관리노트 전용', accepts: ['K'] }
  }
  var THIS_PRODUCT = 'K'   // 이 앱은 피아노 관리노트

  function anHash32(str) {
    var h = 0x811c9dc5
    for (var i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i)
      h = Math.imul(h, 0x01000193) >>> 0
    }
    h ^= h >>> 15
    h = Math.imul(h, 0x2545f491) >>> 0
    h ^= h >>> 13
    return h >>> 0
  }

  function anChecksum(body) {
    var h = anHash32(AN_SALT + '|' + body)
    var out = ''
    for (var i = 0; i < 4; i++) out = AN_CHARS[(h >>> (i * 5)) & 31] + out
    return out
  }

  function anNorm(key) {
    return String(key || '').toUpperCase().replace(/[^0-9A-Z]/g, '')
  }

  /**
   * 학원 관리노트 형식 키인지 확인한다.
   * @returns {{ok:true, plan:'lite'|'pro', product:string, label:string}|{ok:false, reason?:string}}
   */
  function anVerify(key) {
    var k = anNorm(key)
    if (k.length !== 12) return { ok: false }
    var body = k.slice(0, 8)
    if (anChecksum(body) !== k.slice(8)) return { ok: false }

    var head = body[0]
    // 제품 구분이 없던 초기 발급분: 첫 글자가 플랜 문자(L/P)
    if (AN_PLANS[head] && !AN_PRODUCTS[head]) {
      return { ok: true, plan: AN_PLANS[head], product: 'A', label: '학원 관리노트 초기 발급분' }
    }
    var product = AN_PRODUCTS[head]
    if (!product) return { ok: false }
    var plan = AN_PLANS[body[1]]
    if (!plan) return { ok: false }
    if (product.accepts.indexOf(THIS_PRODUCT) === -1) {
      return { ok: false, reason: product.label + ' 키입니다. 이 앱에서는 사용할 수 없습니다' }
    }
    return { ok: true, plan: plan, product: head, label: product.label }
  }

  /**
   * 이 앱에서 쓰는 최종 판정 — 기존 피아노 키가 먼저, 그다음 학원 관리노트 키.
   * @param {string} key
   * @param {string} [academyName] 학원명 방식 키를 확인할 때만 필요 (기존 동작 그대로)
   */
  function licAnyValid(key, academyName) {
    if (typeof licSelfValid === 'function' && licSelfValid(key)) return true
    if (academyName && typeof licKey === 'function') {
      var norm = String(key || '').toUpperCase().replace(/\s/g, '')
      if (licKey(academyName) === norm) return true
    }
    return anVerify(key).ok
  }

  /** 어떤 키인지까지 알고 싶을 때 (안내 문구·플랜 표시에 씁니다) */
  function licDescribe(key, academyName) {
    if (typeof licSelfValid === 'function' && licSelfValid(key)) {
      return { ok: true, source: '피아노 관리노트 · 미리 만든 키', plan: 'pro' }
    }
    if (academyName && typeof licKey === 'function') {
      var norm = String(key || '').toUpperCase().replace(/\s/g, '')
      if (licKey(academyName) === norm) {
        return { ok: true, source: '피아노 관리노트 · 학원명 방식', plan: 'pro', name: academyName }
      }
    }
    var an = anVerify(key)
    if (an.ok) return { ok: true, source: '학원 관리노트 · ' + an.label, plan: an.plan }
    return { ok: false, reason: an.reason || '확인되지 않는 키입니다' }
  }

  // 앱 어디서든 부를 수 있게 전역에 올린다
  var root = typeof window !== 'undefined' ? window : globalThis
  root.anVerifyAcademyNoteKey = anVerify
  root.licAnyValid = licAnyValid
  root.licDescribe = licDescribe
})();
