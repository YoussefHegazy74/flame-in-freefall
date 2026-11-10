#!/usr/bin/env python3
"""Run the Phase 5 assistant evaluation and write a JSON report.

Usage::

    .venv/bin/python scripts/evaluate_assistant.py
    .venv/bin/python scripts/evaluate_assistant.py --check
    .venv/bin/python scripts/evaluate_assistant.py --output /tmp/assistant_eval.json

By default the deterministic provider is evaluated. Use
``--use-configured-provider`` to evaluate a configured real provider; that mode
is not reproducible and requires credentials. The failing-provider and
deterministic mock-provider checks are always software checks, not a model
benchmark.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# The evaluation report is the user-facing output. Per-tool INFO logs are
# available during normal API serving but obscure the metric summary here.
# FLAME_LOG_LEVEL still overrides this if it is already set.
os.environ.setdefault("FLAME_LOG_LEVEL", "WARNING")

from src.analytics.registry import load_registries  # noqa: E402
from src.analytics.service import AnalyticsService  # noqa: E402
from src.assistant.config import (  # noqa: E402
    AssistantSettings,
    safe_settings_from_env,
)
from src.assistant.evaluation import run_golden_evaluation  # noqa: E402
from src.assistant.retrieval import get_default_index  # noqa: E402

GOLDEN_PATH = ROOT / "tests/assistant/golden_questions.json"
RETRIEVAL_PATH = ROOT / "tests/assistant/retrieval_golden.json"
DEFAULT_OUTPUT = ROOT / "data/reports/assistant_evaluation.json"
REAL_MODEL_OUTPUT = ROOT / "data/reports/assistant_real_model_evaluation.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _print_summary(report: dict) -> None:
    summary = report["summary"]
    print(
        "Assistant evaluation: "
        f"{summary['questions_passed']}/{summary['questions_total']} golden questions passed"
    )

    def line(label: str, value, denominator: int | None = None) -> None:
        if value is None:
            print(f"  {label}: not available")
        elif denominator is None:
            print(f"  {label}: {value}")
        else:
            print(f"  {label}: {value} (n={denominator})")

    line(
        "citation validity",
        summary["citation_validity_rate"],
        summary["citation_references_total"],
    )
    line(
        "supported claims",
        summary["supported_claim_rate"],
        summary["claims_total"],
    )
    line(
        "numerical exact match",
        summary["numerical_exact_match_rate"],
        summary["numeric_checks_total"],
    )
    line(
        "unit consistency",
        summary["unit_consistency_rate"],
        summary["unit_checks_total"],
    )
    line(
        "tool selection",
        summary["tool_selection_accuracy"],
        summary["tool_selection_questions"],
    )
    line(
        "correct refusals",
        summary["correct_refusal_rate"],
        summary["refusal_questions_total"],
    )
    latency = summary["latency"]
    print(
        "  latency: "
        f"mean {latency['mean_ms']} ms, p50 {latency['p50_ms']} ms, "
        f"p95 {latency['p95_ms']} ms, max {latency['max_ms']} ms"
    )
    if summary["failed_questions"]:
        print("  failed questions:")
        for item in summary["failed_questions"]:
            print(f"    {item['question_id']}: {', '.join(item['categories'])}")
            for failure in item["failures"]:
                print(f"      - {failure}")

    retrieval = report.get("retrieval")
    if retrieval:
        print(
            "Retrieval: "
            f"precision@k {retrieval['mean_precision_at_k']}, "
            f"recall@k {retrieval['mean_recall_at_k']}, "
            f"MRR {retrieval['mean_reciprocal_rank']} "
            f"(n={retrieval['cases_usable']} labelled cases)"
        )
        if retrieval["label_errors"]:
            print(f"  retrieval label errors: {retrieval['label_errors']}")

    provider = report.get("provider_checks")
    if provider:
        failing = provider["failing_provider"]
        mock = provider["mock_rephrase_provider"]
        print(
            "Provider checks: "
            f"failure fallback {'passed' if failing['passed'] else 'FAILED'}, "
            f"mock rephrase {'passed' if mock['passed'] else 'FAILED'}"
        )
        print(f"  {provider['real_model_note']}")


def _check_report(report: dict) -> list[str]:
    summary = report["summary"]
    failures: list[str] = []
    thresholds = (
        ("contract pass rate", summary["contract_pass_rate"]),
        ("citation validity", summary["citation_validity_rate"]),
        ("numerical exact match", summary["numerical_exact_match_rate"]),
        ("unit consistency", summary["unit_consistency_rate"]),
        ("tool selection", summary["tool_selection_accuracy"]),
        ("correct refusal", summary["correct_refusal_rate"]),
    )
    for label, value in thresholds:
        if value is not None and value < 1.0:
            failures.append(f"{label} is {value}, expected 1.0")
    if summary["failed_questions"]:
        failures.append(
            "failed golden questions: "
            + ", ".join(item["question_id"] for item in summary["failed_questions"])
        )
    provider = report.get("provider_checks")
    if provider:
        if not provider["failing_provider"]["passed"]:
            failures.append("failing-provider fallback checks did not pass")
        if not provider["mock_rephrase_provider"]["passed"]:
            failures.append("mock-provider rephrase checks did not pass")
    retrieval = report.get("retrieval")
    if retrieval:
        if retrieval["label_errors"]:
            failures.append(
                f"retrieval labels contain {retrieval['label_errors']} unknown document ids"
            )
        recall = retrieval["mean_recall_at_k"]
        if recall is not None and recall < 0.8:
            failures.append(
                f"retrieval mean recall@k is {recall}, expected at least 0.8"
            )
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "report path (default: data/reports/assistant_evaluation.json; "
            "real-provider mode defaults to "
            "data/reports/assistant_real_model_evaluation.json)"
        ),
    )
    parser.add_argument(
        "--questions",
        type=Path,
        default=GOLDEN_PATH,
        help="golden question set (default: tests/assistant/golden_questions.json)",
    )
    parser.add_argument(
        "--retrieval-cases",
        type=Path,
        default=RETRIEVAL_PATH,
        help="labelled retrieval cases (default: tests/assistant/retrieval_golden.json)",
    )
    parser.add_argument(
        "--no-retrieval",
        action="store_true",
        help="skip retrieval cases and the retrieval index",
    )
    parser.add_argument(
        "--no-provider-checks",
        action="store_true",
        help="skip failing-provider and mock-provider checks",
    )
    parser.add_argument(
        "--use-configured-provider",
        action="store_true",
        help=(
            "evaluate the environment-configured provider instead of the "
            "deterministic provider; may call a real model"
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if any golden, provider, or retrieval threshold fails",
    )
    args = parser.parse_args(argv)
    if args.output is None:
        args.output = REAL_MODEL_OUTPUT if args.use_configured_provider else DEFAULT_OUTPUT

    if args.use_configured_provider:
        configured, config_error = safe_settings_from_env()
        if not configured.llm_configured:
            print(
                "No real provider is configured. Set FLAME_LLM_PROVIDER="
                "openai_compatible, FLAME_LLM_BASE_URL, FLAME_LLM_MODEL, and "
                "FLAME_LLM_API_KEY, or run without --use-configured-provider "
                "for the deterministic evaluation.",
                file=sys.stderr,
            )
            if config_error:
                print(f"configuration detail: {config_error}", file=sys.stderr)
            return 2

    golden = _load_json(args.questions)
    retrieval_payload = (
        None if args.no_retrieval else _load_json(args.retrieval_cases)
    )

    if args.use_configured_provider:
        settings, config_error = safe_settings_from_env()
        if config_error:
            print(f"configuration warning: {config_error}", file=sys.stderr)
    else:
        settings = AssistantSettings()

    service = AnalyticsService(bundle=load_registries())
    retrieval_index = (
        get_default_index(service=service)
        if settings.retrieval_enabled and not args.no_retrieval
        else None
    )

    report = run_golden_evaluation(
        service=service,
        settings=settings,
        questions=golden["questions"],
        retrieval_index=retrieval_index,
        retrieval_cases=(
            retrieval_payload["cases"] if retrieval_payload else None
        ),
        retrieval_k=int(retrieval_payload.get("default_k", 5))
        if retrieval_payload
        else 5,
        provider_checks=not args.no_provider_checks,
    )
    report["golden_version"] = golden.get("golden_version")
    report["golden_path"] = str(args.questions.relative_to(ROOT))
    report["retrieval_golden_version"] = (
        retrieval_payload.get("retrieval_version") if retrieval_payload else None
    )
    report["command"] = " ".join(
        [".venv/bin/python", "scripts/evaluate_assistant.py", *sys.argv[1:]]
    ).strip()
    report["real_model_evaluated"] = bool(
        report["provider"]["assistant_mode"] == "provider"
        and report["provider"]["name"] not in {"deterministic", "mock_provider"}
    )
    if not report["real_model_evaluated"]:
        report["real_model_note"] = (
            "No real language model answer was evaluated. The report covers the "
            "deterministic orchestrator plus failing-provider and mock-provider "
            "software checks."
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    _print_summary(report)
    print(f"Report written to {args.output}")

    if args.check:
        failures = _check_report(report)
        if failures:
            for failure in failures:
                print(f"evaluation check failed: {failure}", file=sys.stderr)
            return 1
        print("Evaluation checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
