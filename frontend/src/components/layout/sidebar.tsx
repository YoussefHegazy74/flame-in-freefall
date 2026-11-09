"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { Flame, Menu, X, ExternalLink, PanelLeftClose } from "lucide-react";
import { NAV_GROUPS } from "@/lib/navigation";
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
    return () => {
      document.body.style.overflow = previous;
    };
  }, [open]);

  const close = () => {
    onClose();
  };

  return (
    <>
      <div
        aria-hidden="true"
        onClick={close}
        className={cn(
          "fixed inset-0 z-40 bg-void/80 backdrop-blur-sm transition-opacity lg:hidden",
          open ? "opacity-100" : "pointer-events-none opacity-0",
        )}
      />
      <aside
        aria-label="Primary navigation"
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-72 flex-col border-r border-navy-700/80 bg-navy-950/98 shadow-2xl transition-transform duration-200 lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex items-center justify-between border-b border-navy-700/80 px-5 py-5">
          <Link
            href="/"
            onClick={close}
            className="group flex items-center gap-3 rounded-lg focus-ring"
          >
            <span className="relative flex size-10 items-center justify-center rounded-xl border border-ember-400/30 bg-gradient-to-br from-ember-400/20 to-cyan-500/10 shadow-glow">
              <Flame className="size-5 text-ember-300" aria-hidden="true" />
              <span className="absolute -right-1 -top-1 size-2 rounded-full bg-cyan-400" />
            </span>
            <span>
              <span className="block text-sm font-semibold tracking-tight text-ink-50">
                Flame in Freefall
              </span>
              <span className="block font-mono text-[10px] uppercase tracking-[0.16em] text-ink-400">
                NASA PSI evidence explorer
              </span>
            </span>
          </Link>
          <button
            type="button"
            onClick={close}
            className="rounded-lg p-2 text-ink-300 hover:bg-navy-800 hover:text-ink-50 focus-ring lg:hidden"
            aria-label="Close navigation"
          >
            <X className="size-5" aria-hidden="true" />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-4" aria-label="Sections">
          {NAV_GROUPS.map((group) => (
            <div key={group.label} className="mb-5">
              <p className="px-3 pb-2 font-mono text-[10px] font-semibold uppercase tracking-[0.18em] text-ink-500">
                {group.label}
              </p>
              <ul className="space-y-0.5">
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
                        onClick={close}
                        aria-current={active ? "page" : undefined}
                        title={item.description}
                        className={cn(
                          "group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors focus-ring",
                          active
                            ? "border border-cyan-400/20 bg-cyan-400/10 text-cyan-200"
                            : "border border-transparent text-ink-300 hover:bg-navy-800/80 hover:text-ink-50",
                        )}
                      >
                        <Icon
                          className={cn(
                            "size-4 shrink-0",
                            active ? "text-cyan-300" : "text-ink-500 group-hover:text-ink-300",
                          )}
                          aria-hidden="true"
                        />
                        <span className="truncate">{item.label}</span>
                        {active ? (
                          <span className="ml-auto size-1.5 rounded-full bg-cyan-300" aria-hidden="true" />
                        ) : null}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>

        <div className="border-t border-navy-700/80 p-4">
          <div className="rounded-xl border border-navy-700/70 bg-navy-900/70 p-3">
            <div className="flex items-center gap-2">
              <span className="relative flex size-2">
                <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400 opacity-40" />
                <span className="relative inline-flex size-2 rounded-full bg-emerald-400" />
              </span>
              <p className="text-xs font-medium text-ink-200">Read-only scientific API</p>
            </div>
            <p className="mt-1.5 text-[11px] leading-relaxed text-ink-400">
              Comparability and serving states are decided by the backend, never the browser.
            </p>
            <a
              href={API_DOCS_URL}
              target="_blank"
              rel="noreferrer"
              className="mt-2.5 inline-flex items-center gap-1 text-[11px] font-medium text-cyan-300 hover:text-cyan-200 focus-ring"
            >
              Open API reference
              <ExternalLink className="size-3" aria-hidden="true" />
            </a>
          </div>
          <div className="mt-3 flex items-center justify-between px-1">
            <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500">
              Team AFAQ
            </p>
            <button
              type="button"
              onClick={close}
              className="hidden rounded p-1 text-ink-500 hover:text-ink-200 focus-ring lg:block"
              aria-label="Collapse navigation"
              title="Navigation is fixed on desktop"
            >
              <PanelLeftClose className="size-4" aria-hidden="true" />
            </button>
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
      className="rounded-lg border border-navy-700 bg-navy-900 p-2 text-ink-200 hover:border-navy-600 hover:text-ink-50 focus-ring lg:hidden"
      aria-label="Open navigation"
    >
      <Menu className="size-5" aria-hidden="true" />
    </button>
  );
}
