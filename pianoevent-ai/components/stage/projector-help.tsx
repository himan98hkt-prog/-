'use client'

import { ChevronDown, Monitor } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/lib/utils'

/**
 * **노트북을 빔프로젝터에 꽂는 법.**
 *
 * 여기서 대부분 멈추신다. 화면은 다 만들어 놓고, 정작 연주회장에서 선을 꽂았는데
 * 스크린에 아무것도 안 나오거나, 원장님 노트북 화면이 그대로(순서표·메신저까지) 나간다.
 *
 * 이건 우리 프로그램이 아니라 **윈도우·맥의 일**이라 화면에서 해 드릴 수가 없다.
 * 그래서 **눌러야 할 자판**만 정확히 적어 둔다. 연주회장에서 이 화면을 열어 두시면 된다.
 *
 * 접어 둔다 — 아는 분께는 군더더기고, 모르는 분께는 이 한 줄이 전부다.
 */
export function ProjectorHelp() {
  const [open, setOpen] = useState(false)

  return (
    <div className="no-print rounded-lg border border-border p-3" data-testid="projector-help">
      <button
        type="button"
        onClick={() => setOpen((on) => !on)}
        aria-expanded={open}
        className="flex w-full items-center gap-1.5 text-left text-sm font-medium"
        data-testid="projector-toggle"
      >
        <Monitor className="h-4 w-4 text-accent" aria-hidden />
        빔프로젝터에 꽂았는데 스크린에 안 나옵니다
        <ChevronDown className={cn('ml-auto h-4 w-4 transition-transform', open && 'rotate-180')} aria-hidden />
      </button>

      {open && (
        <div className="mt-3 grid gap-3 border-t border-border pt-3 text-sm" data-testid="projector-steps">
          <div>
            <p className="font-medium">윈도우 노트북</p>
            <ol className="mt-1 grid gap-1 text-muted-foreground">
              <li>
                1. 자판에서 <strong className="text-foreground">윈도우키( ⊞ ) + P</strong> 를 함께 누릅니다.
                오른쪽에 네 가지가 뜹니다.
              </li>
              <li>
                2. <strong className="text-foreground">[복제]</strong> 를 고르세요. 원장님 화면과 스크린에 같은 것이
                나옵니다. 가장 안전합니다.
              </li>
              <li>
                3. 순서표나 메신저를 스크린에 안 보이게 하시려면 <strong className="text-foreground">[확장]</strong> 을
                고르고, 이 창을 스크린 쪽으로 끌어다 놓은 뒤 <strong className="text-foreground">[전체화면]</strong>.
              </li>
            </ol>
          </div>

          <div>
            <p className="font-medium">맥북</p>
            <ol className="mt-1 grid gap-1 text-muted-foreground">
              <li>
                1. 화면 오른쪽 위 <strong className="text-foreground">제어 센터</strong> → <strong className="text-foreground">화면 미러링</strong>.
              </li>
              <li>
                2. 빔프로젝터 이름을 고르면 스크린에 같은 화면이 나옵니다.
              </li>
              <li>
                3. 안 보이면 <strong className="text-foreground">시스템 설정 → 디스플레이</strong> 에서{' '}
                <strong className="text-foreground">[디스플레이 감지]</strong> 를 누르세요.
              </li>
            </ol>
          </div>

          <div>
            <p className="font-medium">그래도 안 나올 때</p>
            <ul className="mt-1 grid gap-1 text-muted-foreground">
              <li>· 빔프로젝터 리모컨에서 <strong className="text-foreground">입력(Input/Source)</strong> 을 눌러 꽂으신 자리(HDMI 1·2)로 맞추세요. 이게 가장 흔합니다.</li>
              <li>· 선을 뽑았다 다시 꽂으세요. 노트북이 다시 찾습니다.</li>
              <li>· 노트북에 HDMI 구멍이 없으면 <strong className="text-foreground">USB-C → HDMI 젠더</strong>가 있어야 합니다. 연주회장에 없을 수 있으니 미리 챙기세요.</li>
            </ul>
          </div>

          <p className="rounded-md border border-accent/40 bg-accent/5 px-3 py-2 text-xs">
            <strong>당일 아침에 한 번 해 보세요.</strong> 연주회장에 도착하시면 아이들이 오기 전에 선을 꽂고
            이 화면을 띄워 보시는 것이 좋습니다. 리허설 때가 가장 좋은 때입니다.
          </p>
        </div>
      )}
    </div>
  )
}
