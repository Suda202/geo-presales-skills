#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


PROTOCOL_VERSION = "overseas-geo-backend-report-task/v1"
PAYLOAD_VERSION = "overseas-geo-backend-report-input/v2"
LEGACY_PAYLOAD_VERSION = "overseas-geo-backend-report-input/v1"
RESULT_VERSION = "overseas-geo-backend-report-result/v1"

SUMMARY_KEYS = {
    "M01": "summary_overview",
    "M02": "summary_competitor_performance",
    "M03": "summary_citation_sources",
    "M04": "summary_brand_expression",
    "M05": "summary_category_actions",
    "M06": "summary_priority_opportunities",
    "M07": "summary_platform_consistency",
    "M08": "summary_market_perception",
    "M10": "summary_final",
}

MODULE_ORDER = {
    "M02": 20,
    "M03": 30,
    "M04": 40,
    "M05": 50,
    "M07": 55,
    "M08": 57,
    "M01": 60,
    "M06": 70,
    "M10": 80,
}
BASE_MODULES = ("M02", "M03", "M04", "M05", "M07", "M08")
RESOLVED_STATUSES = {"accepted", "degraded"}
CUSTOMER_BANNED = re.compile(
    r"P[012]|p[012]|通用题|品牌题|通用问题|品牌问题|可见度问题|情绪问题|"
    r"第\s*0\s*(?:名|位)|排名\s*(?:为|是)?\s*0(?![.\d])|平均提及位置\s*(?:为|是)?\s*0(?![.\d])|"
    r"供应商候选名单|候选供应商|进入询价名单|"
    r"自然候选|自然进入|证据承接|证据层级|实绩验证|系统级验证|RFQ|单独核实|"
    r"纯?发现型|发现问题|竞品问题|验证问题|准确性问题|评价问题|品类认知问题|"
    r"竞品比较|功能核实|准确性诊断|品牌评价|采购意图|通用选购回答|"
    r"正式结论|切片观察|题面已含品牌|题型机制|不能据此判断|该指标|只表示|不能视为|不代表|不等于|据此不能|指标含义|统计口径|筛选机制|"
    r"平均提及排名|引用占比|官网引用占比|"
    r"平均首次出现位置|首次出现位置|首次出现顺序|本批(?:次|切片观察)?|"
    r"(?i:\btopic\b)|"
    r"(?i:\battribute\b)|(?i:prompt\s*gap)|"
    r"重新选择.{0,8}竞品|竞品选择有误|真正参与竞争|"
    r"总体胜率|全(?:部)?回答胜率|(?i:overall\s+win\s+rate)|"
    r"(?i:AI\s*Referral\s*Traffic)|AI引荐流量|AI推荐流量|"
    r"(?:流量|线索|成交|收入).{0,4}(?:归因|贡献|提升|增长)|"
    r"(?:提升|增加|带来).{0,6}(?:流量|线索|成交|收入)|"
    r"(?:两|三|多个|\d+)次(?:独立)?胜利|多次独立胜利|"
    r"赋能|深度赋能|全面提升|优化升级|建议您|我们应该|严重落后|毫无建树|被动挨打"
)
ACTION_BANNED = re.compile(r"建议|应该|应当|需要|需|优先补齐|创建|新建|检查并完善|建设页面|强化内容")
ACTION_TARGET_SURFACES = {
    "official_blog",
    "third_party_source",
    "non_blog_official_page",
    "internal_material",
}
ACTION_ROUTE_TYPES = {
    "comprehension_gap",
    "trust_gap",
    "accuracy_correction",
    "objection_reframe",
    "strength_amplification",
}
ACTION_VERIFICATION_SIGNALS = {
    "visibility",
    "citation",
    "brand_expression",
    "accuracy",
}
PAGE_RELEVANCE_STATES = {"high", "low"}
PAGE_CITATION_STATES = {"cited", "uncited"}
PAGE_GAP_SEVERITIES = {"high", "medium", "low", "insufficient"}
PAGE_VALUES = {"high", "medium", "low"}
PAGE_PRIORITIES = {"high", "medium", "low", "none"}
PAGE_OPPORTUNITY_STATES = {
    ("high", "cited"): "reinforce_cited",
    ("high", "uncited"): "citation_gap",
    ("low", "cited"): "avoid_forcing",
    ("low", "uncited"): "ignore",
}
NON_BLOG_OFFICIAL_PAGE = re.compile(
    r"(?:官网)?(?:首页|主页|产品页|产品页面|解决方案页|定价页|价格页|功能页|集成页|"
    r"帮助中心|文档页|产品文档|功能文档|更新日志|服务政策页|支持页|案例页)"
)
DIRECT_PAGE_CHANGE = re.compile(r"直接|修改|更新|优化|改版|重构|发布|上线|建设|新建|维护")
ADVISORY_PAGE_WORK = re.compile(r"修改建议|修改清单|建议文案|页面建议|提供.{0,10}(?:建议|文案|清单)")
CLIENT_RESPONSIBILITY = re.compile(
    r"(?:客户(?:方|团队|相关部门|相关团队)?|企业内部|相关部门|相关团队)"
    r".{0,12}(?:负责|提供|确认|修改|更新|发布|上线|审批|审核|配合)"
)
GEO_ACTOR = re.compile(r"我方|我们|GEO团队|项目团队|服务团队")
VERIFICATION_SIGNAL_PATTERNS = {
    "visibility": re.compile(r"可见度|提及|平均提及位置"),
    "citation": re.compile(r"引用|信源|信息来源|页面.{0,8}(?:采用|被采用)"),
    "brand_expression": re.compile(r"品牌表达|品牌评价|认知|负面|异议|叙事|特点"),
    "accuracy": re.compile(r"准确|错误|事实"),
}
NUMBER_RE = re.compile(r"(?<![A-Za-z0-9_])-?\d+(?:\.\d+)?%?")
UPLOAD_CSV_FIELDS = ("module", "path", "index", "field", "value")


