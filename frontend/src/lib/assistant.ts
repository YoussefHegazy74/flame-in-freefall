import type {
  AssistantAnswerType,
  AssistantConfidence,
  AssistantEvidenceStatus,
  AssistantSeverity,
  AssistantToolStatus,
} from "@/lib/api/types";

export type AssistantTone =
  | "neutral"
  | "cyan"
  | "ember"
  | "emerald"
  | "amber"
  | "rose"
  | "violet"
  | "outline";

export const EVIDENCE_STATUS_LABELS: Record<AssistantEvidenceStatus, string> = {
  fully_supported: "Fully supported",
  partially_supported: "Partially supported",
  insufficient_evidence: "Insufficient evidence",
  unavailable_data: "Unavailable data",
  conflicting_evidence: "Conflicting evidence",
};

export const EVIDENCE_STATUS_TONES: Record<AssistantEvidenceStatus, AssistantTone> = {
  fully_supported: "emerald",
  partially_supported: "amber",
  insufficient_evidence: "rose",
  unavailable_data: "neutral",
  conflicting_evidence: "rose",
};

export const EVIDENCE_STATUS_DESCRIPTIONS: Record<
  AssistantEvidenceStatus,
  string
> = {
  fully_supported:
    "Every factual or numerical content item is backed by a deterministic tool result and a citation that resolved through the Phase 4 registry.",
  partially_supported:
    "Some context is retrieved and labeled, but not every part of the answer is a directly verified measurement. Treat it as orientation, not proof.",
  insufficient_evidence:
    "The curated artifacts do not support the requested result. No value was invented or imputed.",
  unavailable_data:
    "The requested data is not available in the curated artifacts. Absence of data is not evidence that the phenomenon does not exist.",
  conflicting_evidence:
    "The available sources conflict. The conflict was preserved, not silently resolved.",
};

export const ANSWER_TYPE_LABELS: Record<AssistantAnswerType, string> = {
  factual: "Factual",
  numerical: "Numerical",
  exploratory: "Exploratory",
  comparison: "Comparison",
  methodology: "Methodology",
  clarification_required: "Clarification required",
};

export const CONFIDENCE_TONES: Record<AssistantConfidence, AssistantTone> = {
  high: "emerald",
  moderate: "amber",
  low: "rose",
};

export const TOOL_STATUS_TONES: Record<AssistantToolStatus, AssistantTone> = {
  ok: "emerald",
  empty: "neutral",
  rejected: "amber",
  failed: "rose",
};

export const LIMITATION_TONES: Record<AssistantSeverity, AssistantTone> = {
  error: "rose",
  warning: "amber",
  info: "cyan",
};

export function humanizeIdentifier(value: string): string {
  return value.replace(/_/g, " ");
}

export function assistantModeLabel(
  mode: "deterministic" | "provider" | "fallback",
  enabled: boolean,
): string {
  if (!enabled) return "Disabled";
  if (mode === "provider") return "Provider rephrase";
  if (mode === "fallback") return "Deterministic fallback";
  return "Deterministic";
}

/**
 * Preserve the exact serialized value. Assistant numbers are scientific
 * evidence; this UI must never round or reformat them.
 */
export function displayAssistantValue(value: unknown): string {
  if (value === null) return "null";
  if (value === undefined) return "—";
  if (typeof value === "number") return String(value);
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
