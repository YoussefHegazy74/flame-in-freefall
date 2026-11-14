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
    <div className="surface p-5 sm:p-6" role="status" aria-live="polite">
      <div className="flex items-center gap-2 text-sm text-muted">
        <Loader2 className="size-4 animate-spin text-accent" aria-hidden="true" />
        {label}
      </div>
      <div className="mt-5 space-y-3" aria-hidden="true">
        {Array.from({ length: rows }).map((_, index) => (
          <div key={index} className="space-y-2">
            <div className="h-3 w-2/5 animate-pulse rounded bg-surface-3" />
            <div className="h-3 w-full animate-pulse rounded bg-surface-2" />
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
    <div className="surface flex flex-col items-center justify-center px-6 py-14 text-center">
      <span className="mb-4 rounded-xl border border-border bg-surface-2 p-3 text-muted">
        {icon ?? <Info className="size-6" aria-hidden="true" />}
      </span>
      <h2 className="text-base font-semibold text-foreground">{title}</h2>
      <div className="mt-2 max-w-lg text-sm leading-relaxed text-muted">{description}</div>
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
    <div className="surface border-danger/20 p-5 sm:p-6" role="alert">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 rounded-lg border border-danger/20 bg-danger-soft p-2 text-danger">
          {isRange ? (
            <AlertTriangle className="size-4" aria-hidden="true" />
          ) : (
            <XCircle className="size-4" aria-hidden="true" />
          )}
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-semibold text-foreground">{title}</h2>
          <p className="mt-1 text-sm leading-relaxed text-muted">
            {apiError?.message ?? "An unexpected client error occurred."}
          </p>
          {detail ? (
            <p className="mt-3 rounded-lg border border-warning/20 bg-warning-soft p-3 text-xs leading-relaxed text-warning">
              {detail}
            </p>
          ) : null}
          <dl className="mt-3 flex flex-wrap gap-x-5 gap-y-1 font-mono text-[10px] text-muted-2">
            {apiError ? (
              <>
                <div>
                  <dt className="inline">code: </dt>
                  <dd className="inline text-muted">{apiError.code}</dd>
                </div>
                {apiError.status ? (
                  <div>
                    <dt className="inline">http: </dt>
                    <dd className="inline text-muted">{apiError.status}</dd>
                  </div>
                ) : null}
                {apiError.requestId ? (
                  <div>
                    <dt className="inline">request: </dt>
                    <dd className="inline text-muted">{apiError.requestId}</dd>
                  </div>
                ) : null}
              </>
            ) : null}
          </dl>
          {children}
          {onRetry ? (
            <button
              type="button"
              onClick={onRetry}
              className={buttonStyles({ size: "sm", className: "mt-4" })}
            >
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
    info: "border-accent/20 bg-accent-soft text-foreground",
    warning: "border-warning/20 bg-warning-soft text-foreground",
    danger: "border-danger/20 bg-danger-soft text-foreground",
    success: "border-success/20 bg-success-soft text-foreground",
  };
  const iconTones = {
    info: "text-accent-strong",
    warning: "text-warning",
    danger: "text-danger",
    success: "text-success",
  };
  const icons = {
    info: Info,
    warning: AlertTriangle,
    danger: XCircle,
    success: CheckCircle2,
  };
  const Icon = icons[tone];
  return (
    <div className={cn("rounded-xl border p-4 text-xs leading-relaxed", styles[tone], className)}>
      <div className="flex items-start gap-2.5">
        <Icon className={cn("mt-0.5 size-4 shrink-0", iconTones[tone])} aria-hidden="true" />
        <div>
          {title ? <p className="font-semibold text-foreground">{title}</p> : null}
          <div className={cn(title && "mt-1", "text-muted")}>{children}</div>
        </div>
      </div>
    </div>
  );
}
