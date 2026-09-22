from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .config import all_objects
from .util import (
    domain_matches,
    find_alias_spans,
    normalize_host,
    normalize_url,
    sha256_obj,
    write_text,
)


SOURCE_TYPES = {
    # 现行 7 类，以《引用来源分类》定义为准。旧版的 corporate_site（企业网站）已取消：
    # 未命中默认类别的企业网站归入 other；开放竞品官网也不进 competitor_official。
    "brand_official": "自有网站",
    "competitor_official": "竞品网站",
    "ugc": "社交平台",
    "media_review": "媒体网站",
    "press_release": "新闻稿平台",
    "institutional": "机构网站",
    "other": "其他",
}

# 已从 SOURCE_TYPES 退休的类别 → 现行类别，按《引用来源分类》的迁移口径。
# 百科类归「机构网站」（政府/非营利/教育/公共机构），企业网站归「其他」。
RETIRED_SOURCE_TYPES = {
    "encyclopedia_reference": "institutional",
    "corporate_site": "other",
}


KNOWN_HOST_TYPES = {
    # 机构网站（Institutions）：政府、非营利组织、教育机构和公共机构的网站。
    # .gov / .edu 由 _known_type 的后缀规则兜住；这里放经确认的高频机构域名
    # （who.int、wikipedia.org、wikimedia.org 等）。
    "baike.baidu.com": "institutional",
    "who.int": "institutional",
    "reddit.com": "ugc",
    "youtube.com": "ugc",
    "facebook.com": "ugc",
    "instagram.com": "ugc",
    "tiktok.com": "ugc",
    "x.com": "ugc",
    "twitter.com": "ugc",
    "quora.com": "ugc",
    "wikipedia.org": "institutional",
    "wikimedia.org": "institutional",
    "wikidata.org": "institutional",
    "britannica.com": "institutional",
    "reuters.com": "media_review",
    "apnews.com": "media_review",
    "forbes.com": "media_review",
    "techcrunch.com": "media_review",
    "searchenginejournal.com": "media_review",
    "g2.com": "media_review",
    "capterra.com": "media_review",
    "trustpilot.com": "media_review",
    "bbb.org": "media_review",
    "github.com": "other",
    "linkedin.com": "other",
}


def _known_type(host: str, cache: dict | None = None) -> str | None:
    """域名 → 来源类别。

    分类不是封闭集合：`KNOWN_HOST_TYPES` 只放稳定的高频域名，其余走运行时缓存
    （`config["domain_category_cache"]`）。缓存由报告侧按实际链接判读后写回，
    每次运行都会把新出现的域名补进去，因此覆盖度随运行增长。

    历史值兜底：`corporate_site`、`encyclopedia_reference` 等已从 `SOURCE_TYPES`
    退休的分类按迁移口径归并（见 `RETIRED_SOURCE_TYPES`），其余无法识别的值落到
    「其他」。内置表与运行时缓存两条路径都要过一遍——缓存里同样可能残留旧值，
    否则 `SOURCE_TYPES[known]` 会直接 KeyError 打断整条构建。
    """
    def _valid(source_type: str | None) -> str | None:
        if source_type is None:
            return None
        if source_type in SOURCE_TYPES:
            return source_type
        return RETIRED_SOURCE_TYPES.get(source_type, "other")

    for known, source_type in KNOWN_HOST_TYPES.items():
        if host == known or host.endswith("." + known):
            return _valid(source_type)
    if cache:
        for known, source_type in cache.items():
            if host == known or host.endswith("." + known):
                return _valid(source_type)
    if host.endswith(".gov") or ".gov." in host or host.endswith(".edu") or ".edu." in host:
        return "institutional"
    return None


def _classify_official(host: str, objects: list[dict]) -> tuple[str | None, str | None]:
    for obj in objects:
        for domain in obj["official_domains"]:
            if domain_matches(host, domain):
                return ("brand_official" if obj["role"] == "target" else "competitor_official", obj["object_id"])
    return None, None


