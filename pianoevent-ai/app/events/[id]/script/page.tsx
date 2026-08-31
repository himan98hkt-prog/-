import Link from "next/link";
import { notFound } from "next/navigation";
import { CopyButton } from "@/components/copy-button";
import { OrnamentDivider } from "@/components/design/ornaments";
import { Printable } from "@/components/print/printable";
import { getTheme, themeVars } from "@/lib/design/themes";
import { formatEventDate, formatWallClock } from "@/lib/format";
import { resolvePlan } from "@/lib/program/resolve";
import { buildMcScript, buildShortMcScript } from "@/lib/program/script";
import { getRepository } from "@/lib/store";

export const dynamic = "force-dynamic";
export const metadata = { title: "사회자 대본" };

export default async function ScriptPage({
  params,
}: {
  params: { id: string };
}) {
  const repo = getRepository();
  const event = await repo.getEvent(params.id);
  if (!event) notFound();

  const [academy, students] = await Promise.all([
    repo.getAcademy(event.academy_id),
    repo.listStudents(event.id),
  ]);
  const theme = getTheme(event.design_theme ?? academy?.design_theme);
  const { plan } = resolvePlan(students);
  const fallback = buildMcScript(plan, {
    eventTitle: event.title,
    academyName: academy?.name ?? "피아노학원",
  });

  /**
   * 밀렸을 때 그대로 읽는 **짧은 판**.
   *
   * 당일 화면은 "멘트를 줄이세요" 라고 말씀드리는데, 정작 손에 든 종이에는 긴 멘트뿐이었다.
   * 무대 옆에서 어디를 뺄지 눈으로 찾다가 더 늦어진다. 같은 종이에 나란히 찍어 둔다.
   *
   * 원장님이 직접 고쳐 두신 멘트는 짧은 판을 만들 수 없다(무엇을 빼도 되는지 우리가 모른다).
   * 그런 줄은 짧은 판 자리를 비워 두고, 왼쪽 것을 읽으시게 한다.
   */
  const short = buildShortMcScript(plan, {
    eventTitle: event.title,
    academyName: academy?.name ?? "피아노학원",
  });

  const opening = event.mc_opening ?? fallback.opening;
  const closing = event.mc_closing ?? fallback.closing;
  const shortFor = (id: string) =>
    students.find((s) => s.id === id)?.mc_script ? null : (short.byStudentId[id] ?? null);
  const scriptFor = (id: string) =>
    students.find((s) => s.id === id)?.mc_script ??
    fallback.byStudentId[id] ??
    "";

  const fullText = [
    `[오프닝]\n${opening}`,
    ...plan.items.map(
      (item) =>
        `[${item.order_no}. ${item.student.student_name} — ${item.student.piece_title}]\n${scriptFor(item.student.id)}`,
    ),
    `[클로징]\n${closing}`,
  ].join("\n\n");

  return (
    <div className="min-h-screen bg-muted/40 py-8 print:bg-white print:py-0">
      <div className="mx-auto flex max-w-[820px] flex-wrap items-center justify-between gap-2 px-4 pb-4 no-print">
        <Link
          href={`/events/${event.id}`}
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← {event.title}
        </Link>
        <CopyButton text={fullText} label="전체 대본 복사" />
      </div>

      <div className="mx-auto max-w-[820px] px-4">
        <Printable what="사회자 대본" paperId="a4-portrait" marginMm={14}>
          <article
            className="print-page px-12 py-12 shadow-sm print:px-0 print:py-0"
            style={{
              ...themeVars(theme),
              background: "var(--d-paper)",
              color: "var(--d-ink)",
              fontFamily: "var(--d-body)",
            }}
          >
            <header
              className="pb-5 text-center"
              style={{ borderBottom: "1px solid var(--d-line)" }}
            >
              <p
                className="text-[11px] tracking-[0.3em]"
                style={{ color: "var(--d-muted)" }}
              >
                {academy?.name}
              </p>
              <h1
                className="mt-3 text-2xl font-bold tracking-tight"
                style={{ fontFamily: "var(--d-display)" }}
              >
                {event.title} · 사회자 대본
              </h1>
              <p className="mt-2 text-sm" style={{ color: "var(--d-muted)" }}>
                {formatEventDate(event.event_at)}
                {event.venue ? ` · ${event.venue}` : ""} · 총{" "}
                {plan.items.length}곡
              </p>
              <div className="mt-4 flex justify-center">
                <OrnamentDivider id={theme.ornament} width={170} />
              </div>
              <p
                className="mt-3 text-[12px] leading-relaxed"
                style={{ color: "var(--d-muted)" }}
                data-testid="short-guide"
              >
                예정보다 밀리면 <strong style={{ color: "var(--d-accent)" }}>「밀렸을 때」</strong> 줄만
                읽으시면 됩니다. 순서마다 10초쯤 붙습니다.
              </p>
            </header>

            <section className="print-avoid-break mt-8">
              <h2
                className="text-xs font-semibold uppercase tracking-[0.2em]"
                style={{ color: "var(--d-accent)" }}
              >
                오프닝
              </h2>
              <p className="mt-2 whitespace-pre-line text-[15px] leading-loose">
                {opening}
              </p>
              <p
                className="mt-2 rounded border px-3 py-2 text-[13px] leading-relaxed"
                style={{ borderColor: "var(--d-line)", color: "var(--d-muted)" }}
                data-testid="short-opening"
              >
                <strong style={{ color: "var(--d-accent)" }}>밀렸을 때</strong> {short.opening}
              </p>
            </section>

            <ol className="mt-8 space-y-6">
              {plan.items.map((item) => (
                <li
                  key={item.student.id}
                  className="print-avoid-break pt-5"
                  style={{ borderTop: "1px solid var(--d-line)" }}
                >
                  <div className="flex items-baseline justify-between gap-3">
                    <h3
                      className="font-semibold"
                      style={{ fontFamily: "var(--d-display)" }}
                    >
                      {item.order_no}. {item.student.student_name}
                      <span
                        className="ml-2 font-normal"
                        style={{ color: "var(--d-muted)" }}
                      >
                        {item.student.piece_title}
                        {item.student.composer
                          ? ` / ${item.student.composer}`
                          : ""}
                      </span>
                    </h3>
                    <span
                      className="whitespace-nowrap text-xs tabular-nums"
                      style={{ color: "var(--d-muted)" }}
                    >
                      {formatWallClock(event.event_at, item.start_offset_sec)}
                    </span>
                  </div>
                  <p className="mt-2 whitespace-pre-line text-[15px] leading-loose">
                    {scriptFor(item.student.id)}
                  </p>
                  {shortFor(item.student.id) && (
                    <p
                      className="mt-2 rounded border px-3 py-1.5 text-[13px] leading-relaxed"
                      style={{ borderColor: "var(--d-line)", color: "var(--d-muted)" }}
                      data-testid="short-line"
                    >
                      <strong style={{ color: "var(--d-accent)" }}>밀렸을 때</strong>{" "}
                      {shortFor(item.student.id)}
                    </p>
                  )}
                </li>
              ))}
            </ol>

            <section
              className="print-avoid-break mt-8 pt-5"
              style={{ borderTop: "1px solid var(--d-line)" }}
            >
              <h2
                className="text-xs font-semibold uppercase tracking-[0.2em]"
                style={{ color: "var(--d-accent)" }}
              >
                클로징
              </h2>
              <p className="mt-2 whitespace-pre-line text-[15px] leading-loose">
                {closing}
              </p>
              <p
                className="mt-2 rounded border px-3 py-2 text-[13px] leading-relaxed"
                style={{ borderColor: "var(--d-line)", color: "var(--d-muted)" }}
                data-testid="short-closing"
              >
                <strong style={{ color: "var(--d-accent)" }}>밀렸을 때</strong> {short.closing}
              </p>
            </section>
          </article>
        </Printable>
      </div>
    </div>
  );
}
