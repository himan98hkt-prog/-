// 퍼널모아(워드프레스) 플러그인이 PHP 로 만든 키가 이 앱에서 실제로 열리는지 확인한다.
//
// 키 규칙이 자바스크립트(앱)와 PHP(플러그인) 두 곳에 있다. 한쪽만 바뀌면
// "결제하고 받은 키가 안 들어간다" 는 사고가 나므로, PHP 가 뽑은 키를 앱의 검증기로 직접 넣어 본다.
// PHP 가 없는 환경에서는 건너뛴다.

import { describe, it, expect } from 'vitest'
import { spawnSync } from 'node:child_process'
import { verifyKey } from '../src/core/license.js'

const RUNNER = 'integration/funnelmoa/tests/run.php'
// 점검은 SQLite 메모리 DB 에 실제 SQL 을 돌린다 — PHP 와 그 확장이 모두 있어야 한다
const hasPhp = spawnSync('php', ['-r', 'exit(class_exists("SQLite3") ? 0 : 1);']).status === 0

describe.skipIf(!hasPhp)('퍼널모아 플러그인', () => {
  it('플러그인 자체 점검(결제 신호 → 키 발급 → 메일)이 모두 통과한다', () => {
    const res = spawnSync('php', [RUNNER], { encoding: 'utf8' })
    expect(res.stdout).toContain('실패 0')
    expect(res.status, res.stdout.split('\n').filter((l) => l.includes('✗')).join('\n')).toBe(0)
  })

  it('플러그인이 만든 키는 앱에서 그대로 열린다 (종류별 20개)', () => {
    const res = spawnSync('php', [RUNNER, '--keys', '20'], { encoding: 'utf8' })
    expect(res.status).toBe(0)
    const lines = res.stdout.trim().split('\n').map((l) => l.split(' '))
    expect(lines).toHaveLength(7 * 20)

    const expected = {
      piano: { plan: 'pro', scheme: 'piano' },
      'A-pro': { plan: 'pro', product: 'A' },
      'A-lite': { plan: 'lite', product: 'A' },
      'M-pro': { plan: 'pro', product: 'M' },
      'M-lite': { plan: 'lite', product: 'M' }
    }
    for (const [type, key] of lines) {
      if (type.startsWith('K-')) {
        // 피아노 전용 키 — 학원 앱에서는 거부하고, 피아노 앱(K)에서는 연다
        expect(verifyKey(key).ok, key).toBe(false)
        expect(verifyKey(key, { productCode: 'K' })).toMatchObject({ ok: true, product: 'K', plan: type === 'K-pro' ? 'pro' : 'lite' })
        continue
      }
      expect(verifyKey(key), `${type} ${key}`).toMatchObject({ ok: true, ...expected[type] })
    }
  })
})
