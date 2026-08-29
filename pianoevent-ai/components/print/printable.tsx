"use client";

import { ChevronDown, Eye, FileCheck2, Printer, Type } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { printNow } from "@/components/print/print-now";
import { PrintSummary } from "@/components/print/print-summary";
import {
  PRINT_CHECKLIST,
  PRINT_TEXT_SIZES,
  firstPageClipPx,
  fitScale,
  getPaper,
  pageBreakOffsets,
  sheetsNeeded,
  totalSheets,
} from "@/lib/print/paper";
import { cn } from "@/lib/utils";

/**
 * 인쇄할 것을 감싸는 상자.
 *
 * 하는 일은 셋이다.
 *  1. 뽑기 전에 **종이 몇 장**이 나오는지 알려 준다
 *  2. [종이로 보기] 를 누르면 종이 모양 그대로, 잘리는 자리에 점선을 그어 보여 준다
 *  3. 인쇄 대화상자에서 만질 것 네 줄을 적어 둔다 (배율·여백·배경 그래픽)
 *
 * 이 셋이 없어서 원장님은 뽑고 나서야 아셨다. 100부를 뽑고 나서.
 */
export function Printable({
  paperId = "a4-portrait",
  marginMm = 14,
  what,
  children,
}: {
  paperId?: string;
  /** 인쇄 여백(mm). 0 이면 디자인 안에서 여백을 잡는 인쇄물이다 */
  marginMm?: number;
  /** "순서지" 처럼, 무엇을 뽑는지 */
  what: string;
  children: React.ReactNode;
}) {
  const paper = getPaper(paperId);
  const marginPx = Math.round((marginMm / 25.4) * 96);

  const bodyRef = useRef<HTMLDivElement>(null);
  const frameRef = useRef<HTMLDivElement>(null);
  const [height, setHeight] = useState(0);
  const [scale, setScale] = useState(1);
  const [preview, setPreview] = useState(false);
  const [howto, setHowto] = useState(false);
  const [copies, setCopies] = useState(1);
  /**
   * 종이 위 글씨 크기.
   *
   * 화면 글씨는 머리띠에서 키우실 수 있는데, 정작 **종이**가 안 보이신다는 분이 계신다.
   * 관객석은 어둡고 순서지는 작다. 키우면 줄이 늘어 장수가 느는데, 그 장수는
   * 아래에서 실제 높이로 재고 있으므로 저절로 맞는다.
   */
  const [textSize, setTextSize] =
    useState<(typeof PRINT_TEXT_SIZES)[number]["id"]>("normal");
  const textScale =
    PRINT_TEXT_SIZES.find((item) => item.id === textSize)?.scale ?? 1;

  // 내용 높이와 창 너비는 둘 다 변한다 — 글꼴이 늦게 오거나 창을 줄이시면.
  useEffect(() => {
    const measure = () => {
      if (bodyRef.current) setHeight(bodyRef.current.scrollHeight);
      if (frameRef.current)
        setScale(fitScale(frameRef.current.clientWidth, paper));
    };
    measure();
    const observer = new ResizeObserver(measure);
    if (bodyRef.current) observer.observe(bodyRef.current);
    if (frameRef.current) observer.observe(frameRef.current);
    window.addEventListener("resize", measure);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, [paper, preview]);

  const sheets = sheetsNeeded(height, paper, marginPx);
  const cuts = pageBreakOffsets(height, paper, marginPx);

  return (
    <div
      className="grid gap-4"
      style={{
        ["--first-page-h" as string]: `${firstPageClipPx(paper, marginPx)}px`,
      }}
    >
      <div
        className="rounded-lg border border-border bg-card p-3 no-print"
        data-testid="print-bar"
        data-sheets={sheets}
      >
        <div className="flex flex-wrap items-center gap-2">
          <p className="mr-auto text-sm">
            <strong>{what}</strong> · {paper.label} ·{" "}
            <span data-testid="print-sheets">종이 {sheets}장</span>
            {copies > 1 && (
              <span className="text-muted-foreground">
                {" "}
                · {copies}부면 {totalSheets(sheets, copies)}장
              </span>
            )}
            {textSize !== "normal" && (
              <span className="text-muted-foreground">
                {" "}
                · 글씨를 키워 장수를 다시 셌습니다
              </span>
            )}
          </p>

          <label className="flex items-center gap-1.5 text-sm text-muted-foreground">
            부수
            <input
              type="number"
              min={1}
              max={500}
              value={copies}
              onChange={(e) =>
                setCopies(
                  Math.max(1, Math.min(500, Number(e.target.value) || 1)),
                )
              }
              className="h-8 w-16 rounded-md border border-border bg-background px-2 text-sm"
              aria-label="몇 부 뽑으실지"
            />
          </label>

          <div
            className="flex items-center gap-0.5 rounded-md border border-border p-0.5"
            data-testid="print-text-size"
          >
            <Type
              className="ml-1 h-3.5 w-3.5 text-muted-foreground"
              aria-hidden
            />
            {PRINT_TEXT_SIZES.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setTextSize(item.id)}
                aria-pressed={item.id === textSize}
                className={cn(
                  "rounded px-2 py-1 text-xs transition-colors",
                  item.id === textSize
                    ? "bg-primary font-medium text-primary-foreground"
                    : "hover:bg-secondary",
                )}
              >
                {item.label}
              </button>
            ))}
          </div>

          <Button
            variant={preview ? "default" : "outline"}
            size="sm"
            onClick={() => setPreview((on) => !on)}
            aria-pressed={preview}
            data-testid="paper-toggle"
          >
            <Eye className="h-4 w-4" aria-hidden />
            {preview ? "화면으로 보기" : "종이로 보기"}
          </Button>

          {/* 설정이 맞는지는 결국 한 장 뽑아 봐야 아신다. 종이 한 장이 100장을 살린다 */}
          <Button
            variant="outline"
            size="sm"
            onClick={() => printNow(true)}
            data-testid="print-first"
          >
            <FileCheck2 className="h-4 w-4" aria-hidden />첫 장만 뽑아 보기
          </Button>

          <Button size="sm" onClick={() => printNow()} data-testid="print-now">
            <Printer className="h-4 w-4" aria-hidden />
            인쇄 · PDF 저장
          </Button>
        </div>

        {/* 뽑기 직전 마지막 한 줄 — 종이·장수·색·양면 */}
        <PrintSummary paperLabel={paper.label} sheets={sheets} copies={copies} />

        <button
          type="button"
          onClick={() => setHowto((on) => !on)}
          className="mt-2 flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
          aria-expanded={howto}
          data-testid="print-howto-toggle"
        >
          <ChevronDown
            className={cn(
              "h-3.5 w-3.5 transition-transform",
              howto && "rotate-180",
            )}
            aria-hidden
          />
          인쇄 창이 뜨면 무엇을 만지나요?
        </button>
        {howto && (
          <dl
            className="mt-2 grid gap-1.5 border-t border-border pt-2 text-xs"
            data-testid="print-howto"
          >
            {PRINT_CHECKLIST.map((item) => (
              <div key={item.what} className="sm:flex sm:gap-2">
                <dt className="shrink-0 font-medium sm:w-28">{item.what}</dt>
                <dd className="text-muted-foreground">{item.how}</dd>
              </div>
            ))}
            <p className="pt-1 text-muted-foreground">
              브라우저마다 낱말이 조금씩 다릅니다. 없으면{" "}
              <strong>더보기</strong> 안을 보세요.
            </p>
          </dl>
        )}
      </div>

      {/* 화면으로 볼 때는 그냥 넓게, 종이로 볼 때는 종이 크기에 맞춰 줄여 그린다 */}
      <div ref={frameRef} className={cn(preview && "flex justify-center")}>
        {preview ? (
          <div
            style={{
              width: paper.w * scale,
              height: ((height || paper.h) + marginPx * 2) * scale,
            }}
            className="relative"
            data-testid="paper-preview"
          >
            <div
              style={{
                width: paper.w,
                transform: `scale(${scale})`,
                transformOrigin: "top left",
              }}
              className="absolute left-0 top-0"
            >
              <div
                style={{ padding: marginPx }}
                className="bg-white text-black shadow-[0_1px_12px_rgba(20,20,43,.14)]"
              >
                <div
                  ref={bodyRef}
                  className="print-first-clip"
                  style={{ fontSize: `${textScale}em` }}
                >
                  {children}
                </div>
              </div>

              {/* 잘리는 자리 — 여기서 다음 장으로 넘어갑니다 */}
              {cuts.map((top) => (
                <div
                  key={top}
                  className="pointer-events-none absolute left-0 right-0 border-t-2 border-dashed border-destructive/70"
                  style={{ top: top + marginPx }}
                  data-testid="paper-cut"
                >
                  <span className="absolute right-1 top-1 rounded bg-destructive px-1.5 py-0.5 text-[10px] font-medium text-destructive-foreground">
                    여기서 다음 장
                  </span>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div
            ref={bodyRef}
            className="print-first-clip"
            style={{ fontSize: `${textScale}em` }}
          >
            {children}
          </div>
        )}
      </div>
    </div>
  );
}
