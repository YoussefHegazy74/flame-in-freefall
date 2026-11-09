const COUNT_FORMAT = new Intl.NumberFormat("en-US");
const DATE_FORMAT = new Intl.DateTimeFormat("en-US", {
  year: "numeric",
  month: "short",
  day: "2-digit",
  timeZone: "UTC",
});
const DATE_TIME_FORMAT = new Intl.DateTimeFormat("en-US", {
  year: "numeric",
  month: "short",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "UTC",
  timeZoneName: "short",
});

export function formatCount(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return COUNT_FORMAT.format(value);
}

export function formatBytes(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  const tb = value / 1_000_000_000_000;
  if (tb >= 1) return `${tb.toFixed(tb >= 100 ? 0 : 2)} TB`;
  const gb = value / 1_000_000_000;
  if (gb >= 1) return `${gb.toFixed(gb >= 100 ? 0 : 2)} GB`;
  const mb = value / 1_000_000;
  if (mb >= 1) return `${mb.toFixed(2)} MB`;
  const kb = value / 1_000;
  if (kb >= 1) return `${kb.toFixed(1)} kB`;
  return `${value} B`;
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return DATE_FORMAT.format(date);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return DATE_TIME_FORMAT.format(date);
}

export function formatNumber(
  value: number | null | undefined,
  options: { maximumSignificantDigits?: number } = {},
): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  const abs = Math.abs(value);
  if (abs !== 0 && (abs < 0.0001 || abs >= 1_000_000)) {
    return value.toExponential(3);
  }
  return new Intl.NumberFormat("en-US", {
    maximumSignificantDigits: options.maximumSignificantDigits ?? 6,
  }).format(value);
}

export function formatValue(
  value: string | number | boolean | null | undefined,
  unit?: string | null,
): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") {
    const number = formatNumber(value);
    return unit && unit !== "category" ? `${number} ${unit}` : number;
  }
  return String(value);
}

export function formatUnit(unit: string | null | undefined): string {
  if (!unit || unit.trim() === "") return "not stated";
  return unit;
}

export function humanizeKey(key: string): string {
  return key
    .replace(/[_-]+/g, " ")
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `${formatNumber(value * 100, { maximumSignificantDigits: 4 })}%`;
}

export function formatDurationSeconds(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  if (value < 120) return `${formatNumber(value, { maximumSignificantDigits: 5 })} s`;
  const minutes = Math.floor(value / 60);
  const seconds = value - minutes * 60;
  return `${minutes} min ${formatNumber(seconds, { maximumSignificantDigits: 3 })} s`;
}
