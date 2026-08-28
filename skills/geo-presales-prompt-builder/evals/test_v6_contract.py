#!/usr/bin/env python3
"""Regression tests for the variable-topic, Case-field-driven v6 contract."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_question_bank.py"
SPEC = importlib.util.spec_from_file_location("validate_question_bank", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def base_config(topic_count: int = 1) -> dict:
    case_fields = {
        "公司名": "Shanghai Edgelight Industry Co., Ltd.",
        "业务 / 产品名称": "LED Display and Commercial Display Solutions",
        "品牌名称": "Edgelight",
        "业务模式": "B2B",
        "品类": "LED 显示屏制造商与商业显示解决方案提供商",
        "垂直行业": "商业 AV 零售与商业地产 企业设施 舞台与体育场馆",
        "目标客户 1": "商业 AV 集成商与 LED 显示屏分销商——关注参数 集成与服务",
        "目标客户 2": "零售 商业地产与品牌体验团队——关注视觉效果 可靠性与项目成本",
        "目标客户 3": "企业 政企园区与会议设施团队——关注清晰度 文件与维护",
        "目标客户 4": "舞台制作 体育场馆与活动技术团队——关注亮度 刷新率与结构灵活性",
        "痛点 1": "项目团队难以让像素间距 亮度 刷新率 观看距离与结构适配具体场馆",
        "痛点 2": "安装调试 文件 认证与售后缺口会延误交付并提高项目总成本",
        "使用场景 1": "在企业与商业空间安装固定式 LED 显示屏",
        "使用场景 2": "为裸眼 3D 舞台与场馆打造创意沉浸式 LED 体验",
        "产品特性 1": "室内外 固装 租赁与创意 LED 显示产品组合",
        "产品特性 2": "像素间距 亮度 刷新率 色彩与画质能力",
        "产品特性 3": "结构定制与内容控制集成",
        "产品特性 4": "项目设计 安装调试 文件 认证与售后服务",
        "差异化优势": "20 多年 LED 领域经验，五座全球生产基地，产品销往 50 多个国家并获得 100 多项国际认证",
        "适用边界": "只采购 LED 照明、驱动电源、控制器或不需要 LED 显示屏完整方案的客户",
        "主题 1（宽泛）": "LED 显示屏制造商与商业显示解决方案提供商",
        "主题 2（细分）": "面向企业与商业空间的固定安装 LED 显示解决方案",
        "主题 3（细分）": "面向裸眼 3D 舞台与场馆体验的创意沉浸式 LED 显示屏",
        "官方域名": "https://edgelight.com",
        "竞品 1": "SANSI LED (Shanghai Sansi)",
        "竞品 1 官网域名": "https://www.sansi.com",
        "竞品 2": "Unilumin",
        "竞品 2 官网域名": "https://en.unilumin.com",
        "竞品 3": "LianTronics",
        "竞品 3 官网域名": "https://www.liantronics.com",
        "补充内容": "只在 LED 显示屏制造与商业显示解决方案范围内评测，不混入 LED 电源、控制器、装饰照明、广告灯箱和物联网产品。",
    }
    for index in range(topic_count + 1, 4):
        del case_fields[f"主题 {index}（{'宽泛' if index == 1 else '细分'}）"]

    topics = [
        {
            "topic_id": f"topic_{index}",
            "topic": (
                "LED display manufacturers and commercial display solution providers"
                if index == 1
                else "fixed-installation LED display solutions for corporate and commercial spaces"
                if index == 2
                else "creative immersive LED displays for naked-eye 3D stages and venues"
            ),
            "source_field": f"主题 {index}（{'宽泛' if index == 1 else '细分'}）",
            "source_value": case_fields[f"主题 {index}（{'宽泛' if index == 1 else '细分'}）"],
        }
        for index in range(1, topic_count + 1)
    ]
    per_topic = dict(MODULE.V6_PER_TOPIC_QUOTAS)
    return {
        "case_fields": case_fields,
        "brand_name": case_fields["品牌名称"],
        "brand_object_type": "company",
        "category_label": "LED display manufacturer and commercial display solution provider",
        "official_domain": case_fields["官方域名"],
        "derived_field_sources": {
            "brand_name": "品牌名称",
            "category_label": "品类",
            "official_domain": "官方域名",
        },
        "expected_total": 20 * topic_count,
        "topics": topics,
        "quotas": {
            "diagnosis_intent": {
                intent: count * topic_count for intent, count in per_topic.items()
            },
            "per_topic": per_topic,
        },
        "competitor_selection": {
            "status": "frozen",
            "selection_count": 3,
            "formal_competitors": [
                {
                    "name": case_fields["竞品 1"],
                    "official_domain": case_fields["竞品 1 官网域名"],
                    "source_fields": ["竞品 1", "竞品 1 官网域名"],
                },
                {
                    "name": case_fields["竞品 2"],
                    "official_domain": case_fields["竞品 2 官网域名"],
                    "source_fields": ["竞品 2", "竞品 2 官网域名"],
                },
                {
                    "name": case_fields["竞品 3"],
                    "official_domain": case_fields["竞品 3 官网域名"],
                    "source_fields": ["竞品 3", "竞品 3 官网域名"],
                },
            ],
        },
    }


def valid_v6_bank(topic_count: int = 1) -> dict:
    config = base_config(topic_count)
    questions = []

    def append(topic: dict, intent: str, suffix: str, text: str, **extra) -> None:
        question_id = f"Q-{topic['topic_id']}-{suffix}"
        questions.append(
            {
                "question_id": question_id,
                "topic_id": topic["topic_id"],
                "diagnosis_intent": intent,
                "analysis_type": MODULE.V6_ANALYSIS_TYPES[intent],
                "formal_visibility_eligible": intent
                in {"discovery", "competitor", "category_awareness"},
                "intent_key": f"{topic['topic_id']}-{intent}-{suffix}",
                "user_question": text,
                "zh_translation": f"这是 {topic['topic_id']} 下的{intent}测试问题。",
                "monitoring_prompt": text,
                "quality_checks": {"reviewed": True},
                **extra,
            }
        )

    competitors = [
        item["name"].split(" (")[0]
        for item in config["competitor_selection"]["formal_competitors"]
    ]
    for topic in config["topics"]:
        topic_text = topic["topic"]
        for index in range(1, 15):
            append(
                topic,
                "discovery",
                f"D{index:02d}",
                f"Which LED display solution providers should buyers consider for {topic_text} need {index}?",
            )
        for index, competitor in enumerate(competitors, start=1):
            append(
                topic,
                "competitor",
                f"C{index:02d}",
                f"For {topic_text}, would you recommend Edgelight or {competitor}?",
            )

        selected_source_fields = ("产品特性 1", "使用场景 1", "差异化优势")
        statements = [
            f"{label} for {topic['topic_id']}"
            for label in (
                "indoor and outdoor LED display portfolio",
                "fixed LED displays for commercial spaces",
                "project installation and commissioning support",
            )
        ]
        validation_items = [
            {
                "source_field": source_field,
                "source_value": config["case_fields"][source_field],
                "statement": statement,
            }
            for source_field, statement in zip(selected_source_fields, statements)
        ]
        validation_prompt = MODULE.build_v6_validation_prompt(
            config["brand_name"], validation_items
        )
        append(
            topic,
            "verification",
            "V01",
            validation_prompt,
            validation_items=validation_items,
        )
        questions[-1]["zh_translation"] = (
            "请逐项判断以下陈述，并回答是、否或未知："
            "1. 室内外 LED 显示产品组合。"
            "2. 商业空间固定安装 LED 显示屏。"
            "3. 项目安装与调试支持。"
        )
        append(
            topic,
            "evaluation",
            "S01",
            MODULE.build_v6_sentiment_prompt(
                config["category_label"],
                config["brand_object_type"],
                config["brand_name"],
                topic_text,
            ),
        )
        append(
            topic,
            "category_awareness",
            "M01",
            MODULE.build_v6_market_perception_prompt(config["category_label"], topic_text),
        )

    return {
        "schema_version": "overseas-geo-question-bank/v6",
        "config": config,
        "questions": questions,
    }


class V6ContractTests(unittest.TestCase):
    def test_v6_selects_case_fields_directly_without_attribute_ids_and_allows_topic_reuse(self) -> None:
        data = valid_v6_bank(2)
        errors, warnings, summary = MODULE.validate(data)
        self.assertEqual([], errors)
        self.assertEqual([], warnings)
        self.assertEqual(6, summary["validation_item_count"])
        reused_sources = [
            item["source_field"]
            for row in data["questions"]
            if row["diagnosis_intent"] == "verification"
            for item in row["validation_items"]
        ]
        self.assertGreater(reused_sources.count("产品特性 1"), 1)

    def test_one_two_and_three_topic_banks_pass_with_dynamic_totals(self) -> None:
        for topic_count, expected_total in ((1, 20), (2, 40), (3, 60)):
            with self.subTest(topic_count=topic_count):
                errors, warnings, summary = MODULE.validate(valid_v6_bank(topic_count))
                self.assertEqual([], errors)
                self.assertEqual([], warnings)
                self.assertEqual(expected_total, summary["total"])
                self.assertEqual(19 * topic_count, summary["visibility_module_total"])
                self.assertEqual(18 * topic_count, summary["formal_visibility_total"])

    def test_v6_consumes_case_fields_without_legacy_target_attributes_or_topic_type(self) -> None:
        data = valid_v6_bank()
        self.assertNotIn("target_attributes", data["config"])
        self.assertTrue(all("topic_type" not in topic for topic in data["config"]["topics"]))
        self.assertTrue(all("topic_type" not in row for row in data["questions"]))
        errors, _, summary = MODULE.validate(data)
        self.assertEqual([], errors)
        self.assertEqual(3, summary["validation_item_count"])

        data["config"]["target_attributes"] = []
        data["config"]["topics"][0]["topic_type"] = "coverage"
        data["questions"][0]["metric_scopes"] = ["visibility"]
        errors, _, _ = MODULE.validate(data)
        joined = "\n".join(errors)
        self.assertIn("target_attributes is retired in v6", joined)
        self.assertIn("topic_type is retired in v6", joined)
        self.assertIn("retired v6 fields are not allowed ['metric_scopes']", joined)

    def test_v6_requires_edgelight_case_fields_and_three_to_five_validation_items_per_topic(self) -> None:
        data = valid_v6_bank()
        for field in ("痛点 1", "痛点 2"):
            del data["config"]["case_fields"][field]
        validation = next(
            row for row in data["questions"] if row["diagnosis_intent"] == "verification"
        )
        validation["validation_items"] = validation["validation_items"][:2]
        errors, _, _ = MODULE.validate(data)
        joined = "\n".join(errors)
        self.assertIn("Case fields must contain at least one 痛点 n field", joined)
        self.assertIn("validation_items must contain 3 to 5", joined)

    def test_v6_allows_blank_vertical_industry_only_for_b2c(self) -> None:
        data = valid_v6_bank()
        data["config"]["case_fields"]["业务模式"] = "B2C"
        data["config"]["case_fields"]["垂直行业"] = ""
        errors, _, _ = MODULE.validate(data)
        self.assertEqual([], errors)

        data["config"]["case_fields"]["业务模式"] = "B2B"
        errors, _, _ = MODULE.validate(data)
        self.assertTrue(any("垂直行业 must be non-empty" in error for error in errors), errors)

    def test_v6_allows_blank_supplementary_content_but_requires_the_field(self) -> None:
        data = valid_v6_bank()
        data["config"]["case_fields"]["补充内容"] = ""
        errors, _, _ = MODULE.validate(data)
        self.assertEqual([], errors)

        del data["config"]["case_fields"]["补充内容"]
        errors, _, _ = MODULE.validate(data)
        self.assertTrue(any("补充内容 must be present" in error for error in errors), errors)

    def test_v6_validation_items_trace_directly_to_case_fields(self) -> None:
        data = valid_v6_bank()
        row = next(q for q in data["questions"] if q["diagnosis_intent"] == "verification")
        item = row["validation_items"][0]
        item["source_field"] = "target_attributes"
        item["source_value"] = "invented"
        errors, _, _ = MODULE.validate(data)
        joined = "\n".join(errors)
        self.assertIn("source_field must reference an existing supported Case field", joined)

    def test_v6_validation_is_batched_and_uses_yes_no_unknown_contract(self) -> None:
        data = valid_v6_bank()
        row = next(q for q in data["questions"] if q["diagnosis_intent"] == "verification")
        row["user_question"] = "Does Edgelight support installation services?"
        row["monitoring_prompt"] = row["user_question"]
        row["validation_items"] = row["validation_items"][:2]
        errors, _, _ = MODULE.validate(data)
        joined = "\n".join(errors)
        self.assertIn("must use the batch Yes / No / Unknown template", joined)
        self.assertIn("validation_items must contain 3 to 5", joined)

        data = valid_v6_bank()
        row = next(q for q in data["questions"] if q["diagnosis_intent"] == "verification")
        row["validation_items"][0]["statement"] = "a statement missing from the Prompt"
        errors, _, _ = MODULE.validate(data)
        self.assertTrue(
            any("every validation item statement must appear" in error for error in errors),
            errors,
        )

    def test_v6_verification_translation_must_enumerate_every_validation_item(self) -> None:
        data = valid_v6_bank()
        row = next(q for q in data["questions"] if q["diagnosis_intent"] == "verification")
        row["zh_translation"] = "请判断以上三项描述是否属实，并说明依据。"
        errors, _, _ = MODULE.validate(data)
        self.assertTrue(
            any(
                "verification zh_translation must include an ordered Chinese translation"
                in error
                for error in errors
            ),
            errors,
        )

    def test_v6_enforces_analysis_mapping_sentiment_template_and_market_perception_template(self) -> None:
        data = valid_v6_bank()
        competitor = next(q for q in data["questions"] if q["diagnosis_intent"] == "competitor")
        competitor["analysis_type"] = "sentiment"
        sentiment = next(q for q in data["questions"] if q["diagnosis_intent"] == "evaluation")
        sentiment["user_question"] += " and give pros and cons"
        sentiment["monitoring_prompt"] = sentiment["user_question"]
        perception = next(q for q in data["questions"] if q["diagnosis_intent"] == "category_awareness")
        perception["user_question"] = "What criteria matter most for this topic?"
        perception["monitoring_prompt"] = perception["user_question"]
        errors, _, _ = MODULE.validate(data)
        joined = "\n".join(errors)
        self.assertIn("analysis_type must equal visibility", joined)
        self.assertIn("must equal the fixed sentiment template", joined)
        self.assertIn("must equal the category-first market perception template", joined)

    def test_v6_evaluation_rejects_topic_in_english_prompt_but_allows_chinese_translation(self) -> None:
        data = valid_v6_bank()
        evaluation = next(
            q for q in data["questions"] if q["diagnosis_intent"] == "evaluation"
        )
        evaluation["user_question"] = "Evaluate Edgelight for this topic"
        evaluation["monitoring_prompt"] = evaluation["user_question"]
        evaluation["zh_translation"] = "评价 Edgelight 在这一主题上的表现。"

        errors, _, _ = MODULE.validate(data)
        joined = "\n".join(errors)
        self.assertIn("evaluation user_question must not contain the meta word 'topic'", joined)

        data = valid_v6_bank()
        evaluation = next(
            q for q in data["questions"] if q["diagnosis_intent"] == "evaluation"
        )
        evaluation["zh_translation"] = "评价 Edgelight 在这一主题上的表现。"
        errors, _, _ = MODULE.validate(data)
        self.assertEqual([], errors)

    def test_v6_requires_three_competitor_domains_and_controlled_comparison_wording(self) -> None:
        data = valid_v6_bank()
        data["config"]["competitor_selection"]["formal_competitors"][0]["official_domain"] = ""
        competitor = [q for q in data["questions"] if q["diagnosis_intent"] == "competitor"][1]
        competitor["user_question"] = competitor["user_question"].replace("would you recommend", "how do")
        competitor["monitoring_prompt"] = competitor["user_question"]
        errors, _, _ = MODULE.validate(data)
        joined = "\n".join(errors)
        self.assertIn("official_domain must be non-empty", joined)
        self.assertIn("competitor questions must keep the same wording", joined)

    def test_v6_supports_topic_specific_competitor_sets_and_reallocates_discovery(self) -> None:
        data = valid_v6_bank(2)
        competitors = data["config"]["competitor_selection"]["formal_competitors"]
        competitors[0]["topic_ids"] = ["topic_1"]
        competitors[1]["topic_ids"] = ["topic_2"]
        competitors[2]["topic_ids"] = ["topic_2"]

        data["questions"] = [
            row
            for row in data["questions"]
            if not (
                row["diagnosis_intent"] == "competitor"
                and (
                    (row["topic_id"] == "topic_1" and row["question_id"] in {"Q-topic_1-C02", "Q-topic_1-C03"})
                    or (row["topic_id"] == "topic_2" and row["question_id"] == "Q-topic_2-C01")
                )
            )
        ]
        source = next(
            row
            for row in data["questions"]
            if row["topic_id"] == "topic_1" and row["diagnosis_intent"] == "discovery"
        )
        for topic_id, suffixes in (("topic_1", (15, 16)), ("topic_2", (15,))):
            for suffix in suffixes:
                row = dict(source)
                row["question_id"] = f"Q-{topic_id}-D{suffix:02d}"
                row["topic_id"] = topic_id
                row["intent_key"] = f"{topic_id}-discovery-D{suffix:02d}"
                row["user_question"] = (
                    "Which LED display solution providers should buyers consider for "
                    f"{topic_id} additional need {suffix}?"
                )
                row["monitoring_prompt"] = row["user_question"]
                data["questions"].append(row)

        topic_1_quota = dict(MODULE.V6_PER_TOPIC_QUOTAS)
        topic_1_quota.update({"discovery": 16, "competitor": 1})
        topic_2_quota = dict(MODULE.V6_PER_TOPIC_QUOTAS)
        topic_2_quota.update({"discovery": 15, "competitor": 2})
        data["config"]["quotas"]["topic_overrides"] = {
            "topic_1": topic_1_quota,
            "topic_2": topic_2_quota,
        }
        data["config"]["quotas"]["diagnosis_intent"] = {
            "discovery": 31,
            "competitor": 3,
            "verification": 2,
            "accuracy": 0,
            "evaluation": 2,
            "category_awareness": 2,
        }

        errors, warnings, summary = MODULE.validate(data)
        self.assertEqual([], errors)
        self.assertEqual([], warnings)
        self.assertEqual(40, summary["total"])
        self.assertEqual(
            {"SANSI LED (Shanghai Sansi)": 1},
            summary["topic_competitor_coverage"]["topic 1"],
        )
        self.assertEqual(
            {"Unilumin": 1, "LianTronics": 1},
            summary["topic_competitor_coverage"]["topic 2"],
        )

        topic_2_competitor = next(
            row
            for row in data["questions"]
            if row["topic_id"] == "topic_2" and row["diagnosis_intent"] == "competitor"
        )
        topic_2_competitor["user_question"] = topic_2_competitor["user_question"].replace(
            "Unilumin", "SANSI LED"
        )
        topic_2_competitor["monitoring_prompt"] = topic_2_competitor["user_question"]
        errors, _, _ = MODULE.validate(data)
        self.assertTrue(any("is not applicable to topic 2" in error for error in errors), errors)

    def test_v6_discovery_requires_a_concrete_candidate_request(self) -> None:
        data = valid_v6_bank()
        row = next(q for q in data["questions"] if q["diagnosis_intent"] == "discovery")
        row["user_question"] = "What is an LED display?"
        row["monitoring_prompt"] = row["user_question"]
        errors, _, _ = MODULE.validate(data)
        self.assertTrue(
            any("discovery must request concrete candidates" in error for error in errors),
            errors,
        )

    def test_v6_rejects_normalized_duplicate_question_text(self) -> None:
        data = valid_v6_bank()
        rows = [q for q in data["questions"] if q["diagnosis_intent"] == "discovery"][:2]
        rows[1]["user_question"] = rows[0]["user_question"].upper()
        rows[1]["monitoring_prompt"] = rows[1]["user_question"]
        errors, _, _ = MODULE.validate(data)
        self.assertTrue(
            any("normalized user_question values must be unique" in error for error in errors),
            errors,
        )

    def test_v6_defaults_accuracy_to_zero_without_upstream_fact_packages(self) -> None:
        data = valid_v6_bank()
        errors, warnings, summary = MODULE.validate(data)
        self.assertEqual([], errors)
        self.assertEqual([], warnings)
        self.assertEqual(0, summary["diagnosis_intent"].get("accuracy", 0))
        self.assertEqual(20, summary["total"])

    def test_v6_topic_sources_must_map_each_case_topic_exactly_once(self) -> None:
        data = valid_v6_bank(2)
        case_fields = data["config"]["case_fields"]
        del case_fields["主题 2（细分）"]
        topic = data["config"]["topics"][1]
        topic["source_field"] = "主题 1（宽泛）"
        topic["source_value"] = case_fields["主题 1（宽泛）"]
        errors, _, _ = MODULE.validate(data)
        self.assertTrue(
            any("must map each non-empty 主题 n Case field exactly once" in error for error in errors),
            errors,
        )

    def test_v6_validation_prompt_must_exactly_match_its_items(self) -> None:
        data = valid_v6_bank()
        row = next(q for q in data["questions"] if q["diagnosis_intent"] == "verification")
        row["user_question"] += " Also rank the three competitors."
        row["monitoring_prompt"] = row["user_question"]
        errors, _, _ = MODULE.validate(data)
        self.assertTrue(
            any("must exactly equal the batch Validation template" in error for error in errors),
            errors,
        )

    def test_v6_case_field_contract_rejects_unsupported_topic_and_competitor_fields(self) -> None:
        for field in ("主题 4（细分）", "主题 1", "竞品 4", "竞品 4 官网域名"):
            with self.subTest(field=field):
                data = valid_v6_bank()
                data["config"]["case_fields"][field] = "unsupported"
                errors, _, _ = MODULE.validate(data)
                self.assertTrue(
                    any("unsupported Case field" in error and field in error for error in errors),
                    errors,
                )

    def test_v6_rejects_retired_fields_at_root_config_topic_and_question_layers(self) -> None:
        data = valid_v6_bank()
        data["metric_scopes"] = []
        data["config"]["metric_scopes"] = []
        data["config"]["topics"][0]["question_type"] = "visibility"
        data["questions"][0]["attribute_ids"] = []
        errors, _, _ = MODULE.validate(data)
        joined = "\n".join(errors)
        self.assertIn("DATA retired v6 fields are not allowed ['metric_scopes']", joined)
        self.assertIn("CONFIG retired v6 fields are not allowed ['metric_scopes']", joined)
        self.assertIn("CONFIG topics[0] retired v6 fields are not allowed ['question_type']", joined)
        self.assertIn("retired v6 fields are not allowed ['attribute_ids']", joined)

    def test_v6_requires_frozen_competitor_selection(self) -> None:
        data = valid_v6_bank()
        data["config"]["competitor_selection"]["status"] = "draft"
        errors, _, _ = MODULE.validate(data)
        self.assertTrue(
            any("competitor_selection.status must equal frozen" in error for error in errors),
            errors,
        )

    def test_v6_competitor_control_variable_preserves_case_and_whitespace(self) -> None:
        for replacement in ("for ", "For  "):
            with self.subTest(replacement=replacement):
                data = valid_v6_bank()
                row = [q for q in data["questions"] if q["diagnosis_intent"] == "competitor"][1]
                row["user_question"] = row["user_question"].replace("For ", replacement, 1)
                row["monitoring_prompt"] = row["user_question"]
                errors, _, _ = MODULE.validate(data)
                self.assertTrue(
                    any("competitor questions must keep the same wording" in error for error in errors),
                    errors,
                )

    def test_v6_rejects_retired_attribute_pool_and_priority_attribute_ids(self) -> None:
        data = valid_v6_bank()
        data["config"]["attribute_pool"] = []
        data["config"]["topics"][0]["priority_attribute_ids"] = ["ATTR-1"]
        errors, _, _ = MODULE.validate(data)
        joined = "\n".join(errors)
        self.assertIn("retired v6 fields are not allowed ['attribute_pool']", joined)
        self.assertIn("retired v6 fields are not allowed ['priority_attribute_ids']", joined)

    def test_v6_accepts_an_explicit_reduced_discovery_quota(self) -> None:
        data = valid_v6_bank()
        discovery_rows = [
            row for row in data["questions"] if row["diagnosis_intent"] == "discovery"
        ]
        removed_ids = {row["question_id"] for row in discovery_rows[-6:]}
        data["questions"] = [
            row for row in data["questions"] if row["question_id"] not in removed_ids
        ]
        reduced = dict(MODULE.V6_PER_TOPIC_QUOTAS)
        reduced["discovery"] = 8
        data["config"]["expected_total"] = 14
        data["config"]["quotas"]["diagnosis_intent"] = reduced
        data["config"]["quotas"]["topic_overrides"] = {"topic_1": reduced}

        errors, warnings, summary = MODULE.validate(data)
        self.assertEqual([], errors)
        self.assertEqual([], warnings)
        self.assertEqual(14, summary["total"])

    def test_v6_rejects_an_explicit_batch_total_above_sixty(self) -> None:
        data = valid_v6_bank(3)
        source = next(
            row
            for row in data["questions"]
            if row["topic_id"] == "topic_1" and row["diagnosis_intent"] == "discovery"
        )
        for index in range(1, 2):
            row = dict(source)
            row["question_id"] = f"Q-topic_1-DX{index:02d}"
            row["intent_key"] = f"topic_1-discovery-expanded-{index:02d}"
            row["user_question"] = (
                "Which LED display solution providers should buyers consider for "
                f"expanded requirement {index}?"
            )
            row["monitoring_prompt"] = row["user_question"]
            data["questions"].append(row)

        expanded = dict(MODULE.V6_PER_TOPIC_QUOTAS)
        expanded["discovery"] = 15
        aggregate = {
            intent: count * 3 for intent, count in MODULE.V6_PER_TOPIC_QUOTAS.items()
        }
        aggregate["discovery"] = 43
        data["config"]["expected_total"] = 61
        data["config"]["quotas"]["diagnosis_intent"] = aggregate
        data["config"]["quotas"]["topic_overrides"] = {"topic_1": expanded}

        errors, _, _ = MODULE.validate(data)
        self.assertTrue(any("batch total must not exceed 60" in error for error in errors), errors)

    def test_v6_rejects_parallel_or_unknown_config_input_fields(self) -> None:
        for field in ("target_audiences", "pain_points", "use_cases", "unexpected_legacy_contract"):
            with self.subTest(field=field):
                data = valid_v6_bank()
                data["config"][field] = []
                errors, _, _ = MODULE.validate(data)
                self.assertTrue(
                    any("unsupported v6 config field" in error and field in error for error in errors),
                    errors,
                )

    def test_v6_validation_item_source_fields_reject_non_string_items_without_crashing(self) -> None:
        data = valid_v6_bank()
        row = next(q for q in data["questions"] if q["diagnosis_intent"] == "verification")
        row["validation_items"][0]["source_field"] = ["not-a-string"]
        errors, _, _ = MODULE.validate(data)
        self.assertTrue(
            any("source_field must reference an existing supported Case field" in error for error in errors),
            errors,
        )

    def test_csv_contract_uses_fixed_fields_and_english_intent_enums(self) -> None:
        validator = getattr(MODULE, "validate_v6_csv_rows", None)
        self.assertTrue(callable(validator), "CSV contract validator is missing")
        if not callable(validator):
            return

        headers = ["query", "question_zh", "topic", "diagnosis_intent", "question_types", "purchase_intent", "persona_name", "scene_name"]
        rows = [
            {"query": "Which providers should I consider?", "question_zh": "应考虑哪些供应商？", "topic": "主题", "diagnosis_intent": "discovery", "question_types": "visibility,sentiment", "purchase_intent": "", "persona_name": "", "scene_name": ""},
            {"query": "Target or Competitor?", "question_zh": "目标品牌还是竞品？", "topic": "主题", "diagnosis_intent": "competitor", "question_types": "visibility,sentiment", "purchase_intent": "", "persona_name": "", "scene_name": ""},
            {"query": "Validate the statements.", "question_zh": "验证这些描述。", "topic": "主题", "diagnosis_intent": "verification", "question_types": "visibility", "purchase_intent": "", "persona_name": "", "scene_name": ""},
            {"query": "What is the official value?", "question_zh": "官方值是什么？", "topic": "主题", "diagnosis_intent": "accuracy", "question_types": "visibility", "purchase_intent": "", "persona_name": "", "scene_name": ""},
            {"query": "Evaluate Target.", "question_zh": "评价目标品牌。", "topic": "主题", "diagnosis_intent": "evaluation", "question_types": "sentiment", "purchase_intent": "", "persona_name": "", "scene_name": ""},
            {"query": "What is this category?", "question_zh": "这是什么品类？", "topic": "主题", "diagnosis_intent": "category_awareness", "question_types": "visibility", "purchase_intent": "", "persona_name": "", "scene_name": ""},
        ]
        errors, summary = validator(headers, rows)
        self.assertEqual([], errors)
        self.assertEqual({"visibility,sentiment": 2, "visibility": 3, "sentiment": 1}, summary["question_types"])

        invalid_headers = headers + ["analysis_type"]
        invalid_rows = [dict(row, analysis_type=row["question_types"]) for row in rows]
        invalid_rows[2]["question_types"] = "verification"
        errors, _ = validator(invalid_headers, invalid_rows)
        joined = "\n".join(errors)
        self.assertIn("CSV header must exactly equal", joined)
        self.assertIn("diagnosis_intent 'verification' requires question_types 'visibility'", joined)

    def test_csv_evaluation_rejects_topic_in_query_but_allows_other_fields(self) -> None:
        validator = MODULE.validate_v6_csv_rows
        headers = [
            "query",
            "question_zh",
            "topic",
            "diagnosis_intent",
            "question_types",
            "purchase_intent",
            "persona_name",
            "scene_name",
        ]
        rows = [
            {
                "query": "How is Target regarded in this business area?",
                "question_zh": "评价目标品牌在这一主题上的表现。",
                "topic": "主题原始值",
                "diagnosis_intent": "evaluation",
                "question_types": "sentiment",
                "purchase_intent": "",
                "persona_name": "",
                "scene_name": "",
            }
        ]

        errors, _ = validator(headers, rows)
        self.assertEqual([], errors)

        rows[0]["query"] = "How is Target regarded for this topic?"
        errors, _ = validator(headers, rows)
        joined = "\n".join(errors)
        self.assertIn("evaluation query must not contain the meta word 'topic'", joined)


if __name__ == "__main__":
    unittest.main()
