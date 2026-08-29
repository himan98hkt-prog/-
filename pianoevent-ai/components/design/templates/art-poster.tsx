import { LogoSlot } from '@/components/design/logo'
import { Sheet, type as T } from '@/components/design/sheet'
import { dateParts } from '@/components/design/templates/posters'
import { getPosterArt, type PosterArt } from '@/lib/design/art'
import type { DesignContext } from '@/lib/design/context'
import { fitTitle } from '@/lib/design/fit'

/**
 * 그림 한 장으로 가는 포스터.
 *
 * 예술회관 포스터를 뜯어보면 늘 셋이다 — **큰 그림 하나**, 아주 큰 제목, 시원한 여백.
 * 그림은 밖에서 만들어 넣고(`lib/design/art.ts`), 여기서는 그 위에 글만 앉힌다.
 *
 * 양식마다 따로 짜지 않고 **하나로 쓴다.** 그림마다 비어 있는 쪽이 다르므로
 * 글이 앉을 자리(`anchor`)와 막의 진하기(`scrim`)만 그림 쪽에 적어 둔다.
 * 그림을 더 넣으실 때 이 파일은 건드리실 것이 없다.
 */

/** 어두운 그림 위에서는 글씨 색을 테마에서 끌어오지 않는다 — 밝은 테마에서 글씨가 사라진다 */
function palette(art: PosterArt) {
  if (art.tone === 'dark') {
    return {
      ink: '#f8f4ec',
      dim: 'rgba(248,244,236,0.78)',
      // 남색·먹빛처럼 어두운 강조색도 어둠 위에서 보이도록 밝은 쪽으로 끌어올린다
      accent: 'color-mix(in srgb, var(--d-accent) 38%, #f2dda6)',
      rule: 'rgba(242,221,166,0.5)',
      eyebrow: undefined as string | undefined,
    }
  }
  // 밝은 **사진** 위에서는 흐린 색이 사진에 먹힌다. 보조 글씨도 본문 색으로 올린다
  if (art.fill === 'cover') {
    return {
      ink: 'var(--d-ink)',
      dim: 'var(--d-ink)',
      accent: 'var(--d-accent)',
      rule: 'var(--d-line)',
      eyebrow: 'var(--d-ink)',
    }
  }
  // 밝은 그림은 흰 종이에 그린 것이라 테마 색이 그대로 산다
  return {
    ink: 'var(--d-ink)',
    dim: 'var(--d-muted)',
    accent: 'var(--d-accent)',
    rule: 'var(--d-line)',
  }
}

const ALIGN: Record<PosterArt['anchor'], 'flex-start' | 'flex-end' | 'center'> = {
  'top-left': 'flex-start',
  'top-right': 'flex-end',
  'top-center': 'center',
}

const TEXT_ALIGN: Record<PosterArt['anchor'], 'left' | 'right' | 'center'> = {
  'top-left': 'left',
  'top-right': 'right',
  'top-center': 'center',
}

/** 출연진 한 줄 — 이름만. 없으면 통째로 빠진다 */
function Performers({ ctx, color, size = 11.5 }: { ctx: DesignContext; color: string; size?: number }) {
  const names = ctx.plan.items.map((i) => i.student.student_name)
  if (names.length === 0) return null
  return (
    <p style={{ fontSize: size, lineHeight: 1.95, color, letterSpacing: '0.05em', margin: 0 }}>
      {names.join('   ·   ')}
    </p>
  )
}

