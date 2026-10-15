/**
 * 검사 전에 **빌드가 최신인지** 확인한다.
 *
 * 검사 스크립트는 `next start` 로 이미 만들어 둔 것을 띄운다. 소스를 고친 뒤 빌드를
 * 잊고 검사를 돌리면 **고치기 전 화면을 재게 된다.** 실제로 이것 때문에 이미 고쳐진
 * 대비 문제를 열두 건 더 쫓았다 — 검사는 통과·실패를 말할 뿐 「낡았다」고는 말해 주지 않는다.
 *
 * 그래서 소스가 빌드보다 새로우면 검사를 시작하지 않고 알려 준다.
 */
import { existsSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'

const WATCH = ['app', 'components', 'lib', 'public/art', 'next.config.mjs', 'tailwind.config.ts']

function newest(at) {
  if (!existsSync(at)) return 0
  const s = statSync(at)
  if (!s.isDirectory()) return s.mtimeMs
  let max = 0
  for (const name of readdirSync(at)) max = Math.max(max, newest(join(at, name)))
  return max
}

/** 빌드가 낡았으면 그 자리에서 끝낸다 */
export function requireFreshBuild(root = process.cwd()) {
  const stamp = join(root, '.next', 'BUILD_ID')
  if (!existsSync(stamp)) {
    console.error('빌드가 없습니다. 먼저 `npm run build` 를 하세요.')
    process.exit(1)
  }
  const built = statSync(stamp).mtimeMs
  const changed = WATCH.map((rel) => newest(join(root, rel))).reduce((a, b) => Math.max(a, b), 0)
  if (changed > built) {
    console.error('소스가 빌드보다 새롭습니다 — 고치기 전 화면을 재게 됩니다.')
    console.error('먼저 `npm run build` 를 하세요.')
    process.exit(1)
  }
}

/**
 * 검사에 쓸 문(port)이 비어 있는지 본다.
 *
 * 앞선 검사가 서버를 남겨 두고 죽으면 그 서버가 그대로 문을 물고 있다. 다음 검사는
 * 제 서버를 띄우지 못하고(조용히 실패한다) **남이 띄워 둔 낡은 서버를 잰다.**
 * 실제로 이것 때문에 이미 고친 문제가 열두 건 더 실패로 나왔고, 원인을 찾는 데
 * 한참 걸렸다 — 검사가 거짓말을 하면 검사가 없느니만 못하다.
 */
export async function requireFreePort(port) {
  const { createServer } = await import('node:net')
  await new Promise((resolve) => {
    const probe = createServer()
    probe.once('error', () => {
      console.error(`${port} 번 문을 이미 다른 것이 쓰고 있습니다 — 남의 서버를 재게 됩니다.`)
      console.error('앞선 검사가 남긴 서버일 수 있습니다. 그것을 먼저 내려 주세요.')
      process.exit(1)
    })
    probe.listen(port, '127.0.0.1', () => probe.close(resolve))
  })
}

/**
 * 검사가 어떻게 끝나든 띄운 서버를 함께 내린다.
 *
 * 검사가 중간에 죽으면 서버만 남는다. 남은 서버는 다음 검사의 문을 물고 앉아
 * **낡은 화면을 재게 만든다.** 그러니 끝은 어떤 끝이든 서버를 내리는 것으로 끝나야 한다.
 */
export function killOnExit(child) {
  const stop = () => {
    try {
      process.kill(-child.pid)
    } catch {
      try {
        child.kill()
      } catch {
        /* 이미 내려갔으면 그대로 */
      }
    }
  }
  process.once('exit', stop)
  for (const sig of ['SIGINT', 'SIGTERM', 'SIGHUP']) {
    process.once(sig, () => {
      stop()
      process.exit(1)
    })
  }
  process.once('uncaughtException', (err) => {
    stop()
    console.error(err)
    process.exit(1)
  })
}
