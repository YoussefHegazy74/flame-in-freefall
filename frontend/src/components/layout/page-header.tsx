import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  meta?: ReactNode;
  className?: string;
  variant?: "default" | "hero";
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  meta,
  className,
  variant = "default",
}: PageHeaderProps) {
  const hero = variant === "hero";

  return (
    <header
      className={cn(
        "mb-8",
        hero ? "page-hero p-6 sm:p-8 lg:p-10" : "pb-1",
        className,
      )}
    >
      <div className="relative z-10 flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-3xl">
          {eyebrow ? <p className="kicker mb-3">{eyebrow}</p> : null}
          <h1
            className={cn(
              "text-balance font-semibold tracking-[-0.02em]",
              hero
                ? "hero-title text-3xl leading-[1.08] sm:text-4xl lg:text-5xl"
                : "text-2xl leading-tight text-foreground sm:text-3xl lg:text-4xl",
            )}
          >
            {title}
          </h1>
          {description ? (
            <div
              className={cn(
                "mt-3 max-w-2xl text-sm leading-relaxed text-muted",
                hero && "sm:text-base",
              )}
            >
              {description}
            </div>
          ) : null}
        </div>
        {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
      </div>
      {meta ? <div className="relative z-10 mt-5 flex flex-wrap items-center gap-2">{meta}</div> : null}
    </header>
  );
}
