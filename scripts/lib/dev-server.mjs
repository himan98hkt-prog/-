// 검사 스크립트(smoke · perf · shots)가 쓰는 개발 서버.
//
// 예전에는 `npx vite` 를 자식 프로세스로 띄우고 프로세스 그룹째 종료했는데,
// 윈도우에서는 npx 가 npx.cmd 라 바로 실행되지 않고 그룹 종료(kill -pid)도 없다.
// Vite 를 같은 프로세스 안에서 띄우면 운영체제와 상관없이 같은 방식으로 열고 닫힌다.

import { createServer } from 'vite'

/**
 * @param {number} port
 * @returns {Promise<{origin:string, close:()=>Promise<void>}>}
 */
export async function startDevServer(port) {
  const server = await createServer({
    clearScreen: false,
    logLevel: 'error',
    server: { port, strictPort: true, open: false, host: 'localhost' }
  })
  try {
    await server.listen()
  } catch (err) {
    await server.close().catch(() => {})
    if (err?.code === 'EADDRINUSE' || /already in use/i.test(String(err?.message))) {
      throw new Error(`${port}번 포트를 다른 프로그램이 쓰고 있습니다. 그 프로그램(이전 검사나 개발 서버)을 닫고 다시 실행해 주세요.`)
    }
    throw err
  }
  let closed = false
  return {
    origin: `http://localhost:${port}`,
    close: async () => {
      if (closed) return
      closed = true
      await server.close()
    }
  }
}
