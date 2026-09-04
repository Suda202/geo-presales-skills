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


def v2_payload():
    raw = payload()
    raw["schema_version"] = "overseas-geo-backend-report-input/v2"
    raw.pop("core_topic")
    raw["topics"] = [
        {"topic_id": "coverage", "topic_type": "coverage", "topic": "AI search visibility platforms"},
        {"topic_id": "depth_1", "topic_type": "depth", "topic": "AI visibility for agencies"},
        {"topic_id": "depth_2", "topic_type": "depth", "topic": "Enterprise AI visibility reporting"},
    ]
    raw["target_attributes"] = [
        {
            "attribute_id": "ATTR-001",
            "attribute": "multi-engine visibility measurement",
            "topic_ids": ["coverage", "depth_2"],
        }
    ]
    raw["attribute_diagnostics"] = [
        {
            "attribute_id": "ATTR-001",
            "status": "opportunity",
            "evidence_refs": ["Q-001"],
        }
    ]
    raw["comparison_outcomes"] = [
        {
            "question_id": "Q-C01",
            "topic_id": "coverage",
            "target_brand": "Target",
            "competitor": "Leader",
            "outcome": "competitor_wins",
            "decisiveness": "clear",
        }
    ]
    raw["market_perception"] = [
        {"topic_id": "coverage", "criteria": ["platform coverage", "reporting"]}
    ]
    raw["accuracy_findings"] = [
        {
            "question_id": "Q-A01",
            "attribute_id": "ATTR-001",
            "status": "accurate",
            "official_source_url": "https://target.example/product",
        }
    ]
    raw["citation"]["sample_scope"] = {
        "primary_diagnostic_intent": "discovery",
        "included_question_ids": ["Q-001"],
    }
    return raw


def platform_consistency_payload():
    raw = v2_payload()
    raw["platform_consistency"] = {
        "sample_scope": {
            "primary_diagnostic_intent": "discovery",
            "comparison_unit": "matched_prompts",
            "market": "US",
            "language": "en-US",
            "collection_window": "2026-08-01/2026-08-07",
        },
        "findings": [
            {
                "consistency_id": "PC-001",
                "scope_type": "overall",
                "scope_id": "overall",
                "comparable_platform_count": 3,
                "mention_consistency": "mixed",
                "position_consistency": "mixed",
                "consensus_strength": "weak",
                "platform_results": [
                    {"platform": "ChatGPT", "mention_rate": 0.35, "average_first_position": 2.8},
                    {"platform": "Gemini", "mention_rate": 0.47, "average_first_position": 1.7},
                    {"platform": "Perplexity", "mention_rate": 0.12, "average_first_position": 3.0},
                ],
                "evidence_refs": ["Q-001"],
            }
        ],
    }
    return raw


def competitor_comparison_payload(*, decisive=True):
    raw = v2_payload()
    if decisive:
        raw["competitor_comparison_summary"] = {
            "sample_scope": {"primary_diagnostic_intent": "competitor"},
            "pairs": [
                {
                    "comparison_id": "CMP-001",
                    "competitor_name": "Leader",
                    "total_valid_answers": 50,
                    "decisive_answers": 39,
                    "target_wins": 29,
                    "competitor_wins": 10,
                    "ties": 7,
                    "unclear": 4,
                    "target_decisive_win_rate": 29 / 39,
                    "advantage_themes": [
                        {
                            "theme_id": "CMP-ADV-001",
                            "dimension": "reporting",
                            "finding": "Target reporting is easier to use.",
                            "support_count": 2,
                            "evidence_refs": ["A-C01", "A-C02"],
                        }
                    ],
                    "disadvantage_themes": [
                        {
                            "theme_id": "CMP-DIS-001",
                            "dimension": "coverage",
                            "finding": "Leader supports more requested platforms.",
                            "support_count": 1,
                            "evidence_refs": ["A-C03"],
                        }
                    ],
                }
            ],
        }
    else:
        raw["competitor_comparison_summary"] = {
            "sample_scope": {"primary_diagnostic_intent": "competitor"},
            "pairs": [
                {
                    "comparison_id": "CMP-001",
                    "competitor_name": "Leader",
                    "total_valid_answers": 5,
                    "decisive_answers": 0,
                    "target_wins": 0,
                    "competitor_wins": 0,
                    "ties": 3,
                    "unclear": 2,
                    "target_decisive_win_rate": None,
                    "advantage_themes": [],
                    "disadvantage_themes": [],
                }
            ],
        }
    return raw


def market_perception_payload():
    raw = v2_payload()
    raw["market_perception_diagnostics"] = {
        "sample_scope": {"primary_diagnostic_intent": "market_perception"},
        "findings": [
            {
                "finding_id": "MP-001",
                "topic_id": "coverage",
                "attribute_id": "ATTR-001",
                "alignment_status": "missing",
                "intended_differentiator": "multi-engine visibility measurement",
                "market_criteria": ["reporting", "pricing"],
                "finding": "Current purchase criteria omit multi-engine coverage.",
                "support_count": 2,
                "evidence_refs": ["A-MP01", "A-MP02"],
            }
        ],
    }
    return raw


def scoped_action_payload(*, non_blog=False, internal_material=False):
    raw = v2_payload()
    direction = raw["action_context"]["directions"][0]
    direction.update({
        "route_type": "trust_gap",
        "verification_signals": ["citation", "visibility"],
    })
    if non_blog:
        direction.update({
            "target_surfaces": ["official_blog", "third_party_source", "non_blog_official_page"],
            "geo_team_delivery": "生成官网 Blog 和第三方比较内容",
            "client_action": "修改并上线产品页",
        })
    else:
        direction.update({
            "target_surfaces": ["official_blog", "third_party_source"],
            "geo_team_delivery": "生成官网 Blog 和第三方比较内容",
        })
    if internal_material:
        direction["target_surfaces"].append("internal_material")
        direction["client_inputs"] = ["最新集成清单", "可公开客户案例"]
        direction["client_action"] = direction.get("client_action") or "提供并确认内部事实材料"
        direction["confirmed_client_owner"] = "产品团队"
    return raw