class ContractError(ValueError):
    pass


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path):
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path, value):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temp_name, target)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def write_upload_csv(path, rows):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=UPLOAD_CSV_FIELDS, lineterminator="\r\n")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temp_name, target)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def digest(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def file_digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            value.update(chunk)
    return "sha256:" + value.hexdigest()


def parse_json_field(value, field, expected_type):
    parsed = value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ContractError(f"{field} 不能为空")
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as error:
            raise ContractError(f"{field} 不是合法 JSON string") from error
    if not isinstance(parsed, expected_type):
        expected = "对象" if expected_type is dict else "数组"
        raise ContractError(f"{field} 必须是 JSON {expected}或对应 JSON string")
    return parsed


def collect_values(value, keys, found):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in keys and child not in (None, ""):
                found.add(str(child))
            collect_values(child, keys, found)
    elif isinstance(value, list):
        for child in value:
            collect_values(child, keys, found)


def normalize_action_context(raw):
    if raw in (None, ""):
        return {"directions": [], "source": "not_provided"}
    context = parse_json_field(raw, "action_context", dict)
    directions = context.get("directions") or []
    if not isinstance(directions, list):
        raise ContractError("action_context.directions 必须是数组")
    normalized = []
    for index, item in enumerate(directions, 1):
        if not isinstance(item, dict):
            raise ContractError("action_context.directions 项必须是对象")
        direction = str(item.get("direction") or "").strip()
        state = str(item.get("state") or "").strip()
        posture = str(item.get("posture") or "").strip()
        evidence = str(item.get("key_evidence") or item.get("evidence") or "").strip()
        template = str(item.get("action_template") or "").strip()
        if not all((direction, state, posture, evidence, template)):
            raise ContractError("每个行动方向必须提供 direction、state、posture、key_evidence 和 action_template")
        surfaces = item.get("target_surfaces")
        if surfaces is None:
            surfaces = []
        if not isinstance(surfaces, list) or any(
            not isinstance(surface, str) or surface not in ACTION_TARGET_SURFACES
            for surface in surfaces
        ) or len(surfaces) != len(set(surfaces)):
            raise ContractError("action_context.target_surfaces 必须是有效且不重复的页面/材料类型数组")
        client_inputs = item.get("client_inputs")
        if client_inputs is None:
            client_inputs = []
        if not isinstance(client_inputs, list) or any(
            not isinstance(value, str) or not value.strip() for value in client_inputs
        ):
            raise ContractError("action_context.client_inputs 必须是非空字符串数组")
        client_inputs = [value.strip() for value in client_inputs]
        page_opportunity_ids = item.get("page_opportunity_ids")
        if page_opportunity_ids is None:
            page_opportunity_ids = []
        if not isinstance(page_opportunity_ids, list) or any(
            not isinstance(value, str) or not value.strip() for value in page_opportunity_ids
        ) or len(page_opportunity_ids) != len(set(page_opportunity_ids)):
            raise ContractError("action_context.page_opportunity_ids 必须是非空且不重复的字符串数组")
        page_opportunity_ids = [value.strip() for value in page_opportunity_ids]
        route_type = str(item.get("route_type") or "").strip() or None
        if route_type is not None and route_type not in ACTION_ROUTE_TYPES:
            raise ContractError("action_context.route_type 枚举无效")
        verification_signals = item.get("verification_signals")
        if verification_signals is None:
            verification_signals = []
        if not isinstance(verification_signals, list) or any(
            not isinstance(value, str) or value not in ACTION_VERIFICATION_SIGNALS
            for value in verification_signals
        ) or len(verification_signals) != len(set(verification_signals)):
            raise ContractError("action_context.verification_signals 必须是有效且不重复的诊断信号数组")
        if route_type and not verification_signals:
            raise ContractError("正式行动路由必须提供 verification_signals")
        if verification_signals and not route_type:
            raise ContractError("提供 verification_signals 时必须同时提供 route_type")
        public_surfaces = set(surfaces) & {
            "official_blog", "third_party_source", "non_blog_official_page"
        }
        if route_type and not public_surfaces:
            raise ContractError("正式行动路由必须指向至少一个公开页面或第三方信源")
        if route_type == "trust_gap" and "third_party_source" not in surfaces:
            raise ContractError("trust_gap 必须包含 third_party_source")
        if route_type == "accuracy_correction" and "accuracy" not in verification_signals:
            raise ContractError("accuracy_correction 必须使用 accuracy 作为验证信号")
        geo_team_delivery = str(item.get("geo_team_delivery") or "").strip() or None
        client_action = str(item.get("client_action") or "").strip() or None
        confirmed_client_owner = str(item.get("confirmed_client_owner") or "").strip() or None
        if set(surfaces) & {"official_blog", "third_party_source"} and not geo_team_delivery:
            raise ContractError("Blog 或第三方内容方向必须提供 geo_team_delivery")
        if "non_blog_official_page" in surfaces and not client_action:
            raise ContractError("非 Blog 官网页面方向必须提供 client_action")
        if "internal_material" in surfaces and not client_inputs:
            raise ContractError("依赖企业内部材料的方向必须列出 client_inputs")
        normalized.append({
            **item,
            "direction_id": str(item.get("direction_id") or f"ACT-{index:03d}"),
            "direction": direction,
            "state": state,
            "posture": posture,
            "key_evidence": evidence,
            "action_template": template,
            "route_type": route_type,
            "verification_signals": verification_signals,
            "page_opportunity_ids": page_opportunity_ids,
            "target_surfaces": surfaces,
            "client_inputs": client_inputs,
            "geo_team_delivery": geo_team_delivery,
            "client_action": client_action,
            "confirmed_client_owner": confirmed_client_owner,
        })
    if len(normalized) > 3:
        raise ContractError("action_context.directions 最多三个")
    return {**context, "directions": normalized, "source": context.get("source") or "backend"}


def normalize_page_opportunities(raw):
    if raw in (None, ""):
        return {"sample_scope": None, "items": [], "source": "not_provided"}
    context = parse_json_field(raw, "page_opportunities", dict)
    sample_scope = context.get("sample_scope")
    items = context.get("items")
    if not isinstance(sample_scope, dict):
        raise ContractError("page_opportunities.sample_scope 必须是对象")
    if sample_scope.get("scan_scope") not in {
        "topic_relevant_official_pages", "topic_or_tag_relevant_official_pages"
    }:
        raise ContractError("页面机会必须扫描主题/Tag 相关官网页面，不能只使用已引用页面")
    if sample_scope.get("coverage_status") not in {"complete", "partial"}:
        raise ContractError("page_opportunities.coverage_status 必须是 complete/partial")
    included_topic_ids = sample_scope.get("included_topic_ids")
    if not isinstance(included_topic_ids, list) or not included_topic_ids or any(
        not isinstance(value, str) or not value.strip() for value in included_topic_ids
    ) or len(included_topic_ids) != len(set(included_topic_ids)):
        raise ContractError("page_opportunities.included_topic_ids 必须是非空且不重复的字符串数组")
    included_tag_ids = sample_scope.get("included_tag_ids") or []
    if not isinstance(included_tag_ids, list) or any(
        not isinstance(value, str) or not value.strip() for value in included_tag_ids
    ) or len(included_tag_ids) != len(set(included_tag_ids)):
        raise ContractError("page_opportunities.included_tag_ids 必须是不重复的字符串数组")
    candidate_page_count = sample_scope.get("candidate_page_count")
    if not isinstance(candidate_page_count, int) or isinstance(candidate_page_count, bool) or candidate_page_count < 0:
        raise ContractError("page_opportunities.candidate_page_count 必须是非负整数")
    if not isinstance(items, list) or candidate_page_count != len(items):
        raise ContractError("candidate_page_count 必须等于 page_opportunities.items 数量")
    normalized_items = []
    opportunity_ids = set()
    for item in items:
        if not isinstance(item, dict):
            raise ContractError("page_opportunities.items 每一项必须是对象")
        opportunity_id = str(item.get("page_opportunity_id") or "").strip()
        url = str(item.get("url") or "").strip()
        page_type = str(item.get("page_type") or "").strip()
        topic_id = str(item.get("topic_id") or "").strip()
        relevance = str(item.get("relevance_status") or "").strip()
        citation_status = str(item.get("citation_status") or "").strip()
        gap_severity = str(item.get("ai_gap_severity") or "").strip()
        page_value = str(item.get("page_value") or "").strip()
        opportunity_state = str(item.get("opportunity_state") or "").strip()
        priority = str(item.get("priority") or "").strip()
        finding = str(item.get("finding") or "").strip()
        if not opportunity_id or opportunity_id in opportunity_ids:
            raise ContractError("page_opportunities.page_opportunity_id 必须非空且唯一")
        if not re.fullmatch(r"https?://[^\s]+", url):
            raise ContractError("page_opportunities.url 必须是绝对 HTTP(S) URL")
        if page_type not in {"official_blog", "non_blog_official_page"}:
            raise ContractError("page_opportunities.page_type 枚举无效")
        if not topic_id:
            raise ContractError("page_opportunities.topic_id 不能为空")
        if relevance not in PAGE_RELEVANCE_STATES or citation_status not in PAGE_CITATION_STATES:
            raise ContractError("页面相关性或 Citation 状态枚举无效")
        if gap_severity not in PAGE_GAP_SEVERITIES or page_value not in PAGE_VALUES:
            raise ContractError("页面 AI Gap 严重度或页面价值枚举无效")
        expected_state = PAGE_OPPORTUNITY_STATES[(relevance, citation_status)]
        if opportunity_state != expected_state:
            raise ContractError("page_opportunities.opportunity_state 与相关性/Citation 四象限不一致")
        if priority not in PAGE_PRIORITIES:
            raise ContractError("page_opportunities.priority 枚举无效")
        if opportunity_state == "ignore" and priority != "none":
            raise ContractError("低相关且未引用页面的 priority 必须是 none")
        if opportunity_state == "avoid_forcing" and priority not in {"low", "none"}:
            raise ContractError("低相关但已引用页面不能设为中高优先级")
        if opportunity_state in {"reinforce_cited", "citation_gap"} and priority == "none":
            raise ContractError("高相关页面必须提供非 none 优先级")
        priority_score = item.get("priority_score")
        if priority_score is not None and (
            isinstance(priority_score, bool)
            or not isinstance(priority_score, (int, float))
            or not 0 <= priority_score <= 100
        ):
            raise ContractError("page_opportunities.priority_score 必须是 0..100 数值或 null")
        attribute_ids = item.get("attribute_ids") or []
        tag_ids = item.get("tag_ids") or []
        prompt_gap_ids = item.get("prompt_gap_ids") or []
        for field, values in (
            ("attribute_ids", attribute_ids), ("tag_ids", tag_ids), ("prompt_gap_ids", prompt_gap_ids)
        ):
            if not isinstance(values, list) or any(
                not isinstance(value, str) or not value.strip() for value in values
            ) or len(values) != len(set(values)):
                raise ContractError(f"page_opportunities.{field} 必须是不重复的字符串数组")
        attribute_ids = [value.strip() for value in attribute_ids]
        tag_ids = [value.strip() for value in tag_ids]
        prompt_gap_ids = [value.strip() for value in prompt_gap_ids]
        if not attribute_ids and not prompt_gap_ids:
            raise ContractError("页面机会必须关联至少一个 Attribute 或 Prompt Gap")
        citation_refs = item.get("citation_refs") or []
        if not isinstance(citation_refs, list) or any(not str(ref).strip() for ref in citation_refs):
            raise ContractError("page_opportunities.citation_refs 必须是字符串数组")
        citation_refs = [str(ref).strip() for ref in citation_refs]
        if citation_status == "cited" and not citation_refs:
            raise ContractError("已引用页面必须提供 citation_refs")
        if citation_status == "uncited" and citation_refs:
            raise ContractError("未引用页面的 citation_refs 必须为空")
        evidence_refs = item.get("evidence_refs")
        if not isinstance(evidence_refs, list) or not evidence_refs or any(
            not str(ref).strip() for ref in evidence_refs
        ):
            raise ContractError("page_opportunities.evidence_refs 必须是非空字符串数组")
        if not finding:
            raise ContractError("page_opportunities.finding 不能为空")
        normalized_items.append({
            **item,
            "page_opportunity_id": opportunity_id,
            "url": url,
            "page_type": page_type,
            "topic_id": topic_id,
            "attribute_ids": attribute_ids,
            "tag_ids": tag_ids,
            "prompt_gap_ids": prompt_gap_ids,
            "relevance_status": relevance,
            "citation_status": citation_status,
            "citation_refs": citation_refs,
            "ai_gap_severity": gap_severity,
            "page_value": page_value,
            "opportunity_state": opportunity_state,
            "priority": priority,
            "priority_score": priority_score,
            "finding": finding,
            "evidence_refs": [str(ref).strip() for ref in evidence_refs],
        })
        opportunity_ids.add(opportunity_id)
    return {
        **context,
        "sample_scope": {
            **sample_scope,
            "included_topic_ids": [value.strip() for value in included_topic_ids],
            "included_tag_ids": [value.strip() for value in included_tag_ids],
        },
        "items": normalized_items,
        "source": context.get("source") or "backend",
    }


def normalize_platform_consistency(raw):
    if raw in (None, ""):
        return {"sample_scope": None, "findings": [], "source": "not_provided"}
    context = parse_json_field(raw, "platform_consistency", dict)
    sample_scope = context.get("sample_scope")
    findings = context.get("findings")
    if not isinstance(sample_scope, dict):
        raise ContractError("platform_consistency.sample_scope 必须是对象")
    if sample_scope.get("primary_diagnostic_intent") != "discovery":
        raise ContractError("跨平台一致性主样本范围必须是 discovery")
    if sample_scope.get("comparison_unit") not in {"matched_prompts", "matched_prompt_runs"}:
        raise ContractError("跨平台一致性必须使用匹配 Prompt 样本")
    for field in ("market", "language", "collection_window"):
        if not str(sample_scope.get(field) or "").strip():
            raise ContractError(f"platform_consistency.sample_scope.{field} 不能为空")
    if not isinstance(findings, list):
        raise ContractError("platform_consistency.findings 必须是数组")
    consistency_ids = set()
    for item in findings:
        if not isinstance(item, dict):
            raise ContractError("platform_consistency.findings 每一项必须是对象")
        consistency_id = str(item.get("consistency_id") or "").strip()
        scope_type = str(item.get("scope_type") or "").strip()
        results = item.get("platform_results")
        comparable_count = item.get("comparable_platform_count")
        if not consistency_id or consistency_id in consistency_ids:
            raise ContractError("platform_consistency.consistency_id 必须非空且唯一")
        if scope_type not in {"overall", "topic"}:
            raise ContractError("platform_consistency.scope_type 必须是 overall/topic")
        if "attribute_signal_state" in item or "rank_visibility_pattern" in item:
            raise ContractError("platform_consistency 不接收 Attribute 级信号或排名—可见度状态")
        if not isinstance(results, list) or not results:
            raise ContractError("platform_consistency.platform_results 必须是非空数组")
        if not isinstance(comparable_count, int) or isinstance(comparable_count, bool) or comparable_count < 2:
            raise ContractError("platform_consistency.comparable_platform_count 至少为 2")
        platform_names = [str(result.get("platform") or "").strip() for result in results if isinstance(result, dict)]
        if len(platform_names) != len(results) or any(not name for name in platform_names) or len(platform_names) != len(set(platform_names)):
            raise ContractError("platform_consistency.platform_results 必须提供唯一平台名")
        if comparable_count != len(results):
            raise ContractError("comparable_platform_count 必须等于 platform_results 数量")
        for result in results:
            mention_rate = result.get("mention_rate")
            position = result.get("average_first_position")
            if isinstance(mention_rate, bool) or not isinstance(mention_rate, (int, float)) or not 0 <= mention_rate <= 1:
                raise ContractError("platform_results.mention_rate 必须是 0..1 数值")
            if position is not None and (
                isinstance(position, bool) or not isinstance(position, (int, float)) or position <= 0
            ):
                raise ContractError("platform_results.average_first_position 必须是正数或 null")
            if mention_rate == 0 and position is not None:
                raise ContractError("平台未提及时 average_first_position 必须是 null")
            if mention_rate > 0 and position is None:
                raise ContractError("平台有提及时必须提供 average_first_position")
        if item.get("mention_consistency") not in {"consistent_present", "consistent_absent", "mixed", "insufficient"}:
            raise ContractError("platform_consistency.mention_consistency 枚举无效")
        if item.get("position_consistency") not in {"consistent", "mixed", "not_applicable", "insufficient"}:
            raise ContractError("platform_consistency.position_consistency 枚举无效")
        if item.get("consensus_strength") not in {"strong", "moderate", "weak", "insufficient"}:
            raise ContractError("platform_consistency.consensus_strength 枚举无效")
        if item.get("mention_consistency") == "consistent_absent" and item.get("position_consistency") != "not_applicable":
            raise ContractError("所有平台均未提及时，position_consistency 必须是 not_applicable")
        evidence_refs = item.get("evidence_refs")
        if not isinstance(evidence_refs, list) or not evidence_refs or any(
            not str(ref).strip() for ref in evidence_refs
        ):
            raise ContractError("platform_consistency.findings 必须提供非空 evidence_refs")
        consistency_ids.add(consistency_id)
    return {**context, "findings": findings, "source": context.get("source") or "backend"}


def rate_matches_count(rate, count, denominator):
    if denominator == 0:
        return rate is None
    return (
        isinstance(rate, (int, float))
        and not isinstance(rate, bool)
        and abs(rate - count / denominator) <= 0.0001
    )


def normalize_competitor_comparison_summary(raw):
    if raw in (None, ""):
        return {"sample_scope": None, "pairs": [], "source": "not_provided"}
    context = parse_json_field(raw, "competitor_comparison_summary", dict)
    if any("overall" in str(key).lower() and "win" in str(key).lower() for key in context):
        raise ContractError("竞品汇总只保留决胜回答胜率，不接收总体胜率字段")
    sample_scope = context.get("sample_scope")
    pairs = context.get("pairs")
    if not isinstance(sample_scope, dict) or sample_scope.get("primary_diagnostic_intent") != "competitor":
        raise ContractError("竞品胜率主样本范围必须是 competitor")
    if not isinstance(pairs, list):
        raise ContractError("competitor_comparison_summary.pairs 必须是数组")
    comparison_ids = set()
    competitor_names = set()
    theme_ids = set()
    for pair in pairs:
        if not isinstance(pair, dict):
            raise ContractError("competitor_comparison_summary.pairs 每一项必须是对象")
        comparison_id = str(pair.get("comparison_id") or "").strip()
        competitor_name = str(pair.get("competitor_name") or "").strip()
        if (
            not comparison_id
            or comparison_id in comparison_ids
            or not competitor_name
            or competitor_name in competitor_names
        ):
            raise ContractError("竞品汇总必须提供唯一 comparison_id 和唯一非空 competitor_name")
        if any("overall" in str(key).lower() and "win" in str(key).lower() for key in pair):
            raise ContractError("竞品汇总只保留决胜回答胜率，不接收总体胜率字段")
        counts = {}
        for field in ("total_valid_answers", "decisive_answers", "target_wins", "competitor_wins", "ties", "unclear"):
            value = pair.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ContractError(f"competitor_comparison_summary.{field} 必须是非负整数")
            counts[field] = value
        if counts["total_valid_answers"] != sum(
            counts[field] for field in ("target_wins", "competitor_wins", "ties", "unclear")
        ):
            raise ContractError("竞品胜负计数之和必须等于 total_valid_answers")
        if counts["decisive_answers"] != counts["target_wins"] + counts["competitor_wins"]:
            raise ContractError("decisive_answers 必须等于双方明确胜出数之和")
        if "target_decisive_win_rate" not in pair:
            raise ContractError("竞品汇总必须显式提供 target_decisive_win_rate；无决胜回答时写 null")
        rate = pair.get("target_decisive_win_rate")
        if rate is not None and (
            isinstance(rate, bool) or not isinstance(rate, (int, float)) or not 0 <= rate <= 1
        ):
            raise ContractError("target_decisive_win_rate 必须是 0..1 数值或 null")
        if not rate_matches_count(rate, counts["target_wins"], counts["decisive_answers"]):
            raise ContractError("target_decisive_win_rate 与决胜回答计数不一致")
        for group in ("advantage_themes", "disadvantage_themes"):
            themes = pair.get(group)
            if not isinstance(themes, list):
                raise ContractError(f"competitor_comparison_summary.{group} 必须是数组")
            for theme in themes:
                if not isinstance(theme, dict):
                    raise ContractError(f"competitor_comparison_summary.{group} 每一项必须是对象")
                theme_id = str(theme.get("theme_id") or "").strip()
                dimension = str(theme.get("dimension") or "").strip()
                finding = str(theme.get("finding") or "").strip()
                support_count = theme.get("support_count")
                evidence_refs = theme.get("evidence_refs")
                if not theme_id or theme_id in theme_ids or not dimension or not finding:
                    raise ContractError("竞品优劣势主题必须提供唯一 theme_id、dimension 和 finding")
                if not isinstance(support_count, int) or isinstance(support_count, bool) or support_count < 1:
                    raise ContractError("竞品优劣势 support_count 必须是正整数")
                if not isinstance(evidence_refs, list) or not evidence_refs or any(
                    not str(ref).strip() for ref in evidence_refs
                ):
                    raise ContractError("竞品优劣势必须提供非空 evidence_refs")
                if support_count > len(set(str(ref).strip() for ref in evidence_refs)):
                    raise ContractError("竞品优劣势 support_count 不能超过唯一证据引用数")
                theme_ids.add(theme_id)
        comparison_ids.add(comparison_id)
        competitor_names.add(competitor_name)
    return {**context, "pairs": pairs, "source": context.get("source") or "backend"}


def normalize_market_perception_diagnostics(raw):
    if raw in (None, ""):
        return {"sample_scope": None, "findings": [], "source": "not_provided"}
    context = parse_json_field(raw, "market_perception_diagnostics", dict)
    sample_scope = context.get("sample_scope")
    findings = context.get("findings")
    if not isinstance(sample_scope, dict) or sample_scope.get("primary_diagnostic_intent") != "market_perception":
        raise ContractError("品类认知主样本范围必须是 market_perception")
    if not isinstance(findings, list):
        raise ContractError("market_perception_diagnostics.findings 必须是数组")
    finding_ids = set()
    for item in findings:
        if not isinstance(item, dict):
            raise ContractError("market_perception_diagnostics.findings 每一项必须是对象")
        finding_id = str(item.get("finding_id") or "").strip()
        topic_id = str(item.get("topic_id") or "").strip()
        attribute_id = str(item.get("attribute_id") or "").strip()
        status = item.get("alignment_status")
        intended = str(item.get("intended_differentiator") or "").strip()
        finding = str(item.get("finding") or "").strip()
        support_count = item.get("support_count")
        evidence_refs = item.get("evidence_refs")
        criteria = item.get("market_criteria")
        if not finding_id or finding_id in finding_ids or not topic_id or not attribute_id:
            raise ContractError("品类认知诊断必须提供唯一 finding_id、topic_id 和 attribute_id")
        if status not in {"included", "missing", "conflicting", "insufficient"}:
            raise ContractError("market_perception_diagnostics.alignment_status 枚举无效")
        if not intended or not finding:
            raise ContractError("品类认知诊断必须提供 intended_differentiator 和 finding")
        if not isinstance(criteria, list) or any(not str(value).strip() for value in criteria):
            raise ContractError("market_perception_diagnostics.market_criteria 必须是字符串数组")
        if not isinstance(support_count, int) or isinstance(support_count, bool) or support_count < 0:
            raise ContractError("品类认知诊断 support_count 必须是非负整数")
        if status != "insufficient" and support_count < 1:
            raise ContractError("非 insufficient 品类认知诊断必须有支持样本")
        if not isinstance(evidence_refs, list) or (status != "insufficient" and not evidence_refs):
            raise ContractError("非 insufficient 品类认知诊断必须提供 evidence_refs")
        if status != "insufficient" and not criteria:
            raise ContractError("非 insufficient 品类认知诊断必须提供 market_criteria")
        if any(not str(ref).strip() for ref in evidence_refs):
            raise ContractError("market_perception_diagnostics.evidence_refs 不能包含空值")
        if support_count > len(set(str(ref).strip() for ref in evidence_refs)):
            raise ContractError("品类认知 support_count 不能超过唯一证据引用数")
        finding_ids.add(finding_id)
    return {**context, "findings": findings, "source": context.get("source") or "backend"}


def has_material_platform_consistency(payload):
    return any(
        item.get("mention_consistency") != "insufficient"
        for item in payload.get("platform_consistency", {}).get("findings", [])
    )


def has_material_competitor_comparison(payload):
    return bool(payload.get("competitor_comparison_summary", {}).get("pairs", []))


def has_material_market_perception(payload):
    return any(
        item.get("alignment_status") != "insufficient"
        for item in payload.get("market_perception_diagnostics", {}).get("findings", [])
    )


def has_material_page_opportunities(payload):
    return any(
        item.get("relevance_status") == "high" and item.get("priority") != "none"
        for item in payload.get("page_opportunities", {}).get("items", [])
    )


def rate_tokens(rate):
    percent = rate * 100
    values = {
        f"{rate:g}",
        f"{percent:g}",
        f"{percent:g}%",
        f"{percent:.1f}".rstrip("0").rstrip("."),
        f"{percent:.1f}".rstrip("0").rstrip(".") + "%",
        f"{percent:.2f}".rstrip("0").rstrip("."),
        f"{percent:.2f}".rstrip("0").rstrip(".") + "%",
    }
    return values


def normalize_v2_context(raw):
    topics = parse_json_field(raw.get("topics"), "topics", list)
    if len(topics) != 3:
        raise ContractError("topics 必须恰好包含三个主题对象")
    topic_ids = set()
    for item in topics:
        if not isinstance(item, dict):
            raise ContractError("topics 每一项必须是对象")
        topic_id = str(item.get("topic_id") or "").strip()
        topic_type = str(item.get("topic_type") or "").strip()
        topic = str(item.get("topic") or "").strip()
        if not topic_id or topic_id in topic_ids or topic_type not in {"coverage", "depth"} or not topic:
            raise ContractError("topics 必须提供唯一 topic_id、coverage/depth 类型和非空 topic")
        topic_ids.add(topic_id)

    tags = parse_json_field(raw.get("tags") or [], "tags", list)
    tag_ids = set()
    tag_topics = {}
    normalized_tags = []
    for item in tags:
        if not isinstance(item, dict):
            raise ContractError("tags 每一项必须是对象")
        tag_id = str(item.get("tag_id") or "").strip()
        tag = str(item.get("tag") or "").strip()
        mapped_topics = item.get("topic_ids") or []
        if not tag_id or tag_id in tag_ids or not tag:
            raise ContractError("tags 必须提供唯一 tag_id 和非空 tag")
        if not isinstance(mapped_topics, list) or not mapped_topics or any(
            not isinstance(value, str) or not value.strip() for value in mapped_topics
        ) or len(mapped_topics) != len(set(mapped_topics)) or set(mapped_topics) - topic_ids:
            raise ContractError("tags.topic_ids 必须引用至少一个已有主题对象")
        mapped_topics = [value.strip() for value in mapped_topics]
        normalized_tags.append({**item, "tag_id": tag_id, "tag": tag, "topic_ids": mapped_topics})
        tag_ids.add(tag_id)
        tag_topics[tag_id] = set(mapped_topics)

    target_attributes = parse_json_field(raw.get("target_attributes"), "target_attributes", list)
    if not target_attributes:
        raise ContractError("target_attributes 至少包含一个目标属性")
    attribute_ids = set()
    normalized_target_attributes = []
    for item in target_attributes:
        if not isinstance(item, dict):
            raise ContractError("target_attributes 每一项必须是对象")
        attribute_id = str(item.get("attribute_id") or "").strip()
        mapped_topics = item.get("topic_ids") or []
        mapped_tags = item.get("tag_ids") or []
        if not attribute_id or attribute_id in attribute_ids:
            raise ContractError("target_attributes.attribute_id 必须非空且唯一")
        if not isinstance(mapped_topics, list) or any(
            not isinstance(value, str) or not value.strip() for value in mapped_topics
        ) or len(mapped_topics) != len(set(mapped_topics)) or set(mapped_topics) - topic_ids:
            raise ContractError("target_attributes.topic_ids 必须引用已有主题对象")
        if not isinstance(mapped_tags, list) or any(
            not isinstance(value, str) or not value.strip() for value in mapped_tags
        ) or len(mapped_tags) != len(set(mapped_tags)) or set(mapped_tags) - tag_ids:
            raise ContractError("target_attributes.tag_ids 必须引用已有 Tag")
        if not mapped_topics and not mapped_tags:
            raise ContractError("target_attributes 必须通过主题或 Tag 承载")
        mapped_topics = [value.strip() for value in mapped_topics]
        mapped_tags = [value.strip() for value in mapped_tags]
        normalized_target_attributes.append({
            **item,
            "attribute_id": attribute_id,
            "topic_ids": mapped_topics,
            "tag_ids": mapped_tags,
        })
        attribute_ids.add(attribute_id)

    attribute_diagnostics = parse_json_field(raw.get("attribute_diagnostics"), "attribute_diagnostics", list)
    for item in attribute_diagnostics:
        if not isinstance(item, dict) or str(item.get("attribute_id") or "") not in attribute_ids:
            raise ContractError("attribute_diagnostics 必须引用已有 target_attributes.attribute_id")
    comparison_outcomes = parse_json_field(raw.get("comparison_outcomes"), "comparison_outcomes", list)
    outcome_competitors = set()
    for item in comparison_outcomes:
        if not isinstance(item, dict) or item.get("outcome") not in {"target_wins", "competitor_wins", "tie", "unclear"}:
            raise ContractError("comparison_outcomes.outcome 必须是 target_wins/competitor_wins/tie/unclear")
        competitor_name = str(item.get("competitor") or "").strip()
        target_brand = str(item.get("target_brand") or "").strip()
        if not competitor_name or not target_brand:
            raise ContractError("comparison_outcomes 必须提供 target_brand 和 competitor")
        outcome_competitors.add(competitor_name)
    competitor_comparison_summary = normalize_competitor_comparison_summary(
        raw.get("competitor_comparison_summary")
    )
    if competitor_comparison_summary["pairs"]:
        summary_competitors = {str(item["competitor_name"]).strip() for item in competitor_comparison_summary["pairs"]}
        if summary_competitors != outcome_competitors:
            raise ContractError("竞品胜率汇总必须逐一对应 comparison_outcomes 中的正式竞品")
    market_perception = parse_json_field(raw.get("market_perception"), "market_perception", list)
    market_perception_diagnostics = normalize_market_perception_diagnostics(
        raw.get("market_perception_diagnostics")
    )
    attribute_topics = {
        str(item["attribute_id"]): (
            set(item["topic_ids"]) | set().union(*(tag_topics[tag_id] for tag_id in item["tag_ids"]))
        )
        for item in normalized_target_attributes
    }
    for item in market_perception_diagnostics["findings"]:
        topic_id = str(item["topic_id"])
        attribute_id = str(item["attribute_id"])
        if topic_id not in topic_ids:
            raise ContractError("market_perception_diagnostics.topic_id 必须引用已有主题对象")
        if attribute_id not in attribute_ids:
            raise ContractError("market_perception_diagnostics.attribute_id 必须引用已有 Attribute")
        if topic_id not in attribute_topics[attribute_id]:
            raise ContractError("品类认知诊断的主题必须属于该 Attribute 的预设映射")
    accuracy_findings = parse_json_field(raw.get("accuracy_findings"), "accuracy_findings", list)
    platform_consistency = normalize_platform_consistency(raw.get("platform_consistency"))
    for item in platform_consistency["findings"]:
        scope_id = str(item.get("scope_id") or "").strip()
        if not scope_id:
            raise ContractError("platform_consistency.scope_id 不能为空")
        if item["scope_type"] == "overall" and scope_id != "overall":
            raise ContractError("platform_consistency 的 overall scope_id 必须是 overall")
        if item["scope_type"] == "topic" and scope_id not in topic_ids:
            raise ContractError("platform_consistency 的 topic scope_id 必须引用已有主题对象")
    citation = parse_json_field(raw.get("citation"), "citation", dict)
    sample_scope = citation.get("sample_scope")
    if not isinstance(sample_scope, dict) or sample_scope.get("primary_diagnostic_intent") != "discovery":
        raise ContractError("引用主样本范围必须是 discovery")
    page_opportunities = normalize_page_opportunities(raw.get("page_opportunities"))
    page_scope = page_opportunities.get("sample_scope")
    if page_scope:
        included_topics = set(page_scope["included_topic_ids"])
        included_tags = set(page_scope["included_tag_ids"])
        if included_topics - topic_ids:
            raise ContractError("page_opportunities.included_topic_ids 必须引用已有主题对象")
        if included_tags - tag_ids:
            raise ContractError("page_opportunities.included_tag_ids 必须引用已有 Tag")
        for item in page_opportunities["items"]:
            topic_id = item["topic_id"]
            if topic_id not in included_topics:
                raise ContractError("页面机会 topic_id 必须属于官网扫描的主题范围")
            for attribute_id in item["attribute_ids"]:
                if attribute_id not in attribute_ids:
                    raise ContractError("页面机会 attribute_ids 必须引用已有 Attribute")
                if topic_id not in attribute_topics[attribute_id]:
                    raise ContractError("页面机会 Attribute 必须属于该页面主题的预设映射")
            if set(item["tag_ids"]) - included_tags:
                raise ContractError("页面机会 tag_ids 必须属于本次官网扫描 Tag 范围")
            for tag_id in item["tag_ids"]:
                if topic_id not in tag_topics[tag_id]:
                    raise ContractError("页面机会 Tag 必须映射到该页面主题")
    return {
        "topics": topics,
        "tags": normalized_tags,
        "target_attributes": normalized_target_attributes,
        "attribute_diagnostics": attribute_diagnostics,
        "comparison_outcomes": comparison_outcomes,
        "competitor_comparison_summary": competitor_comparison_summary,
        "market_perception": market_perception,
        "market_perception_diagnostics": market_perception_diagnostics,
        "accuracy_findings": accuracy_findings,
        "platform_consistency": platform_consistency,
        "citation": citation,
        "page_opportunities": page_opportunities,
    }


def normalize_payload(raw):
    input_version = str(raw.get("schema_version") or LEGACY_PAYLOAD_VERSION).strip()
    is_v2 = input_version == PAYLOAD_VERSION
    if input_version not in {LEGACY_PAYLOAD_VERSION, PAYLOAD_VERSION}:
        raise ContractError(f"不支持的 schema_version：{input_version}")
    required_text = ("brand_name", "corp_name", "market", "language", "task_id")
    if not is_v2:
        required_text += ("core_topic",)
    common = {}
    for field in required_text:
        value = str(raw.get(field) or "").strip()
        if not value:
            raise ContractError(f"缺少必填字段 {field}")
        common[field] = value
    common["product_name"] = str(raw.get("product_name") or "").strip() or None

    v2_context = normalize_v2_context(raw) if is_v2 else {
        "topics": [],
        "tags": [],
        "target_attributes": [],
        "attribute_diagnostics": [],
        "comparison_outcomes": [],
        "competitor_comparison_summary": normalize_competitor_comparison_summary(
            raw.get("competitor_comparison_summary")
        ),
        "market_perception": [],
        "market_perception_diagnostics": normalize_market_perception_diagnostics(
            raw.get("market_perception_diagnostics")
        ),
        "accuracy_findings": [],
        "platform_consistency": normalize_platform_consistency(raw.get("platform_consistency")),
        "citation": parse_json_field(raw.get("citation"), "citation", dict),
        "page_opportunities": normalize_page_opportunities(raw.get("page_opportunities")),
    }
    if is_v2:
        common["core_topic"] = " / ".join(item["topic"] for item in v2_context["topics"])
    platform_scope = v2_context["platform_consistency"].get("sample_scope")
    if platform_scope and (
        str(platform_scope.get("market")) != common["market"]
        or str(platform_scope.get("language")) != common["language"]
    ):
        raise ContractError("platform_consistency 的 market/language 必须与报告批次一致")

    normalized = {
        "schema_version": input_version,
        **common,
        "overview": parse_json_field(raw.get("overview"), "overview", dict),
        "competitor": parse_json_field(raw.get("competitor"), "competitor", dict),
        "citation": v2_context["citation"],
        "brand_expression": parse_json_field(raw.get("brand_expression"), "brand_expression", list),
        "category_actions": parse_json_field(raw.get("category_actions"), "category_actions", dict),
        "question_details": parse_json_field(raw.get("question_details"), "question_details", list),
        "topics": v2_context["topics"],
        "tags": v2_context["tags"],
        "target_attributes": v2_context["target_attributes"],
        "attribute_diagnostics": v2_context["attribute_diagnostics"],
        "comparison_outcomes": v2_context["comparison_outcomes"],
        "competitor_comparison_summary": v2_context["competitor_comparison_summary"],
        "market_perception": v2_context["market_perception"],
        "market_perception_diagnostics": v2_context["market_perception_diagnostics"],
        "accuracy_findings": v2_context["accuracy_findings"],
        "platform_consistency": v2_context["platform_consistency"],
        "page_opportunities": v2_context["page_opportunities"],
    }

    for index, item in enumerate(normalized["brand_expression"], 1):
        if not isinstance(item, dict):
            raise ContractError("brand_expression 每一项必须是对象")
        item.setdefault("evidence_id", f"BE-{index:03d}")
    evidence_ids = [str(item["evidence_id"]) for item in normalized["brand_expression"]]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ContractError("brand_expression.evidence_id 必须唯一")

    action_raw = raw.get("action_context")
    if action_raw in (None, ""):
        action_raw = normalized["overview"].get("action_context")
    if action_raw in (None, ""):
        action_raw = normalized["category_actions"].get("action_context")
    normalized["action_context"] = normalize_action_context(action_raw)
    page_opportunity_map = {
        item["page_opportunity_id"]: item
        for item in normalized["page_opportunities"]["items"]
    }
    for direction in normalized["action_context"]["directions"]:
        for opportunity_id in direction["page_opportunity_ids"]:
            if opportunity_id not in page_opportunity_map:
                raise ContractError("action_context.page_opportunity_ids 必须引用已有页面机会")
            page = page_opportunity_map[opportunity_id]
            if page["relevance_status"] != "high":
                raise ContractError("行动只能引用与当前主题/Attribute 高相关的页面机会")
            expected_surface = page["page_type"]
            if expected_surface not in direction["target_surfaces"]:
                raise ContractError("行动 target_surfaces 必须覆盖所引用页面的页面类型")

    nested_task_ids = set()
    collect_values(normalized, {"task_id"}, nested_task_ids)
    if nested_task_ids and nested_task_ids != {common["task_id"]}:
        raise ContractError("后端统计包内存在与顶层 task_id 不一致的数据")

    batch_ids = set()
    collect_values(normalized, {"batch_id", "report_batch_id"}, batch_ids)
    explicit_batch = str(raw.get("batch_id") or "").strip()
    if explicit_batch:
        batch_ids.add(explicit_batch)
    if len(batch_ids) > 1:
        raise ContractError("后端统计包混入多个 batch_id")
    normalized["batch_id"] = next(iter(batch_ids), common["task_id"])
    normalized["input_hash"] = digest(normalized)
    return normalized


def manifest_path(root):
    return root / "manifest.json"


def load_run(run_dir):
    root = Path(run_dir).expanduser().resolve()
    if not manifest_path(root).exists():
        raise ContractError(f"运行目录不存在或未初始化：{root}")
    return root, read_json(manifest_path(root))


def save_manifest(root, manifest):
    manifest["updated_at"] = now_iso()
    write_json(manifest_path(root), manifest)


def module_result_path(module_id):
    return f"results/{module_id}.accepted.json"


def module_resolved(manifest, module_id):
    return (manifest.get("modules", {}).get(module_id) or {}).get("status") in RESOLVED_STATUSES


def primary_fact_path(module_id):
    return {
        "M01": "canonical/overview.json",
        "M02": "canonical/competitor.json",
        "M03": "canonical/citation.json",
        "M04": "canonical/brand_expression.json",
        "M05": "canonical/category_actions.json",
        "M06": "canonical/action_context.json",
        "M07": "canonical/platform_consistency.json",
        "M08": "canonical/market_perception_diagnostics.json",
    }.get(module_id)


def diagnostic_fact_paths(module_id):
    return {
        "M02": ("comparison_outcomes", "competitor_comparison_summary"),
        "M03": ("page_opportunities",),
        "M04": ("attribute_diagnostics",),
        "M05": ("accuracy_findings",),
        "M01": ("attribute_diagnostics", "comparison_outcomes", "accuracy_findings"),
        "M06": ("page_opportunities",),
        "M07": (),
        "M08": (),
        "M10": (),
    }.get(module_id, ())


def module_dependencies(module_id):
    return {
        "M01": ["M02", "M03", "M04", "M05", "M07", "M08"],
        "M02": [],
        "M03": [],
        "M04": [],
        "M05": [],
        "M06": ["M02", "M03", "M04", "M05", "M07", "M08"],
        "M07": [],
        "M08": [],
        "M10": ["M01", "M02", "M03", "M04", "M05", "M06", "M07", "M08"],
    }[module_id]


def output_contract(module_id):
    return {
        "M01": {"content": {"title": "string", "points": "string[3..5]", "conclusion": "string"}},
        "M02": {"content": "string[1..6]，同时覆盖发现类问题中的竞争位置和后端正式竞品的决胜回答胜率、正面对比优劣势"},
        "M03": {"content": "string[1..4]，合并重复事实，只保留来源结构、官网采用情况、正式页面机会或明确边界"},
        "M04": {"content": {"positive_evidence": "{keyword,explain}[0..5]", "risk_evidence": "{keyword,explain}[0..5]", "analysis_items": "string[1..3]"}},
        "M05": {"content": {"p0": "string", "p1": "string", "p2": "string"}},
        "M06": {"content": {"summary": "string", "actions": "{direction_id,source_module,title,evidence,action,expected_impact}[]"}},
        "M07": {"content": "string[1..5]，解释后端已确认的整体/主题跨平台一致、分歧或证据不足"},
        "M08": {"content": "string[1..5]，解释后端已确认的购买框架对预设差异点的 included/missing/conflicting/insufficient 状态"},
        "M10": {"content": {"title": "string", "summary": "string", "points": "string[3..5]", "conclusion": "string"}},
    }[module_id]


def module_purpose(module_id):
    return {
        "M01": "综合 overview 与 M02-M05、M07-M08 已定稿结论，先区分整体与六类诊断意图，再选出互不重复的整体、主题、平台、引用和跨维度判断，不引入新事实。",
        "M02": "用 Discovery 指标判断品牌进入与位置状态；用 Competitor 后端汇总说明每个正式竞品的决胜回答胜率及明确正面对比优劣势。",
        "M03": "用来源类型、官网引用和全站候选页面证据判断来源主导权、官网可发现性、页面机会与第三方承接；主题定范围，具体能力/问题缺口定修改目标。",
        "M04": "用本品表达证据及支持强度判断已被识别的差异点、购买顾虑和信任风险。",
        "M05": "解释后端已分档问题覆盖的需求和阶段，判断缺口是单点还是广泛存在；不重新分档或输出行动。",
        "M06": "只把后端给出的行动路由写成客户可读行动，并区分我方可直接交付、我方建议与客户执行，写清复测信号，不重新判状态或新增方向。",
        "M07": "用后端已确认的匹配 Prompt 样本判断整体和主题的品牌提及与平均提及位置是否跨平台稳定，并保留样本与因果边界。",
        "M08": "用后端正式品类认知诊断判断主题下的市场选择标准是否覆盖问题关键属性、是否与品牌预设差异点契合；不改写成品牌可见度或输赢原因。",
        "M10": "综合已定稿模块形成最终摘要，保留主诊断与优先级，不引入新事实或重复所有模块。",
    }[module_id]


def module_synthesis_rules(module_id):
    return {
        "M01": [
            "先把整体指标拆到发现、竞品、验证、准确性、评价、品类认知六类诊断意图；整体提及率包含其他意图时，不得直接称为发现表现。客户文案只使用这六个名称，不另造纯发现型等口径。",
            "后端提供同口径全品牌提及率排名时，核心标题或结论与可见度总结都要写明提及率排名第 x/N 及相对竞品位置；不得用平均提及位置代替。",
            "再从 M02 判断发现中的缺席、位置和竞品中的正式比较结果，用 M03-M05 解释引用、验证、评价和需求缺口，用 M07 判断跨平台稳定性，并用 M08 判断品类认知中的选择框架是否包含关键差异点。",
            "三至五条要点应检查整体、主题、平台共同与差异、诊断意图、引用结构和跨维度张力；按实际证据取舍，不得重复同一组数字或为完整感补句子。",
            "至少形成一个有多模块证据的关系判断；证据不足时保持模块独立，不强行建立因果。",
            "不同数据维度都是分析结论，不人为区分正式结论与切片观察；仍须保留样本范围，不外推全网、不猜机制。",
            "M07 出现实质性跨平台一致或分歧且会改变结论可信度、问题范围或优先级时，至少保留一条；只有证据不足或与更重要判断完全重复时才省略。",
            "M08 出现实质性 included、missing 或 conflicting 且会改变差异化判断或优先级时，至少保留一条；不得写成可见度或确定输赢原因。",
        ],
        "M02": [
            "先判断是否获得提及；提及为零时平均提及位置写为短横线，只能判断缺席。",
            "已有提及时才讨论平均提及位置；它是正文首次合格出现位置的平均值，不是按提及率比较的提及率排名，也不是模型对品牌优劣的语义排序。",
            "后端提供提及率排名时，可见度总结必须写明第 x/N 及相对竞品位置，不得只报提及率或平均提及位置。",
            "提及、声量和平均提及位置只使用后端已确认的发现类问题样本；竞品类问题的比较结果单独表述胜者、平局和强度。",
            "声量占比只代表冻结的目标品牌与正式竞品集合，不得解释为全市场份额。",
            "目标品牌和客户提供的竞品均未被提及时，只能写当前数据无法比较相对表现；不要据此判断竞品选择有误，也不得建议替换客户提供的竞品。",
            "现有证据无法区分问题覆盖不足与这些品牌在回答中出现较少时，必须保留两种可能，不得自行选择原因。",
            "每个正式竞品只把 target_wins / (target_wins + competitor_wins) 称为竞品胜率；平局和无法判断不进入分母，无决胜回答时只能写当前无法计算胜率。",
            "不得生成或表述总体胜率；决胜回答数、双方胜场、平局和无法判断计数用于说明胜率分母与样本边界。",
            "优势和劣势只使用 competitor_comparison_summary 中有支持样本和证据引用的明确正面对比主题，不得混入情绪、Discovery 提及率或品牌常识。",
            "竞品类问题的结论只使用后端提供的决胜结果、竞争层级、比较维度和证据主题；题面已经包含品牌所带来的必然提及或排名不写入客户文案。",
        ],
        "M03": [
            "先确认引用主样本是 Discovery，再依次判断来源主导权、官网可发现性、证据页面层级和第三方承接。",
            "页面机会只使用后端 page_opportunities；候选范围必须来自主题/Tag 相关官网页面扫描，而不是已引用页面子集。主题/Tag 负责定范围，内部 Attribute/Prompt Gap 只指导具体改什么，不作为客户可见一等字段。",
            "页面相关性与 Citation 状态必须分开：高相关且已引用可强化对应能力表达；高相关且未引用是 Citation Gap；低相关但已引用一般不为当前主题硬改；低相关且未引用忽略。",
            "最终顺序服从后端综合的 AI Gap 严重度、Citation 状态、页面价值与 priority；报告侧不手算分数，也不得因页面已引用就自动判为最高优先级。",
            "官网已有引用时不得写不可抓取；存在性页面与产品、证书、政策、案例等决策页面要分开。",
            "引用与可见度同时存在只能写有限关系，不得写引用导致或没有转化为推荐。",
            "来源名称和细分程度必须服从后端分类；标为其他来源时不得自行猜测具体来源，企业网站只在证据能区分非监测对象官网时这样写。",
        ],
        "M04": [
            "评价直接使用完整 analysis_type=sentiment 数据，不得再按 diagnostic_intent、Discovery/Evaluation 或其他意图筛选。如后端提供验证的 Attribute 诊断，按 Strength、Opportunity、Objection 区分，不把 target_attributes 直接写成已形成认知。客户文案统一称评价和验证，不混用品牌评价、功能核实等旧称。",
            "将被认可的特点和阻碍购买的风险分开，寻找二者之间是否存在证据张力。",
            "表达强度必须匹配支持样本；单条证据不得写成高频、普遍或共识。",
            "只使用明确比较证据解释竞品优势，不用品牌常识补写。",
            "评价问题本身会提及目标品牌；正向评价只能说明品牌印象和可识别特点，不能证明品牌在发现中被提及或已经进入真实采购流程。",
            "风险必须说明具体对象、适用场景和缺少的材料；只有需核实、门槛更高等泛化提醒应删除。",
            "不要用公开资料不能替代真实表现这类免责声明；改写为采购判断仍缺少的具体材料，如适用主体、证书范围、质量或服务数据、交付记录、政策说明或客户案例。",
        ],
        "M05": [
            "P0 解释尚未进入哪些需求，P1 解释进入后哪些位置仍落后，P2 解释哪些主题值得保持。",
            "结合后端已有问题文本或主题判断缺口是单点还是跨阶段；没有主题时不补写。",
            "空档保持为空，客户文案隐藏内部档位名称且不得写行动。",
            "不要把不同需求都泛化成采购叙事；发现类问题只说明用户未指定品牌时品牌能否进入对应问题，竞品类问题说明相对表现，验证类问题说明事实识别，评价类问题说明品牌认知，品类认知类问题说明选择标准，准确性类问题说明事实正误。只有原问题明确是采购或制造商初选时才使用采购。",
        ],
        "M06": [
            "每个后端方向恰好对应一个不同问题、一组证据、一个动作和一个可验证预期。",
            "只有 action_context 明确提供 route_type 时才使用行动路由：信息理解缺口走适合承载事实的站内页面，第三方信任缺口走独立信源，错误事实按错误来源纠正，负面认知基于真实事实重构，已有优势做有证据的强化；不得根据单个低指标自行归类。",
            "route_type 和 verification_signals 是内部控制字段，客户文案不得暴露英文枚举；expected_impact 必须写成对应可见度、引用、品牌表达或事实准确性在同口径复测中的可观察变化，不得写流量、线索或成交归因。",
            "不得新增方向、数量、频率、期限或效果承诺，也不得把多条行动都写成泛化的完善内容。",
            "相邻行动必须明确分工；公开网页、第三方内容和非公开审核材料不得重复解决同一问题。",
            "问题和证据只能来自后端方向或已接受模块；不得推断现有资料分散、只存在于图片或附件、分散在不同人员或部门等运营现状。",
            "诊断范围覆盖整个官网与外部信源，但我方可直接交付只限官网 Blog 和第三方内容；首页、产品页、解决方案页、定价页、帮助中心、产品文档等非 Blog 官网页面只能提供修改清单或建议文案，由客户修改并上线。",
            "不得为了匹配我方交付范围，把产品规格、价格、政策、集成、服务承诺等本应更新在对应正式页面的事实全部改写成 Blog 行动；Blog 与第三方内容只能补充解释或验证。",
            "内部产品事实、客户案例、评价授权、服务数据和定位审批由客户相关团队提供或确认；只有 action_context 明确给出 confirmed_client_owner 时才点名具体部门，否则写客户相关团队。",
            "action_context 提供 geo_team_delivery、client_action 或 client_inputs 时，客户文案必须同时写清我方交付和客户配合事项，不得把客户依赖隐藏成我方单方面动作。",
            "action_context 提供 page_opportunity_ids 时，只引用后端已确认的高相关页面；对外写具体能力、Claim 或问题缺口，不展示 Attribute/Prompt Gap 内部字段。已引用页面写强化目标，未引用页面写 Citation Gap，不把两者混为页面相关性。",
            "动作要写清准备什么、放在哪里或如何提供、供谁判断；预期只写信息更容易被采用或采购判断更容易完成，不承诺排名和推荐结果。",
        ],
        "M07": [
            "只使用后端 platform_consistency；不得从逐条平台结果自行计算一致率、阈值或共识强度。",
            "只比较相同市场、语言、采集窗口和匹配 Prompt 样本；不可比或可比平台不足时只写证据不足。",
            "正式诊断只输出整体和主题两级；Attribute 只可作为其他模块或跨模块解释证据，不得建立独立跨平台状态。",
            "分别判断提及是否一致和平均提及位置是否一致；所有平台均未提及时，不得讨论排名一致或竞争位置。",
            "平台一致只代表可比平台结果稳定，不得写成全网共识；平台分歧也不得直接归因为某类页面、来源或平台机制。",
            "不得从平台差异直接提出单平台优化；只有其他模块提供对应来源证据时，M01 才能写有限的跨模块关系。",
            "主题的 mention_consistency 或 position_consistency 为 mixed 时，可写该主题的跨平台判断尚未稳定；不得另造 Attribute 状态或排名—可见度组合状态。",
            "不得仅凭平台分歧断言不同平台给来源赋予不同权重；只有引用数据直接支持时，才在 M01 写有限关系。",
            "先写平台共同支持的结论，再写具体差异；两个平台都不提品牌但由不同竞品占位时，应表达品牌缺席方向一致、竞争结构存在平台差异。",
        ],
        "M08": [
            "只使用后端 market_perception_diagnostics；不得从原始回答重新归纳购买标准、匹配 Attribute 或自判 included/missing/conflicting。",
            "included 表示市场购买框架已包含预设差异点，missing 表示当前框架未把它作为标准，conflicting 表示市场标准与预设差异点存在冲突，insufficient 只写证据不足。",
            "该模块判断购买框架是否有利于品牌差异化，不得写成品牌可见度、直接竞品输赢原因、成交归因或确定行动因果。",
            "结论必须保留主题、Attribute、市场标准、支持样本和证据边界；少量样本不得写成整个市场共识。",
            "客户文案统一称品类认知，重点写选择标准和权衡；没有明确采购场景时，不把所有标准都泛化为采购叙事。",
        ],
        "M10": [
            "只保留会改变客户判断、优先级或行动的三至五条信息。",
            "摘要应覆盖主状态、关键证据关系和先后顺序，不逐模块复述全部数字，也不人为区分正式结论与切片观察。",
        ],
    }[module_id]


def create_task(root, manifest, payload, module_id):
    if module_id in manifest["modules"]:
        return
    resources = {}
    fact_path = primary_fact_path(module_id)
    if fact_path:
        resources["facts"] = {"path": fact_path, "sha256": file_digest(root / fact_path)}
    for diagnostic_name in diagnostic_fact_paths(module_id):
        path = f"canonical/{diagnostic_name}.json"
        resources[f"diagnostic:{diagnostic_name}"] = {
            "path": path,
            "sha256": file_digest(root / path),
        }
    for dependency in module_dependencies(module_id):
        path = module_result_path(dependency)
        resources[f"module:{dependency}"] = {"path": path, "sha256": file_digest(root / path)}
    task_seed = {"module_id": module_id, "input_hash": payload["input_hash"], "resources": resources}
    task_id = f"T-{module_id}-{digest(task_seed).split(':', 1)[1][:12]}"
    task = {
        "protocol_version": PROTOCOL_VERSION,
        "run_id": manifest["run_id"],
        "task_id": task_id,
        "kind": "backend_report_module",
        "module_id": module_id,
        "blocking": True,
        "depends_on": module_dependencies(module_id),
        "resources": resources,
        "input": {
            "brand_name": payload["brand_name"],
            "corp_name": payload["corp_name"],
            "product_name": payload["product_name"],
            "core_topic": payload["core_topic"],
            "topics": payload["topics"],
            "tags": payload["tags"],
            "target_attributes": payload["target_attributes"],
            "market": payload["market"],
            "language": payload["language"],
            "purpose": module_purpose(module_id),
            "synthesis_method": "数据事实 → 状态判断 → 业务含义 → 证据边界",
            "synthesis_rules": module_synthesis_rules(module_id),
            "output_contract": output_contract(module_id),
            "evidence_rule": "output.evidence_refs 必须覆盖每个非空结论，并引用 fact:/JSON指针、diagnostic:资源名:/JSON指针、module:Mxx:/JSON指针、evidence:BE-xxx 或 action:ACT-xxx。",
            "global_rules": [
                "输入文件是唯一事实源，禁止自行计算、补数或根据品牌常识扩写。",
                "输出客户文案固定为中文，保持第三方、客观、结论先行。",
                "需要交代范围时，客户文案只使用发现、竞品、验证、准确性、评价和品类认知六个名称；不得混用发现型、纯发现型、竞品比较、功能核实、准确性诊断或品牌评价。",
                "正式可见度与主要引用生态只使用 Discovery；情绪直接使用完整 analysis_type=sentiment 结果，不再按 diagnostic_intent 或其他意图二次筛选。",
                "提及率排名按 Discovery 提及率比较品牌名次；平均提及位置按被提及回答正文中的首次合格出现位置取平均。客户文案不得混淆两者。",
                "客户指标统一写平均提及位置和引用份额，不得输出平均提及排名、引用占比或官网引用占比。",
                "竞品、验证和评价的问题本身可能提及目标品牌，不能证明品牌在用户未指定时进入回答。",
                "竞品胜负不等于目标品牌情绪；品类选择标准不等于目标品牌可见度。",
                "竞品只把决胜回答胜率称为竞品胜率；不得另写总体胜率，优劣势只来自有支持样本的正面对比证据。",
                "target_attributes 是评测前目标，只有 attribute_diagnostics 和回答证据能形成实际 Strength、Opportunity 或 Objection。",
                "跨平台一致性正式输出只到整体和主题；Attribute 只作内部分析或其他模块解释证据，不得建立独立跨平台状态。",
                "Market Perception 只判断购买框架与预设差异点的关系，不得写成可见度、归因或确定输赢原因。",
                "报告可诊断整个官网，但我方直接交付只限官网 Blog 和第三方内容；非 Blog 官网页面由客户修改上线，我方只能提供修改建议或建议文案。",
                "回答中未出现只能写成未被这批回答提到；不得外推为真实采购名单、市场表现或客户决策。",
                "客户文案隐藏通用题、品牌题、diagnostic_intent、metric_scopes 等内部分类；诊断标签单独展示用发现、竞品、验证、准确性、评价、品类认知，结论句使用带‘类’的写法。",
                "少量样本不得放大为普遍规律，多个事实并存不得写成确定因果。",
                "使用业务读者能直接理解的短句；出现需核实时必须说明核实对象、适用场景和所需材料，否则删除。",
                "不得出现 Markdown、内部编码、夸张措辞或承诺具体提升结果。",
            ],
        },
        "created_at": now_iso(),
    }
    task["task_digest"] = digest(task)
    path = f"tasks/{task_id}.json"
    write_json(root / path, task)
    manifest["tasks"][task_id] = {
        "module_id": module_id,
        "status": "pending",
        "path": path,
        "result_path": None,
    }
    manifest["modules"][module_id] = {"status": "pending", "task_id": task_id, "result_path": None}


def create_degraded_actions(root, manifest):
    content = {"summary": "", "actions": []}
    result = {
        "schema_version": RESULT_VERSION,
        "module_id": "M06",
        "status": "degraded",
        "content": content,
        "evidence_refs": {},
        "reason": "后端未提供 action_context，正式报告不在本地重新计算行动状态。",
    }
    write_json(root / module_result_path("M06"), result)
    manifest["modules"]["M06"] = {
        "status": "degraded",
        "task_id": None,
        "result_path": module_result_path("M06"),
    }
    manifest["warnings"].append(result["reason"])


def create_degraded_platform_consistency(root, manifest):
    result = {
        "schema_version": RESULT_VERSION,
        "module_id": "M07",
        "status": "degraded",
        "content": [],
        "evidence_refs": {},
        "reason": "后端未提供可比的 platform_consistency，正式报告不在本地拼接平台样本或计算一致性。",
    }
    write_json(root / module_result_path("M07"), result)
    manifest["modules"]["M07"] = {
        "status": "degraded",
        "task_id": None,
        "result_path": module_result_path("M07"),
    }
    manifest["warnings"].append(result["reason"])


def create_degraded_market_perception(root, manifest):
    result = {
        "schema_version": RESULT_VERSION,
        "module_id": "M08",
        "status": "degraded",
        "content": [],
        "evidence_refs": {},
        "reason": "后端未提供正式 market_perception_diagnostics，报告不从原始品类认知回答重新归纳购买框架。",
    }
    write_json(root / module_result_path("M08"), result)
    manifest["modules"]["M08"] = {
        "status": "degraded",
        "task_id": None,
        "result_path": module_result_path("M08"),
    }
    manifest["warnings"].append(result["reason"])


def ensure_tasks(root, manifest, payload):
    for module_id in ("M02", "M03", "M04", "M05"):
        create_task(root, manifest, payload, module_id)
    if "M07" not in manifest["modules"]:
        if payload["platform_consistency"]["findings"]:
            create_task(root, manifest, payload, "M07")
        else:
            create_degraded_platform_consistency(root, manifest)
    if "M08" not in manifest["modules"]:
        if payload["market_perception_diagnostics"]["findings"]:
            create_task(root, manifest, payload, "M08")
        else:
            create_degraded_market_perception(root, manifest)
    if all(module_resolved(manifest, module_id) for module_id in BASE_MODULES):
        create_task(root, manifest, payload, "M01")
    if all(module_resolved(manifest, module_id) for module_id in BASE_MODULES) and "M06" not in manifest["modules"]:
        if payload["action_context"]["directions"]:
            create_task(root, manifest, payload, "M06")
        else:
            create_degraded_actions(root, manifest)
    if all(module_resolved(manifest, module_id) for module_id in (
        "M01", "M02", "M03", "M04", "M05", "M06", "M07", "M08"
    )):
        create_task(root, manifest, payload, "M10")


def refresh_state(manifest):
    pending = [item for item in manifest["modules"].values() if item["status"] == "pending"]
    if manifest.get("state") == "COMPLETE":
        return
    manifest["state"] = "WAITING_AGENT" if pending else ("READY_TO_FINALIZE" if module_resolved(manifest, "M10") else "PREPARED")


def prepare_run(input_path, run_dir):
    root = Path(run_dir).expanduser().resolve()
    if root.exists() and any(root.iterdir()):
        raise ContractError(f"运行目录非空：{root}")
    root.mkdir(parents=True, exist_ok=True)
    source = Path(input_path).expanduser().resolve()
    payload = normalize_payload(read_json(source))
    (root / "input").mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, root / "input/backend-payload.source.json")
    write_json(root / "canonical/backend-payload.json", payload)
    for field in (
        "overview", "competitor", "citation", "brand_expression", "category_actions",
        "question_details", "action_context", "topics", "tags", "target_attributes",
        "attribute_diagnostics", "comparison_outcomes", "competitor_comparison_summary",
        "market_perception", "market_perception_diagnostics",
        "accuracy_findings",
        "platform_consistency", "page_opportunities",
    ):
        write_json(root / f"canonical/{field}.json", payload[field])
    manifest = {
        "schema_version": "overseas-geo-backend-report-run/v1",
        "run_id": payload["task_id"],
        "batch_id": payload["batch_id"],
        "input_hash": payload["input_hash"],
        "state": "PREPARED",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "modules": {},
        "tasks": {},
        "warnings": [],
    }
    ensure_tasks(root, manifest, payload)
    refresh_state(manifest)
    save_manifest(root, manifest)
    return root, manifest


