'use client'

import { useEffect, useState } from 'react'
import { QR_QUIET, makeQr, qrSvgPath } from '@/lib/qr'

/**
 * 종이에서 화면으로 돌아오는 길.
 *
 * 주소를 **화면이 붙은 뒤에** 만든다. 프로그램을 켠 자리가 그때그때 다르기 때문이다 —
 * 같은 컴퓨터에서 보시면 `localhost`, 휴대폰으로 보시면 공유기 주소(192.168.…).
 * 서버에서는 어느 쪽인지 알 수가 없으므로 여기서 `window.location.origin` 을 읽는다.
 *
 * QR 아래에 주소를 글로도 적는다. 읽는 기계가 없거나 못 읽어도 손으로 치실 수 있게.
 */
export function QrCode({
  path,
  size = 96,
  label,
  href,
}: {
  /** `/events/…` 처럼 앞자리 빼고 */
  path: string
  /** 그림 한 변(px) */
  size?: number
  label?: string
  /** 이 컴퓨터가 아닌 **다른 자리**를 가리켜야 할 때(공유기 주소 등) 통째로 준다 */
  href?: string
}) {
  const [url, setUrl] = useState<string | null>(href ?? null)

  useEffect(() => {
    if (href) {
      setUrl(href)
      return
    }
    try {
      setUrl(new URL(path, window.location.origin).toString())
    } catch {
      setUrl(null)
    }
  }, [path, href])

  const matrix = url ? makeQr(url) : null
  if (!matrix) {
    // 아직 주소를 모르거나 담기지 않는다 — 자리를 비워 둔다 (종이가 밀리지 않게)
    return <span className="block" style={{ width: size, height: size }} aria-hidden />
  }

  const span = matrix.length + QR_QUIET * 2

  return (
    <span className="grid justify-items-center gap-0.5" data-testid="qr-code">
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${span} ${span}`}
        role="img"
        aria-label={label ?? '휴대폰으로 비추면 열립니다'}
        shapeRendering="crispEdges"
      >
        <rect width={span} height={span} fill="#fff" />
        <g transform={`translate(${QR_QUIET} ${QR_QUIET})`}>
          <path d={qrSvgPath(matrix)} fill="#000" />
        </g>
      </svg>
      {label && <span className="text-[9px] leading-none text-neutral-500">{label}</span>}
    </span>
  )
}
