import Link from 'next/link'
import { AppShell } from '@/components/app-shell'
import { AcademyForm } from '@/components/settings/academy-form'
import { DeleteAccount } from '@/components/settings/delete-account'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { isAiConfigured, PRO_MODEL } from '@/lib/ai/gemini'
import { currentAcademy } from '@/lib/session'
import { getRepository } from '@/lib/store'

export const dynamic = 'force-dynamic'
export const metadata = { title: '설정' }

export default async function SettingsPage() {
  const academy = await currentAcademy()
  const driver = getRepository().driver
  const ai = isAiConfigured()

  return (
    <AppShell academyName={academy.name}>
      <div className="mx-auto grid max-w-2xl gap-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">설정</h1>
          <p className="mt-1 text-sm text-muted-foreground">학원 정보와 데이터 관리.</p>
        </div>

        <AcademyForm academy={academy} />

        <Card>
          <CardHeader>
            <CardTitle>연결 상태</CardTitle>
            <CardDescription>환경변수 설정에 따라 자동으로 전환됩니다.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 text-sm">
            <div className="flex items-center justify-between">
              <span>데이터 저장소</span>
              <Badge variant={driver === 'supabase' ? 'accent' : 'outline'}>
                {driver === 'supabase' ? 'Supabase PostgreSQL' : '로컬 데모 저장소'}
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <span>AI 생성</span>
              <Badge variant={ai ? 'accent' : 'outline'}>{ai ? `Gemini · ${PRO_MODEL}` : '내장 규칙 엔진'}</Badge>
            </div>
            <p className="text-xs text-muted-foreground">
              AI 키가 없어도 순서 배치와 사회자 대본은 내장 규칙 엔진으로 항상 생성됩니다. Gemini 키는 서버에만
              저장되며 브라우저로 전달되지 않습니다.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>개인정보 처리</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            수집·이용 항목과 보관 기간은{' '}
            <Link href="/privacy" className="font-medium text-foreground underline underline-offset-4">
              개인정보처리방침
            </Link>
            에서 확인할 수 있습니다.
          </CardContent>
        </Card>

        <DeleteAccount />
      </div>
    </AppShell>
  )
}