def ready_tasks(root, manifest):
    ready = []
    for task_id, meta in manifest["tasks"].items():
        if meta["status"] != "pending":
            continue
        task = read_json(root / meta["path"])
        if all(module_resolved(manifest, dependency) for dependency in task["depends_on"]):
            ready.append(task)
    ready.sort(key=lambda item: (MODULE_ORDER[item["module_id"]], item["task_id"]))
    return ready


def pointer_get(value, pointer):
    if pointer in ("", "/"):
        return value
    if not pointer.startswith("/"):
        raise ContractError(f"JSON 指针格式错误：{pointer}")
    current = value
    for raw_part in pointer[1:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError) as error:
                raise ContractError(f"JSON 指针不存在：{pointer}") from error
        elif isinstance(current, dict) and part in current:
            current = current[part]
        else:
            raise ContractError(f"JSON 指针不存在：{pointer}")
    return current


def statement_pointers(module_id, content):
    if module_id in {"M02", "M03", "M07", "M08"}:
        return [f"/{index}" for index in range(len(content))]
    if module_id == "M04":
        result = []
        for group in ("positive_evidence", "risk_evidence"):
            result.extend(f"/{group}/{index}" for index in range(len(content[group])))
        result.extend(f"/analysis_items/{index}" for index in range(len(content["analysis_items"])))
        return result
    if module_id == "M05":
        return [f"/{key}" for key in ("p0", "p1", "p2") if content[key]]
    if module_id == "M06":
        result = ["/summary"] if content["summary"] else []
        result.extend(f"/actions/{index}" for index in range(len(content["actions"])))
        return result
    if module_id == "M01":
        return ["/title", *[f"/points/{index}" for index in range(len(content["points"]))], "/conclusion"]
    if module_id == "M10":
        return ["/title", "/summary", *[f"/points/{index}" for index in range(len(content["points"]))], "/conclusion"]
    raise ContractError(f"未知模块：{module_id}")


