import Link from 'next/link'
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

      <main className={cn('container py-8', className)}>{children}</main>

      <footer className="border-t border-border py-6 text-xs text-muted-foreground no-print">
        <div className="container flex flex-wrap items-center justify-between gap-2">
          <span>{academyName} · PianoEvent AI</span>
          <div className="flex gap-4">
            <Link href="/privacy" className="hover:text-foreground">
              개인정보처리방침
            </Link>
            <Link href="/settings" className="hover:text-foreground">
              계정·데이터 삭제
            </Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
