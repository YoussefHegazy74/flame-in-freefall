import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function Card({
  children,
  className,
  as: Tag = "div",
}: {
  children: ReactNode;
  className?: string;
  as?: "div" | "section" | "article" | "li";
}) {
  return <Tag className={cn("surface p-5", className)}>{children}</Tag>;
}

export function SectionCard({
  title,
  description,
  actions,
  children,
  className,
  contentClassName,
}: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  contentClassName?: string;
}) {
  return (
    <section className={cn("surface overflow-hidden", className)}>
      <div className="flex flex-col gap-3 border-b border-navy-700/70 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-sm font-semibold tracking-tight text-ink-100">{title}</h2>
          {description ? (
            <p className="mt-1 max-w-2xl text-xs leading-relaxed text-ink-400">{description}</p>
          ) : null}
        </div>
        {actions ? <div className="flex shrink-0 flex-wrap gap-2">{actions}</div> : null}
      </div>
      <div className={cn("p-5", contentClassName)}>{children}</div>
    </section>
  );
}

export function MetricCard({
  label,
  value,
  hint,
  icon,
  accent = "cyan",
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  icon?: ReactNode;
  accent?: "cyan" | "ember" | "emerald" | "violet";
}) {
  const accents = {
    cyan: "text-cyan-300 bg-cyan-400/10 border-cyan-400/20",
    ember: "text-ember-300 bg-ember-400/10 border-ember-400/20",
    emerald: "text-emerald-300 bg-emerald-400/10 border-emerald-400/20",
    violet: "text-violet-400 bg-violet-400/10 border-violet-400/20",
  };
  return (
    <div className="surface p-4 sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <p className="text-xs font-medium text-ink-400">{label}</p>
        {icon ? (
          <span className={cn("rounded-lg border p-1.5", accents[accent])} aria-hidden="true">
            {icon}
          </span>
        ) : null}
      </div>
      <p className="mt-3 text-2xl font-semibold tracking-tight text-ink-50">{value}</p>
      {hint ? <p className="mt-1.5 text-[11px] leading-relaxed text-ink-400">{hint}</p> : null}
    </div>
  );
}