def require_string(value, field, allow_empty=False, max_length=120):
    if not isinstance(value, str):
        raise ContractError(f"{field} 必须是字符串")
    if not allow_empty and not value.strip():
        raise ContractError(f"{field} 不能为空")
    if len(value) > max_length:
        raise ContractError(f"{field} 超过 {max_length} 字符")
    if "```" in value or CUSTOMER_BANNED.search(value):
        raise ContractError(f"{field} 含禁止表达或内部编码")


def validate_exact_keys(value, keys, field):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ContractError(f"{field} 字段必须严格为 {sorted(keys)}")


def validate_content(module_id, content, payload):
    if module_id in {"M02", "M03", "M07", "M08"}:
        limits = {"M02": 6, "M03": 4, "M07": 5, "M08": 5}
        if not isinstance(content, list) or not 1 <= len(content) <= limits[module_id]:
            raise ContractError(f"{module_id}.content 必须是一至{limits[module_id]}条字符串数组")
        for index, item in enumerate(content):
            require_string(item, f"{module_id}.content[{index}]", max_length=90)
    elif module_id == "M04":
        validate_exact_keys(content, {"positive_evidence", "risk_evidence", "analysis_items"}, "M04.content")
        for group in ("positive_evidence", "risk_evidence"):
            if not isinstance(content[group], list) or len(content[group]) > 5:
                raise ContractError(f"M04.{group} 必须是最多五项数组")
            for index, item in enumerate(content[group]):
                validate_exact_keys(item, {"keyword", "explain"}, f"M04.{group}[{index}]")
                require_string(item["keyword"], f"M04.{group}[{index}].keyword", max_length=16)
                require_string(item["explain"], f"M04.{group}[{index}].explain", max_length=60)
        if not isinstance(content["analysis_items"], list) or not 1 <= len(content["analysis_items"]) <= 3:
            raise ContractError("M04.analysis_items 必须是一至三条")
        for index, item in enumerate(content["analysis_items"]):
            require_string(item, f"M04.analysis_items[{index}]", max_length=80)
    elif module_id == "M05":
        validate_exact_keys(content, {"p0", "p1", "p2"}, "M05.content")
        groups = payload["category_actions"]
        for key in ("p0", "p1", "p2"):
            require_string(content[key], f"M05.{key}", allow_empty=True, max_length=90)
            has_input = bool(groups.get(key) or [])
            if has_input != bool(content[key].strip()):
                raise ContractError(f"M05.{key} 必须与后端该档是否为空保持一致")
            if content[key] and ACTION_BANNED.search(content[key]):
                raise ContractError(f"M05.{key} 只能写现状，不能写行动建议")
    elif module_id == "M01":
        validate_exact_keys(content, {"title", "points", "conclusion"}, "M01.content")
        require_string(content["title"], "M01.title", max_length=60)
        if not isinstance(content["points"], list) or not 3 <= len(content["points"]) <= 5:
            raise ContractError("M01.points 必须是三至五条")
        for index, item in enumerate(content["points"]):
            require_string(item, f"M01.points[{index}]", max_length=90)
        require_string(content["conclusion"], "M01.conclusion", max_length=90)
    elif module_id == "M06":
        validate_exact_keys(content, {"summary", "actions"}, "M06.content")
        require_string(content["summary"], "M06.summary", max_length=70)
        directions = payload["action_context"]["directions"]
        if not isinstance(content["actions"], list) or len(content["actions"]) != len(directions):
            raise ContractError("M06.actions 必须与后端行动方向一一对应")
        direction_map = {item["direction_id"]: item for item in directions}
        seen = set()
        for index, item in enumerate(content["actions"]):
            validate_exact_keys(item, {"direction_id", "source_module", "title", "evidence", "action", "expected_impact"}, f"M06.actions[{index}]")
            direction_id = str(item["direction_id"])
            if direction_id not in direction_map or direction_id in seen:
                raise ContractError("M06.actions.direction_id 必须唯一对应后端方向")
            seen.add(direction_id)
            for field, limit in (("source_module", 20), ("title", 24), ("evidence", 70), ("action", 120), ("expected_impact", 50)):
                require_string(item[field], f"M06.actions[{index}].{field}", max_length=limit)
            direction = direction_map[direction_id]
            action_text = item["action"]
            expected_impact = item["expected_impact"]
            owner = direction.get("confirmed_client_owner")
            for signal in direction.get("verification_signals") or []:
                if not VERIFICATION_SIGNAL_PATTERNS[signal].search(expected_impact):
                    raise ContractError(f"M06.expected_impact 必须写明 {signal} 复测信号")
            if direction.get("geo_team_delivery") and not GEO_ACTOR.search(action_text):
                raise ContractError("M06.action 必须明确写出我方负责的 Blog 或第三方内容交付")
            if (
                direction.get("client_action") or direction.get("client_inputs")
            ) and not (
                CLIENT_RESPONSIBILITY.search(action_text) or (owner and owner in action_text)
            ):
                raise ContractError("M06.action 必须明确写出客户负责的修改、材料或确认事项")
            if owner and owner not in action_text:
                raise ContractError("M06.action 必须保留后端已确认的客户责任团队")
            if NON_BLOG_OFFICIAL_PAGE.search(action_text) and DIRECT_PAGE_CHANGE.search(action_text):
                if not CLIENT_RESPONSIBILITY.search(action_text) and not ADVISORY_PAGE_WORK.search(action_text):
                    raise ContractError("非 Blog 官网页面的修改与上线必须明确由客户执行")
                for clause in re.split(r"[，。；;]", action_text):
                    if (
                        GEO_ACTOR.search(clause)
                        and NON_BLOG_OFFICIAL_PAGE.search(clause)
                        and DIRECT_PAGE_CHANGE.search(clause)
                        and not ADVISORY_PAGE_WORK.search(clause)
                    ):
                        raise ContractError("不得把非 Blog 官网页面写成我方直接修改或上线")
    elif module_id == "M10":
        validate_exact_keys(content, {"title", "summary", "points", "conclusion"}, "M10.content")
        require_string(content["title"], "M10.title", max_length=40)
        require_string(content["summary"], "M10.summary", max_length=100)
        if not isinstance(content["points"], list) or not 3 <= len(content["points"]) <= 5:
            raise ContractError("M10.points 必须是三至五条")
        for index, item in enumerate(content["points"]):
            require_string(item, f"M10.points[{index}]", max_length=70)
        require_string(content["conclusion"], "M10.conclusion", max_length=100)
    else:
        raise ContractError(f"未知模块：{module_id}")


