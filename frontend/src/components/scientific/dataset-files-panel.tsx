"use client";

import { useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Download, FileText, FolderOpen, ShieldQuestion } from "lucide-react";
import type { DatasetFile } from "@/lib/api/types";
import { useDatasetFiles } from "@/lib/api/hooks";
import { formatBytes, formatDate } from "@/lib/format";
import { humanizeKey } from "@/lib/format";
import { roleLabel } from "@/lib/labels";
import { safeExternalUrl } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { FilterBar, SelectFilter } from "@/components/ui/filter";
import { CitationButton } from "./citation-drawer";
import { ProvenanceLink } from "./record-fields";

function availabilityTone(status: string): "emerald" | "rose" | "neutral" {
  if (status === "available") return "emerald";
  if (status === "unavailable") return "rose";
  return "neutral";
}

function verificationTone(status: string): "emerald" | "amber" | "rose" {
  if (status === "verified") return "emerald";
  if (status === "unavailable") return "rose";
  return "amber";
}

function FileCard({
  file,
  onOpenCitation,
}: {
  file: DatasetFile;
  onOpenCitation?: (citationId: string) => void;
}) {
  const sourceUrl = safeExternalUrl(file.source_url);
  const canDownload = file.downloadable && Boolean(sourceUrl);

  return (
    <li className="surface-flat p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={availabilityTone(file.availability)}>{file.availability}</Badge>
            <Badge tone="outline">{humanizeKey(file.kind)}</Badge>
            {file.priority ? <Badge tone="violet">{roleLabel(file.priority)}</Badge> : null}
            <Badge tone={verificationTone(file.verification.status)}>
              {file.verification.status.replace(/_/g, " ")}
            </Badge>
          </div>
          <p className="mt-2 break-all font-mono text-[11px] text-ink-200">{file.file_name}</p>
          {file.purpose ? (
            <p className="mt-1 max-w-3xl text-[11px] leading-relaxed text-ink-400">{file.purpose}</p>
          ) : null}
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          {canDownload ? (
            <a
              href={sourceUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-400/25 bg-emerald-400/10 px-2.5 py-1.5 text-[11px] font-medium text-emerald-200 hover:bg-emerald-400/15 focus-ring"
            >
              <Download className="size-3.5" aria-hidden="true" />
              Download
            </a>
          ) : (
            <span className="inline-flex items-center gap-1.5 rounded-lg border border-rose-400/20 bg-rose-400/5 px-2.5 py-1.5 text-[11px] text-rose-200">
              <AlertTriangle className="size-3.5" aria-hidden="true" />
              Not downloadable
            </span>
          )}
          <CitationButton citationId={file.citation_id} onClick={onOpenCitation ?? (() => undefined)} />
        </div>
      </div>

      {file.availability_reason ? (
        <p className="mt-2 rounded-lg border border-rose-400/20 bg-rose-400/5 p-2 text-[11px] leading-relaxed text-rose-100">
          {file.availability_reason}
        </p>
      ) : null}

      <dl className="mt-3 grid gap-x-5 gap-y-2 text-[11px] sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <dt className="text-ink-500">Download status</dt>
          <dd className="font-mono text-ink-300">{file.download.status.replace(/_/g, " ")}</dd>
        </div>
        <div>
          <dt className="text-ink-500">HTTP status</dt>
          <dd className="font-mono text-ink-300">{file.download.http_status ?? "not recorded"}</dd>
        </div>
        <div>
          <dt className="text-ink-500">Bytes</dt>
          <dd className="font-mono text-ink-300">{formatBytes(file.download.bytes)}</dd>
        </div>
        <div>
          <dt className="text-ink-500">Retrieved</dt>
          <dd className="text-ink-300">{formatDate(file.download.retrieved_at)}</dd>
        </div>
        <div className="sm:col-span-2 lg:col-span-4">
          <dt className="text-ink-500">SHA-256</dt>
          <dd className="break-all font-mono text-[10px] text-ink-400">
            {file.download.sha256 ?? "checksum_not_available"}
          </dd>
        </div>
      </dl>

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-navy-700/60 pt-2.5">
        {file.download.checksum_match === true ? (
          <span className="inline-flex items-center gap-1 text-[10px] text-emerald-300">
            <CheckCircle2 className="size-3" aria-hidden="true" />
            checksum matches manifest
          </span>
        ) : file.download.checksum_match === false ? (
          <span className="inline-flex items-center gap-1 text-[10px] text-rose-300">
            <AlertTriangle className="size-3" aria-hidden="true" />
            checksum mismatch
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 text-[10px] text-ink-500">
            <ShieldQuestion className="size-3" aria-hidden="true" />
            checksum not available
          </span>
        )}
        <ProvenanceLink
          accession={file.accession}
          file={file.file_name}
          label="Resolve file provenance"
        />
      </div>
    </li>
  );
}

export function DatasetFilesPanel({
  datasetId,
  onOpenCitation,
}: {
  datasetId: string;
  onOpenCitation?: (citationId: string) => void;
}) {
  const [availability, setAvailability] = useState("");
  const [kind, setKind] = useState("");
  const files = useDatasetFiles(datasetId, {
    availability: availability || undefined,
    kind: kind || undefined,
    limit: 200,
  });
  const data = files.data?.data;
  const items = data?.files ?? [];
  const kinds = useMemo(() => {
    const values = new Set<string>();
    for (const file of data?.files ?? []) values.add(file.kind);
    return Array.from(values).sort();
  }, [data?.files]);

  return (
    <section className="surface p-5" aria-labelledby="dataset-files">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="dataset-files" className="flex items-center gap-2 text-sm font-semibold text-ink-100">
            <FolderOpen className="size-4 text-cyan-300" aria-hidden="true" />
            Curated source files
          </h2>
          <p className="mt-1 max-w-3xl text-xs leading-relaxed text-ink-400">
            Only files selected by the download manifest are listed. Availability and download
            status come from the backend; unavailable files never receive a download link.
          </p>
        </div>
        {data ? (
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="cyan">{data.summary.curated_files} curated</Badge>
            <Badge tone="emerald">{data.summary.downloadable_files} downloadable</Badge>
            {data.summary.unavailable_files > 0 ? (
              <Badge tone="rose">{data.summary.unavailable_files} unavailable</Badge>
            ) : null}
            {data.summary.known_unavailable_files > 0 ? (
              <Badge tone="amber">{data.summary.known_unavailable_files} known 404</Badge>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="mt-4">
        <FilterBar
          label="Dataset file filters"
          actions={
            <p className="text-[11px] text-ink-400" aria-live="polite">
              {data ? `${items.length} of ${data.page.total} curated files shown` : "Loading files…"}
            </p>
          }
        >
          <SelectFilter
            id={`files-availability-${datasetId}`}
            label="Availability"
            value={availability}
            onChange={setAvailability}
            options={[
              { value: "available", label: "Available" },
              { value: "unavailable", label: "Unavailable" },
            ]}
            placeholder="All availability states"
          />
          <SelectFilter
            id={`files-kind-${datasetId}`}
            label="File kind"
            value={kind}
            onChange={setKind}
            options={kinds.map((value) => ({ value, label: humanizeKey(value) }))}
            placeholder="All file kinds"
          />
        </FilterBar>
      </div>

      {files.isPending ? (
        <div className="mt-4">
          <LoadingState label="Loading curated file manifest…" rows={3} />
        </div>
      ) : files.isError ? (
        <div className="mt-4">
          <ErrorState
            error={files.error}
            title="Curated files could not be loaded"
            onRetry={() => files.refetch()}
          />
        </div>
      ) : items.length === 0 ? (
        <div className="mt-4">
          <EmptyState
            title="No curated file matches these filters"
            description="The manifest is unchanged. Clear the availability or file-kind filter to see every curated file. An empty list does not imply the archive is empty."
            icon={<FileText className="size-6" aria-hidden="true" />}
          />
        </div>
      ) : (
        <ul className="mt-4 space-y-3">
          {items.map((file) => (
            <FileCard key={file.file_id} file={file} onOpenCitation={onOpenCitation} />
          ))}
        </ul>
      )}

      {data ? (
        <p className="mt-4 rounded-lg border border-cyan-400/15 bg-cyan-400/5 p-2.5 text-[11px] leading-relaxed text-ink-300">
          Public inventory: {data.inventory.public_inventory_file_count} files;{" "}
          {data.inventory.curated_file_count} curated; {data.inventory.not_selected_file_count} not
          selected and not exposed. {data.inventory.note}
        </p>
      ) : null}
    </section>
  );
}
