// 데모 데이터 & 성능 테스트용 더미 생성기.
// 대량 생성은 outbox 를 타지 않도록 Dexie 에 직접 bulkPut 한다(20만 건을 큐에 쌓을 이유가 없다).

import { db } from './db.js'
import { uid } from '../core/id.js'
import { addDays, addMonths, toYmd, pad2 } from '../core/date.js'
import { ATT, DEFAULT_REASON_TAGS } from '../core/attendance.js'
import { PRESETS } from '../core/customfields.js'
import { DEFAULT_TEMPLATES } from '../core/templates.js'
import { DEVICE_ONLY_SETTINGS } from '../core/backup.js'

const SURNAMES = '김이박최정강조윤장임한오서신권황안송류전홍고문양손배조백허유남심노정'.split('')
const GIVEN = ['서준', '민준', '서연', '지우', '하은', '도윤', '지호', '수아', '지안', '유진', '예린', '시우', '하준', '서윤', '주원', '채원', '지민', '건우', '다은', '윤서', '은우', '가온', '나윤', '태윤', '소율', '준서', '이준', '아린', '리원', '해준']
const SCHOOLS = ['한빛초', '중앙초', '해솔초', '푸른중', '남산중', '동백중', '서라벌고', '한들고']
const GRADES = ['초1', '초2', '초3', '초4', '초5', '초6', '중1', '중2', '중3', '고1']

function pick(arr, i) { return arr[i % arr.length] }
function randInt(n) { return Math.floor(Math.random() * n) }

export function koreanName(i) {
  return `${pick(SURNAMES, i * 7 + randInt(3))}${pick(GIVEN, i * 3 + randInt(5))}`
}

function phone(i) {
  return `010-${pad2(Math.floor(i / 100) % 100)}${pad2(i % 100)}-${String(1000 + (i * 37) % 9000)}`
}

// ── 계열별 데모 시나리오 (DoD 2번: custom 필드만 바꿔 다른 계열 운영) ──
export const DEMO_SCENARIOS = {
  english: {
    label: '영어학원 (아라 잉글리시)',
    academy: { name: '아라 잉글리시', brand_color: '#2c4a7c', phone: '02-000-0000' },
    customFields: PRESETS['어학'],
    subjects: [
      { name: 'Reading', color: '#2563eb' },
      { name: 'Speaking', color: '#0ea5e9' },
      { name: 'Grammar', color: '#7c3aed' }
    ],
    classNames: ['Starter A', 'Starter B', 'Basic A', 'Basic B', 'Inter A', 'Advanced'],
    fee: 180000,
    custom: (i) => ({
      level: ['Starter', 'Basic', 'Inter', 'Advanced'][i % 4],
      level_test: 60 + ((i * 7) % 40),
      book: `Reading Bridge ${1 + (i % 5)}`
    })
  },
  taekwondo: {
    label: '태권도장 (성무 태권도)',
    academy: { name: '성무 태권도', brand_color: '#a63a3a', phone: '02-000-0000' },
    customFields: PRESETS['체육'],
    subjects: [
      { name: '품새', color: '#dc2626' },
      { name: '겨루기', color: '#f59e0b' },
      { name: '체력', color: '#16a34a' }
    ],
    classNames: ['유아부', '초등 저학년', '초등 고학년', '중등부', '품새 선수반'],
    fee: 130000,
    custom: (i) => ({
      belt: ['흰띠', '노란띠', '파란띠', '빨간띠', '검은띠'][i % 5],
      promo_at: addDays(toYmd(), -(30 + (i % 200))),
      goal: ['1품 승급', '대회 출전', '체력 향상'][i % 3]
    })
  },
  piano: {
    label: '피아노학원 (아첼 음악)',
    academy: { name: '아첼 음악학원', brand_color: '#7a3b62', phone: '02-000-0000' },
    customFields: PRESETS['예체능'],
    subjects: [
      { name: '피아노', color: '#7c3aed' },
      { name: '이론', color: '#0891b2' }
    ],
    classNames: ['월수 4시', '월수 5시', '화목 4시', '화목 5시', '주말반'],
    fee: 150000,
    custom: (i) => ({
      piece: ['체르니 30-12', '소나티네 4번', '인벤션 1번', '아라베스크'][i % 4],
      book: ['하농', '체르니 30', '바이엘 하'][i % 3]
    })
  }
}

