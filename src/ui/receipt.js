// 수강료 영수증 — Canvas 이미지로 만들어 저장·공유한다.
//
// 세금계산서·현금영수증(국세청)이 아니라 학원에서 학부모에게 주는 "수납 확인증" 이다.
// 매달 손으로 쓰던 종이 영수증을 그대로 대체하는 것이 목적이라 항목은 청구 내역 그대로 찍는다.

import { h, modal, toast } from './dom.js'
import { branding, logoDataUrl, readableOn } from './branding.js'
import { formatWon } from '../core/fees.js'
import { toYmd } from '../core/date.js'

const W = 700
const PAD = 40

function loadImage(src) {
  return new Promise((resolve) => {
    if (!src) return resolve(null)
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = () => resolve(null)
    img.src = src
  })
}

export async function drawReceipt({ payment, student, issuedAt = toYmd() }) {
  const b = branding()
  const brand = b.brand_color
  const onBrand = readableOn(brand)
  const lines = Array.isArray(payment.lines) && payment.lines.length
    ? payment.lines
    : [{ label: `${payment.month} 수강료`, amount: payment.amount }]

  const canvas = document.createElement('canvas')
  canvas.width = W
  canvas.height = 300 + lines.length * 38 + 190
  const ctx = canvas.getContext('2d')
  const font = (size, weight = '400') => `${weight} ${size}px -apple-system, "Apple SD Gothic Neo", "Malgun Gothic", sans-serif`

  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, W, canvas.height)

  // 머리글
  ctx.fillStyle = brand
  ctx.fillRect(0, 0, W, 120)
  const logo = await loadImage(logoDataUrl(120))
  if (logo) ctx.drawImage(logo, PAD, 26, 68, 68)
  ctx.fillStyle = onBrand
  ctx.font = font(26, '700')
  ctx.fillText(b.name || '학원', PAD + (logo ? 84 : 0), 58)
  ctx.font = font(15)
  ctx.fillText('수강료 영수증', PAD + (logo ? 84 : 0), 86)

  let y = 168
  ctx.fillStyle = '#111827'
  ctx.font = font(20, '700')
  ctx.fillText(`${student?.name || ''} 학부모님`, PAD, y)
  ctx.font = font(14)
  ctx.fillStyle = '#6b7280'
  ctx.fillText(`${payment.month} 청구분 · 발행일 ${issuedAt}`, PAD, y + 26)

  y += 66
  ctx.strokeStyle = '#e5e7eb'
  ctx.beginPath(); ctx.moveTo(PAD, y); ctx.lineTo(W - PAD, y); ctx.stroke()

  y += 34
  ctx.fillStyle = '#6b7280'
  ctx.font = font(13)
  ctx.fillText('내역', PAD, y)
  ctx.textAlign = 'right'
  ctx.fillText('금액', W - PAD, y)
  ctx.textAlign = 'left'

  for (const line of lines) {
    y += 38
    ctx.fillStyle = '#111827'
    ctx.font = font(15)
    ctx.fillText(String(line.label), PAD, y)
    ctx.textAlign = 'right'
    ctx.fillStyle = line.amount < 0 ? '#16a34a' : '#111827'
    ctx.fillText(formatWon(line.amount), W - PAD, y)
    ctx.textAlign = 'left'
  }

  y += 30
  ctx.strokeStyle = '#e5e7eb'
  ctx.beginPath(); ctx.moveTo(PAD, y); ctx.lineTo(W - PAD, y); ctx.stroke()

  const row = (label, value, strong = false) => {
    y += strong ? 44 : 34
    ctx.fillStyle = strong ? '#111827' : '#6b7280'
    ctx.font = font(strong ? 20 : 15, strong ? '700' : '400')
    ctx.fillText(label, PAD, y)
    ctx.textAlign = 'right'
    ctx.fillStyle = strong ? brand : '#111827'
    ctx.fillText(value, W - PAD, y)
    ctx.textAlign = 'left'
  }
  row('청구 금액', formatWon(payment.amount))
  row('납부 금액', formatWon(payment.paid))
  if (payment.remaining > 0) row('잔액', formatWon(payment.remaining))
  row('결제 방법', payment.method || '-')
  row(payment.remaining > 0 ? '부분 납부' : '납부 완료', formatWon(payment.paid), true)

  ctx.fillStyle = '#9ca3af'
  ctx.font = font(12)
  ctx.fillText('본 영수증은 학원 내부 수납 확인용입니다.', PAD, canvas.height - 34)
  return canvas
}

export async function openReceipt({ payment, student }) {
  const canvas = await drawReceipt({ payment, student })
  const img = h('img', { src: canvas.toDataURL('image/png'), style: { width: '100%', borderRadius: '10px', border: '1px solid var(--line)' } })
  const filename = `영수증_${student?.name || ''}_${payment.month}.png`

  modal({
    title: '수강료 영수증',
    body: h('div', {}, img, h('p', { class: 'small muted' }, '이미지를 저장해 문자·카톡으로 보내거나 인쇄해 주세요.')),
    actions: [
      {
        label: '인쇄', keepOpen: true, onClick: () => {
          const w = window.open('')
          if (!w) return toast('팝업이 차단되었습니다. 이미지를 저장해 인쇄해 주세요', 'error')
          w.document.write(`<img src="${canvas.toDataURL('image/png')}" style="width:100%" onload="window.print();window.close()">`)
        }
      },
      {
        label: '이미지 저장', kind: 'primary', keepOpen: true, onClick: () => {
          const a = document.createElement('a')
          a.href = canvas.toDataURL('image/png')
          a.download = filename
          a.click()
          toast('저장했습니다', 'ok')
        }
      }
    ]
  })
  return canvas
}
