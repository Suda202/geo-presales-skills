#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlsplit


class ContractError(ValueError):
    pass


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


def digest(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def host_of(value):
    raw = str(value or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = "https://" + raw
    try:
        host = (urlsplit(raw).hostname or "").lower().rstrip(".")
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


def domain_matches(host, domain):
    host = host_of(host)
    domain = host_of(domain)
    return bool(host and domain and (host == domain or host.endswith("." + domain)))


def parse_date(value, field):
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as error:
        raise ContractError(f"{field} 必须使用 YYYY-MM-DD") from error


def normalize_input(raw):
    target = raw.get("target") or {}
    name = str(target.get("name") or raw.get("brand_name") or "").strip()
    domain = host_of(target.get("official_domain") or raw.get("brand_domain"))
    topic = str(raw.get("topic") or "").strip()
    market = str(raw.get("market") or "US").strip()
    if not name or not domain or not topic:
        raise ContractError("必须提供 target.name、target.official_domain 和 topic")
    current_date = parse_date(raw.get("current_date") or date.today().isoformat(), "current_date")
    known = raw.get("known_competitors") or []
    if not isinstance(known, list):
        raise ContractError("known_competitors 必须是数组")
    if len(known) > 3:
        raise ContractError("known_competitors 最多包含 3 个用户填写的候选")
    normalized_known = []
    seen_names = set()
    seen_domains = set()
    for index, item in enumerate(known):
        if isinstance(item, str):
            item = {"name": item}
        if not isinstance(item, dict):
            raise ContractError(f"known_competitors[{index}] 必须是字符串或对象")
        known_name = str(item.get("name") or "").strip()
        known_domain = host_of(item.get("official_domain"))
        aliases = item.get("aliases") or []
        if not known_name:
            raise ContractError(f"known_competitors[{index}].name 不能为空")
        if not isinstance(aliases, list):
            raise ContractError(f"known_competitors[{index}].aliases 必须是数组")
        known_key = known_name.casefold()
        if known_key in seen_names or (known_domain and known_domain in seen_domains):
            raise ContractError("known_competitors 中存在重复名称或官网域名")
        seen_names.add(known_key)
        if known_domain:
            seen_domains.add(known_domain)
        normalized_known.append({
            "name": known_name,
            "official_domain": known_domain or None,
            "aliases": [str(alias).strip() for alias in aliases if str(alias).strip()],
        })
    normalized = {
        "schema_version": "overseas-geo-competitor-research-input/v3",
        "target": {
            "name": name,
            "official_domain": domain,
            "product_name": str(target.get("product_name") or raw.get("product_name") or "").strip() or None,
            "description": str(target.get("description") or raw.get("background_info") or "").strip() or None,
            "target_users": [str(item) for item in target.get("target_users") or raw.get("target_users") or []],
            "buying_motion": str(target.get("buying_motion") or "").strip() or None,
            "market_position": str(target.get("market_position") or "unknown").strip(),
        },
        "topic": topic,
        "market": market,
        "current_date": current_date.isoformat(),
        "known_competitors": normalized_known,
        "selection_count": 3,
        "ruleset_version": "competitor-portfolio-v4",
    }
    normalized["input_hash"] = digest(normalized)
    return normalized


def build_plan(config):
    target = config["target"]
    year = config["current_date"][:4]
    subject = target["product_name"] or target["name"]
    topic = config["topic"]
    market = config["market"]
    queries = [
        f'"{subject}" alternatives competitors {market} {year}',
        f'"{subject}" vs {topic}',
        f'best {topic} tools platforms {market} {year}',
        f'{topic} market leaders {market} {year}',
        f'site:g2.com {topic} category {year}',
        f'site:capterra.com {topic} {year}',
        f'{topic} startup challenger funding customers {year}',
    ]
    for known in config["known_competitors"]:
        name = known.get("name") if isinstance(known, dict) else known
        if name:
            queries.append(f'"{subject}" vs "{name}" {year}')
    return {
        "schema_version": "overseas-geo-competitor-research-plan/v3",
        "input_hash": config["input_hash"],
        "researched_for": config["target"],
        "topic": topic,
        "market": market,
        "current_date": config["current_date"],
        "search_queries": queries,
        "required_source_mix": {
            "official_per_candidate": 1,
            "independent_per_candidate": 1,
            "recent_market_position_evidence_months": 18,
            "minimum_distinct_candidates": 3,
        },
        "instructions": [
            "先搜索候选池，再读取候选官网、定价/产品页和至少一条独立来源。",
            "未提供竞品时从零发现；已提供项作为待核验候选，只有通过同一购买集合硬门槛才保留。",
            "为 same_purchase_set 保存绑定证据，证明买家会在同一次选型中比较双方，不能只证明功能相似。",
            "正式竞品只从同一购买集合候选中选择；相邻产品、外围工具和不同购买决策的品牌不能补位。",
            "至少提交三个通过硬门槛的不同官网候选；不足时继续自动检索，不请求业务补充或复核。",
            "所有证据保存 URL、标题、来源类型、发布时间或访问日期以及它支持的具体判断。",
        ],
    }


def evidence_index(research, config):
    evidence = research.get("evidence") or []
    if not isinstance(evidence, list):
        raise ContractError("evidence 必须是数组")
    result = {}
    for item in evidence:
        if not isinstance(item, dict):
            raise ContractError("evidence 项必须是对象")
        evidence_id = str(item.get("evidence_id") or "").strip()
        url = str(item.get("url") or "").strip()
        source_type = str(item.get("source_type") or "").strip()
        if not evidence_id or evidence_id in result or not host_of(url):
            raise ContractError("证据必须有唯一 evidence_id 和合法 URL")
        if source_type not in {"official", "independent_review", "market_report", "news", "directory"}:
            raise ContractError(f"证据 {evidence_id} 的 source_type 不合法")
        accessed_at = parse_date(item.get("accessed_at"), f"evidence.{evidence_id}.accessed_at")
        published_at = parse_date(item["published_at"], f"evidence.{evidence_id}.published_at") if item.get("published_at") else None
        claims = item.get("claims") or []
        if not isinstance(claims, list) or not claims:
            raise ContractError(f"证据 {evidence_id} 必须记录 claims")
        current_date = date.fromisoformat(config["current_date"])
        if accessed_at > current_date:
            raise ContractError(f"证据 {evidence_id} 的 accessed_at 晚于 current_date")
        if published_at and published_at > current_date:
            raise ContractError(f"证据 {evidence_id} 的 published_at 晚于 current_date")
        result[evidence_id] = {
            **item,
            "host": host_of(url),
            "accessed_date": accessed_at,
            "published_date": published_at,
        }
    return result


def match_known_competitor(name, domain, aliases, config):
    candidate_names = {str(name).strip().casefold()}
    candidate_names.update(str(alias).strip().casefold() for alias in aliases if str(alias).strip())
    for index, known in enumerate(config["known_competitors"]):
        known_domain = host_of(known.get("official_domain"))
        known_names = {str(known.get("name") or "").strip().casefold()}
        known_names.update(str(alias).strip().casefold() for alias in known.get("aliases") or [] if str(alias).strip())
        if (known_domain and domain_matches(domain, known_domain)) or candidate_names.intersection(known_names):
            return index
    return None


def score_candidate(candidate, evidence, config):
    name = str(candidate.get("canonical_name") or "").strip()
    domain = host_of(candidate.get("official_domain"))
    if not name or not domain:
        raise ContractError("每个候选必须提供 canonical_name 和 official_domain")
    aliases = candidate.get("aliases") or []
    if not isinstance(aliases, list):
        raise ContractError(f"候选 {name} 的 aliases 必须是数组")
    matched_known_index = match_known_competitor(name, domain, aliases, config)
    dimensions = candidate.get("dimensions") or {}
    if not isinstance(dimensions, dict):
        raise ContractError(f"候选 {name} 的 dimensions 必须是对象")
    required_dimensions = ["sub_track", "product_form", "target_users", "core_job", "buying_motion", "status_similarity", "specialty_fit"]
    values = {}
    missing_dimensions = []
    for key in required_dimensions:
        if key not in dimensions or dimensions.get(key) is None:
            values[key] = 0
            missing_dimensions.append(key)
            continue
        try:
            value = int(dimensions.get(key))
        except (TypeError, ValueError):
            raise ContractError(f"候选 {name} 的 dimensions.{key} 必须是 0–5")
        if not 0 <= value <= 5:
            raise ContractError(f"候选 {name} 的 dimensions.{key} 必须在 0–5")
        values[key] = value

    candidate_evidence_ids = candidate.get("evidence_ids") or []
    if not isinstance(candidate_evidence_ids, list) or any(item not in evidence for item in candidate_evidence_ids):
        raise ContractError(f"候选 {name} 引用了不存在的 evidence_id")
    candidate_evidence = [evidence[item] for item in candidate_evidence_ids]
    official = [item for item in candidate_evidence if item["source_type"] == "official" and domain_matches(item["host"], domain)]
    independent = [item for item in candidate_evidence if item["source_type"] != "official"]
    current_date = date.fromisoformat(config["current_date"])
    current_official = [item for item in official if (current_date - item["accessed_date"]).days <= 30]
    market_position = str(candidate.get("market_position") or "unknown")
    if market_position not in {"leader", "peer", "challenger", "unknown"}:
        raise ContractError(f"候选 {name} 的 market_position 不合法")

    evidence_bindings = candidate.get("evidence_bindings") or {}
    if not isinstance(evidence_bindings, dict):
        raise ContractError(f"候选 {name} 的 evidence_bindings 必须是对象")

    def bound_evidence(field):
        ids = evidence_bindings.get(field) or []
        if not isinstance(ids, list):
            raise ContractError(f"候选 {name} 的 evidence_bindings.{field} 必须是数组")
        if any(item not in candidate_evidence_ids for item in ids):
            raise ContractError(f"候选 {name} 的 evidence_bindings.{field} 引用了候选证据范围外的 ID")
        return [evidence[item] for item in ids]

    dimension_sources = {key: bound_evidence(key) for key in required_dimensions}
    activity_sources = bound_evidence("activity_status")
    substitute_sources = bound_evidence("direct_substitute")
    purchase_set_sources = bound_evidence("same_purchase_set")
    position_sources = bound_evidence("market_position")
    recent_position_sources = [
        item for item in position_sources
        if item["source_type"] != "official"
        and item["published_date"]
        and (current_date - item["published_date"]).days <= 548
    ]

    reasons = []
    if domain == config["target"]["official_domain"] or name.casefold() == config["target"]["name"].casefold():
        reasons.append("候选与监测对象重复")
    for key in missing_dimensions:
        reasons.append(f"评分维度 {key} 缺失，按 0 分降级")
    if candidate.get("activity_status") != "active":
        reasons.append("当前活跃状态未确认")
    if candidate.get("direct_substitute") is not True:
        reasons.append("不能直接替代监测对象的核心任务")
    if values["sub_track"] < 4:
        reasons.append("细分赛道一致性不足")
    if values["core_job"] < 4:
        reasons.append("核心任务一致性不足")
    if values["product_form"] < 3:
        reasons.append("产品或服务形态差异过大")
    if values["target_users"] < 3:
        reasons.append("目标用户重叠不足")
    if not official:
        reasons.append("缺少与官网域名一致的官方证据")
    elif not current_official:
        reasons.append("官网活跃状态缺少近 30 天访问证据")
    if not independent:
        reasons.append("缺少独立来源证据")
    if not activity_sources or not any(item in current_official for item in activity_sources):
        reasons.append("活跃状态未绑定近期官网证据")
    if not substitute_sources:
        reasons.append("直接替代关系缺少绑定证据")
    for key in required_dimensions:
        if not dimension_sources[key]:
            reasons.append(f"评分维度 {key} 缺少绑定证据")
    if market_position in {"leader", "peer", "challenger"} and not recent_position_sources:
        reasons.append("市场地位缺少近 18 个月独立证据")

    purchase_set_reasons = []
    if domain == config["target"]["official_domain"] or name.casefold() == config["target"]["name"].casefold():
        purchase_set_reasons.append("候选与监测对象重复")
    if candidate.get("same_purchase_set") is not True:
        purchase_set_reasons.append("未确认会进入同一次购买决策")
    if not purchase_set_sources:
        purchase_set_reasons.append("同一购买集合缺少绑定证据")
    elif not any(item["source_type"] != "official" for item in purchase_set_sources):
        purchase_set_reasons.append("同一购买集合缺少独立来源证据")
    if candidate.get("direct_substitute") is not True or not substitute_sources:
        purchase_set_reasons.append("直接替代关系未确认或缺少绑定证据")
    if candidate.get("activity_status") != "active" or not current_official:
        purchase_set_reasons.append("当前活跃官网未确认")
    if not activity_sources or not any(item in current_official for item in activity_sources):
        purchase_set_reasons.append("活跃状态未绑定近期官网证据")
    purchase_thresholds = {
        "sub_track": 4,
        "core_job": 4,
        "product_form": 3,
        "target_users": 3,
        "buying_motion": 3,
    }
    for key, minimum in purchase_thresholds.items():
        if values[key] < minimum:
            purchase_set_reasons.append(f"{key} 未达到同一购买集合门槛 {minimum}")
        if not dimension_sources[key]:
            purchase_set_reasons.append(f"{key} 缺少购买集合判断证据")
    same_purchase_set_eligible = not purchase_set_reasons

    weighted = (
        values["sub_track"] * 5
        + values["core_job"] * 5
        + values["product_form"] * 3
        + values["target_users"] * 3
        + values["buying_motion"] * 2
        + values["status_similarity"] * 2
        + values["specialty_fit"] * 2
    )
    comparability = round(weighted / 110 * 60, 2)
    position_points = {"leader": 20, "peer": 16, "challenger": 14, "unknown": 6}[market_position]
    independent_domains = len({item["host"] for item in independent})
    evidence_points = min(5, len(official) * 5) + min(8, independent_domains * 4) + (5 if recent_position_sources else 0) + (2 if len(recent_position_sources) >= 2 else 0)
    total = round(min(100, comparability + position_points + evidence_points), 2)
    if total < 65:
        reasons.append("综合得分低于 65 分")
    direct = not reasons
    adjacent = (
        not direct
        and bool(official)
        and candidate.get("activity_status") == "active"
        and (values["sub_track"] >= 3 or values["core_job"] >= 3)
        and values["product_form"] >= 2
        and values["target_users"] >= 2
        and domain != config["target"]["official_domain"]
        and name.casefold() != config["target"]["name"].casefold()
    )
    comparability_tier = "direct" if direct else "adjacent" if adjacent else "fallback"
    common_dimensions = [
        key for key in required_dimensions
        if values[key] >= 3 and bool(dimension_sources[key])
    ]
    return {
        "candidate": candidate,
        "canonical_name": name,
        "official_domain": domain,
        "qualified": direct,
        "reasons": reasons,
        "scores": {
            "comparability": comparability,
            "market_position": position_points,
            "evidence_quality_and_recency": evidence_points,
            "total": total,
        },
        "market_position": market_position,
        "leader_representativeness_verified": (
            market_position == "leader" and bool(recent_position_sources)
        ),
        "status_similarity": values["status_similarity"],
        "specialty_fit": values["specialty_fit"],
        "source": "user_provided" if matched_known_index is not None else "discovered",
        "matched_known_index": matched_known_index,
        "same_purchase_set_eligible": same_purchase_set_eligible,
        "purchase_set_reasons": purchase_set_reasons,
        "comparability_tier": comparability_tier,
        "common_dimensions": common_dimensions,
        "aliases": aliases,
        "evidence_ids": candidate_evidence_ids,
    }


def portfolio_role(item):
    if item["source"] == "user_provided":
        return "销售指定竞品"
    if item["comparability_tier"] == "adjacent":
        return "相邻可比竞品"
    if item["comparability_tier"] == "fallback":
        return "降级补足竞品"
    if item["market_position"] == "leader":
        return "头部直接竞品"
    if item["market_position"] == "challenger":
        return "垂直挑战者"
    if item["market_position"] == "peer" or item["status_similarity"] >= 4:
        return "同层级直接竞品"
    return "直接竞品"


def choose_portfolio(scored, config):
    selected = []
    selected_domains = set()

    def add(item):
        selected.append({**item, "portfolio_role": portfolio_role(item)})
        selected_domains.add(item["official_domain"])

    for known_index, known in enumerate(config["known_competitors"]):
        matches = [
            item for item in scored
            if item["matched_known_index"] == known_index and item["same_purchase_set_eligible"]
        ]
        if not matches:
            continue
        matches.sort(key=lambda item: (-item["scores"]["total"], item["canonical_name"].casefold()))
        add(matches[0])

    remaining = [
        item for item in scored
        if item["same_purchase_set_eligible"] and item["official_domain"] not in selected_domains
    ]

    def automatic_fill_key(item):
        return (
            0 if item["leader_representativeness_verified"] else 1,
            -item["scores"]["total"],
            item["canonical_name"].casefold(),
        )

    for picked in sorted(remaining, key=automatic_fill_key):
        if len(selected) >= 3:
            break
        add(picked)
    return selected[:3]


def finalize(config, research):
    if research.get("input_hash") != config["input_hash"]:
        raise ContractError("research.input_hash 与冻结输入不一致")
    researched_at = parse_date(research.get("researched_at"), "researched_at")
    if abs((date.fromisoformat(config["current_date"]) - researched_at).days) > 7:
        raise ContractError("researched_at 与 current_date 相差超过 7 天")
    evidence = evidence_index(research, config)
    candidates = research.get("candidates") or []
    if not isinstance(candidates, list):
        raise ContractError("candidates 必须是数组")
    scored = [score_candidate(item, evidence, config) for item in candidates]
    domains = [item["official_domain"] for item in scored if item.get("official_domain")]
    if len(domains) != len(set(domains)):
        raise ContractError("候选中存在重复官网域名")
    eligible = [item for item in scored if item["same_purchase_set_eligible"]]
    if len(eligible) < 3:
        raise ContractError("同一购买集合的合格候选少于 3 个；请继续自动检索并重跑，不能用相邻产品或不同购买决策的品牌补位")
    selected = choose_portfolio(scored, config)
    if len(selected) != 3:
        raise ContractError("未能自动补足 3 个竞品；请扩大自动候选池并重跑，不能返回 needs_manual_input")
    prohibited_claims = ["无证据的全面优劣", "绝对排名", "无证据的全面替代关系", "无证据的领先结论"]

    def comparison_policy(item):
        return {
            "mode": "standard_evidence_based",
            "allowed_dimensions": item["common_dimensions"],
            "prohibited_claims": prohibited_claims,
        }

    tiers = [item["comparability_tier"] for item in selected]
    portfolio_quality = "fallback-heavy" if "fallback" in tiers else "mixed" if "adjacent" in tiers else "direct"
    warnings = []
    for item in selected:
        if item["comparability_tier"] != "direct":
            allowed = ", ".join(item["common_dimensions"]) or "无已验证共同能力维度"
            warnings.append(
                f"{item['canonical_name']} 以 {item['comparability_tier']} 级别保留或补足；仅允许中性比较：{allowed}"
            )
    output = {
        "schema_version": "overseas-geo-competitor-selection/v2",
        "input_hash": config["input_hash"],
        "researched_at": researched_at.isoformat(),
        "ruleset_version": config["ruleset_version"],
        "status": "frozen",
        "selection_count": 3,
        "selection_strategy": {
            "primary_order": [
                "same_purchase_set_gate",
                "eligible_user_provided_first",
                "leader_representativeness",
                "total_score",
            ],
            "user_provided_count": len(config["known_competitors"]),
            "user_provided_retained": all(
                any(
                    item["matched_known_index"] == known_index and item["same_purchase_set_eligible"]
                    for item in scored
                )
                for known_index in range(len(config["known_competitors"]))
            ),
            "discovery_mode": "from_scratch" if not config["known_competitors"] else "verify_and_fill",
            "automatic_fill_policy": "same_purchase_set_only_then_verified_leaders_then_total_score",
        },
        "portfolio_quality": portfolio_quality,
        "degraded": portfolio_quality != "direct",
        "formal_competitors": [
            {
                "name": item["canonical_name"],
                "official_domain": item["official_domain"],
                "aliases": item["aliases"],
                "source": item["source"],
                "portfolio_role": item["portfolio_role"],
                "market_position": item["market_position"],
                "leader_representativeness_verified": item["leader_representativeness_verified"],
                "same_purchase_set_eligible": item["same_purchase_set_eligible"],
                "comparability_tier": item["comparability_tier"],
                "score": item["scores"]["total"],
                "evidence_ids": item["evidence_ids"],
                "limitations": item["reasons"],
                "comparison_policy": comparison_policy(item),
            }
            for item in selected
        ],
        "provided_competitor_rejections": [
            {
                "name": known["name"],
                "official_domain": known.get("official_domain"),
                "reasons": (
                    next(
                        (
                            item["purchase_set_reasons"]
                            for item in scored
                            if item["matched_known_index"] == known_index
                        ),
                        ["研究候选池未找到匹配项"],
                    )
                ),
            }
            for known_index, known in enumerate(config["known_competitors"])
            if not any(
                item["matched_known_index"] == known_index and item["same_purchase_set_eligible"]
                for item in scored
            )
        ],
        "candidate_audit": [
            {
                "name": item.get("canonical_name") or (item.get("candidate") or {}).get("canonical_name"),
                "official_domain": item.get("official_domain"),
                "source": item.get("source"),
                "qualified": item["qualified"],
                "comparability_tier": item.get("comparability_tier"),
                "leader_representativeness_verified": item.get("leader_representativeness_verified"),
                "same_purchase_set_eligible": item.get("same_purchase_set_eligible"),
                "purchase_set_reasons": item.get("purchase_set_reasons"),
                "limitations": item["reasons"],
                "scores": item.get("scores"),
                "selected": item["official_domain"] in {selected_item["official_domain"] for selected_item in selected},
            }
            for item in scored
        ],
        "evidence": [
            {key: value for key, value in item.items() if key not in {"accessed_date", "published_date"}}
            for item in evidence.values()
        ],
        "question_generation_guardrails": {
            "low_comparability_mode": "neutral_shared_dimensions_only",
            "when_no_allowed_dimensions": "仅生成品类关系或使用场景澄清题，不生成能力强弱比较",
            "prohibited_claims": prohibited_claims,
        },
        "warnings": warnings,
    }
    output["selection_hash"] = digest(output)
    return output


def command_prepare(args):
    root = Path(args.run_dir).expanduser().resolve()
    if root.exists() and any(root.iterdir()):
        raise ContractError(f"运行目录非空：{root}")
    root.mkdir(parents=True, exist_ok=True)
    config = normalize_input(read_json(args.input))
    plan = build_plan(config)
    write_json(root / "input.json", config)
    write_json(root / "research-plan.json", plan)
    return {"run_dir": str(root), "input_hash": config["input_hash"], "research_plan": str(root / "research-plan.json")}


def command_finalize(args):
    root = Path(args.run_dir).expanduser().resolve()
    config = read_json(root / "input.json")
    result = finalize(config, read_json(args.research))
    write_json(root / "competitor-selection.json", result)
    return {"status": result["status"], "selection_count": result["selection_count"], "output": str(root / "competitor-selection.json")}


def build_parser():
    parser = argparse.ArgumentParser(prog="competitor_research", description="海外 GEO 售前竞品研究与冻结工具")
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare", help="冻结输入并生成联网检索计划")
    prepare.add_argument("--input", required=True)
    prepare.add_argument("--run-dir", required=True)
    prepare.set_defaults(func=command_prepare)
    finalize_parser = sub.add_parser("finalize", help="校验研究证据并自动选择三个竞品")
    finalize_parser.add_argument("--run-dir", required=True)
    finalize_parser.add_argument("--research", required=True)
    finalize_parser.set_defaults(func=command_finalize)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        result = args.func(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ContractError, FileNotFoundError, json.JSONDecodeError) as error:
        print(json.dumps({"error": type(error).__name__, "message": str(error)}, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
