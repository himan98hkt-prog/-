/**
 * **설치본 그대로** 감동영상을 뽑아 본다.
 *
 * 지금까지 영상 검사는 브라우저(Chromium)에 웹으로 띄워 놓고 했다. 그런데 원장님이
 * 쓰시는 것은 브라우저가 아니라 **설치해서 켜는 프로그램**이다. 껍데기(Electron)가
 * 다르면 쓸 수 있는 코덱도 달라지고, 그러면 **나오는 파일 종류가 달라진다.**
 * 웹에서 MP4 가 나왔다고 설치본에서도 MP4 가 나온다는 보장이 없다.
 *
 * 그래서 설치본과 **같은 묶음**(desktop/app)을 같은 껍데기로 띄워 놓고,
 * 사람이 하듯 [영상 만들기] 를 눌러 나온 파일을 열어 본다.
 *
 *   npm run desktop            # 설치본 본체를 먼저 만든다
 *   Xvfb :99 &                 # 창을 띄울 자리 (화면 없는 컴퓨터에서)
 *   DISPLAY=:99 npm run try:installed
 *
 * 여기서 도는 것은 **리눅스 껍데기**다. 윈도우·맥에서 쓸 수 있는 코덱은 다를 수 있으므로,
 * 「이 컴퓨터가 무엇을 쓸 수 있는가」를 먼저 찍어 두고 그 조건에서의 결과로 읽는다.
 */
