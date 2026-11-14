"use client";

import Link from "next/link";
import { ExternalLink } from "lucide-react";
import { useMeta } from "@/lib/api/hooks";
import { API_DOCS_URL } from "@/lib/api/client";
import { truncateMiddle } from "@/lib/utils";
import { FlarexBrand } from "@/components/brand/flarex-brand";

const EXPLORE_LINKS = [
  { href: "/", label: "Overview" },
  { href: "/investigations", label: "Investigations" },
  { href: "/datasets", label: "Datasets" },
  { href: "/experiments/gas-flame", label: "Gas Flame" },
  { href: "/experiments/materials", label: "Materials" },
  { href: "/experiments/droplets", label: "Droplets" },
];

const ANALYZE_LINKS = [
  { href: "/assistant", label: "Research Assistant" },
  { href: "/compare", label: "Comparison Studio" },
  { href: "/quality", label: "Data Quality" },
  { href: "/provenance", label: "Provenance" },
];

const REFERENCE_LINKS = [
  { href: "/publications", label: "Publications" },
  { href: "/about", label: "Methods" },
];

export function Footer() {
  const meta = useMeta();
  const datasetVersion = meta.data?.data.dataset_version;
  const registrySnapshot = meta.data?.data.registry_snapshot;

  return (
    <footer className="border-t border-border bg-surface/60">
      <div className="mx-auto w-full max-w-[1440px] px-4 py-10 sm:px-6 lg:px-8">
        <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-[1.5fr_1fr_1fr_1fr]">
          <div>
            <Link href="/" className="inline-flex items-center rounded-lg focus-ring">
              <FlarexBrand />
            </Link>
            <p className="mt-3 max-w-sm text-xs leading-relaxed text-muted">
              FLAREX is a read-only evidence explorer for curated NASA PSI microgravity
              combustion experiments. Missing values, units, qualifiers, and comparison limits
              stay visible.
            </p>
            <p className="mt-3 text-[11px] leading-relaxed text-muted-2">
              Interpretations are Team AFAQ&apos;s own. NASA does not endorse this platform.
            </p>
          </div>

          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-2">
              Explore
            </p>
            <ul className="mt-3 space-y-2">
              {EXPLORE_LINKS.map((link) => (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    className="text-xs text-muted transition-colors hover:text-foreground focus-ring"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-2">
              Analyze
            </p>
            <ul className="mt-3 space-y-2">
              {ANALYZE_LINKS.map((link) => (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    className="text-xs text-muted transition-colors hover:text-foreground focus-ring"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-2">
              Reference
            </p>
            <ul className="mt-3 space-y-2">
              {REFERENCE_LINKS.map((link) => (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    className="text-xs text-muted transition-colors hover:text-foreground focus-ring"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
              <li>
                <a
                  href={API_DOCS_URL}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-xs text-muted transition-colors hover:text-foreground focus-ring"
                >
                  API documentation
                  <ExternalLink className="size-3" aria-hidden="true" />
                </a>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-8 flex flex-col gap-3 border-t border-border pt-5 text-[11px] text-muted sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
            <span>© 2026 Team AFAQ</span>
            <span className="hidden h-3 w-px bg-border sm:block" aria-hidden="true" />
            <span>
              Dataset{" "}
              <span className="mono text-foreground" title={datasetVersion ?? undefined}>
                {datasetVersion ? truncateMiddle(datasetVersion, 10, 8) : "—"}
              </span>
            </span>
            <span>
              Registry <span className="mono text-foreground">{registrySnapshot ?? "—"}</span>
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <span className="rounded-full border border-border bg-background px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.1em]">
              API v1
            </span>
            <span className="rounded-full border border-border bg-background px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.1em]">
              Read-only
            </span>
          </div>
        </div>
      </div>
    </footer>
  );
}