def page_opportunity_payload():
    raw = scoped_action_payload(non_blog=True)
    raw["tags"] = [
        {"tag_id": "storage", "tag": "Storage", "topic_ids": ["coverage"]}
    ]
    raw["target_attributes"][0]["tag_ids"] = ["storage"]
    raw["page_opportunities"] = {
        "sample_scope": {
            "scan_scope": "topic_or_tag_relevant_official_pages",
            "coverage_status": "complete",
            "included_topic_ids": ["coverage"],
            "included_tag_ids": ["storage"],
            "candidate_page_count": 4,
        },
        "items": [
            {
                "page_opportunity_id": "PAGE-001",
                "url": "https://target.example/support/local-storage",
                "page_type": "non_blog_official_page",
                "topic_id": "coverage",
                "tag_ids": ["storage"],
                "attribute_ids": ["ATTR-001"],
                "prompt_gap_ids": ["Q-001"],
                "relevance_status": "high",
                "citation_status": "cited",
                "citation_refs": ["CIT-001"],
                "ai_gap_severity": "high",
                "page_value": "high",
                "opportunity_state": "reinforce_cited",
                "priority": "high",
                "priority_score": 92,
                "finding": "页面已被引用，但对本地存储能力的表达仍需强化。",
                "evidence_refs": ["Q-001", "CIT-001"],
            },
            {
                "page_opportunity_id": "PAGE-002",
                "url": "https://target.example/blog/continuous-recording-guide",
                "page_type": "official_blog",
                "topic_id": "coverage",
                "tag_ids": ["storage"],
                "attribute_ids": [],
                "prompt_gap_ids": ["Q-001"],
                "relevance_status": "high",
                "citation_status": "uncited",
                "citation_refs": [],
                "ai_gap_severity": "medium",
                "page_value": "high",
                "opportunity_state": "citation_gap",
                "priority": "medium",
                "priority_score": 78,
                "finding": "页面与持续录像问题高度相关，但尚未进入引用。",
                "evidence_refs": ["Q-001"],
            },
            {
                "page_opportunity_id": "PAGE-003",
                "url": "https://target.example/about-us",
                "page_type": "non_blog_official_page",
                "topic_id": "coverage",
                "tag_ids": [],
                "attribute_ids": [],
                "prompt_gap_ids": ["Q-001"],
                "relevance_status": "low",
                "citation_status": "cited",
                "citation_refs": ["CIT-002"],
                "ai_gap_severity": "low",
                "page_value": "medium",
                "opportunity_state": "avoid_forcing",
                "priority": "low",
                "priority_score": 25,
                "finding": "页面被引用，但与当前主题的能力缺口关系较弱。",
                "evidence_refs": ["Q-001", "CIT-002"],
            },
            {
                "page_opportunity_id": "PAGE-004",
                "url": "https://target.example/careers",
                "page_type": "non_blog_official_page",
                "topic_id": "coverage",
                "tag_ids": [],
                "attribute_ids": [],
                "prompt_gap_ids": ["Q-001"],
                "relevance_status": "low",
                "citation_status": "uncited",
                "citation_refs": [],
                "ai_gap_severity": "low",
                "page_value": "low",
                "opportunity_state": "ignore",
                "priority": "none",
                "priority_score": 0,
                "finding": "页面与当前主题基本无关。",
                "evidence_refs": ["Q-001"],
            },
        ],
    }
    raw["action_context"]["directions"][0]["page_opportunity_ids"] = ["PAGE-001", "PAGE-002"]
    return raw


def topic_consistency_payload():
    raw = platform_consistency_payload()
    raw["platform_consistency"]["findings"][0].update({
        "consistency_id": "PC-TOPIC-001",
        "scope_type": "topic",
        "scope_id": "coverage",
    })
    return raw


def profound_diagnostics_payload():
    raw = competitor_comparison_payload()
    raw["market_perception_diagnostics"] = market_perception_payload()["market_perception_diagnostics"]
    raw["platform_consistency"] = topic_consistency_payload()["platform_consistency"]
    return raw


