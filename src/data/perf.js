// 렌더/조회 성능 측정 — 개발지시서 기준(모든 화면 1초 내)을 앱 안에서 바로 검증한다.

import { db } from './db.js'
import * as repo from './repo.js'
import { toYmd, toMonth, addMonths, monthRange, lastNWeeks } from '../core/date.js'
import { summarize } from '../core/attendance.js'
import { detectRisk } from '../core/risk.js'

const now = () => performance.now()

export async function measure() {
  const results = []
  const month = toMonth(toYmd())
  const today = toYmd()

  await time(results, '데이터 로드(init)', async () => { await repo.init() })

  await time(results, '원생 검색(1회, 이름 부분일치)', async () => {
    repo.searchStudents('김', { status: '재원' })
  })

  await time(results, '원생 검색 100회 연속', async () => {
    for (let i = 0; i < 100; i++) repo.searchStudents(String(i % 10), { status: '재원' })
  })

  const cls = repo.cache.classes[0]
  if (cls) {
    await time(results, '출결 보드(반 1개 · 하루)', async () => {
      await repo.attendanceOfClassDate(cls.id, today)
    })
    await time(results, '출결 조회(반 1개 · 한 달)', async () => {
      summarize(await repo.attendanceOfClassMonth(cls.id, month))
    })
  }

  await time(results, '수납 현황(한 달 전체)', async () => {
    await repo.paymentsOfMonth(month)
  })

  await time(results, '현황 통계 6개월(집계 캐시)', async () => {
    await repo.statsRange(Array.from({ length: 6 }, (_, i) => addMonths(month, -i)))
  })

  await time(results, '월 집계 재계산 1회', async () => {
    await repo.recomputeMonth(month)
  })

  await time(results, '이탈 위험 감지(최근 4주)', async () => {
    const { from, to } = lastNWeeks(today, 4)
    const [att, pays, counsel] = await Promise.all([
      repo.attendanceOfRange(from, to),
      repo.paymentsOfMonth(month),
      repo.counselRecent(500)
    ])
    detectRisk({ students: repo.cache.students, attendance: att, payments: pays, counselLogs: counsel, today })
  })

  const counts = {
    students: await db.students.count(),
    classes: await db.classes.count(),
    attendance: await db.attendance.count(),
    payments: await db.payments.count()
  }
  results.push({ name: `데이터 규모: 원생 ${counts.students} / 반 ${counts.classes} / 출결 ${counts.attendance.toLocaleString('en-US')} / 수납 ${counts.payments}`, ms: 0 })
  return results
}

async function time(results, name, fn) {
  const t0 = now()
  await fn()
  results.push({ name, ms: Math.round(now() - t0) })
}
