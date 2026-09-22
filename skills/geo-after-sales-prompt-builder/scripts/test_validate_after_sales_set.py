#!/usr/bin/env python3
"""Focused contract tests for the after-sales validator."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("validate_after_sales_set.py")


def question(topic_id: str, number: int) -> dict[str, object]:
    text = f"Which category providers fit scenario {topic_id} {number}?"
    return {
        "question_id": f"{topic_id}-{number}",
        "topic_id": topic_id,
        "user_question": text,
        "zh_translation": f"问题 {number}",
        "monitoring_prompt": text,
        "region": "United States",
        "intent": "Discovery",
        "tags": ["Scenario"],
    }


def inherited_question(topic_id: str, number: int) -> dict[str, object]:
    row = question(topic_id, number)
    row.pop("intent")
    row["intent_key"] = f"{topic_id}-discovery-buyer-choice"
    row["tags"] = ["Intent: Discovery", "BrandScope: Non-Branded", "Scenario"]
    return row


def staged_bank(topic_count: int, lifecycle: str) -> dict[str, object]:
    topics = [{"topic_id": "topic_1", "topic": "Example Topic"}]
    return {
        "mode": "after-sales-strategic-topics",
        "config": {
            "generation_stage": "discovery",
            "lifecycle_status": lifecycle,
            "evidence_status": "customer_confirmed",
            "customer_confirmation": {"status": "confirmed"},
            "prompt_version": "v1",
            "topics": topics,
            "expected_total": topic_count,
        },
        "questions": [question("topic_1", number) for number in range(topic_count)],
    }


def validate(data: dict[str, object]) -> subprocess.CompletedProcess[str]:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", encoding="utf-8") as handle:
        json.dump(data, handle)
        handle.flush()
        return subprocess.run(
            [sys.executable, str(SCRIPT), handle.name],
            text=True,
            capture_output=True,
            check=False,
        )


class ValidateAfterSalesSetTests(unittest.TestCase):
    def test_hypothesis_topic_can_remain_below_five(self) -> None:
        result = validate(staged_bank(2, "hypothesis"))
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_formal_topic_requires_five_prompts(self) -> None:
        result = validate(staged_bank(4, "locked"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("at least 5 Prompts per Topic", result.stdout)

    def test_after_sales_signal_cannot_be_formal_ready(self) -> None:
        data = staged_bank(5, "locked")
        data["config"]["evidence_status"] = "after_sales_signal"
        result = validate(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("cannot be marked formal-ready", result.stdout)

    def test_discovery_stage_rejects_later_intents(self) -> None:
        data = staged_bank(5, "hypothesis")
        data["questions"][0]["intent"] = "Evaluation"
        result = validate(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("discovery stage must contain Discovery Prompts only", result.stdout)

    def test_inherited_intent_and_brand_scope_tags_are_normalized(self) -> None:
        data = staged_bank(5, "hypothesis")
        data["questions"] = [inherited_question("topic_1", number) for number in range(5)]
        result = validate(data)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_staged_inherited_long_topic_name_is_accepted(self) -> None:
        data = staged_bank(5, "hypothesis")
        data["config"]["topics"][0]["topic"] = (
            "LED display manufacturers and commercial display solution providers"
        )
        result = validate(data)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_conflicting_explicit_and_inherited_intent_fails(self) -> None:
        data = staged_bank(5, "hypothesis")
        data["questions"][0]["tags"] = ["Intent: Evaluation", "Scenario"]
        result = validate(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("explicit intent conflicts with Intent tag", result.stdout)

    def test_formal_baseline_metadata_cannot_bypass_lifecycle(self) -> None:
        data = staged_bank(5, "hypothesis")
        data["config"]["baseline"] = {
            "status": "formal",
            "window_days": 7,
            "calendar_days": True,
            "conditions_key": "us-en-v1",
            "valid_samples_only": True,
            "failures_as_zero": False,
        }
        result = validate(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("requires a locked or formal lifecycle", result.stdout)

    def test_required_question_fields_and_bad_stage_fail_cleanly(self) -> None:
        data = staged_bank(5, "hypothesis")
        data["config"]["generation_stage"] = ["discovery"]
        data["questions"][0]["question_id"] = ""
        data["questions"][0]["user_question"] = ""
        data["questions"][0]["zh_translation"] = ""
        result = validate(data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("question_id is required", result.stdout)
        self.assertIn("user_question is required", result.stdout)
        self.assertIn("zh_translation is required", result.stdout)
        self.assertIn("generation_stage must be one of", result.stdout)


if __name__ == "__main__":
    unittest.main()
