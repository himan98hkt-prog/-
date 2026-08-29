// 창이 실제로 어떻게 보이는지 사진으로 남긴다 (검사용 · 배포에는 들어가지 않는다)
const { app, BrowserWindow } = require('electron')
const fs = require('node:fs')
app.whenReady().then(() => {
  const t = setInterval(async () => {
    const win = BrowserWindow.getAllWindows()[0]
    if (!win || win.webContents.isLoading()) return
    clearInterval(t)
    setTimeout(async () => {
      const img = await win.capturePage()
      fs.writeFileSync('shots/desktop-app.png', img.toPNG())
      console.log('찍었습니다')
      app.quit()
    }, 4000)
  }, 500)
})
