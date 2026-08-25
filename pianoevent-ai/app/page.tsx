import { CalendarDays, FileMusic, Mic2, Send, Sparkles } from 'lucide-react'
import Link from 'next/link'
import { AppShell } from '@/components/app-shell'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { formatEventDate } from '@/lib/format'
import { currentAcademy } from '@/lib/session'
import { getRepository } from '@/lib/store'
import { EVENT_STATUS_LABEL } from '@/lib/types'

export const dynamic = 'force-dynamic'

const STEPS = [
  {
    icon: FileMusic,
    title: '명단만 붙여넣기',
    body: '엑셀에서 복사한 학생·연주곡·소요시간을 그대로 붙여넣으면 표로 정리됩니다.',
  },
  {
    icon: Sparkles,
    title: '순서와 러닝타임 자동 배치',
    body: '오프닝 → 초급 → 중급 → 앙상블 → 피날레 흐름으로 재배치하고 종료 시각까지 계산합니다.',
  },
  {
    icon: Mic2,
    title: '사회자 대본 원클릭',
    body: '곡 해설과 학생 소개를 합친 멘트를 곡마다 만들어 그대로 읽을 수 있게 인쇄합니다.',
  },
  {
    icon: Send,
    title: '모바일 초대장 + 참석 집계',
    body: '카카오톡으로 보내는 초대장 링크와 실시간 RSVP 집계까지 한 화면에서.',
  },
]

export default async function HomePage() {
  const academy = await currentAcademy()
  const events = await getRepository().listEvents(academy.id)
  const upcoming = events.filter((e) => e.status !== 'done').slice(0, 3)

  return (
    <AppShell academyName={academy.name}>
      <section className="animate-fade-up">
        <Badge variant="accent">피아노학원 행사 기획 자동화</Badge>
        <h1 className="mt-3 max-w-2xl font-serif text-3xl font-bold leading-snug tracking-tight sm:text-4xl">
          연주회 준비에 쓰던 사흘을
          <br />
          삼십 분으로 줄입니다.
        </h1>
        <p className="mt-3 max-w-xl text-muted-foreground">
          학생 명단 하나로 연주 순서표·사회자 대본·모바일 초대장·참석 집계까지. 엑셀과 메모장을 오갈 필요가 없습니다.
        </p>
        <div className="mt-6 flex flex-wrap gap-2">
          <Link href="/events/new">
            <Button size="lg">연주회 만들기</Button>
          </Link>
          <Link href="/seasons">
            <Button size="lg" variant="outline">
              시즌 특강 팩 열기
            </Button>
          </Link>
        </div>
      </section>

      <section className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {STEPS.map((step) => (
          <Card key={step.title}>
            <CardContent className="py-5">
              <step.icon className="h-5 w-5 text-accent" aria-hidden />
              <h3 className="mt-3 text-sm font-semibold">{step.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{step.body}</p>
            </CardContent>
          </Card>
        ))}
      </section>

      <section className="mt-10">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold">진행 중인 행사</h2>
          <Link href="/events" className="text-sm text-muted-foreground hover:text-foreground">
            전체 보기 →
          </Link>
        </div>

        {upcoming.length === 0 ? (
          <Card>
            <CardContent className="py-10 text-center text-sm text-muted-foreground">
              아직 등록된 행사가 없습니다.{' '}
              <Link href="/events/new" className="font-medium text-foreground underline underline-offset-4">
                첫 연주회 만들기
              </Link>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-3 md:grid-cols-3">
            {upcoming.map((event) => (
              <Link key={event.id} href={`/events/${event.id}`}>
                <Card className="h-full transition-shadow hover:shadow-md">
                  <CardHeader>
                    <div className="flex items-center justify-between gap-2">
                      <CardTitle className="truncate">{event.title}</CardTitle>
                      <Badge variant={event.status === 'draft' ? 'outline' : 'accent'}>
                        {EVENT_STATUS_LABEL[event.status]}
                      </Badge>
                    </div>
                    <CardDescription className="flex items-center gap-1.5">
                      <CalendarDays className="h-3.5 w-3.5" aria-hidden />
                      {formatEventDate(event.event_at)}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="text-sm text-muted-foreground">{event.venue || '장소 미정'}</CardContent>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </section>
    </AppShell>
  )
}
