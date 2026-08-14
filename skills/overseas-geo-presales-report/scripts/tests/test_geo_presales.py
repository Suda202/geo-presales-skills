from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(SCRIPT_DIR))

from geo_presales_core.config import normalize_config
from geo_presales_core.crawler import answer_validity, import_crawl
from geo_presales_core.questions import normalize_question_bank
from geo_presales_core.util import ContractError, domain_matches, find_alias_spans, normalize_url, read_json, write_json


CLI = SCRIPT_DIR / "geo_presales.py"


class ContractTests(unittest.TestCase):
    def small_config(self):
        return normalize_config({
            "run_id": "R-test",
            "topic": "AI visibility software",
            "brand": {"name": "Acme AI", "aliases": ["Acme"], "domain": "acme.com"},
            "competitors": [{"name": "Beta", "aliases": ["Beta AI"], "domain": "beta.com"}],
            "quotas": {
                "total": 4,
                "question_type": {"generic": 2, "branded": 2},
                "funnel_intent": {"recommendation": 1, "comparison": 2, "decision": 1}
            }
        })

    def small_questions(self):
        return {
            "questions": [
                {"question_id": "q01", "question_type": "generic", "funnel_intent": "recommendation", "monitoring_prompt": "Which AI visibility tools track brand mentions?"},
                {"question_id": "q02", "question_type": "generic", "funnel_intent": "comparison", "monitoring_prompt": "Which AI visibility tools are best for small teams?"},
                {"question_id": "q03", "question_type": "branded", "funnel_intent": "comparison", "monitoring_prompt": "How does Acme AI compare with other visibility tools?"},
                {"question_id": "q04", "question_type": "branded", "funnel_intent": "decision", "monitoring_prompt": "Is Acme AI worth adopting for a small team?"},
            ]
        }

    def test_alias_boundary(self):
        self.assertEqual(find_alias_spans("A pineapple is not Apple.", ["Apple"])[0]["matched_text"], "Apple")
        self.assertEqual(len(find_alias_spans("pineapple", ["Apple"])), 0)

    def test_alias_conflict_blocks_config(self):
        with self.assertRaises(ContractError):
            normalize_config({
                "topic": "Test",
                "brand": {"name": "Acme", "domain": "acme.com", "aliases": ["Shared"]},
                "competitors": [{"name": "Beta", "domain": "beta.com", "aliases": ["Shared"]}],
            })

    def test_url_and_official_domain_boundaries(self):
        normalized = normalize_url("https://WWW.Acme.com:443/features/?utm_source=x&b=2&a=1#part")
        self.assertEqual(normalized["canonical_url"], "https://acme.com/features?a=1&b=2")
        self.assertEqual(normalized["removed_query_params"], ["utm_source"])
        self.assertTrue(domain_matches("docs.acme.com", "acme.com"))
        self.assertFalse(domain_matches("acme.com.evil.com", "acme.com"))

    def test_answer_validity_does_not_turn_failures_into_zero(self):
        self.assertEqual(answer_validity(""), (False, "EMPTY_ANSWER"))
        self.assertEqual(answer_validity("Something went wrong. Try again later."), (False, "ERROR_PAGE"))
        self.assertEqual(answer_validity("Acme is a valid option."), (True, None))

    def test_question_contract(self):
        config = self.small_config()
        self.assertNotIn("funnel_intent", config["quotas"])
        bank = normalize_question_bank(self.small_questions(), config)
        self.assertEqual(len(bank["questions"]), 4)
        different_distribution = self.small_questions()
        different_distribution["questions"][2]["funnel_intent"] = "recommendation"
        bank = normalize_question_bank(different_distribution, config)
        self.assertEqual(
            {"recommendation", "comparison", "decision"},
            {item["funnel_intent"] for item in bank["questions"]},
        )
        bad = self.small_questions()
        bad["questions"][0]["monitoring_prompt"] = "How does Acme work?"
        with self.assertRaises(ContractError):
            normalize_question_bank(bad, self.small_config())

    def test_legacy_awareness_is_migrated_to_recommendation(self):
        legacy = self.small_questions()
        legacy["questions"][0]["funnel_intent"] = "awareness"
        bank = normalize_question_bank(legacy, self.small_config())
        self.assertEqual("recommendation", bank["questions"][0]["funnel_intent"])
        self.assertTrue(
            any(item["code"] == "LEGACY_AWARENESS_MIGRATED" for item in bank["warnings"]),
            bank["warnings"],
        )

    def test_v3_geo_intent_is_ignored_by_report_consumer(self):
        v3 = self.small_questions()
        v3["questions"][0]["geo_intent"] = "pricing"
        bank = normalize_question_bank(v3, self.small_config())
        self.assertNotIn("geo_intent", bank["questions"][0])
        self.assertEqual("recommendation", bank["questions"][0]["funnel_intent"])

    def test_intent_miner_fixture_imports_without_translation_dependency(self):
        fixture = REPOSITORY_ROOT / "skills/yao-overseas-geo-intent-miner/evals/fixtures/valid-bank.json"
        raw = read_json(fixture)
        config = normalize_config({
            "run_id": "R-intent-fixture",
            "topic": "AI search visibility platforms",
            "brand": {"name": "Peec AI", "domain": "peec.ai"},
            "competitors": [{"name": "Profound", "domain": "tryprofound.com"}],
            "quotas": raw["config"]["quotas"],
        })
        bank = normalize_question_bank(raw, config)
        self.assertEqual(len(bank["questions"]), 4)
        self.assertEqual(len(bank["warnings"]), 4)
        self.assertEqual("decision", bank["questions"][-1]["funnel_intent"])
        self.assertTrue(bank["questions"][-1]["question_text"].startswith("Evaluate the "))

    def test_crawler_fixture_contract(self):
        fixture = REPOSITORY_ROOT / "skills/overseas-geo-presales-report/fixtures/sample-chatgpt-crawl.json"
        raw = read_json(fixture)
        question_bank = {
            "run_id": "R-crawler",
            "questions": [
                {"question_id": item["id"], "generation_sequence": item["index"], "question_text": item["question"]}
                for item in raw["input"]["questions"]
            ],
        }
        imported = import_crawl(raw, question_bank, fixture)
        self.assertEqual(imported["counts"]["valid_count"], 3)
        self.assertEqual(imported["counts"]["failed_count"], 1)
        self.assertEqual(sum(len(item["citations"]) for item in imported["samples"]), 8)
        failed = next(item for item in imported["samples"] if item["sample_id"] == "q02-r02")
        self.assertFalse(failed["analysis_eligible"])
        self.assertIsNone(failed["answer_text"])

    def test_crawler_plan_preserves_pending_samples(self):
        question_bank = {
            "run_id": "R-pending",
            "questions": [
                {"question_id": "q01", "generation_sequence": 1, "question_text": "What is an AI visibility platform?"},
                {"question_id": "q02", "generation_sequence": 2, "question_text": "Which AI visibility platform is best?"},
            ],
        }
        raw = {
            "run": {"engine": "chatgpt"},
            "plan": [
                {"sample_id": "q01-r01", "question_id": "q01", "question": question_bank["questions"][0]["question_text"], "repeat_index": 1},
                {"sample_id": "q02-r01", "question_id": "q02", "question": question_bank["questions"][1]["question_text"], "repeat_index": 1},
            ],
            "samples": [
                {
                    "sample_id": "q01-r01", "question_id": "q01", "question": question_bank["questions"][0]["question_text"],
                    "repeat_index": 1, "ok": True, "status": "done",
                    "result": {"ok": True, "answer": {"text": "A tool for measuring visibility."}, "references": {"items": []}},
                }
            ],
        }
        imported = import_crawl(raw, question_bank, "fixture.json")
        self.assertEqual(imported["counts"]["pending_count"], 1)
        pending = next(item for item in imported["samples"] if item["sample_id"] == "q02-r01")
        self.assertEqual(pending["error_code"], "PENDING")
        self.assertFalse(pending["analysis_eligible"])


