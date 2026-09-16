from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal, ROUND_HALF_UP

from .config import all_objects
from .deterministic import SOURCE_TYPES
from .util import sha256_obj


INTENT_PRIORITY = {"decision": 0, "comparison": 1, "recommendation": 2}


def _percent(numerator: int, denominator: int, digits: int = 0) -> dict:
    if denominator == 0:
        return {"numerator": numerator, "denominator": denominator, "raw": None, "display": "—"}
    raw = Decimal(numerator) / Decimal(denominator)
    quant = Decimal("1") if digits == 0 else Decimal("1." + "0" * digits)
    display_value = (raw * Decimal(100)).quantize(quant, rounding=ROUND_HALF_UP)
    display_number = format(display_value, "f").rstrip("0").rstrip(".") if digits else str(int(display_value))
    return {"numerator": numerator, "denominator": denominator, "raw": float(raw), "display": display_number + "%"}


def _average(values: list[int], digits: int = 1) -> dict:
    if not values:
        return {"numerator": 0, "denominator": 0, "raw": None, "display": "—"}
    raw = Decimal(sum(values)) / Decimal(len(values))
    quant = Decimal("1." + "0" * digits)
    displayed = raw.quantize(quant, rounding=ROUND_HALF_UP)
    return {"numerator": sum(values), "denominator": len(values), "raw": float(raw), "display": f"#{displayed}"}


def _valid_answers(answers_doc: dict) -> list[dict]:
    """指标样本 = 全部有效回答。

    不再按 ``selected_for_report`` 过滤：那个字段的含义是「每题展示哪一条」，属于呈现选择，
    不该同时决定算哪一条。重复采集时每题有 N 条有效回答，N 条全部进分母——只取一条会丢掉
    重复采集的意义（15 次里提到 3 次，与只测 1 次提到 1 次不是一回事）。
    代表样本仍由 ``selected_for_report`` 标记，供明细展示与任务生成使用。
    """
    return [item for item in answers_doc["answers"] if item["validity"] == "valid"]


def _object(answer: dict, object_id: str) -> dict:
    return next(item for item in answer["objects"] if item["object_id"] == object_id)


def _diagnostic_intents(answer: dict) -> set[str]:
    values = answer.get("diagnostic_intents")
    if isinstance(values, list):
        return {str(value).strip() for value in values if str(value).strip()}
    value = str(answer.get("diagnostic_intent") or "").strip()
    return {value} if value else set()


def _metric_scopes(answer: dict) -> set[str]:
    values = answer.get("metric_scopes")
    if isinstance(values, list):
        return {str(value).strip() for value in values if str(value).strip()}
    value = str(values or "").strip()
    return {value} if value else set()


def _is_formal_visibility_answer(answer: dict) -> bool:
    """正式可见度样本 = **Discovery 意图**（Suda 2026-09-16 裁定）。

    只按「分析类型含 visibility」判定会多收品类认知题——本题库里 2 道
    category_awareness 题带着 `visibility,sentiment`，而那 2 道按
    `canonical-intent-mapping.md`「报告侧正式 Visibility 指标只使用 Discovery」
    不应进入可见度。诊断意图是权威判据。

    `analysis_type` 只作为意图缺失时（旧数据）的回落，不再单独决定样本资格。

    | 诊断意图 | 是否进正式可见度 |
    |---|---|
    | discovery | 是 |
    | competitor / evaluation / case category_awareness / accuracy / verification | 否 |
    """
    intents = _diagnostic_intents(answer)
    if intents:
        return "discovery" in intents
    analysis_type = str(answer.get("analysis_type") or "").strip().casefold()
    if analysis_type:
        return "visibility" in {part.strip() for part in analysis_type.split(",") if part.strip()}
    return answer.get("question_type") == "generic"


def _is_sentiment_answer(answer: dict) -> bool:
    """情绪样本口径：`analysis_type` 中**包含** sentiment 即计入。

    canonical-intent-mapping 要求「后端已标记为 Sentiment 的样本必须进入 M05 评价/情绪聚合」，
    因此 Discovery 的 `visibility,sentiment` 必须计入；按精确相等比较会整批漏掉。
    """
    analysis_type = str(answer.get("analysis_type") or "").strip().casefold()
    if analysis_type:
        return "sentiment" in {part.strip() for part in analysis_type.split(",") if part.strip()}
    # Legacy payloads did not carry analysis_type. Explicit sentiment scope
    # markers remain a compatibility fallback only when that field is absent.
    scopes = _metric_scopes(answer)
    if "sentiment" in scopes:
        return True
    intents = _diagnostic_intents(answer)
    if "sentiment" in intents:
        return True
    return not intents and not scopes and answer.get("question_type") == "branded"


