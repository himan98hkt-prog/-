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

/**
 * 글씨 색.
 *
 * **바탕이 무엇인가로 정한다. 테마가 무엇인가로 정하지 않는다.**
 * 이걸 헷갈려서 두 번 사고가 났다 — 밝은 그림을 어두운 테마에 얹었더니 흰 글씨가
 * 밝은 그림 위에 얹혀 대비 1.0:1 로 **아예 안 보였다.** 눈으로는 못 찾았고
 * `npm run verify:poster` 가 2484가지 조합을 재서 찾아냈다.
 *
 *   · 어두운 사진이 바탕 → 늘 밝은 상아색 글씨
 *   · 밝은 그림이 바탕(가득 채움) → 늘 어두운 먹빛 글씨
 *   · 흰 종이에 그린 수채(담아 넣음) → 바탕이 **테마 종이**다. 테마 글씨색이 맞다
 *   · 선화 → 바탕이 테마 종이다. 테마 색 그대로
 *
 * 작은 글씨(출연진·주최)에는 `--d-muted` 를 쓰지 않는다. 그 색은 종이 대비 3:1 만
 * 지키면 되는 색이라, 11px 이름에는 모자란다(4.5:1 이 필요하다).
 */
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

  if (art.tone === 'line') {
    // 선화는 테마 종이 위에 테마 강조색으로 칠한 것이다. 글씨도 테마 색을 그대로 쓴다.
    // 다만 학원 이름만은 **먹빛**으로 둔다 — 그림과 같은 색이라 선 위에 얹히면 묻힌다
    return {
      ink: 'var(--d-ink)',
      dim: 'var(--d-ink)',
      accent: 'var(--d-accent)',
      rule: 'var(--d-line)',
      eyebrow: 'var(--d-ink)' as string | undefined,
    }
  }

  if (art.fill === 'cover') {
    // 밝은 그림이 종이를 가득 채운다. 바탕은 늘 밝으므로 글씨는 늘 어둡다
    return {
      ink: '#1b1712',
      dim: 'rgba(27,23,18,0.82)',
      accent: 'color-mix(in srgb, var(--d-accent) 45%, #4a3618)',
      rule: 'rgba(27,23,18,0.32)',
      eyebrow: '#1b1712' as string | undefined,
    }
  }

  // 흰 종이에 그린 수채를 담아 넣은 것 — 바탕은 테마 종이다
  return {
    ink: 'var(--d-ink)',
    dim: 'var(--d-ink)',
    accent: 'var(--d-accent)',
    rule: 'var(--d-line)',
    eyebrow: undefined as string | undefined,
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
      {art.tone === 'line' ? (
        /*
         * 선화는 **색이 아니라 모양으로** 쓴다.
         * 밝은 곳(금선)만 남기고 검은 곳은 뚫어 낸 뒤, 그 자리를 테마 강조색으로 칠한다.
         * 그래서 한 장이 테마 108종 색으로 다 나온다 — 종이색도 테마 것 그대로다.
         *
         * `mask-mode: luminance` 를 모르는 브라우저에서는 그림이 안 나오고 글씨만 남는다.
         * 깨진 네모를 보여 드리는 것보다 낫다.
         */
        <div
          aria-hidden
          style={{
            position: 'absolute',
            inset: 0,
            background: 'var(--d-accent)',
            opacity: 0.88,
            WebkitMask: `url(${art.src}) center / contain no-repeat`,
            mask: `url(${art.src}) center / contain no-repeat`,
            maskMode: 'luminance',
            ['WebkitMaskMode' as string]: 'luminance',
          }}
        />
      ) : null}

      {/*
        선화 아래쪽에 **종이색 여울**을 깐다.
        선화는 종이를 가득 채우므로 맨 아래 출연진 이름이 그림 위에 얹힌다. 강조색이 진한
        테마(레인보우 플레이)에서 이름 대비가 3.06:1 까지 떨어졌다 — 11px 이름에는 모자란다.
        (`npm run verify:poster` 가 찾았다.)
        그림을 종이색으로 서서히 지우면 이름은 늘 깨끗한 종이 위에 앉는다.
      */}
      {art.tone === 'line' ? (
        <div
          aria-hidden
          style={{
            position: 'absolute',
            inset: 0,
            background:
              'linear-gradient(to top, var(--d-paper) 0%, var(--d-paper) 12%, transparent 30%)',
          }}
        />
      ) : null}

      {art.tone !== 'line' ? (
      /* eslint-disable-next-line @next/next/no-img-element */
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
      ) : null}

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