export function ArtPoster({ ctx, artId }: { ctx: DesignContext; artId: string }) {
  const art = getPosterArt(artId)
  const { theme, academy, event, copy } = ctx
  const d = dateParts(event.event_at)
  const c = palette(art)
  const align = ALIGN[art.anchor]
  const textAlign = TEXT_ALIGN[art.anchor]

  return (
    <Sheet theme={theme} page="a4-portrait" decorated={false}>
      {/*
        그림은 <img> 로 넣는다. 배경으로 깔면 브라우저 인쇄 설정에서 빠질 수 있다.

        어두운 그림은 사진이라 종이를 가득 채운다(cover).
        밝은 그림은 **흰 종이에 그린 수채 한 점**이라 가득 채우면 제목 자리까지 밀고 올라와
        글씨가 그림 위에 얹힌다. 그래서 위아래를 비워 두고 그 안에 담는다(contain).
        비운 자리는 테마 종이색이 그대로 보인다.
      */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={art.src}
        alt=""
        aria-hidden
        style={
          art.tone === 'dark' || art.fill === 'cover'
            ? { position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }
            : {
                position: 'absolute',
                top: `${art.inset?.top ?? 25}%`,
                bottom: `${art.inset?.bottom ?? 13}%`,
                left: 0,
                right: 0,
                width: '100%',
                height: `${100 - (art.inset?.top ?? 25) - (art.inset?.bottom ?? 13)}%`,
                objectFit: 'contain',
                // 흰 바탕을 곱하기로 겹치면 테마 종이색이 그대로 비친다
                mixBlendMode: 'multiply',
              }
        }
      />

      {art.scrim > 0 && (
        <div
          aria-hidden
          style={{
            position: 'absolute',
            inset: 0,
            background: (() => {
              // 밝은 사진에는 흰 막, 어두운 사진에는 검은 막
              const c = art.scrimTone === 'light' ? '255,253,248' : '6,6,10'
              const foot = art.scrimTone === 'light' ? 0.82 : 0.6
              return `linear-gradient(to bottom, rgba(${c},${art.scrim}) 0%, rgba(${c},${(
                art.scrim * 0.7
              ).toFixed(3)}) 34%, rgba(${c},0) 64%),
              linear-gradient(to top, rgba(${c},${foot}) 0%, rgba(${c},${(foot * 0.45).toFixed(
                3,
              )}) 16%, rgba(${c},0) 34%)`
            })(),
          }}
        />
      )}

      <div
        style={{
          position: 'relative',
          height: '100%',
          padding: '68px 62px 56px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: align,
          textAlign,
          color: c.ink,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 13, flexDirection: art.anchor === 'top-right' ? 'row-reverse' : 'row' }}>
          <LogoSlot ctx={ctx} height={theme.logo.height} />
          <p style={{ fontSize: 12, letterSpacing: '0.4em', color: c.eyebrow ?? c.accent, margin: 0 }}>{academy.name}</p>
        </div>

        <h1
          style={{
            ...T.display(fitTitle(event.title, 68)),
            marginTop: 34,
            lineHeight: 1.12,
            color: c.ink,
            maxWidth: 620,
          }}
        >
          {event.title}
        </h1>

        {copy.subtitle && (
          <p style={{ marginTop: 15, fontSize: 16, letterSpacing: '0.28em', color: c.accent }}>{copy.subtitle}</p>
        )}

        <div style={{ marginTop: 30, height: 1, width: 120, background: c.rule }} />

        <div style={{ marginTop: 26, display: 'flex', alignItems: 'flex-end', gap: 16, flexDirection: art.anchor === 'top-right' ? 'row-reverse' : 'row' }}>
          <span style={{ ...T.display(74, 700), color: c.accent, lineHeight: 0.9 }}>
            {d.month}.{d.day}
          </span>
          <span style={{ fontSize: 13.5, letterSpacing: '0.18em', paddingBottom: 10, color: c.dim }}>
            {d.year} · {d.weekday}요일 {d.time}
          </span>
        </div>
        {event.venue && (
          <p style={{ marginTop: 12, fontSize: 15.5, letterSpacing: '0.12em', color: c.ink }}>{event.venue}</p>
        )}

        {/* 아래를 비워 두면 포스터가 아니라 안내문처럼 보인다. 출연진으로 받쳐 준다 */}
        <div style={{ marginTop: 'auto', width: '100%', textAlign: art.anchor === 'top-right' ? 'right' : 'left' }}>
          <div style={{ height: 1, background: c.rule, opacity: 0.6 }} />
          <div style={{ marginTop: 13 }}>
            <Performers ctx={ctx} color={c.dim} />
          </div>
          <p style={{ marginTop: 14, fontSize: 11, letterSpacing: '0.1em', color: c.dim }}>
            {copy.host}
            {copy.contact ? <>{'  ·  '}{copy.contact}</> : null}
          </p>
        </div>
      </div>
    </Sheet>
  )
}
