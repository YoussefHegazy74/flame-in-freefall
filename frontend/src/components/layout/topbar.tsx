"use client";

import { Search, Wifi, WifiOff, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useHealth } from "@/lib/api/hooks";
import { cn } from "@/lib/utils";
import { Breadcrumbs } from "./breadcrumbs";
import { MobileNavButton } from "./sidebar";

export function Topbar({ onOpenNav }: { onOpenNav: () => void }) {
  const router = useRouter();
  const health = useHealth();
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const typing =
        target?.tagName === "INPUT" ||
        target?.tagName === "TEXTAREA" ||
        target?.tagName === "SELECT" ||
        target?.isContentEditable;
      if (event.key === "/" && !typing) {
        event.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const trimmed = query.trim();
    router.push(trimmed ? `/investigations?q=${encodeURIComponent(trimmed)}` : "/investigations");
  };

  const apiState = health.isPending ? "checking" : health.isError ? "offline" : "online";
  const datasetVersion = health.data?.data.dataset_version;

  return (
    <header className="sticky top-0 z-30 border-b border-navy-700/70 bg-void/85 backdrop-blur-xl">
      <div className="mx-auto flex w-full max-w-[1600px] flex-wrap items-center gap-3 px-4 py-3 sm:px-6 lg:px-10">
        <MobileNavButton onClick={onOpenNav} />
        <Breadcrumbs className="hidden md:block" />

        <form
          role="search"
          onSubmit={submit}
          className="order-last flex w-full min-w-0 items-center gap-2 sm:order-none sm:ml-auto sm:w-auto"
        >
          <label htmlFor="global-search" className="sr-only">
            Search investigations
          </label>
          <div className="relative min-w-0 flex-1 sm:w-64">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-500"
              aria-hidden="true"
            />
            <input
              ref={inputRef}
              id="global-search"
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search investigations…"
              className="h-9 w-full rounded-lg border border-navy-700 bg-navy-900/80 pl-9 pr-12 text-sm text-ink-100 placeholder:text-ink-500 focus:border-cyan-400/60 focus-ring"
            />
            <kbd className="pointer-events-none absolute right-2.5 top-1/2 hidden -translate-y-1/2 rounded border border-navy-600 bg-navy-800 px-1.5 py-0.5 font-mono text-[10px] text-ink-500 sm:block">
              /
            </kbd>
          </div>
        </form>

        <div
          className={cn(
            "flex shrink-0 items-center gap-2 rounded-full border px-2.5 py-1.5 text-[11px] font-medium",
            apiState === "online" && "border-emerald-400/25 bg-emerald-400/10 text-emerald-300",
            apiState === "offline" && "border-rose-400/25 bg-rose-400/10 text-rose-300",
            apiState === "checking" && "border-navy-600 bg-navy-800/70 text-ink-300",
          )}
          role="status"
          aria-live="polite"
          title={
            datasetVersion
              ? `API online. Dataset ${datasetVersion}`
              : "Checking the read-only FastAPI backend"
          }
        >
          {apiState === "checking" ? (
            <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
          ) : apiState === "online" ? (
            <Wifi className="size-3.5" aria-hidden="true" />
          ) : (
            <WifiOff className="size-3.5" aria-hidden="true" />
          )}
          <span className="hidden sm:inline">
            {apiState === "online"
              ? "API online"
              : apiState === "offline"
                ? "API offline"
                : "Checking API"}
          </span>
          <span className="sm:hidden">
            {apiState === "online" ? "Online" : apiState === "offline" ? "Offline" : "…"}
          </span>
        </div>
      </div>
      <div className="border-t border-navy-800/80 px-4 py-2 md:hidden">
        <Breadcrumbs />
      </div>
    </header>
  );
}
