import Link from "next/link";
import { ArrowUpRight, Database, FlaskConical, Flame, Layers, ShieldAlert } from "lucide-react";
import type { DatasetSummary } from "@/lib/api/types";
import { familyLabel, labelForUse } from "@/lib/labels";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { ServingStateBadge } from "./state-badge";

const FAMILY_ICONS = {
  gas_flame: Flame,
  material: FlaskConical,
  droplet: Layers,
  telemetry: Database,
  smoke: Database,
  smoke_log: Database,
  metadata: ShieldAlert,
};

export function DatasetCard({
  dataset,
  className,
}: {
  dataset: DatasetSummary;
  className?: string;
}) {
  const Icon = FAMILY_ICONS[dataset.experiment_family as keyof typeof FAMILY_ICONS] ?? Database;
  return (
    <article className={cn("surface card-interactive group flex h-full flex-col p-5 sm:p-6", className)}>
      <div className="flex items-start justify-between gap-3">
        <span className="rounded-xl border border-border bg-surface-2 p-2.5 text-accent-strong">
          <Icon className="size-5" aria-hidden="true" />
        </span>
        <ServingStateBadge state={dataset.base_state} />
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Badge tone="cyan">{dataset.accession}</Badge>
        <Badge tone="neutral">{familyLabel(dataset.experiment_family)}</Badge>
      </div>
      <h2 className="mt-3 text-[15px] font-semibold leading-snug text-foreground">
        <Link href={`/datasets/${encodeURIComponent(dataset.dataset_id)}`} className="transition-colors hover:text-accent-strong focus-ring">
          {dataset.display_name}
        </Link>
      </h2>
      <p className="mt-2 text-[13px] leading-relaxed text-muted">
        {dataset.measurement_count} registered measurement{dataset.measurement_count === 1 ? "" : "s"} ·{" "}
        {dataset.access_scope.replace(/_/g, " ")}
      </p>
      <dl className="mt-4 grid grid-cols-2 gap-2">
        {Object.entries(dataset.use_states).map(([use, state]) => (
          <div key={use} className="rounded-lg border border-border bg-background p-2">
            <dt className="text-[10px] text-muted-2">{labelForUse(use)}</dt>
            <dd className="mt-1">
              <ServingStateBadge state={state} showIcon={false} className="text-[10px]" />
            </dd>
          </div>
        ))}
      </dl>
      <div className="mt-auto flex items-center justify-between gap-3 border-t border-border pt-4">
        <span className="text-[10px] text-muted-2">{dataset.reasons.length} documented reason{dataset.reasons.length === 1 ? "" : "s"}</span>
        <Link
          href={`/datasets/${encodeURIComponent(dataset.dataset_id)}`}
          className="inline-flex items-center gap-1 text-xs font-semibold text-accent-strong transition-colors hover:text-accent focus-ring"
        >
          Open dataset
          <ArrowUpRight className="size-3.5" aria-hidden="true" />
        </Link>
      </div>
    </article>
  );
}