def resource_values(root, task):
    return {name: read_json(root / meta["path"]) for name, meta in task["resources"].items()}


def validate_evidence_refs(root, task, content, refs, payload):
    pointers = statement_pointers(task["module_id"], content)
    if not isinstance(refs, dict) or set(refs) != set(pointers):
        raise ContractError("evidence_refs 必须逐条覆盖全部非空结论，且不能多写或漏写")
    resources = resource_values(root, task)
    expression_ids = {str(item["evidence_id"]) for item in payload["brand_expression"]}
    action_ids = {str(item["direction_id"]) for item in payload["action_context"]["directions"]}
    flattened_refs = [ref for items in refs.values() if isinstance(items, list) for ref in items]
    if task["module_id"] == "M02" and has_material_competitor_comparison(payload):
        customer_text = "\n".join(content)
        customer_numbers = set(NUMBER_RE.findall(customer_text))
        customer_numbers.update(token.rstrip("%") for token in list(customer_numbers))
        for index, pair in enumerate(payload["competitor_comparison_summary"]["pairs"]):
            if pair["competitor_name"] not in customer_text:
                raise ContractError(f"M02 必须逐一说明正式竞品 {pair['competitor_name']}")
            rate = pair["target_decisive_win_rate"]
            if rate is None:
                if "胜率" not in customer_text or not any(
                    phrase in customer_text for phrase in ("无法计算", "暂无决胜", "没有决胜")
                ):
                    raise ContractError(f"M02 必须说明正式竞品 {pair['competitor_name']} 暂无可计算胜率")
            elif not (rate_tokens(rate) & customer_numbers):
                raise ContractError(f"M02 必须展示正式竞品 {pair['competitor_name']} 的决胜回答胜率")
            rate_ref = f"diagnostic:competitor_comparison_summary:/pairs/{index}/target_decisive_win_rate"
            if rate_ref not in flattened_refs:
                raise ContractError(f"M02 必须引用正式竞品 {pair['competitor_name']} 的决胜回答胜率")
            for group in ("advantage_themes", "disadvantage_themes"):
                if pair[group] and not any(
                    isinstance(ref, str)
                    and ref.startswith(f"diagnostic:competitor_comparison_summary:/pairs/{index}/{group}")
                    for ref in flattened_refs
                ):
                    raise ContractError(f"M02 必须引用正式竞品 {pair['competitor_name']} 的{group}")
    if task["module_id"] == "M01" and has_material_platform_consistency(payload):
        if not any(ref.startswith("module:M07:") for ref in flattened_refs if isinstance(ref, str)):
            raise ContractError("M01 必须引用已完成的跨平台一致性结论")
    if task["module_id"] == "M01" and has_material_market_perception(payload):
        if not any(ref.startswith("module:M08:") for ref in flattened_refs if isinstance(ref, str)):
            raise ContractError("M01 必须引用已完成的品类认知/购买框架结论")
    if task["module_id"] == "M03" and has_material_page_opportunities(payload):
        if not any(
            isinstance(ref, str) and ref.startswith("diagnostic:page_opportunities:")
            for ref in flattened_refs
        ):
            raise ContractError("M03 必须引用后端正式页面机会")
    if task["module_id"] == "M08":
        for index, item in enumerate(payload["market_perception_diagnostics"]["findings"]):
            if item["alignment_status"] != "insufficient":
                prefix = f"fact:/findings/{index}/"
                if not any(isinstance(ref, str) and ref.startswith(prefix) for ref in flattened_refs):
                    raise ContractError(f"M08 必须覆盖品类认知诊断 {item['finding_id']}")
    for pointer, items in refs.items():
        if not isinstance(items, list) or not items:
            raise ContractError(f"{pointer} 至少需要一个证据引用")
        for ref in items:
            if not isinstance(ref, str):
                raise ContractError("证据引用必须是字符串")
            if ref.startswith("fact:"):
                if "facts" not in resources:
                    raise ContractError(f"当前模块没有事实资源：{ref}")
                pointer_get(resources["facts"], ref[5:])
            elif ref.startswith("module:"):
                match = re.fullmatch(r"module:(M\d{2}):(.*)", ref)
                if not match or f"module:{match.group(1)}" not in resources:
                    raise ContractError(f"模块证据引用不可用：{ref}")
                module_result = resources[f"module:{match.group(1)}"]
                pointer_get(module_result["content"], match.group(2))
            elif ref.startswith("diagnostic:"):
                match = re.fullmatch(r"diagnostic:([^:]+):(.*)", ref)
                resource_name = f"diagnostic:{match.group(1)}" if match else ""
                if not match or resource_name not in resources:
                    raise ContractError(f"诊断证据引用不可用：{ref}")
                pointer_get(resources[resource_name], match.group(2))
            elif ref.startswith("evidence:"):
                if ref.split(":", 1)[1] not in expression_ids:
                    raise ContractError(f"表达证据 ID 不存在：{ref}")
            elif ref.startswith("action:"):
                if ref.split(":", 1)[1] not in action_ids:
                    raise ContractError(f"行动方向 ID 不存在：{ref}")
            else:
                raise ContractError(f"未知证据引用格式：{ref}")


