#!/usr/bin/env node
/**
 * 실제로 서버를 띄우고 원장의 작업 흐름을 그대로 밟아 보는 스모크 테스트.
 *
 *   npm run build && npm run smoke
 *
 * 데모 저장소(.data/store.json)를 임시 디렉터리로 옮겨 두고 돌리므로
 * 실제 작업 데이터를 건드리지 않는다.
 */
import { spawn } from 'node:child_process'
import { existsSync, mkdtempSync, renameSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const PORT = Number(process.env.SMOKE_PORT ?? 3987)
const BASE = `http://127.0.0.1:${PORT}`
const DATA = join(process.cwd(), '.data')
const BACKUP = join(mkdtempSync(join(tmpdir(), 'pianoevent-smoke-')), 'data')

let passed = 0
const failures = []

function check(name, condition, detail = '') {
  if (condition) {
    passed += 1
    console.log(`  ✓ ${name}`)
  } else {
    failures.push(`${name}${detail ? ` — ${detail}` : ''}`)
    console.log(`  ✗ ${name}${detail ? ` — ${detail}` : ''}`)
  }
}

const cookies = new Map()

async function call(path, init = {}) {
  const headers = new Headers(init.headers ?? {})
  if (cookies.size > 0) {
    headers.set('Cookie', [...cookies].map(([k, v]) => `${k}=${v}`).join('; '))
  }
  const res = await fetch(`${BASE}${path}`, { ...init, headers, redirect: 'manual' })
  for (const raw of res.headers.getSetCookie?.() ?? []) {
    const [pair] = raw.split(';')
    const index = pair.indexOf('=')
    if (index > 0) cookies.set(pair.slice(0, index), pair.slice(index + 1))
  }
  return res
}

const json = (path, body, method = 'POST') =>
  call(path, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })

async function waitForServer(timeoutMs = 60_000) {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    try {
      const res = await fetch(`${BASE}/`, { redirect: 'manual' })
      if (res.status < 500) return true
    } catch {
      // 아직 뜨지 않음
    }
    await new Promise((resolve) => setTimeout(resolve, 400))
  }
  return false
}

const ROSTER = [
  '이름\t연주곡\t작곡가\t소요시간\t난이도\t비고',
  '김서연\t엘리제를 위하여\t베토벤\t3:30\t중급\t세 번째 무대입니다',
  '박지호\t즐거운 나의 집\t비숍\t1:10\t초급\t',
  '이하윤\t소녀의 기도\t바다르체프스카\t4:20\t중급\t',
  '최은우\t작은 별 변주곡\t모차르트\t2:30\t초급\t',
  '윤채원\t녹턴 op.9 no.2\t쇼팽\t4:45\t고급\t콩쿠르를 준비했습니다',
  '임가온\t젓가락 행진곡\t전래\t2:00\t듀엣\t동생과 함께',
].join('\n')

