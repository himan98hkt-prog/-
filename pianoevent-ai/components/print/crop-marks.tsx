import { BLEED_MM, CROP_MM } from '@/lib/print/paper'

/**
 * 인쇄소용 — 물림 여백과 재단선.
 *
 * 인쇄소는 종이를 크게 뽑아 **잘라 냅니다.** 자르는 자리가 종이마다 1~2mm 씩
 * 어긋나므로, 가장자리까지 색이 찬 디자인은 사방 3mm 를 더 그려 둡니다.
 * 그 여백은 잘려 나가고, 어디를 자르는지 알려 주는 것이 네 모서리의 재단선입니다.
 *
 * 원장님이 이 낱말을 아셔야 할 이유는 없습니다 — [인쇄소용] 을 한 번 누르시면
 * 이 상자가 인쇄물을 감싸고, 파일을 그대로 인쇄소에 넘기시면 됩니다.
 */
export function BleedFrame({ paper, children }: { paper: string; children: React.ReactNode }) {
  const line = { background: '#000' } as const
  // 재단선은 잘릴 자리에서 살짝 떨어져 시작한다 — 선이 인쇄면 안으로 들어오면 그대로 찍힌다
  const gap = `${BLEED_MM}mm`
  const len = `${CROP_MM}mm`

  return (
    // 물림 여백은 **인쇄물과 같은 색**이어야 한다. 흰색으로 두면 잘리는 자리가
    // 조금만 어긋나도 가장자리에 흰 줄이 남는다 — 물림 여백을 두는 이유가 그것이다.
    <div className="d-bleed relative" style={{ padding: gap, background: paper }}>
      {children}

      {/* 네 모서리 × 가로·세로 = 여덟 줄 */}
      {(
        [
          { x: 'left', y: 'top' },
          { x: 'right', y: 'top' },
          { x: 'left', y: 'bottom' },
          { x: 'right', y: 'bottom' },
        ] as const
      ).map((corner) => (
        <div key={`${corner.x}-${corner.y}`}>
          <div
            aria-hidden
            className="d-crop pointer-events-none absolute"
            style={{ ...line, [corner.x]: 0, [corner.y]: gap, width: len, height: '0.3mm' }}
          />
          <div
            aria-hidden
            className="d-crop pointer-events-none absolute"
            style={{ ...line, [corner.x]: gap, [corner.y]: 0, width: '0.3mm', height: len }}
          />
        </div>
      ))}
    </div>
  )
}
