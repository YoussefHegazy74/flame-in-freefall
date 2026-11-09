import type { ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

export function Disclosure({
  summary,
  children,
  className,
  defaultOpen = false,
}: {
  summary: ReactNode;
  children: ReactNode;
  className?: string;
  defaultOpen?: boolean;
}) {
  return (
    <details className={cn("group rounded-xl border border-navy-700/70 bg-navy-900/50", className)} open={defaultOpen}>
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-xs font-medium text-ink-200 hover:text-ink-50 focus-ring [&::-webkit-details-marker]:hidden">
        <span>{summary}</span>
        <ChevronDown
          className="size-4 shrink-0 text-ink-500 transition-transform group-open:rotate-180"
          aria-hidden="true"
        />
      </summary>
      <div className="border-t border-navy-700/60 px-4 py-3">{children}</div>
    </details>
  );
}
