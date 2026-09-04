// 학부모 리포트카드 — Canvas 로 이미지 생성 후 공유/저장.
// 로고·학원명·브랜드 컬러가 자동 반영된다(화이트라벨 요구사항).

import { branding, logoDataUrl, readableOn, mix } from './branding.js'

const W = 760
const PAD = 44

function loadImage(src) {
  return new Promise((resolve) => {
    if (!src) return resolve(null)
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = () => resolve(null)
    img.src = src
  })
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath()
  ctx.moveTo(x + r, y)
  ctx.arcTo(x + w, y, x + w, y + h, r)
  ctx.arcTo(x + w, y + h, x, y + h, r)
  ctx.arcTo(x, y + h, x, y, r)
  ctx.arcTo(x, y, x + w, y, r)
  ctx.closePath()
}

function wrapText(ctx, text, x, y, maxWidth, lineHeight, maxLines = 6) {
  const words = String(text || '').split(/(\s+)/)
  let line = ''
  let lines = 0
  for (const w of words) {
    const test = line + w
    if (ctx.measureText(test).width > maxWidth && line) {
      ctx.fillText(line.trim(), x, y)
      y += lineHeight
      line = w.trimStart()
      if (++lines >= maxLines - 1) break
    } else line = test
  }
  if (line) ctx.fillText(line.trim(), x, y)
  return y + lineHeight
}

/**
 * @param data {
 *   student, month, attendance:{rate,total,present,absent,counts},
 *   payment:{amount,paid,status}, customPairs:[{label,value}],
 *   comment, teacherName
 * }
 * @returns HTMLCanvasElement
 */
