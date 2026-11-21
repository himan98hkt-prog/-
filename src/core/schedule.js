// 시간표 — 반의 schedule JSON: [{ dow:0~6(0=일), start:'15:00', end:'16:00' }]

import { hhmmToMin, WEEKDAYS } from './date.js'

export function slotsOf(cls) {
  const raw = cls?.schedule
  const list = Array.isArray(raw) ? raw : []
  return list
    .map((s) => ({
      dow: Number(s.dow),
      start: s.start,
      end: s.end,
      startMin: hhmmToMin(s.start),
      endMin: hhmmToMin(s.end)
    }))
    .filter((s) => Number.isInteger(s.dow) && s.endMin > s.startMin)
}

function overlaps(a, b) {
  return a.dow === b.dow && a.startMin < b.endMin && b.startMin < a.endMin
}

/**
 * 강의실·강사 중복 배정 경고.
 * @returns [{ type:'room'|'teacher', key, a:classId, b:classId, dow, label }]
 */
export function findConflicts(classes = []) {
  const entries = []
  for (const c of classes) {
    if (c.status === '종료') continue
    for (const s of slotsOf(c)) entries.push({ cls: c, slot: s })
  }
  const out = []
  for (let i = 0; i < entries.length; i++) {
    for (let j = i + 1; j < entries.length; j++) {
      const A = entries[i]
      const B = entries[j]
      if (A.cls.id === B.cls.id) continue
      if (!overlaps(A.slot, B.slot)) continue
      if (A.cls.room && B.cls.room && A.cls.room === B.cls.room) {
        out.push(conflict('room', A.cls.room, A, B))
      }
      if (A.cls.teacher_id && B.cls.teacher_id && A.cls.teacher_id === B.cls.teacher_id) {
        out.push(conflict('teacher', A.cls.teacher_id, A, B))
      }
    }
  }
  return out
}

function conflict(type, key, A, B) {
  return {
    type,
    key,
    a: A.cls.id,
    b: B.cls.id,
    aName: A.cls.name,
    bName: B.cls.name,
    dow: A.slot.dow,
    label: `${WEEKDAYS[A.slot.dow]} ${A.slot.start}~${A.slot.end} · ${type === 'room' ? '강의실' : '강사'} 중복: ${A.cls.name} / ${B.cls.name}`
  }
}

/** 주간 그리드 배치: dow -> [{cls, slot}] (시작 시간 순) */
export function weekGrid(classes = []) {
  const grid = new Map(WEEKDAYS.map((_, i) => [i, []]))
  for (const c of classes) {
    for (const slot of slotsOf(c)) grid.get(slot.dow).push({ cls: c, slot })
  }
  for (const [, list] of grid) list.sort((a, b) => a.slot.startMin - b.slot.startMin)
  return grid
}

/** 공석(추가 모집 가능) 계산 */
export function vacancyOf(cls, enrolledCount) {
  const cap = Number(cls?.capacity) || 0
  if (!cap) return { capacity: 0, enrolled: enrolledCount, open: null, full: false }
  return {
    capacity: cap,
    enrolled: enrolledCount,
    open: Math.max(0, cap - enrolledCount),
    full: enrolledCount >= cap
  }
}

/** 특정 날짜(요일)에 수업이 있는 반만 */
export function classesOnDow(classes = [], dow) {
  return classes.filter((c) => slotsOf(c).some((s) => s.dow === dow))
}
