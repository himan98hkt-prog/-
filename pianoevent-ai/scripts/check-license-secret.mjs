/**
 * 인증키 비밀이 들어 있는지 보고, 없으면 **설치본을 못 뽑게 막는다.**
 *
 * 비밀 없이 뽑은 설치본은 개발용 비밀로 잠긴다. 그 판은
 *   ① 파실 발급기의 키를 열지 못하고,
 *   ② 개발용 비밀이 공개 저장소에 적혀 있어 누구나 키를 위조할 수 있다.
 * 그런 판이 받는 자리에 올라가는 것이 가장 나쁘다. 그래서 경고가 아니라 **중단**이다.
 */
import { secretFingerprint, usingDevSecret } from '../lib/license/key.ts'

if (usingDevSecret()) {
  console.error(`
╔══════════════════════════════════════════════════════════════════╗
║  멈췄습니다 — 인증키 비밀(RECITAL_LICENSE_SECRET)이 없습니다.    ║
╚══════════════════════════════════════════════════════════════════╝

이대로 뽑으면 개발용 비밀이 든 설치본이 나옵니다. 그 판은

  · 발급기로 만드신 키를 **열지 못하고**
  · 개발용 비밀은 공개 저장소에 적혀 있어 **누구나 키를 위조**할 수 있습니다

파는 물건이므로 여기서 멈춥니다.

넣으시는 곳 (한 번만 하시면 됩니다)

  https://github.com/himan98hkt-prog/-/settings/secrets/actions/new

  Name   RECITAL_LICENSE_SECRET
  Secret 정하신 비밀값 (발급기를 만드실 때 쓴 것과 **똑같아야** 합니다)

넣으신 뒤 Actions 에서 이 작업을 다시 돌리시면 설치본이 나옵니다.
자세한 것은 pianoevent-ai/docs/SELLING-LICENSE.md 에 있습니다.
`)
  process.exit(1)
}

console.log(`인증키 비밀이 들어 있습니다. 이 설치본의 지문 — ${secretFingerprint()}

발급기 화면 위쪽에 뜨는 지문과 이 여덟 글자가 같으면,
그 발급기로 만드신 키가 이 설치본에서 열립니다.`)
