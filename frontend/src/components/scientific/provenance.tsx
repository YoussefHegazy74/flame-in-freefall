import { ExternalLink, FileText, Fingerprint } from "lucide-react";
import type { ProvenanceRecord, SourceReference } from "@/lib/api/types";
import { formatDate } from "@/lib/format";
import { safeExternalUrl } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

function rowsLabel(record: ProvenanceRecord): string {
  if (record.rows && record.rows.length > 0) return record.rows.join(", ");
  if (record.row_range && record.row_range.length >= 2) {
    return `${record.row_range[0]}–${record.row_range[record.row_range.length - 1]}`;
  }
  return "not specified";
}

export function ProvenanceList({
  provenance,
  compact = false,
}: {
  provenance: ProvenanceRecord[];
  compact?: boolean;
}) {
  if (provenance.length === 0) {
    return (
      <p className="text-xs text-muted">
        No provenance records were returned for this response. Do not infer a source.
      </p>
    );
  }
  return (
    <ul className="space-y-3">
      {provenance.map((record, index) => {
        const sourceUrl = safeExternalUrl(record.source_url);
        return (
          <li
            key={`${record.accession}-${record.file}-${index}`}
            className="rounded-xl border border-border/70 bg-background/45 p-3"
          >
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="cyan">{record.accession}</Badge>
              <span className="flex min-w-0 items-center gap-1.5 text-xs text-text-soft">
                <FileText className="size-3.5 shrink-0 text-muted-2" aria-hidden="true" />
                <span className="break-all font-mono text-[11px]" title={record.file}>
                  {record.file}
                </span>
              </span>
            </div>
            <dl className="mt-2 grid gap-x-5 gap-y-1 text-[11px] sm:grid-cols-2">
              {record.sheet ? (
                <div>
                  <dt className="text-muted-2">Sheet</dt>
                  <dd className="text-muted">{record.sheet}</dd>
                </div>
              ) : null}
              <div>
                <dt className="text-muted-2">Source rows</dt>
                <dd className="font-mono text-muted">{rowsLabel(record)}</dd>
              </div>
              <div>
                <dt className="text-muted-2">Retrieved</dt>
                <dd className="text-muted">{formatDate(record.retrieved_at)}</dd>
              </div>
              {!compact ? (
                <div className="sm:col-span-2">
                  <dt className="flex items-center gap-1 text-muted-2">
                    <Fingerprint className="size-3" aria-hidden="true" />
                    SHA-256
                  </dt>
                  <dd className="break-all font-mono text-[10px] text-muted">
                    {record.sha256 ?? "checksum_not_available"}
                  </dd>
                </div>
              ) : null}
            </dl>
            {sourceUrl ? (
              <a
                href={sourceUrl}
                target="_blank"
                rel="noreferrer"
                className="mt-2 inline-flex items-center gap-1 text-[11px] font-medium text-accent-strong hover:text-accent-strong focus-ring"
              >
                Open NASA source file
                <ExternalLink className="size-3" aria-hidden="true" />
              </a>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}

export function SourceReferenceList({
  references,
}: {
  references: SourceReference[];
}) {
  if (references.length === 0) {
    return <p className="text-xs text-muted">No source references were returned.</p>;
  }
  return (
    <ul className="space-y-2">
      {references.map((reference, index) => {
        const sourceUrl = safeExternalUrl(reference.source_url);
        if (reference.kind === "nasa_psi_file") {
          return (
            <li
              key={`${reference.file_name}-${index}`}
              className="rounded-lg border border-border/60 bg-background/40 p-2.5"
            >
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="cyan">{reference.accession}</Badge>
                <span className="break-all font-mono text-[11px] text-muted">
                  {reference.file_name}
                </span>
              </div>
              {reference.sha256 ? (
                <p className="mt-1 break-all font-mono text-[10px] text-muted-2">
                  sha256: {reference.sha256}
                </p>
              ) : null}
              {sourceUrl ? (
                <a
                  href={sourceUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-1 inline-flex items-center gap-1 text-[11px] text-accent-strong hover:text-accent-strong focus-ring"
                >
                  NASA download
                  <ExternalLink className="size-3" aria-hidden="true" />
                </a>
              ) : null}
            </li>
          );
        }
        return (
          <li
            key={`${reference.path}-${reference.section}-${index}`}
            className="flex items-start gap-2 rounded-lg border border-border/60 bg-background/40 p-2.5 text-[11px] text-muted"
          >
            <FileText className="mt-0.5 size-3.5 shrink-0 text-muted-2" aria-hidden="true" />
            <span>
              <span className="mono text-text-soft">{reference.path ?? reference.kind}</span>
              {reference.section ? <span className="text-muted"> · {reference.section}</span> : null}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
