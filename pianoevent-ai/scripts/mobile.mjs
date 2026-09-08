#!/usr/bin/env node
/**
 * 휴대폰에서 열어 보기.
 *
 *   npm run mobile
 *
 * 같은 와이파이에 있는 휴대폰에서 접속할 수 있도록 서버를 열고,
 * 주소와 QR 코드를 명령창에 크게 띄운다. (QR 은 qrcode-terminal 이 있을 때만)
 */
import { spawn } from 'node:child_process'
import { networkInterfaces } from 'node:os'
import { join } from 'node:path'

const PORT = Number(process.env.PORT ?? 3000)

/** 공유기에서 받은 내 컴퓨터 주소 (192.168.x.x 같은 것) */
function lanAddresses() {
  const found = []
  for (const [name, list] of Object.entries(networkInterfaces())) {
    for (const net of list ?? []) {
      if (net.family !== 'IPv4' || net.internal) continue
      found.push({ name, address: net.address })
    }
  }
  // 집·학원 공유기 대역을 먼저 보여 준다
  const priority = (a) => (/^192\.168\./.test(a.address) ? 0 : /^10\./.test(a.address) ? 1 : 2)
  return found.sort((a, b) => priority(a) - priority(b))
}

function box(lines) {
  const width = Math.max(...lines.map((l) => [...l].reduce((n, ch) => n + (ch.charCodeAt(0) > 0x2000 ? 2 : 1), 0)))
  const pad = (l) => {
    const w = [...l].reduce((n, ch) => n + (ch.charCodeAt(0) > 0x2000 ? 2 : 1), 0)
    return l + ' '.repeat(width - w)
  }
  console.log('\n┌' + '─'.repeat(width + 2) + '┐')
  for (const line of lines) console.log('│ ' + pad(line) + ' │')
  console.log('└' + '─'.repeat(width + 2) + '┘\n')
}

const addresses = lanAddresses()
const url = addresses.length > 0 ? `http://${addresses[0].address}:${PORT}` : `http://localhost:${PORT}`

const lines = ['📱  휴대폰에서 열어 보기', '']
if (addresses.length > 0) {
  lines.push('휴대폰을 컴퓨터와 같은 와이파이에 연결한 뒤,')
  lines.push('휴대폰 브라우저 주소창에 아래를 입력하세요.')
  lines.push('')
  lines.push(`    ${url}`)
  if (addresses.length > 1) {
    lines.push('')
    lines.push('안 열리면 아래 주소도 시도해 보세요.')
    for (const a of addresses.slice(1)) lines.push(`    http://${a.address}:${PORT}`)
  }
} else {
  lines.push('공유기 주소를 찾지 못했습니다.')
  lines.push('와이파이에 연결되어 있는지 확인해 주세요.')
}
lines.push('')
lines.push(`이 컴퓨터에서는  http://localhost:${PORT}`)
lines.push('끄려면 이 창에서 Ctrl + C')
box(lines)

// QR 코드는 있으면 보여 주고, 없으면 조용히 넘어간다
try {
  const { default: qr } = await import('qrcode-terminal')
  console.log('휴대폰 카메라로 아래 QR 을 비춰도 됩니다.\n')
  qr.generate(url, { small: true })
} catch {
  console.log('(QR 코드를 보려면  npm i -D qrcode-terminal  를 한 번 실행하세요)\n')
}

console.log('서버를 켜는 중입니다… 잠시만 기다려 주세요.\n')

const child = spawn(
  process.execPath,
  [join('node_modules', 'next', 'dist', 'bin', 'next'), 'dev', '-H', '0.0.0.0', '-p', String(PORT)],
  { stdio: 'inherit' },
)
child.on('exit', (code) => process.exit(code ?? 0))