def collect_allowed_numbers(value, result):
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, (int, float)):
        variants = {f"{value:g}"}
        if 0 <= abs(float(value)) <= 1:
            percent = value * 100
            for formatted in (
                f"{percent:g}",
                f"{percent:.1f}".rstrip("0").rstrip("."),
                f"{percent:.2f}".rstrip("0").rstrip("."),
            ):
                variants.update({formatted, f"{formatted}%"})
        result.update(variants)
    elif isinstance(value, str):
        result.update(NUMBER_RE.findall(value))
        result.update(token.rstrip("%") for token in NUMBER_RE.findall(value))
    elif isinstance(value, list):
        result.add(str(len(value)))
        for item in value:
            collect_allowed_numbers(item, result)
    elif isinstance(value, dict):
        for item in value.values():
            collect_allowed_numbers(item, result)


def validate_numbers(root, task, content):
    allowed = set()
    for value in resource_values(root, task).values():
        collect_allowed_numbers(value, allowed)
    output_numbers = NUMBER_RE.findall(json.dumps(content, ensure_ascii=False))
    for token in output_numbers:
        if token not in allowed and token.rstrip("%") not in allowed:
            raise ContractError(f"输出出现事实资源中不存在的数字：{token}")


def validate_result_envelope(task, result):
    for key in ("protocol_version", "run_id", "task_id", "kind", "module_id", "task_digest"):
        if result.get(key) != task.get(key):
            raise ContractError(f"result.{key} 与任务不一致")
    if result.get("status") != "completed":
        raise ContractError("正式报告模块只接受 status=completed；无法完成时应保留任务并说明问题")
    output = result.get("output")
    validate_exact_keys(output, {"content", "evidence_refs"}, "result.output")
    return output