def choose_representative_samples(samples: list[dict], questions: list[dict]) -> tuple[dict[str, str | None], list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for sample in samples:
        grouped[sample["question_id"]].append(sample)
    selected: dict[str, str | None] = {}
    issues: list[dict] = []
    for question in questions:
        candidates = sorted(grouped.get(question["question_id"], []), key=lambda item: (item["repeat_index"], item["sample_id"]))
        valid = [item for item in candidates if item["analysis_eligible"]]
        chosen = valid[0] if valid else (candidates[0] if candidates else None)
        selected[question["question_id"]] = chosen["sample_id"] if chosen else None
        if len(valid) > 1:
            issues.append({
                "code": "MULTIPLE_VALID_REPEATS_FIRST_SELECTED",
                "question_id": question["question_id"],
                "selected_sample_id": chosen["sample_id"],
                "valid_sample_ids": [item["sample_id"] for item in valid],
            })
    return selected, issues


def prepare_answers(run_root: Path, config: dict, question_bank: dict, crawl: dict) -> dict:
    question_by_id = {item["question_id"]: item for item in question_bank["questions"]}
    selected, issues = choose_representative_samples(crawl["samples"], question_bank["questions"])
    answers: list[dict] = []
    unknown_hosts: dict[str, dict] = {}

    for sample in crawl["samples"]:
        question = question_by_id[sample["question_id"]]
        answer_text = sample.get("answer_text") or ""
        # 品牌匹配跑在去引用正文上（`ranking_text`，由上游剥离引用标记与商品卡商家列）；
        # 缺该字段时回落到原文以保持旧输入可用。理由见 build_report_data.py 的 de_cite
        # 注释：被引文章标题里的品牌不该算成回答提及。
        matching_text = sample.get("ranking_text") or answer_text
        evidence_path = run_root / "evidence/answers" / f"{sample['sample_id']}.txt"
        write_text(evidence_path, answer_text)
        object_records = []
        for obj in all_objects(config):
            spans = find_alias_spans(matching_text, obj["aliases"]) if sample["analysis_eligible"] else []
            object_records.append({
                "object_id": obj["object_id"],
                "canonical_name": obj["canonical_name"],
                "role": obj["role"],
                "mentioned": bool(spans),
                "matched_aliases": sorted({span["alias"] for span in spans}),
                "match_spans": spans,
                "first_position": spans[0]["start"] if spans else None,
                "mention_order": None,
                "recommendation_rank": None,
                "report_rank": None,
                "sentiment": "not_applicable" if not spans else None,
                "sentiment_score": None,
                "sentiment_confidence": None,
                "sentiment_evidence": [],
                "sentiment_status": "not_applicable" if not spans else "pending",
            })
        mentioned = sorted(
            [item for item in object_records if item["mentioned"]],
            key=lambda item: (item["first_position"], next(obj["display_order"] for obj in config["objects"] if obj["object_id"] == item["object_id"])),
        )
        for rank, item in enumerate(mentioned, 1):
            item["mention_order"] = rank
            item["report_rank"] = rank

        citations = []
        for raw in sample.get("citations") or []:
            normalized = normalize_url(raw.get("raw_url")) if raw.get("raw_url") else None
            row = dict(raw)
            row.update({
                "canonical_url": normalized.get("canonical_url") if normalized else None,
                "host": normalized.get("host") if normalized else normalize_host(raw.get("domain_hint")),
                "registrable_domain": normalized.get("registrable_domain") if normalized else None,
                "removed_query_params": normalized.get("removed_query_params") if normalized else [],
                "normalization_status": "normalized" if normalized else "failed",
                "source_type": "other",
                "source_type_name": SOURCE_TYPES["other"],
                "matched_official_object_id": None,
                "classification_source": "default_other",
                "classification_confidence": None,
            })
            if row["host"]:
                source_type, object_id = _classify_official(row["host"], all_objects(config))
                if source_type:
                    row.update({
                        "source_type": source_type,
                        "source_type_name": SOURCE_TYPES[source_type],
                        "matched_official_object_id": object_id,
                        "classification_source": "official_rule",
                        "classification_confidence": 1.0,
                    })
                else:
                    known = _known_type(row["host"], config.get("domain_category_cache"))
                    if known:
                        row.update({
                            "source_type": known,
                            "source_type_name": SOURCE_TYPES[known],
                            "classification_source": "domain_rule",
                            "classification_confidence": 0.95,
                        })
                    elif normalized and selected.get(sample["question_id"]) == sample["sample_id"]:
                        host_item = unknown_hosts.setdefault(row["host"], {
                            "host": row["host"],
                            "sample_urls": [],
                            "titles": [],
                            "snippets": [],
                            "citation_ids": [],
                        })
                        if row["canonical_url"] and row["canonical_url"] not in host_item["sample_urls"]:
                            host_item["sample_urls"].append(row["canonical_url"])
                        if row.get("title") and row["title"] not in host_item["titles"]:
                            host_item["titles"].append(row["title"])
                        if row.get("summary") and row["summary"] not in host_item["snippets"]:
                            host_item["snippets"].append(row["summary"])
                        host_item["citation_ids"].append(row["raw_citation_id"])
            citations.append(row)

        answers.append({
            "answer_id": sample["sample_id"],
            "sample_id": sample["sample_id"],
            "question_id": sample["question_id"],
            "question_text": question["question_text"],
            "question_zh": question.get("question_zh"),
            "question_type": question["question_type"],
            "funnel_intent": question["funnel_intent"],
            "diagnostic_intent": question.get("diagnostic_intent"),
            "analysis_type": question.get("analysis_type"),
            "metric_scopes": question.get("metric_scopes"),
            "topic_id": question.get("topic_id"),
            "attribute_ids": question.get("attribute_ids") or [],
            "generation_sequence": question["generation_sequence"],
            "repeat_index": sample["repeat_index"],
            "selected_for_report": selected.get(sample["question_id"]) == sample["sample_id"],
            "validity": "valid" if sample["analysis_eligible"] else "invalid",
            "validity_reason": None if sample["analysis_eligible"] else sample.get("error_code"),
            "answer_text": sample.get("answer_text"),
            "answer_zh": None,
            "translation_status": "not_requested",
            "evidence_ref": str(evidence_path.relative_to(run_root)),
            "objects": object_records,
            "citations": citations,
            "provenance": sample.get("provenance"),
        })

    unknown_items = {}
    for index, host in enumerate(sorted(unknown_hosts), 1):
        item = unknown_hosts[host]
        item["sample_urls"] = item["sample_urls"][:3]
        item["titles"] = item["titles"][:3]
        item["snippets"] = item["snippets"][:3]
        unknown_items[f"S-{index:03d}"] = item

    return {
        "schema_version": "geo-presales-answers/v1",
        "run_id": config["run_id"],
        "rank_policy": config["rank_policy"],
        "sample_policy": config["sample_policy"],
        "selected_samples": selected,
        "issues": issues,
        "answers": answers,
        "unknown_source_items": unknown_items,
        "answers_hash": sha256_obj(answers),
    }
