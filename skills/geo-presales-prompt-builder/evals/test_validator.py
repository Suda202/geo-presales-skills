#!/usr/bin/env python3
"""Focused regression tests for deterministic question-bank quality gates."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from validate_question_bank import BARE_ACTION, PROMOTIONAL_DRIVER, validate  # noqa: E402


def validate_fixture(name: str) -> tuple[list[str], list[str], dict]:
    data = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return validate(data)


def make_question(base: dict, question_id: str, question_type: str, funnel: str, text: str, audience: str) -> dict:
    row = dict(base)
    row.update({
        "question_id": question_id,
        "topic_id": base.get("topic_id", "topic-1"),
        "question_type": question_type,
        "funnel_intent": funnel,
        "intent_key": f"intent-{question_id.lower()}",
        "audience_role": audience,
        "cluster": f"cluster_{question_id}",
        "scenario": f"scenario_{question_id}",
        "constraint": f"constraint_{question_id}",
        "user_question": text,
        "zh_translation": f"这是问题 {question_id} 的中文翻译。",
        "standalone_rewrite": text.rstrip("?") + " in the United States?",
        "retrieval_rewrite": f"retrieval query {question_id}",
        "evidence_query": f"evidence query {question_id}",
        "title_seed": f"Question title {question_id}",
        "monitoring_prompt": text,
    })
    return row


def empty_term_config(data: dict) -> None:
    data["config"]["professional_term_assessment"] = {
        "status": "completed",
        "decisions": [],
        "no_required_terms_reason": "No professional term is required for this focused fixture.",
    }
    data["config"]["required_term_coverage"] = {}


class ValidatorRegressionTest(unittest.TestCase):
    def test_task89_bpi_regressions_stay_split_and_evidence_bounded(self) -> None:
        regressions = json.loads(
            (Path(__file__).resolve().parent / "task89_bpi_regressions.json").read_text(encoding="utf-8")
        )
        self.assertIn("未获得线上英文原题", regressions["source_boundary"])
        self.assertEqual(4, len(regressions["cases"]))
        by_id = {case["case_id"]: case for case in regressions["cases"]}
        self.assertEqual([4768], by_id["task-89-4768"]["task_ids"])
        self.assertEqual([4778], by_id["task-89-4778"]["task_ids"])
        self.assertEqual([4789], by_id["task-89-4789"]["task_ids"])
        self.assertEqual(
            [4751, 4753, 4754, 4755, 4757, 4758, 4759],
            by_id["task-89-false-recommendation"]["task_ids"],
        )
        self.assertEqual(
            {"purchasing_object_drift", "false_commercial_intent"},
            {case["failure_family"] for case in regressions["cases"]},
        )

    def test_valid_bank_passes_new_hard_gates(self) -> None:
        errors, warnings, summary = validate_fixture("valid-bank.json")
        self.assertEqual([], errors)
        self.assertEqual([], warnings)
        self.assertEqual(0, summary["quality_patterns"]["promotional_driver_count"])
        self.assertEqual({"direct": 1, "adjacent": 1, "fallback": 1}, summary["formal_competitor_tiers"])
        self.assertEqual({"topic 1": 1}, summary["brand_sentiment_by_topic"])

    def test_bpi_bad_case_fails_category_and_commercial_intent_gates(self) -> None:
        errors, _, summary = validate_fixture("bpi-bad-case-bank.json")
        joined = "\n".join(errors)
        self.assertIn("contains category-placeholder terms ['specialized product suppliers']", joined)
        self.assertIn("category is not visible in the standalone question", joined)
        self.assertIn("quality checks not passed ['commercial_intent']", joined)
        self.assertEqual(3, summary["category_visible_count"])

    def test_bpi_product_term_and_yes_no_decision_pass(self) -> None:
        errors, warnings, summary = validate_fixture("bpi-commercial-bank.json")
        self.assertEqual([], errors)
        self.assertEqual([], warnings)
        self.assertEqual(4, summary["category_visible_count"])
        self.assertEqual(4, summary["commercial_intent_review_count"])

    def test_one_branded_sentiment_template_is_required_per_topic(self) -> None:
        data = json.loads((FIXTURES / "valid-bank.json").read_text(encoding="utf-8"))
        errors, _, _ = validate(data)
        self.assertEqual([], errors)

        data = json.loads((FIXTURES / "valid-bank.json").read_text(encoding="utf-8"))
        data["config"]["brand_name"] = ""
        errors, _, _ = validate(data)
        self.assertTrue(any("brand_name must be a non-empty string" in error for error in errors), errors)

        data["questions"][3]["user_question"] = (
            "Evaluate the AI search visibility product Peec AI on AI search visibility platform selection"
        )
        data["questions"][3]["monitoring_prompt"] = data["questions"][3]["user_question"]
        errors, _, _ = validate(data)
        self.assertTrue(any("invalid brand sentiment template" in error for error in errors), errors)

        data = json.loads((FIXTURES / "valid-bank.json").read_text(encoding="utf-8"))
        data["questions"][3]["user_question"] += "?"
        data["questions"][3]["monitoring_prompt"] = data["questions"][3]["user_question"]
        errors, _, _ = validate(data)
        self.assertTrue(any("invalid brand sentiment template" in error for error in errors), errors)

        data = json.loads((FIXTURES / "valid-bank.json").read_text(encoding="utf-8"))
        data["questions"][3]["funnel_intent"] = "recommendation"
        errors, _, _ = validate(data)
        self.assertTrue(any("brand sentiment question must use funnel_intent='decision'" in error for error in errors), errors)

        data = json.loads((FIXTURES / "valid-bank.json").read_text(encoding="utf-8"))
        data["questions"][3]["question_type"] = "generic"
        errors, _, _ = validate(data)
        self.assertTrue(any("brand sentiment question must use question_type='branded'" in error for error in errors), errors)

        data = json.loads((FIXTURES / "valid-bank.json").read_text(encoding="utf-8"))
        data["questions"][3]["topic_id"] = "unknown-topic"
        errors, _, _ = validate(data)
        self.assertTrue(any("is not in config.topics" in error for error in errors), errors)

        data = json.loads((FIXTURES / "valid-bank.json").read_text(encoding="utf-8"))
        competitor_prompt = (
            "Evaluate the AI search visibility company Peec AI on AI search visibility platform selection with Profound"
        )
        data["questions"][3]["user_question"] = competitor_prompt
        data["questions"][3]["monitoring_prompt"] = competitor_prompt
        errors, _, _ = validate(data)
        self.assertTrue(any("brand sentiment question names competitors" in error for error in errors), errors)

        data = json.loads((FIXTURES / "valid-bank.json").read_text(encoding="utf-8"))
        data["questions"][3]["user_question"] = "Is Peec AI suitable for AI search visibility platform selection?"
        data["questions"][3]["monitoring_prompt"] = data["questions"][3]["user_question"]
        errors, _, _ = validate(data)
        self.assertTrue(any("COVERAGE brand_sentiment.topic 1" in error for error in errors), errors)

        data = json.loads((FIXTURES / "valid-bank.json").read_text(encoding="utf-8"))
        duplicate = dict(data["questions"][3])
        duplicate["question_id"] = "Q5"
        duplicate["intent_key"] = "brand-sentiment-duplicate"
        duplicate["standalone_rewrite"] = duplicate["standalone_rewrite"].rstrip(".") + " for review."
        data["questions"].append(duplicate)
        data["config"]["expected_total"] = 5
        data["config"]["quotas"]["question_type"]["branded"] = 3
        errors, _, _ = validate(data)
        self.assertTrue(any("expected exactly 1" in error and "got 2" in error for error in errors), errors)

        data = json.loads((FIXTURES / "valid-bank.json").read_text(encoding="utf-8"))
        data["config"]["brand_object_type"] = "product"
        product_prompt = (
            "Evaluate the AI search visibility product Peec AI on AI search visibility platform selection"
        )
        data["questions"][3]["user_question"] = product_prompt
        data["questions"][3]["monitoring_prompt"] = product_prompt
        errors, _, _ = validate(data)
        self.assertEqual([], errors)

    def test_brand_sentiment_coverage_scales_to_multiple_topics(self) -> None:
        data = json.loads((FIXTURES / "valid-bank.json").read_text(encoding="utf-8"))
        data["config"]["topics"].append({
            "topic_id": "topic-2",
            "topic": "AI search visibility reporting for agencies",
        })
        data["config"]["expected_total"] = 5
        data["config"]["quotas"]["question_type"]["branded"] = 3
        second = make_question(
            data["questions"][3],
            "Q5",
            "branded",
            "decision",
            "Evaluate the AI search visibility company Peec AI on AI search visibility reporting for agencies",
            "seo_agency",
        )
        second["topic_id"] = "topic-2"
        data["questions"].append(second)
        errors, _, summary = validate(data)
        self.assertEqual([], errors)
        self.assertEqual({"topic 1": 1, "topic 2": 1}, summary["brand_sentiment_by_topic"])

        data["questions"].pop()
        data["config"]["expected_total"] = 4
        data["config"]["quotas"]["question_type"]["branded"] = 2
        errors, _, _ = validate(data)
        self.assertTrue(any("brand_sentiment.topic 2" in error for error in errors), errors)

    def test_v3_retires_awareness_and_requires_unique_intent_key(self) -> None:
        data = json.loads((FIXTURES / "bpi-commercial-bank.json").read_text(encoding="utf-8"))
        data["config"]["quotas"]["funnel_intent"] = {
            "awareness": 2,
            "comparison": 1,
            "decision": 1,
        }
        data["questions"][0]["funnel_intent"] = "awareness"
        data["questions"][1]["funnel_intent"] = "awareness"
        data["questions"][1]["intent_key"] = data["questions"][0]["intent_key"]
        errors, _, _ = validate(data)
        joined = "\n".join(errors)
        self.assertIn("funnel_intent.awareness is retired", joined)
        self.assertIn("awareness is retired; use recommendation", joined)
        self.assertIn("DUPLICATE intent conditions", joined)

    def test_v2_awareness_bank_remains_readable_with_migration_warning(self) -> None:
        data = json.loads((FIXTURES / "valid-bank.json").read_text(encoding="utf-8"))
        data["schema_version"] = "overseas-geo-question-bank/v2"
        del data["config"]["topics"]
        del data["config"]["category_expression_set"]
        data["config"].pop("category_label", None)
        data["config"].pop("brand_object_type", None)
        data["config"]["quotas"]["funnel_intent"] = {
            "awareness": 1,
            "comparison": 2,
            "decision": 1,
        }
        data["config"]["quotas"]["cross"] = {
            "generic": {"awareness": 1, "comparison": 1},
            "branded": {"comparison": 1, "decision": 1},
        }
        for row in data["questions"]:
            row.pop("topic_id", None)
            row.pop("intent_key", None)
            if row["funnel_intent"] == "recommendation":
                row["funnel_intent"] = "awareness"
            row["geo_intent"] = {
                "awareness": "informational",
                "comparison": "comparison",
                "decision": "brand_validation",
            }[row["funnel_intent"]]
        data["questions"][3]["user_question"] = (
            "Is Peec AI the right AI search visibility platform for a small marketing team?"
        )
        data["questions"][3]["monitoring_prompt"] = data["questions"][3]["user_question"]
        errors, warnings, _ = validate(data)
        self.assertEqual([], errors)
        self.assertTrue(any("LEGACY schema_version v2" in warning for warning in warnings), warnings)

    def test_frozen_competitor_selection_contract_is_enforced(self) -> None:
        data = json.loads((FIXTURES / "valid-bank.json").read_text(encoding="utf-8"))
        data["config"]["competitor_selection"]["status"] = "draft"
        data["config"]["competitor_selection"]["formal_competitors"][1]["comparison_policy"]["mode"] = "standard_evidence_based"
        data["questions"][0]["user_question"] = "Which Otterly features support AI search visibility?"
        data["questions"][0]["monitoring_prompt"] = "Which Otterly features support AI search visibility?"
        errors, _, _ = validate(data)
        joined = "\n".join(errors)
        self.assertIn("competitor_selection.status must equal frozen", joined)
        self.assertIn(
            "comparison_policy.mode must equal neutral_shared_dimensions_only for comparability_tier=adjacent",
            joined,
        )
        self.assertIn("brand/product/alias/competitor terms ['Otterly']", joined)

    def test_missing_translation_field_is_rejected(self) -> None:
        errors, _, summary = validate_fixture("missing-translation-bank.json")
        self.assertTrue(any("missing fields ['zh_translation']" in error for error in errors), errors)
        self.assertFalse(any(error.startswith("QUOTA") for error in errors), errors)
        self.assertEqual(1, summary["total"])

    def test_v3_requires_explicit_professional_term_assessment(self) -> None:
        data = json.loads((FIXTURES / "valid-bank.json").read_text(encoding="utf-8"))
        del data["config"]["professional_term_assessment"]
        del data["config"]["required_term_coverage"]
        errors, _, _ = validate(data)
        joined = "\n".join(errors)
        self.assertIn("required_term_coverage must be present in v3", joined)
        self.assertIn("professional_term_assessment must be an object in v3", joined)

        data = json.loads((FIXTURES / "valid-bank.json").read_text(encoding="utf-8"))
        data["config"]["professional_term_assessment"] = {"status": "completed", "decisions": []}
        data["config"]["required_term_coverage"] = {}
        errors, _, _ = validate(data)
        self.assertTrue(
            any("no_required_terms_reason" in error for error in errors),
            errors,
        )

    def test_empty_translation_names_actions_and_promotional_ratio_are_rejected(self) -> None:
        errors, warnings, summary = validate_fixture("deterministic-gates-bank.json")
        joined = "\n".join(errors)
        self.assertIn("zh_translation must be a non-empty string", joined)
        self.assertIn("brand/product/alias/competitor terms ['VisionPulse']", joined)
        self.assertIn("brand/product/alias/competitor terms ['VP Monitor']", joined)
        self.assertEqual(3, joined.count("bare real-world action command"))
        self.assertTrue(any("commercial_openers" in warning for warning in warnings), warnings)
        self.assertEqual(0.4, summary["quality_patterns"]["promotional_driver_ratio"])
        self.assertTrue(any("cluster_singleton_ratio" in warning for warning in warnings), warnings)

    def test_high_precision_action_and_promotional_patterns_avoid_normal_requests(self) -> None:
        self.assertIsNone(BARE_ACTION.search("Give me a comparison of two AI visibility tools."))
        self.assertIsNotNone(BARE_ACTION.search("Give an AI visibility subscription to a colleague."))
        self.assertIsNone(PROMOTIONAL_DRIVER.search("Which metrics matter most to marketing teams?"))
        self.assertIsNone(PROMOTIONAL_DRIVER.search("Who should review AI-generated claims?"))
        self.assertIsNotNone(PROMOTIONAL_DRIVER.search("What do customer reviews say about this tool?"))

    def test_translation_requires_chinese_and_camel_case_aliases_are_blocked(self) -> None:
        data = json.loads((FIXTURES / "valid-bank.json").read_text(encoding="utf-8"))
        data["questions"][0]["zh_translation"] = "English only translation"
        data["config"]["product_name"] = "CreativeHit"
        data["questions"][0]["user_question"] = "How does Creative Hit track brand mentions in AI-generated answers?"
        data["questions"][0]["monitoring_prompt"] = data["questions"][0]["user_question"]
        errors, _, _ = validate(data)
        joined = "\n".join(errors)
        self.assertIn("zh_translation must contain Chinese characters", joined)
        self.assertIn("brand/product/alias/competitor terms ['CreativeHit']", joined)

    def test_style_concentration_is_warning_not_error(self) -> None:
        errors, warnings, summary = validate_fixture("style-warning-bank.json")
        self.assertEqual([], errors)
        self.assertTrue(any("cluster_singleton_ratio" in warning for warning in warnings), warnings)
        self.assertTrue(any("common_question_openers" in warning for warning in warnings), warnings)
        self.assertEqual(1.0, summary["quality_patterns"]["singleton_cluster_ratio"])
        self.assertEqual(1.0, summary["quality_patterns"]["singleton_scenario_ratio"])
        self.assertEqual(0.9, summary["quality_patterns"]["how_what_which_ratio"])

    def test_branded_comparison_requires_three_solo_competitors_plus_two_other_patterns(self) -> None:
        data = json.loads((FIXTURES / "valid-bank.json").read_text(encoding="utf-8"))
        empty_term_config(data)
        data["config"].update({
            "expected_total": 8,
            "quotas": {
                "question_type": {"generic": 2, "branded": 6},
            },
            "min_distinct_counts": {},
        })
        base = data["questions"][2]
        data["questions"] = [
            make_question(base, "BC1", "branded", "comparison", "How does Peec AI compare with Profound for AI answer monitoring?", "agency"),
            make_question(base, "BC2", "branded", "comparison", "How does Peec AI compare with Otterly AI for AI answer monitoring?", "agency"),
            make_question(base, "BC3", "branded", "comparison", "How do Peec AI and Fallback Example fit into different AI visibility workflows?", "enterprise"),
            make_question(base, "BC4", "branded", "comparison", "What reporting factors matter when comparing Peec AI with other AI visibility tools?", "enterprise"),
            make_question(base, "BC5", "branded", "comparison", "How do Peec AI, Profound, and Otterly AI compare on AI answer monitoring?", "consultant"),
            make_question(base, "BC6", "generic", "recommendation", "Which AI visibility platforms suit a small agency?", "agency"),
            make_question(base, "BC7", "generic", "decision", "Which AI visibility platform is the right fit for an enterprise team?", "enterprise"),
            make_question(base, "BS1", "branded", "decision", "Evaluate the AI search visibility company Peec AI on AI search visibility platform selection", "enterprise"),
        ]
        errors, _, summary = validate(data)
        self.assertEqual([], errors)
        self.assertEqual(1, summary["formal_competitor_question_coverage"]["Profound"]["solo_branded_comparison"])
        self.assertEqual(2, summary["branded_comparison_non_solo_count"])

        data["questions"][2] = make_question(
            base,
            "BC3",
            "branded",
            "comparison",
            "How does Peec AI compare with Profound on reporting workflows?",
            "enterprise",
        )
        data["questions"][3] = make_question(
            base,
            "BC4",
            "branded",
            "comparison",
            "How does Peec AI compare with Profound for enterprise reporting?",
            "enterprise",
        )
        data["questions"][4] = make_question(
            base,
            "BC5",
            "branded",
            "comparison",
            "How does Peec AI compare with Otterly AI for agency reporting?",
            "consultant",
        )
        errors, _, _ = validate(data)
        joined = "\n".join(errors)
        self.assertIn("formal_competitor.Fallback Example.solo_branded_comparison", joined)
        self.assertIn("branded_comparison_3_plus_2", joined)

    def test_target_audiences_are_reported_without_fixed_quotas(self) -> None:
        data = json.loads((FIXTURES / "valid-bank.json").read_text(encoding="utf-8"))
        empty_term_config(data)
        data["config"].update({
            "expected_total": 6,
            "quotas": {
                "question_type": {"generic": 5, "branded": 1},
            },
            "min_distinct_counts": {},
            "target_audiences": ["seo_agency", "enterprise_marketing"],
        })
        base = data["questions"][0]
        data["questions"] = [
            make_question(base, "TA1", "generic", "recommendation", "Which AI visibility platforms suit SEO agencies?", "seo_agency"),
            make_question(base, "TA2", "generic", "comparison", "Which AI visibility platforms suit SEO agencies with small teams?", "seo_agency"),
            make_question(base, "TA3", "generic", "recommendation", "Which AI visibility platforms suit enterprise marketing teams?", "enterprise_marketing"),
            make_question(base, "TA4", "generic", "decision", "Which AI visibility platform fits enterprise marketing workflows?", "enterprise_marketing"),
            make_question(base, "TA5", "generic", "comparison", "How should consultants compare AI visibility measurement methods?", "consultant"),
            make_question(base, "TA6", "branded", "decision", "Evaluate the AI search visibility company Peec AI on AI search visibility platform selection", "enterprise_marketing"),
        ]
        errors, _, summary = validate(data)
        self.assertEqual([], errors)
        self.assertEqual(0.4, summary["target_audience_coverage"]["seo_agency"]["generic_share"])
        self.assertEqual(1, summary["target_audience_coverage"]["enterprise_marketing"]["generic_decision"])

        data["questions"][2]["audience_role"] = "seo_agency"
        data["questions"][3]["audience_role"] = "consultant"
        errors, _, summary = validate(data)
        self.assertEqual([], errors)
        self.assertEqual(0, summary["target_audience_coverage"]["enterprise_marketing"].get("generic_total", 0))
        self.assertEqual(0.6, summary["target_audience_coverage"]["seo_agency"]["generic_share"])

    def test_price_is_a_condition_not_a_geo_intent(self) -> None:
        data = json.loads((FIXTURES / "valid-bank.json").read_text(encoding="utf-8"))
        errors, _, _ = validate(data)
        self.assertEqual([], errors)

        data["questions"][0]["geo_intent"] = "pricing"
        data["questions"][1]["intent_angle"] = "risk"
        errors, _, _ = validate(data)
        joined = "\n".join(errors)
        self.assertIn("retired v3 intent fields ['geo_intent']", joined)
        self.assertIn("retired v3 intent fields ['intent_angle']", joined)

    def test_natural_questions_are_not_rejected_by_a_fixed_word_limit(self) -> None:
        data = json.loads((FIXTURES / "valid-bank.json").read_text(encoding="utf-8"))
        long_question = (
            "Which AI search visibility platforms should a small SEO agency consider when it needs "
            "multi-client reporting, prompt tracking, citation analysis, weekly exports, role-based access, "
            "and reliable support across several customer accounts?"
        )
        data["questions"][0]["user_question"] = long_question
        data["questions"][0]["monitoring_prompt"] = long_question
        errors, _, _ = validate(data)
        self.assertEqual([], errors)

    def test_lit_by_larry_regressions_define_brand_answer_endpoints(self) -> None:
        regressions = json.loads(
            (Path(__file__).resolve().parent / "lit_by_larry_regressions.json").read_text(encoding="utf-8")
        )
        self.assertEqual("Lit by Larry", regressions["brand"])
        self.assertFalse(regressions["length_policy"]["hard_max_words"])
        self.assertEqual(
            "The prompt wording itself must require brand candidates, a comparison between brand candidates, or a final brand choice.",
            regressions["generic_answer_scope"]["question_requirement"],
        )
        self.assertEqual(
            {
                "monitored brand if surfaced organically",
                "configured competitors",
                "unconfigured peer brands",
            },
            set(regressions["generic_answer_scope"]["allowed_answer_entities"]),
        )
        self.assertEqual(
            {
                "generic_without_brand_answer_endpoint",
                "incidental_brand_mentions_only",
                "invented_low_frequency_condition",
                "per_question_full_scope_forcing",
            },
            {case["failure_family"] for case in regressions["bad_cases"]},
        )
        self.assertTrue(all(case["expected_repair"] for case in regressions["bad_cases"]))


if __name__ == "__main__":
    unittest.main()
