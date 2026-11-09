import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiRequest, isApiError } from "@/lib/api/client";
import { api } from "@/lib/api/endpoints";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "X-Request-ID": "req_header" },
  });
}

const validEnvelope = {
  data: [{ ok: true }],
  meta: {
    request_id: "req_test",
    generated_at: "2026-11-09T00:00:00Z",
  },
  provenance: [],
  quality: { status: "verified", flags: [], warnings: [] },
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("apiRequest", () => {
  it("returns the full envelope without dropping quality or provenance", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(validEnvelope));
    vi.stubGlobal("fetch", fetchMock);

    const result = await apiRequest<Array<{ ok: boolean }>>("/example");

    expect(result.data).toEqual([{ ok: true }]);
    expect(result.quality.status).toBe("verified");
    expect(result.provenance).toEqual([]);
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it("serializes arrays as a single comma-separated query parameter", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(validEnvelope));
    vi.stubGlobal("fetch", fetchMock);

    await api.getTelemetrySeries("PSI-100::run", {
      channels: ["pcm_air_temp_c", "pcm_pressure_kpa"],
      start_ms: 0,
      end_ms: 1000,
      max_points: 500,
    });

    const requestedUrl = new URL(fetchMock.mock.calls[0][0] as string);
    expect(requestedUrl.pathname).toBe("/api/v1/telemetry/runs/PSI-100%3A%3Arun/series");
    expect(requestedUrl.searchParams.get("channels")).toBe(
      "pcm_air_temp_c,pcm_pressure_kpa",
    );
    expect(requestedUrl.searchParams.get("start_ms")).toBe("0");
    expect(requestedUrl.searchParams.get("end_ms")).toBe("1000");
    expect(requestedUrl.searchParams.get("max_points")).toBe("500");
  });

  it("omits null, undefined, and empty query values", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(validEnvelope));
    vi.stubGlobal("fetch", fetchMock);

    await api.getDatasets({ limit: 10, family: undefined, state: "" });

    const requestedUrl = new URL(fetchMock.mock.calls[0][0] as string);
    expect(requestedUrl.searchParams.get("limit")).toBe("10");
    expect(requestedUrl.searchParams.has("family")).toBe(false);
    expect(requestedUrl.searchParams.has("state")).toBe(false);
  });

  it("preserves backend error code, status, details, and request id", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(
        {
          error: {
            code: "range_too_large",
            message: "too many distinct timestamps",
            details: {
              actual_points: 41000,
              suggested_max_span_ms: 12000,
            },
            request_id: "req_body",
          },
        },
        413,
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      apiRequest("/telemetry/runs/run/series"),
    ).rejects.toMatchObject({
      name: "ApiError",
      kind: "http",
      status: 413,
      code: "range_too_large",
      requestId: "req_body",
      details: {
        actual_points: 41000,
        suggested_max_span_ms: 12000,
      },
    });
  });

  it("rejects a 200 response that is not an envelope", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ rows: [] }));
    vi.stubGlobal("fetch", fetchMock);

    const error = await apiRequest("/example").catch((caught: unknown) => caught);
    expect(isApiError(error)).toBe(true);
    expect((error as ApiError).kind).toBe("invalid_response");
    expect((error as ApiError).code).toBe("invalid_response");
  });

  it("reports an unreachable backend as a network error", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("fetch failed"));
    vi.stubGlobal("fetch", fetchMock);

    const error = await apiRequest("/example").catch((caught: unknown) => caught);
    expect(isApiError(error)).toBe(true);
    expect((error as ApiError).kind).toBe("network");
    expect((error as ApiError).code).toBe("network_error");
  });
});
