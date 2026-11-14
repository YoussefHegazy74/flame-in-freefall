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
  return <Tag className={cn("surface p-5 sm:p-6", className)}>{children}</Tag>;
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
      <div className="flex flex-col gap-3 border-b border-border px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <div>
          <h2 className="text-[15px] font-semibold tracking-tight text-foreground">{title}</h2>
          {description ? (
            <p className="mt-1 max-w-2xl text-[13px] leading-relaxed text-muted">{description}</p>
          ) : null}
        </div>
        {actions ? <div className="flex shrink-0 flex-wrap gap-2">{actions}</div> : null}
      </div>
      <div className={cn("p-5 sm:p-6", contentClassName)}>{children}</div>
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
    cyan: "text-accent-strong bg-accent-soft border-accent/15",
    ember: "text-warning bg-warning-soft border-warning/15",
    emerald: "text-success bg-success-soft border-success/15",
    violet: "text-info bg-info-soft border-info/15",
  };
  return (
    <div className="surface card-interactive p-5">
      <div className="flex items-start justify-between gap-3">
        <p className="text-xs font-medium text-muted">{label}</p>
        {icon ? (
          <span className={cn("rounded-lg border p-1.5", accents[accent])} aria-hidden="true">
            {icon}
          </span>
        ) : null}
      </div>
      <p className="mt-3 text-3xl font-semibold tracking-tight text-foreground">{value}</p>
      {hint ? <p className="mt-1.5 text-[11px] leading-relaxed text-muted">{hint}</p> : null}
    </div>
  );
}
