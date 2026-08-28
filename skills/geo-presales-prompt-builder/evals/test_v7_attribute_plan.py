#!/usr/bin/env python3
"""Regression tests for the Topic-scoped v7 attribute-planning contract."""

from __future__ import annotations

import unittest

from test_v6_contract import MODULE, valid_v6_bank


def valid_v7_bank(topic_count: int = 1) -> dict:
    data = valid_v6_bank(topic_count)
    data["schema_version"] = MODULE.V7_SCHEMA_VERSION
    case_fields = data["config"]["case_fields"]
    plans = []
    for topic in data["config"]["topics"]:
        topic_id = topic["topic_id"]
        verification = next(
            row
            for row in data["questions"]
            if row["topic_id"] == topic_id
            and row["diagnosis_intent"] == "verification"
        )
        p1 = [
            {
                "attribute": f"{topic_id} shortlist attribute {index}",
                "source_field": item["source_field"],
                "source_value": item["source_value"],
                "decision_reason": "It can determine whether the supplier enters the shortlist.",
                "verification_statement": item["statement"],
            }
            for index, item in enumerate(verification["validation_items"], start=1)
        ]
        p2_sources = (
            "目标客户 1",
            "痛点 1",
            "使用场景 2",
            "产品特性 2",
            "适用边界",
        )
        p2 = [
            {
                "attribute": f"{topic_id} comparison attribute {index}",
                "source_field": source_field,
                "source_value": case_fields[source_field],
                "decision_reason": "It materially affects comparison or buyer preference.",
            }
            for index, source_field in enumerate(p2_sources, start=1)
        ]
        plans.append(
            {
                "topic_id": topic_id,
                "priorities": {"P1": p1, "P2": p2, "P3": []},
                "excluded": [
                    {
                        "candidate": f"{topic_id} catalog-only fact",
                        "source_field": "差异化优势",
                        "source_value": case_fields["差异化优势"],
                        "reason": "It does not change shortlist or selection decisions.",
                        "route": "exclude",
                    }
                ],
            }
        )
    data["config"]["attribute_plan"] = plans
    return data


class V7AttributePlanTests(unittest.TestCase):
    def test_v7_requires_and_accepts_one_attribute_plan_per_topic(self) -> None:
        for topic_count in (1, 2, 3):
            with self.subTest(topic_count=topic_count):
                data = valid_v7_bank(topic_count)
                errors, warnings, summary = MODULE.validate(data)
                self.assertEqual([], errors)
                self.assertEqual([], warnings)
                self.assertEqual(topic_count, len(summary["attribute_priority_counts"]))
                self.assertTrue(
                    all(
                        counts == {"P1": 3, "P2": 5, "P3": 0}
                        for counts in summary["attribute_priority_counts"].values()
                    )
                )

    def test_v7_rejects_missing_attribute_plan_but_v6_remains_readable(self) -> None:
        data = valid_v7_bank()
        del data["config"]["attribute_plan"]
        errors, _, _ = MODULE.validate(data)
        self.assertTrue(any("attribute_plan must be an array" in error for error in errors), errors)

        legacy = valid_v6_bank()
        errors, warnings, _ = MODULE.validate(legacy)
        self.assertEqual([], errors)
        self.assertEqual([], warnings)

    def test_v7_enforces_priority_counts_and_warns_on_thin_p2(self) -> None:
        data = valid_v7_bank()
        priorities = data["config"]["attribute_plan"][0]["priorities"]
        priorities["P1"] = priorities["P1"][:2]
        priorities["P2"] = priorities["P2"][:4]
        errors, warnings, _ = MODULE.validate(data)
        self.assertTrue(any("P1 must contain 3 to 5" in error for error in errors), errors)
        self.assertTrue(any("fewer than the recommended 5" in warning for warning in warnings), warnings)

    def test_v7_verification_must_exactly_follow_the_ordered_p1_plan(self) -> None:
        data = valid_v7_bank()
        verification = next(
            row for row in data["questions"] if row["diagnosis_intent"] == "verification"
        )
        verification["validation_items"] = list(reversed(verification["validation_items"]))
        verification["user_question"] = MODULE.build_v6_validation_prompt(
            data["config"]["brand_name"], verification["validation_items"]
        )
        verification["monitoring_prompt"] = verification["user_question"]
        errors, _, _ = MODULE.validate(data)
        self.assertTrue(
            any("must exactly match the ordered P1 attribute plan" in error for error in errors),
            errors,
        )

    def test_v7_rejects_untraceable_or_misrouted_attribute_candidates(self) -> None:
        data = valid_v7_bank()
        plan = data["config"]["attribute_plan"][0]
        plan["priorities"]["P2"][0]["source_value"] = "invented"
        plan["excluded"][0]["route"] = "P3"
        errors, _, _ = MODULE.validate(data)
        joined = "\n".join(errors)
        self.assertIn("source_value must equal its Case field", joined)
        self.assertIn("route must equal exclude or accuracy_only", joined)

    def test_v7_accepts_human_readable_chinese_attribute_labels(self) -> None:
        data = valid_v7_bank()
        plan = data["config"]["attribute_plan"][0]
        plan["priorities"]["P1"][0]["attribute"] = "视觉规格选型"
        plan["excluded"][0]["candidate"] = "官网产品目录归类"
        errors, warnings, _ = MODULE.validate(data)
        self.assertEqual([], errors)
        self.assertEqual([], warnings)


if __name__ == "__main__":
    unittest.main()
