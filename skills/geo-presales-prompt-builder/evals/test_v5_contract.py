#!/usr/bin/env python3
"""Regression tests for the three-topic / attribute-aware v5 contract."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_question_bank.py"
SPEC = importlib.util.spec_from_file_location("validate_question_bank", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def base_config() -> dict:
    topics = [
        {"topic_id": "coverage", "topic_type": "coverage", "topic": "AI search visibility platforms"},
        {"topic_id": "depth_1", "topic_type": "depth", "topic": "AI visibility for agencies"},
        {"topic_id": "depth_2", "topic_type": "depth", "topic": "Enterprise AI visibility reporting"},
    ]
    return {
        "expected_total": 51,
        "brand_name": "Target",
        "brand_object_type": "company",
        "category_label": "AI search visibility platform",
        "topics": topics,
        "target_attributes": [
            {
                "attribute_id": "ATTR-001",
                "attribute_type": "capability",
                "attribute": "multi-engine visibility measurement",
                "business_relevance": "Changes enterprise platform selection.",
                "evidence_sources": [
                    {"evidence_type": "official", "detail": "https://target.example/product"}
                ],
                "topic_ids": ["coverage", "depth_2"],
            },
            {
                "attribute_id": "ATTR-002",
                "attribute_type": "audience",
                "attribute": "agency multi-brand workflows",
                "business_relevance": "Defines the agency buying use case.",
                "evidence_sources": [
                    {"evidence_type": "input", "detail": "Customer evaluation brief"}
                ],
                "topic_ids": ["depth_1"],
            },
        ],
        "quotas": {
            "diagnostic_intent": {
                "discovery": 30,
                "competitor": 9,
                "validation": 3,
                "accuracy": 3,
                "sentiment": 3,
                "market_perception": 3,
            },
            "per_topic": {
                "discovery": 10,
                "competitor": 3,
                "validation": 1,
                "accuracy": 1,
                "sentiment": 1,
                "market_perception": 1,
            },
        },
        "competitor_selection": {
            "status": "frozen",
            "selection_count": 3,
            "formal_competitors": [
                {"name": "Alpha"},
                {"name": "Beta"},
                {"name": "Gamma"},
            ],
        },
    }


def valid_v5_bank() -> dict:
    config = base_config()
    attributes_by_topic = {
        "coverage": "ATTR-001",
        "depth_1": "ATTR-002",
        "depth_2": "ATTR-001",
    }
    questions = []
    for topic in config["topics"]:
        topic_id = topic["topic_id"]
        topic_type = topic["topic_type"]
        attribute_id = attributes_by_topic[topic_id]

        def append(intent: str, suffix: str, text: str, **extra) -> str:
            question_id = f"Q-{topic_id}-{suffix}"
            questions.append(
                {
                    "question_id": question_id,
                    "topic_id": topic_id,
                    "topic_type": topic_type,
                    "diagnostic_intent": intent,
                    "metric_scopes": list(MODULE.V5_METRIC_SCOPES[intent]),
                    "attribute_ids": [attribute_id],
                    "intent_key": f"{topic_id}-{intent}-{suffix}",
                    "user_question": text,
                    "zh_translation": f"这是 {topic_id} 下的{intent}测试问题。",
                    "monitoring_prompt": text,
                    "quality_checks": {"reviewed": True},
                    **extra,
                }
            )
            return question_id

        discovery_ids = [
            append(
                "discovery",
                f"D{index:02d}",
                f"Which AI search visibility platforms fit {topic_id} use case {index}?",
            )
            for index in range(1, 11)
        ]
        for index, competitor in enumerate(("Alpha", "Beta", "Gamma"), 1):
            append(
                "competitor",
                f"C{index:02d}",
                f"How do Target and {competitor} compare as AI search visibility platforms for {topic_id}?",
            )
        append(
            "validation",
            "V01",
            f"Does Target support the tested AI visibility attribute for {topic_id}?",
            paired_discovery_ids=[discovery_ids[0]],
        )
        append(
            "accuracy",
            "A01",
            f"What does Target officially state about its AI visibility support for {topic_id}?",
            fact_value="Supported",
            official_source_url="https://target.example/product",
            fact_checked_at="2026-08-25",
        )
        append(
            "sentiment",
            "S01",
            f"Evaluate Target as an AI search visibility platform for {topic_id}.",
        )
        append(
            "market_perception",
            "M01",
            f"What criteria matter when choosing AI search visibility platforms for {topic_id}?",
        )
    return {
        "schema_version": "overseas-geo-question-bank/v5",
        "config": config,
        "questions": questions,
    }


class V5ContractTests(unittest.TestCase):
    def test_complete_three_topic_bank_passes(self) -> None:
        errors, warnings, summary = MODULE.validate(valid_v5_bank())
        self.assertEqual([], errors)
        self.assertEqual([], warnings)
        self.assertEqual(51, summary["total"])
        self.assertEqual(30, summary["diagnostic_intent"]["discovery"])
        self.assertEqual(17, sum(summary["topic_diagnostic_intent"]["coverage"].values()))

    def test_v5_is_supported_and_rejects_observed_associations_in_case_config(self) -> None:
        config = base_config()
        config["observed_associations"] = [{"attribute_id": "ATTR-001", "association": "known"}]
        errors, _, _ = MODULE.validate(
            {
                "schema_version": "overseas-geo-question-bank/v5",
                "config": config,
                "questions": [],
            }
        )
        self.assertFalse(any("unsupported schema_version" in error for error in errors))
        self.assertTrue(
            any("observed_associations" in error and "采集结果" in error for error in errors),
            errors,
        )

    def test_v5_enforces_three_topics_51_questions_and_target_attributes(self) -> None:
        config = base_config()
        config["expected_total"] = 50
        config["topics"] = config["topics"][:1]
        config["target_attributes"] = []
        errors, _, _ = MODULE.validate(
            {
                "schema_version": "overseas-geo-question-bank/v5",
                "config": config,
                "questions": [],
            }
        )
        joined = "\n".join(errors)
        self.assertIn("expected_total must equal 51 in v5", joined)
        self.assertIn("topics must contain exactly 3 topics in v5", joined)
        self.assertIn("target_attributes must contain at least one selected attribute", joined)


if __name__ == "__main__":
    unittest.main()
