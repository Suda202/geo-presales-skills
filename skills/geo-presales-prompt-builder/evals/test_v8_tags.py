#!/usr/bin/env python3
"""Regression tests for the v8 Topic + free Tags contract."""

from __future__ import annotations

import unittest

from test_v7_attribute_plan import MODULE, valid_v7_bank


def valid_v8_bank(topic_count: int = 1) -> dict:
    data = valid_v7_bank(topic_count)
    data["schema_version"] = MODULE.V8_SCHEMA_VERSION
    quotas = data["config"]["quotas"]
    quotas["intent_tags"] = {
        MODULE.V8_INTENT_TAGS[role]: count
        for role, count in quotas.pop("diagnosis_intent").items()
    }
    quotas["per_topic"] = {
        MODULE.V8_INTENT_TAGS[role]: count
        for role, count in quotas["per_topic"].items()
    }
    if "topic_overrides" in quotas:
        quotas["topic_overrides"] = {
            topic_id: {
                MODULE.V8_INTENT_TAGS[role]: count
                for role, count in topic_quota.items()
            }
            for topic_id, topic_quota in quotas["topic_overrides"].items()
        }

    p1_by_topic = {
        plan["topic_id"]: [entry["attribute"] for entry in plan["priorities"]["P1"]]
        for plan in data["config"]["attribute_plan"]
    }
    discovery_index: dict[str, int] = {}
    for row in data["questions"]:
        role = row.pop("diagnosis_intent")
        branded = role in {"competitor", "verification", "accuracy", "evaluation"}
        tags = [
            MODULE.V8_INTENT_TAGS[role],
            MODULE.V8_BRAND_SCOPE_TAGS[branded],
        ]
        p1 = p1_by_topic[row["topic_id"]]
        if role == "verification":
            tags.extend(f"Attribute: {attribute}" for attribute in p1)
        elif role == "competitor":
            tags.append(f"Attribute: {p1[0]}")
        elif role == "discovery":
            index = discovery_index.get(row["topic_id"], 0)
            discovery_index[row["topic_id"]] = index + 1
            if index < len(p1):
                tags.append(f"Attribute: {p1[index]}")
        row["tags"] = tags
    return data


