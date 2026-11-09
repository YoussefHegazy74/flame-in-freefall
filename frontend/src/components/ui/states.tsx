import type { ReactNode } from "react";
import { AlertTriangle, CheckCircle2, Info, Loader2, RefreshCw, XCircle } from "lucide-react";
import { isApiError, type ApiError } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { buttonStyles } from "./button";

export function LoadingState({
  label = "Loading data from the read-only API…",
  rows = 3,
}: {
  label?: string;
  rows?: number;
}) {
  return (
    <div className="surface p-5" role="status" aria-live="polite">
      <div className="flex items-center gap-2 text-sm text-ink-300">
        <Loader2 className="size-4 animate-spin text-cyan-300" aria-hidden="true" />
        {label}
      </div>
      <div className="mt-5 space-y-3" aria-hidden="true">
        {Array.from({ length: rows }).map((_, index) => (
          <div key={index} className="space-y-2">
            <div className="h-3 w-2/5 animate-pulse rounded bg-navy-700/80" />
            <div className="h-3 w-full animate-pulse rounded bg-navy-800" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function EmptyState({
  title,
  description,
  icon,
  action,
}: {
  title: string;
  description: ReactNode;
  icon?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="surface flex flex-col items-center justify-center px-6 py-12 text-center">
      <span className="mb-4 rounded-2xl border border-navy-600 bg-navy-800/70 p-3 text-ink-400">
        {icon ?? <Info className="size-6" aria-hidden="true" />}
      </span>
      <h2 className="text-base font-semibold text-ink-100">{title}</h2>
      <div className="mt-2 max-w-lg text-sm leading-relaxed text-ink-400">{description}</div>
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}

function errorDetail(error: ApiError): string | null {
  const details = error.details;
  if (!details || typeof details !== "object") return null;
  const record = details as Record<string, unknown>;
  if (error.code === "range_too_large") {
    const actual = record.actual_points;
    const max = record.max_points;
    const suggested = record.suggested_max_span_ms ?? record.suggested_max_span_s;
    return [
      actual !== undefined ? `The request would return ${String(actual)} points.` : null,
      max !== undefined ? `The limit is ${String(max)} points.` : null,
      suggested !== undefined
        ? `Try a narrower span of about ${String(suggested)} ${record.suggested_max_span_ms !== undefined ? "ms" : "s"}.`
        : null,
    ]
      .filter(Boolean)
      .join(" ");
  }
  if (error.code === "validation_error" && Array.isArray(record.errors)) {
    return "One or more filter values are invalid. Check numeric ranges and page limits.";
  }
  return null;
}

export function ErrorState({
  error,
  title = "The request could not be completed",
  onRetry,
  children,
}: {
  error: unknown;
  title?: string;
  onRetry?: () => void;
  children?: ReactNode;
}) {
  const apiError = isApiError(error) ? error : null;
  const detail = apiError ? errorDetail(apiError) : null;
  const isRange = apiError?.code === "range_too_large";

  return (
    <div className="surface border-rose-400/20 p-5" role="alert">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 rounded-lg border border-rose-400/25 bg-rose-400/10 p-2 text-rose-300">
          {isRange ? (
            <AlertTriangle className="size-4" aria-hidden="true" />
          ) : (
            <XCircle className="size-4" aria-hidden="true" />
          )}
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-semibold text-ink-100">{title}</h2>
          <p className="mt-1 text-sm leading-relaxed text-ink-300">
            {apiError?.message ?? "An unexpected client error occurred."}
          </p>
          {detail ? (
            <p className="mt-2 rounded-lg border border-amber-400/20 bg-amber-400/5 p-2.5 text-xs leading-relaxed text-amber-200">
              {detail}
            </p>
          ) : null}
          <dl className="mt-3 flex flex-wrap gap-x-5 gap-y-1 font-mono text-[10px] text-ink-500">
            {apiError ? (
              <>
                <div>
                  <dt className="inline">code: </dt>
                  <dd className="inline text-ink-300">{apiError.code}</dd>
                </div>
                {apiError.status ? (
                  <div>
                    <dt className="inline">http: </dt>
                    <dd className="inline text-ink-300">{apiError.status}</dd>
                  </div>
                ) : null}
                {apiError.requestId ? (
                  <div>
                    <dt className="inline">request: </dt>
                    <dd className="inline text-ink-300">{apiError.requestId}</dd>
                  </div>
                ) : null}
              </>
            ) : null}
          </dl>
          {children}
          {onRetry ? (
            <button type="button" onClick={onRetry} className={buttonStyles({ size: "sm", className: "mt-4" })}>
              <RefreshCw className="size-3.5" aria-hidden="true" />
              Retry request
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export function InlineAlert({
  tone = "info",
  title,
  children,
  className,
}: {
  tone?: "info" | "warning" | "danger" | "success";
  title?: string;
  children: ReactNode;
  className?: string;
}) {
  const styles = {
    info: "border-cyan-400/20 bg-cyan-400/5 text-cyan-100",
    warning: "border-amber-400/25 bg-amber-400/5 text-amber-100",
    danger: "border-rose-400/25 bg-rose-400/5 text-rose-100",
    success: "border-emerald-400/25 bg-emerald-400/5 text-emerald-100",
  };
  const icons = {
    info: Info,
    warning: AlertTriangle,
    danger: XCircle,
    success: CheckCircle2,
  };
  const Icon = icons[tone];
  return (
    <div className={cn("rounded-xl border p-3.5 text-xs leading-relaxed", styles[tone], className)}>
      <div className="flex items-start gap-2.5">
        <Icon className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
        <div>
          {title ? <p className="font-semibold">{title}</p> : null}
          <div className={cn(title && "mt-0.5", "text-ink-300")}>{children}</div>
        </div>
      </div>
    </div>
  );
}
