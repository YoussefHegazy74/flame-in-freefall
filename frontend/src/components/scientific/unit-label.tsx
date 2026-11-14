import { Badge } from "@/components/ui/badge";
import type { ValueKind } from "@/lib/api/types";
import { formatUnit } from "@/lib/format";
import { valueKindLabel } from "@/lib/labels";
import { cn } from "@/lib/utils";

const VALUE_KIND_TONES: Record<ValueKind, "cyan" | "violet" | "amber" | "neutral" | "outline"> = {
  measured: "cyan",
  computed: "violet",
  raw: "amber",
  categorical: "neutral",
  derived: "outline",
};

export function ValueKindBadge({ valueKind }: { valueKind: ValueKind | string }) {
  const kind = valueKind as ValueKind;
  return (
    <Badge tone={VALUE_KIND_TONES[kind] ?? "outline"} title={`value_kind: ${valueKind}`}>
      {valueKindLabel(valueKind)}
    </Badge>
  );
}

export function UnitLabel({
  unit,
  status,
  className,
}: {
  unit: string | null | undefined;
  status?: string | null;
  className?: string;
}) {
  const label = formatUnit(unit);
  const ambiguous = status === "ambiguous" || status === "not_stated";
  return (
    <span
      className={cn(
        "font-mono text-[11px]",
        ambiguous ? "text-warning" : "text-muted",
        className,
      )}
      title={status ? `unit_status: ${status}` : undefined}
    >
      {label}
    </span>
  );
}
