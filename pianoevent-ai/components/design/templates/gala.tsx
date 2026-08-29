import { LogoSlot } from '@/components/design/logo'
import { PhotoFullBleed } from '@/components/design/photo'
import { Bokeh, GrandPiano, HallArch, KeysPerspective, Laurel, StaffFlow, StageBeams } from '@/components/design/scenery'
import { Sheet, type as T } from '@/components/design/sheet'
import { dateParts } from '@/components/design/templates/posters'
import { fitTitle } from '@/lib/design/fit'
import type { DesignContext } from '@/lib/design/context'

/**
 * 명품 연주회 포스터.
 *
 * 기존 포스터들은 깔끔했지만 "상장" 처럼 보였다 — 가운데가 비고, 무엇에 관한 종이인지
 * 그림으로는 알 수 없었다. 예술회관 포스터가 왜 다른가를 뜯어보면 늘 같은 셋이다.
 *
 *   1. **큰 그림 하나**가 종이를 지배한다
 *   2. 제목이 아주 크고, 그 둘레가 시원하게 비어 있다
 *   3. 어둠에서 빛으로 번지는 **깊이**가 있다
 *
 * 그래서 여기 있는 것들은 하나같이 그림이 종이의 절반 가까이를 차지하고, 제목은
 * 기존보다 두 배 가까이 크며, 설명글은 최소한만 남긴다. 원장님이 하실 일은 없다 —
 * 명단과 날짜는 이미 들어 있고, 고르시기만 하면 된다.
 */


/**
 * 어두운 무대 바탕.
 *
 * 처음에는 테마의 머리띠 색(`--d-band`)에서 바탕을 끌어왔는데, 그 색이 밝은 테마
 * (금색·아이보리)에서는 바탕이 환해지고 글씨가 어두운 채로 남아 **제목이 안 읽혔다.**
 * 108종 중 어느 것을 고르셔도 결과가 좋아야 하므로, 이 포스터들은 **제 색을 가진다.**
 *
 *   · 바탕은 늘 깊은 어둠. 테마의 강조색을 아주 옅게 섞어 테마마다 공기만 달라진다
 *   · 글씨는 늘 밝은 상아색 — 대비를 셈할 필요가 없다
 *   · 강조색은 밝은 쪽으로 끌어올린다. 남색·먹빛 같은 어두운 강조색도 어둠 위에서 보인다
 */
function DarkGround({ children, glow = '50% 8%' }: { children: React.ReactNode; glow?: string }) {
  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        overflow: 'hidden',
        background: `radial-gradient(130% 95% at ${glow}, color-mix(in srgb, var(--d-accent) 17%, #16141d) 0%, #0c0b12 44%, #050509 100%)`,
        ['--g-ink' as string]: '#f7f3ea',
        ['--g-dim' as string]: 'rgba(247,243,234,0.72)',
        ['--g-accent' as string]: 'color-mix(in srgb, var(--d-accent) 52%, #f2dda6)',
        color: 'var(--g-ink)',
      }}
    >
      {children}
    </div>
  )
}

/** 작은 대문자 라벨 — 가로로 넓게 벌려야 격이 산다 */
function Eyebrow({ children, color = 'var(--g-accent)' }: { children: React.ReactNode; color?: string }) {
  return (
    <p style={{ fontSize: 12, letterSpacing: '0.42em', color, margin: 0, textTransform: 'uppercase' }}>{children}</p>
  )
}

/** 출연진 한 줄 — 이름만 담백하게. 명단이 길면 줄여 앉힌다 */
function Performers({ ctx, color, size = 12 }: { ctx: DesignContext; color: string; size?: number }) {
  const names = ctx.plan.items.map((i) => i.student.student_name)
  if (names.length === 0) return null
  return (
    <p style={{ fontSize: size, lineHeight: 1.9, color, letterSpacing: '0.06em', margin: 0 }}>
      {names.join('   ·   ')}
    </p>
  )
}

/* ────────────────────────────────────────────────────────────────────────────
 * 1. 그랜드피아노 — 가장 널리 쓰이는 연주회 포스터의 얼굴
 * ──────────────────────────────────────────────────────────────────────────── */
