import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function TableShell({
  caption,
  children,
  className,
}: {
  caption: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("surface overflow-hidden", className)}>
      <div className="table-scroll">
        <table className="w-full min-w-[880px] border-collapse text-left text-xs">
          <caption className="sr-only">{caption}</caption>
          {children}
        </table>
      </div>
    </div>
  );
}

export const TH_CLASS =
  "sticky top-0 z-10 whitespace-nowrap border-b border-border bg-surface-2/95 px-3 py-3 text-[10px] font-semibold uppercase tracking-[0.08em] text-muted backdrop-blur-sm";
export const TD_CLASS = "border-b border-border/80 px-3 py-3 align-top text-muted";
export const NUMERIC_TD_CLASS = cn(
  TD_CLASS,
  "text-right font-mono tabular-nums text-text-soft",
);
