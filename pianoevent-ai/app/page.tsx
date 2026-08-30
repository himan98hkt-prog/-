import { ArrowRight, CalendarDays, FileMusic, Mic2, Send, Sparkles } from 'lucide-react'
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

/**
 * 첫 화면.
 *
 * 프로그램을 켜면 가장 먼저 보이는 화면이다. 여기가 문서처럼 보이면 **프로그램 전체가
 * 문서처럼 보인다.** 그래서 여느 화면과 다르게 짠다 —
 *
 *   · 사진이 화면 **끝까지** 닿는다. 양옆이 비면 웹사이트가 아니라 인쇄물이 된다
 *   · 마디마다 바탕이 밝다·어둡다로 갈린다. 띠가 갈리면 화면이 길어 보이지 않는다
 *   · 제목은 크고, 그 둘레는 시원하게 빈다
 *
 * 쓰이는 사진은 **인쇄물에 쓰는 그림 그대로**다(`public/art/`). 프로그램 안에 들어 있으니
 * 인터넷이 없어도 뜨고, 첫 화면에서 본 그림이 그대로 포스터로 나온다.
 */
const STEPS = [
  {
    no: '01',
    icon: FileMusic,
    title: '명단만 붙여넣기',
    body: '엑셀에서 복사한 학생·연주곡·소요시간을 그대로 붙여넣으면 표로 정리됩니다.',
  },
  {
    no: '02',
    icon: Sparkles,
    title: '순서와 러닝타임 자동 배치',
    body: '오프닝 → 초급 → 중급 → 앙상블 → 피날레 흐름으로 재배치하고 종료 시각까지 계산합니다.',
  },
  {
    no: '03',
    icon: Mic2,
    title: '사회자 대본 원클릭',
    body: '곡 해설과 학생 소개를 합친 멘트를 곡마다 만들어 그대로 읽을 수 있게 인쇄합니다.',
  },
  {
    no: '04',
    icon: Send,
    title: '모바일 초대장 + 참석 집계',
    body: '카카오톡으로 보내는 초대장 링크와 실시간 RSVP 집계까지 한 화면에서.',
  },
]

/** 첫 화면에 늘어놓는 실제 인쇄물 그림 — 「이런 것이 나옵니다」를 말 대신 보여 준다 */
const SHOWCASE = [
  { src: '/art/poster/ink-wash.jpg', name: '수묵' },
  { src: '/art/poster/deco.jpg', name: '아르데코' },
  { src: '/art/poster/engraving.jpg', name: '고전 동판화' },
  { src: '/art/poster/blossom-piano.jpg', name: '꽃과 피아노' },
  { src: '/art/poster/real-stage.jpg', name: '무대 (사진)' },
]