class V8TagsTests(unittest.TestCase):
    def test_v8_accepts_free_tags_and_uses_no_diagnosis_intent_field(self) -> None:
        data = valid_v8_bank(2)
        data["questions"][0]["tags"].extend(
            ["Lifecycle: Consideration", "Region: North America"]
        )
        errors, warnings, summary = MODULE.validate(data)
        self.assertEqual([], errors)
        self.assertEqual([], warnings)
        self.assertTrue(all("diagnosis_intent" not in row for row in data["questions"]))
        self.assertEqual(2, summary["tags"]["Intent: Verification"])
        self.assertEqual(1, summary["tags"]["Lifecycle: Consideration"])

    def test_v8_rejects_semicolons_inside_a_single_free_tag(self) -> None:
        data = valid_v8_bank()
        data["questions"][0]["tags"].append("Region: US; Intent: Evaluation")
        errors, _, _ = MODULE.validate(data)
        self.assertTrue(any("reserved CSV semicolon delimiter" in error for error in errors), errors)

    def test_v8_brand_scope_must_follow_actual_brand_mentions(self) -> None:
        data = valid_v8_bank()
        discovery = next(
            row for row in data["questions"] if "Intent: Discovery" in row["tags"]
        )
        discovery["tags"] = [
            "Brand Scope: Branded" if tag == "Brand Scope: Non-Branded" else tag
            for tag in discovery["tags"]
        ]
        errors, _, _ = MODULE.validate(data)
        self.assertTrue(any("Brand Scope must equal" in error for error in errors), errors)

    def test_v8_discovery_rejects_a_competitors_parenthetical_alias(self) -> None:
        data = valid_v8_bank()
        discovery = next(
            row for row in data["questions"] if "Intent: Discovery" in row["tags"]
        )
        discovery["user_question"] = (
            "Which LED display solution providers, including Shanghai Sansi, "
            "should buyers consider?"
        )
        discovery["monitoring_prompt"] = discovery["user_question"]
        errors, _, _ = MODULE.validate(data)
        self.assertTrue(any("Brand Scope must equal" in error for error in errors), errors)
        self.assertTrue(any("discovery must not name configured brands" in error for error in errors), errors)

    def test_v8_discovery_must_ask_for_candidates_not_provider_factors(self) -> None:
        data = valid_v8_bank()
        discovery = next(
            row for row in data["questions"] if "Intent: Discovery" in row["tags"]
        )
        discovery["user_question"] = (
            "Which factors should LED display solution providers consider when planning "
            "a fixed-installation project?"
        )
        discovery["monitoring_prompt"] = discovery["user_question"]
        errors, _, _ = MODULE.validate(data)
        self.assertTrue(
            any("discovery must request concrete candidates" in error for error in errors),
            errors,
        )

    def test_v8_discovery_rejects_provider_as_an_abstract_noun_modifier(self) -> None:
        data = valid_v8_bank()
        discovery = next(
            row for row in data["questions"] if "Intent: Discovery" in row["tags"]
        )
        discovery["user_question"] = (
            "Which provider capabilities matter most for a fixed-installation LED display project?"
        )
        discovery["monitoring_prompt"] = discovery["user_question"]
        errors, _, _ = MODULE.validate(data)
        self.assertTrue(
            any("discovery must request concrete candidates" in error for error in errors),
            errors,
        )

    def test_v8_attribute_tags_must_exist_in_the_current_topic_plan(self) -> None:
        data = valid_v8_bank()
        discovery = next(
            row for row in data["questions"] if "Intent: Discovery" in row["tags"]
        )
        discovery["tags"].append("Attribute: Invented Capability")
        errors, _, _ = MODULE.validate(data)
        self.assertTrue(
            any("must exist in the current Topic attribute_plan" in error for error in errors),
            errors,
        )

    def test_v8_allows_the_same_attribute_tag_across_topics(self) -> None:
        data = valid_v8_bank(2)
        shared = "Night Vision"
        for plan in data["config"]["attribute_plan"]:
            old = plan["priorities"]["P1"][0]["attribute"]
            plan["priorities"]["P1"][0]["attribute"] = shared
            for row in data["questions"]:
                if row["topic_id"] == plan["topic_id"]:
                    row["tags"] = [
                        f"Attribute: {shared}" if tag == f"Attribute: {old}" else tag
                        for tag in row["tags"]
                    ]
        errors, warnings, summary = MODULE.validate(data)
        self.assertEqual([], errors)
        self.assertEqual([], warnings)
        self.assertGreaterEqual(summary["tags"]["Attribute: Night Vision"], 4)

    def test_v8_discovery_attribute_tags_cover_every_p1(self) -> None:
        data = valid_v8_bank()
        p1 = data["config"]["attribute_plan"][0]["priorities"]["P1"][0]["attribute"]
        for row in data["questions"]:
            if "Intent: Discovery" in row["tags"]:
                row["tags"] = [tag for tag in row["tags"] if tag != f"Attribute: {p1}"]
        errors, _, _ = MODULE.validate(data)
        self.assertTrue(
            any("Discovery Attribute tags must cover every P1" in error for error in errors),
            errors,
        )

    def test_v8_verification_attribute_tags_follow_ordered_p1(self) -> None:
        data = valid_v8_bank()
        verification = next(
            row for row in data["questions"] if "Intent: Verification" in row["tags"]
        )
        attribute_tags = [tag for tag in verification["tags"] if tag.startswith("Attribute: ")]
        other_tags = [tag for tag in verification["tags"] if not tag.startswith("Attribute: ")]
        verification["tags"] = other_tags + list(reversed(attribute_tags))
        errors, _, _ = MODULE.validate(data)
        self.assertTrue(
            any("must exactly match the ordered P1 plan" in error for error in errors),
            errors,
        )

    def test_v8_rejects_retired_diagnosis_and_parallel_attributes_fields(self) -> None:
        data = valid_v8_bank()
        data["questions"][0]["diagnosis_intent"] = "discovery"
        data["questions"][0]["attributes"] = []
        errors, _, _ = MODULE.validate(data)
        joined = "\n".join(errors)
        self.assertIn("diagnosis_intent", joined)
        self.assertIn("attributes", joined)

    def test_v8_routes_are_not_changed_by_extra_free_tags(self) -> None:
        data = valid_v8_bank()
        competitor = next(
            row for row in data["questions"] if "Intent: Competitor" in row["tags"]
        )
        competitor["tags"].append("Intent: Custom Buyer Comparison")
        competitor["analysis_type"] = "sentiment"
        errors, _, _ = MODULE.validate(data)
        self.assertTrue(any("analysis_type must equal visibility" in error for error in errors), errors)

    def test_v8_competitor_attribute_tags_must_be_non_empty_and_isomorphic(self) -> None:
        missing = valid_v8_bank()
        for row in missing["questions"]:
            if "Intent: Competitor" in row["tags"]:
                row["tags"] = [
                    tag for tag in row["tags"] if not tag.startswith("Attribute: ")
                ]
        errors, _, _ = MODULE.validate(missing)
        self.assertTrue(
            any("Competitor must include at least one Attribute tag" in error for error in errors),
            errors,
        )

        mismatched = valid_v8_bank()
        competitors = [
            row for row in mismatched["questions"] if "Intent: Competitor" in row["tags"]
        ]
        second_p1 = mismatched["config"]["attribute_plan"][0]["priorities"]["P1"][1]["attribute"]
        competitors[1]["tags"] = [
            f"Attribute: {second_p1}" if tag.startswith("Attribute: ") else tag
            for tag in competitors[1]["tags"]
        ]
        errors, _, _ = MODULE.validate(mismatched)
        self.assertTrue(
            any("Competitor Attribute tags must keep the same dimensions" in error for error in errors),
            errors,
        )

    def test_v8_rejects_non_array_p1_without_crashing(self) -> None:
        data = valid_v8_bank()
        data["config"]["attribute_plan"][0]["priorities"]["P1"] = 1
        errors, _, _ = MODULE.validate(data)
        self.assertTrue(any("priorities.P1 must be an array" in error for error in errors), errors)

    def test_v8_rejects_too_many_verification_items_without_crashing(self) -> None:
        data = valid_v8_bank()
        verification = next(
            row for row in data["questions"] if "Intent: Verification" in row["tags"]
        )
        verification["validation_items"] = verification["validation_items"] * 2
        errors, _, _ = MODULE.validate(data)
        self.assertTrue(any("validation_items must contain 3 to 5" in error for error in errors), errors)

    def test_v8_rejects_non_string_analysis_type_without_crashing(self) -> None:
        data = valid_v8_bank()
        data["questions"][0]["analysis_type"] = []
        errors, _, _ = MODULE.validate(data)
        self.assertTrue(any("analysis_type must equal" in error for error in errors), errors)

    def test_v8_evaluation_is_target_only_and_rejects_competitors(self) -> None:
        data = valid_v8_bank()
        errors, warnings, _ = MODULE.validate(data)
        self.assertEqual([], errors)
        self.assertEqual([], warnings)
        evaluation = next(
            row
            for row in data["questions"]
            if "Intent: Evaluation" in row["tags"]
        )
        evaluation["user_question"] = evaluation["user_question"].replace(
            "Edgelight", "Unilumin"
        )
        evaluation["monitoring_prompt"] = evaluation["user_question"]
        errors, _, _ = MODULE.validate(data)
        self.assertTrue(
            any("evaluation must name only the target brand" in error for error in errors),
            errors,
        )

    def test_v8_accepts_uneven_attribute_driven_topic_counts(self) -> None:
        data = valid_v8_bank(3)
        discovery_limits = {"topic_1": 12, "topic_2": 10, "topic_3": 10}
        seen = {topic_id: 0 for topic_id in discovery_limits}
        retained = []
        for row in data["questions"]:
            if "Intent: Discovery" not in row["tags"]:
                retained.append(row)
                continue
            topic_id = row["topic_id"]
            seen[topic_id] += 1
            if seen[topic_id] <= discovery_limits[topic_id]:
                retained.append(row)
        data["questions"] = retained

        def quota(discovery: int) -> dict[str, int]:
            return {
                "Intent: Discovery": discovery,
                "Intent: Competitor": 3,
                "Intent: Verification": 1,
                "Intent: Accuracy": 0,
                "Intent: Evaluation": 1,
                "Intent: Category Awareness": 1,
            }

        data["config"]["quotas"] = {
            "intent_tags": {
                "Intent: Discovery": 32,
                "Intent: Competitor": 9,
                "Intent: Verification": 3,
                "Intent: Accuracy": 0,
                "Intent: Evaluation": 3,
                "Intent: Category Awareness": 3,
            },
            "per_topic": quota(12),
            "topic_overrides": {
                "topic_2": quota(10),
                "topic_3": quota(10),
            },
        }
        data["config"]["expected_total"] = 50

        errors, warnings, summary = MODULE.validate(data)
        self.assertEqual([], errors)
        self.assertEqual([], warnings)
        self.assertEqual(
            {"topic 1": 18, "topic 2": 16, "topic 3": 16},
            {
                topic_id: sum(counts.values())
                for topic_id, counts in summary["topic_default_intent_tags"].items()
            },
        )

    def test_v8_requires_discovery_to_be_each_topics_strict_majority(self) -> None:
        data = valid_v8_bank()
        discoveries = [
            row for row in data["questions"] if "Intent: Discovery" in row["tags"]
        ]
        remove_ids = {row["question_id"] for row in discoveries[6:]}
        data["questions"] = [
            row for row in data["questions"] if row["question_id"] not in remove_ids
        ]
        data["config"]["quotas"]["per_topic"]["Intent: Discovery"] = 6
        data["config"]["quotas"]["intent_tags"]["Intent: Discovery"] = 6
        data["config"]["expected_total"] = 12

        errors, _, _ = MODULE.validate(data)
        self.assertTrue(
            any("discovery must be a strict majority" in error for error in errors),
            errors,
        )

    def test_v8_topic_range_is_guidance_not_a_hard_quota(self) -> None:
        data = valid_v8_bank()
        source = next(
            row for row in data["questions"] if "Intent: Discovery" in row["tags"]
        )
        for index in range(15, 22):
            row = dict(source)
            row["question_id"] = f"Q-topic_1-D{index:02d}"
            row["intent_key"] = f"topic_1-discovery-D{index:02d}"
            row["user_question"] = (
                "Which LED display solution providers should buyers consider for "
                f"an additional distinct requirement {index}?"
            )
            row["monitoring_prompt"] = row["user_question"]
            data["questions"].append(row)
        data["config"]["quotas"]["per_topic"]["Intent: Discovery"] = 21
        data["config"]["quotas"]["intent_tags"]["Intent: Discovery"] = 21
        data["config"]["expected_total"] = 27

        errors, warnings, summary = MODULE.validate(data)
        self.assertEqual([], errors)
        self.assertEqual(27, summary["total"])
        self.assertTrue(any("recommended 10-25 range" in warning for warning in warnings), warnings)

    def test_v8_csv_uses_one_semicolon_delimited_free_tags_column(self) -> None:
        headers = MODULE.V8_CSV_HEADERS
        rows = [
            {
                "query": "Which providers should I consider?",
                "question_zh": "应考虑哪些供应商？",
                "topic": "主题",
                "tags": "Intent: Discovery; Brand Scope: Non-Branded; Attribute: Easy to Use; Lifecycle: Consideration",
                "question_types": "visibility,sentiment",
                "purchase_intent": "",
                "persona_name": "",
                "scene_name": "",
            }
        ]
        errors, summary = MODULE.validate_v8_csv_rows(headers, rows)
        self.assertEqual([], errors)
        self.assertEqual(1, summary["tags"]["Attribute: Easy to Use"])

    def test_v8_csv_rejects_wrong_brand_scope_and_empty_attribute(self) -> None:
        rows = [
            {
                "query": "How well does Edgelight perform for LED display buyers?",
                "question_zh": "Edgelight 对 LED 显示屏买家的表现如何？",
                "topic": "LED 显示屏",
                "tags": "Intent: Evaluation; Brand Scope: Non-Branded; Attribute:",
                "question_types": "sentiment",
                "purchase_intent": "",
                "persona_name": "",
                "scene_name": "",
            }
        ]
        errors, _ = MODULE.validate_v8_csv_rows(MODULE.V8_CSV_HEADERS, rows)
        self.assertTrue(any("Brand Scope must equal" in error for error in errors), errors)
        self.assertTrue(any("Attribute labels must be non-empty" in error for error in errors), errors)

    def test_v8_csv_competitor_attribute_tags_must_be_non_empty_and_isomorphic(self) -> None:
        def competitor_row(query: str, attribute: str = "") -> dict:
            attribute_tag = f"; Attribute: {attribute}" if attribute else ""
            return {
                "query": query,
                "question_zh": "对比两个品牌。",
                "topic": "LED 显示屏",
                "tags": f"Intent: Competitor; Brand Scope: Branded{attribute_tag}",
                "question_types": "visibility,sentiment",
                "purchase_intent": "",
                "persona_name": "",
                "scene_name": "",
            }

        missing = [competitor_row("Should buyers choose Edgelight or Unilumin?")]
        errors, _ = MODULE.validate_v8_csv_rows(MODULE.V8_CSV_HEADERS, missing)
        self.assertTrue(
            any("Competitor must include at least one Attribute tag" in error for error in errors),
            errors,
        )

        mismatched = [
            competitor_row("Should buyers choose Edgelight or Unilumin?", "Brightness"),
            competitor_row("Should buyers choose Edgelight or LianTronics?", "Refresh Rate"),
        ]
        errors, _ = MODULE.validate_v8_csv_rows(MODULE.V8_CSV_HEADERS, mismatched)
        self.assertTrue(
            any("Competitor Attribute tags must keep the same dimensions" in error for error in errors),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