class EndToEndTests(unittest.TestCase):
    def run_cli(self, *args, expected=0):
        completed = subprocess.run(
            [sys.executable, str(CLI), *map(str, args)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode != expected:
            self.fail(f"CLI failed ({completed.returncode}): {completed.stdout}\n{completed.stderr}")
        return json.loads(completed.stdout)

    def task_result(self, task: dict, output: dict, status="completed"):
        return {
            "protocol_version": task["protocol_version"],
            "run_id": task["run_id"],
            "task_id": task["task_id"],
            "kind": task["kind"],
            "task_digest": task["task_digest"],
            "status": status,
            "output": output,
            "issues": [],
        }

    def test_low_confidence_creates_item_only_review(self):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            run_dir = temp / "run"
            config_path = temp / "config.json"
            questions_path = temp / "questions.json"
            crawl_path = temp / "crawl.json"
            write_json(config_path, {
                "run_id": "R-review",
                "topic": "AI visibility software",
                "brand": {"name": "Acme AI", "aliases": ["Acme"], "domain": "acme.com"},
                "competitors": [{"name": "Beta", "domain": "beta.com"}],
                "quotas": {
                    "total": 3,
                    "question_type": {"generic": 2, "branded": 1}
                }
            })
            question = "What should teams know about Acme AI?"
            answer = "Acme is capable, but the available evidence is limited."
            write_json(questions_path, {"questions": [
                {"question_id": "q01", "question_type": "branded", "funnel_intent": "recommendation", "monitoring_prompt": question},
                {"question_id": "q02", "question_type": "generic", "funnel_intent": "comparison", "monitoring_prompt": "Which AI visibility tools are easier for small teams?"},
                {"question_id": "q03", "question_type": "generic", "funnel_intent": "decision", "monitoring_prompt": "Which AI visibility tool should a small team choose?"},
            ]})
            write_json(crawl_path, {
                "run": {"engine": "chatgpt"},
                "samples": [{
                    "sample_id": "q01-r01", "question_id": "q01", "question_index": 1, "repeat_index": 1, "repeat_total": 1,
                    "question": question, "ok": True, "status": "done",
                    "result": {"ok": True, "answer": {"text": answer}, "references": {"items": []}},
                }]
            })
            self.run_cli("create-run", "--config", config_path, "--run-dir", run_dir)
            self.run_cli("import-questions", "--run-dir", run_dir, "--questions", questions_path)
            self.run_cli("import-crawl", "--run-dir", run_dir, "--crawl", crawl_path)
            self.run_cli("prepare", "--run-dir", run_dir)
            manifest = read_json(run_dir / "manifest.json")
            initial_id = next(iter(manifest["tasks"]))
            task = read_json(run_dir / manifest["tasks"][initial_id]["path"])
            result_path = temp / "low.json"
            write_json(result_path, self.task_result(task, {"items": {
                "q01-r01": {"label": "neutral", "score": 0.0, "confidence": 0.55, "evidence": [{"quote": answer}], "flags": ["AMBIGUOUS"]}
            }}))
            submitted = self.run_cli("submit-task", "--run-dir", run_dir, "--task-id", initial_id, "--result", result_path)
            self.assertEqual(submitted["receipt"]["decision"], "accepted_with_review")
            manifest = read_json(run_dir / "manifest.json")
            review_tasks = [
                read_json(run_dir / meta["path"])
                for task_id, meta in manifest["tasks"].items()
                if task_id != initial_id
            ]
            self.assertEqual(len(review_tasks), 1)
            self.assertEqual(review_tasks[0]["mode"], "review")
            self.assertEqual(set(review_tasks[0]["input"]["items"]), {"q01-r01"})

    def test_full_cli_lifecycle(self):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            run_dir = temp / "run"
            config_path = temp / "config.json"
            questions_path = temp / "questions.json"
            crawl_path = temp / "crawl.json"
            write_json(config_path, {
                "run_id": "R-e2e",
                "topic": "AI visibility software",
                "brand": {"name": "Acme AI", "aliases": ["Acme"], "domain": "acme.com"},
                "competitors": [{"name": "Beta", "aliases": ["Beta AI"], "domain": "beta.com"}],
                "quotas": {
                    "total": 4,
                    "question_type": {"generic": 2, "branded": 2},
                    "funnel_intent": {"recommendation": 1, "comparison": 2, "decision": 1}
                }
            })
            write_json(questions_path, {
                "questions": [
                    {"question_id": "q01", "question_type": "generic", "funnel_intent": "recommendation", "monitoring_prompt": "Which AI visibility tools track brand mentions?"},
                    {"question_id": "q02", "question_type": "generic", "funnel_intent": "comparison", "monitoring_prompt": "Which AI visibility tools are best for small teams?"},
                    {"question_id": "q03", "question_type": "branded", "funnel_intent": "comparison", "monitoring_prompt": "How does Acme AI compare with other visibility tools?"},
                    {"question_id": "q04", "question_type": "branded", "funnel_intent": "decision", "monitoring_prompt": "Is Acme AI worth adopting for a small team?"},
                ]
            })
            answers = {
                "q01": "Beta is a commonly cited option for basic monitoring.",
                "q02": "Beta appears first, while Acme offers clearer workflows for small teams.",
                "q03": "Acme is easy to use and has clear onboarding.",
                "q04": "Acme is expensive for a small team and its reporting is limited.",
            }
            refs = {
                "q01": [{"url": "https://beta.com/overview", "title": "Beta"}],
                "q02": [{"url": "https://acme.com/features?utm_source=test", "title": "Acme features"}],
                "q03": [{"url": "https://www.acme.com/features#details", "title": "Acme features"}],
                "q04": [{"url": "https://reddit.com/r/tools/post", "title": "Discussion"}],
            }
            write_json(crawl_path, {
                "schema_version": "yao-chatgpt-crawler/v1",
                "run": {"engine": "chatgpt"},
                "samples": [
                    {
                        "sample_id": f"{qid}-r01", "question_id": qid, "question_index": index,
                        "repeat_index": 1, "repeat_total": 1,
                        "question": read_json(questions_path)["questions"][index-1]["monitoring_prompt"],
                        "ok": True, "status": "done", "error": "",
                        "result": {"ok": True, "answer": {"text": answers[qid]}, "references": {"count": 1, "items": refs[qid]}},
                    }
                    for index, qid in enumerate(("q01", "q02", "q03", "q04"), 1)
                ]
            })

            self.run_cli("create-run", "--config", config_path, "--run-dir", run_dir)
            self.run_cli("import-questions", "--run-dir", run_dir, "--questions", questions_path)
            self.run_cli("import-crawl", "--run-dir", run_dir, "--crawl", crawl_path)
            self.run_cli("prepare", "--run-dir", run_dir)

            manifest = read_json(run_dir / "manifest.json")
            sentiment_id = next(task_id for task_id, meta in manifest["tasks"].items() if meta["kind"] == "sentiment_batch")
            sentiment_task = read_json(run_dir / manifest["tasks"][sentiment_id]["path"])
            sentiment_output = {"items": {}}
            labels = {"q02-r01": ("positive", 0.5), "q03-r01": ("positive", 0.8), "q04-r01": ("negative", -0.7)}
            for answer_id, item in sentiment_task["input"]["items"].items():
                label, score = labels[answer_id]
                sentiment_output["items"][answer_id] = {
                    "label": label,
                    "score": score,
                    "confidence": 0.9,
                    "evidence": [{"quote": answers[answer_id.split("-r")[0]]}],
                    "flags": [],
                }
            result_path = temp / "sentiment.json"
            write_json(result_path, self.task_result(sentiment_task, sentiment_output))
            self.run_cli("submit-task", "--run-dir", run_dir, "--task-id", sentiment_id, "--result", result_path)

            computed = self.run_cli("compute", "--run-dir", run_dir)
            self.assertEqual(computed["coverage"]["valid_answers"], 4)
            metrics = read_json(run_dir / "artifacts/metrics.json")
            self.assertEqual(metrics["opportunity"]["counts"], {"priority_improve": 1, "continue_optimize": 0, "stable": 1})
            self.assertEqual(metrics["sentiment"]["counts"], {"positive": 2, "neutral": 0, "negative": 1})

            while True:
                self.run_cli("prepare-report-tasks", "--run-dir", run_dir)
                manifest = read_json(run_dir / "manifest.json")
                pending = [
                    (task_id, meta, read_json(run_dir / meta["path"]))
                    for task_id, meta in manifest["tasks"].items()
                    if meta["status"] == "pending" and all(manifest["tasks"][dep]["status"] in {"accepted", "degraded"} for dep in meta.get("depends_on") or [])
                ]
                if not pending:
                    break
                for task_id, meta, task in pending:
                    if task["kind"] == "brand_expression_themes":
                        output = {
                            "positive": [{
                                "label": "Easy onboarding",
                                "summary": "Verified answers describe clear setup and workflows.",
                                "evidence_ids": ["E-q03-r01-01"],
                                "confidence": 0.9,
                            }],
                            "risk": [{
                                "label": "Cost and reporting limits",
                                "summary": "One verified answer raises cost and reporting concerns.",
                                "evidence_ids": ["E-q04-r01-01"],
                                "confidence": 0.9,
                            }],
                        }
                    elif task["kind"] == "report_module":
                        output = {
                            "module_id": task["input"]["module_id"],
                            "title": f"Module {task['input']['module_id']}",
                            "points": [{"text_template": "This module summarizes verified batch evidence.", "refs": []}],
                            "conclusion": None,
                        }
                    elif task["kind"] == "next_actions":
                        output = {
                            "summary": {"text_template": "Prioritize the verified gaps in this batch.", "refs": []},
                            "actions": [
                                {
                                    "direction_id": direction["direction_id"],
                                    "source_module": direction["source_module"],
                                    "title": "Act on verified evidence",
                                    "evidence_template": "The deterministic metrics support this direction.",
                                    "expected_impact_template": "Make the relevant evidence easier to understand and cite.",
                                    "action": "Review the verified gaps and improve the corresponding factual explanation and proof points.",
                                    "refs": [],
                                }
                                for direction in task["input"]["directions"]
                            ],
                        }
                    else:
                        self.fail(f"Unexpected task kind {task['kind']}")
                    task_result_path = temp / f"{task_id}.json"
                    write_json(task_result_path, self.task_result(task, output))
                    self.run_cli("submit-task", "--run-dir", run_dir, "--task-id", task_id, "--result", task_result_path)

            finalized = self.run_cli("finalize", "--run-dir", run_dir)
            self.assertTrue(finalized["publishable"])
            report = read_json(run_dir / "artifacts/report-data.json")
            self.assertEqual(report["run_id"], "R-e2e")
            self.assertEqual(len(report["modules"]), 5)
            self.assertEqual(len(report["next_actions"]["actions"]), 3)


if __name__ == "__main__":
    unittest.main()
