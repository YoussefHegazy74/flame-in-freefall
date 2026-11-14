"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { BookOpen, Loader2, Search, Wifi, WifiOff, X } from "lucide-react";
import { useHealth } from "@/lib/api/hooks";
import { API_DOCS_URL } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { ThemeToggle } from "@/components/theme-toggle";
import { FlarexBrand } from "@/components/brand/flarex-brand";
import { Breadcrumbs } from "./breadcrumbs";
import { MobileNavButton } from "./sidebar";

export function Topbar({ onOpenNav }: { onOpenNav: () => void }) {
  const router = useRouter();
  const health = useHealth();
  const [query, setQuery] = useState("");
  const [scrolled, setScrolled] = useState(false);
  const [mobileSearchOpen, setMobileSearchOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

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
      if (event.key === "Escape") setMobileSearchOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const trimmed = query.trim();
    setMobileSearchOpen(false);
    router.push(trimmed ? `/investigations?q=${encodeURIComponent(trimmed)}` : "/investigations");
  };

  const apiState = health.isPending ? "checking" : health.isError ? "offline" : "online";
  const datasetVersion = health.data?.data.dataset_version;

  return (
    <header
      className={cn(
        "site-header sticky top-0 z-40 w-full",
        scrolled && "site-header-scrolled",
      )}
    >
      <div className="mx-auto flex h-16 w-full max-w-[1600px] items-center gap-2 px-4 sm:px-6 lg:px-8">
        <MobileNavButton onClick={onOpenNav} />

        <Link
          href="/"
          className="group flex shrink-0 items-center rounded-lg focus-ring"
        >
          <FlarexBrand taglineClassName="max-xl:hidden" />
        </Link>

        <Breadcrumbs className="ml-4 hidden max-w-[18rem] xl:block" />

        <form
          role="search"
          onSubmit={submit}
          className="ml-auto hidden w-full max-w-xs items-center gap-2 md:flex lg:max-w-sm"
        >
          <label htmlFor="global-search" className="sr-only">
            Search investigations
          </label>
          <div className="relative min-w-0 flex-1">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-2"
              aria-hidden="true"
            />
            <input
              ref={inputRef}
              id="global-search"
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search investigations…"
              className="h-9 w-full rounded-lg border border-border bg-surface/80 pl-9 pr-12 text-sm text-foreground placeholder:text-muted-2 transition-colors focus:border-accent focus:bg-background focus-ring"
            />
            <kbd className="pointer-events-none absolute right-2.5 top-1/2 hidden -translate-y-1/2 rounded border border-border bg-background px-1.5 py-0.5 font-mono text-[10px] text-muted-2 lg:block">
              /
            </kbd>
          </div>
        </form>

        <div className="ml-auto flex items-center gap-1.5 md:ml-2">
          <button
            type="button"
            onClick={() => setMobileSearchOpen((value) => !value)}
            className="inline-flex size-9 items-center justify-center rounded-lg border border-border bg-surface text-muted transition-colors hover:bg-surface-2 hover:text-foreground focus-ring md:hidden"
            aria-label={mobileSearchOpen ? "Close search" : "Open search"}
            aria-expanded={mobileSearchOpen}
          >
            {mobileSearchOpen ? (
              <X className="size-4" aria-hidden="true" />
            ) : (
              <Search className="size-4" aria-hidden="true" />
            )}
          </button>

          <div
            className={cn(
              "hidden items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium sm:flex",
              apiState === "online" && "border-success/20 bg-success-soft text-success",
              apiState === "offline" && "border-danger/20 bg-danger-soft text-danger",
              apiState === "checking" && "border-border bg-surface-2 text-muted",
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
              <Loader2 className="size-3 animate-spin" aria-hidden="true" />
            ) : apiState === "online" ? (
              <Wifi className="size-3" aria-hidden="true" />
            ) : (
              <WifiOff className="size-3" aria-hidden="true" />
            )}
            <span>
              {apiState === "online"
                ? "API online"
                : apiState === "offline"
                  ? "API offline"
                  : "Checking"}
            </span>
          </div>

          <a
            href={API_DOCS_URL}
            target="_blank"
            rel="noreferrer"
            className="hidden size-9 items-center justify-center rounded-lg border border-border bg-surface text-muted transition-colors hover:bg-surface-2 hover:text-foreground focus-ring lg:inline-flex"
            aria-label="Open API documentation"
            title="API documentation"
          >
            <BookOpen className="size-4" aria-hidden="true" />
          </a>

          <ThemeToggle />
        </div>
      </div>

      {mobileSearchOpen ? (
        <div className="border-t border-border bg-background/95 px-4 py-3 backdrop-blur-xl md:hidden">
          <form role="search" onSubmit={submit} className="flex items-center gap-2">
            <label htmlFor="mobile-global-search" className="sr-only">
              Search investigations
            </label>
            <div className="relative min-w-0 flex-1">
              <Search
                className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-2"
                aria-hidden="true"
              />
              <input
                id="mobile-global-search"
                autoFocus
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search investigations…"
                className="h-10 w-full rounded-lg border border-border bg-surface pl-9 pr-3 text-sm text-foreground placeholder:text-muted-2 focus:border-accent focus:bg-background focus-ring"
              />
            </div>
            <button
              type="submit"
              className="inline-flex h-10 items-center justify-center rounded-lg bg-accent px-4 text-sm font-semibold text-accent-contrast transition-colors hover:bg-accent-hover focus-ring"
            >
              Search
            </button>
          </form>
        </div>
      ) : null}
    </header>
  );
}
