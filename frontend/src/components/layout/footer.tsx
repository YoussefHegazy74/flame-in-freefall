"use client";

import Link from "next/link";
import { ExternalLink } from "lucide-react";
import { useMeta } from "@/lib/api/hooks";
import { API_DOCS_URL } from "@/lib/api/client";
import { truncateMiddle } from "@/lib/utils";

export function Footer() {
  const meta = useMeta();
  const datasetVersion = meta.data?.data.dataset_version;
  const registrySnapshot = meta.data?.data.registry_snapshot;

  return (
    <footer className="mt-16 border-t border-navy-700/70 bg-navy-950/60">
      <div className="mx-auto grid w-full max-w-[1600px] gap-6 px-4 py-8 text-xs text-ink-400 sm:px-6 lg:grid-cols-[1.4fr_1fr_1fr] lg:px-10">
        <div>
          <p className="font-semibold text-ink-200">Flame in Freefall · Team AFAQ</p>
          <p className="mt-1.5 max-w-xl leading-relaxed">
            A read-only exploration layer over NASA Physical Sciences Informatics combustion
            experiments. Interpretations are the team&apos;s own; NASA does not endorse this
            platform.
          </p>
        </div>
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500">
            Canonical data
          </p>
          <p className="mt-1.5">
            Dataset version:{" "}
            <span className="mono text-ink-300" title={datasetVersion ?? undefined}>
              {datasetVersion ? truncateMiddle(datasetVersion, 12, 8) : "—"}
            </span>
          </p>
          <p className="mt-1">
            Registry snapshot: <span className="mono text-ink-300">{registrySnapshot ?? "—"}</span>
          </p>
        </div>
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500">
            Reference
          </p>
          <a
            href={API_DOCS_URL}
            target="_blank"
            rel="noreferrer"
            className="mt-1.5 inline-flex items-center gap-1 text-cyan-300 hover:text-cyan-200 focus-ring"
          >
            API documentation
            <ExternalLink className="size-3" aria-hidden="true" />
          </a>
          <p className="mt-1">
            <Link href="/about" className="hover:text-ink-200 focus-ring">
              Methods and limitations
            </Link>
          </p>
        </div>
      </div>
    </footer>
  );
}