import { spawnSync } from 'node:child_process'
import { existsSync, mkdtempSync, readFileSync, readdirSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { _electron as electron } from 'playwright'

const KIDS = join(process.cwd(), 'detail', 'kids')
const OUT = join(process.cwd(), 'promo', 'installed-video')
const EVENT_ID = 'demo-event'
const TMP = mkdtempSync(join(tmpdir(), 'recital-installed-'))
/** 개발용 비밀로 만든 인증키 — 파는 판은 다른 비밀로 서명되어 이 키가 안 열린다 */
const LICENSE_KEY = process.env.RECITAL_TEST_KEY ?? 'RM-20000-0003S-GQREE-4NJFK'

const say = (line) => console.log(line)
let bad = 0
const check = (label, ok, detail = '') => {
  say(`  ${ok ? '✓' : '✗'} ${label}${detail ? `  — ${detail}` : ''}`)
  if (!ok) bad += 1
}

if (!existsSync(join('desktop', 'app'))) {
  console.error('desktop/app 이 없습니다 — 먼저 `npm run desktop` 을 돌리세요.')
  process.exit(1)
}
rmSync(OUT, { recursive: true, force: true })
spawnSync('mkdir', ['-p', OUT])

say('설치본을 켭니다 (창 없는 화면에서)')
const app = await electron.launch({
  args: [
    join(process.cwd(), 'desktop', 'main.js'),
    `--user-data-dir=${join(TMP, 'userdata')}`,
    '--no-sandbox',
    '--disable-gpu',
  ],
  env: { ...process.env, DISPLAY: process.env.DISPLAY ?? ':99' },
})

// 껍데기가 하는 말을 그대로 받아 둔다 — 창이 안 뜨면 여기에 이유가 있다
const chatter = []
app.process().stdout?.on('data', (d) => chatter.push(`[out] ${String(d).trim()}`))
app.process().stderr?.on('data', (d) => chatter.push(`[err] ${String(d).trim()}`))

try {
  // 시작 화면이 먼저 뜨고, 그 뒤에 진짜 창이 뜬다 — 진짜 창을 기다린다
  let page = null
  const until = Date.now() + 90_000
  let seen = ''
  while (Date.now() < until) {
    for (const win of app.windows()) {
      const url = win.url()
      if (url !== seen) {
        seen = url
        say(`  · 창: ${url.slice(0, 70)}`)
      }
      if (/^http:\/\/(127\.0\.0\.1|localhost):/.test(url)) {
        page = win
        break
      }
    }
    if (page) break
    await new Promise((r) => setTimeout(r, 500))
  }
  if (!page) {
    say(chatter.slice(-25).join('\n'))
    throw new Error('프로그램 창이 뜨지 않았습니다.')
  }

  const base = new URL(page.url()).origin
  check('프로그램이 제 서버를 켜고 창을 띄웠다', true, base)
  await page.waitForLoadState('networkidle').catch(() => undefined)

  /*
   * 인증키를 넣는다 — 결제하신 원장님이 처음 하시는 그 일이다.
   *
   * 여기 쓰는 키는 **개발용 비밀로 만든 것**이다. 파실 설치본은 GitHub Secrets 의
   * 비밀로 서명되므로 이 키로는 안 열린다. 열고 난 뒤의 동작은 같다.
   */
  if (page.url().includes('/activate')) {
    say('  · 인증키 화면이 떴습니다 — 키를 넣습니다')
    await page.fill('#license-key', LICENSE_KEY)
    await page.fill('#license-academy', '하모니 피아노학원')
    await page.getByRole('button', { name: '시작하기' }).click()
    await page.waitForURL((u) => !u.pathname.includes('/activate'), { timeout: 30_000 })
    check('인증키를 받아 주고 안으로 들어갔다', true, page.url().replace(base, ''))
    await page.waitForLoadState('networkidle').catch(() => undefined)
  }

  /** 창 안에서 부르는 fetch — 설치본이 제 자신에게 말하는 것과 같은 길이다 */
  const api = (path, init) =>
    page.evaluate(
      async ([p, i]) => {
        const res = await fetch(p, i ? { ...i, headers: { 'Content-Type': 'application/json' } } : undefined)
        const text = await res.text()
        try {
          return { status: res.status, body: JSON.parse(text) }
        } catch {
          return { status: res.status, body: text.slice(0, 200) }
        }
      },
      [path, init],
    )

  // 연주회 한 건을 세운다
  await api(`/api/events/${EVENT_ID}/program`, { method: 'POST', body: '{}' })
  await api(`/api/events/${EVENT_ID}`, {
    method: 'PATCH',
    body: JSON.stringify({ status: 'published', design_theme: 'sunlit-ivory' }),
  })
  for (const reply of [
    { parent_name: '김○○', student_name: '김서연', headcount: 3, message: '연습한 만큼만 하고 오면 돼. 우리 딸 최고!' },
    { parent_name: '윤○○', student_name: '윤채원', headcount: 4, message: '일 년 동안 참 많이 늘었다.' },
  ]) {
    await api('/api/rsvp', { method: 'POST', body: JSON.stringify({ event_id: EVENT_ID, attending: true, ...reply }) })
  }

  const roster = (await api(`/api/events/${EVENT_ID}/students`)).body
  const students = roster.students ?? []
  check('명단이 들어갔다', students.length > 0, `${students.length}명`)

  // 아이마다 사진을 붙인다 — 사진이 없으면 이름만 지나가는 영상이 된다
  const files = existsSync(KIDS) ? readdirSync(KIDS).filter((f) => /\.(jpe?g|png)$/i.test(f)) : []
  let attached = 0
  for (const file of files) {
    const name = file.replace(/\.[^.]+$/, '')
    const student = students.find((s) => s.student_name === name)
    if (!student) continue
    const ext = file.toLowerCase().endsWith('.png') ? 'png' : 'jpeg'
    const url = `data:image/${ext};base64,${readFileSync(join(KIDS, file)).toString('base64')}`
    const made = await api('/api/academy/assets', {
      method: 'POST',
      body: JSON.stringify({ kind: 'photo', label: `${name} 연습`, url }),
    })
    if (made.body?.asset?.id) {
      await api(`/api/students/${student.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ photo_asset_id: made.body.asset.id }),
      })
      attached += 1
    }
  }
  check('아이 사진이 붙었다', attached >= 8, `${attached}명 분`)

  // 감동영상 화면으로
  await page.goto(`${base}/events/${EVENT_ID}/video`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(2500)
  const tip = page.getByTestId('first-run-close')
  if (await tip.count()) {
    await tip.click()
    await page.waitForTimeout(300)
  }

  // 이 껍데기가 무엇을 만들 수 있는가 — 웹과 다를 수 있는 바로 그 자리
  const able = await page.evaluate(async () => {
    const mr = ['video/mp4;codecs="avc1.42E01E,mp4a.40.2"', 'video/mp4;codecs=avc1', 'video/webm;codecs="vp9,opus"', 'video/webm', 'video/mp4']
      .filter((t) => MediaRecorder.isTypeSupported(t))
    const fast = []
    if (typeof VideoEncoder !== 'undefined') {
      for (const c of ['avc1.4D002A', 'avc1.42002A', 'vp09.00.10.08']) {
        try {
          const r = await VideoEncoder.isConfigSupported({ codec: c, width: 1280, height: 720, bitrate: 4_500_000, framerate: 30 })
          if (r.supported) fast.push(c)
        } catch { /* 다음 */ }
      }
    }
    const sound = []
    if (typeof AudioEncoder !== 'undefined') {
      for (const c of ['mp4a.40.2', 'opus']) {
        try {
          const r = await AudioEncoder.isConfigSupported({ codec: c, sampleRate: 48_000, numberOfChannels: 2, bitrate: 128_000 })
          if (r.supported) sound.push(c)
        } catch { /* 다음 */ }
      }
    }
    return { mr, fast, sound, secure: isSecureContext }
  })
  say(`\n  이 설치본이 쓸 수 있는 것`)
  say(`    예전 방식(MediaRecorder) : ${able.mr[0] ?? '없음'}`)
  say(`    빠른 길(WebCodecs)       : ${able.fast.join(', ') || '없음'}  · 소리 ${able.sound.join(', ') || '없음'}`)
  check('안전한 자리에서 돈다 (빠른 길을 쓰려면 필요하다)', able.secure)

  /**
   * 한 편 뽑아 본다 — 사람이 하듯 [영상 만들기] 를 누르고, 나온 파일을 열어 본다.
   */
  const makeOne = async (label, tag) => {
    const cost = (await page.getByTestId('record-cost').textContent().catch(() => '')) ?? ''
    const fastPath = cost.includes('빠르게')
    const lengthText = (await page.getByTestId('video-length').textContent()) ?? ''
    const total = Number(
      lengthText.match(/\/ (?:(\d+)분 )?(\d+)초/)?.slice(1).reduce((a, b) => Number(a || 0) * 60 + Number(b || 0), 0) ?? 40,
    )
    say(`\n■ ${label}`)
    say(`    화면이 하는 말 : ${cost.trim().replace(/\s+/g, ' ').slice(0, 56)}`)
    say(`    ${total}초짜리를 뽑습니다 (${fastPath ? '빠른 길' : '예전 방식'})`)

    const started = Date.now()
    await page.getByRole('button', { name: '영상 만들기' }).click()
    await page.waitForSelector('text=내려받기', { timeout: (total + 180) * 1000 })
    const took = (Date.now() - started) / 1000

    const made = await page.evaluate(async () => {
      const link = document.querySelector('a[download]')
      if (!link) return null
      const res = await fetch(link.href)
      const buf = new Uint8Array(await res.arrayBuffer())
      return { name: link.getAttribute('download'), bytes: Array.from(buf) }
    })
    if (!made) throw new Error('내려받을 파일이 안 나왔습니다.')

    const file = join(OUT, `${tag} ${made.name}`)
    writeFileSync(file, Buffer.from(made.bytes))
    const head = Buffer.from(made.bytes.slice(0, 12))
    const isMp4 = head.slice(4, 8).toString('latin1') === 'ftyp'
    const isWebm = head[0] === 0x1a && head[1] === 0x45 && head[2] === 0xdf && head[3] === 0xa3

    check('영상 파일이 나왔다', made.bytes.length > 20_000, `${Math.round(made.bytes.length / 1024)}KB · ${made.name}`)
    check('진짜 영상 파일이다 (MP4 또는 WebM)', isMp4 || isWebm, head.toString('hex'))
    check('확장자가 실제 형식과 맞는다', isMp4 ? made.name.endsWith('.mp4') : made.name.endsWith('.webm'))
    if (fastPath) {
      check('빠른 길이 영상 길이보다 빨리 끝났다', took < total, `${total}초짜리를 ${took.toFixed(1)}초에 (${(total / took).toFixed(1)}배)`)
    } else {
      say(`    · ${total}초짜리에 ${took.toFixed(1)}초 걸렸습니다`)
    }

    const ffprobe = spawnSync('which', ['ffprobe'], { encoding: 'utf8' }).stdout.trim()
    let streams = ''
    if (ffprobe) {
      const info = spawnSync(ffprobe, ['-v', 'error', '-show_entries', 'format=duration:stream=codec_type,codec_name', '-of', 'default=nw=1', file], { encoding: 'utf8' })
      streams = (info.stdout ?? '').replace(/\n/g, ' ')
      check('영상 도구가 읽어 낸다', info.status === 0, (info.stderr ?? '').trim().slice(0, 120))
      check('영상 트랙이 들어 있다', streams.includes('video'), streams.trim().slice(0, 90))
      const dur = Number(streams.match(/duration=([\d.]+)/)?.[1] ?? 0)
      check('길이가 짠 것과 맞는다', Math.abs(dur - total) <= Math.max(2, total * 0.15), `${dur.toFixed(1)}초 / 짠 것 ${total}초`)
      const ffmpeg = spawnSync('which', ['ffmpeg'], { encoding: 'utf8' }).stdout.trim()
      if (ffmpeg) {
        const still = join(OUT, `${tag}-아이.jpg`)
        spawnSync(ffmpeg, ['-y', '-v', 'error', '-ss', String(Math.max(2, Math.round(total * 0.45))), '-i', file, '-frames:v', '1', still], { encoding: 'utf8' })
        check('영상을 풀면 그림이 나온다', existsSync(still))
      }
    }
    return { fastPath, took, total, streams, isMp4 }
  }

  // ① 음악 없이 — 소리 인코더가 없어도 빠른 길로 갈 수 있어야 한다
  const plain = await makeOne('음악 없이', '01-음악없이')
  check('음악이 없으면 소리 트랙도 없다', !plain.streams.includes('audio'), plain.streams.trim().slice(0, 80))

  // ② 음악을 얹고 — 원장님 대부분이 하시는 그 상태
  const ffmpegBin = spawnSync('which', ['ffmpeg'], { encoding: 'utf8' }).stdout.trim()
  if (ffmpegBin) {
    const tune = join(TMP, 'tune.m4a')
    spawnSync(ffmpegBin, ['-y', '-v', 'error', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=120', '-c:a', 'aac', '-b:a', '128k', tune], { encoding: 'utf8' })
    await page.locator('input[type="file"][accept="audio/*"]').first().setInputFiles({
      name: 'tune.m4a',
      mimeType: 'audio/mp4',
      buffer: readFileSync(tune),
    })
    await page.waitForTimeout(2500)
    const withTune = await makeOne('음악을 얹고', '02-음악얹고')
    check('음악을 얹으면 소리 트랙이 들어간다', withTune.streams.includes('audio'), withTune.streams.trim().slice(0, 90))
  } else {
    say('\n  · ffmpeg 이 없어 음악 얹은 경우는 건너뜁니다')
  }

  say(`\n나온 것 → ${OUT}`)
} finally {
  await app.close().catch(() => undefined)
  rmSync(TMP, { recursive: true, force: true })
}

if (bad > 0) {
  console.error(`\n${bad}건 실패`)
  process.exitCode = 1
} else {
  console.log('\n설치본에서 감동영상이 나왔습니다.')
}
