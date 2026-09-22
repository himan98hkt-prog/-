// 피아노 반주(MR) 연동 — 연습 기록을 **되받는다**.
//
// 5단계에서 명단은 관리노트 → 반주 한 방향으로 갔다. 이건 반대 방향이다.
// 아이가 어떤 곡을 며칠에 몇 번, 몇 분이나 연습했는지가 반주 쪽에만 남아 있으면
// 학부모 리포트에는 출석률밖에 못 쓴다. "이번 달 집에서 12번, 3시간 40분"이
// 리포트에 찍히는 것이 이 기능의 전부다.
//
// **무엇이 넘어오는가.** 학생(가능하면 id)·곡·날짜·횟수·초·템포뿐이다. 반주 쪽에는
// 애초에 연락처가 없고(5단계), 이 파일에도 넣을 자리를 두지 않는다.
//
// **왜 기기 id 가 붙는가.** 같은 날 같은 곡을 학원에서도 치고 집에서도 치면 기록이
// 두 벌 생긴다. 기기를 구분하지 않으면 둘 중 하나가 사라지거나(덮어쓰기) 같은 파일을
// 두 번 넣었을 때 두 배가 된다(더하기). **학부모에게 나가는 숫자**라서 둘 다 안 된다.
// 기기별로 나눠 두면 기기 안에서는 덮어쓰고 기기끼리는 더해서, 두 번 넣어도 같은 값이
// 나온다. 기기 id 는 설치할 때 만든 무작위 문자열이고 사람을 가리키지 않는다.
//
// ─────────────────────────────────────────────────────────────────────────────
// **이 파일은 반주 플레이어에도 똑같이 들어간다.**
// `mr/server/static/player/js/practice-format.js` 는 이 파일의 **글자 그대로의 사본**이다.
// 플레이어는 정적 꾸러미로 따로 배포돼서 관리노트 소스를 불러올 수 없다.
//
// 형식을 한쪽에서만 고치면 원장님 쪽에서 파일이 안 읽힌다. 그래서 사본을 손으로
// 맞추지 않는다 — 고친 뒤 `npm run sync:shared` 를 돌리면 되고, 두 파일이 한 글자라도
// 다르면 `npm test` 가 실패한다.
// ─────────────────────────────────────────────────────────────────────────────

export const PRACTICE_FORMAT = 'academy-note-piano-practice'
export const PRACTICE_VERSION = 1

/** 기록 한 줄에 담기는 항목. 이 목록에 없는 건 버린다. */
export const PRACTICE_FIELDS = [
  'student_id', 'student', 'song_id', 'title', 'date', 'device',
  'count', 'seconds', 'bpm'
]

/** 절대 넘어오면 안 되는 항목 — 반주 쪽이 실수로 넣어도 여기서 막는다. */
export const NEVER_IMPORT = [
  'phone', 'parent_phone', 'memo', 'custom', 'discount',
  'school', 'grade', 'address', 'birth'
]

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/
const DAY_SECONDS = 24 * 60 * 60

class PracticeError extends Error {}

const int = (v, max) => {
  const n = Math.floor(Number(v))
  if (!Number.isFinite(n) || n < 0) return 0
  return max === undefined ? n : Math.min(n, max)
}

/**
 * 같은 연습을 가리키는 열쇠.
 *
 * 학생·곡·날짜·기기가 같으면 같은 연습이다. 파일을 두 번 넣어도 줄이 안 늘어나는
 * 근거가 이 열쇠다. id 를 모르는 기록은 이름으로 묶는다 — 이름이 갈리면 나중에
 * 사람이 붙여 줘야 하지만, 버리는 것보다 낫다.
 */
export function practiceKey(row) {
  const who = row.student_id ? `id:${row.student_id}` : `name:${String(row.student || '').trim()}`
  return `${who}::${row.song_id}::${row.date}::${row.device || '_'}`
}

