import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  CircleHelp,
  FileQuestion,
  Info,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import type {
  ComparisonStatus,
  QualityStatus,
  ServingState,
} from "@/lib/api/types";
import {
  COMPARISON_LABELS,
  QUALITY_LABELS,
  STATE_LABELS,
} from "@/lib/labels";
import { cn } from "@/lib/utils";

const SERVING_STYLES: Record<ServingState, string> = {
  available: "border-emerald-400/25 bg-emerald-400/10 text-emerald-300",
  available_with_warnings: "border-amber-400/25 bg-amber-400/10 text-amber-300",
  restricted: "border-ember-400/25 bg-ember-400/10 text-ember-300",
  blocked: "border-rose-400/25 bg-rose-400/10 text-rose-300",
  metadata_only: "border-navy-600 bg-navy-800/80 text-ink-300",
};

const SERVING_ICONS: Record<ServingState, typeof CheckCircle2> = {
  available: CheckCircle2,
  available_with_warnings: AlertTriangle,
  restricted: ShieldAlert,
  blocked: Ban,
  metadata_only: FileQuestion,
};

export function ServingStateBadge({
  state,
  className,
  showIcon = true,
}: {
  state: ServingState;
  className?: string;
  showIcon?: boolean;
}) {
  const Icon = SERVING_ICONS[state];
  return (
    <span
      title={state}
      data-state={state}
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium leading-5",
        SERVING_STYLES[state],
        className,
      )}
    >
      {showIcon ? <Icon className="size-3" aria-hidden="true" /> : null}
      {STATE_LABELS[state]}
    </span>
  );
}

const COMPARISON_STYLES: Record<ComparisonStatus, string> = {
  comparable: "border-emerald-400/25 bg-emerald-400/10 text-emerald-300",
  conditionally_comparable: "border-cyan-400/25 bg-cyan-400/10 text-cyan-300",
  not_comparable: "border-ember-400/25 bg-ember-400/10 text-ember-300",
  blocked: "border-rose-400/25 bg-rose-400/10 text-rose-300",
  insufficient_metadata: "border-violet-400/25 bg-violet-400/10 text-violet-400",
};

const COMPARISON_ICONS: Record<ComparisonStatus, typeof CheckCircle2> = {
  comparable: CheckCircle2,
  conditionally_comparable: CircleHelp,
  not_comparable: Info,
  blocked: Ban,
  insufficient_metadata: FileQuestion,
};

export function ComparisonStateBadge({
  status,
  className,
  showIcon = true,
}: {
  status: ComparisonStatus;
  className?: string;
  showIcon?: boolean;
}) {
  const Icon = COMPARISON_ICONS[status];
  return (
    <span
      title={status}
      data-status={status}
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium leading-5",
        COMPARISON_STYLES[status],
        className,
      )}
    >
      {showIcon ? <Icon className="size-3" aria-hidden="true" /> : null}
      {COMPARISON_LABELS[status]}
    </span>
  );
}

const QUALITY_STYLES: Record<QualityStatus, string> = {
  verified: "border-emerald-400/25 bg-emerald-400/10 text-emerald-300",
  partial: "border-amber-400/25 bg-amber-400/10 text-amber-300",
  blocked: "border-rose-400/25 bg-rose-400/10 text-rose-300",
  experimental_table_only: "border-violet-400/25 bg-violet-400/10 text-violet-400",
  not_available: "border-navy-600 bg-navy-800/80 text-ink-300",
};

const QUALITY_ICONS: Record<QualityStatus, typeof CheckCircle2> = {
  verified: ShieldCheck,
  partial: AlertTriangle,
  blocked: Ban,
  experimental_table_only: FileQuestion,
  not_available: Info,
};

export function QualityStatusBadge({
  status,
  className,
  showIcon = true,
}: {
  status: QualityStatus;
  className?: string;
  showIcon?: boolean;
}) {
  const Icon = QUALITY_ICONS[status];
  return (
    <span
      title={status}
      data-quality={status}
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium leading-5",
        QUALITY_STYLES[status],
        className,
      )}
    >
      {showIcon ? <Icon className="size-3" aria-hidden="true" /> : null}
      {QUALITY_LABELS[status]}
    </span>
  );
}
