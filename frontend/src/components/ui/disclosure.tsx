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
    <details className={cn("group rounded-xl border border-border bg-surface", className)} open={defaultOpen}>
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-xs font-medium text-text-soft hover:text-foreground focus-ring [&::-webkit-details-marker]:hidden">
        <span>{summary}</span>
        <ChevronDown
          className="size-4 shrink-0 text-muted-2 transition-transform group-open:rotate-180"
          aria-hidden="true"
        />
      </summary>
      <div className="border-t border-border px-4 py-3">{children}</div>
    </details>
  );
}