def _benchmark(objects: list[dict], values: dict[str, dict], higher_is_better: bool) -> dict:
    competitors = [obj for obj in objects if obj["role"] == "competitor" and values[obj["object_id"]]["raw"] is not None]
    if not competitors:
        return {"best_value": None, "selected_competitor_id": None, "tied_competitor_ids": [], "display": "—"}
    key = max if higher_is_better else min
    best = key(values[obj["object_id"]]["raw"] for obj in competitors)
    tied = [obj for obj in competitors if values[obj["object_id"]]["raw"] == best]
    tied.sort(key=lambda obj: obj["display_order"])
    selected = tied[0]
    return {
        "best_value": best,
        "selected_competitor_id": selected["object_id"],
        "selected_competitor_name": selected["canonical_name"],
        "tied_competitor_ids": [obj["object_id"] for obj in tied],
        "display": values[selected["object_id"]]["display"],
    }


def _opportunity_sort_key(item: dict):
    intent = INTENT_PRIORITY[item["funnel_intent"]]
    if item["bucket"] == "priority_improve":
        return (intent, item["generation_sequence"])
    if item["bucket"] == "continue_optimize":
        return (intent, 0 if not item["mentioned"] else 1, -(item["report_rank"] or 999), item["generation_sequence"])
    return (intent, item["report_rank"] or 999, item["generation_sequence"])