export default async function HomePage() {
  const academy = await currentAcademy()
  const events = await getRepository().listEvents(academy.id)
  const upcoming = events.filter((e) => e.status !== 'done').slice(0, 3)

  return (
    <AppShell academyName={academy.name} bleed>
      {/* ── 히어로 ─────────────────────────────────────────────── */}
      <section className="hero-band relative isolate overflow-hidden">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/art/app/hero-wide.jpg"
          alt=""
          aria-hidden
          className="hero-photo absolute inset-0 h-full w-full object-cover"
        />
        <div className="hero-scrim absolute inset-0" aria-hidden />

        <div className="container relative flex min-h-[26rem] flex-col justify-center py-16 sm:min-h-[32rem] sm:py-24">
          <p className="hero-eyebrow">피아노학원 연주회 준비 프로그램</p>
          <h1 className="mt-5 max-w-3xl font-serif text-[2.1rem] font-bold leading-[1.22] tracking-tight text-white sm:text-[3rem] lg:text-[3.5rem]">
            연주회 준비에 쓰던 사흘을
            <br />
            <span className="hero-gold">삼십 분</span>으로 줄입니다.
          </h1>
          <p className="mt-6 max-w-xl text-[0.98rem] leading-relaxed text-white/80 sm:text-lg">
            학생 명단 하나로 연주 순서표 · 사회자 대본 · 인쇄물 · 무대 화면 · 모바일 초대장까지.
            엑셀과 메모장을 오갈 필요가 없습니다.
          </p>

          <div className="mt-9 flex flex-wrap gap-3">
            <Link href="/events/new">
              <Button size="lg" className="h-12 px-7 text-base">
                연주회 만들기
              </Button>
            </Link>
            <Link href="/seasons">
              <Button size="lg" variant="outline" className="h-12 border-white/50 bg-white/10 px-7 text-base text-white backdrop-blur hover:border-white/80 hover:bg-white/20 hover:text-white">
                시즌 특강 팩 열기
              </Button>
            </Link>
          </div>

          <p className="mt-8 max-w-xl text-sm text-white/60">
            곡 선정과 악보는 원장님이 하시던 그대로입니다. 이 프로그램은{' '}
            <strong className="font-medium text-white/85">정해진 곡을 받아</strong> 순서 · 시간 · 멘트 ·
            인쇄물을 만듭니다.
          </p>
        </div>
      </section>

      {/* ── 네 가지 ────────────────────────────────────────────── */}
      <section className="container py-16 sm:py-20">
        <p className="section-eyebrow">하는 일</p>
        <h2 className="mt-3 max-w-xl font-serif text-2xl font-bold leading-snug tracking-tight sm:text-3xl">
          명단 하나를 넣으면
          <br className="hidden sm:block" /> 나머지가 따라 만들어집니다.
        </h2>

        <div className="stagger mt-10 grid gap-px overflow-hidden rounded-xl border border-border bg-border sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((step) => (
            <div key={step.title} className="step-cell bg-card p-6">
              <span className="step-no">{step.no}</span>
              <step.icon className="mt-5 h-6 w-6 text-accent" aria-hidden />
              <h3 className="mt-4 font-semibold">{step.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{step.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── 이런 것이 나옵니다 ─────────────────────────────────── */}
      <section className="showcase-band py-16 sm:py-20">
        <div className="container">
          <p className="section-eyebrow text-accent/90">결과물</p>
          <div className="mt-3 flex flex-wrap items-end justify-between gap-4">
            <h2 className="max-w-xl font-serif text-2xl font-bold leading-snug tracking-tight text-white sm:text-3xl">
              고르시기만 하면
              <br className="hidden sm:block" /> 예술회관 포스터가 나옵니다.
            </h2>
            <p className="text-sm text-white/60">인쇄물 75종 · 테마 108종 · 전부 인터넷 없이</p>
          </div>

          <ul className="stagger mt-9 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
            {SHOWCASE.map((art) => (
              <li key={art.src} className="showcase-card">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={art.src} alt={art.name} className="block w-full" loading="lazy" />
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* ── 진행 중인 행사 ─────────────────────────────────────── */}
      <section className="container py-16 sm:py-20">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-serif text-2xl font-bold tracking-tight">진행 중인 행사</h2>
          <Link
            href="/events"
            className="nudge press inline-flex items-center gap-1.5 rounded-md px-1 text-sm font-medium text-muted-foreground hover:text-foreground"
          >
            전체 보기 <ArrowRight className="h-4 w-4" aria-hidden />
          </Link>
        </div>

        {upcoming.length === 0 ? (
          <Card>
            <CardContent className="py-14 text-center">
              <p className="text-sm text-muted-foreground">아직 등록된 행사가 없습니다.</p>
              <Link href="/events/new" className="mt-4 inline-block">
                <Button>첫 연주회 만들기</Button>
              </Link>
            </CardContent>
          </Card>
        ) : (
          <div className="stagger grid gap-4 md:grid-cols-3">
            {upcoming.map((event) => (
              <Link key={event.id} href={`/events/${event.id}`}>
                <Card interactive className="press event-card h-full">
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
