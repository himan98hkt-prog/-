'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'

/**
 * 머리띠의 차림표 한 칸.
 *
 * 예전에는 **지금 어느 화면에 있는지 표시가 없었다.** 다섯 칸이 똑같이 회색이라
 * 「설정에 들어와 있는 건가?」를 화면 내용으로 짐작하셔야 했다.
 * 지금 보고 계신 칸에는 금색 밑줄이 그어진다.
 *
 * 하위 화면(`/events/…`)에 계실 때도 「행사」에 줄이 그어져야 한다 —
 * 정확히 같은 주소일 때만 표시하면 정작 일하시는 동안에는 표시가 사라진다.
 */
export function NavLink({ href, label, short }: { href: string; label: string; short: string }) {
  const pathname = usePathname() ?? '/'
  const here = pathname === href || pathname.startsWith(`${href}/`)

  return (
    <Link
      href={href}
      aria-current={here ? 'page' : undefined}
      className={cn(
        'press whitespace-nowrap rounded-md px-2 py-1.5 text-muted-foreground hover:bg-secondary hover:text-foreground sm:px-3',
        here && 'nav-here',
      )}
    >
      <span className="sm:hidden">{short}</span>
      <span className="hidden sm:inline">{label}</span>
    </Link>
  )
}