def content_for(module_id):
    return {
        "M02": [
            "本品提及率为35%，进入回答的频率低于Leader。",
            "本品声量占比为28%，当前仍低于Leader。",
            "本品平均提及位置为2.8，进入回答后的顺位仍有差距。",
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
                "当前正向表达主要集中在易用性，风险证据未形成独立结论。",
                "当前证据有助于降低初步选择门槛。",
            ],
        },
        "M05": {
            "p0": "优先改进问题集中在品牌尚未进入回答的企业比较场景。",
            "p1": "",
            "p2": "",
        },
        "M01": {
            "title": "品牌已有初步可见性，主要缺口在竞争进入与证据覆盖",
            "points": [
                "品牌进入回答的频率仍低于主要竞品，差距首先属于进入不足。",
                "官网已有页面被实际引用，说明可以被发现，但决策证据覆盖仍有限。",
                "易用性已形成明确正向认知，但企业比较场景仍存在品牌进入缺口。",
            ],
            "conclusion": "当前主问题是企业比较场景尚未稳定提及品牌，且采购方仍缺少支撑产品特点的具体资料。",
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
        "M07": [
            "可比平台的品牌提及结果存在差异，尚未形成稳定共识。",
            "品牌获得提及时，平均提及位置在不同平台之间也存在差异。",
        ],
        "M08": [
            "当前品类购买标准集中在报告与价格，尚未包含品牌预设的多平台覆盖差异点。",
        ],
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
            "/title": ["module:M02:/0", "module:M03:/1"],
            "/points/0": ["module:M02:/0"],
            "/points/1": ["module:M03:/1"],
            "/points/2": ["module:M04:/analysis_items/0", "module:M05:/p0"],
            "/conclusion": ["module:M04:/analysis_items/0", "module:M05:/p0"],
        },
        "M06": {
            "/summary": ["action:ACT-001"],
            "/actions/0": ["action:ACT-001", "module:M05:/p0"],
        },
        "M07": {
            "/0": ["fact:/findings/0/mention_consistency", "fact:/findings/0/consensus_strength"],
            "/1": ["fact:/findings/0/position_consistency"],
        },
        "M08": {
            "/0": [
                "fact:/findings/0/alignment_status",
                "fact:/findings/0/market_criteria",
                "fact:/findings/0/intended_differentiator",
            ],
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

    def test_accepts_v2_topics_attributes_and_independent_diagnostics(self):
        normalized = MODULE.normalize_payload(v2_payload())
        self.assertEqual(normalized["schema_version"], "overseas-geo-backend-report-input/v2")
        self.assertEqual(len(normalized["topics"]), 3)
        self.assertEqual(normalized["target_attributes"][0]["attribute_id"], "ATTR-001")
        self.assertEqual(normalized["comparison_outcomes"][0]["outcome"], "competitor_wins")
        self.assertEqual(
            normalized["citation"]["sample_scope"]["primary_diagnostic_intent"],
            "discovery",
        )

    def test_v2_rejects_citation_scope_that_mixes_non_discovery_samples(self):
        raw = v2_payload()
        raw["citation"]["sample_scope"]["primary_diagnostic_intent"] = "sentiment"
        with self.assertRaisesRegex(MODULE.ContractError, "引用主样本范围必须是 discovery"):
            MODULE.normalize_payload(raw)

    def test_v2_prepare_persists_all_independent_diagnostic_resources(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_root, _ = MODULE.prepare_run(self.write_payload(root, v2_payload()), root / "run")
            for name in (
                "topics", "target_attributes", "attribute_diagnostics",
                "comparison_outcomes", "competitor_comparison_summary", "market_perception",
                "market_perception_diagnostics", "accuracy_findings", "platform_consistency",
            ):
                self.assertTrue((run_root / f"canonical/{name}.json").exists(), name)

    def test_v2_tasks_receive_their_independent_diagnostic_resources(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_root, manifest = MODULE.prepare_run(self.write_payload(root, v2_payload()), root / "run")
            tasks = {task["module_id"]: task for task in MODULE.ready_tasks(run_root, manifest)}
            self.assertIn("diagnostic:comparison_outcomes", tasks["M02"]["resources"])
            self.assertIn("diagnostic:competitor_comparison_summary", tasks["M02"]["resources"])
            self.assertIn("diagnostic:attribute_diagnostics", tasks["M04"]["resources"])
            self.assertIn("diagnostic:accuracy_findings", tasks["M05"]["resources"])
            self.assertEqual(manifest["modules"]["M08"]["status"], "degraded")
            self.assertIn("diagnostic:", tasks["M04"]["input"]["evidence_rule"])

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
            self.assertEqual(manifest["modules"]["M07"]["status"], "degraded")
            self.assertEqual(manifest["modules"]["M08"]["status"], "degraded")
            self.assertTrue(any("不在本地拼接平台样本" in item for item in manifest["warnings"]))

    def test_platform_consistency_is_a_formal_parallel_fact_module(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_root, manifest = MODULE.prepare_run(
                self.write_payload(root, platform_consistency_payload()), root / "run"
            )
            tasks = {task["module_id"]: task for task in MODULE.ready_tasks(run_root, manifest)}
            self.assertIn("M07", tasks)
            self.assertEqual(tasks["M07"]["resources"]["facts"]["path"], "canonical/platform_consistency.json")
            self.assertTrue(any("不得从逐条平台结果自行计算" in rule for rule in tasks["M07"]["input"]["synthesis_rules"]))

    def test_competitor_summary_uses_only_decisive_win_rate_and_evidence_themes(self):
        normalized = MODULE.normalize_payload(competitor_comparison_payload())
        pair = normalized["competitor_comparison_summary"]["pairs"][0]
        self.assertEqual(pair["decisive_answers"], 39)
        self.assertAlmostEqual(pair["target_decisive_win_rate"], 29 / 39)
        self.assertNotAlmostEqual(pair["target_decisive_win_rate"], 29 / 50)
        self.assertNotIn("target_overall_win_rate", pair)
        self.assertEqual(pair["advantage_themes"][0]["support_count"], 2)

    def test_competitor_summary_rejects_bad_denominator_rate_and_overall_rate(self):
        raw = competitor_comparison_payload()
        raw["competitor_comparison_summary"]["pairs"][0]["decisive_answers"] = 40
        with self.assertRaisesRegex(MODULE.ContractError, "双方明确胜出数之和"):
            MODULE.normalize_payload(raw)

        raw = competitor_comparison_payload()
        raw["competitor_comparison_summary"]["pairs"][0]["target_decisive_win_rate"] = 0.58
        with self.assertRaisesRegex(MODULE.ContractError, "决胜回答计数不一致"):
            MODULE.normalize_payload(raw)

        raw = competitor_comparison_payload()
        raw["competitor_comparison_summary"]["pairs"][0]["target_overall_win_rate"] = 0.58
        with self.assertRaisesRegex(MODULE.ContractError, "不接收总体胜率字段"):
            MODULE.normalize_payload(raw)

        raw = competitor_comparison_payload()
        raw["competitor_comparison_summary"]["pairs"][0]["advantage_themes"][0]["support_count"] = 3
        with self.assertRaisesRegex(MODULE.ContractError, "不能超过唯一证据引用数"):
            MODULE.normalize_payload(raw)

        raw = competitor_comparison_payload()
        raw["competitor_comparison_summary"]["pairs"][0]["competitor_name"] = "Other"
        with self.assertRaisesRegex(MODULE.ContractError, "逐一对应 comparison_outcomes"):
            MODULE.normalize_payload(raw)

    def test_competitor_summary_requires_null_without_decisive_answers(self):
        normalized = MODULE.normalize_payload(competitor_comparison_payload(decisive=False))
        self.assertIsNone(normalized["competitor_comparison_summary"]["pairs"][0]["target_decisive_win_rate"])
        raw = competitor_comparison_payload(decisive=False)
        raw["competitor_comparison_summary"]["pairs"][0]["target_decisive_win_rate"] = 0
        with self.assertRaisesRegex(MODULE.ContractError, "决胜回答计数不一致"):
            MODULE.normalize_payload(raw)

    def test_m02_must_show_decisive_rate_and_comparison_themes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_root, manifest = MODULE.prepare_run(
                self.write_payload(root, competitor_comparison_payload()), root / "run"
            )
            task = next(item for item in MODULE.ready_tasks(run_root, manifest) if item["module_id"] == "M02")
            content = [
                "Target对Leader的竞品胜率为74.36%，39个决胜回答中目标品牌获胜29次、Leader获胜10次。",
                "正面对比中，Target在报告易用性上占优，但Leader的平台覆盖更完整。",
            ]
            refs = {
                "/0": [
                    "diagnostic:competitor_comparison_summary:/pairs/0/target_decisive_win_rate",
                    "diagnostic:competitor_comparison_summary:/pairs/0/decisive_answers",
                ],
                "/1": [
                    "diagnostic:competitor_comparison_summary:/pairs/0/advantage_themes/0",
                    "diagnostic:competitor_comparison_summary:/pairs/0/disadvantage_themes/0",
                ],
            }
            result_path = root / "M02-result.json"
            MODULE.write_json(result_path, result_for(task, content=content, refs=refs))
            MODULE.submit_result(run_root, task["task_id"], result_path)

            invalid = list(content)
            invalid[0] = "Target对Leader的总体胜率为58%。"
            with self.assertRaisesRegex(MODULE.ContractError, "禁止表达"):
                MODULE.validate_content("M02", invalid, MODULE.normalize_payload(competitor_comparison_payload()))

    def test_market_perception_is_a_formal_parallel_fact_module(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_root, manifest = MODULE.prepare_run(
                self.write_payload(root, market_perception_payload()), root / "run"
            )
            tasks = {task["module_id"]: task for task in MODULE.ready_tasks(run_root, manifest)}
            self.assertIn("M08", tasks)
            self.assertEqual(
                tasks["M08"]["resources"]["facts"]["path"],
                "canonical/market_perception_diagnostics.json",
            )
            rules = "\n".join(tasks["M08"]["input"]["synthesis_rules"])
            self.assertIn("不得从原始回答重新归纳", rules)
            self.assertIn("不得写成品牌可见度", rules)

    def test_topic_consistency_uses_existing_topic_without_attribute_state(self):
        normalized = MODULE.normalize_payload(topic_consistency_payload())
        finding = normalized["platform_consistency"]["findings"][0]
        self.assertEqual(finding["scope_type"], "topic")
        self.assertEqual(finding["scope_id"], "coverage")
        self.assertNotIn("attribute_signal_state", finding)
        self.assertNotIn("rank_visibility_pattern", finding)

        raw = topic_consistency_payload()
        raw["platform_consistency"]["findings"][0]["scope_id"] = "unknown-topic"
        with self.assertRaisesRegex(MODULE.ContractError, "必须引用已有主题对象"):
            MODULE.normalize_payload(raw)

        raw = topic_consistency_payload()
        raw["platform_consistency"]["findings"][0]["attribute_signal_state"] = "unsettled"
        with self.assertRaisesRegex(MODULE.ContractError, "不接收 Attribute 级信号"):
            MODULE.normalize_payload(raw)

    def test_consistency_rules_limit_formal_output_to_overall_and_topic(self):
        rules = "\n".join(MODULE.module_synthesis_rules("M07"))
        self.assertIn("只输出整体和主题两级", rules)
        self.assertIn("Attribute 只可作为其他模块或跨模块解释证据", rules)
        self.assertIn("该主题的跨平台判断尚未稳定", rules)

        raw = topic_consistency_payload()
        raw["platform_consistency"]["findings"][0]["scope_type"] = "attribute"
        raw["platform_consistency"]["findings"][0]["scope_id"] = "ATTR-001"
        with self.assertRaisesRegex(MODULE.ContractError, "必须是 overall/topic"):
            MODULE.normalize_payload(raw)

    def test_market_perception_accepts_four_formal_states_and_validates_mapping(self):
        for status in ("included", "missing", "conflicting", "insufficient"):
            with self.subTest(status=status):
                raw = market_perception_payload()
                finding = raw["market_perception_diagnostics"]["findings"][0]
                finding["alignment_status"] = status
                if status == "insufficient":
                    finding["support_count"] = 0
                    finding["evidence_refs"] = []
                    finding["market_criteria"] = []
                normalized = MODULE.normalize_payload(raw)
                self.assertEqual(
                    normalized["market_perception_diagnostics"]["findings"][0]["alignment_status"],
                    status,
                )

        raw = market_perception_payload()
        raw["market_perception_diagnostics"]["findings"][0]["topic_id"] = "depth_1"
        with self.assertRaisesRegex(MODULE.ContractError, "必须属于该 Attribute"):
            MODULE.normalize_payload(raw)

        raw = market_perception_payload()
        raw["market_perception_diagnostics"]["findings"][0]["support_count"] = 3
        with self.assertRaisesRegex(MODULE.ContractError, "不能超过唯一证据引用数"):
            MODULE.normalize_payload(raw)

    def test_m01_must_use_material_market_perception_when_provided(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_root, manifest = MODULE.prepare_run(
                self.write_payload(root, market_perception_payload()), root / "run"
            )
            for module_id in ("M02", "M03", "M04", "M05", "M08"):
                task = next(task for task in MODULE.ready_tasks(run_root, manifest) if task["module_id"] == module_id)
                result_path = root / f"{module_id}-result.json"
                MODULE.write_json(result_path, result_for(task))
                MODULE.submit_result(run_root, task["task_id"], result_path)
                _, manifest = MODULE.load_run(run_root)
            m01 = next(task for task in MODULE.ready_tasks(run_root, manifest) if task["module_id"] == "M01")
            result_path = root / "M01-result.json"
            MODULE.write_json(result_path, result_for(m01))
            with self.assertRaisesRegex(MODULE.ContractError, "必须引用已完成的品类认知"):
                MODULE.submit_result(run_root, m01["task_id"], result_path)

    def test_market_perception_flows_into_overview_without_new_csv_module(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_root, manifest = MODULE.prepare_run(
                self.write_payload(root, market_perception_payload()), root / "run"
            )
            while True:
                tasks = MODULE.ready_tasks(run_root, manifest)
                if not tasks:
                    break
                for task in tasks:
                    content = content_for(task["module_id"])
                    refs = refs_for(task["module_id"])
                    if task["module_id"] == "M01":
                        content = json.loads(json.dumps(content, ensure_ascii=False))
                        refs = json.loads(json.dumps(refs, ensure_ascii=False))
                        content["points"].append("当前购买框架尚未包含品牌预设的多平台覆盖差异点。")
                        refs["/points/3"] = ["module:M08:/0"]
                    result_path = root / f"{task['task_id']}.result.json"
                    MODULE.write_json(result_path, result_for(task, content=content, refs=refs))
                    MODULE.submit_result(run_root, task["task_id"], result_path)
                    _, manifest = MODULE.load_run(run_root)
            _, _, report = MODULE.finalize_run(run_root)
            self.assertEqual(report["modules"]["summary_market_perception"], content_for("M08"))
            with (run_root / "artifacts/report-upload.csv").open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertTrue(any("购买框架尚未包含" in row["value"] for row in rows))
            self.assertNotIn("summary_market_perception", {row["module"] for row in rows})

    def test_profound_diagnostics_complete_together_without_expanding_upload_schema(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_root, manifest = MODULE.prepare_run(
                self.write_payload(root, profound_diagnostics_payload()), root / "run"
            )
            while True:
                tasks = MODULE.ready_tasks(run_root, manifest)
                if not tasks:
                    break
                for task in tasks:
                    content = content_for(task["module_id"])
                    refs = refs_for(task["module_id"])
                    if task["module_id"] == "M02":
                        content = [
                            "Target对Leader的竞品胜率为74.36%，39个决胜回答中目标品牌获胜29次、Leader获胜10次。",
                            "正面对比中，Target在报告易用性上占优，但Leader的平台覆盖更完整。",
                        ]
                        refs = {
                            "/0": [
                                "diagnostic:competitor_comparison_summary:/pairs/0/target_decisive_win_rate",
                                "diagnostic:competitor_comparison_summary:/pairs/0/decisive_answers",
                            ],
                            "/1": [
                                "diagnostic:competitor_comparison_summary:/pairs/0/advantage_themes/0",
                                "diagnostic:competitor_comparison_summary:/pairs/0/disadvantage_themes/0",
                            ],
                        }
                    elif task["module_id"] == "M07":
                        content = [
                            "覆盖主题在不同平台的品牌提及结果存在差异，该主题的跨平台判断尚未稳定。",
                            "品牌获得提及时，覆盖主题的平均提及位置在平台之间也存在差异。",
                        ]
                        refs = {
                            "/0": ["fact:/findings/0/mention_consistency"],
                            "/1": ["fact:/findings/0/position_consistency"],
                        }
                    elif task["module_id"] == "M01":
                        content = json.loads(json.dumps(content, ensure_ascii=False))
                        refs = json.loads(json.dumps(refs, ensure_ascii=False))
                        content["points"].extend([
                            "覆盖主题的品牌进入与平均提及位置存在平台差异，该主题的跨平台判断尚未稳定。",
                            "当前购买框架尚未包含品牌预设的多平台覆盖差异点。",
                        ])
                        refs["/points/3"] = ["module:M07:/0"]
                        refs["/points/4"] = ["module:M08:/0"]
                    result_path = root / f"{task['task_id']}.result.json"
                    MODULE.write_json(result_path, result_for(task, content=content, refs=refs))
                    MODULE.submit_result(run_root, task["task_id"], result_path)
                    _, manifest = MODULE.load_run(run_root)

            _, _, report = MODULE.finalize_run(run_root)
            self.assertIn("summary_platform_consistency", report["modules"])
            self.assertIn("summary_market_perception", report["modules"])
            dify = MODULE.read_json(run_root / "artifacts/dify-compatible-output.json")
            self.assertNotIn("summary_platform_consistency", dify)
            self.assertNotIn("summary_market_perception", dify)
            with (run_root / "artifacts/report-upload.csv").open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            modules = {row["module"] for row in rows}
            self.assertNotIn("summary_platform_consistency", modules)
            self.assertNotIn("summary_market_perception", modules)
            self.assertTrue(any("74.36%" in row["value"] for row in rows))
            self.assertTrue(any("该主题的跨平台判断尚未稳定" in row["value"] for row in rows))
            self.assertTrue(any("购买框架尚未包含" in row["value"] for row in rows))

    def test_platform_consistency_requires_discovery_matched_prompts(self):
        raw = platform_consistency_payload()
        raw["platform_consistency"]["sample_scope"]["primary_diagnostic_intent"] = "sentiment"
        with self.assertRaisesRegex(MODULE.ContractError, "主样本范围必须是 discovery"):
            MODULE.normalize_payload(raw)
        raw = platform_consistency_payload()
        raw["platform_consistency"]["sample_scope"]["comparison_unit"] = "unmatched_prompts"
        with self.assertRaisesRegex(MODULE.ContractError, "匹配 Prompt 样本"):
            MODULE.normalize_payload(raw)

    def test_platform_consistency_rejects_incomparable_position_and_scope(self):
        raw = platform_consistency_payload()
        raw["platform_consistency"]["findings"][0]["platform_results"][0]["mention_rate"] = 0
        with self.assertRaisesRegex(MODULE.ContractError, "average_first_position 必须是 null"):
            MODULE.normalize_payload(raw)
        raw = platform_consistency_payload()
        raw["platform_consistency"]["findings"][0]["scope_type"] = "attribute"
        raw["platform_consistency"]["findings"][0]["scope_id"] = "ATTR-001"
        with self.assertRaisesRegex(MODULE.ContractError, "必须是 overall/topic"):
            MODULE.normalize_payload(raw)

        raw = topic_consistency_payload()
        raw["platform_consistency"]["findings"][0]["scope_id"] = "TOPIC-UNKNOWN"
        with self.assertRaisesRegex(MODULE.ContractError, "必须引用已有主题对象"):
            MODULE.normalize_payload(raw)

    def test_platform_consistency_rejects_all_absent_with_position_consistency(self):
        raw = platform_consistency_payload()
        finding = raw["platform_consistency"]["findings"][0]
        finding["mention_consistency"] = "consistent_absent"
        finding["position_consistency"] = "consistent"
        for result in finding["platform_results"]:
            result["mention_rate"] = 0
            result["average_first_position"] = None
        with self.assertRaisesRegex(MODULE.ContractError, "必须是 not_applicable"):
            MODULE.normalize_payload(raw)

    def test_insufficient_platform_finding_does_not_have_to_enter_overview(self):
        raw = platform_consistency_payload()
        finding = raw["platform_consistency"]["findings"][0]
        finding["mention_consistency"] = "insufficient"
        finding["position_consistency"] = "insufficient"
        finding["consensus_strength"] = "insufficient"
        normalized = MODULE.normalize_payload(raw)
        self.assertFalse(MODULE.has_material_platform_consistency(normalized))

    def test_m01_waits_for_all_fact_modules_and_reads_them(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_root, manifest = MODULE.prepare_run(self.write_payload(root, payload()), root / "run")

            m05 = next(task for task in MODULE.ready_tasks(run_root, manifest) if task["module_id"] == "M05")
            result_path = root / "M05-result.json"
            MODULE.write_json(result_path, result_for(m05))
            MODULE.submit_result(run_root, m05["task_id"], result_path)
            _, manifest = MODULE.load_run(run_root)
            self.assertNotIn("M01", manifest["modules"])

            for module_id in ("M02", "M03", "M04"):
                task = next(task for task in MODULE.ready_tasks(run_root, manifest) if task["module_id"] == module_id)
                result_path = root / f"{module_id}-result.json"
                MODULE.write_json(result_path, result_for(task))
                MODULE.submit_result(run_root, task["task_id"], result_path)
                _, manifest = MODULE.load_run(run_root)

            m01 = next(task for task in MODULE.ready_tasks(run_root, manifest) if task["module_id"] == "M01")
            self.assertEqual(m01["depends_on"], ["M02", "M03", "M04", "M05", "M07", "M08"])
            self.assertEqual(
                set(m01["resources"]),
                {
                    "facts",
                    "diagnostic:attribute_diagnostics",
                    "diagnostic:comparison_outcomes",
                    "diagnostic:accuracy_findings",
                    "module:M02",
                    "module:M03",
                    "module:M04",
                    "module:M05",
                    "module:M07",
                    "module:M08",
                },
            )
            self.assertEqual(m01["input"]["synthesis_method"], "数据事实 → 状态判断 → 业务含义 → 证据边界")
            self.assertTrue(any("不得重复同一组数字" in rule for rule in m01["input"]["synthesis_rules"]))

    def test_m01_must_use_material_platform_consistency_when_provided(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_root, manifest = MODULE.prepare_run(
                self.write_payload(root, platform_consistency_payload()), root / "run"
            )
            for module_id in ("M02", "M03", "M04", "M05", "M07"):
                task = next(task for task in MODULE.ready_tasks(run_root, manifest) if task["module_id"] == module_id)
                result_path = root / f"{module_id}-result.json"
                MODULE.write_json(result_path, result_for(task))
                MODULE.submit_result(run_root, task["task_id"], result_path)
                _, manifest = MODULE.load_run(run_root)
            m01 = next(task for task in MODULE.ready_tasks(run_root, manifest) if task["module_id"] == "M01")
            result_path = root / "M01-result.json"
            MODULE.write_json(result_path, result_for(m01))
            with self.assertRaisesRegex(MODULE.ContractError, "必须引用已完成的跨平台一致性结论"):
                MODULE.submit_result(run_root, m01["task_id"], result_path)

    def test_platform_consistency_flows_into_uploaded_overview_without_new_csv_module(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_root, manifest = MODULE.prepare_run(
                self.write_payload(root, platform_consistency_payload()), root / "run"
            )
            while True:
                tasks = MODULE.ready_tasks(run_root, manifest)
                if not tasks:
                    break
                for task in tasks:
                    content = content_for(task["module_id"])
                    refs = refs_for(task["module_id"])
                    if task["module_id"] == "M01":
                        content = json.loads(json.dumps(content, ensure_ascii=False))
                        refs = json.loads(json.dumps(refs, ensure_ascii=False))
                        content["points"].append("可比平台的品牌进入结果存在差异，跨平台表现尚未稳定。")
                        refs["/points/3"] = ["module:M07:/0"]
                    result_path = root / f"{task['task_id']}.result.json"
                    MODULE.write_json(result_path, result_for(task, content=content, refs=refs))
                    MODULE.submit_result(run_root, task["task_id"], result_path)
                    _, manifest = MODULE.load_run(run_root)
            _, _, report = MODULE.finalize_run(run_root)
            self.assertEqual(report["modules"]["summary_platform_consistency"], content_for("M07"))
            with (run_root / "artifacts/report-upload.csv").open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertTrue(any("跨平台表现尚未稳定" in row["value"] for row in rows))
            self.assertNotIn("summary_platform_consistency", {row["module"] for row in rows})

    def test_customer_copy_rejects_internal_question_types_and_zero_rank(self):
        normalized = MODULE.normalize_payload(payload())
        cases = (
            (0, "通用问题中的品牌提及率为35%。"),
            (2, "品牌平均提及位置为0，当前没有进入回答。"),
        )
        for index, text in cases:
            with self.subTest(text=text):
                invalid = content_for("M02")
                invalid[index] = text
                with self.assertRaisesRegex(MODULE.ContractError, "禁止表达或内部编码"):
                    MODULE.validate_content("M02", invalid, normalized)

    def test_customer_copy_rejects_deprecated_metric_terms(self):
        normalized = MODULE.normalize_payload(payload())
        cases = (
            ("M02", 0, "本品平均提及排名为2.8，进入回答后的顺位仍有差距。"),
            ("M03", 0, "品牌官网引用占比为12%。"),
        )
        for module_id, index, text in cases:
            with self.subTest(text=text):
                invalid = content_for(module_id)
                invalid[index] = text
                with self.assertRaisesRegex(MODULE.ContractError, "禁止表达或内部编码"):
                    MODULE.validate_content(module_id, invalid, normalized)

    def test_customer_copy_rejects_procurement_overclaim_and_editor_jargon(self):
        normalized = MODULE.normalize_payload(payload())
        cases = (
            ("M02", 0, "目标品牌尚未进入供应商候选名单。"),
            ("M02", 1, "当前是自然进入缺口，需要补强证据承接。"),
            ("M02", 2, "建议重新选择监测竞品。"),
            ("M02", 1, "竞品比较中品牌提及稳定且值得维护。"),
            ("M03", 2, "官网可以抓取，但决策证据层级不足。"),
        )
        for module_id, index, text in cases:
            with self.subTest(text=text):
                invalid = content_for(module_id)
                invalid[index] = text
                with self.assertRaisesRegex(MODULE.ContractError, "禁止表达或内部编码"):
                    MODULE.validate_content(module_id, invalid, normalized)

        invalid_expression = content_for("M04")
        invalid_expression["analysis_items"][0] = "公开信息尚不能替代供应商实绩验证。"
        with self.assertRaisesRegex(MODULE.ContractError, "禁止表达或内部编码"):
            MODULE.validate_content("M04", invalid_expression, normalized)

    def test_tasks_explain_metric_scope_and_protect_customer_provided_competitors(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_root, manifest = MODULE.prepare_run(self.write_payload(root, payload()), root / "run")
            tasks = {task["module_id"]: task for task in MODULE.ready_tasks(run_root, manifest)}

            global_rules = "\n".join(tasks["M02"]["input"]["global_rules"])
            self.assertIn("发现、竞品、验证、准确性、评价和品类认知", global_rules)
            self.assertIn("不得混用", global_rules)
            self.assertIn("主要引用生态只使用 Discovery", global_rules)
            self.assertIn("情绪直接使用完整 analysis_type=sentiment 结果", global_rules)
            self.assertIn("不再按 diagnostic_intent", global_rules)
            self.assertIn("提及率排名按 Discovery 提及率比较品牌名次", global_rules)
            self.assertIn("客户指标统一写平均提及位置和引用份额", global_rules)
            self.assertIn("问题本身可能提及目标品牌", global_rules)
            self.assertIn("不能证明品牌在用户未指定时进入回答", global_rules)

            competitor_rules = "\n".join(tasks["M02"]["input"]["synthesis_rules"])
            self.assertIn("客户提供的竞品", competitor_rules)
            self.assertIn("不要据此判断竞品选择有误", competitor_rules)
            self.assertIn("不得建议替换", competitor_rules)

    def test_task190_regression_contract_covers_scope_and_copy_terms(self):
        cases_path = SCRIPT.parents[1] / "evals" / "task_190_regression_cases.json"
        regression = json.loads(cases_path.read_text(encoding="utf-8"))
        cases = {item["id"]: item for item in regression["cases"]}

        self.assertFalse(
            cases["visibility_excludes_non_discovery"]["expected"]["include_in_formal_visibility"]
        )
        self.assertTrue(
            cases["discovery_included_in_visibility"]["expected"]["include_in_formal_visibility"]
        )
        self.assertTrue(
            cases["sentiment_retained_without_discovery"]["expected"]["include_in_sentiment"]
        )
        self.assertTrue(
            cases["sentiment_retained_with_overlapping_intents"]["expected"]["include_in_sentiment"]
        )
        self.assertTrue(
            cases["sentiment_caveat_not_automatically_negative"]["expected"]["forbid_automatic_negative"]
        )

        rank_terms = cases["rank_metrics_remain_distinct"]["expected_customer_terms"]
        self.assertEqual(rank_terms["mention_rate_rank"], "提及率排名")
        self.assertEqual(rank_terms["average_first_position"], "平均提及位置")

        deprecated = cases["deprecated_copy_terms_rejected"]["forbidden_customer_terms"]
        for term in deprecated:
            with self.subTest(term=term):
                self.assertIsNotNone(MODULE.CUSTOMER_BANNED.search(term))

    def test_customer_modules_allow_fewer_non_redundant_conclusions(self):
        normalized = MODULE.normalize_payload(payload())

        MODULE.validate_content(
            "M02",
            ["目标品牌和指定竞品均未被提及，因此当前数据无法比较相对表现。"],
            normalized,
        )
        MODULE.validate_content(
            "M03",
            [
                "官网已有页面被回答引用，说明可以被正常找到。",
                "官网引用只出现在情绪分析中，可见度统计尚未采用官网内容。",
            ],
            normalized,
        )
        expression = content_for("M04")
        expression["analysis_items"] = [
            "回答能识别产品特点，但采购方仍缺少具体工厂、型号证书和量产记录。"
        ]
        MODULE.validate_content("M04", expression, normalized)

    def test_action_rules_forbid_invented_operational_state(self):
        action_rules = "\n".join(MODULE.module_synthesis_rules("M06"))
        self.assertIn("不得推断现有资料分散", action_rules)
        self.assertIn("只存在于图片或附件", action_rules)
        self.assertIn("分散在不同人员或部门", action_rules)
        self.assertIn("问题和证据只能来自后端方向或已接受模块", action_rules)
        self.assertIn("我方可直接交付只限官网 Blog 和第三方内容", action_rules)
        self.assertIn("非 Blog 官网页面只能提供修改清单或建议文案", action_rules)
        self.assertIn("由客户修改并上线", action_rules)
        self.assertIn("不得为了匹配我方交付范围", action_rules)
        self.assertIn("不得根据单个低指标自行归类", action_rules)
        self.assertIn("page_opportunity_ids", action_rules)
        self.assertIn("已引用页面写强化目标，未引用页面写 Citation Gap", action_rules)

        citation_rules = "\n".join(MODULE.module_synthesis_rules("M03"))
        self.assertIn("主题/Tag 相关官网页面扫描，而不是已引用页面子集", citation_rules)
        self.assertIn("页面相关性与 Citation 状态必须分开", citation_rules)
        self.assertIn("Attribute/Prompt Gap 只指导具体改什么", citation_rules)

    def test_action_context_validates_delivery_surfaces_and_client_dependencies(self):
        normalized = MODULE.normalize_payload(scoped_action_payload(non_blog=True, internal_material=True))
        direction = normalized["action_context"]["directions"][0]
        self.assertEqual(
            direction["target_surfaces"],
            ["official_blog", "third_party_source", "non_blog_official_page", "internal_material"],
        )
        self.assertEqual(direction["confirmed_client_owner"], "产品团队")
        self.assertEqual(direction["route_type"], "trust_gap")
        self.assertEqual(direction["verification_signals"], ["citation", "visibility"])

        raw = scoped_action_payload(non_blog=True)
        raw["action_context"]["directions"][0].pop("client_action")
        with self.assertRaisesRegex(MODULE.ContractError, "必须提供 client_action"):
            MODULE.normalize_payload(raw)

        raw = scoped_action_payload(internal_material=True)
        raw["action_context"]["directions"][0]["client_inputs"] = []
        with self.assertRaisesRegex(MODULE.ContractError, "必须列出 client_inputs"):
            MODULE.normalize_payload(raw)

        raw = scoped_action_payload()
        raw["action_context"]["directions"][0]["target_surfaces"] = ["homepage"]
        with self.assertRaisesRegex(MODULE.ContractError, "有效且不重复"):
            MODULE.normalize_payload(raw)

    def test_action_context_validates_chapter5_route_and_verification_signal(self):
        normalized = MODULE.normalize_payload(scoped_action_payload())
        direction = normalized["action_context"]["directions"][0]
        self.assertEqual(direction["route_type"], "trust_gap")
        self.assertEqual(direction["verification_signals"], ["citation", "visibility"])

        raw = scoped_action_payload()
        raw["action_context"]["directions"][0]["route_type"] = "content_gap"
        with self.assertRaisesRegex(MODULE.ContractError, "route_type 枚举无效"):
            MODULE.normalize_payload(raw)

        raw = scoped_action_payload()
        raw["action_context"]["directions"][0]["verification_signals"] = []
        with self.assertRaisesRegex(MODULE.ContractError, "必须提供 verification_signals"):
            MODULE.normalize_payload(raw)

        raw = scoped_action_payload()
        raw["action_context"]["directions"][0]["target_surfaces"] = ["official_blog"]
        with self.assertRaisesRegex(MODULE.ContractError, "trust_gap 必须包含 third_party_source"):
            MODULE.normalize_payload(raw)

        raw = scoped_action_payload()
        direction = raw["action_context"]["directions"][0]
        direction["route_type"] = "accuracy_correction"
        direction["verification_signals"] = ["citation"]
        with self.assertRaisesRegex(MODULE.ContractError, "必须使用 accuracy"):
            MODULE.normalize_payload(raw)

    def test_page_opportunities_scan_all_relevant_pages_and_preserve_two_axes(self):
        normalized = MODULE.normalize_payload(page_opportunity_payload())
        pages = normalized["page_opportunities"]["items"]
        self.assertEqual([item["opportunity_state"] for item in pages], [
            "reinforce_cited", "citation_gap", "avoid_forcing", "ignore"
        ])
        self.assertEqual(normalized["tags"][0]["tag_id"], "storage")
        self.assertEqual(
            normalized["action_context"]["directions"][0]["page_opportunity_ids"],
            ["PAGE-001", "PAGE-002"],
        )

        raw = page_opportunity_payload()
        raw["page_opportunities"]["sample_scope"]["scan_scope"] = "cited_pages_only"
        with self.assertRaisesRegex(MODULE.ContractError, "不能只使用已引用页面"):
            MODULE.normalize_payload(raw)

        raw = page_opportunity_payload()
        raw["page_opportunities"]["items"][1]["opportunity_state"] = "reinforce_cited"
        with self.assertRaisesRegex(MODULE.ContractError, "四象限不一致"):
            MODULE.normalize_payload(raw)

        raw = page_opportunity_payload()
        raw["page_opportunities"]["items"][0]["citation_refs"] = []
        with self.assertRaisesRegex(MODULE.ContractError, "已引用页面必须提供"):
            MODULE.normalize_payload(raw)

    def test_attribute_can_be_carried_by_tag_without_becoming_output_field(self):
        raw = page_opportunity_payload()
        raw["target_attributes"][0]["topic_ids"] = []
        normalized = MODULE.normalize_payload(raw)
        self.assertEqual(normalized["target_attributes"][0]["tag_ids"], ["storage"])
        self.assertEqual(normalized["target_attributes"][0]["topic_ids"], [])

    def test_action_rejects_low_relevance_or_mismatched_page_surface(self):
        raw = page_opportunity_payload()
        raw["action_context"]["directions"][0]["page_opportunity_ids"] = ["PAGE-003"]
        with self.assertRaisesRegex(MODULE.ContractError, "只能引用.*高相关"):
            MODULE.normalize_payload(raw)

        raw = page_opportunity_payload()
        raw["action_context"]["directions"][0]["target_surfaces"].remove("official_blog")
        with self.assertRaisesRegex(MODULE.ContractError, "必须覆盖所引用页面"):
            MODULE.normalize_payload(raw)

    def test_m03_page_opportunity_task_requires_formal_page_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_root, manifest = MODULE.prepare_run(
                self.write_payload(root, page_opportunity_payload()), root / "run"
            )
            task = next(item for item in MODULE.ready_tasks(run_root, manifest) if item["module_id"] == "M03")
            self.assertIn("diagnostic:page_opportunities", task["resources"])
            self.assertEqual(task["input"]["tags"][0]["tag_id"], "storage")

            content = [
                "本地存储支持页与当前能力缺口高度相关且已被引用，可强化无需订阅和本地保存说明。"
            ]
            invalid_path = root / "M03-page-invalid.json"
            MODULE.write_json(
                invalid_path,
                result_for(task, content=content, refs={"/0": ["fact:/brand_official_pages"]}),
            )
            with self.assertRaisesRegex(MODULE.ContractError, "M03 必须引用后端正式页面机会"):
                MODULE.submit_result(run_root, task["task_id"], invalid_path)

            refs = {
                "/0": [
                    "diagnostic:page_opportunities:/items/0/url",
                    "diagnostic:page_opportunities:/items/0/relevance_status",
                    "diagnostic:page_opportunities:/items/0/citation_status",
                ]
            }
            path = root / "M03-page-result.json"
            MODULE.write_json(path, result_for(task, content=content, refs=refs))
            MODULE.submit_result(run_root, task["task_id"], path)

    def test_m06_distinguishes_geo_delivery_from_client_owned_page_changes(self):
        normalized = MODULE.normalize_payload(scoped_action_payload(non_blog=True))
        content = content_for("M06")
        content["actions"][0]["expected_impact"] = "复测目标页面引用和品牌提及是否变化"
        content["actions"][0]["action"] = (
            "我方生成官网 Blog 和第三方比较内容，并提供产品页修改建议；客户负责修改并上线产品页。"
        )
        MODULE.validate_content("M06", content, normalized)

        invalid = json.loads(json.dumps(content, ensure_ascii=False))
        invalid["actions"][0]["action"] = "我方直接修改并上线官网产品页，同时生成第三方比较内容。"
        with self.assertRaisesRegex(MODULE.ContractError, "客户负责的修改"):
            MODULE.validate_content("M06", invalid, normalized)

        invalid = json.loads(json.dumps(content, ensure_ascii=False))
        invalid["actions"][0]["action"] = "更新官网产品页，同时生成 Blog 和第三方比较内容。"
        with self.assertRaisesRegex(MODULE.ContractError, "我方负责的 Blog"):
            MODULE.validate_content("M06", invalid, normalized)

    def test_m06_requires_confirmed_internal_owner_and_client_inputs_in_copy(self):
        normalized = MODULE.normalize_payload(scoped_action_payload(internal_material=True))
        content = content_for("M06")
        content["actions"][0]["expected_impact"] = "复测目标页面引用和品牌提及是否变化"
        content["actions"][0]["action"] = (
            "产品团队向我方提供并确认集成清单与客户案例；我方生成官网 Blog 和第三方比较内容。"
        )
        MODULE.validate_content("M06", content, normalized)

        invalid = json.loads(json.dumps(content, ensure_ascii=False))
        invalid["actions"][0]["action"] = "客户提供并确认材料；我方生成官网 Blog 和第三方比较内容。"
        with self.assertRaisesRegex(MODULE.ContractError, "已确认的客户责任团队"):
            MODULE.validate_content("M06", invalid, normalized)

    def test_m06_does_not_treat_customer_case_as_client_actor(self):
        raw = scoped_action_payload(internal_material=True)
        raw["action_context"]["directions"][0]["confirmed_client_owner"] = None
        normalized = MODULE.normalize_payload(raw)
        content = content_for("M06")
        content["actions"][0]["expected_impact"] = "复测目标页面引用和品牌提及是否变化"
        content["actions"][0]["action"] = "我方生成客户案例 Blog 和第三方比较内容。"
        with self.assertRaisesRegex(MODULE.ContractError, "客户负责的修改"):
            MODULE.validate_content("M06", content, normalized)

    def test_m06_requires_declared_verification_signals_and_rejects_attribution(self):
        normalized = MODULE.normalize_payload(scoped_action_payload())
        content = content_for("M06")
        content["actions"][0]["action"] = "我方生成官网 Blog 和第三方比较内容。"
        content["actions"][0]["expected_impact"] = "复测目标页面引用和品牌提及是否变化"
        MODULE.validate_content("M06", content, normalized)

        invalid = json.loads(json.dumps(content, ensure_ascii=False))
        invalid["actions"][0]["expected_impact"] = "复测品牌提及是否变化"
        with self.assertRaisesRegex(MODULE.ContractError, "citation 复测信号"):
            MODULE.validate_content("M06", invalid, normalized)

        invalid = json.loads(json.dumps(content, ensure_ascii=False))
        invalid["actions"][0]["expected_impact"] = "提升 AI Referral Traffic 和线索归因"
        with self.assertRaisesRegex(MODULE.ContractError, "禁止表达"):
            MODULE.validate_content("M06", invalid, normalized)

    def test_rejects_invented_number(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_root, manifest = MODULE.prepare_run(self.write_payload(root, payload()), root / "run")
            task = next(item for item in MODULE.ready_tasks(run_root, manifest) if item["module_id"] == "M02")
            bad = content_for("M02")
            bad[0] = "本品提及率为99%，该数字不存在于后端事实包。"
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
            self.assertNotIn("summary_platform_consistency", dify)
            self.assertIn("summary_platform_consistency", report["modules"])
            self.assertNotIn("summary_market_perception", dify)
            self.assertIn("summary_market_perception", report["modules"])
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
                        "value": "品牌已有初步可见性，主要缺口在竞争进入与证据覆盖",
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
