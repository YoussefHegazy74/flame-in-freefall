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
        <table className="w-full min-w-[900px] border-collapse text-left text-xs">
          <caption className="sr-only">{caption}</caption>
          {children}
        </table>
      </div>
    </div>
  );
}

export const TH_CLASS =
  "sticky top-0 z-10 whitespace-nowrap border-b border-navy-700/80 bg-navy-900/95 px-3 py-2.5 font-mono text-[10px] font-semibold uppercase tracking-[0.1em] text-ink-400";
export const TD_CLASS = "border-b border-navy-800/80 px-3 py-2.5 align-top text-ink-300";
export const NUMERIC_TD_CLASS = cn(TD_CLASS, "text-right font-mono tabular-nums text-ink-200");
