"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { buttonStyles } from "./button";
import { formatCount } from "@/lib/format";

export function Pagination({
  total,
  limit,
  offset,
  onPageChange,
  label = "records",
}: {
  total: number;
  limit: number;
  offset: number;
  onPageChange: (offset: number) => void;
  label?: string;
}) {
  const page = Math.floor(offset / limit) + 1;
  const pages = Math.max(1, Math.ceil(total / limit));
  const start = total === 0 ? 0 : offset + 1;
  const end = Math.min(offset + limit, total);

  return (
    <nav
      aria-label="Pagination"
      className="flex flex-col gap-3 border-t border-navy-700/70 px-1 pt-4 sm:flex-row sm:items-center sm:justify-between"
    >
      <p className="text-xs text-ink-400" aria-live="polite">
        Showing <span className="text-ink-200">{formatCount(start)}</span>–
        <span className="text-ink-200">{formatCount(end)}</span> of{" "}
        <span className="text-ink-200">{formatCount(total)}</span> {label}
      </p>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => onPageChange(Math.max(0, offset - limit))}
          disabled={offset <= 0}
          className={buttonStyles({ variant: "secondary", size: "sm" })}
          aria-label="Previous page"
        >
          <ChevronLeft className="size-3.5" aria-hidden="true" />
          Previous
        </button>
        <span className="min-w-20 text-center font-mono text-[11px] text-ink-400">
          {page} / {pages}
        </span>
        <button
          type="button"
          onClick={() => onPageChange(offset + limit)}
          disabled={offset + limit >= total}
          className={buttonStyles({ variant: "secondary", size: "sm" })}
          aria-label="Next page"
        >
          Next
          <ChevronRight className="size-3.5" aria-hidden="true" />
        </button>
      </div>
    </nav>
  );
}
