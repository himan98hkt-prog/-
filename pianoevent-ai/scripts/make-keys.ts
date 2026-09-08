/**
 * 인증키 찍어 내기 — **파는 쪽에서만** 쓴다.
 *
 *   RECITAL_LICENSE_SECRET=... npm run key:new -- --plan year --count 5
 *   RECITAL_LICENSE_SECRET=... npm run key:new -- --plan life --count 1
 *
 * 키를 만드는 규칙은 본체(`lib/license/key.ts`)에 한 벌만 둔다. 두 군데 적으면
 * 반드시 어긋나고, 어긋나면 원장님 화면에 「저희가 발급한 것이 아닙니다」가 뜬다.
 *
 * **비밀은 설치본을 뽑을 때 쓴 것과 같아야 한다.** 다르면 위와 같은 일이 벌어진다.
 */
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname } from 'node:path'
import { PLAN_LABEL, makeKey, type LicensePlan } from '../lib/license/key.ts'

const args = process.argv.slice(2)
const get = (name: string, fallback: string): string => {
  const at = args.indexOf(`--${name}`)
  return at >= 0 && args[at + 1] ? args[at + 1] : fallback
}

const plan = get('plan', 'year') as LicensePlan
const count = Number(get('count', '1'))
const months = Number(get('months', plan === 'year' ? '12' : plan === 'trial' ? '1' : '0'))
const out = get('out', '')

if (!['life', 'year', 'trial'].includes(plan)) {
  console.error('--plan 은 life · year · trial 중 하나입니다')
  process.exit(1)
}
if (!process.env.RECITAL_LICENSE_SECRET) {
  console.error('RECITAL_LICENSE_SECRET 이 없습니다 — 개발용 비밀로 만든 키는 파실 수 없습니다.')
  console.error('설치본을 뽑을 때 쓰신 비밀을 그대로 넣어 주세요.')
  process.exit(1)
}

/** 마지막으로 쓴 일련번호를 적어 둔다 — 같은 번호를 두 번 팔지 않기 위해서다 */
const LEDGER = '배포/키/last-serial.txt'
const asked = get('serial', '')
let serial = asked ? Number(asked) : existsSync(LEDGER) ? Number(readFileSync(LEDGER, 'utf8').trim()) + 1 : 1

const today = new Date()
const expiresAt =
  months > 0 ? new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth() + months, today.getUTCDate())) : null

const rows: { serial: number; key: string; expires: string }[] = []
for (let i = 0; i < count; i += 1) {
  rows.push({ serial, key: makeKey({ plan, expiresAt, serial }), expires: expiresAt ? expiresAt.toISOString().slice(0, 10) : '' })
  serial += 1
}

console.log(`\n${rows.length}개 · ${PLAN_LABEL[plan]}${expiresAt ? ` · ${rows[0].expires} 까지` : ''}\n`)
for (const r of rows) console.log(`  ${r.key}   (일련번호 ${r.serial})`)

const csv = [
  '일련번호,판,만료일,키,판매일,받으신 분',
  ...rows.map((r) => `${r.serial},${PLAN_LABEL[plan]},${r.expires},${r.key},,`),
].join('\n')

mkdirSync(dirname(LEDGER), { recursive: true })
writeFileSync(LEDGER, String(rows[rows.length - 1].serial), 'utf8')
if (out) {
  mkdirSync(dirname(out), { recursive: true })
  writeFileSync(out, `${csv}\n`, 'utf8')
  console.log(`\n장부: ${out}`)
}
console.log(`\n다음 일련번호는 ${rows[rows.length - 1].serial + 1} 입니다 (${LEDGER} 에 적어 두었습니다).`)
