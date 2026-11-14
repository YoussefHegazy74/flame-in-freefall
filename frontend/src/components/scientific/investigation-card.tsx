import Link from "next/link";
import { ArrowUpRight, CalendarDays, Database, FileText } from "lucide-react";
import type { Investigation } from "@/lib/api/types";
import { formatCount, formatDate } from "@/lib/format";
import { roleLabel } from "@/lib/labels";
import { Badge } from "@/components/ui/badge";

export function InvestigationCard({ investigation }: { investigation: Investigation }) {
  const roleTone =
    investigation.mvp_role === "primary"
      ? "cyan"
      : investigation.mvp_role === "supporting"
        ? "ember"
        : "neutral";
  return (
    <article className="surface card-interactive flex h-full flex-col p-5 sm:p-6">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="cyan">{investigation.accession}</Badge>
        <Badge tone={roleTone}>{roleLabel(investigation.mvp_role)}</Badge>
        <Badge tone={investigation.archive_status === "available" ? "emerald" : "amber"}>
          Archive: {investigation.archive_status}
        </Badge>
      </div>
      <h2 className="mt-3 text-[15px] font-semibold leading-snug text-foreground">
        <Link
          href={`/investigations/${encodeURIComponent(investigation.accession)}`}
          className="transition-colors hover:text-accent-strong focus-ring"
        >
          {investigation.title}
        </Link>
      </h2>
      <p className="mt-1 text-xs font-medium text-accent-strong">{investigation.acronym}</p>
      <p className="mt-3 line-clamp-3 text-[13px] leading-relaxed text-muted">
        {investigation.rationale}
      </p>
      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 border-t border-border pt-4 text-[11px]">
        <div>
          <dt className="text-muted-2">Research area</dt>
          <dd className="text-text-soft">{investigation.sub_research_area}</dd>
        </div>
        <div>
          <dt className="text-muted-2">Files</dt>
          <dd className="flex items-center gap-1 text-ink-300">
            <FileText className="size-3" aria-hidden="true" />
            {formatCount(investigation.file_count)} added
          </dd>
        </div>
        <div>
          <dt className="text-muted-2">Experimental tables</dt>
          <dd className="flex items-center gap-1 text-ink-300">
            <Database className="size-3" aria-hidden="true" />
            {formatCount(investigation.experimental_table_count)}
          </dd>
        </div>
        <div>
          <dt className="text-muted-2">Start date</dt>
          <dd className="flex items-center gap-1 text-ink-300">
            <CalendarDays className="size-3" aria-hidden="true" />
            {formatDate(investigation.start_date)}
          </dd>
        </div>
      </dl>
      {investigation.limitations.length > 0 ? (
        <p className="mt-3 text-[11px] text-warning">
          {investigation.limitations.length} documented limitation
          {investigation.limitations.length === 1 ? "" : "s"}
        </p>
      ) : null}
      <div className="mt-auto flex items-center justify-between gap-2 border-t border-border pt-4">
        <span className="text-[10px] text-muted-2">DOI: {investigation.doi ?? "not stated"}</span>
        <Link
          href={`/investigations/${encodeURIComponent(investigation.accession)}`}
          className="inline-flex items-center gap-1 text-xs font-semibold text-accent-strong transition-colors hover:text-accent focus-ring"
        >
          Open record
          <ArrowUpRight className="size-3.5" aria-hidden="true" />
        </Link>
      </div>
    </article>
  );
}