async function run() {
  console.log('\n▸ 원장 작업 흐름')

  const created = await json('/api/events', {
    title: '스모크 정기 연주회',
    type: 'recital',
    event_at: new Date(Date.now() + 7 * 864e5).toISOString(),
    venue: '스모크 홀',
    greeting: '한 해의 연습을 들려드립니다.',
  })
  const { event } = await created.json()
  check('행사 생성', created.status === 201 && Boolean(event?.id), `status=${created.status}`)

  const imported = await json(`/api/events/${event.id}/students`, { text: ROSTER })
  const importedBody = await imported.json()
  check('엑셀 붙여넣기로 명단 등록', imported.status === 201 && importedBody.students?.length === 6,
    `${importedBody.students?.length}명`)
  check('소요시간 표기 파싱', importedBody.students?.[0]?.duration_sec === 210)

  const generated = await json(`/api/events/${event.id}/program`, {})
  const program = await generated.json()
  check('순서표 생성', generated.ok && program.plan?.items?.length === 6, program.error ?? '')
  check('오프닝·피날레 배치', program.plan?.items?.[0]?.stage === 'opening' &&
    program.plan?.items?.at(-1)?.stage === 'finale')
  check('러닝타임 계산', program.plan?.total_sec > program.plan?.play_sec)
  check('사회자 대본 전원 생성',
    Object.keys(program.script?.byStudentId ?? {}).length === 6 && Boolean(program.script?.opening))
  check(`생성 경로 = ${program.source}`, program.source === 'ai' || program.source === 'rule')

  const reloaded = await (await call(`/api/events/${event.id}/students`)).json()
  check('순서와 멘트가 저장됨',
    reloaded.students?.every((s) => s.order_no !== null && s.mc_script) === true)

  const printPage = await call(`/events/${event.id}/program/print`)
  const printHtml = await printPage.text()
  check('인쇄용 순서표 렌더', printPage.ok && printHtml.includes('스모크 정기 연주회'))

  const scriptPage = await call(`/events/${event.id}/script`)
  check('사회자 대본 페이지 렌더', scriptPage.ok && (await scriptPage.text()).includes('사회자 대본'))

  console.log('\n▸ 인쇄물 디자인')

  const studio = await call(`/events/${event.id}/design`)
  check('디자인 스튜디오 렌더', studio.ok && (await studio.text()).includes('인쇄물 디자인'))

  const savedDesign = await json(
    `/api/events/${event.id}`,
    { design_theme: 'blush-romance', design_template: 'program-cover', design_copy: { subtitle: '봄 정기 연주회' } },
    'PATCH',
  )
  const savedBody = await savedDesign.json()
  check('양식·테마·문구 저장', savedDesign.ok && savedBody.event?.design_theme === 'blush-romance', savedBody.error ?? '')
  check('문구는 허용된 키만 저장', savedBody.event?.design_copy?.subtitle === '봄 정기 연주회')

  const badTheme = await json(`/api/events/${event.id}`, { design_theme: '없는테마' }, 'PATCH')
  check('없는 테마는 저장하지 않음', badTheme.status === 400)

  const poster = await call(`/events/${event.id}/design/print?template=poster-classic&theme=classic-navy`)
  const posterHtml = await poster.text()
  check('포스터 인쇄면 렌더', poster.ok && posterHtml.includes('스모크 정기 연주회'))
  check('포스터에 연주자 이름 노출', posterHtml.includes('김서연'))
  check('포스터에 학원 로고가 들어감', posterHtml.includes('data:image/svg+xml'))
  check('인쇄물에는 빈 로고 자리를 찍지 않음', !posterHtml.includes('로고 자리'))

  const photoPoster = await call(`/events/${event.id}/design/print?template=poster-photo&theme=modern-mono`)
  const photoHtml = await photoPoster.text()
  check('사진 포스터 렌더', photoPoster.ok && photoHtml.includes('스모크 정기 연주회'))
  check('학원 대표 사진이 인쇄물에 들어감', photoHtml.includes('data:image/svg+xml'))

  const badPhoto = await json(`/api/events/${event.id}`, { photo_url: 'javascript:alert(1)' }, 'PATCH')
  check('사진 주소는 http(s)·data 이미지만 허용', badPhoto.status === 400)

  const certificate = await call(`/events/${event.id}/design/print?template=certificate&theme=ivory-gold`)
  const certificateHtml = await certificate.text()
  check('참가 상장은 인원수만큼 렌더', certificate.ok && certificateHtml.includes('참 가 상'))
  check('상장에 곡명이 들어감', certificateHtml.includes('엘리제를 위하여'))

  const nametag = await call(`/events/${event.id}/design/print?template=nametag&theme=pastel-kids`)
  check('좌석 이름표 렌더', nametag.ok && (await nametag.text()).includes('좌석 이름표'))

  console.log('\n▸ 학부모 초대장')

  await json(`/api/events/${event.id}`, { status: 'published' }, 'PATCH')
  const invite = await fetch(`${BASE}/e/${event.id}`)
  const inviteHtml = await invite.text()
  check('공개 초대장 렌더(로그인 없이)', invite.ok && inviteHtml.includes('참석 여부'))
  check('초대장에 연주 순서 노출', inviteHtml.includes('김서연'))

  const rsvp = await json('/api/rsvp', {
    event_id: event.id,
    parent_name: '김보호',
    student_name: '김서연',
    attending: true,
    headcount: 3,
    message: '연습한 만큼만 하고 오렴',
  })
  check('참석 회신 저장', rsvp.status === 201, `status=${rsvp.status}`)

  const again = await json('/api/rsvp', {
    event_id: event.id,
    parent_name: '김보호',
    student_name: '김서연',
    attending: true,
    headcount: 2,
  })
  const againBody = await again.json()
  check('같은 학생 재회신은 이전 응답을 대체', againBody.replaced === true)

  const summaryRes = await (await call(`/api/events/${event.id}/rsvps`)).json()
  check('참석 집계', summaryRes.summary?.responses === 1 && summaryRes.summary?.headcount === 2,
    JSON.stringify(summaryRes.summary))

  const badRsvp = await json('/api/rsvp', { event_id: event.id, parent_name: '', student_name: '' })
  check('잘못된 회신 거부', badRsvp.status === 400)

  console.log('\n▸ 시즌 특강')

  const season = await json('/api/season', { theme: 'christmas', weeks: 4, target: '초등 저학년' })
  const seasonBody = await season.json()
  check('시즌 특강 팩 생성', season.ok && seasonBody.pack?.weeks?.length >= 1, seasonBody.error ?? '')
  check('활동지 포함', (seasonBody.pack?.worksheets?.length ?? 0) > 0)

  const seasonsPage = await call('/seasons')
  check('시즌 특강 화면 렌더', seasonsPage.ok && (await seasonsPage.text()).includes('시즌 특강'))

  console.log('\n▸ 무상태 API (개발 지시서 Step 2)')

  const stateless = await json('/api/generate-program', {
    eventTitle: '무상태 연주회',
    students: [
      { name: '가온', piece: '작은 별', level: '초급', duration: 90 },
      { name: '나윤', piece: '인벤션 1번', composer: '바흐', level: '중급', duration: 180 },
      { name: '다현', piece: '즉흥환상곡', composer: '쇼팽', level: '고급', duration: 300 },
    ],
  })
  const statelessBody = await stateless.json()
  check('무상태 순서표 생성', stateless.ok && statelessBody.program?.length === 3, statelessBody.error ?? '')
  check('멘트 동봉', Boolean(statelessBody.program?.[0]?.mc_script && statelessBody.openingScript))

  const noStudents = await json('/api/generate-program', { eventTitle: 'x', students: [] })
  check('빈 명단 거부', noStudents.status === 400)

  console.log('\n▸ 계정·데이터 삭제 (Google Play 요건)')

  const wrongConfirm = await json('/api/account/delete', { confirm: 'ㅇㅇ' })
  check('확인 문구가 틀리면 삭제하지 않음', wrongConfirm.status === 400)

  const deleted = await json('/api/account/delete', { confirm: '삭제' })
  check('계정·데이터 삭제', deleted.ok)

  const afterDelete = await call(`/api/events/${event.id}/students`)
  const afterBody = await afterDelete.json()
  check('삭제 후 학생 데이터가 남지 않음', (afterBody.students?.length ?? 0) === 0)
}

