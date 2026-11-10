"""Deterministic intent, entity, and scope planning for the assistant.

The planner never calls a language model. It maps a bounded set of scientific
question patterns to an explicit, allowlisted tool plan. Topics that cannot be
answered from verified artifacts are planned as refusals or clarifications
instead of guesses. The composer owns all prose and numbers; the planner only
selects deterministic tools and scope.

The planner is intentionally conservative. When a question is ambiguous it
asks for clarification rather than choosing a dataset on the user's behalf.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from src.assistant.config import AssistantSettings
from src.assistant.contract import AnswerType, EvidenceStatus
from src.assistant.conversation import (
    ConversationContext,
    extract_accessions,
    extract_dataset_ids,
    resolve_followup_accession,
    resolve_followup_dataset,
)

CURATED_DATASETS: dict[str, str] = {
    "PSI-10": "psi-10-gas-flame",
    "PSI-25": "psi-25-material",
    "PSI-26": "psi-26-material",
    "PSI-69": "psi-69-droplet",
    "PSI-98": "psi-98-metadata",
    "PSI-100": "psi-100-telemetry",
    "PSI-101": "psi-101-smoke",
    "PSI-102": "psi-102-smoke-log",
    "PSI-159": "psi-159-gas-flame",
}
ACCESSION_BY_DATASET = {dataset: accession for accession, dataset in CURATED_DATASETS.items()}

TELEMETRY_DATASETS = ("psi-100-telemetry", "psi-101-smoke")
GAS_FLAME_DATASETS = ("psi-10-gas-flame", "psi-159-gas-flame")


@dataclass(frozen=True)
class PlannedCall:
    tool: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Plan:
    topic: str
    question: str
    answer_type: AnswerType
    evidence_status: EvidenceStatus
    accession: str | None
    dataset_id: str | None
    calls: tuple[PlannedCall, ...] = ()
    retrieval_query: str | None = None
    retrieval_accession: str | None = None
    retrieval_dataset_id: str | None = None
    flags: frozenset[str] = frozenset()
    expected_limitation_codes: tuple[str, ...] = ()
    clarification_question: str | None = None
    clarification_options: tuple[str, ...] = ()
    clarification_missing: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def call_names(self) -> list[str]:
        return [call.tool for call in self.calls]


def _has(question: str, *terms: str) -> bool:
    return any(term in question for term in terms)


def _any_word(question: str, *terms: str) -> bool:
    return any(re.search(rf"\b{re.escape(term)}\b", question) for term in terms)


def _call(tool: str, **arguments: Any) -> PlannedCall:
    return PlannedCall(tool=tool, arguments=arguments)


def _plan(
    topic: str,
    question: str,
    answer_type: AnswerType,
    evidence_status: EvidenceStatus,
    *,
    accession: str | None = None,
    dataset_id: str | None = None,
    calls: Sequence[PlannedCall] = (),
    **kwargs: Any,
) -> Plan:
    return Plan(
        topic=topic,
        question=question,
        answer_type=answer_type,
        evidence_status=evidence_status,
        accession=accession,
        dataset_id=dataset_id,
        calls=tuple(calls),
        **kwargs,
    )


def plan_question(
    question: str,
    *,
    context: ConversationContext | None = None,
    settings: AssistantSettings | None = None,
    forced_accession: str | None = None,
    forced_dataset_id: str | None = None,
) -> Plan:
    """Map a question to a deterministic plan.

    ``settings`` is accepted for callers that want to reason about retrieval
    availability. Retrieval-dependent plans still fail closed if the index is
    unavailable; the tool registry reports that failure safely.
    """

    raw_question = " ".join((question or "").split())
    text = raw_question.lower()

    explicit_accessions = extract_accessions(raw_question)
    explicit_datasets = extract_dataset_ids(raw_question)
    accession = forced_accession.upper() if forced_accession else (
        explicit_accessions[0] if explicit_accessions else None
    )
    dataset_id = forced_dataset_id.lower() if forced_dataset_id else (
        explicit_datasets[0] if explicit_datasets else None
    )
    if dataset_id is None and accession:
        dataset_id = CURATED_DATASETS.get(accession)
    if accession is None and dataset_id:
        accession = ACCESSION_BY_DATASET.get(dataset_id)
    if accession is None and context is not None:
        accession = resolve_followup_accession(raw_question, context)
    if dataset_id is None and context is not None:
        dataset_id = resolve_followup_dataset(raw_question, context)
    if accession is None and dataset_id:
        accession = ACCESSION_BY_DATASET.get(dataset_id)

    def scoped_plan(topic: str, *args: Any, **kwargs: Any) -> Plan:
        kwargs.setdefault("accession", accession)
        kwargs.setdefault("dataset_id", dataset_id)
        return _plan(topic, raw_question, *args, **kwargs)

    # ------------------------------------------------------------------
    # Safety refusals. These precede every data-shaped interpretation so a
    # request for secrets or adversarial behaviour can never trigger a tool
    # that might expose unrelated content.
    # ------------------------------------------------------------------
    secret_markers = (
        "flame_llm_api_key",
        "api key",
        "api_key",
        "secret key",
        "environment variable",
        "env var",
        "credentials",
        "authorization header",
        ".env",
        "private key",
    )
    injection_markers = (
        "ignore previous instructions",
        "ignore all previous",
        "ignore the previous",
        "system prompt",
        "reveal secrets",
        "print the value of",
        "disregard instructions",
    )
    filesystem_markers = (
        "contents of the .env",
        "read the file",
        "open the file",
        "filesystem",
        "file path",
        "local file",
        "print the file",
        "cat /",
        "environment variables",
    )
    if _has(text, *filesystem_markers):
        return scoped_plan(
            "security_refusal",
            AnswerType.factual,
            EvidenceStatus.insufficient_evidence,
            expected_limitation_codes=("filesystem_access_blocked",),
            flags=frozenset({"security"}),
        )
    if _has(text, *injection_markers) or _has(text, *secret_markers):
        return scoped_plan(
            "prompt_injection",
            AnswerType.factual,
            EvidenceStatus.insufficient_evidence,
            calls=(
                _call(
                    "search_scientific_documents",
                    query="verified source documentation evidence policy",
                    limit=3,
                ),
            ),
            expected_limitation_codes=("prompt_injection_blocked",),
            flags=frozenset({"security", "prompt_injection"}),
        )

    fire_markers = (
        "fire-risk score",
        "fire risk score",
        "risk score",
        "fire risk",
        "material ranking",
        "rank the materials",
        "rank materials",
        "fire-safety guarantee",
        "fire safety guarantee",
        "guarantee spacecraft fire safety",
        "predict spacecraft fire",
        "safer than",
        "which is safer",
        "which material is safest",
        "safest material",
        "safe for spacecraft",
        "spacecraft-safe",
    )
    if _has(text, *fire_markers):
        calls = (
            (_call("get_dataset_limitations", dataset_id=dataset_id, limit=50),)
            if dataset_id
            else ()
        )
        return scoped_plan(
            "fire_risk_refusal",
            AnswerType.methodology,
            EvidenceStatus.insufficient_evidence,
            calls=calls,
            expected_limitation_codes=("no_fire_risk_model",),
            flags=frozenset({"refusal", "fire_risk"}),
        )

    if _has(text, "invent a publication", "fabricate a publication", "make up a publication", "invent a doi", "fabricate a doi", "write a fake publication"):
        calls = (
            _call("get_publications", accession=accession, limit=10)
            if accession
            else _call("get_publications", limit=10),
        )
        return scoped_plan(
            "publication_invention",
            AnswerType.factual,
            EvidenceStatus.insufficient_evidence,
            calls=calls,
            expected_limitation_codes=(
                "publication_not_in_registry",
                "year_not_available",
                "venue_not_available",
            ),
            flags=frozenset({"refusal", "publication"}),
        )

    if _any_word(text, "convert", "conversion") and _has(text, "bar", "atm") and _has(text, "psi-159", "psi-10"):
        calls = (
            _call(
                "evaluate_comparison",
                left="psi-10-gas-flame.pressure_initial_atm",
                right="psi-159-gas-flame.pressure_initial_atm",
            ),
            _call(
                "dataset_field_statistics",
                dataset_id="psi-159-gas-flame",
                fields=["pressure_approx_bar", "pressure_initial_atm"],
            ),
            _call(
                "dataset_field_statistics",
                dataset_id="psi-10-gas-flame",
                fields=["pressure_initial_atm", "pressure_approx_bar"],
            ),
        )
        return scoped_plan(
            "unit_conversion_refusal",
            AnswerType.numerical,
            EvidenceStatus.insufficient_evidence,
            calls=calls,
            expected_limitation_codes=("pressure_unit_mismatch", "conversion_not_authorized"),
            flags=frozenset({"refusal", "conversion"}),
        )

    if _has(text, "treat", "impute", "assume") and _has(text, "missing", "blank") and _has(text, "zero", "0"):
        target_dataset = dataset_id or "psi-10-gas-flame"
        target_accession = accession or ACCESSION_BY_DATASET.get(target_dataset)
        calls = (
            _call(
                "dataset_field_statistics",
                dataset_id=target_dataset,
                fields=["pressure_approx_bar", "pressure_initial_atm"],
            ),
            _call("get_dataset_limitations", dataset_id=target_dataset, limit=50),
        )
        return _plan(
            "missing_as_zero",
            raw_question,
            AnswerType.numerical,
            EvidenceStatus.insufficient_evidence,
            accession=target_accession,
            dataset_id=target_dataset,
            calls=calls,
            expected_limitation_codes=(
                "measurement_has_no_canonical_values",
                "missing_not_zero",
            ),
            flags=frozenset({"refusal", "missing_values"}),
        )

    # ------------------------------------------------------------------
    # Citation and provenance questions.
    # ------------------------------------------------------------------
    citation_match = re.search(r"\bcit_[fr]_[A-Za-z0-9_-]{4,512}\b", raw_question)
    if citation_match:
        return scoped_plan(
            "citation_resolution",
            AnswerType.factual,
            EvidenceStatus.fully_supported,
            calls=(_call("resolve_citation", citation_id=citation_match.group(0)),),
        )

    if _has(text, "where did", "where does", "originate", "come from") and _has(text, "observation", "row", "record"):
        target_dataset = dataset_id or "psi-10-gas-flame"
        target_accession = accession or ACCESSION_BY_DATASET.get(target_dataset)
        calls = (
            _call(
                "query_gas_flame_tests",
                accession=target_accession,
                limit=1,
                sort="source_row",
                order="asc",
            ),
        )
        return _plan(
            "row_provenance",
            raw_question,
            AnswerType.factual,
            EvidenceStatus.fully_supported,
            accession=target_accession,
            dataset_id=target_dataset,
            calls=calls,
            flags=frozenset({"provenance"}),
        )

    if _has(text, "which source file supports", "source of", "supported by", "backed by"):
        target_dataset = dataset_id or ("psi-159-gas-flame" if _has(text, "psi-159") else None)
        target_accession = accession or ACCESSION_BY_DATASET.get(target_dataset or "")
        if target_dataset in GAS_FLAME_DATASETS and _has(text, "pressure", "bar", "atm"):
            calls = (
                _call(
                    "get_dataset_fields",
                    dataset_id=target_dataset,
                    physical_quantity="pressure",
                    limit=10,
                ),
            )
            return _plan(
                "pressure_source",
                raw_question,
                AnswerType.factual,
                EvidenceStatus.fully_supported,
                accession=target_accession,
                dataset_id=target_dataset,
                calls=calls,
                expected_limitation_codes=("pressure_unit_mismatch",),
                flags=frozenset({"provenance", "pressure"}),
            )
        if target_dataset:
            calls = (
                _call("get_dataset_fields", dataset_id=target_dataset, limit=25),
                _call("get_dataset_files", dataset_id=target_dataset, limit=20),
            )
            return _plan(
                "file_source_lookup",
                raw_question,
                AnswerType.factual,
                EvidenceStatus.fully_supported,
                accession=target_accession,
                dataset_id=target_dataset,
                calls=calls,
                flags=frozenset({"provenance"}),
            )

    # ------------------------------------------------------------------
    # Comparison questions.
    # ------------------------------------------------------------------
    if _has(text, "paired observations", "paired values", "paired data", "paired comparison"):
        return scoped_plan(
            "paired_observations",
            AnswerType.factual,
            EvidenceStatus.fully_supported,
            accession="PSI-159",
            dataset_id="psi-159-gas-flame",
            calls=(
                _call(
                    "evaluate_comparison",
                    left="psi-10-gas-flame.oxygen_mole_fraction",
                    right="psi-159-gas-flame.oxygen_mole_fraction",
                    conditions={
                        "same_oxygen_basis": True,
                        "flame_configuration_documented": True,
                    },
                ),
            ),
            expected_limitation_codes=(
                "no_verified_alignment",
                "comparison_not_approved",
            ),
            flags=frozenset({"comparison"}),
        )

    if _has(text, "why are some comparisons withheld", "why is a comparison withheld", "why are comparisons withheld", "why withheld"):
        return scoped_plan(
            "comparison_withheld",
            AnswerType.methodology,
            EvidenceStatus.fully_supported,
            calls=(
                _call(
                    "evaluate_comparison",
                    left="psi-10-gas-flame.oxygen_mole_fraction",
                    right="psi-159-gas-flame.oxygen_mole_fraction",
                ),
                _call(
                    "evaluate_comparison",
                    left="psi-10-gas-flame.pressure_initial_atm",
                    right="psi-159-gas-flame.pressure_initial_atm",
                ),
            ),
            retrieval_query="comparison alignment withholding conditions paired values",
            expected_limitation_codes=(
                "conditions_not_verified",
                "no_verified_alignment",
                "comparison_not_approved",
                "measurement_unavailable",
            ),
            flags=frozenset({"comparison"}),
        )

    if _has(text, "psi-10", "psi-159") and _has(text, "pressure") and _has(text, "compar"):
        return scoped_plan(
            "pressure_comparison",
            AnswerType.comparison,
            EvidenceStatus.unavailable_data,
            accession="PSI-159",
            dataset_id="psi-159-gas-flame",
            calls=(
                _call(
                    "evaluate_comparison",
                    left="psi-10-gas-flame.pressure_initial_atm",
                    right="psi-159-gas-flame.pressure_initial_atm",
                ),
                _call(
                    "evaluate_comparison",
                    left="psi-10-gas-flame.pressure_initial_atm",
                    right="psi-159-gas-flame.pressure_initial_atm",
                    conditions={
                        "same_pressure_basis": True,
                        "flame_configuration_documented": True,
                    },
                ),
                _call(
                    "dataset_field_statistics",
                    dataset_id="psi-159-gas-flame",
                    fields=["pressure_initial_atm", "pressure_approx_bar"],
                ),
            ),
            expected_limitation_codes=(
                "measurement_unavailable",
                "pressure_unit_mismatch",
                "no_verified_alignment",
            ),
            flags=frozenset({"comparison", "pressure"}),
        )

    if _has(text, "psi-10", "psi-159") and _has(text, "oxygen") and _has(text, "compar"):
        return scoped_plan(
            "oxygen_comparison",
            AnswerType.comparison,
            EvidenceStatus.partially_supported,
            accession="PSI-159",
            dataset_id="psi-159-gas-flame",
            calls=(
                _call(
                    "evaluate_comparison",
                    left="psi-10-gas-flame.oxygen_mole_fraction",
                    right="psi-159-gas-flame.oxygen_mole_fraction",
                ),
                _call(
                    "evaluate_comparison",
                    left="psi-10-gas-flame.oxygen_mole_fraction",
                    right="psi-159-gas-flame.oxygen_mole_fraction",
                    conditions={
                        "same_oxygen_basis": True,
                        "flame_configuration_documented": True,
                    },
                ),
            ),
            expected_limitation_codes=(
                "conditions_not_verified",
                "no_verified_alignment",
                "comparison_not_approved",
            ),
            flags=frozenset(
                {
                    "comparison",
                    "oxygen",
                    "without_conditions" if _has(text, "without verifying", "without conditions", "unverified") else "with_conditions_explained",
                }
            ),
        )

    # ------------------------------------------------------------------
    # Specific dataset and numerical questions.
    # ------------------------------------------------------------------
    if _has(text, "psi-98") and _has(text, "download", "404", "unavailable"):
        return scoped_plan(
            "psi98_unavailable",
            AnswerType.factual,
            EvidenceStatus.fully_supported,
            accession="PSI-98",
            dataset_id="psi-98-metadata",
            calls=(
                _call("get_dataset_files", dataset_id="psi-98-metadata", limit=20),
            ),
            expected_limitation_codes=("telemetry_404", "unavailable_not_downloadable"),
            flags=frozenset({"files"}),
        )

    if _has(text, "no public measurement files", "no measurement files", "without measurement files", "no public measurement file"):
        return scoped_plan(
            "datasets_without_measurement_files",
            AnswerType.factual,
            EvidenceStatus.fully_supported,
            accession="PSI-98",
            dataset_id="psi-98-metadata",
            calls=(
                _call("search_datasets", limit=10),
                _call("get_dataset_files", dataset_id="psi-98-metadata", limit=20),
            ),
            expected_limitation_codes=("telemetry_404", "metadata_only"),
            flags=frozenset({"files"}),
        )

    if _has(text, "which datasets contain telemetry", "datasets contain telemetry", "which datasets have telemetry"):
        return scoped_plan(
            "telemetry_datasets",
            AnswerType.factual,
            EvidenceStatus.fully_supported,
            calls=(
                _call("search_datasets", family="telemetry", limit=10),
                _call("search_datasets", family="smoke", limit=10),
                _call("get_dataset_files", dataset_id="psi-98-metadata", limit=20),
            ),
            expected_limitation_codes=("telemetry_404", "runs_are_separate"),
            flags=frozenset({"catalog", "telemetry"}),
        )

    if _has(text, "difference between the available gas-flame datasets", "difference between the gas-flame datasets", "difference between psi-10 and psi-159 datasets"):
        return scoped_plan(
            "gas_flame_difference",
            AnswerType.exploratory,
            EvidenceStatus.partially_supported,
            accession="PSI-159",
            dataset_id="psi-159-gas-flame",
            calls=(
                _call("search_datasets", family="gas_flame", limit=10),
                _call("gas_flame_statistics", accession="PSI-10"),
                _call("gas_flame_statistics", accession="PSI-159"),
                _call("get_dataset_limitations", dataset_id="psi-10-gas-flame", limit=50),
            ),
            expected_limitation_codes=(
                "pressure_unit_mismatch",
                "fuel_labels_not_cross_mapped",
            ),
            flags=frozenset({"comparison", "catalog"}),
        )

    if _has(text, "experiments are included in psi-10", "experiments included in psi-10", "what experiments are in psi-10"):
        return scoped_plan(
            "psi10_experiments",
            AnswerType.factual,
            EvidenceStatus.fully_supported,
            accession="PSI-10",
            dataset_id="psi-10-gas-flame",
            calls=(
                _call("get_investigation", accession="PSI-10"),
                _call("get_dataset", dataset_id="psi-10-gas-flame"),
                _call("get_dataset_fields", dataset_id="psi-10-gas-flame", limit=25),
                _call("get_dataset_limitations", dataset_id="psi-10-gas-flame", limit=50),
            ),
            expected_limitation_codes=("computed_tad_zst", "summary_table_only"),
            flags=frozenset({"catalog"}),
        )

    if _has(text, "what does the psi-159 dataset contain", "what does psi-159 contain", "what is in the psi-159 dataset"):
        return scoped_plan(
            "psi159_contents",
            AnswerType.factual,
            EvidenceStatus.fully_supported,
            accession="PSI-159",
            dataset_id="psi-159-gas-flame",
            calls=(
                _call("get_dataset", dataset_id="psi-159-gas-flame"),
                _call("gas_flame_statistics", accession="PSI-159"),
                _call("get_dataset_fields", dataset_id="psi-159-gas-flame", limit=25),
            ),
            expected_limitation_codes=(
                "undefined_tfp",
                "unexpanded_xf",
                "measurement_has_no_canonical_values",
            ),
            flags=frozenset({"catalog"}),
        )

    if _has(text, "how many valid psi-10", "psi-10 gas-flame records are available", "psi-10 records are available", "valid psi-10 gas-flame"):
        return scoped_plan(
            "psi10_valid_records",
            AnswerType.numerical,
            EvidenceStatus.fully_supported,
            accession="PSI-10",
            dataset_id="psi-10-gas-flame",
            calls=(_call("gas_flame_statistics", accession="PSI-10"),),
            expected_limitation_codes=("ramped_condition_rows",),
            flags=frozenset({"numerical", "gas_flame"}),
        )

    if _has(text, "how many valid psi-159", "psi-159 gas-flame records are available", "psi-159 records are available", "valid psi-159 gas-flame"):
        return scoped_plan(
            "psi159_valid_records",
            AnswerType.numerical,
            EvidenceStatus.fully_supported,
            accession="PSI-159",
            dataset_id="psi-159-gas-flame",
            calls=(_call("gas_flame_statistics", accession="PSI-159"),),
            expected_limitation_codes=("pressure_unit_mismatch",),
            flags=frozenset({"numerical", "gas_flame"}),
        )

    if _has(text, "pressure_initial_atm") and _has(text, "psi-159") and _has(text, "available", "values"):
        return scoped_plan(
            "psi159_pressure_initial",
            AnswerType.numerical,
            EvidenceStatus.unavailable_data,
            accession="PSI-159",
            dataset_id="psi-159-gas-flame",
            calls=(
                _call(
                    "dataset_field_statistics",
                    dataset_id="psi-159-gas-flame",
                    fields=["pressure_initial_atm", "pressure_approx_bar"],
                ),
                _call("get_dataset_limitations", dataset_id="psi-159-gas-flame", limit=50),
            ),
            expected_limitation_codes=(
                "measurement_has_no_canonical_values",
                "blank_means_missing",
            ),
            flags=frozenset({"numerical", "pressure"}),
        )

    if _has(text, "pressure information for psi-159", "psi-159 pressure information", "available pressure information"):
        return scoped_plan(
            "psi159_pressure_info",
            AnswerType.numerical,
            EvidenceStatus.partially_supported,
            accession="PSI-159",
            dataset_id="psi-159-gas-flame",
            calls=(
                _call(
                    "dataset_field_statistics",
                    dataset_id="psi-159-gas-flame",
                    fields=["pressure_approx_bar", "pressure_initial_atm"],
                ),
                _call("gas_flame_statistics", accession="PSI-159"),
                _call("get_dataset_limitations", dataset_id="psi-159-gas-flame", limit=50),
            ),
            expected_limitation_codes=(
                "measurement_has_no_canonical_values",
                "pressure_unit_mismatch",
            ),
            flags=frozenset({"numerical", "pressure"}),
        )

    if _has(text, "oxygen conditions in psi-10", "psi-10 oxygen conditions", "available oxygen conditions"):
        return scoped_plan(
            "psi10_oxygen",
            AnswerType.numerical,
            EvidenceStatus.partially_supported,
            accession="PSI-10",
            dataset_id="psi-10-gas-flame",
            calls=(
                _call(
                    "dataset_field_statistics",
                    dataset_id="psi-10-gas-flame",
                    fields=["oxygen_mole_fraction", "oxygen_mole_fraction_initial"],
                ),
                _call("gas_flame_statistics", accession="PSI-10"),
                _call("get_dataset_limitations", dataset_id="psi-10-gas-flame", limit=50),
            ),
            expected_limitation_codes=("blank_means_missing", "ramped_condition_rows"),
            flags=frozenset({"numerical", "oxygen"}),
        )

    if _has(text, "average measured peak_burner_temp_c", "average peak_burner_temp_c", "mean measured peak_burner_temp_c", "average measured peak burner temp", "average peak burner temp"):
        return scoped_plan(
            "psi159_peak_temp",
            AnswerType.numerical,
            EvidenceStatus.partially_supported,
            accession="PSI-159",
            dataset_id="psi-159-gas-flame",
            calls=(
                _call(
                    "dataset_field_statistics",
                    dataset_id="psi-159-gas-flame",
                    fields=["peak_burner_temp_c", "peak_burner_temp_k"],
                ),
                _call("get_dataset_limitations", dataset_id="psi-159-gas-flame", limit=50),
            ),
            expected_limitation_codes=(
                "method_not_documented",
                "do_not_merge_celsius_kelvin",
            ),
            flags=frozenset({"numerical", "temperature"}),
        )

    if _has(text, "measured flame temperature") and _has(text, "psi-10"):
        return scoped_plan(
            "psi10_measured_temperature",
            AnswerType.numerical,
            EvidenceStatus.unavailable_data,
            accession="PSI-10",
            dataset_id="psi-10-gas-flame",
            calls=(
                _call(
                    "dataset_field_statistics",
                    dataset_id="psi-10-gas-flame",
                    fields=[
                        "adiabatic_flame_temp_k",
                        "peak_burner_temp_c",
                        "peak_burner_temp_k",
                    ],
                ),
                _call("get_dataset_limitations", dataset_id="psi-10-gas-flame", limit=50),
            ),
            expected_limitation_codes=("computed_source_field", "measurement_unavailable"),
            flags=frozenset({"numerical", "temperature"}),
        )

    if _has(text, "measured and computed values") and _has(text, "psi-10"):
        return scoped_plan(
            "measured_vs_computed",
            AnswerType.methodology,
            EvidenceStatus.fully_supported,
            accession="PSI-10",
            dataset_id="psi-10-gas-flame",
            calls=(
                _call("get_dataset_fields", dataset_id="psi-10-gas-flame", limit=25),
                _call(
                    "dataset_field_statistics",
                    dataset_id="psi-10-gas-flame",
                    fields=[
                        "pressure_initial_atm",
                        "oxygen_mole_fraction",
                        "adiabatic_flame_temp_k",
                        "stoich_mixture_fraction",
                    ],
                ),
            ),
            expected_limitation_codes=("computed_tad_zst",),
            flags=frozenset({"methodology"}),
        )

    if _has(text, "how many telemetry runs", "number of telemetry runs", "telemetry runs are available"):
        target_accession = accession or "PSI-100"
        target_dataset = dataset_id or CURATED_DATASETS.get(target_accession, "psi-100-telemetry")
        return _plan(
            "telemetry_run_count",
            raw_question,
            AnswerType.numerical,
            EvidenceStatus.fully_supported,
            accession=target_accession,
            dataset_id=target_dataset,
            calls=(
                _call("get_telemetry_runs", accession=target_accession, limit=20),
                _call("get_dataset_limitations", dataset_id=target_dataset, limit=50),
            ),
            expected_limitation_codes=("runs_are_separate", "raw_not_calibrated"),
            flags=frozenset({"numerical", "telemetry"}),
        )

    if _has(text, "raw voltage") and _has(text, "smoke concentration", "concentration"):
        return scoped_plan(
            "psi100_raw_voltage",
            AnswerType.methodology,
            EvidenceStatus.insufficient_evidence,
            accession="PSI-100",
            dataset_id="psi-100-telemetry",
            calls=(
                _call("get_dataset_fields", dataset_id="psi-100-telemetry", limit=25),
                _call("get_dataset_limitations", dataset_id="psi-100-telemetry", limit=50),
            ),
            expected_limitation_codes=("raw_not_calibrated",),
            flags=frozenset({"refusal", "raw"}),
        )

    if _has(text, "flame-spread rate", "flame spread rate", "spread rate") and _has(text, "bass", "psi-25", "psi-26"):
        target_dataset = dataset_id or "psi-25-material"
        target_accession = accession or ACCESSION_BY_DATASET.get(target_dataset, "PSI-25")
        return _plan(
            "bass_flame_spread",
            raw_question,
            AnswerType.methodology,
            EvidenceStatus.insufficient_evidence,
            accession=target_accession,
            dataset_id=target_dataset,
            calls=(
                _call("get_dataset_limitations", dataset_id=target_dataset, limit=50),
            ),
            retrieval_query="flame spread rate BASS material test matrix validated method",
            retrieval_accession=target_accession,
            retrieval_dataset_id=target_dataset,
            expected_limitation_codes=("no_flame_spread_rate",),
            flags=frozenset({"refusal", "methodology"}),
        )

    if _has(text, "psi-26") and _has(text, "oxygen") and _has(text, "percent", "percentage", "%"):
        return scoped_plan(
            "psi26_oxygen_unit",
            AnswerType.factual,
            EvidenceStatus.insufficient_evidence,
            accession="PSI-26",
            dataset_id="psi-26-material",
            calls=(
                _call("get_dataset_fields", dataset_id="psi-26-material", limit=25),
                _call("get_dataset_limitations", dataset_id="psi-26-material", limit=50),
            ),
            expected_limitation_codes=("ambiguous_unit",),
            flags=frozenset({"refusal", "unit"}),
        )

    if _has(text, "what does acme flame design investigate", "acme flame design investigate", "explore acme flame design", "about acme flame design"):
        return scoped_plan(
            "acme_flame_design",
            AnswerType.methodology,
            EvidenceStatus.fully_supported,
            accession="PSI-10",
            dataset_id="psi-10-gas-flame",
            calls=(
                _call("get_investigation", accession="PSI-10"),
                _call("get_dataset_limitations", dataset_id="psi-10-gas-flame", limit=50),
            ),
            retrieval_query="ACME Flame Design investigation objective microgravity gas flames",
            retrieval_accession="PSI-10",
            retrieval_dataset_id="psi-10-gas-flame",
            expected_limitation_codes=("computed_tad_zst",),
            flags=frozenset({"investigation"}),
        )

    if _has(text, "purpose of saffire-iii", "what is saffire-iii", "what does saffire-iii measure", "about saffire-iii"):
        return scoped_plan(
            "saffire_iii",
            AnswerType.methodology,
            EvidenceStatus.fully_supported,
            accession="PSI-100",
            dataset_id="psi-100-telemetry",
            calls=(
                _call("get_investigation", accession="PSI-100"),
                _call("get_dataset", dataset_id="psi-100-telemetry"),
                _call("get_dataset_limitations", dataset_id="psi-100-telemetry", limit=50),
            ),
            expected_limitation_codes=("raw_not_calibrated", "runs_are_separate"),
            flags=frozenset({"investigation"}),
        )

    if _has(text, "same-r", "same r", "what information is available in same"):
        return scoped_plan(
            "same_r",
            AnswerType.factual,
            EvidenceStatus.fully_supported,
            accession="PSI-101",
            dataset_id="psi-101-smoke",
            calls=(
                _call("get_dataset", dataset_id="psi-101-smoke"),
                _call("get_dataset_fields", dataset_id="psi-101-smoke", limit=25),
                _call("get_dataset_limitations", dataset_id="psi-101-smoke", limit=50),
                _call("get_smoke_runs", accession="PSI-101", limit=50),
            ),
            expected_limitation_codes=("sentinel_values", "no_flame_spread_rate"),
            flags=frozenset({"dataset"}),
        )

    # ------------------------------------------------------------------
    # Catalog questions.
    # ------------------------------------------------------------------
    if _has(text, "which combustion investigations are available", "what investigations are available", "how many investigations", "list the investigations"):
        return scoped_plan(
            "investigation_catalog",
            AnswerType.factual,
            EvidenceStatus.fully_supported,
            calls=(
                _call("search_investigations", limit=30),
                _call("search_datasets", limit=10),
            ),
            expected_limitation_codes=("catalog_scope_curated",),
            flags=frozenset({"catalog"}),
        )

    if _has(text, "limitations of", "dataset limitations", "what are the limitations", "limitations for"):
        if dataset_id:
            return _plan(
                "dataset_limitations",
                raw_question,
                AnswerType.methodology,
                EvidenceStatus.fully_supported,
                accession=accession,
                dataset_id=dataset_id,
                calls=(
                    _call("get_dataset_limitations", dataset_id=dataset_id, limit=50),
                ),
                flags=frozenset({"limitations"}),
            )

    # ------------------------------------------------------------------
    # Generic scoped questions.
    # ------------------------------------------------------------------
    if _any_word(text, "investigate", "investigates", "investigation", "purpose", "objective") and accession:
        target_dataset = dataset_id or CURATED_DATASETS.get(accession)
        calls: list[PlannedCall] = [_call("get_investigation", accession=accession)]
        if target_dataset:
            calls.append(_call("get_dataset", dataset_id=target_dataset))
        return _plan(
            "investigation_overview",
            raw_question,
            AnswerType.methodology,
            EvidenceStatus.fully_supported,
            accession=accession,
            dataset_id=target_dataset,
            calls=tuple(calls),
            retrieval_query=f"{accession} investigation objective and methods",
            retrieval_accession=accession,
            retrieval_dataset_id=target_dataset,
            flags=frozenset({"investigation"}),
        )

    if dataset_id and _has(text, "pressure") and _any_word(text, "show", "available", "measurements", "fields"):
        return _plan(
            "pressure_fields",
            raw_question,
            AnswerType.factual,
            EvidenceStatus.partially_supported,
            accession=accession,
            dataset_id=dataset_id,
            calls=(
                _call(
                    "get_dataset_fields",
                    dataset_id=dataset_id,
                    physical_quantity="pressure",
                    limit=25,
                ),
                _call("get_dataset_limitations", dataset_id=dataset_id, limit=50),
            ),
            flags=frozenset({"fields", "pressure"}),
        )

    if dataset_id and _any_word(text, "dataset", "data", "contain", "contains", "overview", "about"):
        return _plan(
            "dataset_overview",
            raw_question,
            AnswerType.factual,
            EvidenceStatus.partially_supported,
            accession=accession,
            dataset_id=dataset_id,
            calls=(
                _call("get_dataset", dataset_id=dataset_id),
                _call("get_dataset_limitations", dataset_id=dataset_id, limit=50),
            ),
            flags=frozenset({"dataset"}),
        )

    # "Show the available pressure measurements" without a scope is a real
    # ambiguity: PSI-10 and PSI-159 use different pressure fields and units.
    if _has(text, "pressure measurement", "pressure measurements", "pressure fields"):
        return _plan(
            "clarification",
            raw_question,
            AnswerType.clarification_required,
            EvidenceStatus.insufficient_evidence,
            clarification_question=(
                "Which pressure measurement should I inspect? PSI-10 uses "
                "pressure_initial_atm (atm); PSI-159 uses pressure_approx_bar "
                "(bar) and has no pressure_initial_atm values."
            ),
            clarification_options=(
                "PSI-10 pressure_initial_atm",
                "PSI-159 pressure_approx_bar",
                "Compare PSI-10 and PSI-159 pressure",
            ),
            clarification_missing=("dataset",),
        )

    if _any_word(text, "it", "that", "this", "them", "those") and not accession and not dataset_id:
        return _plan(
            "clarification",
            raw_question,
            AnswerType.clarification_required,
            EvidenceStatus.insufficient_evidence,
            clarification_question=(
                "Which investigation or dataset does the follow-up refer to? "
                "No conversation context is available for this request."
            ),
            clarification_options=("PSI-10", "PSI-159", "PSI-100", "PSI-101"),
            clarification_missing=("accession_or_dataset",),
        )

    # ------------------------------------------------------------------
    # Retrieval-only fallback. It can explain verified documentation but can
    # never produce a numerical answer.
    # ------------------------------------------------------------------
    return _plan(
        "retrieval_overview",
        raw_question,
        AnswerType.exploratory,
        EvidenceStatus.partially_supported,
        accession=accession,
        dataset_id=dataset_id,
        retrieval_query=raw_question,
        retrieval_accession=accession,
        retrieval_dataset_id=dataset_id,
        expected_limitation_codes=("retrieval_context_only",),
        flags=frozenset({"retrieval"}),
    )
