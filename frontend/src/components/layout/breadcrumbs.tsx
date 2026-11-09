"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight, Home } from "lucide-react";
import { ROUTE_LABELS } from "@/lib/navigation";
import { cn } from "@/lib/utils";

export function Breadcrumbs({ className }: { className?: string }) {
  const pathname = usePathname();
  const segments = pathname.split("/").filter(Boolean);

  if (segments.length === 0) {
    return (
      <nav aria-label="Breadcrumb" className={cn("text-xs text-ink-400", className)}>
        <span className="font-medium text-ink-200">Overview</span>
      </nav>
    );
  }

  const crumbs = segments.map((segment, index) => {
    const href = `/${segments.slice(0, index + 1).join("/")}`;
    const previous = segments[index - 1];
    const label =
      ROUTE_LABELS[segment] ??
      (previous === "investigations" || previous === "datasets"
        ? decodeURIComponent(segment)
        : decodeURIComponent(segment).replace(/-/g, " "));
    return { href, label, last: index === segments.length - 1 };
  });

  return (
    <nav aria-label="Breadcrumb" className={cn("min-w-0 text-xs text-ink-400", className)}>
      <ol className="flex min-w-0 items-center gap-1.5">
        <li>
          <Link
            href="/"
            className="inline-flex items-center gap-1 rounded text-ink-400 hover:text-cyan-300 focus-ring"
            aria-label="Overview"
          >
            <Home className="size-3.5" aria-hidden="true" />
            <span className="sr-only">Overview</span>
          </Link>
        </li>
        {crumbs.map((crumb) => (
          <li key={crumb.href} className="flex min-w-0 items-center gap-1.5">
            <ChevronRight className="size-3 shrink-0 text-ink-600" aria-hidden="true" />
            {crumb.last ? (
              <span
                aria-current="page"
                className="max-w-[11rem] truncate font-medium text-ink-200 sm:max-w-[18rem]"
                title={crumb.label}
              >
                {crumb.label}
              </span>
            ) : (
              <Link
                href={crumb.href}
                className="max-w-[10rem] truncate rounded text-ink-400 hover:text-cyan-300 focus-ring"
                title={crumb.label}
              >
                {crumb.label}
              </Link>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
