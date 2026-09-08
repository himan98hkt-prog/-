import { notFound } from "next/navigation";
import { PlanSummary, PlanTable } from "@/components/event/plan-table";
import { Printable } from "@/components/print/printable";
import { formatEventDate } from "@/lib/format";
import { resolvePlan } from "@/lib/program/resolve";
import { getRepository } from "@/lib/store";

export const dynamic = "force-dynamic";
export const metadata = { title: "순서표 인쇄" };

export default async function ProgramPrintPage({
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
  const { plan } = resolvePlan(students);

  return (
    <div className="min-h-screen bg-muted/40 py-8 print:bg-white print:py-0">
      <div className="mx-auto max-w-[820px] px-4">
        <Printable what="순서지" paperId="a4-portrait" marginMm={14}>
          <article className="print-page bg-white px-12 py-14 shadow-sm print:px-0 print:py-0">
            <header className="border-b-2 border-foreground/80 pb-6 text-center">
              <p className="text-sm tracking-[0.3em] text-muted-foreground">
                {academy?.name ?? ""}
              </p>
              <h1 className="mt-3 font-serif text-3xl font-bold tracking-tight">
                {event.title}
              </h1>
              <p className="mt-3 text-sm text-muted-foreground">
                {formatEventDate(event.event_at)}
                {event.venue ? ` · ${event.venue}` : ""}
              </p>
            </header>

            {event.greeting && (
              <p className="mt-8 whitespace-pre-line text-center text-[15px] leading-relaxed text-muted-foreground">
                {event.greeting}
              </p>
            )}

            <section className="mt-8">
              <PlanTable plan={plan} startISO={event.event_at} />
            </section>

            <section className="mt-8 border-t border-border pt-5">
              <PlanSummary plan={plan} startISO={event.event_at} />
            </section>

            <footer className="mt-10 text-center text-xs text-muted-foreground">
              {academy?.name}
              {academy?.director_name ? ` · 원장 ${academy.director_name}` : ""}
            </footer>
          </article>
        </Printable>
      </div>
    </div>
  );
}
