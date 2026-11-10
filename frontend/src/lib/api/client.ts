import type { Envelope } from "./types";

export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1"
).replace(/\/+$/, "");

export const API_DOCS_URL = `${API_BASE_URL}/docs`;
export const API_OPENAPI_URL = `${API_BASE_URL}/openapi.json`;

export type QueryValue =
  | string
  | number
  | boolean
  | null
  | undefined
  | Array<string | number>;

export type QueryParams = Record<string, QueryValue>;

export type ApiErrorKind =
  | "http"
  | "network"
  | "timeout"
  | "abort"
  | "invalid_response";

interface ErrorEnvelope {
  error?: {
    code?: string;
    message?: string;
    details?: unknown;
    request_id?: string;
  };
}

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status: number;
  readonly code: string;
  readonly details: unknown;
  readonly requestId?: string;

  constructor(options: {
    kind: ApiErrorKind;
    message: string;
    status?: number;
    code?: string;
    details?: unknown;
    requestId?: string;
  }) {
    super(options.message);
    this.name = "ApiError";
    this.kind = options.kind;
    this.status = options.status ?? 0;
    this.code = options.code ?? "request_failed";
    this.details = options.details ?? null;
    this.requestId = options.requestId;
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

export function isAbortError(error: unknown): boolean {
  return isApiError(error) && error.kind === "abort";
}

function buildUrl(path: string, query?: QueryParams): string {
  const base = /^https?:\/\//i.test(API_BASE_URL)
    ? API_BASE_URL
    : new URL(API_BASE_URL, "http://localhost:3000").toString().replace(/\/+$/, "");
  const url = new URL(`${base}${path.startsWith("/") ? path : `/${path}`}`);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value === null || value === undefined || value === "") continue;
      if (Array.isArray(value)) {
        if (value.length === 0) continue;
        url.searchParams.set(key, value.join(","));
      } else {
        url.searchParams.set(key, String(value));
      }
    }
  }
  return url.toString();
}

function isEnvelope(value: unknown): value is Envelope<unknown> {
  if (typeof value !== "object" || value === null) return false;
  const record = value as Record<string, unknown>;
  return (
    "data" in record &&
    "meta" in record &&
    "quality" in record &&
    typeof record.meta === "object" &&
    record.meta !== null &&
    typeof record.quality === "object" &&
    record.quality !== null
  );
}

export interface RequestOptions {
  query?: QueryParams;
  signal?: AbortSignal;
  timeoutMs?: number;
}

interface InternalRequestOptions extends RequestOptions {
  method?: "GET" | "POST";
  body?: unknown;
}

async function requestEnvelope<T>(
  path: string,
  options: InternalRequestOptions = {},
): Promise<Envelope<T>> {
  const {
    query,
    signal,
    timeoutMs = 20_000,
    method = "GET",
    body,
  } = options;
  const controller = new AbortController();
  let timedOut = false;

  if (signal?.aborted) {
    throw new ApiError({
      kind: "abort",
      message: "The request was cancelled.",
      code: "request_aborted",
    });
  }

  const timeout = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  const onAbort = () => controller.abort();
  signal?.addEventListener("abort", onAbort, { once: true });

  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  let response: Response;
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
      cache: "no-store",
      credentials: "omit",
    });
  } catch (error) {
    if (timedOut) {
      throw new ApiError({
        kind: "timeout",
        message: `The API did not respond within ${Math.round(timeoutMs / 1000)} seconds.`,
        code: "request_timeout",
      });
    }
    if (signal?.aborted || (error instanceof DOMException && error.name === "AbortError")) {
      throw new ApiError({
        kind: "abort",
        message: "The request was cancelled.",
        code: "request_aborted",
      });
    }
    throw new ApiError({
      kind: "network",
      message:
        "The API could not be reached. Check that the FastAPI backend is running and that NEXT_PUBLIC_API_BASE_URL points to it.",
      code: "network_error",
      details: error instanceof Error ? error.message : String(error),
    });
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener("abort", onAbort);
  }

  const responseRequestId = response.headers.get("X-Request-ID") ?? undefined;
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new ApiError({
      kind: "invalid_response",
      status: response.status,
      message: "The API returned a response that was not valid JSON.",
      code: "invalid_response",
      requestId: responseRequestId,
    });
  }

  if (!response.ok) {
    const envelope = payload as ErrorEnvelope;
    const error = envelope.error;
    throw new ApiError({
      kind: "http",
      status: response.status,
      message: error?.message ?? `The API returned HTTP ${response.status}.`,
      code: error?.code ?? "http_error",
      details: error?.details ?? null,
      requestId: error?.request_id ?? responseRequestId,
    });
  }

  if (!isEnvelope(payload)) {
    throw new ApiError({
      kind: "invalid_response",
      status: response.status,
      message: "The API response did not contain the expected data, meta, and quality envelope.",
      code: "invalid_response",
      requestId: responseRequestId,
    });
  }

  return payload as Envelope<T>;
}

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<Envelope<T>> {
  return requestEnvelope<T>(path, { ...options, method: "GET" });
}

/**
 * Send a JSON POST body. The assistant query endpoint is the only write-like
 * route; it is still read-only science: it runs allowlisted tools and returns
 * a validated answer envelope.
 */
export async function apiPost<T>(
  path: string,
  body: unknown,
  options: RequestOptions = {},
): Promise<Envelope<T>> {
  return requestEnvelope<T>(path, { ...options, method: "POST", body });
}
