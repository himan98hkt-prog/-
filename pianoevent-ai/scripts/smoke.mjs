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

  console.log('\n▸ 무대 화면 (연주회장 스크린)')

  const stagePage = await call(`/events/${event.id}/stage`)
  const stageHtml = await stagePage.text()
  check('무대 화면 렌더', stagePage.ok && stageHtml.includes('무대 화면'))
  check('16:9 슬라이드 크기 고정', stageHtml.includes('1280') && stageHtml.includes('720'))
  check('대기 화면에 행사 제목', stageHtml.includes('스모크 정기 연주회'))
  check('연주자가 슬라이드에 오름', stageHtml.includes('김서연') && stageHtml.includes('윤채원'))
  check('연주곡·작곡가 노출', stageHtml.includes('녹턴 op.9 no.2'))
  check('전체화면·PDF 안내', stageHtml.includes('전체화면') && stageHtml.includes('PDF로 저장'))
  check('인쇄용 슬라이드 묶음 포함', stageHtml.includes('stage-print-deck') && stageHtml.includes('stage-print-page'))
  check(
    '인쇄 용지가 16:9 로 지정됨',
    stageHtml.includes('size: 1280px 720px') || stageHtml.includes('size: 1280px 720px; margin: 0'),
  )

  const stageThemed = await call(`/events/${event.id}/stage?theme=blush-romance`)
  check('무대 화면도 테마를 따른다', stageThemed.ok && (await stageThemed.text()).includes('--d-accent'))
  check('무대 화면에서 테마를 바꿀 수 있음', stageHtml.includes('테마 바꾸기'))
  check('테마 100종을 쓴다고 안내', stageHtml.includes('테마 100종'))
  check('연주자 화면 모양을 고를 수 있음', stageHtml.includes('연주자 화면 모양'))
  check('무대 배경을 고를 수 있음', stageHtml.includes('무대 배경') && stageHtml.includes('건반'))

  check('화면에 넣을 것을 고를 수 있음', stageHtml.includes('곡 해설') && stageHtml.includes('오늘의 순서'))

  const pptx = await call(`/api/events/${event.id}/pptx?theme=ivory-gold`)
  const pptxBody = new Uint8Array(await pptx.arrayBuffer())
  check('파워포인트 파일 내려받기', pptx.ok, String(pptx.status))
  check(
    '파워포인트 형식으로 내려옴',
    (pptx.headers.get('content-type') ?? '').includes('presentationml.presentation'),
  )
  check('ZIP(=pptx) 로 시작한다', pptxBody[0] === 0x50 && pptxBody[1] === 0x4b)
  check('파일 이름이 붙어 있다', (pptx.headers.get('content-disposition') ?? '').includes('.pptx'))
  const pptxText = new TextDecoder('utf-8').decode(pptxBody)
  check('슬라이드에 학생 이름이 글자로 들어감', pptxText.includes('김서연'))
  check('슬라이드가 글상자다 (그림 아님)', pptxText.includes('txBox="1"'))
  check('고른 테마가 파일에 들어감', pptxText.includes('ppt/theme/theme1.xml'))

  console.log('\n▸ 아이 사진 · 감동영상')

  const photoPixel =
    'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
  const savedPhoto = await json('/api/academy/assets', { kind: 'photo', label: '아이 사진', url: photoPixel })
  const savedPhotoBody = await savedPhoto.json()
  check('아이 사진 보관함에 올리기', savedPhoto.status === 201, String(savedPhoto.status))

  const rosterNow = await (await call(`/api/events/${event.id}/students`)).json()
  const firstId = rosterNow.students?.[0]?.id
  const linked = await json(`/api/students/${firstId}`, { photo_asset_id: savedPhotoBody.asset?.id }, 'PATCH')
  const linkedBody = await linked.json()
  check('아이에게 사진 붙이기', linked.ok && linkedBody.student?.photo_asset_id === savedPhotoBody.asset?.id)

  const badPhotoId = await json(`/api/students/${firstId}`, { photo_asset_id: 'nope' }, 'PATCH')
  check('보관함에 없는 사진은 거절', badPhotoId.status === 400)

  const unlinked = await json(`/api/students/${firstId}`, { photo_asset_id: null }, 'PATCH')
  check('사진 빼기', unlinked.ok && (await unlinked.json()).student?.photo_asset_id === null)
  await json(`/api/students/${firstId}`, { photo_asset_id: savedPhotoBody.asset?.id }, 'PATCH')

  const stageWithPhoto = await call(`/events/${event.id}/stage`)
  check('무대 화면에 아이 사진이 실린다', (await stageWithPhoto.text()).includes(photoPixel.slice(0, 60)))

  const pptxWithPhoto = await call(`/api/events/${event.id}/pptx`)
  const pptxPhotoText = new TextDecoder('utf-8').decode(new Uint8Array(await pptxWithPhoto.arrayBuffer()))
  check('파워포인트 파일에 사진이 실제 그림으로 들어감', pptxPhotoText.includes('ppt/media/image1.png'))
  check('사진 확장자가 선언됨', pptxPhotoText.includes('<Default Extension="png"'))

  // 사진 창 모양·무대 배경이 파워포인트에도 그대로 (사진을 붙인 뒤라야 액자 모양이 나온다)
  const decorated = await call(`/api/events/${event.id}/pptx?layout=photo-frame&shape=hexagon&backdrop=keys`)
  const decoratedText = new TextDecoder('utf-8').decode(new Uint8Array(await decorated.arrayBuffer()))
  check('파워포인트에 사진 창 모양이 들어감', decoratedText.includes('prst="hexagon"'))
  check('파워포인트에 무대 배경이 들어감', decoratedText.includes('흰건반'))

  const videoPage = await call(`/events/${event.id}/video`)
  const videoHtml = await videoPage.text()
  check('감동영상 화면 렌더', videoPage.ok && videoHtml.includes('감동영상'))
  check('사진·동영상·음악을 고를 수 있음', videoHtml.includes('사진 고르기') && videoHtml.includes('음악 고르기'))
  check('걸리는 시간을 미리 알려 줌', videoHtml.includes('영상 길이만큼'))
  check('저장하지 않는다고 밝힘', videoHtml.includes('저장되지 않습니다'))

  const pptxBare = await call(`/api/events/${event.id}/pptx?agenda=0&sections=0&commentary=0`)
  const bareBody = new Uint8Array(await pptxBare.arrayBuffer())
  const bareText = new TextDecoder('utf-8').decode(bareBody)
  check('항목을 끄면 파일도 작아진다', bareBody.length < pptxBody.length, `${bareBody.length} < ${pptxBody.length}`)
  check('순서 화면을 끄면 파일에서도 빠진다', !bareText.includes('오늘의 순서'))
  check('꺼도 연주자는 그대로', bareText.includes('김서연'))

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

  const cueSheet = await call(`/events/${event.id}/design/print?template=cue-sheet&theme=daylight-studio`)
  const cueHtml = await cueSheet.text()
  check('당일 진행표 렌더', cueSheet.ok && cueHtml.includes('당일 진행표'))
  check('진행표에 리허설·시상이 들어감', cueHtml.includes('무대 리허설') && cueHtml.includes('시상'))

  const checklist = await call(`/events/${event.id}/design/print?template=checklist&theme=sunlit-ivory`)
  const checklistHtml = await checklist.text()
  check('준비 체크리스트 렌더', checklist.ok && checklistHtml.includes('준비 체크리스트'))
  check('체크리스트에 조율 예약이 들어감', checklistHtml.includes('조율 예약'))

  const pack = await call(`/events/${event.id}/design/print?pack=audience&theme=daylight-studio`)
  const packHtml = await pack.text()
  check('관객용 한 벌 인쇄', pack.ok && packHtml.includes('관객용 한 벌'))
  check('한 벌에 여러 양식이 함께 나옴', packHtml.includes('연주 순서') && packHtml.includes('ADMIT ONE'))

  console.log('\n▸ 확장 양식 · 원장 운영 계산')

  const notes = await call(`/events/${event.id}/design/print?template=program-notes&theme=vienna-hall`)
  const notesHtml = await notes.text()
  check('곡 해설 순서지 렌더', notes.ok && notesHtml.includes('엘리제를 위하여'))

  const trifold = await call(`/events/${event.id}/design/print?template=program-trifold&theme=royal-emerald`)
  check('3단 접지 프로그램 렌더', trifold.ok && (await trifold.text()).includes('관람 안내'))

  const story = await call(`/events/${event.id}/design/print?template=story-card&theme=cotton-candy`)
  const storyHtml = await story.text()
  check('SNS 세로 스토리 렌더', story.ok && storyHtml.includes('세로 스토리'))

  const banner = await call(`/events/${event.id}/design/print?template=banner-stand&theme=cherry-spring`)
  check('X배너 시안 렌더', banner.ok && (await banner.text()).includes('X배너 시안'))

  const invitationCard = await call(`/events/${event.id}/design/print?template=invitation-card&theme=antique-rose`)
  check('초대장 카드 2매 렌더', invitationCard.ok && (await invitationCard.text()).includes('참석 회신'))

  const backstage = await call(`/events/${event.id}/design/print?template=backstage-board&theme=summer-marine`)
  const backstageHtml = await backstage.text()
  check('대기 순서판 렌더', backstage.ok && backstageHtml.includes('대기 순서'))
  check('대기 순서판에 연주자 이름', backstageHtml.includes('김서연'))

  const award = await call(`/events/${event.id}/design/print?template=award-sheet&theme=graduation-day`)
  check('시상 명단 렌더', award.ok && (await award.text()).includes('시상 명단'))

  const mcSheet = await call(`/events/${event.id}/design/print?template=mc-script&theme=steinway-black`)
  const mcHtml = await mcSheet.text()
  check('사회자 대본 인쇄면 렌더', mcSheet.ok && mcHtml.includes('사회자 대본'))
  check('대본에 곡별 멘트가 들어감', mcHtml.includes('엘리제를 위하여'))

  const rehearsal = await call(`/events/${event.id}/design/print?template=rehearsal-sheet&theme=winter-snow`)
  const rehearsalHtml = await rehearsal.text()
  check('리허설 시간표 렌더', rehearsal.ok && rehearsalHtml.includes('리허설 시간표'))
  check('조별 소집이 계산됨', rehearsalHtml.includes('조 ·') && rehearsalHtml.includes('도착'))

  const budget = await call(`/events/${event.id}/design/print?template=budget-sheet&theme=newyear-red`)
  const budgetHtml = await budget.text()
  check('예산·정산표 렌더', budget.ok && budgetHtml.includes('권장 참가비'))
  check('예산표에 대관료가 들어감', budgetHtml.includes('대관료'))

  const parentNotice = await call(`/events/${event.id}/design/print?template=parent-notice&theme=peach-blossom`)
  check('학부모 안내문 렌더', parentNotice.ok && (await parentNotice.text()).includes('관람 안내'))

  const studentNotice = await call(`/events/${event.id}/design/print?template=student-notice&theme=milky-bear`)
  check('학생 준비 안내문 렌더', studentNotice.ok && (await studentNotice.text()).includes('연주회 준비물'))

  const noticePack = await call(`/events/${event.id}/design/print?pack=notice&theme=sunlit-ivory`)
  check('안내문 한 벌 인쇄', noticePack.ok && (await noticePack.text()).includes('안내문 한 벌'))

  // 학생이 많으면 문서가 한 장을 넘는다. 넘친 부분이 잘려 사라지면 안 된다.
  const bigRoster = Array.from({ length: 34 }, (_, i) => `학생${i + 1}\t연습곡 ${i + 1}\t체르니\t2:30\t중급`).join('\n')
  const bigCreated = await json('/api/events', {
    title: '대형 연주회 스모크',
    type: 'recital',
    event_at: '2026-11-14T15:00',
    venue: '아트홀',
  })
  const bigId = (await bigCreated.json())?.event?.id
  await json(`/api/events/${bigId}/students`, { text: bigRoster })
  await json(`/api/events/${bigId}/program`, {})
  const bigScript = await call(`/events/${bigId}/design/print?template=mc-script&theme=classic-navy`)
  const bigScriptHtml = await bigScript.text()
  check('34명 대본에서 마지막 연주자까지 나옴', bigScript.ok && bigScriptHtml.includes('학생34'))
  const bigProgram = await call(`/events/${bigId}/design/print?template=program-inner&theme=classic-navy`)
  check('34명 순서지에서 마지막 연주자까지 나옴', (await bigProgram.text()).includes('학생34'))

  console.log('\n▸ 곡 사전 · 순서 직접 조정')

  const catalogEvent = await json('/api/events', {
    title: '곡 사전 스모크',
    type: 'recital',
    event_at: '2027-05-16T15:00',
    venue: '연습실',
  })
  const catId = (await catalogEvent.json())?.event?.id
  // 이름과 곡만 있는 명단 — 나머지는 사전이 채워야 한다
  const bare = await json(`/api/events/${catId}/students`, {
    text: '김서연\t엘리제를 위하여\n박지호\t징글벨\n이하윤\t녹턴 op.9 no.2',
  })
  const bareRows = (await bare.json()).students ?? []
  check('곡만 적어도 작곡가가 채워짐', bareRows[0]?.composer === '베토벤', bareRows[0]?.composer ?? '(빈칸)')
  check('곡만 적어도 연주시간이 채워짐', bareRows[0]?.duration_sec === 210, String(bareRows[0]?.duration_sec))
  check('곡만 적어도 난이도가 채워짐', bareRows[0]?.level === 'intermediate', bareRows[0]?.level ?? '')

  await json(`/api/events/${catId}/program`, {})
  const beforeOrder = await call(`/api/events/${catId}/students`)
  const beforeRows = (await beforeOrder.json()).students ?? []
  const reversed = [...beforeRows].sort((a, b) => (b.order_no ?? 0) - (a.order_no ?? 0)).map((r) => r.id)
  const reordered = await json(`/api/events/${catId}/program`, { order: reversed }, 'PATCH')
  check('순서를 손으로 바꿔 저장', reordered.ok, (await reordered.clone().json()).error ?? '')
  const afterRows = (await (await call(`/api/events/${catId}/students`)).json()).students ?? []
  const afterOrder = [...afterRows].sort((a, b) => (a.order_no ?? 0) - (b.order_no ?? 0)).map((r) => r.id)
  check('바뀐 순서가 그대로 저장됨', afterOrder.join(',') === reversed.join(','))
  check('순서를 바꿔도 멘트가 남는다', afterRows.every((r) => (r.mc_script ?? '').length > 0))

  const partial = await json(`/api/events/${catId}/program`, { order: [reversed[0]] }, 'PATCH')
  const partialBody = await partial.json()
  check('빠뜨린 학생도 사라지지 않음', partialBody.order?.length === bareRows.length)

  const programTab = await call(`/events/${catId}?tab=program`)
  check('순서 직접 바꾸기 노출', (await programTab.text()).includes('순서 직접 바꾸기'))

  console.log('\n▸ 새 양식 8종 · 테마 100종')

  for (const [id, needle] of [
    ['stage-map', '무대 배치도'],
    ['banner-horizontal', '가로 현수막'],
    ['signage', '접 수 처'],
    ['practice-log', '연습 기록표'],
    ['performer-cards', '연주자'],
    ['guestbook', 'From.'],
    ['thanks-letter', '감 사 장'],
    ['after-notice', '마치며'],
  ]) {
    const res = await call(`/events/${event.id}/design/print?template=${id}&theme=classic-navy`)
    check(`${needle} 렌더`, res.ok && (await res.text()).includes(needle))
  }

  const venuePack = await call(`/events/${event.id}/design/print?pack=venue&theme=sunlit-ivory`)
  check('현장 안내 한 벌 인쇄', venuePack.ok && (await venuePack.text()).includes('현장 안내 한 벌'))

  // 새로 만든 테마도 실제로 인쇄면에 적용되는지
  for (const theme of ['onyx-pearl', 'plum-blossom', 'marshmallow', 'blueprint', 'rainbow-play']) {
    const res = await call(`/events/${event.id}/design/print?template=poster-classic&theme=${theme}`)
    check(`테마 ${theme} 적용`, res.ok && (await res.text()).includes('스모크 정기 연주회'))
  }

  const studioSearch = await call(`/events/${event.id}/design`)
  check('테마 찾기 상자 노출', (await studioSearch.text()).includes('테마 찾기'))

  console.log('\n▸ 이미지 보관함')

  const PNG = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
  const addLogo = await json('/api/academy/assets', { kind: 'logo', label: '스모크 로고', url: PNG })
  const addedLogo = await addLogo.json()
  check('보관함에 로고 추가', addLogo.status === 201 && Boolean(addedLogo.asset?.id), addedLogo.error ?? '')

  const beforeCount = addedLogo.academy?.assets?.length ?? 0
  const addPhoto = await json('/api/academy/assets', { kind: 'photo', label: '스모크 사진', url: PNG })
  const addedPhoto = await addPhoto.json()
  check(
    '보관함에 사진 추가',
    addPhoto.status === 201 && addedPhoto.academy?.assets?.length === beforeCount + 1,
    `${beforeCount} → ${addedPhoto.academy?.assets?.length}`,
  )

  const badAsset = await json('/api/academy/assets', { kind: 'photo', label: 'x', url: 'ftp://nope' })
  check('이미지가 아닌 주소는 거부', badAsset.status === 400)

  const mapped = await json(
    `/api/events/${event.id}`,
    { image_map: { logo: addedLogo.asset.id, poster: addedPhoto.asset.id } },
    'PATCH',
  )
  const mappedBody = await mapped.json()
  check('인쇄물 갈래별 이미지 지정 저장', mapped.ok && mappedBody.event?.image_map?.poster === addedPhoto.asset.id)

  const withImage = await call(`/events/${event.id}/design/print?template=poster-photo&theme=classic-navy`)
  check('지정한 사진이 인쇄물에 들어감', (await withImage.text()).includes('iVBORw0KGgo'))

  // image_map 은 통째로 갈아 끼운다. 없는 이미지는 걸러지고 나머지도 함께 지워진다
  const ghost = await json(`/api/events/${event.id}`, { image_map: { poster: 'no-such-asset' } }, 'PATCH')
  check('보관함에 없는 이미지는 저장하지 않음', (await ghost.json()).event?.image_map?.poster === undefined)

  const removed = await fetch(`${BASE}/api/academy/assets/${addedPhoto.asset.id}`, { method: 'DELETE' })
  check('보관함에서 이미지 삭제', removed.ok)

  console.log('\n▸ 지난 행사에서 명단 가져오기')

  const nextYear = await json('/api/events', {
    title: '제13회 정기 연주회',
    type: 'recital',
    event_at: '2027-09-16T15:00',
    venue: '구민회관',
  })
  const nextId = (await nextYear.json())?.event?.id
  const carried = await json(`/api/events/${nextId}/students/import`, { from_event_id: event.id })
  const carriedRows = await carried.json()
  check('지난 행사에서 명단 가져오기', carried.status === 201 && carriedRows.students?.length === 6,
    carriedRows.error ?? '')
  check('이름은 그대로 오고 곡은 비워진다',
    carriedRows.students?.[0]?.student_name?.length > 0 && carriedRows.students?.[0]?.piece_title === '')

  const withPieces = await json(`/api/events/${nextId}/students/import`, {
    from_event_id: event.id,
    keep_pieces: true,
  })
  check('곡까지 가져오기', (await withPieces.json()).students?.[0]?.piece_title?.length > 0)

  const selfImport = await json(`/api/events/${nextId}/students/import`, { from_event_id: nextId })
  check('같은 행사에서는 가져오지 않음', selfImport.status === 400)

  const rosterTab = await call(`/events/${nextId}?tab=roster`)
  check('명단 화면에 지난 행사 불러오기 노출', (await rosterTab.text()).includes('지난 행사에서 명단 가져오기'))

  const settings = await call('/settings')
  const settingsHtml = await settings.text()
  check('설정에 이미지 보관함 노출', settingsHtml.includes('이미지 보관함'))
  check('로고·사진 주소 입력칸은 사라짐', !settingsHtml.includes('로고 이미지 주소'))
  check('보관함에서 학원 기본으로 지정 가능', settingsHtml.includes('학원 기본으로 지정'))
  check('자가 진단 노출', settingsHtml.includes('이 컴퓨터에서 지금 되는 것'))
  check('AI 키 없이도 된다고 명시', settingsHtml.includes('AI 키 없이도 전부 만들어집니다'))
  check('인터넷 필요한 항목이 셋뿐임을 명시', settingsHtml.includes('이 셋뿐입니다'))

  const defaulted = await json('/api/academy', { logo_url: PNG }, 'PATCH')
  check('학원 기본 로고 지정', defaulted.ok && (await defaulted.json()).academy?.logo_url === PNG)

  const planTab = await call(`/events/${event.id}?tab=plan`)
  const planHtml = await planTab.text()
  check('리허설·예산·좌석 탭 렌더', planTab.ok && planHtml.includes('리허설 시간표'))
  check('순서표 점검 결과 노출', planHtml.includes('순서표 점검'))
  check('권장 참가비 계산 노출', planHtml.includes('권장 참가비'))

  const prep = await call(`/events/${event.id}?tab=prep`)
  const prepHtml = await prep.text()
  check('진행 준비 탭 렌더', prep.ok && prepHtml.includes('준비 체크리스트'))
  check('학부모 안내 문구 4종 노출', prepHtml.includes('첫 공지') && prepHtml.includes('끝나고 감사'))

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