/** 기록 한 줄을 받아들일 모양으로 줄인다. 이상하면 null (버린다). */
export function toPracticeEntry(row = {}) {
  const date = String(row.date || '')
  if (!DATE_RE.test(date)) return null
  const song_id = String(row.song_id || '').trim()
  if (!song_id) return null
  const student_id = String(row.student_id || '').trim()
  const student = String(row.student || '').trim()
  if (!student_id && !student) return null       // 누구 건지 모르는 기록은 쓸 데가 없다

  const count = int(row.count, 999)
  const seconds = int(row.seconds, DAY_SECONDS)  // 하루를 넘는 연습은 없다
  if (!count && !seconds) return null            // 아무것도 안 한 줄은 넣지 않는다

  const entry = { student_id, student, song_id, date, count, seconds }
  if (row.title) entry.title = String(row.title).slice(0, 120)
  if (row.device) entry.device = String(row.device).slice(0, 32)
  if (row.bpm) entry.bpm = int(row.bpm, 400)
  return entry
}

/**
 * 내보낼 기록 파일을 만든다.
 *
 * @param {object[]} rows
 * @param {object} meta  academy(학원명) · device(이 기기) · note
 */
export function buildPractice(rows = [], meta = {}) {
  const entries = rows.map(toPracticeEntry).filter(Boolean)
  entries.sort((a, b) => a.date.localeCompare(b.date) ||
    String(a.student || a.student_id).localeCompare(String(b.student || b.student_id), 'ko'))
  return {
    format: PRACTICE_FORMAT,
    version: PRACTICE_VERSION,
    academy: String(meta.academy || ''),
    device: String(meta.device || ''),
    exported_at: new Date().toISOString(),
    practice: entries
  }
}

/** 관리노트가 읽을 때 쓰는 검사 — 형식이 아니면 일찍 거절한다. */
export function parsePractice(text) {
  let json
  try {
    json = typeof text === 'string' ? JSON.parse(text) : text
  } catch (e) {
    throw new PracticeError('연습 기록 파일을 읽을 수 없습니다 (JSON 형식이 아닙니다)')
  }
  if (json?.format !== PRACTICE_FORMAT) {
    throw new PracticeError('피아노 반주 연습 기록 파일이 아닙니다')
  }
  if (Number(json.version) > PRACTICE_VERSION) {
    throw new PracticeError('더 최신 버전에서 만든 기록입니다. 관리노트를 업데이트해 주세요')
  }
  if (!Array.isArray(json.practice)) throw new PracticeError('기록이 비어 있습니다')

  const rows = []
  for (const raw of json.practice) {
    const entry = toPracticeEntry({ ...raw, device: raw.device || json.device })
    if (entry) rows.push(entry)
  }
  return {
    format: json.format,
    version: Number(json.version) || 1,
    academy: String(json.academy || ''),
    device: String(json.device || ''),
    exported_at: String(json.exported_at || ''),
    practice: rows
  }
}

/**
 * 들어온 기록을 이미 가진 기록에 합친다.
 *
 * **기기 안에서는 덮어쓰고, 기기끼리는 그냥 같이 둔다.** 한 기기가 보내는 값은
 * 그 날 그 곡의 **누적**이라 나중 것이 이긴다. 다른 기기 것은 다른 줄이므로 건드리지
 * 않는다. 그래서 같은 파일을 두 번 넣어도 합계가 그대로다.
 *
 * @returns {{rows: object[], added: number, updated: number, same: number}}
 */
