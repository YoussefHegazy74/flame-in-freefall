#!/usr/bin/env python3
"""Reproducible operational benchmark for the read-only API.

The benchmark runs against an already-running local server. It does not build
data, download NASA files, or change query semantics. It measures the endpoints
used by the frontend and the deterministic assistant with bounded concurrency.

Usage::

    .venv/bin/python scripts/benchmark_api.py
    .venv/bin/python scripts/benchmark_api.py --iterations 40 --concurrency 8

The JSON report records the environment, dataset version, request counts,
latency, error rate, and the exact scenarios. It is an indicative local
baseline, not a production service-level objective.
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_OUTPUT = ROOT / "data/reports/phase6_performance.json"
GOLDEN_PATH = ROOT / "tests/assistant/golden_questions.json"


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _process_snapshot(pid: int | None) -> dict[str, Any] | None:
    if not pid:
        return None
    try:
        status = Path(f"/proc/{pid}/status").read_text(encoding="utf-8")
    except OSError:
        return {"pid": pid, "available": False}
    values: dict[str, Any] = {"pid": pid, "available": True}
    for line in status.splitlines():
        if line.startswith("VmRSS:"):
            values["rss_kb"] = int(line.split()[1])
        elif line.startswith("Threads:"):
            values["threads"] = int(line.split()[1])
    return values


def _latency(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"mean_ms": None, "p50_ms": None, "p95_ms": None, "max_ms": None}
    return {
        "mean_ms": round(statistics.fmean(values), 3),
        "p50_ms": round(_percentile(values, 0.50) or 0.0, 3),
        "p95_ms": round(_percentile(values, 0.95) or 0.0, 3),
        "max_ms": round(max(values), 3),
    }


def _request(
    client: httpx.Client,
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
) -> tuple[int, float, str | None]:
    started = time.perf_counter()
    try:
        kwargs = {} if json_body is None else {"json": json_body}
        response = client.request(method, path, **kwargs)
        elapsed = (time.perf_counter() - started) * 1000.0
        if response.status_code >= 400:
            return response.status_code, elapsed, f"HTTP {response.status_code}"
        payload = response.json()
        if not isinstance(payload, dict) or "data" not in payload:
            return response.status_code, elapsed, "response was not an envelope"
        return response.status_code, elapsed, None
    except Exception as exc:  # benchmark failures are data, not crashes
        return 0, (time.perf_counter() - started) * 1000.0, type(exc).__name__


def _run_scenario(
    client: httpx.Client,
    *,
    name: str,
    method: str,
    path: str,
    json_body: dict[str, Any] | None = None,
    iterations: int,
    concurrency: int,
) -> dict[str, Any]:
    _request(client, method, path, json_body=json_body)
    latencies: list[float] = []
    status_counts: dict[str, int] = {}
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(
                _request, client, method, path, json_body=json_body
            )
            for _ in range(iterations)
        ]
        for future in as_completed(futures):
            status, elapsed, error = future.result()
            latencies.append(elapsed)
            status_counts[str(status)] = status_counts.get(str(status), 0) + 1
            if error:
                errors.append(error)
    return {
        "name": name,
        "method": method,
        "path": path,
        "requests": iterations,
        "concurrency": concurrency,
        "status_counts": dict(sorted(status_counts.items())),
        "error_count": len(errors),
        "error_rate": round(len(errors) / iterations, 6) if iterations else None,
        "errors": sorted(set(errors))[:10],
        "latency_ms": _latency(latencies),
    }


def _discover(client: httpx.Client, base_url: str) -> dict[str, Any]:
    """Discover identifiers from the API instead of hardcoding scientific values."""

    discovered: dict[str, Any] = {"skipped": {}}

    try:
        runs = client.get(
            f"{base_url}/telemetry/runs", params={"accession": "PSI-100", "limit": 1}
        ).json()["data"]
        run = runs[0]
        detail = client.get(
            f"{base_url}/telemetry/runs/{quote(run['run_id'], safe='')}"
        ).json()["data"]
        channel = next(
            (
                item["channel_name_canonical"]
                for item in detail["channels"]
                if not item.get("constant") and item.get("point_count", 0) > 0
            ),
            None,
        )
        if channel:
            start = float(detail["time_min_ms"])
            end = min(float(detail["time_max_ms"]), start + 60_000.0)
            discovered["telemetry"] = {
                "run_id": run["run_id"],
                "channel": channel,
                "start_ms": start,
                "end_ms": end,
                "max_points": 1000,
            }
        else:
            discovered["skipped"]["telemetry"] = "no non-constant channel found"
    except Exception as exc:
        discovered["skipped"]["telemetry"] = type(exc).__name__

    try:
        citation = client.get(
            f"{base_url}/citations", params={"accession": "PSI-10", "limit": 1}
        ).json()["data"][0]
        discovered["citation"] = citation["citation_id"]
        discovered["provenance"] = {
            "accession": citation["accession"],
            "file": citation["file"]["name"],
        }
    except Exception as exc:
        discovered["skipped"]["citation"] = type(exc).__name__
        discovered["skipped"]["provenance"] = type(exc).__name__

    try:
        golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        discovered["assistant_question"] = next(
            item["question"]
            for item in golden["questions"]
            if item["question_id"] == "dq-001"
        )
    except Exception as exc:
        discovered["skipped"]["assistant_query"] = type(exc).__name__

    return discovered


def _scenarios(base_url: str, discovered: dict[str, Any]) -> list[dict[str, Any]]:
    scenarios: list[dict[str, Any]] = [
        {
            "name": "health",
            "method": "GET",
            "path": f"{base_url}/health",
        },
        {
            "name": "investigations",
            "method": "GET",
            "path": f"{base_url}/investigations?limit=10",
        },
        {
            "name": "datasets",
            "method": "GET",
            "path": f"{base_url}/datasets?limit=10",
        },
        {
            "name": "dataset_metadata",
            "method": "GET",
            "path": f"{base_url}/datasets/psi-10-gas-flame",
        },
        {
            "name": "gas_flame_tests",
            "method": "GET",
            "path": f"{base_url}/gas-flame/tests?accession=PSI-10&limit=20",
        },
        {
            "name": "assistant_status",
            "method": "GET",
            "path": f"{base_url}/assistant/status?include_index=true",
        },
    ]

    telemetry = discovered.get("telemetry")
    if telemetry:
        scenarios.append(
            {
                "name": "telemetry_series",
                "method": "GET",
                "path": (
                    f"{base_url}/telemetry/runs/"
                    f"{quote(telemetry['run_id'], safe='')}/series"
                    f"?channels={quote(telemetry['channel'], safe='')}"
                    f"&start_ms={telemetry['start_ms']}"
                    f"&end_ms={telemetry['end_ms']}"
                    f"&max_points={telemetry['max_points']}"
                ),
            }
        )

    citation = discovered.get("citation")
    if citation:
        scenarios.append(
            {
                "name": "citation_resolution",
                "method": "GET",
                "path": f"{base_url}/citations/{quote(citation, safe='')}",
            }
        )

    provenance = discovered.get("provenance")
    if provenance:
        scenarios.append(
            {
                "name": "provenance",
                "method": "GET",
                "path": (
                    f"{base_url}/provenance"
                    f"?accession={quote(provenance['accession'], safe='')}"
                    f"&file={quote(provenance['file'], safe='')}"
                ),
            }
        )

    question = discovered.get("assistant_question")
    if question:
        scenarios.append(
            {
                "name": "assistant_query_deterministic",
                "method": "POST",
                "path": f"{base_url}/assistant/query",
                "json": {"question": question},
            }
        )

    return scenarios


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000/api/v1",
        help="API base URL",
    )
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument(
        "--server-pid",
        type=int,
        default=None,
        help="optional backend process ID for RSS/thread observations",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    if args.iterations < 1 or args.concurrency < 1:
        parser.error("iterations and concurrency must be positive")

    process_before = _process_snapshot(args.server_pid)
    with httpx.Client(timeout=30.0) as client:
        try:
            health = client.get(f"{args.base_url}/health").json()["data"]
        except Exception as exc:
            print(
                f"API is not reachable at {args.base_url}: {type(exc).__name__}",
                file=sys.stderr,
            )
            return 1
        discovered = _discover(client, args.base_url)
        scenarios = _scenarios(args.base_url, discovered)
        results = [
            _run_scenario(
                client,
                name=scenario["name"],
                method=scenario["method"],
                path=scenario["path"],
                json_body=scenario.get("json"),
                iterations=args.iterations,
                concurrency=args.concurrency,
            )
            for scenario in scenarios
        ]

    process_after = _process_snapshot(args.server_pid)
    report = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "processor": platform.processor() or "not reported",
        },
        "api_base_url": args.base_url,
        "dataset_version": health.get("dataset_version"),
        "registry_version": health.get("registry_version"),
        "iterations_per_scenario": args.iterations,
        "concurrency": args.concurrency,
        "server_process": {
            "before": process_before,
            "after": process_after,
        },
        "scenarios": results,
        "skipped": discovered.get("skipped", {}),
        "notes": [
            "Local indicative baseline, not a service-level objective.",
            "The benchmark uses bounded concurrency and existing API caps.",
            "No scientific query semantics were changed for the benchmark.",
            "No raw NASA archive was downloaded or loaded.",
            "The benchmark server used a high request limit to avoid self-throttling; the shipped default remains 600 requests per 60 seconds.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(
        f"Benchmark: {len(results)} scenarios, {args.iterations} requests each, "
        f"concurrency {args.concurrency}"
    )
    for item in results:
        latency = item["latency_ms"]
        print(
            f"  {item['name']:<32} "
            f"mean {latency['mean_ms']} ms  p95 {latency['p95_ms']} ms  "
            f"errors {item['error_count']}/{item['requests']}"
        )
    if discovered.get("skipped"):
        print(f"  skipped: {discovered['skipped']}")
    print(f"Report written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