export async function drawReportCard(data) {
  const b = branding()
  const brand = b.brand_color
  const onBrand = readableOn(brand)

  // 내용에 맞춰 높이를 먼저 계산한다 — 출결 종류·학습 항목 수가 학원마다 달라서
  // 고정 높이로 그리면 항목이 많은 학원에서 아래가 잘린다.
  const att = data.attendance || { rate: 0, total: 0, present: 0, absent: 0, counts: {} }
  const entries = Object.entries(att.counts || {}).filter(([, v]) => v > 0)
  const pairs = (data.customPairs || []).slice(0, 8)
  const H =
    168 + 76 + 34 +                                   // 헤더 + 원생 정보
    150 + 40 +                                        // 출석 요약 카드
    (30 + entries.length * 42 + 30) +                 // 출결 상세
    (pairs.length ? 30 + pairs.length * 40 + 30 : 0) + // 학습 현황
    (data.payment ? 30 + 72 + 26 : 0) +               // 수납
    (data.comment ? 30 + 150 + 26 : 0) +              // 코멘트
    76                                                // 푸터

  const canvas = document.createElement('canvas')
  canvas.width = W
  canvas.height = Math.max(760, Math.round(H))
  const ctx = canvas.getContext('2d')
  const F = (weight, size) => `${weight} ${size}px system-ui, -apple-system, "Noto Sans KR", "Malgun Gothic", sans-serif`

  // 배경
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, W, canvas.height)

  // 헤더
  ctx.fillStyle = brand
  ctx.fillRect(0, 0, W, 168)
  const logo = await loadImage(logoDataUrl(192))
  if (logo) {
    ctx.save()
    roundRect(ctx, PAD, 40, 88, 88, 20)
    ctx.clip()
    ctx.drawImage(logo, PAD, 40, 88, 88)
    ctx.restore()
  }
  ctx.fillStyle = onBrand
  ctx.font = F(700, 34)
  ctx.fillText(b.name, PAD + 108, 82)
  ctx.font = F(400, 22)
  ctx.globalAlpha = 0.9
  ctx.fillText(`${data.month} 학습 리포트`, PAD + 108, 116)
  ctx.globalAlpha = 1

  // 원생 정보
  let y = 226
  ctx.fillStyle = '#111827'
  ctx.font = F(700, 40)
  ctx.fillText(`${data.student?.name || ''}`, PAD, y)
  ctx.font = F(400, 22)
  ctx.fillStyle = '#6b7280'
  const sub = [data.student?.school, data.student?.grade, data.className].filter(Boolean).join(' · ')
  ctx.fillText(sub, PAD, y + 34)

  // 출석 요약 카드
  y += 76
  ctx.fillStyle = mix(brand, '#ffffff', 0.9)
  roundRect(ctx, PAD, y, W - PAD * 2, 150, 20)
  ctx.fill()
  ctx.fillStyle = brand
  ctx.font = F(700, 56)
  ctx.fillText(`${att.rate}%`, PAD + 28, y + 88)
  ctx.fillStyle = '#374151'
  ctx.font = F(500, 22)
  ctx.fillText('출석률', PAD + 30, y + 122)

  const stats = [
    ['수업', `${att.total}회`],
    ['출석', `${att.present}회`],
    ['결석', `${att.absent}회`]
  ]
  stats.forEach(([label, val], i) => {
    const x = PAD + 240 + i * 150
    ctx.fillStyle = '#111827'
    ctx.font = F(700, 30)
    ctx.fillText(val, x, y + 78)
    ctx.fillStyle = '#6b7280'
    ctx.font = F(400, 20)
    ctx.fillText(label, x, y + 110)
  })

  // 출결 상세 막대
  y += 190
  ctx.fillStyle = '#111827'
  ctx.font = F(700, 24)
  ctx.fillText('출결 상세', PAD, y)
  y += 22
  const max = Math.max(1, ...entries.map(([, v]) => v))
  entries.forEach(([label, v], i) => {
    const rowY = y + 14 + i * 42
    ctx.fillStyle = '#4b5563'
    ctx.font = F(400, 20)
    ctx.fillText(label, PAD, rowY + 20)
    const barX = PAD + 80
    const barW = (W - PAD * 2 - 140) * (v / max)
    ctx.fillStyle = mix(brand, '#ffffff', 0.75)
    roundRect(ctx, barX, rowY + 4, W - PAD * 2 - 140, 22, 11)
    ctx.fill()
    ctx.fillStyle = brand
    roundRect(ctx, barX, rowY + 4, Math.max(8, barW), 22, 11)
    ctx.fill()
    ctx.fillStyle = '#111827'
    ctx.font = F(600, 20)
    ctx.fillText(`${v}`, W - PAD - 38, rowY + 22)
  })
  y += 14 + entries.length * 42 + 30

  // custom 필드 (계열별 항목: 진도/급수/점수 …)
  if (pairs.length) {
    ctx.fillStyle = '#111827'
    ctx.font = F(700, 24)
    ctx.fillText('학습 현황', PAD, y)
    y += 18
    pairs.forEach((p, i) => {
      const rowY = y + 12 + i * 40
      ctx.fillStyle = '#6b7280'
      ctx.font = F(400, 20)
      ctx.fillText(p.label, PAD, rowY + 20)
      ctx.fillStyle = '#111827'
      ctx.font = F(600, 21)
      ctx.fillText(String(p.value), PAD + 220, rowY + 20)
      ctx.strokeStyle = '#f3f4f6'
      ctx.beginPath()
      ctx.moveTo(PAD, rowY + 34)
      ctx.lineTo(W - PAD, rowY + 34)
      ctx.stroke()
    })
    y += 12 + pairs.length * 40 + 30
  }

  // 수납
  if (data.payment) {
    ctx.fillStyle = '#111827'
    ctx.font = F(700, 24)
    ctx.fillText('수납', PAD, y)
    y += 16
    ctx.fillStyle = '#f9fafb'
    roundRect(ctx, PAD, y, W - PAD * 2, 72, 16)
    ctx.fill()
    ctx.fillStyle = '#374151'
    ctx.font = F(400, 21)
    ctx.fillText(`${data.month} 수강료`, PAD + 22, y + 44)
    const st = data.payment.status || '미납'
    ctx.fillStyle = st === '완납' ? '#16a34a' : st === '부분' ? '#d97706' : '#dc2626'
    ctx.font = F(700, 22)
    const label = `${Number(data.payment.amount || 0).toLocaleString('ko-KR')}원 · ${st}`
    ctx.fillText(label, W - PAD - 22 - ctx.measureText(label).width, y + 44)
    y += 98
  }

  // 강사 코멘트
  if (data.comment) {
    ctx.fillStyle = '#111827'
    ctx.font = F(700, 24)
    ctx.fillText('선생님 한마디', PAD, y)
    y += 20
    ctx.fillStyle = mix(brand, '#ffffff', 0.94)
    const boxH = 150
    roundRect(ctx, PAD, y, W - PAD * 2, boxH, 16)
    ctx.fill()
    ctx.fillStyle = '#374151'
    ctx.font = F(400, 21)
    wrapText(ctx, data.comment, PAD + 22, y + 42, W - PAD * 2 - 44, 32, 4)
    y += boxH + 26
  }

  // 푸터
  ctx.fillStyle = '#9ca3af'
  ctx.font = F(400, 18)
  const foot = [b.name, b.phone, data.teacherName ? `담당 ${data.teacherName}` : null].filter(Boolean).join(' · ')
  ctx.fillText(foot, PAD, canvas.height - 44)
  ctx.fillText(new Date().toLocaleDateString('ko-KR'), W - PAD - 96, canvas.height - 44)
  ctx.strokeStyle = brand
  ctx.lineWidth = 6
  ctx.beginPath()
  ctx.moveTo(0, canvas.height - 6)
  ctx.lineTo(W, canvas.height - 6)
  ctx.stroke()

  return canvas
}

export function canvasToBlob(canvas) {
  return new Promise((resolve) => canvas.toBlob(resolve, 'image/png'))
}

export async function shareReport(canvas, filename = 'report.png', text = '') {
  const blob = await canvasToBlob(canvas)
  const file = new File([blob], filename, { type: 'image/png' })
  if (navigator.canShare?.({ files: [file] })) {
    await navigator.share({ files: [file], text })
    return 'shared'
  }
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 4000)
  return 'downloaded'
}
