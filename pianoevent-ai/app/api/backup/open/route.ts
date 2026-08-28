import { spawn } from 'node:child_process'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { BACKUP_DIR } from '@/lib/events/backup'
import { guard, ok } from '@/lib/http'

export const dynamic = 'force-dynamic'

/**
 * 자동 저장 폴더를 탐색기로 열어 준다.
 *
 * "백업 폴더에 있습니다" 라고 글로만 알려 드리면 원장님은 그 폴더를 못 찾으신다.
 * 프로그램이 원장님 컴퓨터에서 도는 것이므로, 그 컴퓨터의 탐색기를 열어 드릴 수 있다.
 *
 * 여는 자리는 **정해진 한 곳뿐**이다 — 화면에서 경로를 받지 않는다.
 * 받는 순간 아무 폴더나 열 수 있는 길이 된다.
 *
 * 창이 안 뜨는 자리(서버에 올려 쓰시는 경우)도 있다. 그때를 위해 실제 경로를
 * 늘 함께 돌려주고, 화면에서 그것을 보여 드린다.
 */
export async function POST() {
  return guard(async () => {
    const folder = path.join(process.cwd(), BACKUP_DIR)
    await mkdir(folder, { recursive: true })

    const opener =
      process.platform === 'win32'
        ? { cmd: 'explorer.exe', args: [folder] }
        : process.platform === 'darwin'
          ? { cmd: 'open', args: [folder] }
          : { cmd: 'xdg-open', args: [folder] }

    try {
      const child = spawn(opener.cmd, opener.args, { detached: true, stdio: 'ignore' })
      // 못 여는 컴퓨터에서 오류가 프로그램을 흔들지 않게 받아만 둔다
      child.on('error', () => {})
      child.unref()
      return ok({ opened: true, folder })
    } catch {
      return ok({ opened: false, folder })
    }
  })
}
