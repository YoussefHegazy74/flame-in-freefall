import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  meta?: ReactNode;
  className?: string;
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  meta,
  className,
}: PageHeaderProps) {
  return (
    <header className={cn("mb-7 border-b border-navy-700/60 pb-6", className)}>
      <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-3xl">
          {eyebrow ? <p className="kicker mb-2">{eyebrow}</p> : null}
          <h1 className="text-balance text-2xl font-semibold tracking-tight text-ink-50 sm:text-3xl">
            {title}
          </h1>
          {description ? (
            <div className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-300">
              {description}
            </div>
          ) : null}
        </div>
        {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
      </div>
      {meta ? <div className="mt-4 flex flex-wrap items-center gap-2">{meta}</div> : null}
    </header>
  );
}