def submit_result(run_dir, task_id, result_path):
    root, manifest = load_run(run_dir)
    if task_id not in manifest["tasks"]:
        raise ContractError(f"未知 task_id：{task_id}")
    meta = manifest["tasks"][task_id]
    if meta["status"] != "pending":
        raise ContractError(f"任务已经处理：{task_id}")
    task = read_json(root / meta["path"])
    for resource in task["resources"].values():
        if file_digest(root / resource["path"]) != resource["sha256"]:
            raise ContractError("任务资源在发出后发生变化")
    result = read_json(result_path)
    output = validate_result_envelope(task, result)
    payload = read_json(root / "canonical/backend-payload.json")
    validate_content(task["module_id"], output["content"], payload)
    validate_evidence_refs(root, task, output["content"], output["evidence_refs"], payload)
    validate_numbers(root, task, output["content"])
    accepted = {
        "schema_version": RESULT_VERSION,
        "module_id": task["module_id"],
        "status": "accepted",
        "content": output["content"],
        "evidence_refs": output["evidence_refs"],
        "accepted_at": now_iso(),
        "task_id": task_id,
        "task_digest": task["task_digest"],
    }
    target = root / module_result_path(task["module_id"])
    write_json(target, accepted)
    meta["status"] = "accepted"
    meta["result_path"] = module_result_path(task["module_id"])
    manifest["modules"][task["module_id"]]["status"] = "accepted"
    manifest["modules"][task["module_id"]]["result_path"] = module_result_path(task["module_id"])
    ensure_tasks(root, manifest, payload)
    refresh_state(manifest)
    save_manifest(root, manifest)
    return root, manifest, accepted