/** 시나리오 데모 데이터 (수십 명 규모) */
export async function seedDemo(key = 'english', { students = 40 } = {}) {
  const sc = DEMO_SCENARIOS[key]
  if (!sc) throw new Error(`알 수 없는 데모 시나리오: ${key}`)
  await clearAll()

  const teachers = ['원장', '김강사', '이강사'].map((name, i) => ({
    id: uid('u'), name, role: i === 0 ? 'owner' : 'teacher', pin: i === 0 ? '0000' : `111${i}`, updated_at: new Date().toISOString()
  }))
  const subjects = sc.subjects.map((s) => ({ id: uid('sub'), ...s, updated_at: new Date().toISOString() }))
  const classes = sc.classNames.map((name, i) => ({
    id: uid('c'),
    subject_id: subjects[i % subjects.length].id,
    name,
    teacher_id: teachers[1 + (i % 2)].id,
    schedule: [
      { dow: 1 + (i % 5), start: `${15 + (i % 4)}:00`, end: `${16 + (i % 4)}:00` },
      { dow: ((3 + i) % 5) + 1, start: `${15 + (i % 4)}:00`, end: `${16 + (i % 4)}:00` }
    ],
    capacity: 8 + (i % 5),
    room: `${1 + (i % 3)}실`,
    fee: sc.fee,
    status: '운영',
    updated_at: new Date().toISOString()
  }))

  const studentRows = []
  const enrollRows = []
  for (let i = 0; i < students; i++) {
    const id = uid('s')
    const parent = phone(Math.floor(i / 1.6)) // 일부러 겹치게 만들어 형제 묶기가 보이도록
    studentRows.push({
      id,
      name: koreanName(i),
      school: pick(SCHOOLS, i),
      grade: pick(GRADES, i),
      phone: phone(i + 500),
      parent_phone: parent,
      siblings_group: null,
      status: i % 17 === 0 ? '휴원' : '재원',
      joined_at: addDays(toYmd(), -(30 + i * 3)),
      memo: '',
      custom: sc.custom(i),
      updated_at: new Date().toISOString()
    })
    const cls = classes[i % classes.length]
    enrollRows.push({
      id: uid('e'), student_id: id, class_id: cls.id, started_at: addDays(toYmd(), -(20 + i)), ended_at: null, fee_override: null, updated_at: new Date().toISOString()
    })
  }

  const attendance = []
  const today = toYmd()
  for (const st of studentRows) {
    const en = enrollRows.find((e) => e.student_id === st.id)
    for (let d = 0; d < 40; d++) {
      const date = addDays(today, -d)
      if ([0, 6].includes(new Date(date).getDay())) continue
      if (d % 2) continue
      const r = Math.random()
      attendance.push({
        id: uid('a'),
        student_id: st.id,
        class_id: en.class_id,
        date,
        status: r < 0.08 ? ATT.ABSENT : r < 0.14 ? ATT.LATE : ATT.PRESENT,
        reason_tag: r < 0.08 ? pick(DEFAULT_REASON_TAGS, d) : null,
        checked_by: teachers[1].id,
        checked_at: `${date}T16:00:00.000Z`,
        updated_at: new Date().toISOString()
      })
    }
  }

  const payments = []
  const expenses = []
  for (let m = 0; m < 4; m++) {
    const month = addMonths(toYmd().slice(0, 7), -m)
    for (const st of studentRows) {
      if (st.status === '퇴원') continue
      const paidRoll = Math.random()
      payments.push({
        id: uid('p'),
        student_id: st.id,
        month,
        amount: sc.fee,
        method: '계좌이체',
        paid_at: paidRoll < 0.85 ? `${month}-05` : null,
        status: paidRoll < 0.85 ? '완납' : '미납',
        installments: [],
        updated_at: new Date().toISOString()
      })
    }
    expenses.push(
      { id: uid('x'), category: '임대료', amount: 1200000, memo: '', date: `${month}-05`, updated_at: new Date().toISOString() },
      { id: uid('x'), category: '인건비', amount: 2400000, memo: '', date: `${month}-10`, updated_at: new Date().toISOString() },
      { id: uid('x'), category: '교재', amount: 350000, memo: '', date: `${month}-15`, updated_at: new Date().toISOString() }
    )
  }

  const counsel = studentRows.slice(0, 12).map((st, i) => ({
    id: uid('cl'),
    student_id: st.id,
    type: i % 3 === 0 ? '입회상담' : i % 3 === 1 ? '전화' : '대면',
    stage: ['상담중', '체험', '등록', '보류'][i % 4],
    content: '학습 태도 및 진도 상담',
    next_action: i % 2 ? '2주 뒤 재상담' : '',
    created_by: teachers[0].id,
    created_at: `${addDays(toYmd(), -(i * 5))}T10:00:00.000Z`,
    updated_at: new Date().toISOString()
  }))

  await db.transaction('rw', [db.users, db.subjects, db.classes, db.students, db.enrollments, db.attendance, db.payments, db.expenses, db.counselLogs, db.settings], async () => {
    await db.users.bulkPut(teachers)
    await db.subjects.bulkPut(subjects)
    await db.classes.bulkPut(classes)
    await db.students.bulkPut(studentRows)
    await db.enrollments.bulkPut(enrollRows)
    await db.attendance.bulkPut(attendance)
    await db.payments.bulkPut(payments)
    await db.expenses.bulkPut(expenses)
    await db.counselLogs.bulkPut(counsel)
    await db.settings.bulkPut([
      { key: 'branding', value: { ...sc.academy, logo: null } },
      { key: 'customFields', value: sc.customFields },
      { key: 'templates', value: DEFAULT_TEMPLATES },
      { key: 'reasonTags', value: DEFAULT_REASON_TAGS },
      { key: 'demo', value: key },
      { key: 'wizardDone', value: true }
    ])
  })

  return { students: studentRows.length, classes: classes.length, attendance: attendance.length, payments: payments.length }
}

