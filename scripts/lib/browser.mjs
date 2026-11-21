// 검사 스크립트가 쓸 브라우저를 고른다.
//
// 순서: 직접 지정(CHROMIUM_PATH) → 플레이라이트가 받아 둔 크로미움 → 이 PC 에 깔린 Edge · Chrome.
// 윈도우에는 Edge 가 기본으로 깔려 있어, `npx playwright install` 로 크로미움을 따로 받지 않아도 돈다.

import { existsSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { chromium } from 'playwright'

/** 클라우드·CI 처럼 브라우저를 미리 받아 둔 폴더(PLAYWRIGHT_BROWSERS_PATH)에서 찾는다 */
function preinstalled() {
  const root = process.env.PLAYWRIGHT_BROWSERS_PATH
  if (!root || root === '0' || !existsSync(root)) return null
  const dirs = readdirSync(root).filter((d) => /^chromium-\d+$/.test(d)).sort()
  for (const dir of dirs.reverse()) {
    // 플레이라이트 버전·운영체제에 따라 폴더 이름이 다르다
    for (const sub of ['chrome-linux64/chrome', 'chrome-linux/chrome', 'chrome-win64/chrome.exe', 'chrome-win/chrome.exe',
      'chrome-mac-arm64/Chromium.app/Contents/MacOS/Chromium', 'chrome-mac/Chromium.app/Contents/MacOS/Chromium']) {
      const p = join(root, dir, sub)
      if (existsSync(p)) return p
    }
  }
  return null
}

/**
 * chromium.launch / launchPersistentContext 에 함께 넘길 옵션.
 * @returns {{executablePath?:string, channel?:string, label:string}}
 */
export function browserOptions() {
  const explicit = process.env.CHROMIUM_PATH
  if (explicit && existsSync(explicit)) return { executablePath: explicit, label: explicit }

  const pre = preinstalled()
  if (pre) return { executablePath: pre, label: pre }

  try {
    const own = chromium.executablePath()
    if (own && existsSync(own)) return { label: '플레이라이트 크로미움' }
  } catch { /* 아직 받지 않았다 */ }

  // PC 에 깔린 브라우저 — 윈도우는 Edge 가 기본, 맥은 Chrome 이 있으면 쓴다
  if (process.platform === 'win32') return { channel: 'msedge', label: 'Microsoft Edge' }
  if (process.platform === 'darwin') return { channel: 'chrome', label: 'Google Chrome' }
  return { label: '플레이라이트 기본값' }
}

/** 옵션에서 표시용 이름을 뺀 것 */
export function launchOptions() {
  const { label, ...opts } = browserOptions()
  return opts
}

/** 브라우저를 못 띄웠을 때 다음에 할 일을 알려 준다 */
export function explainLaunchError(err) {
  const { label } = browserOptions()
  return [
    `브라우저(${label})를 열지 못했습니다.`,
    '  아래 중 하나를 해 주세요:',
    '  1) 검사용 크로미움 받기:  npx playwright install chromium',
    '  2) 또는 크롬·엣지 실행 파일 위치를 직접 지정:  CHROMIUM_PATH=…/chrome.exe',
    `  (원래 오류: ${String(err?.message || err).split('\n')[0]})`
  ].join('\n')
}

/** 영속 프로필로 브라우저를 연다 (IndexedDB 가 실행 사이에 남는다). 못 열면 다음에 할 일을 알려 준다. */
export async function openContext(profileDir, options = {}) {
  try {
    return await chromium.launchPersistentContext(profileDir, { ...options, ...launchOptions() })
  } catch (err) {
    throw new Error(explainLaunchError(err))
  }
}

/** 프로필 없이 브라우저를 연다 */
export async function openBrowser(options = {}) {
  try {
    return await chromium.launch({ ...options, ...launchOptions() })
  } catch (err) {
    throw new Error(explainLaunchError(err))
  }
}
