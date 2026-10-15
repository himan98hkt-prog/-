import { networkInterfaces } from 'node:os'

/**
 * 이 컴퓨터가 공유기에서 어떤 주소로 보이는가.
 *
 * 원장님이 태블릿으로 같은 화면을 여시려면 **PC 의 주소**를 아셔야 한다.
 * 「명령창을 열고 ipconfig 를 치세요」는 우리가 없애기로 한 종류의 안내다.
 * 그래서 프로그램이 직접 찾아 화면에 적어 드린다.
 *
 * 여기서 나가는 것은 없다 — 이 컴퓨터의 랜카드를 들여다볼 뿐이다.
 */
export function lanAddresses(): string[] {
  const found: string[] = []
  try {
    for (const list of Object.values(networkInterfaces())) {
      for (const at of list ?? []) {
        if (at.family !== 'IPv4' || at.internal) continue
        // 169.254.x 는 공유기를 못 찾았을 때 윈도우가 스스로 붙이는 주소다 — 쓸 수 없다
        if (at.address.startsWith('169.254.')) continue
        found.push(at.address)
      }
    }
  } catch {
    /* 못 읽으면 빈 목록 — 화면에서 「찾지 못했습니다」로 안내한다 */
  }
  // 집·학원 공유기 대역(192.168.…)을 앞에 둔다. 원장님이 고르실 일이 없게
  return found.sort((a, b) => Number(b.startsWith('192.168.')) - Number(a.startsWith('192.168.')))
}

/** 지금 서버가 듣고 있는 문 */
export function serverPort(): string {
  return process.env.PORT?.trim() || '3000'
}

/** 태블릿·휴대폰에서 열 수 있게 켜 두셨는가 */
export function lanOpen(): boolean {
  return process.env.PIANOEVENT_LAN === '1'
}