def clean_dify_content(module_id, content):
    if module_id != "M06":
        return content
    return {
        "summary": content["summary"],
        "actions": [
            {key: value for key, value in item.items() if key != "direction_id"}
            for item in content["actions"]
        ],
    }


def build_upload_rows(modules):
    rows = []

    def append(module, path, index, field, value):
        rows.append({
            "module": module,
            "path": path,
            "index": "" if index is None else str(index),
            "field": field,
            "value": "" if value is None else str(value),
        })

    overview = modules["M01"]["content"]
    append("summary_overview", "", None, "title", overview["title"])

    category_actions = modules["M05"]["content"]
    for field in ("p0", "p1", "p2"):
        append("summary_category_actions", "", None, field, category_actions[field])

    for index, value in enumerate(overview["points"]):
        append("summary_overview", "points", index, "text", value)

    for index, value in enumerate(modules["M02"]["content"]):
        append("summary_competitor_performance", "items", index, "text", value)

    brand_expression = modules["M04"]["content"]
    for path in ("positive_evidence", "risk_evidence"):
        for index, item in enumerate(brand_expression[path]):
            for field in ("keyword", "explain"):
                append("summary_brand_expression", path, index, field, item[field])
    for index, value in enumerate(brand_expression["analysis_items"]):
        append("summary_brand_expression", "analysis_items", index, "text", value)

    for index, value in enumerate(modules["M03"]["content"]):
        append("summary_citation_sources", "items", index, "text", value)

    for index, item in enumerate(modules["M06"]["content"]["actions"]):
        for field in ("source_module", "title", "evidence", "action", "expected_impact"):
            append("summary_priority_opportunities", "actions", index, field, item[field])

    return rows


def finalize_run(run_dir):
    root, manifest = load_run(run_dir)
    required = ("M01", "M02", "M03", "M04", "M05", "M06", "M07", "M08", "M10")
    unresolved = [module_id for module_id in required if not module_resolved(manifest, module_id)]
    if unresolved:
        raise ContractError("仍有未完成模块：" + ", ".join(unresolved))
    payload = read_json(root / "canonical/backend-payload.json")
    modules = {module_id: read_json(root / module_result_path(module_id)) for module_id in required}
    normalized = {
        "schema_version": "overseas-geo-presales-report/v1",
        "task_id": payload["task_id"],
        "batch_id": payload["batch_id"],
        "brand_name": payload["brand_name"],
        "corp_name": payload["corp_name"],
        "product_name": payload["product_name"],
        "core_topic": payload["core_topic"],
        "market": payload["market"],
        "language": payload["language"],
        "backend_input_hash": payload["input_hash"],
        "modules": {SUMMARY_KEYS[module_id]: modules[module_id]["content"] for module_id in required},
        "warnings": manifest["warnings"],
        "generated_at": now_iso(),
    }
    normalized["report_hash"] = digest(normalized)
    dify = {
        SUMMARY_KEYS[module_id]: json.dumps(clean_dify_content(module_id, modules[module_id]["content"]), ensure_ascii=False)
        for module_id in required if module_id not in {"M07", "M08"}
    }
    audit = {
        "schema_version": "overseas-geo-presales-report-audit/v1",
        "task_id": payload["task_id"],
        "batch_id": payload["batch_id"],
        "backend_input_hash": payload["input_hash"],
        "report_hash": normalized["report_hash"],
        "module_status": {module_id: modules[module_id]["status"] for module_id in required},
        "evidence_refs": {module_id: modules[module_id]["evidence_refs"] for module_id in required},
        "warnings": manifest["warnings"],
        "production_fact_owner": "company_backend",
        "local_metric_recalculation": False,
    }
    write_json(root / "artifacts/report.json", normalized)
    write_json(root / "artifacts/dify-compatible-output.json", dify)
    write_json(root / "artifacts/audit.json", audit)
    write_upload_csv(root / "artifacts/report-upload.csv", build_upload_rows(modules))
    manifest["state"] = "COMPLETE"
    manifest["artifacts"] = {
        "report": "artifacts/report.json",
        "dify_compatible_output": "artifacts/dify-compatible-output.json",
        "audit": "artifacts/audit.json",
        "upload_csv": "artifacts/report-upload.csv",
    }
    save_manifest(root, manifest)
    return root, manifest, normalized


def emit(value):
    json.dump(value, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def cmd_prepare(args):
    root, manifest = prepare_run(args.input, args.run_dir)
    emit({
        "run_dir": str(root),
        "state": manifest["state"],
        "ready_modules": [task["module_id"] for task in ready_tasks(root, manifest)],
        "warnings": manifest["warnings"],
    })


def cmd_next_task(args):
    root, manifest = load_run(args.run_dir)
    tasks = ready_tasks(root, manifest)
    selected = tasks if args.all_ready else tasks[:1]
    emit({
        "state": manifest["state"],
        "tasks": [
            {
                "task_id": task["task_id"],
                "module_id": task["module_id"],
                "task_path": str(root / manifest["tasks"][task["task_id"]]["path"]),
                "suggested_result_path": str(root / "results" / f"{task['task_id']}.inbox.json"),
                "task": task if args.inline else None,
            }
            for task in selected
        ],
    })


def cmd_submit(args):
    root, manifest, accepted = submit_result(args.run_dir, args.task_id, args.result)
    emit({
        "accepted_module": accepted["module_id"],
        "state": manifest["state"],
        "ready_modules": [task["module_id"] for task in ready_tasks(root, manifest)],
        "warnings": manifest["warnings"],
    })


def cmd_status(args):
    root, manifest = load_run(args.run_dir)
    emit({
        "run_id": manifest["run_id"],
        "batch_id": manifest["batch_id"],
        "state": manifest["state"],
        "modules": manifest["modules"],
        "ready_modules": [task["module_id"] for task in ready_tasks(root, manifest)],
        "warnings": manifest["warnings"],
        "artifacts": manifest.get("artifacts") or {},
    })


def cmd_finalize(args):
    root, manifest, report = finalize_run(args.run_dir)
    emit({
        "state": manifest["state"],
        "report_hash": report["report_hash"],
        "upload_csv": str(root / manifest["artifacts"]["upload_csv"]),
        "report": str(root / manifest["artifacts"]["report"]),
        "dify_compatible_output": str(root / manifest["artifacts"]["dify_compatible_output"]),
        "audit": str(root / manifest["artifacts"]["audit"]),
        "warnings": manifest["warnings"],
    })


def build_parser():
    parser = argparse.ArgumentParser(prog="backend_report", description="基于公司后端统计包生成海外 GEO 售前报告结论")
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare", help="校验并冻结后端统计包，生成首批报告任务")
    prepare.add_argument("--input", required=True)
    prepare.add_argument("--run-dir", required=True)
    prepare.set_defaults(func=cmd_prepare)
    next_task = sub.add_parser("next-task", help="读取下一个或全部当前可执行的报告任务")
    next_task.add_argument("--run-dir", required=True)
    next_task.add_argument("--inline", action="store_true")
    next_task.add_argument("--all-ready", action="store_true")
    next_task.set_defaults(func=cmd_next_task)
    submit = sub.add_parser("submit-task", help="校验并接收一个报告模块结果")
    submit.add_argument("--run-dir", required=True)
    submit.add_argument("--task-id", required=True)
    submit.add_argument("--result", required=True)
    submit.set_defaults(func=cmd_submit)
    status = sub.add_parser("status", help="查看模块依赖、待处理任务与降级状态")
    status.add_argument("--run-dir", required=True)
    status.set_defaults(func=cmd_status)
    finalize = sub.add_parser("finalize", help="生成正式报告、Dify 兼容输出与审计文件")
    finalize.add_argument("--run-dir", required=True)
    finalize.set_defaults(func=cmd_finalize)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
        return 0
    except (ContractError, FileNotFoundError, json.JSONDecodeError, KeyError) as error:
        emit({"error": type(error).__name__, "message": str(error)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
