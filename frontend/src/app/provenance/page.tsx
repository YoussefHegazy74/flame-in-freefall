"use client";

import { Suspense, useMemo, useState, type FormEvent } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  CheckCircle2,
  Database,
  ExternalLink,
  FileSearch,
  Fingerprint,
  Info,
  Search,
  ShieldQuestion,
} from "lucide-react";
import { useDatasets, useInvestigations, useProvenance } from "@/lib/api/hooks";
import type { SourceReference } from "@/lib/api/types";
import { useUrlState } from "@/lib/use-url-state";
import { formatBytes, formatDate } from "@/lib/format";
import { safeExternalUrl } from "@/lib/utils";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { buttonStyles } from "@/components/ui/button";
import { ErrorState, InlineAlert, LoadingState } from "@/components/ui/states";
import { TextFilter } from "@/components/ui/filter";
import { QualityBanner } from "@/components/scientific/quality-banner";
import { CitationButton, CitationDrawer } from "@/components/scientific/citation-drawer";

interface ProvenanceForm {
  accession: string;
  file: string;
  sheet: string;
  row: string;
}

function formFromParams(get: (key: string, fallback?: string) => string | undefined): ProvenanceForm {
  return {
    accession: get("accession") ?? "",
    file: get("file") ?? "",
    sheet: get("sheet") ?? "",
    row: get("row") ?? "",
  };
}