let server
try {
  if (existsSync(DATA)) renameSync(DATA, BACKUP)

  // next 바이너리를 직접 띄운다. npx 를 거치면 중간 프로세스가 남아 종료가 지저분해진다.
  server = spawn(process.execPath, [join('node_modules', 'next', 'dist', 'bin', 'next'), 'start', '-p', String(PORT)], {
    stdio: ['ignore', 'ignore', 'pipe'],
    detached: true,
    env: { ...process.env, NODE_ENV: 'production' },
  })
  server.stderr.on('data', (chunk) => {
    const line = String(chunk).trim()
    if (line) console.error(`  [server] ${line}`)
  })

  if (!(await waitForServer())) throw new Error(`서버가 ${BASE} 에서 뜨지 않았습니다.`)

  await run()
} catch (error) {
  failures.push(`실행 오류 — ${error instanceof Error ? error.message : String(error)}`)
} finally {
  if (server?.pid) {
    // 프로세스 그룹째 종료해 서버가 남지 않게 한다
    try {
      process.kill(-server.pid, 'SIGTERM')
    } catch {
      server.kill('SIGTERM')
    }
  }
  rmSync(DATA, { recursive: true, force: true })
  if (existsSync(BACKUP)) renameSync(BACKUP, DATA)
}

console.log(`\n${passed}건 통과 · ${failures.length}건 실패`)
if (failures.length > 0) {
  console.log(failures.map((f) => `  - ${f}`).join('\n'))
  process.exit(1)
}
