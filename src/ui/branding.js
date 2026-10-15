// 화이트라벨 브랜딩 — 학원명/로고/브랜드컬러가 헤더·리포트·설치 아이콘까지 한 번에 반영된다.

import { getSetting, setSetting } from '../data/repo.js'

export const DEFAULT_BRANDING = {
  name: '학원 관리노트',
  brand_color: '#2563eb',
  logo: null,       // dataURL (Lite: IndexedDB 에 그대로 저장 / Pro: Storage URL)
  phone: '',
  slogan: ''
}

export function branding() {
  return { ...DEFAULT_BRANDING, ...(getSetting('branding') || {}) }
}

export async function saveBranding(patch) {
  const next = { ...branding(), ...patch }
  await setSetting('branding', next)
  applyBranding()
  return next
}

// ── 색 계산 ────────────────────────────────────────────────
export function hexToRgb(hex) {
  const m = String(hex || '').replace('#', '')
  const full = m.length === 3 ? m.split('').map((c) => c + c).join('') : m
  const n = parseInt(full, 16)
  return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 }
}

export function mix(hex, target, ratio) {
  const a = hexToRgb(hex)
  const b = hexToRgb(target)
  const c = (k) => Math.round(a[k] + (b[k] - a[k]) * ratio)
  return `#${[c('r'), c('g'), c('b')].map((v) => v.toString(16).padStart(2, '0')).join('')}`
}

/** 배경색 위에서 읽히는 글자색 (WCAG 상대 휘도 기준) */
export function readableOn(hex) {
  const { r, g, b } = hexToRgb(hex)
  const lin = (v) => { const s = v / 255; return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4 }
  const L = 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
  return L > 0.45 ? '#111827' : '#ffffff'
}

export function applyBranding() {
  const b = branding()
  const root = document.documentElement
  root.style.setProperty('--brand', b.brand_color)
  root.style.setProperty('--brand-dark', mix(b.brand_color, '#000000', 0.22))
  root.style.setProperty('--brand-light', mix(b.brand_color, '#ffffff', 0.86))
  root.style.setProperty('--brand-soft', mix(b.brand_color, '#ffffff', 0.94))
  root.style.setProperty('--on-brand', readableOn(b.brand_color))
  document.title = b.name
  const meta = document.querySelector('meta[name="theme-color"]')
  if (meta) meta.setAttribute('content', b.brand_color)
  updateManifest(b)
  document.dispatchEvent(new CustomEvent('branding:changed', { detail: b }))
  return b
}

// ── 로고 ────────────────────────────────────────────────────
/** 업로드 이미지를 정사각형으로 리사이즈해 dataURL 로 (원본 그대로 저장하면 용량이 터진다) */
export function resizeImage(file, size = 256) {
  return new Promise((resolve, reject) => {
    if (!/^image\/(png|jpeg|jpg|webp)$/.test(file.type)) return reject(new Error('PNG 또는 JPG 이미지를 올려 주세요'))
    const reader = new FileReader()
    reader.onerror = () => reject(new Error('파일을 읽지 못했습니다'))
    reader.onload = () => {
      const img = new Image()
      img.onerror = () => reject(new Error('이미지를 열지 못했습니다'))
      img.onload = () => {
        const canvas = document.createElement('canvas')
        canvas.width = canvas.height = size
        const ctx = canvas.getContext('2d')
        const scale = Math.min(size / img.width, size / img.height)
        const w = img.width * scale
        const hgt = img.height * scale
        ctx.clearRect(0, 0, size, size)
        ctx.drawImage(img, (size - w) / 2, (size - hgt) / 2, w, hgt)
        resolve(canvas.toDataURL('image/png'))
      }
      img.src = reader.result
    }
    reader.readAsDataURL(file)
  })
}

/** 로고 미업로드 시 학원명 이니셜 아바타 */
export function initialsAvatar(name, color, size = 192) {
  const canvas = document.createElement('canvas')
  canvas.width = canvas.height = size
  const ctx = canvas.getContext('2d')
  ctx.fillStyle = color || DEFAULT_BRANDING.brand_color
  const r = size * 0.22
  ctx.beginPath()
  ctx.moveTo(r, 0)
  ctx.arcTo(size, 0, size, size, r)
  ctx.arcTo(size, size, 0, size, r)
  ctx.arcTo(0, size, 0, 0, r)
  ctx.arcTo(0, 0, size, 0, r)
  ctx.fill()
  ctx.fillStyle = readableOn(color)
  ctx.font = `600 ${size * 0.42}px system-ui, -apple-system, "Noto Sans KR", sans-serif`
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(initialsOf(name), size / 2, size * 0.54)
  return canvas.toDataURL('image/png')
}

export function initialsOf(name) {
  const clean = String(name || '학원').replace(/\s+/g, ' ').trim()
  const words = clean.split(' ')
  if (words.length >= 2) return (words[0][0] || '') + (words[1][0] || '')
  return clean.slice(0, 2)
}

export function logoDataUrl(size = 192) {
  const b = branding()
  return b.logo || initialsAvatar(b.name, b.brand_color, size)
}

// ── PWA manifest 동적 생성 ──────────────────────────────────
let manifestUrl = null
export function updateManifest(b = branding()) {
  try {
    const icon = b.logo || initialsAvatar(b.name, b.brand_color, 512)
    const manifest = {
      name: b.name,
      short_name: b.name.slice(0, 12),
      description: `${b.name} 관리노트`,
      start_url: './',
      scope: './',
      display: 'standalone',
      background_color: '#ffffff',
      theme_color: b.brand_color,
      icons: [
        { src: icon, sizes: '192x192', type: 'image/png', purpose: 'any' },
        { src: icon, sizes: '512x512', type: 'image/png', purpose: 'any maskable' }
      ]
    }
    const blob = new Blob([JSON.stringify(manifest)], { type: 'application/manifest+json' })
    const url = URL.createObjectURL(blob)
    let link = document.querySelector('link[rel="manifest"]')
    if (!link) {
      link = document.createElement('link')
      link.rel = 'manifest'
      document.head.append(link)
    }
    link.href = url
    if (manifestUrl) URL.revokeObjectURL(manifestUrl)
    manifestUrl = url
    // 홈 화면 아이콘(iOS)도 같이 교체
    let apple = document.querySelector('link[rel="apple-touch-icon"]')
    if (!apple) {
      apple = document.createElement('link')
      apple.rel = 'apple-touch-icon'
      document.head.append(apple)
    }
    apple.href = icon
    return true
  } catch (err) {
    // blob manifest 를 막는 환경(일부 인앱 브라우저) — 기본 아이콘으로 폴백하고 앱 내 브랜딩만 유지
    console.warn('동적 manifest 실패, 기본 아이콘으로 폴백합니다', err)
    return false
  }
}
