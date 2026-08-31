/**
 * 연주회 매니저 — 설치해서 쓰는 프로그램의 겉껍데기.
 *
 * 지금까지 원장님이 받으신 것은 사실 개발 도구였다. 압축을 풀고, 검은 명령창을 띄우고,
 * `npm install` 이 2~4분 돌기를 기다린 뒤, 브라우저 주소창에 뜬 `localhost:3000` 을 보셨다.
 * 아무리 잘 만들어도 그 화면을 보시는 순간 "이건 내가 쓸 물건이 아니다" 가 된다.
 *
 * 여기서 하는 일은 셋뿐이다.
 *   1. 프로그램 안에 들어 있는 서버를 조용히 켠다 (설치도, 인터넷도 필요 없다)
 *   2. 주소창 없는 **제 창**으로 띄운다
 *   3. 학원 자료를 운영체제가 정해 준 **쓸 수 있는 자리**에 둔다
 *
 * 창을 닫으면 서버도 함께 내린다 — 원장님이 "껐는데 뭐가 남아 있나" 를 걱정하실 일이 없어야 한다.
 */
const { app, BrowserWindow, Menu, shell, dialog } = require('electron')
const { spawn } = require('node:child_process')
const { createServer } = require('node:net')
const path = require('node:path')
const fs = require('node:fs')
const { splashHtml } = require('./splash.js')
const BRAND = require('./brand.js')

/** 켜져 있는 서버 (창을 닫을 때 함께 내린다) */
let server = null
let win = null

/**
 * 프로그램 본체가 놓인 자리.
 *
 * 설치판에서는 이 파일이 `app.asar` 안에 들어가 있다. asar 는 여러 파일을 하나로 묶은
 * 것이라 그 안의 파일은 실행할 수 없으므로, 서버는 옆에 풀어 둔 `app.asar.unpacked` 에 있다.
 */
function appRoot() {
  if (!app.isPackaged) return path.join(__dirname, 'app')
  return path.join(__dirname.replace(`app.asar${path.sep}`, `app.asar.unpacked${path.sep}`), 'app')
}

/**
 * 학원 자료가 놓이는 자리.
 *
 * 설치 폴더(Program Files)는 윈도우가 쓰기를 막는다. 거기에 명단을 쓰려 들면 저장이
 * 통째로 실패하고, 원장님 눈에는 "넣었는데 없어졌다" 로 보인다. 운영체제가 정해 준
 * 사용자 자료 폴더를 쓴다 — 그래도 **이 컴퓨터 안**이라는 약속은 그대로다.
 */
function dataDir() {
  const dir = app.getPath('userData')
  fs.mkdirSync(dir, { recursive: true })
  return dir
}

/**
 * 껍데기가 기억해 두는 것 — 지금은 「태블릿에서 열기」 하나뿐이다.
 *
 * 학원 자료와 같은 폴더에 둔다. 프로그램을 다시 깔아도 설정이 남는다.
 */
function shellPrefs() {
  try {
    return JSON.parse(fs.readFileSync(path.join(dataDir(), 'shell.json'), 'utf8'))
  } catch {
    return {}
  }
}

function saveShellPrefs(next) {
  try {
    fs.writeFileSync(path.join(dataDir(), 'shell.json'), `${JSON.stringify(next, null, 2)}\n`, 'utf8')
  } catch {
    /* 못 적으면 이번 판에서만 안 켜질 뿐이다 */
  }
}

/** 인증키를 확인할 때 쓰는 비밀 (설치본을 뽑을 때 담긴다) */
function licenseSecret() {
  try {
    return fs.readFileSync(path.join(appRoot(), 'license-secret.txt'), 'utf8').trim()
  } catch {
    return ''
  }
}

/** 비어 있는 문(port) 하나 — 3000 이 다른 프로그램에 물려 있어도 켜져야 한다 */
function freePort() {
  return new Promise((resolve, reject) => {
    const probe = createServer()
    probe.unref()
    probe.on('error', reject)
    probe.listen(0, '127.0.0.1', () => {
      const { port } = probe.address()
      probe.close(() => resolve(port))
    })
  })
}

