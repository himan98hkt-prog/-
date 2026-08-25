// CSV 입출력 — 엑셀에서 쓰던 명단을 그대로 가져오고, 세무·보고용으로 내보낸다.
//
// 엑셀(한국어 Windows)은 UTF-8 BOM 이 없으면 한글이 깨지므로 내보낼 때 BOM 을 붙인다.
// 가져오기는 CSV 파일뿐 아니라 "엑셀에서 복사한 탭 구분 붙여넣기" 도 그대로 받는다.

const HEADER_ALIASES = {
  name: ['이름', '성명', '학생명', '원생명', 'name'],
  phone: ['학생연락처', '학생전화', '본인연락처', '연락처', '전화번호', 'phone'],
  parent_phone: ['학부모연락처', '학부모전화', '보호자연락처', '학부모', 'parent_phone'],
  school: ['학교', 'school'],
  grade: ['학년', 'grade'],
  class: ['반', '반이름', '수업', 'class'],
  memo: ['메모', '비고', 'memo'],
  joined_at: ['등록일', '입회일', 'joined_at'],
  status: ['상태', 'status']
}

/** 한 줄을 따옴표 규칙(RFC4180)에 맞춰 자른다. 구분자는 쉼표 또는 탭. */
export function parseCsv(text, delimiter) {
  const src = String(text || '').replace(/\r\n?/g, '\n')
  const delim = delimiter || (src.split('\n')[0].includes('\t') ? '\t' : ',')
  const rows = []
  let row = []
  let cell = ''
  let quoted = false

  for (let i = 0; i < src.length; i++) {
    const ch = src[i]
    if (quoted) {
      if (ch === '"') {
        if (src[i + 1] === '"') { cell += '"'; i++ } else quoted = false
      } else cell += ch
      continue
    }
    if (ch === '"') { quoted = true; continue }
    if (ch === delim) { row.push(cell); cell = ''; continue }
    if (ch === '\n') { row.push(cell); rows.push(row); row = []; cell = ''; continue }
    cell += ch
  }
  if (cell !== '' || row.length) { row.push(cell); rows.push(row) }
  return rows.filter((r) => r.some((c) => String(c).trim() !== ''))
}

export function toCsv(headers, rows) {
  const esc = (v) => {
    const s = v === null || v === undefined ? '' : String(v)
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  return [headers.map(esc).join(','), ...rows.map((r) => r.map(esc).join(','))].join('\r\n')
}

export function downloadCsv(filename, headers, rows) {
  const blob = new Blob(['﻿' + toCsv(headers, rows)], { type: 'text/csv;charset=utf-8' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename
  a.click()
  setTimeout(() => URL.revokeObjectURL(a.href), 1000)
}

function normalizeHeader(h) {
  return String(h || '').replace(/\s|_/g, '').toLowerCase()
}

/** 헤더 줄을 보고 어느 칸이 무엇인지 추측한다. 못 찾으면 -1. */
export function mapHeaders(headerRow = []) {
  const map = {}
  const cells = headerRow.map(normalizeHeader)
  for (const [field, names] of Object.entries(HEADER_ALIASES)) {
    map[field] = cells.findIndex((c) => names.some((n) => normalizeHeader(n) === c))
  }
  return map
}

export function normalizePhone(v) {
  const d = String(v || '').replace(/[^0-9]/g, '')
  if (!d) return ''
  const t = d.startsWith('82') ? `0${d.slice(2)}` : d
  if (t.length === 11) return `${t.slice(0, 3)}-${t.slice(3, 7)}-${t.slice(7)}`
  if (t.length === 10) return `${t.slice(0, 3)}-${t.slice(3, 6)}-${t.slice(6)}`
  return t
}

/**
 * 원생 명단 텍스트 → 등록 후보 목록.
 * 헤더가 없으면 첫 칸을 이름으로 본다(엑셀에서 이름만 긁어오는 경우가 잦다).
 * @returns {{rows:Array, skipped:Array, hasHeader:boolean}}
 */
export function parseStudentTable(text, { existing = [] } = {}) {
  const table = parseCsv(text)
  if (!table.length) return { rows: [], skipped: [], hasHeader: false }

  const map = mapHeaders(table[0])
  const hasHeader = map.name >= 0 || Object.values(map).some((i) => i >= 0)
  const body = hasHeader ? table.slice(1) : table
  const idx = hasHeader ? map : { ...map, name: 0, phone: -1, parent_phone: -1 }

  const seen = new Set()
  const known = new Set(existing.map((s) => `${String(s.name).trim()}|${normalizePhone(s.parent_phone || s.phone)}`))
  const rows = []
  const skipped = []

  for (const cells of body) {
    const pick = (key) => (idx[key] >= 0 ? String(cells[idx[key]] ?? '').trim() : '')
    const name = pick('name')
    if (!name) { skipped.push({ cells, reason: '이름 없음' }); continue }
    const parent_phone = normalizePhone(pick('parent_phone'))
    const phone = normalizePhone(pick('phone'))
    const dupKey = `${name}|${parent_phone || phone}`
    if (seen.has(dupKey)) { skipped.push({ cells, reason: '파일 안 중복' }); continue }
    seen.add(dupKey)
    rows.push({
      name,
      phone,
      parent_phone,
      school: pick('school'),
      grade: pick('grade'),
      memo: pick('memo'),
      className: pick('class'),
      joined_at: pick('joined_at') || undefined,
      status: pick('status') || '재원',
      duplicate: known.has(dupKey)
    })
  }
  return { rows, skipped, hasHeader }
}