export function GalaPiano({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event, copy } = ctx
  const d = dateParts(event.event_at)

  return (
    <Sheet theme={theme} page="a4-portrait" decorated={false}>
      <DarkGround>
        <div style={{ position: 'absolute', inset: 0, opacity: 0.5 }}>
          <Bokeh width={794} height={300} color="var(--g-accent)" opacity={0.45} />
        </div>

        <div style={{ position: 'relative', height: '100%', padding: '74px 68px 60px', display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <LogoSlot ctx={ctx} height={theme.logo.height} />
            <Eyebrow>{academy.name}</Eyebrow>
          </div>

          <h1 style={{ ...T.display(fitTitle(event.title, 74)), marginTop: 40, lineHeight: 1.1, color: 'var(--g-ink)' }}>{event.title}</h1>
          {copy.subtitle && (
            <p style={{ marginTop: 16, fontSize: 17, letterSpacing: '0.28em', color: 'var(--g-accent)' }}>
              {copy.subtitle}
            </p>
          )}

          <div style={{ marginTop: 34, height: 1, background: 'var(--g-accent)', opacity: 0.55, width: 132 }} />

          <div style={{ marginTop: 30, display: 'flex', alignItems: 'flex-end', gap: 18 }}>
            <span style={{ ...T.display(92, 700), color: 'var(--g-accent)', lineHeight: 0.9 }}>
              {d.month}.{d.day}
            </span>
            <span style={{ fontSize: 14, letterSpacing: '0.2em', paddingBottom: 12, opacity: 0.9 }}>
              {d.year} · {d.weekday}요일 {d.time}
            </span>
          </div>
          {event.venue && (
            <p style={{ marginTop: 12, fontSize: 16, letterSpacing: '0.14em', opacity: 0.92 }}>{event.venue}</p>
          )}

          {/* 피아노는 종이 밖으로 흘러 나간다 — 잘려 나가야 크게 보인다 */}
          <div style={{ position: 'absolute', right: -84, bottom: 132, opacity: 0.95 }}>
            <GrandPiano width={700} color="var(--g-ink)" accent="var(--g-accent)" opacity={0.92} />
          </div>

          <div style={{ marginTop: 'auto', position: 'relative' }}>
            <div style={{ height: 1, background: 'var(--g-accent)', opacity: 0.35 }} />
            <div style={{ marginTop: 14, display: 'flex', justifyContent: 'space-between', gap: 20 }}>
              <div style={{ maxWidth: 420 }}>
                <Eyebrow>출연</Eyebrow>
                <div style={{ marginTop: 8 }}>
                  <Performers ctx={ctx} color="var(--g-ink)" />
                </div>
              </div>
              <p style={{ fontSize: 11, letterSpacing: '0.1em', opacity: 0.7, textAlign: 'right', margin: 0 }}>
                {copy.host}
                {copy.contact ? <><br />{copy.contact}</> : null}
              </p>
            </div>
          </div>
        </div>
      </DarkGround>
    </Sheet>
  )
}

/* ────────────────────────────────────────────────────────────────────────────
 * 2. 건반 — 보는 사람이 피아노 앞에 앉는다
 * ──────────────────────────────────────────────────────────────────────────── */
export function GalaKeys({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event, copy } = ctx
  const d = dateParts(event.event_at)

  return (
    <Sheet theme={theme} page="a4-portrait" decorated={false}>
      <DarkGround>
        <div style={{ position: 'absolute', inset: 0, opacity: 0.6 }}>
          <StageBeams width={794} height={620} color="var(--g-accent)" count={3} />
        </div>

        {/* 글이 건반 위 빈 자리의 가운데에 놓여야 아래위가 벌어지지 않는다 */}
        <div style={{ position: 'relative', height: '100%', padding: '70px 70px 470px', display: 'flex', flexDirection: 'column', justifyContent: 'center', textAlign: 'center', alignItems: 'center' }}>
          <Eyebrow>{academy.name}</Eyebrow>
          <h1 style={{ ...T.display(fitTitle(event.title, 70)), marginTop: 28, lineHeight: 1.12, color: 'var(--g-ink)' }}>{event.title}</h1>
          {copy.subtitle && (
            <p style={{ marginTop: 16, fontSize: 16, letterSpacing: '0.3em', color: 'var(--g-accent)' }}>{copy.subtitle}</p>
          )}

          <div style={{ marginTop: 40, display: 'flex', alignItems: 'center', gap: 20 }}>
            <span style={{ height: 1, width: 56, background: 'var(--g-accent)', opacity: 0.6 }} />
            <span style={{ ...T.display(46, 700), color: 'var(--g-accent)' }}>
              {d.month} · {d.day}
            </span>
            <span style={{ height: 1, width: 56, background: 'var(--g-accent)', opacity: 0.6 }} />
          </div>
          <p style={{ marginTop: 12, fontSize: 14, letterSpacing: '0.22em', opacity: 0.9 }}>
            {d.year} {d.weekday}요일 {d.time}
          </p>
          {event.venue && <p style={{ marginTop: 8, fontSize: 15, letterSpacing: '0.12em', opacity: 0.9 }}>{event.venue}</p>}

          <div style={{ marginTop: 30, maxWidth: 520 }}>
            <Performers ctx={ctx} color="var(--g-ink)" size={11} />
          </div>

          <p style={{ marginTop: 26, fontSize: 11, letterSpacing: '0.1em', opacity: 0.65 }}>{copy.host}</p>
        </div>

        {/* 건반이 종이 아래 절반 가까이를 차지한다 — 가운데가 비면 상장처럼 보인다 */}
        <div style={{ position: 'absolute', insetInline: 0, bottom: 0 }}>
          <KeysPerspective width={794} height={560} color="#08080e" glow="var(--g-accent)" />
        </div>
      </DarkGround>
    </Sheet>
  )
}

/* ────────────────────────────────────────────────────────────────────────────
 * 3. 무대 조명 — 제목이 빛 안에 선다
 * ──────────────────────────────────────────────────────────────────────────── */
export function GalaSpotlight({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event, copy } = ctx
  const d = dateParts(event.event_at)

  return (
    <Sheet theme={theme} page="a4-portrait" decorated={false}>
      <DarkGround>
        <div style={{ position: 'absolute', insetInline: 0, top: 0 }}>
          <StageBeams width={794} height={720} color="var(--g-accent)" count={1} />
        </div>

        <div style={{ position: 'relative', height: '100%', padding: '96px 78px 56px', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>
          <Eyebrow>{academy.name}</Eyebrow>

          <h1 style={{ ...T.display(fitTitle(event.title, 80)), marginTop: 34, lineHeight: 1.06, color: 'var(--g-ink)' }}>{event.title}</h1>
          {copy.subtitle && (
            <p style={{ marginTop: 20, fontSize: 17, letterSpacing: '0.3em', color: 'var(--g-accent)' }}>{copy.subtitle}</p>
          )}

          <div style={{ marginTop: 34, padding: '16px 34px', border: '1px solid var(--g-accent)', borderLeft: 'none', borderRight: 'none' }}>
            <p style={{ ...T.display(34, 700), color: 'var(--g-accent)', margin: 0 }}>
              {d.year}. {d.month}. {d.day}
            </p>
            <p style={{ marginTop: 8, fontSize: 13, letterSpacing: '0.24em', opacity: 0.9, margin: '8px 0 0' }}>
              {d.weekday}요일 {d.time}
              {event.venue ? ` · ${event.venue}` : ''}
            </p>
          </div>

          {/* 빛이 고이는 자리에 피아노가 선다 — 조명만 있으면 가운데가 빈다 */}
          <div style={{ marginTop: 26, opacity: 0.92 }}>
            <GrandPiano width={510} color="var(--g-ink)" accent="var(--g-accent)" opacity={0.9} />
          </div>

          <div style={{ marginTop: 'auto', width: '100%' }}>
            <div style={{ maxWidth: 560, margin: '0 auto' }}>
              <Performers ctx={ctx} color="var(--g-ink)" size={11.5} />
            </div>
            <p style={{ marginTop: 18, fontSize: 11, letterSpacing: '0.1em', opacity: 0.62 }}>{copy.host}</p>
          </div>
        </div>
      </DarkGround>
    </Sheet>
  )
}

/* ────────────────────────────────────────────────────────────────────────────
 * 4. 무대 아치 — 격식 있는 정기 연주회
 * ──────────────────────────────────────────────────────────────────────────── */
export function GalaArch({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event, copy } = ctx
  const d = dateParts(event.event_at)

  return (
    <Sheet theme={theme} page="a4-portrait" decorated={false}>
      <DarkGround>
        <div style={{ position: 'absolute', inset: 0 }}>
          <HallArch width={794} height={1123} color="var(--g-accent)" ink="#05060a" />
        </div>

        <div style={{ position: 'relative', height: '100%', padding: '176px 128px 66px', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>
          <Eyebrow>{academy.name}</Eyebrow>
          <h1 style={{ ...T.display(fitTitle(event.title, 58)), marginTop: 26, lineHeight: 1.16, color: 'var(--g-ink)' }}>{event.title}</h1>
          {copy.subtitle && (
            <p style={{ marginTop: 14, fontSize: 15, letterSpacing: '0.28em', color: 'var(--g-accent)' }}>{copy.subtitle}</p>
          )}

          <div style={{ marginTop: 30, opacity: 0.92 }}>
            <GrandPiano width={330} color="var(--g-ink)" accent="var(--g-accent)" opacity={0.85} />
          </div>

          <p style={{ ...T.display(40, 700), color: 'var(--g-accent)', marginTop: 24 }}>
            {d.month}.{d.day}
          </p>
          <p style={{ marginTop: 8, fontSize: 13, letterSpacing: '0.2em', opacity: 0.9 }}>
            {d.year} {d.weekday}요일 {d.time}
          </p>
          {event.venue && <p style={{ marginTop: 6, fontSize: 14, letterSpacing: '0.1em', opacity: 0.88 }}>{event.venue}</p>}

          {/* 아래 절반이 비면 포스터가 아니라 안내문처럼 보인다. 출연진으로 받쳐 준다 */}
          <div style={{ marginTop: 'auto', width: '100%' }}>
            <Eyebrow>출연</Eyebrow>
            <div style={{ marginTop: 12 }}>
              <Performers ctx={ctx} color="var(--g-ink)" size={11.5} />
            </div>
            <p style={{ marginTop: 20, fontSize: 11, letterSpacing: '0.1em', opacity: 0.65 }}>{copy.host}</p>
          </div>
        </div>
      </DarkGround>
    </Sheet>
  )
}

/* ────────────────────────────────────────────────────────────────────────────
 * 5. 편집형 — 날짜를 큰 숫자로 세운 비대칭 판짜기
 * ──────────────────────────────────────────────────────────────────────────── */
export function GalaEditorial({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event, copy } = ctx
  const d = dateParts(event.event_at)

  return (
    <Sheet theme={theme} page="a4-portrait" decorated={false}>
      <div style={{ position: 'absolute', inset: 0, background: 'var(--d-paper)' }} />
      <div style={{ position: 'absolute', insetInline: 0, top: 0, height: 300, opacity: 0.5 }}>
        <StaffFlow width={794} height={300} color="var(--d-accent)" opacity={0.3} />
      </div>

      <div style={{ position: 'relative', height: '100%', padding: '72px 66px 58px', display: 'flex', flexDirection: 'column' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Eyebrow color="var(--d-muted)">{academy.name}</Eyebrow>
          <LogoSlot ctx={ctx} height={theme.logo.height} />
        </div>

        {/* 큰 숫자 — 이 하나가 편집 디자인의 축이 된다 */}
        <div style={{ marginTop: 40, display: 'flex', alignItems: 'baseline', gap: 26 }}>
          <span style={{ ...T.display(150, 700), color: 'var(--d-accent)', lineHeight: 0.82, letterSpacing: '-0.04em' }}>
            {d.day}
          </span>
          <div>
            <p style={{ ...T.display(30, 700), margin: 0 }}>{d.month}월</p>
            <p style={{ marginTop: 6, fontSize: 13, letterSpacing: '0.2em', color: 'var(--d-muted)', margin: '6px 0 0' }}>
              {d.year} · {d.weekday}요일 {d.time}
            </p>
          </div>
        </div>

        <div style={{ marginTop: 34, height: 3, background: 'var(--d-accent)', width: 96 }} />

        <h1 style={{ ...T.display(fitTitle(event.title, 64)), marginTop: 28, lineHeight: 1.12 }}>{event.title}</h1>
        {copy.subtitle && (
          <p style={{ marginTop: 14, fontSize: 16, letterSpacing: '0.24em', color: 'var(--d-muted)' }}>{copy.subtitle}</p>
        )}
        {event.venue && <p style={{ marginTop: 18, fontSize: 16, fontFamily: 'var(--d-display)' }}>{event.venue}</p>}

        <div style={{ position: 'absolute', left: -40, right: -40, bottom: 132, opacity: 0.95 }}>
          <GrandPiano width={700} color="var(--d-ink)" accent="var(--d-accent)" opacity={0.9} />
        </div>

        <div style={{ marginTop: 'auto', borderTop: '1px solid var(--d-line)', paddingTop: 16 }}>
          <Eyebrow color="var(--d-muted)">출연</Eyebrow>
          <div style={{ marginTop: 8 }}>
            <Performers ctx={ctx} color="var(--d-muted)" />
          </div>
          <p style={{ marginTop: 14, fontSize: 11, letterSpacing: '0.08em', color: 'var(--d-muted)' }}>
            {copy.host}
            {copy.contact ? ` · ${copy.contact}` : ''}
          </p>
        </div>
      </div>
    </Sheet>
  )
}

/* ────────────────────────────────────────────────────────────────────────────
 * 6. 사진 전면 — 학원 사진이 있으면 그것이 주인공
 * ──────────────────────────────────────────────────────────────────────────── */
export function GalaPhoto({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event, copy } = ctx
  const d = dateParts(event.event_at)

  return (
    <Sheet theme={theme} page="a4-portrait" decorated={false}>
      <DarkGround>
        {ctx.photoUrl ? (
          <PhotoFullBleed ctx={ctx} />
        ) : (
          <div style={{ position: 'absolute', inset: 0, opacity: 0.75 }}>
            <StageBeams width={794} height={760} color="var(--g-accent)" count={2} />
          </div>
        )}
        {/* 사진 위에 글을 얹으려면 어두운 막이 있어야 읽힌다 */}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background: 'linear-gradient(180deg, rgba(4,5,9,.72) 0%, rgba(4,5,9,.35) 38%, rgba(4,5,9,.92) 100%)',
          }}
        />

        <div style={{ position: 'relative', height: '100%', padding: '70px 66px 60px', display: 'flex', flexDirection: 'column' }}>
          <Eyebrow>{academy.name}</Eyebrow>

          <div style={{ marginTop: 'auto' }}>
            <h1 style={{ ...T.display(fitTitle(event.title, 76)), lineHeight: 1.08, color: '#fff' }}>{event.title}</h1>
            {copy.subtitle && (
              <p style={{ marginTop: 16, fontSize: 16, letterSpacing: '0.3em', color: 'var(--g-accent)' }}>
                {copy.subtitle}
              </p>
            )}
            <div style={{ marginTop: 26, height: 1, background: 'rgba(255,255,255,.35)' }} />
            <div style={{ marginTop: 18, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 20 }}>
              <div>
                <p style={{ ...T.display(42, 700), color: 'var(--g-accent)', margin: 0 }}>
                  {d.month}.{d.day}
                </p>
                <p style={{ marginTop: 8, fontSize: 13, letterSpacing: '0.18em', color: 'rgba(255,255,255,.86)', margin: '8px 0 0' }}>
                  {d.year} {d.weekday}요일 {d.time}
                  {event.venue ? ` · ${event.venue}` : ''}
                </p>
              </div>
              <p style={{ fontSize: 11, letterSpacing: '0.1em', color: 'rgba(255,255,255,.7)', textAlign: 'right', margin: 0 }}>
                {copy.host}
              </p>
            </div>
          </div>
        </div>
      </DarkGround>
    </Sheet>
  )
}

/* ────────────────────────────────────────────────────────────────────────────
 * 7. 월계관 — 콩쿠르 · 정기 연주회의 격
 * ──────────────────────────────────────────────────────────────────────────── */
export function GalaLaurel({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event, copy } = ctx
  const d = dateParts(event.event_at)

  return (
    <Sheet theme={theme} page="a4-portrait" decorated={false}>
      <div style={{ position: 'absolute', inset: 0, background: 'var(--d-paper)' }} />
      <div style={{ position: 'absolute', inset: 30, border: '1px solid var(--d-accent)', opacity: 0.5 }} />
      <div style={{ position: 'absolute', inset: 38, border: '3px solid var(--d-accent)', opacity: 0.22 }} />

      <div style={{ position: 'relative', height: '100%', padding: '74px 84px 60px', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>
        <LogoSlot ctx={ctx} height={theme.logo.height} />
        <p style={{ ...T.label(11), marginTop: 16 }}>{academy.name}</p>

        {/* 월계관 안에 연도를 앉힌다 — 콩쿠르 포스터의 문법 */}
        <div style={{ marginTop: 26, position: 'relative', width: 230, height: 230 }}>
          <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Laurel width={230} color="var(--d-accent)" />
          </div>
          <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
            <span style={{ ...T.display(44, 700), color: 'var(--d-accent)', lineHeight: 1 }}>{d.year}</span>
            <span style={{ fontSize: 11, letterSpacing: '0.3em', color: 'var(--d-muted)', marginTop: 8 }}>
              {d.month}.{d.day}
            </span>
          </div>
        </div>

        <h1 style={{ ...T.display(fitTitle(event.title, 56)), marginTop: 24, lineHeight: 1.16 }}>{event.title}</h1>
        {copy.subtitle && (
          <p style={{ marginTop: 14, fontSize: 15, letterSpacing: '0.26em', color: 'var(--d-muted)' }}>{copy.subtitle}</p>
        )}
        <p style={{ marginTop: 18, fontSize: 15, fontFamily: 'var(--d-display)' }}>
          {d.weekday}요일 {d.time}
          {event.venue ? ` · ${event.venue}` : ''}
        </p>

        <div style={{ marginTop: 26, width: 220, height: 1, background: 'var(--d-accent)', opacity: 0.45 }} />

        <div style={{ marginTop: 22, maxWidth: 520 }}>
          <Performers ctx={ctx} color="var(--d-muted)" size={11.5} />
        </div>

        {/* 아래 절반이 비면 상장이 된다 — 피아노가 받쳐 준다 */}
        <div style={{ marginTop: 26, opacity: 0.9 }}>
          <GrandPiano width={430} color="var(--d-ink)" accent="var(--d-accent)" opacity={0.88} />
        </div>

        <p style={{ marginTop: 'auto', fontSize: 11, letterSpacing: '0.1em', color: 'var(--d-muted)' }}>{copy.host}</p>
      </div>
    </Sheet>
  )
}

/* ────────────────────────────────────────────────────────────────────────────
 * 8. 여백형 — 비운 자리가 격을 만든다
 * ──────────────────────────────────────────────────────────────────────────── */
export function GalaMinimal({ ctx }: { ctx: DesignContext }) {
  const { theme, academy, event, copy } = ctx
  const d = dateParts(event.event_at)

  return (
    <Sheet theme={theme} page="a4-portrait" decorated={false}>
      <div style={{ position: 'absolute', inset: 0, background: 'var(--d-paper)' }} />

      <div style={{ position: 'relative', height: '100%', padding: '96px 74px 64px', display: 'flex', flexDirection: 'column' }}>
        <Eyebrow color="var(--d-muted)">{academy.name}</Eyebrow>

        <h1 style={{ ...T.display(fitTitle(event.title, 92)), marginTop: 118, lineHeight: 1.04, letterSpacing: '-0.03em' }}>{event.title}</h1>

        <div style={{ marginTop: 42, height: 1, background: 'var(--d-ink)', opacity: 0.85, width: 200 }} />

        <p style={{ marginTop: 30, fontSize: 19, letterSpacing: '0.06em', fontFamily: 'var(--d-display)' }}>
          {d.year}.{d.month}.{d.day} {d.weekday} {d.time}
        </p>
        {event.venue && (
          <p style={{ marginTop: 10, fontSize: 17, letterSpacing: '0.04em', color: 'var(--d-muted)' }}>{event.venue}</p>
        )}
        {copy.subtitle && (
          <p style={{ marginTop: 22, fontSize: 14, letterSpacing: '0.26em', color: 'var(--d-accent)' }}>{copy.subtitle}</p>
        )}

        {/* 피아노를 아주 옅게, 오른쪽 아래에 — 있는 듯 없는 듯 */}
        {/* 있는 듯 없는 듯 — 진하면 얼룩처럼 보이고, 아주 옅으면 종이의 결이 된다 */}
        <div style={{ position: 'absolute', right: -70, bottom: 92, opacity: 0.055 }}>
          <GrandPiano width={620} color="var(--d-ink)" accent="var(--d-ink)" />
        </div>

        <div style={{ marginTop: 'auto', position: 'relative' }}>
          <Performers ctx={ctx} color="var(--d-muted)" size={11} />
          <p style={{ marginTop: 16, fontSize: 11, letterSpacing: '0.08em', color: 'var(--d-muted)' }}>{copy.host}</p>
        </div>
      </div>
    </Sheet>
  )
}