export function mergePractice(existing = [], incoming = []) {
  const byKey = new Map()
  for (const row of existing) byKey.set(practiceKey(row), { ...row })

  let added = 0
  let updated = 0
  let same = 0
  for (const row of incoming) {
    const key = practiceKey(row)
    const old = byKey.get(key)
    if (!old) {
      byKey.set(key, { ...row })
      added++
    } else if (old.count === row.count && old.seconds === row.seconds) {
      same++
    } else {
      // 누적값이라 큰 쪽이 맞다. 거꾸로 온 파일(옛날 것)이 최신을 깎으면 안 된다.
      byKey.set(key, {
        ...old, ...row,
        count: Math.max(old.count, row.count),
        seconds: Math.max(old.seconds, row.seconds)
      })
      updated++
    }
  }
  return { rows: [...byKey.values()], added, updated, same }
}

/**
 * 기록을 학생 id 에 붙인다.
 *
 * 반주 쪽이 id 를 모르고 이름만 보냈을 때 쓴다. 이름이 정확히 하나만 맞을 때만
 * 붙인다 — **동명이인을 아무 데나 붙이면 남의 아이 연습이 우리 아이 리포트에
 * 찍힌다.** 못 붙인 것은 버리지 않고 돌려준다. 사람이 고르면 된다.
 *
 * @returns {{linked: object[], unmatched: object[]}}
 */
export function linkToStudents(rows = [], students = []) {
  const byName = new Map()
  for (const s of students) {
    const name = String(s.name || '').trim()
    if (!name) continue
    byName.set(name, byName.has(name) ? null : s.id)   // 겹치면 null = 못 고름
  }
  const known = new Set(students.map((s) => s.id))

  const linked = []
  const unmatched = []
  for (const row of rows) {
    if (row.student_id && known.has(row.student_id)) { linked.push(row); continue }
    const hit = byName.get(String(row.student || '').trim())
    if (hit) linked.push({ ...row, student_id: hit })
    else unmatched.push(row)
  }
  return { linked, unmatched }
}

/**
 * 리포트에 쓸 한 학생의 한 달 요약.
 *
 * @param {object[]} rows   그 학생 기록
 * @param {string} month    'YYYY-MM'
 */
export function summarize(rows = [], month = '') {
  const inMonth = month ? rows.filter((r) => r.date.startsWith(month)) : rows
  const days = new Set()
  const songs = new Map()
  let count = 0
  let seconds = 0
  for (const r of inMonth) {
    days.add(r.date)
    count += r.count
    seconds += r.seconds
    const key = r.title || r.song_id
    songs.set(key, (songs.get(key) || 0) + r.count)
  }
  return {
    days: days.size,
    count,
    seconds,
    minutes: Math.round(seconds / 60),
    songs: [...songs.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([title, n]) => ({ title, count: n }))
  }
}

/** "3시간 40분" — 리포트에 그대로 들어가는 글자. */
export function humanDuration(seconds = 0) {
  const total = Math.max(0, Math.round(seconds / 60))
  const h = Math.floor(total / 60)
  const m = total % 60
  if (!h) return `${m}분`
  return m ? `${h}시간 ${m}분` : `${h}시간`
}

/**
 * 오늘 날짜 'YYYY-MM-DD' — **그 기기가 있는 곳의 날짜**로.
 *
 * `toISOString()` 은 UTC 라서 한국에서 저녁 9시에 친 연습이 **다음 날**로 기록된다.
 * 학부모가 "어제 저녁에 쳤는데 왜 오늘로 돼 있냐"고 물으실 자리다.
 */
export function localDate(when = new Date()) {
  const p = (n) => String(n).padStart(2, '0')
  return `${when.getFullYear()}-${p(when.getMonth() + 1)}-${p(when.getDate())}`
}

/** 파일 이름 — 누구 것인지 보여야 원장님이 여러 개를 받아도 안 섞인다. */
export function practiceFilename(academy = '', who = '') {
  const day = new Date().toISOString().slice(0, 10)
  const clean = (s, fallback) =>
    String(s || '').replace(/[\\/:*?"<>|]/g, '').trim() || fallback
  const name = clean(academy, '학원')
  const whom = who ? `-${clean(who, '')}` : ''
  return `${name}${whom}-연습기록-${day}.json`
}
