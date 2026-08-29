import { ArrowRight, Check } from "lucide-react";
import Link from "next/link";
import {
  REQUIRED_STEPS,
  getStep,
  isDone,
  nextAfter,
  progress,
  stepHref,
  stepTone,
  type FlowState,
  type StepKey,
} from "@/lib/flow/steps";
import { MarkSeen } from "@/components/event/mark-seen";
import { cn } from "@/lib/utils";

/**
 * 모든 화면의 맨 위에 같은 모양으로 붙는 띠.
 *
 * 원장님이 화면을 여실 때마다 세 가지를 즉시 아셔야 한다.
 *   1. **여기가 어디인가** — 화면마다 다른 색과 큰 이름
 *   2. **꼭 해야 하는 것인가** — 필수면 ① ② ③ 번호, 곁들이면 "안 하셔도 됩니다"
 *   3. **어디까지 왔나 · 다음은 무엇인가** — 점 세 개와 다음 단추
 *
 * 셋 다 글이 아니라 **생김새**로 답한다. 글로 적어 두면 안 읽으신다.
 */
export function ScreenHeader({
  step,
  eventId,
  eventTitle,
  state,
  children,
}: {
  step: StepKey;
  eventId: string;
  eventTitle?: string;
  state: FlowState;
  /** 오른쪽에 붙일 것 (내려받기 단추 등) */
  children?: React.ReactNode;
}) {
  const here = getStep(step);
  const tone = stepTone(step);
  const bar = progress(state);
  const next = nextAfter(step, state);
  const done = isDone(step, state);

  return (
    <>
      {/* 어느 화면을 열어 보셨는지 이 컴퓨터에만 적어 둔다 — 구경용 띠에서 남은 것을 짚어 드리려고 */}
      <MarkSeen eventId={eventId} step={step} />

      {/* 화면 전체 바탕도 이 단계의 색으로 아주 옅게 물들인다.
          "여기는 아까 그 화면이 아니다" 를 글이 아니라 색으로 알려 준다. */}
      <style
        dangerouslySetInnerHTML={{
          __html: `body{--screen-bg:${tone.bg}}`,
        }}
      />
      <header
        className="mb-6 overflow-hidden rounded-xl border no-print"
        style={{ background: tone.bg, borderColor: tone.soft }}
        data-testid="screen-header"
        data-step={step}
      >
        {/* 색 띠 — 어느 화면인지 눈으로 먼저 안다 */}
        <div style={{ background: tone.band, height: 6 }} aria-hidden />

        <div className="grid gap-3 p-4 sm:p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="flex flex-wrap items-center gap-2 text-xs">
                {eventTitle && (
                  <Link
                    href={`/events/${eventId}`}
                    className="text-muted-foreground underline-offset-2 hover:underline"
                  >
                    ← {eventTitle}
                  </Link>
                )}
                {here.required ? (
                  <span
                    className="rounded-full px-2 py-0.5 font-semibold text-white"
                    style={{ background: tone.band }}
                  >
                    꼭 하셔야 하는 {here.no}번째
                  </span>
                ) : (
                  <span className="rounded-full border border-border bg-background px-2 py-0.5 text-muted-foreground">
                    안 하셔도 됩니다 · 하시면 더 좋습니다
                  </span>
                )}
                {done && (
                  <span
                    className="flex items-center gap-1 font-medium"
                    style={{ color: tone.ink }}
                  >
                    <Check className="h-3.5 w-3.5" aria-hidden />
                    끝났습니다
                  </span>
                )}
              </p>

              <h1 className="mt-1.5 flex items-baseline gap-2 text-2xl font-bold tracking-tight">
                {here.no && (
                  <span className="tabular-nums" style={{ color: tone.band }}>
                    {here.no}.
                  </span>
                )}
                <span style={{ color: tone.ink }}>{here.name}</span>
              </h1>
              <p className="mt-1 text-sm text-muted-foreground">{here.why}</p>
            </div>

            {children && (
              <div className="flex flex-wrap items-center gap-2">
                {children}
              </div>
            )}
          </div>

          <div
            className="flex flex-wrap items-center gap-3 border-t pt-3"
            style={{ borderColor: tone.soft }}
          >
            {/* 점 세 개 — 어디까지 왔는지 */}
            <div
              className="flex items-center gap-1.5"
              data-testid="flow-progress"
              aria-label={`${bar.done} / ${bar.total} 단계`}
            >
              {REQUIRED_STEPS.map((s) => {
                const finished = isDone(s.key, state);
                const current = s.key === step;
                return (
                  <Link
                    key={s.key}
                    href={stepHref(s.key, eventId)}
                    title={s.name}
                    className={cn(
                      "flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs transition-colors",
                      current ? "font-semibold" : "hover:bg-background",
                    )}
                    style={
                      current
                        ? {
                            borderColor: tone.band,
                            background: "#fff",
                            color: tone.ink,
                          }
                        : {
                            borderColor: "transparent",
                            color: finished ? tone.ink : undefined,
                          }
                    }
                  >
                    <span
                      className="flex h-4 w-4 items-center justify-center rounded-full text-[10px] font-bold text-white"
                      style={{
                        background: finished ? tone.band : "hsl(0 0% 78%)",
                      }}
                      aria-hidden
                    >
                      {finished ? "✓" : s.no}
                    </span>
                    {s.short}
                  </Link>
                );
              })}
              <span className="ml-1 text-xs text-muted-foreground">
                {bar.done} / {bar.total}
              </span>
            </div>

            {next && (
              <Link
                href={stepHref(next.key, eventId)}
                className="ml-auto"
                data-testid="flow-next"
              >
                <span
                  className="inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium text-white transition-opacity hover:opacity-90"
                  style={{ background: tone.band }}
                >
                  다음 — {next.no ? `${next.no}. ` : ""}
                  {next.name}
                  <ArrowRight className="h-4 w-4" aria-hidden />
                </span>
              </Link>
            )}
            {!next && bar.allDone && (
              <span
                className="ml-auto text-sm font-medium"
                style={{ color: tone.ink }}
              >
                준비가 끝났습니다. 나머지는 하시면 더 좋은 것들입니다.
              </span>
            )}
          </div>
        </div>
      </header>
    </>
  );
}
