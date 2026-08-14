from __future__ import annotations

import csv
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "backend_report.py"
SPEC = importlib.util.spec_from_file_location("backend_report", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def payload(*, as_strings=False, action_context=True):
    overview = {
        "category_mention_rate": "35%",
        "share_of_voice": "28%",
        "average_rank": "2.8",
        "competitive_gaps": {
            "mention_rate": {
                "competitor_brand_name": "Leader",
                "comparison_result": "behind",
                "gap_text": "低12个百分点",
            }
        },
    }
    competitor = {
        "mention_ranking": [
            {"brand_name": "Target", "is_self": True, "mention_rate": 0.35},
            {"brand_name": "Leader", "is_self": False, "mention_rate": 0.47},
        ],
        "share_segments": [
            {"brand_name": "Target", "rate_percent": 28},
            {"brand_name": "Leader", "rate_percent": 38},
        ],
        "rank_performance": [
            {"brand_name": "Target", "is_self": True, "average_rank": 2.8},
            {"brand_name": "Leader", "is_self": False, "average_rank": 1.7},
        ],
    }
    citation = {
        "source_type_bars": [
            {"label": "媒体评测", "value": 40},
            {"label": "品牌官网", "value": 12},
        ],
        "brand_official_pages": [
            {"url": "https://target.example/product", "quote_count": 2},
            {"url": "https://target.example/docs", "quote_count": 1},
        ],
    }
    brand_expression = [
        {
            "query": "Which platform is suitable?",
            "sentiment_quote": "Target is easy to use.",
            "sentiment_score": "0.8",
        }
    ]
    category_actions = {
        "p0": [{"question_zh": "哪款平台适合企业团队？", "mentioned": False}],
        "p1": [],
        "p2": [],
    }
    raw = {
        "brand_name": "Target",
        "corp_name": "Target Inc.",
        "product_name": "Target Platform",
        "core_topic": "AI 搜索可见性监测",
        "market": "US",
        "language": "en-US",
        "task_id": "TASK-001",
        "batch_id": "BATCH-001",
        "overview": overview,
        "competitor": competitor,
        "citation": citation,
        "brand_expression": brand_expression,
        "category_actions": category_actions,
        "question_details": [{"question_id": "Q-001", "question_zh": "哪款平台适合企业团队？"}],
    }
    if action_context:
        raw["action_context"] = {
            "directions": [
                {
                    "direction_id": "ACT-001",
                    "direction": "品牌进入机会",
                    "state": "缺席型",
                    "posture": "补齐",
                    "key_evidence": "优先改进问题共8条",
                    "action_template": "围绕真实比较场景检查并完善事实信息入口",
                }
            ]
        }
    if as_strings:
        for field in ("overview", "competitor", "citation", "brand_expression", "category_actions", "question_details"):
            raw[field] = json.dumps(raw[field], ensure_ascii=False)
    return raw


def content_for(module_id):
    return {
        "M02": [
            "本品提及率为35%，进入回答的频率低于Leader。",
            "本品声量占比为28%，当前仍低于Leader。",
            "本品平均排名为2.8，进入回答后的顺位仍有差距。",
        ],
        "M03": [
            "媒体评测占比40%，是当前最主要的引用来源。",
            "品牌官网占比12%，已有2个官网页面被实际引用。",
            "现有官网引用已有基础，可继续检查并完善覆盖范围。",
        ],
        "M04": {
            "positive_evidence": [{"keyword": "易于使用", "explain": "现有回答明确认可产品使用门槛较低。"}],
            "risk_evidence": [],
            "analysis_items": [
                "正向表达主要集中在易用性。",
                "本批次未发现明确负向表达。",
                "当前证据有助于降低初步选择门槛。",
            ],
        },
        "M05": {
            "p0": "优先改进问题集中在品牌尚未进入回答的企业比较场景。",
            "p1": "",
            "p2": "",
        },
        "M01": {
            "title": "品牌已经进入部分回答，但相对竞品仍有可见性差距",
            "points": [
                "通用问题中的品牌进入率仍低于主要竞品。",
                "当前声量位置尚未形成稳定优势。",
                "品牌进入缺口集中在企业比较场景。",
            ],
            "conclusion": "后续应围绕已识别的比较意图补强可引用事实。",
        },
        "M06": {
            "summary": "本次行动聚焦已经确认的品牌进入缺口。",
            "actions": [
                {
                    "direction_id": "ACT-001",
                    "source_module": "品牌进入机会",
                    "title": "补强品牌进入",
                    "evidence": "优先改进问题共8条",
                    "action": "围绕真实比较场景检查并完善事实信息入口。",
                    "expected_impact": "提高回答采用信息的完整性",
                }
            ],
        },
        "M10": {
            "title": "海外 GEO 诊断结论",
            "summary": "品牌已有初步可见性，但在竞争位置和事实覆盖上仍有明确改进空间。",
            "points": [
                "品牌进入回答的频率仍低于主要竞品。",
                "引用结构已有官网基础但覆盖仍可扩展。",
                "正向表达集中在产品易用性。",
            ],
            "conclusion": "围绕真实比较场景补强事实入口，并持续观察后续采样变化。",
        },
    }[module_id]


def refs_for(module_id):
    return {
        "M02": {
            "/0": ["fact:/mention_ranking/0", "fact:/mention_ranking/1"],
            "/1": ["fact:/share_segments/0", "fact:/share_segments/1"],
            "/2": ["fact:/rank_performance/0", "fact:/rank_performance/1"],
        },
        "M03": {
            "/0": ["fact:/source_type_bars/0"],
            "/1": ["fact:/source_type_bars/1", "fact:/brand_official_pages"],
            "/2": ["fact:/brand_official_pages"],
        },
        "M04": {
            "/positive_evidence/0": ["evidence:BE-001"],
            "/analysis_items/0": ["evidence:BE-001"],
            "/analysis_items/1": ["fact:/"],
            "/analysis_items/2": ["evidence:BE-001"],
        },
        "M05": {"/p0": ["fact:/p0"]},
        "M01": {
            "/title": ["fact:/competitive_gaps/mention_rate"],
            "/points/0": ["fact:/competitive_gaps/mention_rate"],
            "/points/1": ["fact:/share_of_voice"],
            "/points/2": ["module:M05:/p0"],
            "/conclusion": ["module:M05:/p0"],
        },
        "M06": {
            "/summary": ["action:ACT-001"],
            "/actions/0": ["action:ACT-001", "module:M05:/p0"],
        },
        "M10": {
            "/title": ["module:M01:/title"],
            "/summary": ["module:M01:/conclusion"],
            "/points/0": ["module:M02:/0"],
            "/points/1": ["module:M03:/1"],
            "/points/2": ["module:M04:/analysis_items/0"],
            "/conclusion": ["module:M06:/summary"],
        },
    }[module_id]


def result_for(task, *, content=None, refs=None):
    return {
        "protocol_version": task["protocol_version"],
        "run_id": task["run_id"],
        "task_id": task["task_id"],
        "kind": task["kind"],
        "module_id": task["module_id"],
        "task_digest": task["task_digest"],
        "status": "completed",
        "output": {
            "content": content if content is not None else content_for(task["module_id"]),
            "evidence_refs": refs if refs is not None else refs_for(task["module_id"]),
        },
    }


class BackendReportTests(unittest.TestCase):
    def write_payload(self, root, raw):
        path = root / "payload.json"
        MODULE.write_json(path, raw)
        return path

    def submit_all(self, run_dir):
        while True:
            root, manifest = MODULE.load_run(run_dir)
            tasks = MODULE.ready_tasks(root, manifest)
            if not tasks:
                return
            for task in tasks:
                result_path = root / "results" / f"{task['task_id']}.inbox.json"
                MODULE.write_json(result_path, result_for(task))
                MODULE.submit_result(root, task["task_id"], result_path)

    def test_accepts_current_dify_json_string_inputs(self):
        normalized = MODULE.normalize_payload(payload(as_strings=True))
        self.assertIsInstance(normalized["overview"], dict)
        self.assertIsInstance(normalized["brand_expression"], list)
        self.assertEqual(normalized["brand_expression"][0]["evidence_id"], "BE-001")

    def test_rejects_mixed_batches(self):
        raw = payload()
        raw["overview"]["batch_id"] = "BATCH-OTHER"
        with self.assertRaisesRegex(MODULE.ContractError, "多个 batch_id"):
            MODULE.normalize_payload(raw)

    def test_prepare_emits_four_parallel_base_modules(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_path = self.write_payload(root, payload())
            run_dir = root / "run"
            run_root, manifest = MODULE.prepare_run(input_path, run_dir)
            self.assertEqual([task["module_id"] for task in MODULE.ready_tasks(run_root, manifest)], ["M02", "M03", "M04", "M05"])
            self.assertNotIn("M01", manifest["modules"])

    def test_rejects_invented_number(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_root, manifest = MODULE.prepare_run(self.write_payload(root, payload()), root / "run")
            task = next(item for item in MODULE.ready_tasks(run_root, manifest) if item["module_id"] == "M02")
            bad = content_for("M02")
            bad[0] = "本品提及率为99%，该数字并不存在于后端事实包。"
            path = root / "bad.json"
            MODULE.write_json(path, result_for(task, content=bad))
            with self.assertRaisesRegex(MODULE.ContractError, "不存在的数字"):
                MODULE.submit_result(run_root, task["task_id"], path)

    def test_m05_empty_group_must_remain_empty(self):
        normalized = MODULE.normalize_payload(payload())
        invalid = content_for("M05")
        invalid["p1"] = "持续优化问题存在明确缺口。"
        with self.assertRaisesRegex(MODULE.ContractError, "是否为空保持一致"):
            MODULE.validate_content("M05", invalid, normalized)

    def test_missing_action_context_degrades_without_local_recalculation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_root, _ = MODULE.prepare_run(self.write_payload(root, payload(action_context=False)), root / "run")
            self.submit_all(run_root)
            _, manifest = MODULE.load_run(run_root)
            self.assertEqual(manifest["modules"]["M06"]["status"], "degraded")
            self.assertTrue(any("不在本地重新计算" in item for item in manifest["warnings"]))

    def test_full_flow_outputs_normalized_and_dify_compatible_reports(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_root, _ = MODULE.prepare_run(self.write_payload(root, payload(as_strings=True)), root / "run")
            self.submit_all(run_root)
            _, manifest, report = MODULE.finalize_run(run_root)
            self.assertEqual(manifest["state"], "COMPLETE")
            self.assertEqual(report["backend_input_hash"], MODULE.read_json(run_root / "canonical/backend-payload.json")["input_hash"])
            dify = MODULE.read_json(run_root / "artifacts/dify-compatible-output.json")
            self.assertEqual(len(json.loads(dify["summary_competitor_performance"])), 3)
            actions = json.loads(dify["summary_priority_opportunities"])["actions"]
            self.assertNotIn("direction_id", actions[0])
            audit = MODULE.read_json(run_root / "artifacts/audit.json")
            self.assertFalse(audit["local_metric_recalculation"])

    def test_full_flow_outputs_backend_upload_csv_contract(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_root, _ = MODULE.prepare_run(self.write_payload(root, payload()), root / "run")
            self.submit_all(run_root)
            _, manifest, _ = MODULE.finalize_run(run_root)

            upload_path = run_root / "artifacts/report-upload.csv"
            self.assertTrue(upload_path.exists(), "finalize must write the backend-upload CSV artifact")
            self.assertEqual(manifest["artifacts"]["upload_csv"], "artifacts/report-upload.csv")
            raw = upload_path.read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
            decoded = raw.decode("utf-8-sig")
            self.assertEqual(decoded.count("\n"), decoded.count("\r\n"))

            reader = csv.DictReader(io.StringIO(decoded, newline=""))
            rows = list(reader)
            self.assertEqual(reader.fieldnames, ["module", "path", "index", "field", "value"])
            self.assertEqual(len(rows), 23)
            self.assertEqual(
                rows[:4],
                [
                    {
                        "module": "summary_overview",
                        "path": "",
                        "index": "",
                        "field": "title",
                        "value": "品牌已经进入部分回答，但相对竞品仍有可见性差距",
                    },
                    {
                        "module": "summary_category_actions",
                        "path": "",
                        "index": "",
                        "field": "p0",
                        "value": "优先改进问题集中在品牌尚未进入回答的企业比较场景。",
                    },
                    {
                        "module": "summary_category_actions",
                        "path": "",
                        "index": "",
                        "field": "p1",
                        "value": "",
                    },
                    {
                        "module": "summary_category_actions",
                        "path": "",
                        "index": "",
                        "field": "p2",
                        "value": "",
                    },
                ],
            )
            self.assertEqual(
                rows[-1],
                {
                    "module": "summary_priority_opportunities",
                    "path": "actions",
                    "index": "0",
                    "field": "expected_impact",
                    "value": "提高回答采用信息的完整性",
                },
            )
            self.assertNotIn("summary_final", {row["module"] for row in rows})


if __name__ == "__main__":
    unittest.main()
