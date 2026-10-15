'use client'

import { Sparkles } from 'lucide-react'
import { useState } from 'react'
import { CopyButton } from '@/components/copy-button'
import { PrintTips } from '@/components/print/print-tips'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { FieldHint, Input, Label, Textarea } from '@/components/ui/field'
import type { SeasonPack } from '@/lib/season/types'
import { SEASON_LABEL, type SeasonTheme } from '@/lib/types'
import { cn } from '@/lib/utils'

const THEME_STYLE: Record<SeasonTheme, string> = {
  halloween: 'from-orange-500/15 to-purple-500/10',
  christmas: 'from-emerald-600/15 to-red-500/10',
  vacation: 'from-sky-500/15 to-amber-400/10',
}

const THEME_EMOJI: Record<SeasonTheme, string> = {
  halloween: '🎃',
  christmas: '🎄',
  vacation: '☀️',
}

export function SeasonStudio({ initialPack }: { initialPack: SeasonPack }) {
  const [pack, setPack] = useState<SeasonPack>(initialPack)
  const [theme, setTheme] = useState<SeasonTheme>(initialPack.theme)
  const [weeks, setWeeks] = useState(4)
  const [target, setTarget] = useState('초등 저·중학년')
  const [focus, setFocus] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function generate() {
    setPending(true)
    setError(null)
    try {
      const res = await fetch('/api/season', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ theme, weeks, target, focus }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error ?? '특강 팩을 만들지 못했습니다.')
      setPack(data.pack as SeasonPack)
    } catch (e) {
      setError(e instanceof Error ? e.message : '특강 팩을 만들지 못했습니다.')
    } finally {
      setPending(false)
    }
  }

  const planText = [
    `${pack.title}`,
    pack.subtitle,
    `대상: ${pack.target}`,
    '',
    ...pack.weeks.map((w) =>
      [
        `${w.week}주차 · ${w.title}`,
        `목표: ${w.goal}`,
        ...w.activities.map((a) => `- ${a}`),
        w.repertoire.length ? `다루는 곡: ${w.repertoire.join(', ')}` : '',
        `과제: ${w.homework}`,
        '',
      ]
        .filter(Boolean)
        .join('\n'),
    ),
  ].join('\n')

  return (
    <div className="grid gap-6">
      <Card className="no-print">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-accent" aria-hidden />
            테마를 고르면 4주 커리큘럼과 활동지가 한 번에 나옵니다
          </CardTitle>
          <CardDescription>주차별 수업 계획서·인쇄용 활동지·학부모 안내 문구까지 함께 만듭니다.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-5">
          <div className="grid gap-3 sm:grid-cols-3">
            {(Object.keys(SEASON_LABEL) as SeasonTheme[]).map((key) => (
              <button
                key={key}
                type="button"
                onClick={() => setTheme(key)}
                aria-pressed={theme === key}
                className={cn(
                  'rounded-lg border bg-gradient-to-br p-4 text-left transition-all',
                  THEME_STYLE[key],
                  theme === key ? 'border-accent ring-2 ring-accent/30' : 'border-border hover:border-accent/50',
                )}
              >
                <span className="text-2xl" aria-hidden>
                  {THEME_EMOJI[key]}
                </span>
                <p className="mt-2 font-semibold">{SEASON_LABEL[key]}</p>
              </button>
            ))}
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <div>
              <Label htmlFor="weeks">주차 수</Label>
              <Input
                id="weeks"
                type="number"
                min={1}
                max={12}
                value={weeks}
                onChange={(e) => setWeeks(Number(e.target.value))}
              />
            </div>
            <div className="sm:col-span-2">
              <Label htmlFor="target">대상</Label>
              <Input id="target" value={target} onChange={(e) => setTarget(e.target.value)} maxLength={80} />
            </div>
          </div>

          <div>
            <Label htmlFor="focus">이번 특강에서 특히 하고 싶은 것 (선택)</Label>
            <Textarea
              id="focus"
              value={focus}
              onChange={(e) => setFocus(e.target.value)}
              maxLength={300}
              placeholder="형제 수강생이 많아 함께 하는 활동을 넣고 싶어요. 마지막 주에는 작은 발표회를 열 예정입니다."
            />
            <FieldHint>비워 두면 표준 커리큘럼으로 만듭니다.</FieldHint>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button onClick={generate} disabled={pending}>
              {pending ? '만드는 중…' : '특강 팩 만들기'}
            </Button>
            <Badge variant={pack.source === 'ai' ? 'accent' : 'outline'}>
              {pack.source === 'ai' ? 'AI 생성' : '기본 커리큘럼 템플릿'}
            </Badge>
            {pack.fallbackReason && <span className="text-xs text-muted-foreground">{pack.fallbackReason}</span>}
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}
        </CardContent>
      </Card>

      <div className="grid gap-2 no-print">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-semibold">{pack.title}</h2>
          <div className="flex gap-2">
            <CopyButton text={planText} label="계획서 복사" />
            <CopyButton text={pack.parentNotice} label="학부모 안내 복사" />
          </div>
        </div>
        {/* 계획서 한 장 + 활동지들. 계획서가 길면 한 장 더 넘어가므로 "안팎" 으로 적는다 */}
        <PrintTips
          what="계획서 · 활동지"
          paperLabel="A4 세로"
          sheets={1 + pack.worksheets.length}
          approx
        />
      </div>

      <article className="print-page surface px-8 py-8">
        <header className="border-b border-border pb-5">
          <p className="text-xs tracking-[0.25em] text-accent">{SEASON_LABEL[pack.theme]}</p>
          <h1 className="mt-2 font-serif text-2xl font-bold tracking-tight">{pack.title}</h1>
          <p className="mt-1.5 text-sm text-muted-foreground">{pack.subtitle}</p>
          <p className="mt-1 text-sm text-muted-foreground">대상 · {pack.target}</p>
        </header>

        <ol className="mt-6 space-y-6">
          {pack.weeks.map((week) => (
            <li key={week.week} className="print-avoid-break border-t border-border/70 pt-5 first:border-0 first:pt-0">
              <div className="flex flex-wrap items-baseline gap-2">
                <span className="rounded-full bg-primary px-2.5 py-0.5 text-xs font-medium text-primary-foreground">
                  {week.week}주차
                </span>
                <h3 className="text-base font-semibold">{week.title}</h3>
              </div>
              <p className="mt-2 text-sm text-muted-foreground">
                <strong className="text-foreground">목표</strong> · {week.goal}
              </p>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
                {week.activities.map((activity) => (
                  <li key={activity}>{activity}</li>
                ))}
              </ul>
              {week.repertoire.length > 0 && (
                <p className="mt-2 text-sm text-muted-foreground">
                  <strong className="text-foreground">다루는 곡</strong> · {week.repertoire.join(' / ')}
                </p>
              )}
              <p className="mt-1 text-sm text-muted-foreground">
                <strong className="text-foreground">과제</strong> · {week.homework}
              </p>
            </li>
          ))}
        </ol>

        <section className="print-avoid-break mt-8 rounded-lg border border-border bg-muted/40 p-5">
          <h3 className="text-sm font-semibold">학부모 안내 문구</h3>
          <p className="mt-2 whitespace-pre-line text-sm leading-relaxed text-muted-foreground">{pack.parentNotice}</p>
        </section>
      </article>

      {pack.worksheets.map((sheet) => (
        <article key={sheet.id} className="print-page print-break surface px-8 py-8">
          <header className="border-b border-border pb-4">
            <p className="text-xs tracking-[0.25em] text-accent">활동지</p>
            <h2 className="mt-2 font-serif text-xl font-bold">{sheet.title}</h2>
            <p className="mt-1.5 text-sm text-muted-foreground">{sheet.instruction}</p>
            <div className="mt-4 flex gap-6 text-sm text-muted-foreground">
              <span>이름 _______________</span>
              <span>날짜 _______________</span>
            </div>
          </header>

          <ol className="mt-6 space-y-5">
            {sheet.questions.map((q, index) => (
              <li key={`${sheet.id}-${index}`} className="print-avoid-break">
                <p className="text-sm font-medium">
                  {index + 1}. {q.prompt}
                </p>
                {q.choices.length > 0 ? (
                  <div className="mt-2 flex flex-wrap gap-4 text-sm text-muted-foreground">
                    {q.choices.map((choice) => (
                      <span key={choice} className="rounded-full border border-border px-3 py-1">
                        {choice}
                      </span>
                    ))}
                  </div>
                ) : (
                  <div className="mt-3 h-8 border-b border-dashed border-border" />
                )}
              </li>
            ))}
          </ol>

          <details className="mt-8 rounded-md border border-border bg-muted/40 p-4 text-sm no-print">
            <summary className="cursor-pointer font-medium">정답 보기 (선생님용)</summary>
            <ul className="mt-2 space-y-1 text-muted-foreground">
              {sheet.questions.map((q, index) => (
                <li key={`${sheet.id}-answer-${index}`}>
                  {index + 1}. {q.answer || '자유 응답'}
                </li>
              ))}
            </ul>
          </details>
        </article>
      ))}
    </div>
  )
}
