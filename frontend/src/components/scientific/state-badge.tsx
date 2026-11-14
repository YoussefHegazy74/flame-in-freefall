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
  available: "border-success/20 bg-success-soft text-success",
  available_with_warnings: "border-warning/20 bg-warning-soft text-warning",
  restricted: "border-warning/20 bg-warning-soft text-warning",
  blocked: "border-danger/20 bg-danger-soft text-danger",
  metadata_only: "border-border bg-surface-2 text-muted",
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
  comparable: "border-success/20 bg-success-soft text-success",
  conditionally_comparable: "border-accent/20 bg-accent-soft text-accent-strong",
  not_comparable: "border-warning/20 bg-warning-soft text-warning",
  blocked: "border-danger/20 bg-danger-soft text-danger",
  insufficient_metadata: "border-info/20 bg-info-soft text-info",
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
  verified: "border-success/20 bg-success-soft text-success",
  partial: "border-warning/20 bg-warning-soft text-warning",
  blocked: "border-danger/20 bg-danger-soft text-danger",
  experimental_table_only: "border-info/20 bg-info-soft text-info",
  not_available: "border-border bg-surface-2 text-muted",
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
