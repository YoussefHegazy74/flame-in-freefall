"use client";

import { Suspense, useState, type FormEvent } from "react";
import { Search, X } from "lucide-react";
import { useInvestigations } from "@/lib/api/hooks";
import { useUrlState } from "@/lib/use-url-state";
import { roleLabel } from "@/lib/labels";
import { formatCount } from "@/lib/format";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { buttonStyles } from "@/components/ui/button";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { FilterBar, FilterActions, SelectFilter } from "@/components/ui/filter";
import { Pagination } from "@/components/ui/pagination";
import { InvestigationCard } from "@/components/scientific/investigation-card";

const PAGE_SIZE = 12;
const ROLES = ["primary", "supporting", "context", "future"];

function InvestigationsContent() {
  const { get, setParams, clearParams, searchParams } = useUrlState();
  const role = get("role") ?? "";
  const query = get("q") ?? "";
  const offset = Number(get("offset") ?? 0) || 0;
  const [searchText, setSearchText] = useState(query);

  const investigations = useInvestigations({
    role: role || undefined,
    q: query || undefined,
    limit: PAGE_SIZE,
    offset,
  });

  const page = investigations.data?.meta.page;
  const total = page?.total ?? 0;
  const items = investigations.data?.data ?? [];

  const submitSearch = (event: FormEvent) => {
    event.preventDefault();
    setParams({ q: searchText.trim() || null, offset: null });
  };

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Catalog"
        title="Investigation catalog"
        description={
          <>
            All catalogued NASA PSI investigations in the registry, with curated MVP roles,
            archive status, and documented limitations. Search matches accession, acronym, or
            title on the backend.
          </>
        }
        meta={
          <>
            <Badge tone="cyan">{formatCount(total)} investigations</Badge>
            <Badge tone="neutral">Page size {PAGE_SIZE}</Badge>
            {role ? <Badge tone="ember">Role: {roleLabel(role)}</Badge> : null}
            {query ? <Badge tone="violet">Search: {query}</Badge> : null}
          </>
        }
      />

      <FilterBar
        label="Investigation filters"
        actions={
          <FilterActions
            onClear={() => {
              setSearchText("");
              clearParams();
            }}
            resultLabel={
              investigations.isFetching && !investigations.isPending
                ? "Refreshing catalog…"
                : `${formatCount(total)} matching investigation${total === 1 ? "" : "s"}`
            }
          />
        }
      >
        <form onSubmit={submitSearch} className="sm:col-span-2" role="search">
          <label htmlFor="investigation-search" className="mb-1 block text-[11px] font-medium text-ink-300">
            Search accession, acronym, or title
          </label>
          <div className="flex gap-2">
            <div className="relative min-w-0 flex-1">
              <Search
                className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-ink-500"
                aria-hidden="true"
              />
              <input
                id="investigation-search"
                type="search"
                value={searchText}
                onChange={(event) => setSearchText(event.target.value)}
                placeholder="e.g. PSI-159, CFI-G, flame"
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
            The search is executed by the API. No client-side result filtering is applied.
          </p>
        </form>

        <SelectFilter
          id="investigation-role"
          label="Curated MVP role"
          value={role}
          onChange={(value) => setParams({ role: value || null })}
          options={ROLES.map((item) => ({ value: item, label: roleLabel(item) }))}
          placeholder="All roles"
          hint="Roles are assigned in the curated registry."
        />
      </FilterBar>

      {investigations.isPending ? (
        <LoadingState label="Loading investigations from the API…" rows={4} />
      ) : investigations.isError ? (
        <ErrorState
          error={investigations.error}
          title="The investigation catalog could not be loaded"
          onRetry={() => investigations.refetch()}
        />
      ) : items.length === 0 ? (
        <EmptyState
          title="No investigations match these filters"
          description={
            query || role
              ? "Clear the search and role filter to return to the full catalog. No records are hidden locally."
              : "The API returned an empty catalog."
          }
          icon={<Search className="size-6" aria-hidden="true" />}
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
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {items.map((investigation) => (
              <InvestigationCard key={investigation.accession} investigation={investigation} />
            ))}
          </div>
          <Pagination
            total={total}
            limit={PAGE_SIZE}
            offset={offset}
            onPageChange={(nextOffset) =>
              setParams({ offset: nextOffset || null }, { resetOffset: false, scroll: true })
            }
            label="investigations"
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

export default function InvestigationsPage() {
  return (
    <Suspense fallback={<LoadingState label="Loading investigation catalog…" rows={4} />}>
      <InvestigationsContent />
    </Suspense>
  );
}
