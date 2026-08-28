import Link from 'next/link'
import { AutoBackup } from '@/components/backup/auto-backup'
import { ErrorLog } from '@/components/support/error-log'
import { UndoProvider } from '@/components/undo/undo-bar'
import { FirstRun } from '@/components/tour/first-run'
import { cn } from '@/lib/utils'

const NAV = [
  { href: '/events', label: '행사' },
  { href: '/seasons', label: '시즌 특강' },
  { href: '/history', label: '기록' },
  // 설명서는 늘 손 닿는 곳에 있어야 한다 — 막혔을 때 찾아 나서게 하면 안 된다
  { href: '/help', label: '사용설명서' },
  { href: '/settings', label: '설정' },
]

export function AppShell({
  children,
  academyName,
  className,
}: {
  children: React.ReactNode
  academyName: string
  className?: string
}) {
  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-20 border-b border-border bg-background/85 backdrop-blur no-print">
        <div className="container flex h-14 items-center justify-between gap-3">
          <Link
            href="/"
            className="flex shrink-0 items-center gap-2 whitespace-nowrap font-semibold tracking-tight"
          >
            <span aria-hidden className="text-lg">
              🎹
            </span>
            {/* 휴대폰에서는 이름이 두 줄로 접혀 머리띠가 무너진다 — 그림만 남긴다 */}
            <span className="hidden sm:inline">PianoEvent AI</span>
          </Link>
          <nav className="flex items-center gap-0.5 text-sm sm:gap-1">
            {NAV.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="whitespace-nowrap rounded-md px-2.5 py-1.5 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground sm:px-3"
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </div>
      </header>

      {/* 되돌리기는 화면 위 한 자리에만 둔다 — 자리마다 있으면 자리마다 배우셔야 한다 */}
      <main className={cn('container py-8', className)}>
        <UndoProvider>{children}</UndoProvider>
      </main>

      <footer className="border-t border-border py-6 text-xs text-muted-foreground no-print">
        <div className="container flex flex-wrap items-center justify-between gap-2">
          <span>{academyName} · PianoEvent AI</span>
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
