import { createHmac, timingSafeEqual } from 'node:crypto'

/**
 * 인증키.
 *
 * 원장님은 결제하시고 **키 한 줄**을 받으신다. 프로그램에 한 번 넣으면 그 컴퓨터에서
 * 계속 쓰신다. 확인은 **인터넷 없이** 이 컴퓨터 안에서 끝난다 —
 * 「학원 자료가 밖으로 나가지 않는다」는 약속을 인증 때문에 깨지 않기 위해서다.
 *
 * 키에는 무엇이 들었나 — 판(평생·1년·체험) · 만료일 · 일련번호, 그리고 그 셋을 묶은
 * **서명**이다. 서명이 맞지 않으면 한 글자만 바꿔 만든 키도 걸러진다.
 *
 * 한계는 분명히 적어 둔다. 오프라인 확인은 **유출된 키를 막을 수 없다.**
 * 서버에 물어보지 않으니 「이 키는 취소됐다」를 알 길이 없다. 그 대신 서버 운영비가
 * 0원이고 인터넷이 끊긴 학원에서도 열린다. 파는 규모에서는 이쪽이 맞다.
 *
 * 키는 사람이 손으로 치신다. 그래서 **크록포드 base32** 를 쓴다 — I·L·O·U 가 빠져 있어
 * 1 과 I, 0 과 O 를 헷갈릴 일이 없고, 입력할 때 소문자·하이픈을 알아서 받아 준다.
 */

/** 크록포드 base32 — I L O U 가 없다 */
const ALPHABET = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'
/** 사람이 잘못 치기 쉬운 글자를 제자리로 돌린다 */
const FIX: Record<string, string> = { I: '1', L: '1', O: '0', U: 'V' }

export type LicensePlan = 'life' | 'year' | 'trial'

const PLAN_CODE: Record<LicensePlan, number> = { life: 0, year: 1, trial: 2 }
const PLAN_NAME: Record<number, LicensePlan> = { 0: 'life', 1: 'year', 2: 'trial' }

export const PLAN_LABEL: Record<LicensePlan, string> = {
  life: '평생 이용',
  year: '1년 이용',
  trial: '체험',
}

/** 만료일을 세는 기준 날짜 */
const EPOCH = Date.UTC(2026, 0, 1)
const DAY = 86_400_000

export const KEY_PREFIX = 'RM'

export interface LicenseFields {
  plan: LicensePlan
  /** 없으면 만료 없음(평생) */
  expiresAt?: Date | null
  /** 몇 번째로 발급한 키인가 — 누구에게 팔았는지 판매 장부와 맞춰 보는 번호 */
  serial: number
}

/**
 * 서명에 쓰는 비밀.
 *
 * 설치본을 뽑을 때 `RECITAL_LICENSE_SECRET` 으로 넣어 준다. 저장소에는 두지 않는다 —
 * 저장소가 공개돼 있어 여기 적어 두면 **누구나 키를 찍어 낼 수 있다.**
 * 없을 때는 개발용 비밀로 돌아간다. 그 비밀로 만든 키는 개발판에서만 열린다.
 */
function secret(): string {
  return process.env.RECITAL_LICENSE_SECRET?.trim() || 'recital-manager-dev-secret'
}

function toBits(value: number, width: number): string {
  return value.toString(2).padStart(width, '0')
}

/** 44비트 알맹이 — 판(4) · 만료일(16) · 일련번호(20). 앞의 4비트는 판올림 자리다 */
function payloadBits(fields: LicenseFields): string {
  const days = fields.expiresAt ? Math.round((fields.expiresAt.getTime() - EPOCH) / DAY) : 0
  if (days < 0 || days > 0xffff) throw new Error('만료일이 셀 수 있는 범위를 벗어났습니다')
  if (fields.serial < 0 || fields.serial > 0xfffff) throw new Error('일련번호가 범위를 벗어났습니다')
  return toBits(1, 4) + toBits(PLAN_CODE[fields.plan], 4) + toBits(days, 16) + toBits(fields.serial, 20)
}

function macBits(payload: string): string {
  const mac = createHmac('sha256', secret()).update(payload).digest()
  // 56비트만 쓴다 — 키를 손으로 칠 수 있는 길이에 맞춘다
  let bits = ''
  for (let i = 0; i < 7; i += 1) bits += toBits(mac[i], 8)
  return bits
}

function bitsToKey(bits: string): string {
  let out = ''
  for (let i = 0; i < bits.length; i += 5) out += ALPHABET[parseInt(bits.slice(i, i + 5), 2)]
  return out
}

/** 손으로 치신 것을 알아본다 — 소문자·하이픈·헷갈리는 글자를 바로잡는다 */
export function normalizeKey(input: string): string {
  const up = input.toUpperCase().replace(/[^0-9A-Z]/g, '')
  const body = up.startsWith(KEY_PREFIX) ? up.slice(KEY_PREFIX.length) : up
  return [...body].map((c) => FIX[c] ?? c).join('')
}

/** 보기 좋게 다섯 자씩 끊는다 */
export function formatKey(body: string): string {
  return `${KEY_PREFIX}-${(body.match(/.{1,5}/g) ?? []).join('-')}`
}

/** 키를 만든다 (파는 쪽에서만 쓴다) */
export function makeKey(fields: LicenseFields): string {
  const payload = payloadBits(fields)
  return formatKey(bitsToKey(payload + macBits(payload)))
}

export interface LicenseCheck {
  ok: boolean
  /** 왜 안 되는지 — 원장님께 그대로 보여 드릴 말 */
  reason?: string
  plan?: LicensePlan
  expiresAt?: Date | null
  serial?: number
}

/**
 * 키를 확인한다.
 *
 * @param now 만료를 재는 기준 시각. 검사에서 넣어 준다.
 */
export function checkKey(input: string, now = new Date()): LicenseCheck {
  const body = normalizeKey(input)
  if (body.length !== 20) {
    return { ok: false, reason: '키는 스무 글자입니다. 받으신 것을 다시 확인해 주세요.' }
  }
  let bits = ''
  for (const ch of body) {
    const at = ALPHABET.indexOf(ch)
    if (at < 0) return { ok: false, reason: '키에 쓸 수 없는 글자가 있습니다.' }
    bits += toBits(at, 5)
  }
  const payload = bits.slice(0, 44)
  const mac = bits.slice(44)
  const want = Buffer.from(macBits(payload))
  const got = Buffer.from(mac)
  if (want.length !== got.length || !timingSafeEqual(want, got)) {
    return { ok: false, reason: '이 키는 저희가 발급한 것이 아닙니다. 한 글자씩 다시 확인해 주세요.' }
  }
  if (parseInt(payload.slice(0, 4), 2) !== 1) {
    return { ok: false, reason: '더 새로운 판의 키입니다. 프로그램을 최신판으로 올려 주세요.' }
  }
  const plan = PLAN_NAME[parseInt(payload.slice(4, 8), 2)]
  if (!plan) return { ok: false, reason: '알 수 없는 이용 형태입니다.' }
  const days = parseInt(payload.slice(8, 24), 2)
  const serial = parseInt(payload.slice(24), 2)
  const expiresAt = days === 0 ? null : new Date(EPOCH + days * DAY)
  if (expiresAt && expiresAt.getTime() < now.getTime()) {
    return {
      ok: false,
      reason: `이용 기간이 ${expiresAt.getFullYear()}년 ${expiresAt.getMonth() + 1}월 ${expiresAt.getDate()}일에 끝났습니다.`,
      plan,
      expiresAt,
      serial,
    }
  }
  return { ok: true, plan, expiresAt, serial }
}
