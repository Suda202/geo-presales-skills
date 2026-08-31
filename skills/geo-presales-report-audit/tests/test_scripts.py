#!/usr/bin/env python3
"""Regression tests for deterministic audit helpers."""

from __future__ import annotations

import json
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DRAFT_SCRIPT = ROOT / "scripts" / "prepare_badcase_draft.py"
SCREENSHOT_SCRIPT = ROOT / "scripts" / "annotate_evidence_screenshot.py"
STRUCTURED_SCRIPT = ROOT / "scripts" / "structured_result_audit.py"
STRUCTURED_EVAL_SCRIPT = ROOT / "scripts" / "run_structured_result_evals.py"

SPEC = importlib.util.spec_from_file_location("structured_result_audit", STRUCTURED_SCRIPT)
assert SPEC and SPEC.loader
STRUCTURED = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STRUCTURED)


class DraftScriptTests(unittest.TestCase):
    def test_draft_requires_completion_before_strict_validation(self) -> None:
        with tempfile.TemporaryDirectory() as raw_dir:
            draft = Path(raw_dir) / "draft.json"
            subprocess.run(
                [
                    sys.executable,
                    str(DRAFT_SCRIPT),
                    "new",
                    "--task",
                    "123",
                    "--record",
                    "4567",
                    "--summary",
                    "本来要评估目标品类供应商，题目却改问另一类服务商",
                    "--output",
                    str(draft),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            allowed = subprocess.run(
                [sys.executable, str(DRAFT_SCRIPT), "validate", "--input", str(draft), "--allow-draft"],
                capture_output=True,
                text=True,
            )
            strict = subprocess.run(
                [sys.executable, str(DRAFT_SCRIPT), "validate", "--input", str(draft)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(allowed.returncode, 0)
            self.assertNotEqual(strict.returncode, 0)
            self.assertIn("字段未填写：错误类型", strict.stdout)
            self.assertIn("字段未填写：问题截图", strict.stdout)

    def test_complete_draft_passes(self) -> None:
        payload = {
            "Bad Case": "Task 123 #4567：本来要评估目标品类供应商，题目却改问另一类服务商",
            "错误类型": "问题生成错误",
            "模块": "Prompt生成",
            "问题与影响": "问题：购买对象已经改变。\n影响：客户会看到错误的供应商推荐。",
            "复现证据": "Task 123 #4567\n原题：比较另一类服务商。\n实际：回答推荐另一类服务商。\n预期：比较目标品类供应商。",
            "建议": "在问题生成后校验购买对象，并用当前记录回归。",
            "状态": "待修复",
            "优先级": "P1",
            "问题截图": ["/tmp/annotated.png"],
            "来源报告": "https://example.com/report/123",
            "报告级问题": False,
        }
        with tempfile.TemporaryDirectory() as raw_dir:
            draft = Path(raw_dir) / "draft.json"
            draft.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(DRAFT_SCRIPT), "validate", "--input", str(draft)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class ScreenshotScriptTests(unittest.TestCase):
    def test_annotation_adds_banner_and_keeps_source_area(self) -> None:
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is not available in this Python runtime")

        with tempfile.TemporaryDirectory() as raw_dir:
            raw = Path(raw_dir) / "raw.png"
            annotated = Path(raw_dir) / "annotated.png"
            Image.new("RGB", (640, 360), "white").save(raw)
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCREENSHOT_SCRIPT),
                    "--input",
                    str(raw),
                    "--output",
                    str(annotated),
                    "--title",
                    "问题：关键证据需要标记",
                    "--subtitle",
                    "Task 123 · #4567",
                    "--box",
                    "100,100,400,220",
                    "--arrow",
                    "80,40,140,100",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            with Image.open(annotated) as output:
                self.assertEqual(output.width, 640)
                self.assertGreater(output.height, 360)


class StructuredResultTests(unittest.TestCase):
    def base_payload(self) -> dict:
        return {
            "version": "test-v1",
            "task_id": 102,
            "rows": [
                {
                    "wordid": 1,
                    "platform": "test",
                    "answer_text": "<p>Chatham 先出现，然后是 Lit by Larry。</p>",
                    "sentiment": "neutral",
                    "brand_rankings": [
                        {"brand_name": "Lit by Larry", "rank_pos": 1}
                    ],
                },
                {
                    "wordid": 2,
                    "platform": "test",
                    "answer_text": "<p>Lit by Larry 值得考虑。</p>",
                    "sentiment": "positive",
                    "brand_rankings": [
                        {"brand_name": "Lit by Larry", "rank_pos": 1}
                    ],
                },
            ],
        }

    def test_citation_cleaning_preserves_product_card_title(self) -> None:
        cleaned, removed = STRUCTURED.remove_citations(
            '<div data-testid="product-card"><a href="/p">MiaDonna Ring</a></div>'
            '<span data-testid="webpage-citation-pill"><a href="https://source">Source+1</a></span>'
        )
        self.assertEqual(cleaned, "MiaDonna Ring")
        self.assertEqual(removed, ["Source+1"])

    def test_gemini_source_chip_is_removed_before_brand_ranking(self) -> None:
        cleaned, removed = STRUCTURED.remove_citations(
            '<div class="source-inline-chip-container"><button><span class="source-title">PETKIT</span></button></div>'
            '<p>PETLIBRO appears before PETKIT in the answer body.</p>'
        )
        self.assertEqual(cleaned, "PETLIBRO appears before PETKIT in the answer body.")
        self.assertEqual(removed, ["PETKIT"])

    def test_rank_uses_first_normalized_body_occurrence(self) -> None:
        catalog = [
            {
                "canonical_name": "Lit by Larry",
                "aliases": ["Lit by Aria", "Lit byarry"],
                "eligible": True,
            },
            {"canonical_name": "Chatham", "aliases": [], "eligible": True},
        ]
        self.assertEqual(
            STRUCTURED.rank_from_catalog(
                "Chatham appears before Lit by Aria and Lit byarry.", catalog
            ),
            [
                {"brand_name": "Chatham", "rank_pos": 1},
                {"brand_name": "Lit by Larry", "rank_pos": 2},
            ],
        )

    def test_visibility_only_cannot_generate_sentiment(self) -> None:
        with self.assertRaisesRegex(STRUCTURED.AuditValidationError, "不含 sentiment"):
            STRUCTURED.sentiment_from_review("visibility", "negative_dominant")

    def test_visibility_and_sentiment_uses_reviewed_polarity(self) -> None:
        self.assertEqual(
            STRUCTURED.sentiment_from_review(
                ["visibility", "sentiment"], "positive_dominant"
            ),
            "positive",
        )

    def test_question_types_and_diagnostic_tags_combine_scopes(self) -> None:
        self.assertEqual(
            STRUCTURED.metric_scopes_for_dimensions("visibility", "discovery"),
            ("visibility", "citation"),
        )
        self.assertEqual(
            STRUCTURED.metric_scopes_for_dimensions("visibility", "competitor"),
            ("visibility", "citation", "comparison"),
        )
        self.assertEqual(
            STRUCTURED.metric_scopes_for_dimensions("sentiment", "sentiment"),
            ("sentiment",),
        )
        self.assertEqual(
            STRUCTURED.metric_scopes_for_dimensions("visibility", "market_perception"),
            ("visibility", "citation", "market_perception"),
        )

    def test_missing_required_scopes_are_rejected(self) -> None:
        with self.assertRaisesRegex(STRUCTURED.AuditValidationError, "诊断范围"):
            STRUCTURED.validate_metric_scopes(
                "visibility", "competitor", ["sentiment"]
            )

    def test_unknown_diagnostic_tag_is_preserved_and_custom_scope_allowed(self) -> None:
        row = {"diagnostic_intents": ["competitor", "custom-risk"]}
        self.assertEqual(
            STRUCTURED.diagnostic_intents_from_row(row),
            ("competitor", "custom-risk"),
        )
        actual = STRUCTURED.validate_metric_scopes(
            ["visibility", "sentiment"],
            ["competitor", "custom-risk"],
            ["visibility", "citation", "sentiment", "comparison", "custom-risk-score"],
        )
        self.assertIn("custom-risk-score", actual)

    def test_brand_polarities_map_to_three_product_labels(self) -> None:
        expected = {
            "positive_dominant": "positive",
            "balanced_or_insufficient": "neutral",
            "negative_dominant": "negative",
        }
        for polarity, label in expected.items():
            with self.subTest(polarity=polarity):
                self.assertEqual(
                    STRUCTURED.sentiment_from_review("sentiment", polarity), label
                )

    def test_apply_patch_changes_only_target_fields(self) -> None:
        payload = self.base_payload()
        patch = {
            "rows": [
                {
                    "wordid": 1,
                    "brand_rankings": [
                        {"brand_name": "Chatham", "rank_pos": 1},
                        {"brand_name": "Lit by Larry", "rank_pos": 2},
                    ],
                    "sentiment": "negative",
                }
            ]
        }
        result, changes = STRUCTURED.apply_reviewed_patch(payload, patch)
        self.assertEqual({item["field"] for item in changes}, {"brand_rankings", "sentiment"})
        self.assertEqual(result["version"], payload["version"])
        self.assertEqual(result["task_id"], payload["task_id"])
        self.assertEqual(result["rows"][0]["answer_text"], payload["rows"][0]["answer_text"])
        self.assertEqual(result["rows"][1], payload["rows"][1])

    def test_same_wordid_on_two_platforms_is_valid_and_patch_requires_platform(self) -> None:
        payload = self.base_payload()
        duplicate = json.loads(json.dumps(payload["rows"][0]))
        duplicate["platform"] = "second-platform"
        payload["rows"].append(duplicate)
        STRUCTURED.validate_payload(payload)
        with self.assertRaisesRegex(STRUCTURED.AuditValidationError, "必须显式提供 platform"):
            STRUCTURED.apply_reviewed_patch(
                payload, {"rows": [{"wordid": 1, "sentiment": "positive"}]}
            )
        result, changes = STRUCTURED.apply_reviewed_patch(
            payload,
            {
                "rows": [
                    {
                        "platform": "second-platform",
                        "wordid": 1,
                        "sentiment": "positive",
                    }
                ]
            },
        )
        changed = next(
            row
            for row in result["rows"]
            if row["platform"] == "second-platform" and row["wordid"] == 1
        )
        untouched = next(
            row
            for row in result["rows"]
            if row["platform"] == "test" and row["wordid"] == 1
        )
        self.assertEqual(changed["sentiment"], "positive")
        self.assertEqual(untouched["sentiment"], "neutral")
        self.assertEqual(changes[0]["platform"], "second-platform")

    def test_rank_discontinuity_fails_validation(self) -> None:
        payload = self.base_payload()
        payload["rows"][0]["brand_rankings"][0]["rank_pos"] = 2
        with self.assertRaisesRegex(STRUCTURED.AuditValidationError, "不从 1 连续"):
            STRUCTURED.validate_payload(payload)

    def test_historical_question_label_does_not_override_reviewed_sentiment(self) -> None:
        payload = self.base_payload()
        payload["rows"][0]["sentiment"] = "positive"
        STRUCTURED.validate_payload(payload, sentiment_wordids={2})

    def test_overlap_non_neutral_passes(self) -> None:
        payload = self.base_payload()
        payload["rows"][0]["sentiment"] = "positive"
        payload["rows"][0]["question_types"] = ["visibility", "sentiment"]
        STRUCTURED.validate_payload(payload, sentiment_wordids={1, 2})

    def test_null_answer_is_preserved_and_marked_unavailable_for_semantic_review(self) -> None:
        payload = self.base_payload()
        payload["rows"][0]["answer_text"] = None
        bundle = STRUCTURED.build_review_bundle(payload, {2}, "Lit by Larry")
        self.assertFalse(bundle["rows"][0]["semantic_review_available"])
        self.assertEqual(bundle["rows"][0]["cleaned_text"], "")

    def test_full_structured_fixture_runner_passes(self) -> None:
        result = subprocess.run(
            [sys.executable, str(STRUCTURED_EVAL_SCRIPT)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("structured_result_cases=17", result.stdout)
        self.assertIn("failed=0", result.stdout)

    def test_prepare_records_explicit_target_brand(self) -> None:
        bundle = STRUCTURED.build_review_bundle(
            self.base_payload(), {2}, "Lit by Larry"
        )
        self.assertEqual(bundle["target_brand"], "Lit by Larry")


if __name__ == "__main__":
    unittest.main()
