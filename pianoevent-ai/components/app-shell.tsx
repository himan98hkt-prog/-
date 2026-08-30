import Link from 'next/link'
import { AutoBackup } from '@/components/backup/auto-backup'
import { NavLink } from '@/components/nav-link'
import { ErrorLog } from '@/components/support/error-log'
import { TextSizeToggle } from '@/components/ui/text-size-toggle'
import { UndoProvider } from '@/components/undo/undo-bar'
import { FirstRun } from '@/components/tour/first-run'
import { BRAND } from '@/lib/brand'
import { cn } from '@/lib/utils'

/**
 * 머리띠.
 *
 * 좁은 화면에서는 짧은 이름으로 바꾼다. 글씨 크기 단추까지 들어가면 다섯 글자짜리
 * 이름이 화면을 넘어가고, 넘어가면 **[설정]이 화면 밖으로 밀려나** 아예 못 누르신다.
 * 줄여도 뜻이 통하는 말로만 줄인다.
 */
const NAV = [
  { href: '/events', label: '행사', short: '행사' },
  { href: '/seasons', label: '시즌 특강', short: '특강' },
  { href: '/history', label: '기록', short: '기록' },
  // 설명서는 늘 손 닿는 곳에 있어야 한다 — 막혔을 때 찾아 나서게 하면 안 된다
  { href: '/help', label: '사용설명서', short: '설명서' },
  { href: '/settings', label: '설정', short: '설정' },
]

export function AppShell({
  children,
  academyName,
  className,
  eventId,
  bleed = false,
}: {
  children: React.ReactNode
  academyName: string
  className?: string
  /** 이 화면이 어느 행사의 것인가 — 되돌리기가 행사를 넘어가지 않게 */
  eventId?: string
  /**
   * 가장자리까지 꽉 채우는 화면(첫 화면).
   *
   * 여느 화면은 가운데 통(`container`)에 담긴다. 그런데 첫 화면의 큰 사진은
   * 화면 끝까지 닿아야 한다 — 양옆이 비면 **웹사이트가 아니라 문서처럼 보인다.**
   * 이때는 통을 벗기고, 각 마디가 알아서 통을 두른다.
   */
  bleed?: boolean
}) {
  return (
    // 바탕색은 화면(단계)마다 다르다 — ScreenHeader 가 --screen-bg 를 바꿔 준다
    <div className="app-shell min-h-screen">
      <header className="sticky top-0 z-20 border-b border-border bg-background/85 backdrop-blur no-print">
        <div className="container flex h-14 items-center justify-between gap-3">
          <Link
            href="/"
            className="press flex shrink-0 items-center gap-2 whitespace-nowrap rounded-md px-1 py-1 font-semibold tracking-tight"
          >
            <span aria-hidden className="text-lg">
              🎹
            </span>
            {/* 휴대폰에서는 이름이 두 줄로 접혀 머리띠가 무너진다 — 그림만 남긴다 */}
            <span className="hidden sm:inline">{BRAND.name}</span>
          </Link>
          <nav className="flex items-center gap-0.5 text-sm sm:gap-1">
            {/* 눈이 편치 않으신 분이 많다. 확대하는 법을 아셔야 할 이유는 없다 */}
            <TextSizeToggle />
            {NAV.map((item) => (
              <NavLink key={item.href} href={item.href} label={item.label} short={item.short} />
            ))}
          </nav>
        </div>
      </header>

      {/* 되돌리기는 화면 위 한 자리에만 둔다 — 자리마다 있으면 자리마다 배우셔야 한다 */}
      <main className={cn(bleed ? 'pb-10' : 'container py-8', className)}>
        <UndoProvider eventId={eventId}>{children}</UndoProvider>
      </main>

      <footer className="border-t border-border py-6 text-xs text-muted-foreground no-print">
        <div className="container flex flex-wrap items-center justify-between gap-2">
          <span>{academyName} · {BRAND.name} · {BRAND.maker}</span>
          <div className="flex gap-4">
            <Link href="/help#막히면" className="hover:text-foreground">
              막히면 여기
            </Link>
            <Link href="/privacy" className="hover:text-foreground">
              개인정보처리방침
            </Link>
            <Link href="/settings" className="hover:text-foreground">
              계정·데이터 삭제
            </Link>
          </div>
        </div>
      </footer>

      {/* 화면에서 난 오류를 이 브라우저 안에만 모아 둔다 — [막히면 여기] 에서 쓰인다 */}
      <ErrorLog />

      {/* 하루에 한 번, 묻지 않고 조용히 떠 둔다 */}
      <AutoBackup />

      {/* 처음 켜신 분께만 뜨는 안내. 화면을 가리지 않는다 */}
      <FirstRun />
    </div>
  )
}