function ProvenanceContent() {
  const { get, setParams, clearParams } = useUrlState();
  const investigations = useInvestigations({ limit: 200 });
  const datasets = useDatasets({ limit: 20 });

  const applied = useMemo(() => formFromParams(get), [get]);
  const appliedKey = useMemo(() => JSON.stringify(applied), [applied]);
  const [draftState, setDraftState] = useState<{
    key: string;
    value: ProvenanceForm;
  } | null>(null);
  const form = draftState?.key === appliedKey ? draftState.value : applied;
  const [formError, setFormError] = useState<string | null>(null);
  const [citationId, setCitationId] = useState<string | null>(null);

  const accession = applied.accession.trim();
  const file = applied.file.trim();
  const row = applied.row.trim() ? Number(applied.row) : undefined;
  const sheet = applied.sheet.trim() || undefined;
  const queryEnabled = Boolean(accession && file);
  const provenance = useProvenance(
    {
      accession,
      file,
      sheet,
      row: row !== undefined && Number.isFinite(row) ? row : undefined,
    },
    queryEnabled,
  );

  const knownFiles = useMemo(() => {
    const map = new Map<string, Array<{ datasetId: string; reference: SourceReference }>>();
    for (const dataset of datasets.data?.data ?? []) {
      for (const reference of dataset.source_references) {
        if (reference.kind !== "nasa_psi_file" || !reference.file_name) continue;
        const key = reference.accession ?? dataset.accession;
        const list = map.get(key) ?? [];
        list.push({ datasetId: dataset.dataset_id, reference });
        map.set(key, list);
      }
    }
    return Array.from(map.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [datasets.data]);

  const filesForAccession = useMemo(() => {
    if (!form.accession) return [];
    return (knownFiles.find(([key]) => key === form.accession)?.[1] ?? []).map(
      (item) => item.reference.file_name!,
    );
  }, [knownFiles, form.accession]);

  const accessions = (investigations.data?.data ?? []).map((item) => item.accession);

  const setField = (key: keyof ProvenanceForm, value: string) => {
    const next = { ...form, [key]: value };
    if (key === "accession" && value !== form.accession) {
      next.file = "";
      next.sheet = "";
      next.row = "";
    }
    setDraftState({ key: appliedKey, value: next });
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!form.accession.trim()) {
      setFormError("Enter the NASA PSI accession that owns the source file.");
      return;
    }
    if (!form.file.trim()) {
      setFormError("Enter the exact source file name. A path is not accepted.");
      return;
    }
    let rowValue: number | undefined;
    if (form.row.trim()) {
      rowValue = Number(form.row);
      if (!Number.isInteger(rowValue) || rowValue < 1) {
        setFormError("Row must be a positive integer when supplied.");
        return;
      }
    }
    setFormError(null);
    setParams({
      accession: form.accession.trim(),
      file: form.file.trim(),
      sheet: form.sheet.trim() || null,
      row: rowValue ?? null,
    });
  };

  const loadFile = (nextAccession: string, reference: SourceReference) => {
    setDraftState({
      key: appliedKey,
      value: {
        accession: nextAccession,
        file: reference.file_name ?? "",
        sheet: "",
        row: "",
      },
    });
    setFormError(null);
    setParams({
      accession: nextAccession,
      file: reference.file_name ?? "",
      sheet: null,
      row: null,
    });
  };

  const result = provenance.data?.data;
  const sourceUrl = safeExternalUrl(result?.source_url);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Analysis · Provenance"
        title="Resolve a source file and row"
        description={
          <>
            Look up the exact NASA source file, checksum, retrieval time, and optional row presence
            behind a record. Provenance establishes source identity. It does not by itself establish
            that a measurement is valid, calibrated, or comparable.
          </>
        }
        meta={
          <>
            <Badge tone="cyan">{knownFiles.reduce((sum, [, files]) => sum + files.length, 0)} curated source files</Badge>
            <Badge tone="neutral">Checksum-backed</Badge>
            <Badge tone="amber">Row presence ≠ value validity</Badge>
          </>
        }
      />

      <section className="rounded-xl border border-cyan-400/20 bg-accent-soft p-3.5">
        <div className="flex items-start gap-2.5">
          <Info className="mt-0.5 size-4 shrink-0 text-cyan-300" aria-hidden="true" />
          <div className="text-[11px] leading-relaxed text-ink-300">
            <p className="font-semibold text-cyan-100">
              File lookup requires the exact source file name.
            </p>
            <p className="mt-1">
              The API does not accept paths and does not expose raw files. If a file is not listed
              below, copy its exact name from a record&apos;s source identity. An unknown file
              returns a 404 rather than a guessed match.
            </p>
          </div>
        </div>
      </section>

      <section className="surface p-5" aria-labelledby="provenance-lookup">
        <h2 id="provenance-lookup" className="flex items-center gap-2 text-sm font-semibold text-ink-100">
          <FileSearch className="size-4 text-cyan-300" aria-hidden="true" />
          Provenance lookup
        </h2>
        <p className="mt-1 text-xs leading-relaxed text-ink-400">
          Accession and file are required. Sheet and row are optional. The query is stored in the
          URL and can be shared.
        </p>

        <form onSubmit={submit} className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <label htmlFor="provenance-accession" className="mb-1 block text-[11px] font-medium text-ink-300">
              Accession
            </label>
            <input
              id="provenance-accession"
              type="text"
              list="provenance-accessions"
              value={form.accession}
              onChange={(event) => setField("accession", event.target.value)}
              placeholder="e.g. PSI-10"
              className="h-9 w-full rounded-lg border border-navy-700 bg-navy-950/70 px-2.5 font-mono text-xs text-ink-100 placeholder:text-ink-500 focus:border-cyan-400/60 focus-ring"
            />
            <datalist id="provenance-accessions">
              {accessions.map((item) => (
                <option key={item} value={item} />
              ))}
            </datalist>
          </div>
          <div className="lg:col-span-2">
            <label htmlFor="provenance-file" className="mb-1 block text-[11px] font-medium text-ink-300">
              Exact source file name
            </label>
            <input
              id="provenance-file"
              type="text"
              list="provenance-files"
              value={form.file}
              onChange={(event) => setField("file", event.target.value)}
              placeholder="e.g. PSI-10_Experimental table_Flame Design_Normal Flame.csv"
              className="h-9 w-full rounded-lg border border-navy-700 bg-navy-950/70 px-2.5 font-mono text-[11px] text-ink-100 placeholder:text-ink-500 focus:border-cyan-400/60 focus-ring"
            />
            <datalist id="provenance-files">
              {filesForAccession.map((fileName) => (
                <option key={fileName} value={fileName} />
              ))}
            </datalist>
            <p className="mt-1 text-[10px] text-ink-500">
              {filesForAccession.length > 0
                ? `${filesForAccession.length} curated file${filesForAccession.length === 1 ? "" : "s"} suggested for this accession.`
                : "No curated file suggestion for this accession; enter the exact name."}
            </p>
          </div>
          <TextFilter
            id="provenance-sheet"
            label="Sheet (optional, echoed as supplied)"
            value={form.sheet}
            onChange={(value) => setField("sheet", value)}
            placeholder="e.g. Normal Flame"
          />
          <TextFilter
            id="provenance-row"
            label="Source row (optional)"
            type="number"
            min={1}
            step={1}
            value={form.row}
            onChange={(value) => setField("row", value)}
            placeholder="e.g. 1"
            hint="Checks presence in canonical row tables."
          />
          <div className="flex items-end gap-2 sm:col-span-2">
            <button type="submit" className={buttonStyles({ variant: "primary" })}>
              <Search className="size-4" aria-hidden="true" />
              Resolve provenance
            </button>
            <button
              type="button"
              className={buttonStyles({ variant: "ghost" })}
              onClick={() => {
                setDraftState(null);
                setFormError(null);
                clearParams();
              }}
            >
              Clear
            </button>
          </div>
        </form>
        {formError ? (
          <InlineAlert tone="warning" className="mt-3">
            {formError}
          </InlineAlert>
        ) : null}
      </section>

      {queryEnabled ? (
        provenance.isPending ? (
          <LoadingState label="Resolving source provenance…" rows={4} />
        ) : provenance.isError ? (
          <ErrorState
            error={provenance.error}
            title="Provenance could not be resolved"
            onRetry={() => provenance.refetch()}
          >
            <p className="mt-2 text-[11px] leading-relaxed text-ink-400">
              The file must exist in the canonical file metadata for the stated accession. The
              interface does not substitute a similar file name.
            </p>
          </ErrorState>
        ) : result ? (
          <section className="surface overflow-hidden" aria-labelledby="provenance-result">
            <div className="border-b border-navy-700/70 p-5">
              <div className="flex flex-wrap items-center gap-2">
                <span className="kicker">Resolved source</span>
                <Badge tone="cyan">{result.accession}</Badge>
                {result.row === null ? (
                  <Badge tone="neutral">File-level lookup</Badge>
                ) : result.row_verified ? (
                  <Badge tone="emerald">
                    <CheckCircle2 className="size-3" aria-hidden="true" />
                    Row present in canonical tables
                  </Badge>
                ) : (
                  <Badge tone="amber">
                    <AlertTriangle className="size-3" aria-hidden="true" />
                    Row not found in canonical tables
                  </Badge>
                )}
                <Badge tone="outline" className="font-mono">
                  origin: {result.origin}
                </Badge>
              </div>
              <h2 id="provenance-result" className="mt-3 break-all font-mono text-sm text-ink-100">
                {result.file}
              </h2>
              {result.sheet ? (
                <p className="mt-1 text-xs text-ink-400">
                  Sheet supplied: <span className="mono text-ink-300">{result.sheet}</span>. The API
                  echoes this value; it does not validate the sheet name.
                </p>
              ) : null}
            </div>

            <div className="space-y-4 p-5">
              {result.row !== null && result.row_verified === false ? (
                <InlineAlert tone="warning" title="The requested row was not found">
                  A missing row does not prove the source is invalid, but this lookup cannot confirm
                  that the row exists in the canonical row tables. Do not cite the row as verified.
                </InlineAlert>
              ) : null}

              <dl className="grid gap-3 text-xs sm:grid-cols-2 lg:grid-cols-3">
                <div>
                  <dt className="text-ink-500">Origin</dt>
                  <dd className="font-mono text-ink-200">{result.origin}</dd>
                </div>
                <div>
                  <dt className="text-ink-500">File size</dt>
                  <dd className="font-mono text-ink-200">{formatBytes(result.bytes)}</dd>
                </div>
                <div>
                  <dt className="text-ink-500">Retrieved</dt>
                  <dd className="text-ink-200">{formatDate(result.retrieved_at)}</dd>
                </div>
                <div>
                  <dt className="text-ink-500">Requested row</dt>
                  <dd className="font-mono text-ink-200">{result.row ?? "not requested"}</dd>
                </div>
                <div>
                  <dt className="text-ink-500">Row verified</dt>
                  <dd className="font-mono text-ink-200">
                    {result.row_verified === null ? "not applicable" : String(result.row_verified)}
                  </dd>
                </div>
                <div>
                  <dt className="text-ink-500">Row tables</dt>
                  <dd className="break-all font-mono text-[10px] text-ink-200">
                    {result.row_tables.length > 0 ? result.row_tables.join(", ") : "none returned"}
                  </dd>
                </div>
                <div className="sm:col-span-2 lg:col-span-3">
                  <dt className="flex items-center gap-1 text-ink-500">
                    <Fingerprint className="size-3" aria-hidden="true" />
                    SHA-256
                  </dt>
                  <dd className="break-all font-mono text-[11px] text-ink-300">
                    {result.sha256 ?? "not available"}
                  </dd>
                </div>
                {sourceUrl ? (
                  <div className="sm:col-span-2 lg:col-span-3">
                    <dt className="text-ink-500">NASA source</dt>
                    <dd>
                      <a
                        href={sourceUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 break-all text-[11px] text-cyan-300 hover:text-cyan-200 focus-ring"
                      >
                        {result.source_url}
                        <ExternalLink className="size-3 shrink-0" aria-hidden="true" />
                      </a>
                    </dd>
                  </div>
                ) : null}
              </dl>

              {result.citation_id || (result.row_citation_ids?.length ?? 0) > 0 ? (
                <div className="flex flex-wrap items-center gap-4 rounded-lg border border-navy-700/60 bg-navy-950/35 p-3">
                  <span className="text-[10px] uppercase tracking-[0.08em] text-ink-500">
                    Citation records
                  </span>
                  <CitationButton
                    citationId={result.citation_id}
                    onClick={setCitationId}
                    label="File citation"
                  />
                  {(result.row_citation_ids ?? []).map((id, index) => (
                    <CitationButton
                      key={id}
                      citationId={id}
                      onClick={setCitationId}
                      label={`Row citation ${index + 1}`}
                    />
                  ))}
                </div>
              ) : null}

              {result.warnings.length > 0 ? (
                <div>
                  <h3 className="text-xs font-semibold text-ink-100">Lookup warnings</h3>
                  <ul className="mt-2 space-y-2">
                    {result.warnings.map((warning) => (
                      <li
                        key={warning}
                        className="rounded-lg border border-amber-400/20 bg-warning-soft p-2.5 text-xs leading-relaxed text-amber-100"
                      >
                        {warning}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              <QualityBanner quality={provenance.data.quality} title="Provenance response quality" />

              <div className="rounded-xl border border-navy-700/60 bg-navy-950/35 p-3.5 text-[11px] leading-relaxed text-ink-400">
                <p className="font-semibold text-ink-200">What this lookup establishes</p>
                <p className="mt-1">
                  The named file exists in the canonical file metadata for this accession, and the
                  checksum identifies the exact bytes used by the registry. When a row is supplied,
                  the API checks whether that row appears in the canonical row tables. It does not
                  verify every cell, recalibrate a value, or change a quality or serving decision.
                </p>
              </div>
            </div>
          </section>
        ) : null
      ) : (
        <InlineAlert tone="info">
          Enter an accession and exact file name to resolve provenance. No partial or fuzzy match is
          performed.
        </InlineAlert>
      )}

      <section aria-labelledby="known-files">
        <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 id="known-files" className="flex items-center gap-2 text-sm font-semibold text-ink-100">
              <Database className="size-4 text-cyan-300" aria-hidden="true" />
              Curated source files
            </h2>
            <p className="mt-1 text-xs leading-relaxed text-ink-400">
              Files referenced by the nine curated datasets. Selecting one loads its exact name into
              the lookup; it does not download or display the file.
            </p>
          </div>
          {datasets.isFetching ? <Badge tone="neutral">Refreshing files…</Badge> : null}
        </div>

        {datasets.isPending ? (
          <LoadingState label="Loading curated source files…" rows={3} />
        ) : datasets.isError ? (
          <ErrorState
            error={datasets.error}
            title="Curated source files could not be loaded"
            onRetry={() => datasets.refetch()}
          />
        ) : knownFiles.length === 0 ? (
          <div className="surface p-5 text-sm text-ink-300">
            No curated source files were returned. Provenance lookup still requires an exact file
            name from a record.
          </div>
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            {knownFiles.map(([accessionKey, files]) => (
              <article key={accessionKey} className="surface p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="font-mono text-xs font-semibold text-cyan-200">{accessionKey}</h3>
                  <Badge tone="neutral">{files.length} files</Badge>
                </div>
                <ul className="mt-2 space-y-2">
                  {files.map(({ datasetId, reference }) => (
                    <li
                      key={`${datasetId}-${reference.file_name}`}
                      className="rounded-lg border border-navy-700/60 bg-navy-950/35 p-2.5"
                    >
                      <p className="break-all font-mono text-[11px] text-ink-200">
                        {reference.file_name}
                      </p>
                      {reference.sha256 ? (
                        <p className="mt-1 break-all font-mono text-[9px] text-ink-500">
                          sha256: {reference.sha256}
                        </p>
                      ) : null}
                      <div className="mt-2 flex flex-wrap gap-3">
                        <button
                          type="button"
                          onClick={() => loadFile(accessionKey, reference)}
                          className="text-[11px] font-medium text-cyan-300 hover:text-cyan-200 focus-ring"
                        >
                          Load into lookup
                        </button>
                        <Link
                          href={`/datasets/${encodeURIComponent(datasetId)}`}
                          className="text-[11px] text-ink-400 hover:text-cyan-200 focus-ring"
                        >
                          Dataset context
                        </Link>
                      </div>
                    </li>
                  ))}
                </ul>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="surface p-5" aria-labelledby="provenance-limits">
        <h2 id="provenance-limits" className="flex items-center gap-2 text-sm font-semibold text-ink-100">
          <ShieldQuestion className="size-4 text-amber-300" aria-hidden="true" />
          Provenance limitations
        </h2>
        <ul className="mt-3 grid gap-2 text-xs leading-relaxed text-ink-300 md:grid-cols-2">
          <li className="rounded-lg border border-navy-700/60 bg-navy-950/35 p-2.5">
            A checksum identifies file bytes, not the scientific validity of a column or row.
          </li>
          <li className="rounded-lg border border-navy-700/60 bg-navy-950/35 p-2.5">
            Row presence does not prove that every cell in that row was parsed correctly.
          </li>
          <li className="rounded-lg border border-navy-700/60 bg-navy-950/35 p-2.5">
            The API does not validate sheet names; a supplied sheet is echoed, not confirmed.
          </li>
          <li className="rounded-lg border border-navy-700/60 bg-navy-950/35 p-2.5">
            A missing file or row is reported as an error or unverified result, never guessed.
          </li>
        </ul>
      </section>

      <CitationDrawer citationId={citationId} onClose={() => setCitationId(null)} />
    </div>
  );
}

export default function ProvenancePage() {
  return (
    <Suspense fallback={<LoadingState label="Loading provenance explorer…" rows={4} />}>
      <ProvenanceContent />
    </Suspense>
  );
}
