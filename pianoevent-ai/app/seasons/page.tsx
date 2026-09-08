import { AppShell } from '@/components/app-shell'
import { SeasonStudio } from '@/components/season/season-studio'
import { templatePack } from '@/lib/season/templates'
import { currentAcademy } from '@/lib/session'
import type { SeasonTheme } from '@/lib/types'

export const dynamic = 'force-dynamic'
export const metadata = { title: '시즌 특강' }

const THEMES: SeasonTheme[] = ['halloween', 'christmas', 'vacation']

export default async function SeasonsPage({ searchParams }: { searchParams: { theme?: string } }) {
  const academy = await currentAcademy()
  const theme = THEMES.includes(searchParams.theme as SeasonTheme) ? (searchParams.theme as SeasonTheme) : 'christmas'

  return (
    <AppShell academyName={academy.name}>
      <div className="mb-6 no-print">
        <h1 className="text-2xl font-bold tracking-tight">시즌 특강 팩</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          할로윈·크리스마스·방학 테마를 고르면 주차별 수업 계획서와 인쇄용 활동지가 한 번에 나옵니다.
        </p>
      </div>
      <SeasonStudio initialPack={templatePack(theme)} />
    </AppShell>
  )
}
