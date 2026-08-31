from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .util import (
    domain_matches,
    find_alias_spans,
    normalize_host,
    normalize_url,
    sha256_obj,
    write_text,
)


SOURCE_TYPES = {
    "brand_official": "品牌官网",
    "competitor_official": "竞品官网",
    "media_review": "媒体评测",
    "ugc": "用户生成内容",
    "corporate_site": "企业网站",
    "encyclopedia_reference": "百科与参考资料",
    "institutional": "机构网站",
    "other": "其他来源",
}


KNOWN_HOST_TYPES = {
    "reddit.com": "ugc",
    "youtube.com": "ugc",
    "facebook.com": "ugc",
    "instagram.com": "ugc",
    "tiktok.com": "ugc",
    "x.com": "ugc",
    "twitter.com": "ugc",
    "quora.com": "ugc",
    "wikipedia.org": "encyclopedia_reference",
    "wikidata.org": "encyclopedia_reference",
    "britannica.com": "encyclopedia_reference",
    "reuters.com": "media_review",
    "apnews.com": "media_review",
    "forbes.com": "media_review",
    "techcrunch.com": "media_review",
    "searchenginejournal.com": "media_review",
    "g2.com": "media_review",
    "capterra.com": "media_review",
    "trustpilot.com": "media_review",
    "bbb.org": "media_review",
    "github.com": "corporate_site",
    "linkedin.com": "corporate_site",
}


def _known_type(host: str) -> str | None:
    for known, source_type in KNOWN_HOST_TYPES.items():
        if host == known or host.endswith("." + known):
            return source_type
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
        evidence_path = run_root / "evidence/answers" / f"{sample['sample_id']}.txt"
        write_text(evidence_path, answer_text)
        object_records = []
        for obj in config["objects"]:
            spans = find_alias_spans(answer_text, obj["aliases"]) if sample["analysis_eligible"] else []
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
                source_type, object_id = _classify_official(row["host"], config["objects"])
                if source_type:
                    row.update({
                        "source_type": source_type,
                        "source_type_name": SOURCE_TYPES[source_type],
                        "matched_official_object_id": object_id,
                        "classification_source": "official_rule",
                        "classification_confidence": 1.0,
                    })
                else:
                    known = _known_type(row["host"])
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
