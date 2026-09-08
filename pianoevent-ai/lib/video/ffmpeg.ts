import { spawnSync } from 'node:child_process'

/**
 * 이 컴퓨터에 ffmpeg 이 있으면 토막을 몇 초 만에 잇는다.
 *
 * 브라우저 안에서 잇는 방법은 토막을 차례로 틀며 다시 담는 것뿐이라 실제 시간만큼 걸린다.
 * 8분짜리면 8분이다. 그런데 원장님 컴퓨터에 ffmpeg 이 이미 있는 경우가 꽤 있고
 * (곰녹음기·다음팟 같은 것들이 함께 깔아 둔다), 있으면 같은 일이 몇 초에 끝난다.
 *
 * **원장님께 묻지 않는다.** 있으면 쓰고 없으면 하던 대로 한다 —
 * "ffmpeg 을 설치하시겠습니까" 는 컴맹 원장님께 물어서는 안 되는 질문이다.
 * 화면에는 결과만 알려 준다: "빠르게 이었습니다" 또는 "다시 담는 중입니다".
 */

let cached: string | null | undefined

/** ffmpeg 이 어디 있는가. 없으면 null. 한 번만 찾아보고 기억한다 */
export function findFfmpeg(): string | null {
  if (cached !== undefined) return cached
  for (const name of ['ffmpeg', '/usr/bin/ffmpeg', '/usr/local/bin/ffmpeg', '/opt/homebrew/bin/ffmpeg']) {
    try {
      const probe = spawnSync(name, ['-version'], { encoding: 'utf8', timeout: 4000 })
      if (probe.status === 0) {
        cached = name
        return cached
      }
    } catch {
      /* 다음 자리를 본다 */
    }
  }
  cached = null
  return cached
}

/** 검사에서 다시 찾아보게 할 때 */
export function forgetFfmpeg(): void {
  cached = undefined
}

/**
 * concat 목록 파일의 내용.
 * 파일 이름에 작은따옴표가 들어가면 목록이 깨지므로 ffmpeg 규칙대로 겹쳐 쓴다.
 */
export function concatList(paths: string[]): string {
  return paths.map((row) => `file '${row.replace(/'/g, "'\\''")}'`).join('\n') + '\n'
}

/**
 * 토막을 이어 하나로.
 *
 * 먼저 **다시 인코딩하지 않고**(-c copy) 붙여 본다 — 우리가 만든 토막은 같은 규격이라
 * 대개 이쪽이 되고, 몇 초면 끝난다. 안 되면 한 번 다시 인코딩한다(그래도 실시간보다 빠르다).
 */
export function joinWithFfmpeg(
  bin: string,
  listPath: string,
  outPath: string,
): { ok: boolean; reencoded: boolean; error?: string } {
  const base = ['-hide_banner', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', listPath]
  const fast = spawnSync(bin, [...base, '-c', 'copy', outPath], { encoding: 'utf8', timeout: 10 * 60_000 })
  if (fast.status === 0) return { ok: true, reencoded: false }

  const again = spawnSync(
    bin,
    [...base, '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-c:a', 'aac', outPath],
    { encoding: 'utf8', timeout: 20 * 60_000 },
  )
  if (again.status === 0) return { ok: true, reencoded: true }
  return { ok: false, reencoded: false, error: (again.stderr || fast.stderr || '').trim().slice(0, 200) }
}
