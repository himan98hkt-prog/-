// 백업 복원 — 화면과 검증 스크립트가 같은 경로를 쓰도록 한 곳에 모은다.
//
// 복원은 자료를 통째로 바꾸지만 "이 기기의 인증" 은 건드리지 않는다.
// (백업 파일에는 인증키가 없고, 복원했다고 원장이 다시 키를 넣어야 한다면 사고에 가깝다)

import { db } from './db.js'
import { BACKUP_TABLES, DEVICE_ONLY_SETTINGS } from '../core/backup.js'

export async function restoreFromBackup(backup) {
  const keep = (await db.settings.bulkGet(DEVICE_ONLY_SETTINGS)).filter(Boolean)
  const counts = {}
  await db.transaction('rw', db.tables, async () => {
    for (const t of BACKUP_TABLES) {
      if (!db[t]) continue
      await db[t].clear()
      const rows = backup.data?.[t] || []
      if (rows.length) await db[t].bulkPut(rows)
      counts[t] = rows.length
    }
    if (keep.length) await db.settings.bulkPut(keep)
  })
  return counts
}
