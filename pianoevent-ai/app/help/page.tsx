import { readFile } from 'node:fs/promises'
import path from 'node:path'
import Link from 'next/link'
import { AppShell } from '@/components/app-shell'
import { HelpBook } from '@/components/help/help-book'
import { renderManual } from '@/lib/help/markdown'
import { currentAcademy } from '@/lib/session'

export const dynamic = 'force-dynamic'
export const metadata = { title: '사용설명서' }

/**
 * 프로그램 안에서 보는 사용설명서.
 *
 * 설명서는 `docs/MANUAL.md` 한 곳에만 둔다 — 같은 글을 두 벌 쓰면 반드시 어긋난다.
 * 원장님은 GitHub 을 열지 않으시므로, 그 파일을 읽어 여기에 그린다.
 */
async function loadManual(): Promise<string | null> {
  for (const spot of [
    path.join(process.cwd(), 'docs', 'MANUAL.md'),
    path.join(process.cwd(), 'public', 'manual.md'),
  ]) {
    try {
      return await readFile(spot, 'utf8')
    } catch {
      /* 다음 자리를 본다 */
    }
  }
  return null
}

export default async function HelpPage() {
  const [academy, markdown] = await Promise.all([currentAcademy(), loadManual()])
  const manual = markdown ? renderManual(markdown) : null

  return (
    <AppShell academyName={academy.name} className="container py-8 print:max-w-none print:p-0">
      <div className="mb-5 no-print">
        <h1 className="text-2xl font-bold tracking-tight">{manual?.title ?? '사용설명서'}</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          처음부터 끝까지 순서대로 적어 두었습니다. 급하시면 왼쪽 차례에서 바로 넘어가세요.
        </p>
      </div>

      {manual ? (
        <HelpBook sections={manual.sections} />
      ) : (
        <p className="rounded-lg border border-border px-4 py-10 text-center text-sm text-muted-foreground">
          설명서 파일을 찾지 못했습니다. 프로그램 폴더의 <code>docs/MANUAL.md</code> 를 열어 보세요.{' '}
          <Link href="/" className="underline underline-offset-4">
            홈으로
          </Link>
        </p>
      )}
    </AppShell>
  )
}