def compute_metrics(config: dict, question_bank: dict, answers_doc: dict) -> dict:
    valid_answers = _valid_answers(answers_doc)
    discovery = [item for item in valid_answers if _is_formal_visibility_answer(item)]
    sentiment_answers = [item for item in valid_answers if _is_sentiment_answer(item)]
    target_id = config["target_object_id"]

    object_metrics = {}
    mention_values = {}
    rank_values = {}
    mention_counts = {}
    for obj in all_objects(config):
        included = [answer for answer in discovery if _object(answer, obj["object_id"])["mentioned"]]
        mention_counts[obj["object_id"]] = len(included)
        mention_values[obj["object_id"]] = _percent(len(included), len(discovery))
        mention_values[obj["object_id"]]["included_answer_ids"] = [item["answer_id"] for item in included]
        ranks = [_object(answer, obj["object_id"])["report_rank"] for answer in included]
        rank_values[obj["object_id"]] = _average(ranks)
        rank_values[obj["object_id"]]["included_answer_ids"] = [item["answer_id"] for item in included]

    total_mentions = sum(mention_counts.values())
    voice_values = {object_id: _percent(count, total_mentions) for object_id, count in mention_counts.items()}
    for obj in all_objects(config):
        object_metrics[obj["object_id"]] = {
            "object_id": obj["object_id"],
            "name": obj["canonical_name"],
            "role": obj["role"],
            "mention_rate": mention_values[obj["object_id"]],
            "share_of_voice": voice_values[obj["object_id"]],
            "average_rank": rank_values[obj["object_id"]],
        }

    mentioned_target = [answer for answer in sentiment_answers if _object(answer, target_id)["mentioned"]]
    resolved_sentiments = [
        _object(answer, target_id)["sentiment"]
        for answer in mentioned_target
        if _object(answer, target_id)["sentiment_status"] == "accepted"
    ]
    unresolved_sentiment_ids = [
        answer["answer_id"] for answer in mentioned_target
        if _object(answer, target_id)["sentiment_status"] != "accepted"
    ]
    sentiment_counts = Counter(resolved_sentiments)
    positive_ratio = _percent(sentiment_counts["positive"], sentiment_counts["positive"] + sentiment_counts["negative"])
    expression_distribution = {
        label: _percent(sentiment_counts[label], len(resolved_sentiments))
        for label in ("positive", "neutral", "negative")
    }

    raw_citations = [citation for answer in discovery for citation in answer["citations"]]
    official_raw = [citation for citation in raw_citations if citation.get("matched_official_object_id") == target_id]
    official_share = _percent(len(official_raw), len(raw_citations))
    official_share["included_citation_ids"] = [item["raw_citation_id"] for item in official_raw]
    official_share["all_citation_ids"] = [item["raw_citation_id"] for item in raw_citations]

    deduped = {}
    for answer in discovery:
        for citation in answer["citations"]:
            canonical = citation.get("canonical_url")
            if canonical:
                deduped.setdefault((answer["answer_id"], canonical), citation)
    source_counts = Counter(item["source_type"] for item in deduped.values())
    source_distribution = {
        source_type: {
            **_percent(source_counts[source_type], len(deduped)),
            "label": label,
        }
        for source_type, label in SOURCE_TYPES.items()
    }

    domain_answers: dict[str, set[str]] = defaultdict(set)
    page_answers: dict[str, set[str]] = defaultdict(set)
    official_pages: dict[str, set[str]] = defaultdict(set)
    for (answer_id, canonical_url), citation in deduped.items():
        domain = citation.get("registrable_domain") or citation.get("host")
        if domain:
            domain_answers[domain].add(answer_id)
        page_answers[canonical_url].add(answer_id)
        if citation.get("matched_official_object_id") == target_id:
            official_pages[canonical_url].add(answer_id)
    top_domains = [
        {"domain": domain, "answer_count": len(answer_ids)}
        for domain, answer_ids in sorted(domain_answers.items(), key=lambda pair: (-len(pair[1]), pair[0]))[:8]
    ]
    top_pages = [
        {"url": url, "answer_count": len(answer_ids)}
        for url, answer_ids in sorted(page_answers.items(), key=lambda pair: (-len(pair[1]), pair[0]))[:8]
    ]
    brand_official_pages = [
        {"url": url, "answer_count": len(answer_ids)}
        for url, answer_ids in sorted(official_pages.items(), key=lambda pair: (-len(pair[1]), pair[0]))[:8]
    ]

    opportunities = {"priority_improve": [], "continue_optimize": [], "stable": []}
    for answer in discovery:
        target = _object(answer, target_id)
        if not target["mentioned"]:
            bucket = "priority_improve"
            reason = "target_absent_commercial_intent"
        elif target["report_rank"] >= 4:
            bucket = "continue_optimize"
            reason = "target_rank_four_or_later"
        else:
            bucket = "stable"
            reason = "target_rank_one_to_three"
        opportunities[bucket].append({
            "question_id": answer["question_id"],
            "answer_id": answer["answer_id"],
            "question_text": answer["question_text"],
            "question_zh": answer.get("question_zh"),
            "funnel_intent": answer["funnel_intent"],
            "generation_sequence": answer["generation_sequence"],
            "mentioned": target["mentioned"],
            "report_rank": target["report_rank"],
            "bucket": bucket,
            "reason": reason,
        })
    opportunity_counts = {key: len(value) for key, value in opportunities.items()}
    opportunity_display = {}
    for key, items in opportunities.items():
        items.sort(key=_opportunity_sort_key)
        opportunity_display[key] = items[:3]

    benchmarks = {
        "mention_rate": _benchmark(config["objects"], mention_values, True),
        "share_of_voice": _benchmark(config["objects"], voice_values, True),
        "average_rank": _benchmark(config["objects"], rank_values, False),
    }
    target_metrics = object_metrics[target_id]
    directions = []
    best_mention = benchmarks["mention_rate"]
    priority_share = opportunity_counts["priority_improve"] / len(discovery) if discovery else None
    mention_gap = (best_mention["best_value"] - target_metrics["mention_rate"]["raw"]) if best_mention["best_value"] is not None and target_metrics["mention_rate"]["raw"] is not None else None
    if discovery:
        if (mention_gap is not None and mention_gap >= 0.10) or (priority_share is not None and priority_share >= 0.20):
            state, posture = "absent", "补齐"
        else:
            best_rank = benchmarks["average_rank"]
            rank_gap = (target_metrics["average_rank"]["raw"] - best_rank["best_value"]) if target_metrics["average_rank"]["raw"] is not None and best_rank["best_value"] is not None else None
            if rank_gap is not None and rank_gap >= 1.0:
                state, posture = "position_lag", "提升"
            else:
                state, posture = "no_significant_gap", "保持"
        directions.append({
            "direction_id": "D-brand-entry",
            "direction": "brand_entry",
            "source_module": "M05",
            "state": state,
            "posture": posture,
            "fact_refs": [
                "fact:opportunity.counts.priority_improve",
                "fact:overview.target.mention_rate",
            ],
        })

    if raw_citations:
        if official_share["raw"] < 0.10:
            state, posture = "weak", "补强"
        elif len(brand_official_pages) <= 2:
            state, posture = "insufficient_coverage", "扩展"
        else:
            state, posture = "stable", "保持"
        directions.append({
            "direction_id": "D-citation-evidence",
            "direction": "citation_evidence",
            "source_module": "M03",
            "state": state,
            "posture": posture,
            "fact_refs": [
                "fact:citations.official_share",
                "fact:citations.official_page_count",
            ],
        })

    if mentioned_target and resolved_sentiments:
        negative = expression_distribution["negative"]["raw"]
        positive = expression_distribution["positive"]["raw"]
        if negative is not None and negative >= 0.15:
            state, posture = "risk", "澄清"
        elif positive is not None and positive < 0.50:
            state, posture = "flat", "强化"
        else:
            state, posture = "positive", "巩固"
        directions.append({
            "direction_id": "D-brand-expression",
            "direction": "brand_expression",
            "source_module": "M04",
            "state": state,
            "posture": posture,
            "fact_refs": [
                "fact:sentiment.expression_distribution.positive",
                "fact:sentiment.expression_distribution.negative",
            ],
        })

    metrics = {
        "schema_version": "geo-presales-metrics/v1",
        "run_id": config["run_id"],
        "input_hashes": {
            "config_hash": config["config_hash"],
            "question_bank_hash": question_bank["question_bank_hash"],
            "answers_hash": answers_doc["answers_hash"],
        },
        "coverage": {
            "designed_questions": len(question_bank["questions"]),
            "valid_answers": len(valid_answers),
            # 直接数无效回答。原先用「题数 − 有效回答数」在重复采集下会算出负数：
            # 每题 N 条重复时有效回答数可以大于题数。
            "invalid_or_missing_answers": sum(
                1 for item in answers_doc["answers"] if item["validity"] != "valid"
            ),
            "valid_discovery_answers": len(discovery),
        },
        "overview": {
            "target": object_metrics[target_id],
            "objects": object_metrics,
            "positive_sentiment_ratio": positive_ratio,
        },
        "benchmarks": benchmarks,
        "sentiment": {
            "resolved_mentioned_answers": len(resolved_sentiments),
            "unresolved_answer_ids": unresolved_sentiment_ids,
            "counts": {label: sentiment_counts[label] for label in ("positive", "neutral", "negative")},
            "positive_ratio_excluding_neutral": positive_ratio,
            "expression_distribution": expression_distribution,
        },
        "citations": {
            "raw_count": len(raw_citations),
            "normalized_dedup_count": len(deduped),
            "official_share": official_share,
            "source_type_distribution": source_distribution,
            "top_domains": top_domains,
            "top_pages": top_pages,
            "official_pages": brand_official_pages,
            "official_page_count": len(brand_official_pages),
        },
        "opportunity": {
            "counts": opportunity_counts,
            "all": opportunities,
            "display": opportunity_display,
        },
        "action_directions": directions[:3],
        "methodology": {
            "sample_policy": config["sample_policy"],
            "rank_policy": config["rank_policy"],
            "visibility_scope": "diagnostic_intents contains discovery; non-Discovery excluded even when another visibility-processing flag exists",
            "share_of_voice_denominator": "有效 Discovery 回答中各已配置对象提及次数之和",
            "sentiment_scope": "all analysis_type=sentiment records; no diagnostic_intent filter (legacy explicit sentiment scopes only when analysis_type is absent)",
            "positive_sentiment_denominator": "有效 Sentiment 回答中已完成判断的目标品牌正向与负向评价之和；排除中性",
            "citation_scope": "diagnostic_intent=discovery",
            "official_citation_denominator": "有效 Discovery 回答产生的原始引用记录",
            "source_type_denominator": "Discovery 引用按 answer_id 与 canonical_url 组合去重",
            "registrable_domain_resolver": "纯标准库常见多级域名后缀规则 v1",
        },
    }
    metrics["metrics_hash"] = sha256_obj(metrics)
    return metrics
