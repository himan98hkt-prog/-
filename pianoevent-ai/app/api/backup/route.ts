import { mkdir, readFile, readdir, rm, stat, writeFile } from 'node:fs/promises'
import { backupRoot } from '@/lib/paths'
import path from 'node:path'
import { BACKUP_DIR, backupDay, pruneDays, safeFileName, sortDays, uniqueName, type BackupDay } from '@/lib/events/backup'
import { buildBundle } from '@/lib/events/transfer'
import { guard, ok } from '@/lib/http'
import { currentAcademyId } from '@/lib/session'
import { getRepository } from '@/lib/store'

export const dynamic = 'force-dynamic'

function root(): string {
  return backupRoot(BACKUP_DIR)
}

/**
 * 오늘 몫을 뜬다.
 *
 * 원장님 컴퓨터 안에서만 움직인다 — 프로그램 폴더 아래 `백업/날짜/` 다.
 * 인터넷으로 나가는 것은 하나도 없다.
 */
export async function POST() {
  return guard(async () => {
    const repo = getRepository()
    const academy = await repo.ensureAcademy(currentAcademyId())
    const events = await repo.listEvents(academy.id)

    const day = backupDay()
    const dir = path.join(root(), day)
    await mkdir(dir, { recursive: true })

    const taken = new Set<string>()
    let saved = 0
    for (const event of events) {
      const students = await repo.listStudents(event.id)
      // 빈 행사는 뜨지 않는다 — 되살릴 것이 없는 파일만 쌓인다
      if (students.length === 0) continue
      const bundle = buildBundle({
        academyName: academy.name,
        event,
        students,
        assets: academy.assets ?? [],
      })
      const name = uniqueName(safeFileName(event.title), taken)
      taken.add(name)
      await writeFile(path.join(dir, `${name}.json`), JSON.stringify(bundle, null, 2), 'utf8')
      saved += 1
    }

    // 열네 날치만 남긴다
    let removed = 0
    try {
      const days = (await readdir(root(), { withFileTypes: true })).filter((d) => d.isDirectory()).map((d) => d.name)
      for (const old of pruneDays(days)) {
        await rm(path.join(root(), old), { recursive: true, force: true })
        removed += 1
      }
    } catch {
      /* 폴더를 못 읽어도 오늘 몫은 이미 떴다 */
    }

    return ok({ day, saved, removed, folder: path.join(BACKUP_DIR, day) })
  })
}

/** 지금까지 떠 둔 것 — 설정 화면에서 보여 드린다 */
export async function GET() {
  return guard(async () => {
    let days: BackupDay[] = []
    try {
      const dirs = (await readdir(root(), { withFileTypes: true })).filter((d) => d.isDirectory())
      days = await Promise.all(
        dirs.map(async (dir) => {
          const files = (await readdir(path.join(root(), dir.name))).filter((f) => f.endsWith('.json'))
          return {
            day: dir.name,
            files: await Promise.all(
              files.map(async (name) => ({
                name: name.replace(/\.json$/, ''),
                bytes: (await stat(path.join(root(), dir.name, name))).size,
              })),
            ),
          }
        }),
      )
    } catch {
      /* 아직 한 번도 안 떴다 */
    }
    return ok({ days: sortDays(days.filter((d) => d.files.length > 0)), folder: BACKUP_DIR })
  })
}

/** 되살릴 파일 한 개의 내용 — 화면이 이것을 가져오기 길로 넘긴다 */
export async function PUT(req: Request) {
  return guard(async () => {
    const url = new URL(req.url)
    const day = url.searchParams.get('day') ?? ''
    const name = url.searchParams.get('name') ?? ''
    // 폴더를 거슬러 올라가는 이름은 받지 않는다
    if (!/^\d{4}-\d{2}-\d{2}$/.test(day) || !name || /[\\/]|\.\./.test(name)) {
      return ok({ error: '그런 백업이 없습니다.' }, 400)
    }
    const text = await readFile(path.join(root(), day, `${name}.json`), 'utf8')
    return ok({ text })
  })
}
