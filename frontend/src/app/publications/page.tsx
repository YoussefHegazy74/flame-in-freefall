"use client";

import { Suspense, useState, type FormEvent } from "react";
import { BookOpen, Search, X } from "lucide-react";
import { useDatasets, useInvestigations, usePublications } from "@/lib/api/hooks";
import { useUrlState } from "@/lib/use-url-state";
import { formatCount } from "@/lib/format";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { buttonStyles } from "@/components/ui/button";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { FilterBar, FilterActions, SelectFilter } from "@/components/ui/filter";
import { Pagination } from "@/components/ui/pagination";
import { PublicationCard } from "@/components/scientific/publications-panel";

const PAGE_SIZE = 20;

function PublicationsContent() {
  const { get, setParams, clearParams, searchParams } = useUrlState();
  const accession = get("accession") ?? "";
  const datasetId = get("dataset_id") ?? "";
  const query = get("q") ?? "";
  const offset = Number(get("offset") ?? 0) || 0;
  const [searchText, setSearchText] = useState(query);

  const publications = usePublications({
    accession: accession || undefined,
    dataset_id: datasetId || undefined,
    q: query || undefined,
    limit: PAGE_SIZE,
    offset,
  });
  const investigations = useInvestigations({ limit: 200 });
  const datasets = useDatasets({ limit: 200 });

  const page = publications.data?.meta.page;
  const summary = publications.data?.data.summary;
  const total = page?.total ?? 0;
  const items = publications.data?.data.publications ?? [];

  const submitSearch = (event: FormEvent) => {
    event.preventDefault();
    setParams({ q: searchText.trim() || null, offset: null });
  };

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Reference"
        title="Publications"
        description={
          <>
            Registry-linked publications for the curated NASA PSI investigations. Only fields
            present in the source registry are returned. Year and venue are unavailable and are
            never inferred from external sources.
          </>
        }
        meta={
          <>
            <Badge tone="cyan">{formatCount(total)} matching records</Badge>
            {summary ? (
              <>
                <Badge tone="emerald">{formatCount(summary.with_doi)} with DOI</Badge>
                {summary.without_doi > 0 ? (
                  <Badge tone="amber">{formatCount(summary.without_doi)} without DOI</Badge>
                ) : null}
              </>
            ) : null}
            {accession ? <Badge tone="violet">{accession}</Badge> : null}
            {datasetId ? <Badge tone="violet">{datasetId}</Badge> : null}
          </>
        }
      />

      <FilterBar
        label="Publication filters"
        actions={
          <FilterActions
            onClear={() => {
              setSearchText("");
              clearParams();
            }}
            resultLabel={
              publications.isFetching && !publications.isPending
                ? "Refreshing publications…"
                : `${formatCount(total)} matching publication${total === 1 ? "" : "s"}`
            }
          />
        }
      >
        <form onSubmit={submitSearch} className="sm:col-span-2" role="search">
          <label
            htmlFor="publication-search"
            className="mb-1 block text-[11px] font-medium text-ink-300"
          >
            Search title, authors, or DOI
          </label>
          <div className="flex gap-2">
            <div className="relative min-w-0 flex-1">
              <Search
                className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-ink-500"
                aria-hidden="true"
              />
              <input
                id="publication-search"
                type="search"
                value={searchText}
                onChange={(event) => setSearchText(event.target.value)}
                placeholder="e.g. Soret, diffusion flame, 10.1016"
                className="h-9 w-full rounded-lg border border-navy-700 bg-navy-950/70 pl-8 pr-2.5 text-xs text-ink-100 placeholder:text-ink-500 focus:border-cyan-400/60 focus-ring"
              />
            </div>
            <button type="submit" className={buttonStyles({ variant: "primary", size: "sm" })}>
              Search
            </button>
            {query ? (
              <button
                type="button"
                onClick={() => {
                  setSearchText("");
                  setParams({ q: null });
                }}
                className={buttonStyles({ variant: "ghost", size: "sm" })}
                aria-label="Clear search"
              >
                <X className="size-3.5" aria-hidden="true" />
              </button>
            ) : null}
          </div>
          <p className="mt-1 text-[10px] text-ink-500">
            Search is executed by the API. Titles and author strings are matched against verified
            registry values.
          </p>
        </form>

        <SelectFilter
          id="publication-accession"
          label="Investigation"
          value={accession}
          onChange={(value) => setParams({ accession: value || null, dataset_id: null })}
          options={(investigations.data?.data ?? []).map((investigation) => ({
            value: investigation.accession,
            label: `${investigation.accession} · ${investigation.acronym || investigation.title}`,
          }))}
          placeholder="All investigations"
        />
        <SelectFilter
          id="publication-dataset"
          label="Dataset"
          value={datasetId}
          onChange={(value) => setParams({ dataset_id: value || null, accession: null })}
          options={(datasets.data?.data ?? []).map((dataset) => ({
            value: dataset.dataset_id,
            label: dataset.dataset_id,
          }))}
          placeholder="All datasets"
        />
      </FilterBar>

      {summary ? (
        <p className="rounded-lg border border-cyan-400/15 bg-cyan-400/5 p-2.5 text-[11px] leading-relaxed text-ink-300">
          {summary.note}
        </p>
      ) : null}

      {publications.isPending ? (
        <LoadingState label="Loading publications from the API…" rows={4} />
      ) : publications.isError ? (
        <ErrorState
          error={publications.error}
          title="The publication list could not be loaded"
          onRetry={() => publications.refetch()}
        />
      ) : items.length === 0 ? (
        <EmptyState
          title="No publication matches these filters"
          description={
            query || accession || datasetId
              ? "Clear the search and scope filters to return to the full registry list. No records are hidden locally."
              : "The source registry returned no publication records."
          }
          icon={<BookOpen className="size-6" aria-hidden="true" />}
          action={
            <button
              type="button"
              className={buttonStyles()}
              onClick={() => {
                setSearchText("");
                clearParams();
              }}
            >
              Clear filters
            </button>
          }
        />
      ) : (
        <>
          <ul className="space-y-3">
            {items.map((publication) => (
              <li key={publication.publication_id}>
                <PublicationCard publication={publication} />
              </li>
            ))}
          </ul>
          <Pagination
            total={total}
            limit={PAGE_SIZE}
            offset={offset}
            onPageChange={(nextOffset) =>
              setParams({ offset: nextOffset || null }, { resetOffset: false, scroll: true })
            }
            label="publications"
          />
          {searchParams.toString() ? (
            <p className="text-[10px] text-ink-500">
              Filters are stored in the URL and can be shared or reloaded.
            </p>
          ) : null}
        </>
      )}
    </div>
  );
}

export default function PublicationsPage() {
  return (
    <Suspense fallback={<LoadingState label="Loading publications…" rows={4} />}>
      <PublicationsContent />
    </Suspense>
  );
}