async function waitForServer(port, timeoutMs = 60_000) {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/`, { redirect: 'manual' })
      if (res.status < 500) return true
    } catch {
      /* 아직 켜지는 중 */
    }
    await new Promise((r) => setTimeout(r, 250))
  }
  return false
}

/**
 * 안에 든 서버를 켠다.
 *
 * 따로 깔아 둔 Node 를 찾지 않는다 — 이 프로그램이 이미 Node 를 품고 있다.
 * (`ELECTRON_RUN_AS_NODE` 를 켜면 프로그램 자신이 Node 노릇을 한다.)
 * 원장님 컴퓨터에 Node 가 있든 없든, 몇 판이든 상관없다.
 */
async function startServer() {
  const lanOn = shellPrefs().lan === true
  const port = await freePort()
  const entry = path.join(appRoot(), 'server.js')
  if (!fs.existsSync(entry)) throw new Error(`프로그램 본체를 찾지 못했습니다:\n${entry}`)

  server = spawn(process.execPath, [entry], {
    cwd: appRoot(),
    env: {
      ...process.env,
      ELECTRON_RUN_AS_NODE: '1',
      NODE_ENV: 'production',
      PORT: String(port),
      /*
       * 기본은 **이 컴퓨터 안에서만** 듣는다(127.0.0.1).
       *
       * 「태블릿에서 열기」를 켜신 때만 공유기 쪽으로도 문을 연다. 늘 열어 두면
       * 학원과 함께 쓰는 와이파이에서 아이 명단이 남의 기기에도 보이게 된다.
       * 켜고 끄는 것은 원장님이 정하시고, 바뀌면 다시 열 때 적용된다.
       */
      HOSTNAME: lanOn ? '0.0.0.0' : '127.0.0.1',
      PIANOEVENT_LAN: lanOn ? '1' : '0',
      // 학원 자료는 쓸 수 있는 자리에
      PIANOEVENT_DATA_DIR: dataDir(),
      // 설치판은 인증키를 묻는다. 상세페이지의 체험판(웹)은 묻지 않는다
      PIANOEVENT_REQUIRE_LICENSE: '1',
      // 키를 확인할 때 쓰는 비밀 — 설치본을 뽑을 때 본체 옆에 담아 두었다
      ...(licenseSecret() ? { RECITAL_LICENSE_SECRET: licenseSecret() } : {}),
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  })
  server.stdout.on('data', (chunk) => process.stdout.write(`[서버] ${chunk}`))
  server.stderr.on('data', (chunk) => process.stderr.write(`[서버] ${chunk}`))

  if (!(await waitForServer(port))) throw new Error('프로그램이 뜨지 않았습니다. 잠시 뒤 다시 열어 주세요.')
  return port
}

function stopServer() {
  if (!server) return
  try {
    server.kill()
  } catch {
    /* 이미 내려갔으면 그대로 */
  }
  server = null
}

/**
 * 첫 화면 — 서버가 켜지는 동안 보여 드리는 창.
 *
 * 안에 든 서버가 뜨기까지 학원 컴퓨터에서는 10~25초가 걸린다. 그 동안 화면에 아무것도
 * 없으면 원장님은 **안 켜진 줄 알고 다시 두 번 누르신다.** (두 개가 뜨는 것은 막아 두었지만
 * 「눌렀는데 아무 일도 없다」는 느낌 자체가 이미 실패다.)
 *
 * 그래서 누르시는 즉시 무대 사진 한 장과 「준비하고 있습니다」를 띄운다. 기다림은 같지만
 * **기다리고 있다는 것을 아신다.** 전문 프로그램은 모두 이렇게 한다.
 */
let splash = null

/** 첫 화면에 넣을 그림을 data: 주소로 읽어 온다. 못 읽으면 그림 없이 띄운다 */
function artData(name, mime) {
  for (const at of [
    path.join(appRoot(), 'public', 'art', 'app', name),
    path.join(__dirname, '..', 'public', 'art', 'app', name),
  ]) {
    try {
      if (fs.existsSync(at)) return `data:${mime};base64,${fs.readFileSync(at).toString('base64')}`
    } catch {
      /* 첫 화면이 못 떠서 프로그램이 안 열리는 일은 없어야 한다 */
    }
  }
  return null
}

function showSplash() {
  const html = splashHtml(artData('splash.jpg', 'image/jpeg'), artData('logo.png', 'image/png'))

  splash = new BrowserWindow({
    width: 560,
    height: 340,
    frame: false,
    resizable: false,
    center: true,
    show: false,
    skipTaskbar: false,
    backgroundColor: '#08080a',
    title: BRAND.name,
    icon: path.join(__dirname, 'icon.png'),
    webPreferences: { contextIsolation: true, nodeIntegration: false },
  })
  splash.once('ready-to-show', () => splash?.show())
  void splash.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`)
}

function closeSplash() {
  try {
    splash?.destroy()
  } catch {
    /* 이미 닫혔으면 그대로 */
  }
  splash = null
}

/**
 * 메뉴.
 *
 * 영어로 된 기본 메뉴(File · Edit · View · Window)를 그대로 두면 그것부터 낯설다.
 * 원장님이 실제로 쓰실 것만 우리 말로 남긴다.
 */
