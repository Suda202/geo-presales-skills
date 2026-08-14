from __future__ import annotations

import re
import uuid

from . import RULESET_VERSION, SCHEMA_VERSION
from .util import ContractError, normalize_alias, normalize_host, now_iso, sha256_obj


DEFAULT_QUOTAS = {
    "total": 50,
    "question_type": {"generic": 40, "branded": 10},
}


def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _clean_aliases(name: str, aliases) -> list[str]:
    values = [name]
    for item in _as_list(aliases):
        if isinstance(item, dict):
            if item.get("confirmed") is False:
                continue
            item = item.get("raw_alias") or item.get("alias") or item.get("name")
        if item:
            values.append(str(item))
    result = []
    seen = set()
    for item in values:
        raw = str(item).strip()
        normalized = normalize_alias(raw)
        if raw and normalized and normalized not in seen:
            seen.add(normalized)
            result.append(raw)
    return result


def _normalize_object(raw: dict | str, role: str, index: int) -> dict:
    if isinstance(raw, str):
        raw = {"name": raw}
    name = str(raw.get("name") or raw.get("canonical_name") or raw.get("brand_name") or "").strip()
    if not name:
        raise ContractError(f"{role} object is missing a name")
    domain_value = raw.get("official_domain") or raw.get("domain") or raw.get("brand_domain")
    domains = [normalize_host(item) for item in _as_list(raw.get("official_domains") or domain_value)]
    domains = [item for item in domains if item]
    if not domains:
        raise ContractError(f"{role} object {name!r} is missing a valid official domain")
    aliases = _clean_aliases(name, raw.get("aliases") or raw.get("confirmed_aliases"))
    return {
        "object_id": "target" if role == "target" else f"competitor-{index:02d}",
        "role": role,
        "display_order": index,
        "canonical_name": name,
        "official_domains": domains,
        "aliases": aliases,
        "object_scope": str(raw.get("object_scope") or "brand"),
    }


def _normalize_quotas(raw) -> dict:
    if not raw:
        return {
            "total": DEFAULT_QUOTAS["total"],
            "question_type": dict(DEFAULT_QUOTAS["question_type"]),
        }
    qt = raw.get("question_type") or {}
    result = {
        "total": int(raw.get("total") or raw.get("expected_total") or 0),
        "question_type": {
            "generic": int(qt.get("generic", 0)),
            "branded": int(qt.get("branded", qt.get("brand", 0))),
        },
    }
    if result["total"] <= 0:
        result["total"] = sum(result["question_type"].values())
    if sum(result["question_type"].values()) != result["total"]:
        raise ContractError("Question-type quotas do not sum to total")
    return result


def normalize_config(raw: dict) -> dict:
    topic = str(raw.get("topic") or "").strip()
    if not topic:
        raise ContractError("Config is missing topic")
    if isinstance(raw.get("topics"), list) and len(raw["topics"]) != 1:
        raise ContractError("This version supports exactly one topic")

    market = str(raw.get("market") or raw.get("target_market") or "US").strip().casefold()
    if market not in {"us", "usa", "united states", "united_states"}:
        raise ContractError("This version supports only the US market")
    language = str(raw.get("language") or "en").strip().casefold()
    if language not in {"en", "en-us", "english", "english-us"}:
        raise ContractError("This version supports only English")
    platform = str(raw.get("platform") or "chatgpt").strip().casefold()
    if platform != "chatgpt":
        raise ContractError("This version supports only ChatGPT")

    brand_raw = raw.get("brand") or {
        "name": raw.get("brand_name") or raw.get("customer_name"),
        "aliases": raw.get("brand_aliases") or raw.get("aliases"),
        "domain": raw.get("brand_domain") or raw.get("official_domain"),
        "object_scope": raw.get("object_scope"),
    }
    target = _normalize_object(brand_raw, "target", 0)
    competitor_raw = raw.get("competitors") or raw.get("comps_list") or []
    competitors = [_normalize_object(item, "competitor", index) for index, item in enumerate(_as_list(competitor_raw), 1)]
    if not 1 <= len(competitors) <= 3:
        raise ContractError("Config must contain 1 to 3 confirmed competitors")

    alias_owner: dict[str, str] = {}
    for obj in [target, *competitors]:
        for alias in obj["aliases"]:
            normalized = normalize_alias(alias)
            previous = alias_owner.get(normalized)
            if previous and previous != obj["object_id"]:
                raise ContractError(f"Alias conflict: {alias!r} belongs to both {previous} and {obj['object_id']}")
            alias_owner[normalized] = obj["object_id"]

    quotas = _normalize_quotas(raw.get("quotas"))
    run_id = str(raw.get("run_id") or f"R-{now_iso()[:10].replace('-', '')}-{uuid.uuid4().hex[:8]}")
    result = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "config_version": str(raw.get("config_version") or "1"),
        "topic": topic,
        "market": "US",
        "language": "en",
        "platform": "chatgpt",
        "audiences": [str(item) for item in _as_list(raw.get("audiences")) if str(item).strip()],
        "supplemental_context": str(raw.get("supplemental_context") or raw.get("background_info") or "").strip(),
        "avoid_expressions": [str(item) for item in _as_list(raw.get("avoid_expressions")) if str(item).strip()],
        "objects": [target, *competitors],
        "target_object_id": "target",
        "quotas": quotas,
        "sample_policy": str(raw.get("sample_policy") or "first_valid_per_question"),
        "rank_policy": "configured_objects_first_appearance_v1",
        "source_taxonomy_version": "prd-8-types-v1",
        "sentiment_confidence_threshold": float(raw.get("sentiment_confidence_threshold", 0.78)),
        "ruleset_version": RULESET_VERSION,
        "frozen_at": now_iso(),
    }
    if result["sample_policy"] != "first_valid_per_question":
        raise ContractError("Only first_valid_per_question sample policy is supported")
    if not 0.5 <= result["sentiment_confidence_threshold"] <= 1:
        raise ContractError("sentiment_confidence_threshold must be between 0.5 and 1")
    result["config_hash"] = sha256_obj(result)
    return result


def validate_domain_text(value: str) -> bool:
    return bool(re.match(r"^[a-z0-9.-]+$", value, flags=re.IGNORECASE) and normalize_host(value))
