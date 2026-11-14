"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { Menu, X, ExternalLink } from "lucide-react";
import { NAV_GROUPS } from "@/lib/navigation";
import { FlarexBrand } from "@/components/brand/flarex-brand";
import { API_DOCS_URL } from "@/lib/api/client";
import { cn } from "@/lib/utils";

interface SidebarProps {
  open: boolean;
  onClose: () => void;
}

export function Sidebar({ open, onClose }: SidebarProps) {
  const pathname = usePathname();

  useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previous;
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open, onClose]);

  return (
    <>
      <div
        aria-hidden="true"
        onClick={onClose}
        className={cn(
          "fixed inset-0 z-40 bg-black/45 backdrop-blur-sm transition-opacity duration-200 lg:hidden",
          open ? "opacity-100" : "pointer-events-none opacity-0",
        )}
      />
      <aside
        aria-label="Primary navigation"
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-[272px] flex-col border-r border-border bg-surface shadow-xl transition-transform duration-200",
          "lg:top-16 lg:z-30 lg:h-[calc(100vh-4rem)] lg:translate-x-0 lg:shadow-none",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex items-center justify-between border-b border-border px-5 py-4 lg:hidden">
          <Link
            href="/"
            onClick={onClose}
            className="group flex min-w-0 items-center rounded-lg focus-ring"
          >
            <FlarexBrand taglineClassName="whitespace-normal text-[8px] tracking-[0.08em]" />
          </Link>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-2 text-muted transition-colors hover:bg-surface-2 hover:text-foreground focus-ring"
            aria-label="Close navigation"
          >
            <X className="size-5" aria-hidden="true" />
          </button>
        </div>

        <div className="hidden items-center justify-between px-5 pb-1 pt-5 lg:flex">
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">
            Navigation
          </p>
          <span className="rounded-full border border-border bg-background px-2 py-0.5 font-mono text-[9px] uppercase tracking-[0.12em] text-muted">
            v1
          </span>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-3" aria-label="Sections">
          {NAV_GROUPS.map((group) => (
            <div key={group.label} className="mb-5 last:mb-2">
              <p className="px-3 pb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-2">
                {group.label}
              </p>
              <ul className="space-y-1">
                {group.items.map((item) => {
                  const active =
                    item.href === "/"
                      ? pathname === "/"
                      : pathname === item.href || pathname.startsWith(`${item.href}/`);
                  const Icon = item.icon;
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        onClick={onClose}
                        aria-current={active ? "page" : undefined}
                        title={item.description}
                        className={cn(
                          "group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-[13px] font-medium transition-colors focus-ring",
                          active
                            ? "bg-accent-soft text-accent-strong"
                            : "text-muted hover:bg-surface-2 hover:text-foreground",
                        )}
                      >
                        {active ? (
                          <span
                            className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-accent"
                            aria-hidden="true"
                          />
                        ) : null}
                        <Icon
                          className={cn(
                            "size-4 shrink-0",
                            active
                              ? "text-accent-strong"
                              : "text-muted-2 group-hover:text-muted",
                          )}
                          aria-hidden="true"
                        />
                        <span className="truncate">{item.label}</span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>

        <div className="border-t border-border p-3">
          <a
            href={API_DOCS_URL}
            target="_blank"
            rel="noreferrer"
            className="flex items-start gap-3 rounded-lg border border-border bg-background p-3 transition-colors hover:border-border-strong hover:bg-surface-2 focus-ring"
          >
            <span className="mt-0.5 rounded-md bg-accent-soft p-1.5 text-accent-strong">
              <ExternalLink className="size-3.5" aria-hidden="true" />
            </span>
            <span>
              <span className="block text-xs font-semibold text-foreground">
                Scientific API
              </span>
              <span className="mt-0.5 block text-[10px] leading-relaxed text-muted">
                Read-only endpoints, schemas, and examples.
              </span>
            </span>
          </a>
          <div className="mt-3 flex items-center justify-between px-1">
            <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-muted">
              Team AFAQ
            </p>
            <p className="text-[10px] text-muted-2">2026</p>
          </div>
        </div>
      </aside>
    </>
  );
}

export function MobileNavButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex size-9 items-center justify-center rounded-lg border border-border bg-surface text-muted transition-colors hover:bg-surface-2 hover:text-foreground focus-ring lg:hidden"
      aria-label="Open navigation"
    >
      <Menu className="size-4.5" aria-hidden="true" />
    </button>
  );
}