function buildMenu(port) {
  const go = (to) => () => win?.loadURL(`http://127.0.0.1:${port}${to}`)
  Menu.setApplicationMenu(
    Menu.buildFromTemplate([
      {
        label: BRAND.name,
        submenu: [
          { label: '행사 목록', accelerator: 'CmdOrCtrl+1', click: go('/events') },
          { label: '사용설명서', accelerator: 'F1', click: go('/help') },
          { label: '학원 설정', click: go('/settings') },
          { type: 'separator' },
          {
            label: '학원 자료 폴더 열기',
            click: () => shell.openPath(dataDir()),
          },
          {
            label: '태블릿에서 열기',
            type: 'checkbox',
            checked: shellPrefs().lan === true,
            click: (item) => {
              saveShellPrefs({ ...shellPrefs(), lan: item.checked })
              dialog.showMessageBox({
                type: 'info',
                title: BRAND.name,
                message: item.checked ? '태블릿에서 열기를 켰습니다.' : '태블릿에서 열기를 껐습니다.',
                detail: item.checked
                  ? '프로그램을 닫았다가 다시 열면 켜집니다.\n그다음 [설정] 화면에 태블릿으로 비출 QR과 주소가 나옵니다.\n\n같은 와이파이에 있는 다른 기기에서도 아이 명단이 보이게 됩니다.'
                  : '프로그램을 닫았다가 다시 열면 이 컴퓨터에서만 열립니다.',
                buttons: ['확인'],
              })
            },
          },
          { type: 'separator' },
          { label: '끝내기', role: 'quit' },
        ],
      },
      {
        label: '보기',
        submenu: [
          { label: '뒤로', accelerator: 'Alt+Left', click: () => win?.webContents.navigationHistory?.goBack() ?? win?.webContents.goBack() },
          { label: '새로고침', accelerator: 'CmdOrCtrl+R', role: 'reload' },
          { type: 'separator' },
          { label: '글씨 크게', accelerator: 'CmdOrCtrl+Plus', role: 'zoomIn' },
          { label: '글씨 작게', accelerator: 'CmdOrCtrl+-', role: 'zoomOut' },
          { label: '글씨 보통', accelerator: 'CmdOrCtrl+0', role: 'resetZoom' },
          { type: 'separator' },
          { label: '전체 화면', accelerator: 'F11', role: 'togglefullscreen' },
        ],
      },
      {
        label: '편집',
        submenu: [
          { label: '실행 취소', role: 'undo' },
          { label: '다시 실행', role: 'redo' },
          { type: 'separator' },
          { label: '잘라내기', role: 'cut' },
          { label: '복사', role: 'copy' },
          { label: '붙여넣기', role: 'paste' },
          { label: '모두 선택', role: 'selectAll' },
        ],
      },
    ]),
  )
}

function createWindow(port) {
  win = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 960,
    minHeight: 620,
    show: false,
    backgroundColor: '#faf9f6',
    title: BRAND.name,
    icon: path.join(__dirname, 'icon.png'),
    webPreferences: { contextIsolation: true, nodeIntegration: false },
  })

  // 본 창이 뜨는 순간 첫 화면을 치운다 — 둘이 겹쳐 보이면 그것대로 어수선하다
  win.once('ready-to-show', () => {
    closeSplash()
    win?.show()
  })

  // 본 창이 끝내 못 뜨면 첫 화면만 남아 영원히 「준비하고 있습니다」가 된다.
  // 그럴 때는 첫 화면을 치우고 무엇이 잘못됐는지 말씀드린다.
  win.webContents.on('did-fail-load', (_event, code, description) => {
    closeSplash()
    dialog.showErrorBox(`${BRAND.name}를 열지 못했습니다`, `${description} (${code})\n프로그램을 닫았다가 다시 열어 주세요.`)
  })
  win.on('closed', () => {
    win = null
  })

  // 학부모 초대장 같은 바깥 주소는 늘 쓰시던 브라우저로 — 이 창은 프로그램 창이다
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (!url.startsWith(`http://127.0.0.1:${port}`)) {
      void shell.openExternal(url)
      return { action: 'deny' }
    }
    return { action: 'allow' }
  })

  void win.loadURL(`http://127.0.0.1:${port}/events`)
}

// 두 번 눌러 두 개가 뜨면 같은 자료를 두 곳에서 고치게 된다
if (!app.requestSingleInstanceLock()) {
  app.quit()
} else {
  app.on('second-instance', () => {
    if (win) {
      if (win.isMinimized()) win.restore()
      win.focus()
    }
  })

  app.whenReady().then(async () => {
    try {
      showSplash()
      const port = await startServer()
      buildMenu(port)
      createWindow(port)
      // 검사용 사진 찍기 — 배포본에는 이 파일이 없으므로 조용히 넘어간다
      if (process.env.PIANOEVENT_SHOT) {
        try {
          require('./_shot.js')
        } catch {
          /* 없으면 그냥 뜬다 */
        }
      }
      app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) createWindow(port)
      })
    } catch (error) {
      closeSplash()
      dialog.showErrorBox(`${BRAND.name}를 열지 못했습니다`, String(error?.message ?? error))
      app.quit()
    }
  })

  app.on('window-all-closed', () => {
    stopServer()
    app.quit()
  })
  app.on('before-quit', stopServer)
  app.on('quit', stopServer)
}
