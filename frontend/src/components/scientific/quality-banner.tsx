import { AlertTriangle, Info } from "lucide-react";
import type { Quality } from "@/lib/api/types";
import { cn } from "@/lib/utils";
import { QualityStatusBadge } from "./state-badge";

export function WarningList({
  warnings,
  className,
  emptyLabel = "No warnings were returned for this response.",
}: {
  warnings: string[];
  className?: string;
  emptyLabel?: string;
}) {
  if (warnings.length === 0) {
    return <p className={cn("text-xs text-ink-400", className)}>{emptyLabel}</p>;
  }
  return (
    <ul className={cn("space-y-2", className)}>
      {warnings.map((warning) => (
        <li key={warning} className="flex items-start gap-2 text-xs leading-relaxed text-ink-300">
          <AlertTriangle className="mt-0.5 size-3.5 shrink-0 text-amber-300" aria-hidden="true" />
          <span>{warning}</span>
        </li>
      ))}
    </ul>
  );
}

export function QualityBanner({
  quality,
  title = "Response quality",
  className,
  showFlags = true,
}: {
  quality: Quality;
  title?: string;
  className?: string;
  showFlags?: boolean;
}) {
  const warnings = quality.warnings ?? [];
  return (
    <section
      className={cn(
        "rounded-xl border border-navy-700/70 bg-navy-900/55 p-4",
        className,
      )}
      aria-label={title}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold text-ink-100">{title}</span>
        <QualityStatusBadge status={quality.status} />
        <span className="font-mono text-[10px] text-ink-500" title="Raw quality status from the API">
          {quality.status}
        </span>
      </div>
      {showFlags && quality.flags.length > 0 ? (
        <div className="mt-3">
          <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-ink-500">
            Quality flags
          </p>
          <ul className="mt-1.5 flex flex-wrap gap-1.5" aria-label="Quality flags">
            {quality.flags.map((flag) => (
              <li
                key={flag}
                className="rounded border border-navy-600 bg-navy-800/80 px-1.5 py-0.5 font-mono text-[10px] text-ink-300"
              >
                {flag}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <div className="mt-3">
        <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-ink-500">
          Warnings
        </p>
        {warnings.length > 0 ? (
          <WarningList warnings={warnings} className="mt-1.5" />
        ) : (
          <p className="mt-1.5 flex items-start gap-2 text-xs text-ink-400">
            <Info className="mt-0.5 size-3.5 shrink-0 text-ink-500" aria-hidden="true" />
            No response-level warnings. Dataset and measurement restrictions still apply.
          </p>
        )}
      </div>
    </section>
  );
}
