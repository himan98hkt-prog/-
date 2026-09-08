import Link from 'next/link'
import { AppShell } from '@/components/app-shell'
import { BackupList } from '@/components/backup/backup-list'
import { AcademyForm } from '@/components/settings/academy-form'
import { AssetLibrary } from '@/components/settings/asset-library'
import { SystemCheck } from '@/components/settings/system-check'
import { TabletAccess } from '@/components/settings/tablet-access'
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

        <AssetLibrary academy={academy} />

        <SystemCheck driver={driver} ai={ai} />

        <TabletAccess />

        {/* 원장님이 잃으시는 경우는 사고가 아니라 평범한 하루다 */}
        <BackupList />

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
