import { AppShell } from '@/components/app-shell'
import { NewEventForm } from '@/components/event/new-event-form'
import { currentAcademy } from '@/lib/session'

export const dynamic = 'force-dynamic'
export const metadata = { title: '새 행사' }

export default async function NewEventPage() {
  const academy = await currentAcademy()
  return (
    <AppShell academyName={academy.name}>
      <div className="mx-auto max-w-xl">
        <h1 className="text-2xl font-bold tracking-tight">새 행사 만들기</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          행사명과 일시만 정하면 됩니다. 학생 명단은 다음 화면에서 붙여넣으세요.
        </p>
        <div className="mt-6">
          <NewEventForm />
        </div>
      </div>
    </AppShell>
  )
}
