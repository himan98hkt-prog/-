/**
 * 피아노이벤트 — 설치해서 쓰는 프로그램의 겉껍데기.
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
      HOSTNAME: '127.0.0.1',
      // 학원 자료는 쓸 수 있는 자리에
      PIANOEVENT_DATA_DIR: dataDir(),
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
        label: '피아노이벤트',
        submenu: [
          { label: '행사 목록', accelerator: 'CmdOrCtrl+1', click: go('/events') },
          { label: '사용설명서', accelerator: 'F1', click: go('/help') },
          { label: '학원 설정', click: go('/settings') },
          { type: 'separator' },
          {
            label: '학원 자료 폴더 열기',
            click: () => shell.openPath(dataDir()),
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
    title: '피아노이벤트',
    icon: path.join(__dirname, 'icon.png'),
    webPreferences: { contextIsolation: true, nodeIntegration: false },
  })

  win.once('ready-to-show', () => win.show())
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
      dialog.showErrorBox('피아노이벤트를 열지 못했습니다', String(error?.message ?? error))
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
