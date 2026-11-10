"""Structural validation for the versioned golden question set."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.analytics.registry import load_registries
from src.assistant.contract import AnswerType, EvidenceStatus

GOLDEN_PATH = Path(__file__).with_name("golden_questions.json")
CATEGORIES = {
    "dataset_discovery",
    "experimental_understanding",
    "numerical",
    "limitations",
    "comparison",
    "provenance",
    "adversarial",
    "prompt_injection",
    "methodology",
}
REQUIRED_KEYS = {
    "question_id",
    "category",
    "question",
    "expected_evidence_status",
    "expected_answer_type",
    "expected_answer_behavior",
    "required_tools",
    "required_citation_types",
    "forbidden_claims",
}


@pytest.fixture(scope="module")
def golden() -> dict:
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def test_golden_set_is_versioned_and_matches_the_dataset(golden):
    assert golden["golden_version"] == "1.0.0"
    assert golden["contract_version"] == "1.0.0"
    assert golden["dataset_version"] == load_registries().dataset_version


def test_golden_set_has_unique_questions(golden):
    questions = golden["questions"]
    assert len(questions) >= 30
    ids = [item["question_id"] for item in questions]
    assert len(ids) == len(set(ids))
    assert len({item["question"] for item in questions}) == len(questions)


def test_every_question_has_the_required_contract(golden):
    evidence_values = {item.value for item in EvidenceStatus}
    answer_values = {item.value for item in AnswerType}
    for question in golden["questions"]:
        missing = REQUIRED_KEYS - set(question)
        assert not missing, (question["question_id"], missing)
        assert question["category"] in CATEGORIES
        assert question["expected_evidence_status"] in evidence_values
        assert question["expected_answer_type"] in answer_values
        assert isinstance(question["required_tools"], list)
        assert isinstance(question["required_citation_types"], list)
        assert set(question["required_citation_types"]) <= {"file", "row"}
        assert question["forbidden_claims"], question["question_id"]
        assert all(isinstance(tool, str) and tool for tool in question["required_tools"])


def test_every_category_is_covered(golden):
    categories = {item["category"] for item in golden["questions"]}
    assert categories == CATEGORIES


def test_numerical_questions_declare_expected_values(golden):
    for question in golden["questions"]:
        if question["category"] == "numerical":
            assert "expected_numeric" in question, question["question_id"]
        for expected in question.get("expected_numeric", []):
            assert expected["field"]
            assert isinstance(expected["value"], (int, float))
            assert expected["unit"]
            assert expected["tolerance"] >= 0


def test_adversarial_questions_have_forbidden_claims(golden):
    adversarial = [
        item
        for item in golden["questions"]
        if item["category"] in {"adversarial", "prompt_injection"}
    ]
    assert len(adversarial) >= 6
    for question in adversarial:
        assert question["forbidden_claims"]
        assert question["expected_evidence_status"] in {
            "insufficient_evidence",
            "unavailable_data",
        }