/**
 * 성능 테스트용 대량 더미. 기본값이 개발지시서 기준(원생 1,000 / 반 80 / 출결 20만).
 * onProgress(done, total) 로 진행률을 알린다.
 */
export async function seedBulk(opts = {}, onProgress = () => {}) {
  const {
    students = 1000,
    classes: classCount = 80,
    attendance: attCount = 200000,
    months = 12,
    chunk = 5000
  } = opts
  await clearAll()

  const now = new Date()
  const iso = now.toISOString()
  const teachers = Array.from({ length: 20 }, (_, i) => ({
    id: uid('u'), name: `강사${i + 1}`, role: i === 0 ? 'owner' : 'teacher', pin: String(1000 + i), updated_at: iso
  }))
  const subjects = ['수학', '영어', '국어', '과학', '미술', '태권도', '피아노', '코딩'].map((name, i) => ({
    id: uid('sub'), name, color: ['#2563eb', '#dc2626', '#16a34a', '#f59e0b', '#7c3aed', '#0891b2', '#db2777', '#65a30d'][i], updated_at: iso
  }))
  const classes = Array.from({ length: classCount }, (_, i) => ({
    id: uid('c'),
    subject_id: subjects[i % subjects.length].id,
    name: `${subjects[i % subjects.length].name} ${Math.floor(i / subjects.length) + 1}반`,
    teacher_id: teachers[i % teachers.length].id,
    schedule: [{ dow: (i % 5) + 1, start: `${14 + (i % 6)}:00`, end: `${15 + (i % 6)}:00` }],
    capacity: 12 + (i % 8),
    room: `${(i % 10) + 1}실`,
    fee: 120000 + (i % 6) * 20000,
    status: '운영',
    updated_at: iso
  }))

  const studentRows = []
  const enrollRows = []
  for (let i = 0; i < students; i++) {
    const id = uid('s')
    studentRows.push({
      id,
      name: koreanName(i),
      school: pick(SCHOOLS, i),
      grade: pick(GRADES, i),
      phone: phone(i + 3000),
      parent_phone: phone(Math.floor(i / 1.7)),
      siblings_group: null,
      status: i % 12 === 0 ? '휴원' : i % 31 === 0 ? '퇴원' : '재원',
      joined_at: addDays(toYmd(), -(i % 900)),
      memo: '',
      custom: { textbook: `교재 ${1 + (i % 12)}`, progress: `${1 + (i % 20)}단원` },
      updated_at: iso
    })
    const c1 = classes[i % classCount]
    const c2 = classes[(i * 7 + 3) % classCount]
    enrollRows.push({ id: uid('e'), student_id: id, class_id: c1.id, started_at: addDays(toYmd(), -400), ended_at: null, fee_override: null, updated_at: iso })
    if (i % 3 === 0) enrollRows.push({ id: uid('e'), student_id: id, class_id: c2.id, started_at: addDays(toYmd(), -300), ended_at: null, fee_override: null, updated_at: iso })
  }

  await db.transaction('rw', [db.users, db.subjects, db.classes, db.students, db.enrollments], async () => {
    await db.users.bulkPut(teachers)
    await db.subjects.bulkPut(subjects)
    await db.classes.bulkPut(classes)
    await db.students.bulkPut(studentRows)
    await db.enrollments.bulkPut(enrollRows)
  })

  // 출결: 최근 months 개월에 고르게 분포시킨다
  const dayCount = months * 30
  const statuses = [ATT.PRESENT, ATT.PRESENT, ATT.PRESENT, ATT.PRESENT, ATT.PRESENT, ATT.PRESENT, ATT.PRESENT, ATT.LATE, ATT.ABSENT, ATT.MAKEUP]
  let written = 0
  let buf = []
  for (let i = 0; i < attCount; i++) {
    const en = enrollRows[i % enrollRows.length]
    const date = addDays(toYmd(), -(i % dayCount))
    buf.push({
      id: uid('a'),
      student_id: en.student_id,
      class_id: en.class_id,
      date,
      status: statuses[i % statuses.length],
      reason_tag: i % 10 === 8 ? pick(DEFAULT_REASON_TAGS, i) : null,
      checked_by: teachers[i % teachers.length].id,
      checked_at: `${date}T16:00:00.000Z`,
      updated_at: iso
    })
    if (buf.length >= chunk) {
      await db.attendance.bulkPut(buf)
      written += buf.length
      buf = []
      onProgress(written, attCount)
    }
  }
  if (buf.length) {
    await db.attendance.bulkPut(buf)
    written += buf.length
    onProgress(written, attCount)
  }

  // 수납: months 개월치
  const payments = []
  for (let m = 0; m < months; m++) {
    const month = addMonths(toYmd().slice(0, 7), -m)
    for (const st of studentRows) {
      if (st.status === '퇴원') continue
      const paid = (st.id.charCodeAt(3) + m) % 10 < 9
      payments.push({
        id: uid('p'), student_id: st.id, month, amount: 150000, method: '계좌이체',
        paid_at: paid ? `${month}-05` : null, status: paid ? '완납' : '미납', installments: [], updated_at: iso
      })
    }
  }
  await db.payments.bulkPut(payments)

  const expenses = []
  for (let m = 0; m < months; m++) {
    const month = addMonths(toYmd().slice(0, 7), -m)
    expenses.push({ id: uid('x'), category: '임대료', amount: 3000000, memo: '', date: `${month}-05`, updated_at: iso })
    expenses.push({ id: uid('x'), category: '인건비', amount: 9000000, memo: '', date: `${month}-10`, updated_at: iso })
  }
  await db.expenses.bulkPut(expenses)

  await db.settings.bulkPut([
    { key: 'branding', value: { name: '대형 테스트 학원', brand_color: '#2563eb', logo: null } },
    { key: 'customFields', value: PRESETS['교과'] },
    { key: 'templates', value: DEFAULT_TEMPLATES },
    { key: 'reasonTags', value: DEFAULT_REASON_TAGS },
    { key: 'wizardDone', value: true },
    { key: 'perfSeed', value: { students, classes: classCount, attendance: attCount, months, at: iso } }
  ])

  return { students: studentRows.length, classes: classes.length, attendance: written, payments: payments.length }
}

/**
 * 전체 초기화. 인증키·설치 식별자는 이 기기의 것이라 기본적으로 남긴다
 * (데모 시드나 초기화를 했다고 해서 다시 인증을 받게 만들지 않는다).
 */
export async function clearAll({ keepDeviceSettings = true } = {}) {
  const keep = keepDeviceSettings
    ? (await db.settings.bulkGet(DEVICE_ONLY_SETTINGS)).filter(Boolean)
    : []
  await db.transaction('rw', db.tables, async () => {
    await Promise.all(db.tables.map((t) => t.clear()))
    if (keep.length) await db.settings.bulkPut(keep)
  })
}
