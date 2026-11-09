import type { ReactNode } from "react";
import Link from "next/link";
import { ArrowUpRight, FileSearch } from "lucide-react";
import type { QualityFlag } from "@/lib/api/types";
import { fieldLabel } from "@/lib/labels";
import { formatValue } from "@/lib/format";
import { cn } from "@/lib/utils";

export function flagText(flag: QualityFlag): string {
  if (typeof flag === "string") return flag;
  return `${flag.field}: ${flag.flag}${flag.token ? ` (“${flag.token}”)` : ""}`;
}

export function RowQualityFlags({
  flags,
  className,
}: {
  flags: QualityFlag[] | undefined;
  className?: string;
}) {
  if (!flags || flags.length === 0) {
    return <span className="text-[11px] text-ink-500">No row-level flags returned.</span>;
  }
  return (
    <ul className={cn("flex flex-wrap gap-1", className)} aria-label="Row quality flags">
      {flags.map((flag, index) => (
        <li
          key={`${flagText(flag)}-${index}`}
          className="rounded border border-amber-400/20 bg-amber-400/5 px-1.5 py-0.5 font-mono text-[10px] text-amber-200"
          title={typeof flag === "string" ? flag : `${flag.raw_field} · token: ${flag.token ?? "null"}`}
        >
          {typeof flag === "string" ? flag : `${flag.field}=${flag.flag}`}
        </li>
      ))}
    </ul>
  );
}

export function ProvenanceLink({
  accession,
  file,
  sheet,
  row,
  label = "Inspect provenance",
  className,
}: {
  accession: string;
  file: string;
  sheet?: string | null;
  row?: number | null;
  label?: string;
  className?: string;
}) {
  const params = new URLSearchParams({ accession, file });
  if (sheet) params.set("sheet", sheet);
  if (row) params.set("row", String(row));
  return (
    <Link
      href={`/provenance?${params.toString()}`}
      className={cn(
        "inline-flex items-center gap-1 text-[11px] font-medium text-cyan-300 hover:text-cyan-200 focus-ring",
        className,
      )}
    >
      <FileSearch className="size-3.5" aria-hidden="true" />
      {label}
      <ArrowUpRight className="size-3" aria-hidden="true" />
    </Link>
  );
}

export function FieldGrid({
  fields,
  columns = 2,
}: {
  fields: Array<{ key: string; value: string | number | boolean | null | undefined; unit?: string | null }>;
  columns?: 1 | 2 | 3;
}) {
  return (
    <dl
      className={cn(
        "grid gap-x-5 gap-y-3",
        columns === 1 && "grid-cols-1",
        columns === 2 && "grid-cols-1 sm:grid-cols-2",
        columns === 3 && "grid-cols-1 sm:grid-cols-2 xl:grid-cols-3",
      )}
    >
      {fields.map((field) => (
        <div key={field.key} className="min-w-0">
          <dt className="text-[10px] uppercase tracking-[0.08em] text-ink-500">
            {fieldLabel(field.key)}
          </dt>
          <dd className="mt-0.5 break-words font-mono text-[11px] text-ink-200">
            {formatValue(field.value, field.unit)}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function DetailSection({
  title,
  description,
  children,
  actions,
}: {
  title: string;
  description?: ReactNode;
  children: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <section className="surface-flat p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-xs font-semibold text-ink-100">{title}</h3>
          {description ? <p className="mt-1 text-[11px] leading-relaxed text-ink-400">{description}</p> : null}
        </div>
        {actions}
      </div>
      <div className="mt-3">{children}</div>
    </section>
  );
}
