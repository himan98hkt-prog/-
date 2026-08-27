import { StrictMode, useEffect, useMemo, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { renderTemplate } from '@/components/design/render'
import { defaultCopy } from '@/lib/design/context'
import {
  CATEGORY_LABEL,
  DESIGN_TEMPLATES,
  PAGE_PX,
  getTemplate,
  templatesByCategory,
  type TemplateCategory,
} from '@/lib/design/templates'
import {
  DESIGN_THEMES,
  FAMILY_LABEL,
  FAMILY_ORDER,
  getTheme,
  type ThemeFamily,
} from '@/lib/design/themes'
import { formatDuration, formatWallClock, isoAtLocalTime } from '@/lib/format'
import { buildBudget, DEFAULT_BUDGET_ITEMS, formatWon } from '@/lib/ops/budget'
import { buildRehearsal, rehearsalCallMessage } from '@/lib/ops/rehearsal'
import { buildSeating, seatLabel } from '@/lib/ops/seating'
import { diagnoseProgram, ISSUE_LEVEL_LABEL } from '@/lib/program/diagnose'
import { buildProgram } from '@/lib/program/order'
import { CATALOG_SIZE } from '@/lib/program/catalog'
import { parseRoster } from '@/lib/program/roster'
import { buildMcScript } from '@/lib/program/script'
import { StageSlideView } from '@/components/stage/slide'
import { buildStageDeck, STAGE_SLIDE_H, STAGE_SLIDE_W } from '@/lib/stage/deck'
import type { Academy, EventRecord, EventStudent, Rsvp } from '@/lib/types'
import { DEMO_ROSTER, DEMO_RSVPS } from './roster'
import './style.css'

const BUY_URL = 'https://accelssam.com/cart/?add-to-cart=2089'

const ACADEMY: Academy = {
  id: 'demo',
  name: '하모니 피아노학원',
  director_name: '김보람',
  logo_url: null,
  theme_color: '#1f2a44',
  design_theme: null,
  photo_url: null,
  assets: [],
  created_at: '2026-01-01T00:00:00.000Z',
}

const EVENT: EventRecord = {
  id: 'demo',
  academy_id: 'demo',
  title: '제12회 정기 연주회',
  type: 'recital',
  event_at: isoAtLocalTime(21, 15),
  venue: '구민회관 소공연장',
  status: 'published',
  theme: null,
  greeting: '한 해 동안 아이들이 쌓아 온 시간을 부모님께 들려드리는 자리입니다. 서툰 소리에도 따뜻한 박수 부탁드립니다.',
  mc_opening: null,
  mc_closing: null,
  program_source: 'rule',
  program_generated_at: null,
  design_theme: null,
  design_template: null,
  design_copy: null,
  photo_url: null,
  image_map: null,
  created_at: '2026-01-01T00:00:00.000Z',
}

const RSVPS: Rsvp[] = DEMO_RSVPS.map((r, i) => ({
  id: `r${i}`,
  event_id: 'demo',
  parent_name: r.parent,
  student_name: r.student,
  headcount: r.headcount,
  message: null,
  attending: true,
  created_at: '2026-01-01T00:00:00.000Z',
}))

/** 붙여넣은 텍스트 → 앱과 같은 학생 레코드 */
function toStudents(text: string) {
  const { rows, errors, autofilled } = parseRoster(text)
  return {
    autofilled,
    students: rows.map((row, i) => ({
      id: `s${i}`,
      event_id: 'demo',
      student_name: row.student_name,
      piece_title: row.piece_title,
      composer: row.composer,
      duration_sec: row.duration_sec ?? 0,
      level: row.level,
      order_no: null,
      mc_script: null,
      note: row.note,
      created_at: '2026-01-01T00:00:00.000Z',
    })),
    errors,
  }
}

function Stage({
  n,
  title,
  lead,
  children,
  wide = false,
}: {
  n: string
  title: string
  lead: string
  children: React.ReactNode
  wide?: boolean
}) {
  return (
    <section className={wide ? 'stage stage--wide' : 'stage'}>
      <header className="stage__head">
        <span className="stage__n">{n}</span>
        <div>
          <h2>{title}</h2>
          <p>{lead}</p>
        </div>
      </header>
      {children}
    </section>
  )
}

function App() {
  const [text, setText] = useState(DEMO_ROSTER)
  const [templateId, setTemplateId] = useState('poster-classic')
  const [themeId, setThemeId] = useState('classic-navy')
  const [category, setCategory] = useState<TemplateCategory>('poster')
  const [family, setFamily] = useState<ThemeFamily>('classic')

  // 종이는 실제 A4 픽셀로 그린 뒤 축소한다. 좁은 화면에서 잘리지 않게 칸 폭을 재서 배율을 정한다.
  const paperRef = useRef<HTMLDivElement>(null)
  const [column, setColumn] = useState(468)
  useEffect(() => {
    const el = paperRef.current
    if (!el) return
    const measure = () => setColumn(el.clientWidth)
    measure()
    const ro = new ResizeObserver(measure)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const { students, errors, autofilled } = useMemo(() => toStudents(text), [text])
  const plan = useMemo(() => buildProgram(students), [students])
  const script = useMemo(
    () => buildMcScript(plan, { eventTitle: EVENT.title, academyName: ACADEMY.name }),
    [plan],
  )
  const rehearsal = useMemo(() => buildRehearsal(plan), [plan])
  const seating = useMemo(() => buildSeating(RSVPS), [])
  const budget = useMemo(
    () =>
      buildBudget({
        students: plan.items.length,
        families: Math.max(RSVPS.length, plan.items.length),
        guests: RSVPS.reduce((s, r) => s + r.headcount, 0),
        items: DEFAULT_BUDGET_ITEMS,
        academy_share: 0,
      }),
    [plan.items.length],
  )

  const theme = getTheme(themeId)
  const template = getTemplate(templateId)
  const page = PAGE_PX[template.page]

  // 멘트까지 붙인 완성 순서표 — 인쇄물과 점검이 같은 것을 본다
  const planned = useMemo(
    () => ({
      ...plan,
      items: plan.items.map((item) => ({
        ...item,
        student: { ...item.student, mc_script: script.byStudentId[item.student.id] ?? null },
      })),
    }),
    [plan, script],
  )
  const issues = useMemo(() => diagnoseProgram(planned), [planned])

  // 무대 화면 — 순서표에서 바로 만들어진다. 명단을 고치면 슬라이드도 따라 바뀐다.
  const deck = useMemo(() => buildStageDeck(EVENT, planned, ACADEMY.name), [planned])
  const [slideIndex, setSlideIndex] = useState(0)
  const [deckDark, setDeckDark] = useState(true)
  const deckRef = useRef<HTMLDivElement>(null)
  const [deckColumn, setDeckColumn] = useState(720)
  useEffect(() => {
    const el = deckRef.current
    if (!el) return
    const measure = () => setDeckColumn(el.clientWidth)
    measure()
    const ro = new ResizeObserver(measure)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  // 명단을 고쳐 슬라이드 수가 줄면 보고 있던 장이 사라질 수 있다
  useEffect(() => {
    setSlideIndex((i) => Math.min(i, deck.length - 1))
  }, [deck.length])
  const deckScale = Math.min(1, deckColumn / STAGE_SLIDE_W)

  const ctx = {
    theme,
    academy: ACADEMY,
    event: { ...EVENT, mc_opening: script.opening, mc_closing: script.closing },
    plan: planned,
    copy: defaultCopy(ACADEMY, EVENT),
    inviteUrl: 'https://piano.example.com/e/demo',
    logoUrl: null,
    photoUrl: null,
    placeholder: false,
    rsvps: RSVPS,
  }

  const previewWidth = Math.max(220, Math.min(468, column))
  const scale = previewWidth / page.w

  return (
    <>
      <header className="masthead">
        <div className="shell">
          <p className="kicker">피아노학원 연주회 기획 도구</p>
          <h1>
            명단만 있으면
            <br />
            나머지는 이미 끝나 있습니다
          </h1>
          <p className="masthead__lead">
            엑셀에서 학생 명단을 복사해 붙여넣는 순간, 연주 순서와 예상 시각, 곡별 사회자 멘트,
            포스터와 순서지까지 만들어집니다. 아래는 <strong>설명이 아니라 실제 프로그램</strong>입니다.
            지금 이 화면에서 직접 고쳐 보세요.
          </p>
          <div className="masthead__meta">
            <span>설치 없음</span>
            <span>회원가입 없음</span>
            <span>이 페이지 안에서 그대로 동작</span>
          </div>
          <p className="masthead__scope">
            악보는 드리지 않습니다. 곡 선정과 악보는 원장님이 하시던 그대로이고, 이 프로그램은{' '}
            <strong>정해진 곡을 받아</strong> 순서 · 시간 · 멘트 · 인쇄물을 만듭니다.
          </p>
        </div>
      </header>

      <main className="shell">
        <Stage
          n="1"
          title="학생 명단 붙여넣기"
          lead="원장님이 이미 가지고 계신 명단을 그대로 씁니다. 엑셀에서 복사해 붙여넣거나, 지난 행사에서 그대로 가져오거나, 한 명씩 추가합니다. 한 줄만 고쳐 보세요 — 아래가 전부 다시 계산됩니다."
        >
          <textarea
            className="roster"
            value={text}
            spellCheck={false}
            onChange={(e) => setText(e.target.value)}
            aria-label="학생 명단"
          />
          <div className="rowline">
            <span className="tag">{students.length}명 읽음</span>
            {autofilled.length > 0 && (
              <span className="tag tag--fill">곡 사전이 {autofilled.length}곡 채움</span>
            )}
            <button type="button" className="ghost" onClick={() => setText(DEMO_ROSTER)}>
              예시 명단으로 되돌리기
            </button>
          </div>
          <p className="hint">
            <b>직접 해보세요</b> — 아무 줄에서 <b>작곡가와 시간을 지워</b> 보세요. 곡 사전 {CATALOG_SIZE}곡에서
            알아서 다시 채웁니다. 원장님이 적은 값이 있으면 절대 덮어쓰지 않습니다.
          </p>
          {errors.length > 0 && (
            <ul className="notes">
              {errors.slice(0, 4).map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          )}
        </Stage>

        <Stage
          n="2"
          title="연주 순서와 예상 시각"
          lead="오프닝 · 초급 · 중급 · 앙상블 · 피날레로 흐름을 잡고, 곡 사이 전환 시간까지 더해 끝나는 시각을 계산합니다."
        >
          <div className="scroller">
            <table className="grid">
              <thead>
                <tr>
                  <th>순서</th>
                  <th>시각</th>
                  <th>학생</th>
                  <th>연주곡</th>
                  <th className="num">길이</th>
                </tr>
              </thead>
              <tbody>
                {plan.items.map((item) => (
                  <tr key={item.student.id}>
                    <td className="num accent">{item.order_no}</td>
                    <td className="num">{formatWallClock(EVENT.event_at, item.start_offset_sec)}</td>
                    <td className="name">{item.student.student_name}</td>
                    <td>
                      {item.student.piece_title}
                      {item.student.composer && <span className="dim"> · {item.student.composer}</span>}
                    </td>
                    <td className="num dim">{formatDuration(item.duration_sec)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="summary">
            총 러닝타임 <b>{formatDuration(plan.total_sec)}</b> · 연주 {formatDuration(plan.play_sec)} · 종료{' '}
            <b>{formatWallClock(EVENT.event_at, plan.total_sec)}</b>
          </p>
        </Stage>

        <Stage
          n="3"
          title="사회자 대본"
          lead="곡과 작곡가, 학생 메모를 엮어 곡마다 멘트를 씁니다. 원장님이 밤새 쓰던 그 문장입니다."
        >
          <div className="script">
            <p className="script__label">오프닝</p>
            <p className="script__body">{script.opening}</p>
            {plan.items.slice(0, 3).map((item) => (
              <div key={item.student.id}>
                <p className="script__label">
                  {item.order_no}. {item.student.student_name} · {item.student.piece_title}
                </p>
                <p className="script__body">{script.byStudentId[item.student.id]}</p>
              </div>
            ))}
            <p className="script__more">…{plan.items.length}곡 전부 이렇게 만들어집니다</p>
          </div>
        </Stage>

        <Stage
          n="4"
          title="순서표 점검"
          lead="당일 학부모 전화를 부르는 것들을 기계가 먼저 봅니다. 명단을 고치면 이 결과도 바뀝니다."
        >
          {issues.length === 0 ? (
            <p className="clear">걸리는 곳이 없습니다. 이대로 인쇄하셔도 됩니다.</p>
          ) : (
            <ul className="issues">
              {issues.map((issue) => (
                <li key={issue.id} data-level={issue.level}>
                  <div className="issues__top">
                    <b>{issue.title}</b>
                    <span className="pill">{ISSUE_LEVEL_LABEL[issue.level]}</span>
                  </div>
                  <p>{issue.detail}</p>
                  <p className="issues__fix">→ {issue.fix}</p>
                </li>
              ))}
            </ul>
          )}
        </Stage>
      </main>

      <div className="proscenium">
        <div className="shell">
          <Stage
            n="5"
            title="인쇄물"
            lead="양식 40종 × 테마 100종. 고르는 즉시 오른쪽 종이가 바뀝니다. 실제 A4 크기 그대로 그린 것을 축소해 보여 줍니다."
            wide
          >
            <div className="studio">
              <div className="studio__picker">
                <p className="pick__title">양식 {DESIGN_TEMPLATES.length}종</p>
                <div className="chips">
                  {templatesByCategory().map((g) => (
                    <button
                      key={g.category}
                      type="button"
                      className="chip"
                      aria-pressed={g.category === category}
                      onClick={() => setCategory(g.category)}
                    >
                      {CATEGORY_LABEL[g.category]} {g.items.length}
                    </button>
                  ))}
                </div>
                <div className="list">
                  {(templatesByCategory().find((g) => g.category === category)?.items ?? []).map((t) => (
                    <button
                      key={t.id}
                      type="button"
                      className="opt"
                      aria-pressed={t.id === templateId}
                      onClick={() => setTemplateId(t.id)}
                    >
                      <span>{t.name}</span>
                      <span className="dim">{PAGE_PX[t.page].label}</span>
                    </button>
                  ))}
                </div>

                <p className="pick__title">테마 {DESIGN_THEMES.length}종</p>
                <div className="chips">
                  {FAMILY_ORDER.map((f) => (
                    <button
                      key={f}
                      type="button"
                      className="chip"
                      aria-pressed={f === family}
                      onClick={() => setFamily(f)}
                    >
                      {FAMILY_LABEL[f]} {DESIGN_THEMES.filter((t) => t.family === f).length}
                    </button>
                  ))}
                </div>
                <div className="swatches">
                  {DESIGN_THEMES.filter((t) => t.family === family).map((t) => (
                    <button
                      key={t.id}
                      type="button"
                      className="swatch"
                      aria-pressed={t.id === themeId}
                      onClick={() => setThemeId(t.id)}
                      title={t.tagline}
                    >
                      <span className="swatch__chips" aria-hidden>
                        <i style={{ background: t.palette.paper }} />
                        <i style={{ background: t.palette.band }} />
                        <i style={{ background: t.palette.accent }} />
                      </span>
                      {t.name}
                    </button>
                  ))}
                </div>
              </div>

              <div className="studio__paper" ref={paperRef}>
                <div className="paper__frame" style={{ width: previewWidth, height: page.h * scale }}>
                  <div
                    className="paper__scale"
                    style={{ transform: `scale(${scale})`, width: page.w, height: page.h }}
                  >
                    {renderTemplate(templateId, ctx, true)}
                  </div>
                </div>
                <p className="paper__caption">
                  {template.name} · {getTheme(themeId).name} · {page.label}
                </p>
              </div>
            </div>
          </Stage>
        </div>
      </div>

      <main className="shell">
        <Stage
          n="6"
          title="무대 화면 — 연주회장 스크린"
          lead="해마다 파워포인트로 다시 만들던 화면입니다. 순서표에서 16:9 슬라이드가 통째로 만들어집니다. 실제 프로그램에서는 전체화면으로 띄우고 화살표 키로 넘깁니다."
          wide
        >
          <div className="deck">
            <div className="deck__screen" ref={deckRef}>
              <div
                className="deck__scale"
                style={{ transform: `scale(${deckScale})`, width: STAGE_SLIDE_W, height: STAGE_SLIDE_H }}
              >
                <StageSlideView
                  slide={deck[slideIndex]}
                  theme={getTheme(themeId)}
                  academyName={ACADEMY.name}
                  dark={deckDark}
                />
              </div>
            </div>
            <div className="deck__bar">
              <button type="button" onClick={() => setSlideIndex((i) => Math.max(0, i - 1))} disabled={slideIndex === 0}>
                ← 이전
              </button>
              <button
                type="button"
                onClick={() => setSlideIndex((i) => Math.min(deck.length - 1, i + 1))}
                disabled={slideIndex === deck.length - 1}
              >
                다음 →
              </button>
              <span className="num">
                {slideIndex + 1} / {deck.length}
              </span>
              <button type="button" className="ghost" onClick={() => setDeckDark((v) => !v)}>
                {deckDark ? '밝은 화면' : '어두운 화면'}
              </button>
            </div>
            <p className="deck__note">
              다음 화면 — <b>{deck[slideIndex].next || '없음 (마지막)'}</b>
              {' · '}순서를 바꾸면 이 화면도 같이 바뀝니다. 위에서 고른 테마를 그대로 씁니다.
            </p>
          </div>
        </Stage>

        <Stage
          n="7"
          title="원장님이 손으로 하던 계산"
          lead="순서표가 나온 뒤에도 일은 남습니다. 리허설 시각, 참가비, 좌석 — 매번 다시 하던 계산입니다."
        >
          <div className="calc">
            <article>
              <h3>리허설 소집</h3>
              <p className="calc__lead">
                전원을 한 번에 부르면 대기실이 터집니다. 조 단위로 나눠 계산하고, 조마다 보낼 문자를
                만들어 둡니다.
              </p>
              <ul className="calc__list">
                {rehearsal.groups.map((g) => (
                  <li key={g.group}>
                    <b>{g.group}조</b>
                    <span className="num">{formatWallClock(EVENT.event_at, g.call_offset_sec)} 도착</span>
                    <span className="dim">{g.members.map((m) => m.student_name).join(', ')}</span>
                  </li>
                ))}
              </ul>
              <details>
                <summary>1조에 보낼 문자 보기</summary>
                <pre>{rehearsalCallMessage(EVENT, rehearsal.groups[0], ACADEMY.name)}</pre>
              </details>
            </article>

            <article>
              <h3>참가비</h3>
              <p className="calc__lead">
                대관료가 확정되기 전에도 안내는 나가야 합니다. 항목별 예산에서 1인당 원가를 역산합니다.
              </p>
              <dl className="calc__figures">
                <div>
                  <dt>예산 합계</dt>
                  <dd className="num">{formatWon(budget.total)}</dd>
                </div>
                <div>
                  <dt>학생 1인당 원가</dt>
                  <dd className="num">{formatWon(budget.per_student)}</dd>
                </div>
                <div className="calc__hero">
                  <dt>권장 참가비</dt>
                  <dd className="num">{formatWon(budget.suggested_fee)}</dd>
                </div>
              </dl>
              {budget.warnings[0] && <p className="calc__warn">{budget.warnings[0]}</p>}
            </article>

            <article>
              <h3>객석</h3>
              <p className="calc__lead">
                참석 회신을 가정 단위로 붙여 앉히고 앞 두 줄은 연주자석으로 비웁니다. 학부모에게 그대로
                보낼 수 있는 표기로 나옵니다.
              </p>
              <ul className="calc__list">
                {seating.blocks.map((b) => (
                  <li key={`${b.row}-${b.from}`}>
                    <b>{b.student_name}</b>
                    <span className="dim">가족 {b.headcount}명</span>
                    <span className="num accent">{seatLabel(b)}</span>
                  </li>
                ))}
              </ul>
            </article>
          </div>
        </Stage>
      </main>

      <footer className="close">
        <div className="shell">
          <p className="kicker">여기까지가 체험판입니다</p>
          <h2>실제로 쓰실 때 달라지는 것</h2>
          <div className="close__grid">
            <div>
              <b>초대장 링크가 진짜 링크가 됩니다</b>
              <p>단톡방에 올리면 학부모가 눌러 참석 회신을 남기고, 인원이 저절로 쌓입니다.</p>
            </div>
            <div>
              <b>인쇄와 PDF 저장</b>
              <p>지금 보신 종이를 A4 그대로 뽑거나 PDF로 저장합니다. 한 벌 인쇄로 여러 장을 한 번에.</p>
            </div>
            <div>
              <b>이미지 보관함</b>
              <p>
                로고·학원 상징·사진을 끌어다 놓으면 크기까지 알아서 줄입니다. 포스터엔 단체사진, 표지엔 학원
                전경처럼 인쇄물마다 다르게 쓸 수도 있습니다.
              </p>
            </div>
            <div>
              <b>지난 행사에서 명단 가져오기</b>
              <p>
                학원은 학생이 그대로입니다. 이름과 난이도를 그대로 가져오고 곡만 채우면 됩니다. 12명 명단을
                다시 칠 일이 없습니다.
              </p>
            </div>
          </div>
          <a className="cta" href={BUY_URL}>
            피아노 이벤트 솔루션 보러 가기
          </a>
          <p className="close__note">
            체험판은 이 페이지 안에서만 돌아갑니다. 입력하신 내용은 저장되지도, 전송되지도 않습니다.
          </p>
        </div>
      </footer>
    </>
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
