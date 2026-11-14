import type { ReactNode } from "react";
import { AlertTriangle, Database } from "lucide-react";
import { cn } from "@/lib/utils";

export function ChartFrame({
  title,
  description,
  unit,
  timeUnit,
  source,
  warnings = [],
  children,
  footer,
  className,
  accessibleDescription,
}: {
  title: string;
  description?: ReactNode;
  unit?: string;
  timeUnit?: string;
  source: ReactNode;
  warnings?: string[];
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
  accessibleDescription?: string;
}) {
  return (
    <figure className={cn("surface overflow-hidden", className)}>
      <div className="border-b border-border px-4 py-4 sm:px-5">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <h3 className="text-[15px] font-semibold text-foreground">{title}</h3>
            {description ? (
              <div className="mt-1 text-[11px] leading-relaxed text-muted">{description}</div>
            ) : null}
          </div>
          <div className="flex flex-wrap gap-1.5">
            {unit ? (
              <span className="rounded border border-accent/20 bg-accent-soft px-1.5 py-0.5 font-mono text-[10px] text-accent-strong">
                y: {unit}
              </span>
            ) : null}
            {timeUnit ? (
              <span className="rounded border border-border bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] text-muted">
                x: {timeUnit}
              </span>
            ) : null}
          </div>
        </div>
        {warnings.length > 0 ? (
          <ul className="mt-2 space-y-1" aria-label="Chart warnings">
            {warnings.map((warning) => (
              <li key={warning} className="flex items-start gap-1.5 text-[11px] leading-relaxed text-warning">
                <AlertTriangle className="mt-0.5 size-3 shrink-0" aria-hidden="true" />
                {warning}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
      <div
        className="px-2 py-3 sm:px-4"
        role="group"
        aria-label={accessibleDescription ?? `${title}. ${description ?? ""}`}
      >
        {children}
      </div>
      <figcaption className="border-t border-navy-700/70 px-4 py-3 text-[11px] leading-relaxed text-muted">
        <div className="flex items-start gap-1.5">
          <Database className="mt-0.5 size-3.5 shrink-0 text-muted-2" aria-hidden="true" />
          <div>{source}</div>
        </div>
        {footer ? <div className="mt-2">{footer}</div> : null}
      </figcaption>
    </figure>
  );
}
