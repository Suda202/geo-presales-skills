#!/usr/bin/env python3
"""Deterministic validation for Overseas GEO question-bank JSON files."""

from __future__ import annotations

import json
import copy
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urlparse


DEFAULT_QUOTAS = {
    "question_type": {"generic": 40, "branded": 10},
}
V6_SCHEMA_VERSION = "overseas-geo-question-bank/v6"
V7_SCHEMA_VERSION = "overseas-geo-question-bank/v7"
V8_SCHEMA_VERSION = "overseas-geo-question-bank/v8"
DEFAULT_GENERATION_SCHEMA_VERSION = V8_SCHEMA_VERSION
V6_MAX_TOTAL = 60
V8_MAX_TOTAL = 75
V6_PER_TOPIC_QUOTAS = {
    "discovery": 14,
    "competitor": 3,
    "verification": 1,
    "accuracy": 0,
    "evaluation": 1,
    "category_awareness": 1,
}
V6_ANALYSIS_TYPES = {
    "discovery": "visibility,sentiment",
    "competitor": "sentiment",
    "verification": "accuracy",
    "accuracy": "accuracy",
    "evaluation": "sentiment",
    "category_awareness": None,
}
V8_INTENT_TAGS = {
    "discovery": "Intent: Discovery",
    "competitor": "Intent: Competitor",
    "verification": "Intent: Verification",
    "accuracy": "Intent: Accuracy",
    "evaluation": "Intent: Evaluation",
    "category_awareness": "Intent: Category Awareness",
}
V8_TAG_TO_ROLE = {tag: role for role, tag in V8_INTENT_TAGS.items()}
V8_BRAND_SCOPE_TAGS = {
    True: "Brand Scope: Branded",
    False: "Brand Scope: Non-Branded",
}
V8_ATTRIBUTE_TAG_PREFIX = "Attribute: "
V6_REQUIRED_CASE_FIELDS = {
    "公司名",
    "业务 / 产品名称",
    "品牌名称",
    "业务模式",
    "品类",
    "垂直行业",
    "差异化优势",
    "适用边界",
    "官方域名",
    "竞品 1",
    "竞品 1 官网域名",
    "竞品 2",
    "竞品 2 官网域名",
    "竞品 3",
    "竞品 3 官网域名",
    "补充内容",
}
V6_NUMBERED_CASE_FIELDS = ("目标客户", "痛点", "使用场景", "产品特性")
V6_NUMBERED_CASE_FIELD = re.compile(r"^(?:目标客户|痛点|使用场景|产品特性)\s+\d+$")
V6_TOPIC_CASE_FIELD = re.compile(r"^主题\s+[1-3]（(?:宽泛|细分)）$")
V6_ATTRIBUTE_SOURCE_FIELD = re.compile(
    r"^(?:品类|垂直行业|目标客户\s+\d+|痛点\s+\d+|使用场景\s+\d+|"
    r"产品特性\s+\d+|差异化优势|适用边界|补充内容)$"
)
V6_RETIRED_FIELDS = {
    "target_attributes",
    "attribute_pool",
    "attribute_id",
    "priority_attribute_ids",
    "topic_type",
    "question_type",
    "funnel_intent",
    "decision_stage",
    "metric_scopes",
    "attribute_ids",
    "paired_discovery_ids",
    "diagnostic_intent",
}
V8_RETIRED_FIELDS = V6_RETIRED_FIELDS | {"diagnosis_intent", "attributes"}
V6_CONFIG_FIELDS = {
    "case_fields",
    "brand_name",
    "brand_object_type",
    "category_label",
    "official_domain",
    "derived_field_sources",
    "topics",
    "expected_total",
    "quotas",
    "competitor_selection",
}
V7_CONFIG_FIELDS = V6_CONFIG_FIELDS | {"attribute_plan"}
V7_ATTRIBUTE_PRIORITIES = ("P1", "P2", "P3")
V7_ATTRIBUTE_ENTRY_FIELDS = {
    "attribute",
    "source_field",
    "source_value",
    "decision_reason",
}
V7_P1_ATTRIBUTE_ENTRY_FIELDS = V7_ATTRIBUTE_ENTRY_FIELDS | {"verification_statement"}
V7_EXCLUDED_ENTRY_FIELDS = {
    "candidate",
    "source_field",
    "source_value",
    "reason",
    "route",
}
V7_EXCLUDED_ROUTES = {"exclude", "accuracy_only"}
V6_CSV_HEADERS = [
    "query",
    "question_zh",
    "topic",
    "diagnosis_intent",
    "question_types",
    "purchase_intent",
    "persona_name",
    "scene_name",
]
V6_CSV_QUESTION_TYPES = {
    "discovery": "visibility,sentiment",
    "competitor": "visibility,sentiment",
    "verification": "visibility",
    "accuracy": "visibility",
    "evaluation": "sentiment",
    "category_awareness": "visibility",
}
V8_CSV_HEADERS = [
    "query",
    "question_zh",
    "topic",
    "diagnosis_intent",
    "tags",
    "question_types",
    "purchase_intent",
    "persona_name",
    "scene_name",
]
V8_CSV_TAGS_MAX_LENGTH = 200
V8_CSV_QUESTION_TYPES = {
    "discovery": "visibility,sentiment",
    "competitor": "sentiment",
    "verification": "visibility,sentiment",
    "accuracy": "visibility,sentiment",
    "evaluation": "sentiment",
    "category_awareness": "visibility,sentiment",
}
V6_EVALUATION_META_TOPIC = re.compile(r"\btopic\b", re.IGNORECASE)
V5_SCHEMA_VERSION = "overseas-geo-question-bank/v5"
V5_PER_TOPIC_QUOTAS = {
    "discovery": 10,
    "competitor": 3,
    "validation": 1,
    "accuracy": 1,
    "sentiment": 1,
    "market_perception": 1,
}
V5_DEFAULT_QUOTAS = {
    "diagnostic_intent": {
        intent: count * 3 for intent, count in V5_PER_TOPIC_QUOTAS.items()
    },
    "per_topic": V5_PER_TOPIC_QUOTAS,
}
V5_METRIC_SCOPES = {
    "discovery": ("visibility", "citation"),
    "competitor": ("comparison",),
    "validation": ("attribute_validation",),
    "accuracy": ("accuracy",),
    "sentiment": ("sentiment",),
    "market_perception": ("market_perception",),
}
V5_ATTRIBUTE_TYPES = {
    "product_category",
    "audience",
    "pain_point",
    "use_case",
    "capability",
    "integration",
    "business_specific",
    "factual",
}
V5_EVIDENCE_TYPES = {"input", "official", "first_party", "public_market", "assumption"}
V4_DEFAULT_QUOTAS = {
    "question_type": {"visibility": 40, "sentiment": 10},
    "diagnostic_intent": {
        "discovery": 37,
        "competitor": 3,
        "validation": 1,
        "accuracy": 1,
        "sentiment": 7,
        "market_perception": 1,
    },
    "funnel_intent": {"recommendation": 18, "comparison": 19, "decision": 13},
}
REQUIRED_COMMERCIAL_INTENTS = {"recommendation", "comparison", "decision"}
BRAND_EVALUATION_INTENT = "decision"
V4_DIAGNOSTIC_INTENTS = {
    "discovery",
    "competitor",
    "validation",
    "accuracy",
    "sentiment",
    "market_perception",
}
V4_ANALYSIS_TYPES = {"visibility", "sentiment", "accuracy"}
V4_TOPIC_TYPES = {"coverage"}
V4_FUNNEL_MAPPING = {
    "competitor": "comparison",
    "validation": "decision",
    "accuracy": "decision",
    "sentiment": "decision",
    "market_perception": "recommendation",
}
REQUIRED_FIELDS = (
    "question_id",
    "question_type",
    "funnel_intent",
    "decision_stage",
    "cluster",
    "audience_role",
    "scenario",
    "constraint",
    "evidence_need",
    "user_question",
    "zh_translation",
    "standalone_rewrite",
    "retrieval_rewrite",
    "evidence_query",
    "title_seed",
    "monitoring_prompt",
    "quality_checks",
)
V4_REQUIRED_FIELDS = REQUIRED_FIELDS + (
    "topic_id",
    "intent_key",
    "diagnostic_intent",
    "analysis_type",
    "topic_type",
)
LEGACY_REQUIRED_FIELDS = REQUIRED_FIELDS + ("geo_intent",)
RETIRED_V3_INTENT_FIELDS = ("geo_intent", "intent_angle")
QUALITY_FIELDS = (
    "natural",
    "standalone",
    "answerable",
    "single_intent",
    "category_aligned",
    "neutral_premise",
    "monitoring_field_valid",
)
V3_QUALITY_FIELDS = QUALITY_FIELDS + (
    "topic_aligned",
    "category_visible",
    "commercial_intent",
)
V3_DECISION_STAGES = {"shortlist", "evaluation", "purchase", "implementation", "review"}
CONVERSATIONAL_START = re.compile(
    r"^(how|what|which|who|where|when|why|is|are|am|do|does|did|can|could|"
    r"should|would|will|has|have|recommend|compare|explain|show me|tell me|help me|"
    r"please recommend|please compare|give me|give us|list|suggest|find|"
    r"i need|i am looking for|i['’]m looking for|"
    r"any recommendations)\b",
    re.IGNORECASE,
)
BARE_ACTION = re.compile(
    r"^(buy|purchase|order|gift|subscribe(?:\s+to)?|sign\s+up(?:\s+for)?|request|book|get)\b|"
    r"^give\b(?=.*\b(?:subscription|gift|access|licen[cs]e|account)\b)",
    re.IGNORECASE,
)
PROMOTIONAL_DRIVER = re.compile(
    r"\b(?:best|top)\b|"
    r"\bmost\s+(?:popular|recommended|reliable|trusted|affordable|effective|accurate|"
    r"visible|comprehensive|advanced|integrations?|features?|citations?|mentions?|coverage|value)\b|"
    r"\breviews\b|\b(?:customer|user|buyer|verified|product|platform|tool|brand)\s+review\b",
    re.IGNORECASE,
)
LOW_CONFIDENCE_PROMOTIONAL = re.compile(r"\b(?:most|review)\b", re.IGNORECASE)
COMMON_QUESTION_OPENERS = {"how", "what", "which"}
MAX_PROMOTIONAL_DRIVER_RATIO = 0.20
WARN_SINGLETON_CLUSTER_RATIO = 0.50
HIGH_RISK_SINGLETON_CLUSTER_RATIO = 0.80
WARN_METADATA_SINGLETON_RATIO = 0.80
MAX_COMMON_OPENER_RATIO = 0.75
HIGH_RISK_COMMON_OPENER_RATIO = 0.90
MAX_SINGLE_OPENER_RATIO = 0.50
MIN_BATCH_FOR_STYLE_WARNINGS = 10
AMBIGUOUS_CATEGORY = re.compile(r"\bbrand\s+(tracking|monitoring)\b", re.IGNORECASE)
CATEGORY_CLARIFIER = re.compile(
    r"\b(AI\s+search|AI-generated\s+answers?|generative\s+search|LLMs?|"
    r"large\s+language\s+models?)\b",
    re.IGNORECASE,
)
CJK_CHARACTER = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
# Kept for the legacy generic-validator branch; new generation defaults to v8.
CURRENT_SCHEMA_VERSION = "overseas-geo-question-bank/v4"
COMPATIBLE_V3_SCHEMA_VERSION = "overseas-geo-question-bank/v3"
LEGACY_SCHEMA_VERSIONS = {"overseas-geo-question-bank/v2", COMPATIBLE_V3_SCHEMA_VERSION}
NON_COMMERCIAL_GENERIC = re.compile(
    r"^(?:what\s+is\s+(?!(?:the\s+)?(?:best|top|recommended|right|better|good)\b)|"
    r"how\s+do(?:es)?\b.{0,120}\bwork|what\s+is\s+the\s+difference\s+between|"
    r"what\s+should\s+(?:i|we|buyers|a\s+buyer)\s+(?:look\s+for|consider|evaluate|assess)|"
    r"where\s+to\s+buy|how\s+to\s+buy|where\s+can\s+i\s+buy)\b",
    re.IGNORECASE,
)
ABSTRACT_EVALUATION_LABELS = {
    "broad topic",
    "category breadth",
    "online trust",
    "overall brand fit",
    "overall value",
    "technology and sourcing",
}


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def normalize_human_label(value: object) -> str:
    """Normalize human-readable labels without discarding Chinese characters."""
    return re.sub(r"[\W_]+", " ", str(value or "").casefold(), flags=re.UNICODE).strip()


def contains_name(text: str, name: str) -> bool:
    needle = normalize(name)
    haystack = f" {normalize(text)} "
    return bool(needle) and f" {needle} " in haystack


def contains_entity_name(text: str, name: str) -> bool:
    """Match configured entities across camel-case, spaces, underscores, and hyphens."""
    expanded = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", str(name).strip())
    tokens = re.findall(r"[A-Za-z0-9]+", expanded.lower())
    if not tokens:
        return False
    pattern = r"(?<![a-z0-9])" + r"[\s_-]*".join(re.escape(token) for token in tokens) + r"(?![a-z0-9])"
    return re.search(pattern, text, re.IGNORECASE) is not None


def normalize_template_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def format_dimension_list(dimensions: list[str]) -> str:
    if len(dimensions) == 2:
        return f"{dimensions[0]} and {dimensions[1]}"
    return f"{', '.join(dimensions[:-1])}, and {dimensions[-1]}"


def build_brand_evaluation_prompt(brand: str, subject: str, dimensions: list[str]) -> str:
    return (
        f"How well does {brand} perform as {subject} on "
        f"{format_dimension_list(dimensions)}?"
    )


def build_v4_sentiment_prompt(category_label: str, brand_object_type: str, brand: str, topic: str) -> str:
    object_label = "company" if brand_object_type == "company" else "product"
    return f"Evaluate the {category_label} {object_label} {brand} on {topic}"


def build_v6_sentiment_prompt(
    category_label: str,
    brand_object_type: str,
    brand: str,
    evaluation_scope: str,
) -> str:
    """Build the v6 sentiment Prompt with a customer-facing business scope."""
    object_label = "company" if brand_object_type == "company" else "product"
    return f"Evaluate the {category_label} {object_label} {brand} on {evaluation_scope}"


def build_v6_market_perception_prompt(category_label: str, topic: str) -> str:
    """Build the category-first market-perception Prompt template."""
    return f"What is a {category_label}, and how should I evaluate one for {topic}?"


def build_v6_validation_prompt(brand: str, validation_items: list[dict]) -> str:
    """Build the exact batch-Validation Prompt from its ordered atomic items."""
    numbered = " ".join(
        f"{index}. {str(item.get('statement') or '').strip().rstrip('.')}."
        for index, item in enumerate(validation_items, start=1)
    )
    return (
        f"For {brand}, determine whether each statement is true. "
        "Answer Yes / No / Unknown for each item and explain the basis for your judgment: "
        f"{numbered}"
    )


def _v6_translation_has_ordered_item_markers(translation: str, item_count: int) -> bool:
    """Require one ordered Chinese-visible marker for every Verification item."""
    chinese_numbers = ("一", "二", "三", "四", "五")
    if not 1 <= item_count <= len(chinese_numbers):
        return False
    positions: list[int] = []
    for index in range(1, item_count + 1):
        marker = re.search(
            rf"(?<!\d){index}\s*[.．、)）]|{chinese_numbers[index - 1]}\s*[、.．)）]",
            translation,
        )
        if marker is None:
            return False
        positions.append(marker.start())
    return positions == sorted(positions)


def validate_v6_csv_rows(fieldnames: list[str] | None, rows: list[dict]) -> tuple[list[str], dict]:
    """Validate the fixed-field CSV export contract for v6 monitoring Prompts."""
    errors: list[str] = []
    if fieldnames != V6_CSV_HEADERS:
        errors.append(f"CSV header must exactly equal {V6_CSV_HEADERS}")
    if len(rows) > V6_MAX_TOTAL:
        errors.append(f"CSV batch total must not exceed {V6_MAX_TOTAL}")

    question_types: Counter = Counter()
    diagnostic_intents: Counter = Counter()
    topics: Counter = Counter()
    normalized_queries: Counter = Counter()
    for index, row in enumerate(rows, start=2):
        if not isinstance(row, dict):
            errors.append(f"CSV row {index} must be an object")
            continue
        for field in ("query", "question_zh", "topic", "diagnosis_intent", "question_types"):
            if not str(row.get(field) or "").strip():
                errors.append(f"CSV row {index} field {field!r} must be non-empty")
        if len(str(row.get("query") or "")) > 1000:
            errors.append(f"CSV row {index} query must not exceed 1000 characters")
        if len(str(row.get("question_zh") or "")) > 1000:
            errors.append(f"CSV row {index} question_zh must not exceed 1000 characters")
        if len(str(row.get("topic") or "")) > 255:
            errors.append(f"CSV row {index} topic must not exceed 255 characters")
        purchase_intent = str(row.get("purchase_intent") or "").strip()
        if purchase_intent not in {"", "0", "1", "2", "3"}:
            errors.append(f"CSV row {index} purchase_intent must be blank or one of 0, 1, 2, 3")
        for field in ("persona_name", "scene_name"):
            if len(str(row.get(field) or "")) > 200:
                errors.append(f"CSV row {index} {field} must not exceed 200 characters")
        intent = str(row.get("diagnosis_intent") or "").strip()
        query = str(row.get("query") or "").strip()
        question_type = str(row.get("question_types") or "").strip()
        expected_type = V6_CSV_QUESTION_TYPES.get(intent)
        if expected_type is None:
            errors.append(f"CSV row {index} has unsupported diagnosis_intent {intent!r}")
        elif question_type != expected_type:
            errors.append(
                f"CSV row {index} diagnosis_intent {intent!r} requires question_types {expected_type!r}"
            )
        if intent == "evaluation":
            if V6_EVALUATION_META_TOPIC.search(query):
                errors.append(
                    f"CSV row {index} evaluation query must not contain the meta word 'topic'"
                )
        question_types[question_type] += 1
        diagnostic_intents[intent] += 1
        topics[str(row.get("topic") or "").strip()] += 1
        normalized_queries[normalize(str(row.get("query") or ""))] += 1

    duplicates = sorted(
        query for query, count in normalized_queries.items() if query and count > 1
    )
    if duplicates:
        errors.append(f"CSV normalized query values must be unique {duplicates}")
    return errors, {
        "total": len(rows),
        "question_types": dict(question_types),
        "diagnosis_intent": dict(diagnostic_intents),
        "topic": dict(topics),
    }


def _parse_v8_csv_tags(value: object) -> list[str]:
    """Parse upload CSV Tags while preserving free-form tag text."""
    return [tag.strip() for tag in re.split(r"[，,;\n]+", str(value or "")) if tag.strip()]


def validate_v8_csv_rows(fieldnames: list[str] | None, rows: list[dict]) -> tuple[list[str], dict]:
    """Validate the upload CSV adapter for a v8 JSON question bank."""
    errors: list[str] = []
    if fieldnames != V8_CSV_HEADERS:
        errors.append(f"CSV header must exactly equal {V8_CSV_HEADERS}")
    if len(rows) > V6_MAX_TOTAL:
        errors.append(f"CSV batch total must not exceed {V6_MAX_TOTAL}")

    diagnostic_intents: Counter = Counter()
    question_types: Counter = Counter()
    topics: Counter = Counter()
    csv_tags: Counter = Counter()
    normalized_queries: Counter = Counter()
    for index, row in enumerate(rows, start=2):
        if not isinstance(row, dict):
            errors.append(f"CSV row {index} must be an object")
            continue
        for field in ("query", "question_zh", "topic", "diagnosis_intent", "question_types"):
            if not str(row.get(field) or "").strip():
                errors.append(f"CSV row {index} field {field!r} must be non-empty")
        query = str(row.get("query") or "").strip()
        if len(query) > 1000:
            errors.append(f"CSV row {index} query must not exceed 1000 characters")
        if len(str(row.get("question_zh") or "")) > 1000:
            errors.append(f"CSV row {index} question_zh must not exceed 1000 characters")
        if len(str(row.get("topic") or "")) > 255:
            errors.append(f"CSV row {index} topic must not exceed 255 characters")
        raw_tags = str(row.get("tags") or "").strip()
        if len(raw_tags) > V8_CSV_TAGS_MAX_LENGTH:
            errors.append(
                f"CSV row {index} tags must not exceed {V8_CSV_TAGS_MAX_LENGTH} characters"
            )
        parsed_tags = _parse_v8_csv_tags(raw_tags)
        if raw_tags and not parsed_tags:
            errors.append(f"CSV row {index} tags must contain at least one non-empty tag")
        purchase_intent = str(row.get("purchase_intent") or "").strip()
        if purchase_intent not in {"", "0", "1", "2", "3"}:
            errors.append(f"CSV row {index} purchase_intent must be blank or one of 0, 1, 2, 3")
        for field in ("persona_name", "scene_name"):
            if len(str(row.get(field) or "")) > 200:
                errors.append(f"CSV row {index} {field} must not exceed 200 characters")

        role = str(row.get("diagnosis_intent") or "").strip()
        topic = str(row.get("topic") or "").strip()
        question_type = str(row.get("question_types") or "").strip()
        expected_type = V8_CSV_QUESTION_TYPES.get(role)
        if expected_type is None:
            errors.append(f"CSV row {index} has unsupported diagnosis_intent {role!r}")
        elif question_type != expected_type:
            errors.append(
                f"CSV row {index} diagnosis_intent {role!r} requires "
                f"question_types {expected_type!r}"
            )
        if role == "evaluation" and V6_EVALUATION_META_TOPIC.search(query):
            errors.append(f"CSV row {index} evaluation query must not contain the meta word 'topic'")
        diagnostic_intents[role] += 1
        question_types[question_type] += 1
        topics[topic] += 1
        normalized_queries[normalize(query)] += 1
        csv_tags.update(parsed_tags)

    duplicates = sorted(query for query, count in normalized_queries.items() if query and count > 1)
    if duplicates:
        errors.append(f"CSV normalized query values must be unique {duplicates}")
    return errors, {
        "total": len(rows),
        "diagnosis_intent": dict(diagnostic_intents),
        "question_types": dict(question_types),
        "topic": dict(topics),
        "tags": dict(csv_tags),
    }


def normalize_label(value: object) -> str:
    return normalize(str(value))


def check_quota(errors: list[str], label: str, actual: Counter, expected: dict) -> None:
    for key, count in expected.items():
        if actual.get(key, 0) != count:
            errors.append(f"QUOTA {label}.{key}: expected {count}, got {actual.get(key, 0)}")
    unexpected = sorted(set(actual) - set(expected))
    if unexpected:
        errors.append(f"QUOTA {label}: unexpected values {unexpected}")


def _v5_competitor_names(config: dict, errors: list[str]) -> list[str]:
    selection = config.get("competitor_selection")
    raw_items = selection.get("formal_competitors") if isinstance(selection, dict) else config.get("competitors")
    if not isinstance(raw_items, list) or len(raw_items) != 3:
        errors.append("CONFIG competitor_selection must provide exactly 3 formal competitors in v5")
        return []
    names: list[str] = []
    for index, item in enumerate(raw_items):
        name = str(item.get("name") if isinstance(item, dict) else item or "").strip()
        if not name:
            errors.append(f"CONFIG formal competitor {index + 1} must have a non-empty name")
        else:
            names.append(name)
    if len({normalize_label(name) for name in names}) != len(names):
        errors.append("CONFIG formal competitor names must be unique in v5")
    return names


def _entity_pattern(name: str) -> re.Pattern[str] | None:
    expanded = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", str(name).strip())
    tokens = re.findall(r"[A-Za-z0-9]+", expanded.lower())
    if not tokens:
        return None
    return re.compile(
        r"(?<![a-z0-9])" + r"[^a-z0-9]*".join(re.escape(token) for token in tokens) + r"(?![a-z0-9])",
        re.IGNORECASE,
    )


def _v6_entity_variants(name: str) -> list[str]:
    canonical = str(name).strip()
    variants = [canonical]
    short = re.sub(r"\s*\([^)]*\)\s*$", "", canonical).strip()
    if short and short != canonical:
        variants.append(short)
    for parenthetical in re.findall(r"\(([^()]*)\)", canonical):
        alias = parenthetical.strip()
        if alias and alias not in variants:
            variants.append(alias)
    return variants


def _contains_v6_entity(text: str, name: str) -> bool:
    return any(
        pattern and pattern.search(text)
        for variant in _v6_entity_variants(name)
        if (pattern := _entity_pattern(variant))
    )


def _replace_v6_entity(text: str, name: str, replacement: str) -> str:
    for variant in _v6_entity_variants(name):
        exact = re.compile(re.escape(variant), re.IGNORECASE)
        if exact.search(text):
            return exact.sub(replacement, text)
        pattern = _entity_pattern(variant)
        if pattern and pattern.search(text):
            return pattern.sub(replacement, text)
    return text


def _v6_requests_concrete_candidates(text: str) -> bool:
    """Accept high-confidence commercial questions that naturally yield named candidates."""
    lowered = str(text).strip().casefold()
    if re.match(r"^what\s+(?:is|does)\b", lowered):
        return False
    candidate_pattern = re.compile(
        r"\b(?:brands?|companies|manufacturers?|providers?|products?|solutions?|suppliers?|"
        r"tools?|vendors?|options?|platforms?)\b"
    )
    if not candidate_pattern.search(lowered):
        return False
    interrogative = re.match(r"^(?:which|what)\s+", lowered)
    if interrogative:
        candidate = candidate_pattern.search(lowered, interrogative.end())
        prefix = lowered[interrogative.end():candidate.start()] if candidate else ""
        abstract_noun_pattern = (
            r"\b(?:factors?|criteria|features?|capabilities|attributes|requirements?|"
            r"considerations?|benefits?|risks?|differences?|tradeoffs?)\b"
        )
        if re.search(abstract_noun_pattern, prefix):
            return False
        suffix = lowered[candidate.end():] if candidate else ""
        if re.match(rf"^\s*(?:['’]s?)?\s*{abstract_noun_pattern}", suffix):
            return False
        if candidate and len(prefix) <= 100:
            return True
    if re.match(r"^who\b", lowered):
        return True
    return bool(
        re.search(
            r"\b(?:best|top|leading|recommend(?:ed)?|suggest|list|name|find|compare)\b"
            r".{0,100}\b(?:brands?|companies|manufacturers?|providers?|products?|solutions?|"
            r"suppliers?|tools?|vendors?|options?|platforms?)\b",
            lowered,
        )
    )


def _v6_url_belongs_to_domain(source_url: str, official_domain: str) -> bool:
    source = urlparse(source_url)
    target_value = official_domain if "://" in official_domain else f"https://{official_domain}"
    target = urlparse(target_value)
    source_host = (source.hostname or "").casefold().rstrip(".")
    target_host = (target.hostname or "").casefold().rstrip(".")
    return (
        source.scheme in {"http", "https"}
        and bool(source_host)
        and bool(target_host)
        and (source_host == target_host or source_host.endswith(f".{target_host}"))
    )


def _v6_is_iso_date(value: str) -> bool:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _v6_competitors(
    config: dict,
    case_fields: dict,
    errors: list[str],
    topic_ids: set[str] | None = None,
) -> list[dict]:
    selection = config.get("competitor_selection")
    items = selection.get("formal_competitors") if isinstance(selection, dict) else None
    if not isinstance(items, list) or len(items) != 3:
        errors.append("CONFIG competitor_selection must provide exactly 3 formal competitors in v6")
        return []
    if selection.get("selection_count") != 3:
        errors.append("CONFIG competitor_selection.selection_count must equal 3 in v6")
    if selection.get("status") != "frozen":
        errors.append("CONFIG competitor_selection.status must equal frozen in v6")

    result: list[dict] = []
    seen: set[str] = set()
    for index, item in enumerate(items, start=1):
        prefix = f"CONFIG formal_competitors[{index - 1}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        name = str(item.get("name") or "").strip()
        domain = str(item.get("official_domain") or "").strip()
        if not name:
            errors.append(f"{prefix}.name must be non-empty")
        if not domain:
            errors.append(f"{prefix}.official_domain must be non-empty")
        key = normalize_label(name)
        if key in seen:
            errors.append(f"{prefix}.name must be unique")
        seen.add(key)
        expected_name_field = f"竞品 {index}"
        expected_domain_field = f"竞品 {index} 官网域名"
        source_fields = item.get("source_fields")
        if source_fields != [expected_name_field, expected_domain_field]:
            errors.append(
                f"{prefix}.source_fields must equal [{expected_name_field!r}, {expected_domain_field!r}]"
            )
        if name and str(case_fields.get(expected_name_field) or "").strip() != name:
            errors.append(f"{prefix}.name must match Case field {expected_name_field}")
        if domain and str(case_fields.get(expected_domain_field) or "").strip() != domain:
            errors.append(f"{prefix}.official_domain must match Case field {expected_domain_field}")
        raw_item_topic_ids = item.get("topic_ids")
        if raw_item_topic_ids is None:
            item_topic_ids = set(topic_ids or set())
        elif not isinstance(raw_item_topic_ids, list) or not raw_item_topic_ids:
            errors.append(f"{prefix}.topic_ids must be a non-empty list when supplied")
            item_topic_ids = set()
        else:
            normalized_item_topic_ids = [
                normalize_label(value) for value in raw_item_topic_ids if normalize_label(value)
            ]
            item_topic_ids = set(normalized_item_topic_ids)
            if len(normalized_item_topic_ids) != len(raw_item_topic_ids):
                errors.append(f"{prefix}.topic_ids must contain only non-empty strings")
            if len(item_topic_ids) != len(normalized_item_topic_ids):
                errors.append(f"{prefix}.topic_ids must be unique after normalization")
            unknown_topic_ids = sorted(item_topic_ids - set(topic_ids or set()))
            if unknown_topic_ids:
                errors.append(f"{prefix}.topic_ids references unknown topics {unknown_topic_ids}")
        result.append({
            "name": name,
            "official_domain": domain,
            "topic_ids": item_topic_ids,
        })
    return result


def _validate_v7_attribute_plan(
    config: dict,
    topics: dict[str, dict],
    case_fields: dict,
    errors: list[str],
    warnings: list[str],
) -> dict[str, dict[str, list[dict]]]:
    """Validate the Topic-scoped P1/P2/P3 plan that must precede v7 Prompt writing."""

    raw_plans = config.get("attribute_plan")
    if not isinstance(raw_plans, list):
        errors.append("CONFIG attribute_plan must be an array in v7")
        return {}

    plans: dict[str, dict[str, list[dict]]] = {}
    for plan_index, plan in enumerate(raw_plans):
        prefix = f"CONFIG attribute_plan[{plan_index}]"
        if not isinstance(plan, dict):
            errors.append(f"{prefix} must be an object")
            continue
        expected_plan_fields = {"topic_id", "priorities", "excluded"}
        if set(plan) != expected_plan_fields:
            errors.append(
                f"{prefix} must contain exactly topic_id, priorities, and excluded"
            )
        topic_id = normalize_label(plan.get("topic_id"))
        if topic_id not in topics:
            errors.append(f"{prefix}.topic_id must reference a configured Topic")
            continue
        if topic_id in plans:
            errors.append(f"{prefix}.topic_id must be unique")
            continue

        priorities = plan.get("priorities")
        if not isinstance(priorities, dict) or set(priorities) != set(V7_ATTRIBUTE_PRIORITIES):
            errors.append(f"{prefix}.priorities must contain exactly P1, P2, and P3")
            priorities = {}

        normalized_priorities: dict[str, list[dict]] = {}
        seen_attributes: set[str] = set()
        for priority in V7_ATTRIBUTE_PRIORITIES:
            entries = priorities.get(priority)
            entry_prefix = f"{prefix}.priorities.{priority}"
            if not isinstance(entries, list):
                errors.append(f"{entry_prefix} must be an array")
                entries = []
            if priority == "P1" and not 3 <= len(entries) <= 5:
                errors.append(f"{entry_prefix} must contain 3 to 5 shortlist attributes")
            if priority == "P2":
                if len(entries) > 10:
                    errors.append(f"{entry_prefix} must not exceed 10 P2 attributes")
                elif len(entries) < 5:
                    warnings.append(
                        f"{entry_prefix} contains fewer than the recommended 5 P2 attributes"
                    )
            if priority == "P3" and len(entries) > 10:
                errors.append(f"{entry_prefix} must not exceed 10 P3 attributes")

            validated_entries: list[dict] = []
            for entry_index, entry in enumerate(entries):
                item_prefix = f"{entry_prefix}[{entry_index}]"
                if not isinstance(entry, dict):
                    errors.append(f"{item_prefix} must be an object")
                    continue
                expected_fields = (
                    V7_P1_ATTRIBUTE_ENTRY_FIELDS
                    if priority == "P1"
                    else V7_ATTRIBUTE_ENTRY_FIELDS
                )
                if set(entry) != expected_fields:
                    errors.append(
                        f"{item_prefix} must contain exactly {sorted(expected_fields)}"
                    )
                attribute = str(entry.get("attribute") or "").strip()
                attribute_key = normalize_human_label(attribute)
                if not attribute_key:
                    errors.append(f"{item_prefix}.attribute must be non-empty")
                elif attribute_key in seen_attributes:
                    errors.append(
                        f"{item_prefix}.attribute must be unique across this Topic's priorities"
                    )
                seen_attributes.add(attribute_key)
                if not str(entry.get("decision_reason") or "").strip():
                    errors.append(f"{item_prefix}.decision_reason must be non-empty")
                source_field = str(entry.get("source_field") or "").strip()
                if (
                    source_field not in case_fields
                    or not V6_ATTRIBUTE_SOURCE_FIELD.fullmatch(source_field)
                ):
                    errors.append(
                        f"{item_prefix}.source_field must reference an existing supported Case field"
                    )
                elif str(entry.get("source_value") or "").strip() != str(
                    case_fields[source_field]
                ).strip():
                    errors.append(f"{item_prefix}.source_value must equal its Case field")
                if priority == "P1" and not str(
                    entry.get("verification_statement") or ""
                ).strip():
                    errors.append(f"{item_prefix}.verification_statement must be non-empty")
                validated_entries.append(entry)
            normalized_priorities[priority] = validated_entries

        excluded = plan.get("excluded")
        if not isinstance(excluded, list):
            errors.append(f"{prefix}.excluded must be an array")
            excluded = []
        validated_excluded: list[dict] = []
        seen_candidates: set[str] = set()
        for entry_index, entry in enumerate(excluded):
            item_prefix = f"{prefix}.excluded[{entry_index}]"
            if not isinstance(entry, dict):
                errors.append(f"{item_prefix} must be an object")
                continue
            if set(entry) != V7_EXCLUDED_ENTRY_FIELDS:
                errors.append(
                    f"{item_prefix} must contain exactly {sorted(V7_EXCLUDED_ENTRY_FIELDS)}"
                )
            candidate = str(entry.get("candidate") or "").strip()
            candidate_key = normalize_human_label(candidate)
            if not candidate_key:
                errors.append(f"{item_prefix}.candidate must be non-empty")
            elif candidate_key in seen_candidates:
                errors.append(f"{item_prefix}.candidate must be unique within the Topic")
            seen_candidates.add(candidate_key)
            source_field = str(entry.get("source_field") or "").strip()
            if (
                source_field not in case_fields
                or not V6_ATTRIBUTE_SOURCE_FIELD.fullmatch(source_field)
            ):
                errors.append(
                    f"{item_prefix}.source_field must reference an existing supported Case field"
                )
            elif str(entry.get("source_value") or "").strip() != str(
                case_fields[source_field]
            ).strip():
                errors.append(f"{item_prefix}.source_value must equal its Case field")
            if not str(entry.get("reason") or "").strip():
                errors.append(f"{item_prefix}.reason must be non-empty")
            if entry.get("route") not in V7_EXCLUDED_ROUTES:
                errors.append(
                    f"{item_prefix}.route must equal exclude or accuracy_only"
                )
            validated_excluded.append(entry)

        plans[topic_id] = {
            **normalized_priorities,
            "excluded": validated_excluded,
        }

    missing_topics = sorted(set(topics) - set(plans))
    extra_topics = sorted(set(plans) - set(topics))
    if missing_topics or extra_topics:
        errors.append(
            "CONFIG attribute_plan must map every configured Topic exactly once"
        )
    return plans


def _convert_v8_quota_map(
    value: object,
    *,
    path: str,
    errors: list[str],
) -> dict[str, int]:
    """Convert default Intent-tag quota keys into internal generation roles."""
    if not isinstance(value, dict):
        errors.append(f"{path} must be an object keyed by default Intent tags")
        return {}
    converted: dict[str, int] = {}
    for tag, count in value.items():
        role = V8_TAG_TO_ROLE.get(str(tag))
        if role is None:
            errors.append(f"{path} contains unsupported default Intent tag {tag!r}")
            continue
        converted[role] = count
    return converted


def validate_v8(data: dict) -> tuple[list[str], list[str], dict]:
    """Validate v8 free Tags while reusing the proven v7 generation-role gates."""
    errors: list[str] = []
    warnings: list[str] = []
    config = data.get("config")
    questions = data.get("questions")
    if not isinstance(config, dict):
        return ["SCHEMA config must be an object in v8"], warnings, {}
    if not isinstance(questions, list):
        return ["SCHEMA questions must be an array in v8"], warnings, {}

    for location, value in (("DATA", data), ("CONFIG", config)):
        retired = sorted(set(value) & V8_RETIRED_FIELDS)
        if retired:
            errors.append(f"{location} retired v8 fields are not allowed {retired}")

    adapted = copy.deepcopy(data)
    adapted["schema_version"] = V7_SCHEMA_VERSION
    adapted_config = adapted.get("config", {})
    raw_quotas = config.get("quotas")
    if not isinstance(raw_quotas, dict):
        errors.append("CONFIG quotas must be an object in v8")
        raw_quotas = {}
    allowed_quota_fields = {"intent_tags", "per_topic", "topic_overrides"}
    unsupported_quota_fields = sorted(set(raw_quotas) - allowed_quota_fields)
    if unsupported_quota_fields:
        errors.append(f"CONFIG quotas has unsupported v8 fields {unsupported_quota_fields}")
    adapted_quotas = {
        "diagnosis_intent": _convert_v8_quota_map(
            raw_quotas.get("intent_tags"),
            path="CONFIG quotas.intent_tags",
            errors=errors,
        ),
        "per_topic": _convert_v8_quota_map(
            raw_quotas.get("per_topic"),
            path="CONFIG quotas.per_topic",
            errors=errors,
        ),
    }
    raw_overrides = raw_quotas.get("topic_overrides", {})
    if not isinstance(raw_overrides, dict):
        errors.append("CONFIG quotas.topic_overrides must be an object")
        raw_overrides = {}
    adapted_quotas["topic_overrides"] = {
        topic_id: _convert_v8_quota_map(
            quota,
            path=f"CONFIG quotas.topic_overrides.{topic_id}",
            errors=errors,
        )
        for topic_id, quota in raw_overrides.items()
    }
    if not adapted_quotas["topic_overrides"]:
        adapted_quotas.pop("topic_overrides")
    adapted_config["quotas"] = adapted_quotas

    raw_plans = config.get("attribute_plan")
    attributes_by_topic: dict[str, dict[str, str]] = {}
    p1_by_topic: dict[str, list[str]] = {}
    if isinstance(raw_plans, list):
        for plan in raw_plans:
            if not isinstance(plan, dict):
                continue
            topic_id = normalize_label(plan.get("topic_id"))
            priorities = plan.get("priorities")
            if not topic_id or not isinstance(priorities, dict):
                continue
            lookup: dict[str, str] = {}
            for priority in V7_ATTRIBUTE_PRIORITIES:
                entries = priorities.get(priority)
                if not isinstance(entries, list):
                    continue
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    attribute = str(entry.get("attribute") or "").strip()
                    key = normalize_human_label(attribute)
                    if key:
                        lookup[key] = attribute
            attributes_by_topic[topic_id] = lookup
            raw_p1_entries = priorities.get("P1")
            p1_entries = raw_p1_entries if isinstance(raw_p1_entries, list) else []
            p1_by_topic[topic_id] = [
                str(entry.get("attribute") or "").strip()
                for entry in p1_entries
                if isinstance(entry, dict) and str(entry.get("attribute") or "").strip()
            ]

    competitor_names = []
    selection = config.get("competitor_selection")
    if isinstance(selection, dict) and isinstance(selection.get("formal_competitors"), list):
        competitor_names = [
            str(item.get("name") or "").strip()
            for item in selection["formal_competitors"]
            if isinstance(item, dict) and str(item.get("name") or "").strip()
        ]
    brand = str(config.get("brand_name") or "").strip()
    discovery_attribute_coverage: dict[str, set[str]] = {}
    competitor_attribute_tags: dict[str, list[tuple[str, ...]]] = {}
    tag_counts: Counter = Counter()

    adapted_questions = adapted.get("questions", [])
    for index, (row, adapted_row) in enumerate(zip(questions, adapted_questions)):
        prefix = f"QUESTION[{index}]"
        if not isinstance(row, dict) or not isinstance(adapted_row, dict):
            continue
        retired = sorted(set(row) & V8_RETIRED_FIELDS)
        if retired:
            errors.append(f"{prefix} retired v8 fields are not allowed {retired}")
        tags = row.get("tags")
        if not isinstance(tags, list) or not tags:
            errors.append(f"{prefix}.tags must be a non-empty array")
            tags = []
        clean_tags: list[str] = []
        for tag_index, tag in enumerate(tags):
            if not isinstance(tag, str) or not tag.strip():
                errors.append(f"{prefix}.tags[{tag_index}] must be a non-empty string")
                continue
            clean_tags.append(tag.strip())
        normalized_tags = [normalize_human_label(tag) for tag in clean_tags]
        if len(normalized_tags) != len(set(normalized_tags)):
            errors.append(f"{prefix}.tags must be unique after normalization")
        if any(";" in tag for tag in clean_tags):
            errors.append(f"{prefix}.tags entries must not contain the reserved CSV semicolon delimiter")

        intent_tags = [tag for tag in clean_tags if tag in V8_TAG_TO_ROLE]
        if len(intent_tags) != 1:
            errors.append(f"{prefix}.tags must contain exactly one default Intent tag")
            role = ""
        else:
            role = V8_TAG_TO_ROLE[intent_tags[0]]
            adapted_row["diagnosis_intent"] = role
            if role == "category_awareness":
                adapted_row.pop("analysis_type", None)
        scope_tags = [tag for tag in clean_tags if tag in set(V8_BRAND_SCOPE_TAGS.values())]
        if len(scope_tags) != 1:
            errors.append(f"{prefix}.tags must contain exactly one Brand Scope tag")
        text = str(row.get("user_question") or "").strip()
        mentions_brand = any(
            _contains_v6_entity(text, entity)
            for entity in [brand, *competitor_names]
            if entity
        )
        expected_scope = V8_BRAND_SCOPE_TAGS[mentions_brand]
        if scope_tags and scope_tags[0] != expected_scope:
            errors.append(
                f"{prefix}.tags Brand Scope must equal {expected_scope!r} from the Prompt text"
            )

        topic_id = normalize_label(row.get("topic_id"))
        attribute_tags = [
            tag for tag in clean_tags if tag.startswith(V8_ATTRIBUTE_TAG_PREFIX)
        ]
        if any(re.fullmatch(r"Attribute:\s*", tag) for tag in clean_tags):
            errors.append(f"{prefix}.tags Attribute labels must be non-empty")
        attribute_names = [
            tag[len(V8_ATTRIBUTE_TAG_PREFIX):].strip() for tag in attribute_tags
        ]
        if any(not name for name in attribute_names):
            errors.append(f"{prefix}.tags Attribute labels must be non-empty")
        topic_attributes = attributes_by_topic.get(topic_id, {})
        for name in attribute_names:
            if normalize_human_label(name) not in topic_attributes:
                errors.append(
                    f"{prefix}.tags Attribute {name!r} must exist in the current Topic attribute_plan"
                )
        if role == "verification" and attribute_names != p1_by_topic.get(topic_id, []):
            errors.append(
                f"{prefix}.tags Verification Attribute tags must exactly match the ordered P1 plan"
            )
        if role == "competitor":
            if not attribute_names:
                errors.append(f"{prefix}.tags Competitor must include at least one Attribute tag")
            competitor_attribute_tags.setdefault(topic_id, []).append(
                tuple(normalize_human_label(name) for name in attribute_names)
            )
        if role == "discovery":
            discovery_attribute_coverage.setdefault(topic_id, set()).update(
                normalize_human_label(name) for name in attribute_names
            )
        tag_counts.update(clean_tags)
        adapted_row.pop("tags", None)

    base_errors, base_warnings, summary = validate_v6(
        adapted,
        require_attribute_plan=True,
        flexible_topic_quotas=True,
        fixed_v8_presales_quotas=True,
    )
    errors.extend(
        error.replace(" in v6", " in v8").replace(" v6 ", " v8 ").replace(" in v7", " in v8")
        for error in base_errors
    )
    warnings.extend(base_warnings)

    for topic_id, p1_names in p1_by_topic.items():
        missing = [
            name for name in p1_names
            if normalize_human_label(name) not in discovery_attribute_coverage.get(topic_id, set())
        ]
        if missing:
            errors.append(
                f"COVERAGE topic.{topic_id}.Discovery Attribute tags must cover every P1 {missing}"
            )

    for topic_id, tag_sets in competitor_attribute_tags.items():
        if len(tag_sets) >= 2 and len(set(tag_sets)) != 1:
            errors.append(
                f"QUESTION topic.{topic_id}: Competitor Attribute tags must keep the same dimensions"
            )

    if summary:
        role_counts = summary.pop("diagnosis_intent", {})
        topic_role_counts = summary.pop("topic_diagnosis_intent", {})
        summary["default_intent_tags"] = {
            V8_INTENT_TAGS[role]: count for role, count in role_counts.items()
        }
        summary["topic_default_intent_tags"] = {
            topic_id: {V8_INTENT_TAGS[role]: count for role, count in counts.items()}
            for topic_id, counts in topic_role_counts.items()
        }
        summary["tags"] = dict(tag_counts)
        summary["discovery_attribute_tag_coverage"] = {
            topic_id: sorted(values)
            for topic_id, values in discovery_attribute_coverage.items()
        }
    return errors, warnings, summary


def validate_v6(
    data: dict,
    *,
    require_attribute_plan: bool = False,
    flexible_topic_quotas: bool = False,
    fixed_v8_presales_quotas: bool = False,
) -> tuple[list[str], list[str], dict]:
    """Validate the variable-topic, Edgelight-Case-field-driven question bank."""

    errors: list[str] = []
    warnings: list[str] = []
    config = data.get("config")
    questions = data.get("questions")
    if not isinstance(config, dict):
        return ["SCHEMA config must be an object in v6"], warnings, {}
    if not isinstance(questions, list):
        return ["SCHEMA questions must be an array"], warnings, {}

    allowed_config_fields = V7_CONFIG_FIELDS if require_attribute_plan else V6_CONFIG_FIELDS
    unsupported_config = sorted(set(config) - allowed_config_fields - V6_RETIRED_FIELDS)
    for field in unsupported_config:
        errors.append(f"CONFIG unsupported v6 config field {field!r}")

    root_retired = sorted((set(data) & V6_RETIRED_FIELDS) - {"target_attributes"})
    if root_retired:
        errors.append(f"DATA retired v6 fields are not allowed {root_retired}")
    config_retired = sorted((set(config) & V6_RETIRED_FIELDS) - {"target_attributes"})
    if config_retired:
        errors.append(f"CONFIG retired v6 fields are not allowed {config_retired}")
    if "target_attributes" in config or "target_attributes" in data:
        errors.append("CONFIG target_attributes is retired in v6; consume Case fields directly")
    if "observed_associations" in config or "observed_associations" in data:
        errors.append("CONFIG observed_associations belongs to collected results, not v6 input")

    case_fields = config.get("case_fields")
    if not isinstance(case_fields, dict):
        errors.append("CONFIG case_fields must be an object containing the original Case fields")
        case_fields = {}
    for field in case_fields:
        field_name = str(field)
        if not (
            field_name in V6_REQUIRED_CASE_FIELDS
            or V6_NUMBERED_CASE_FIELD.fullmatch(field_name)
            or V6_TOPIC_CASE_FIELD.fullmatch(field_name)
        ):
            errors.append(f"CONFIG unsupported Case field {field_name!r}")
    for field in sorted(V6_REQUIRED_CASE_FIELDS):
        if field not in case_fields:
            errors.append(f"CONFIG Case field {field} must be present")
        elif field == "补充内容":
            continue
        elif (
            field == "垂直行业"
            and str(case_fields.get("业务模式") or "").strip() == "B2C"
        ):
            continue
        elif not str(case_fields.get(field) or "").strip():
            errors.append(f"CONFIG Case field {field} must be non-empty")
    for prefix in V6_NUMBERED_CASE_FIELDS:
        matches = [
            key for key, value in case_fields.items()
            if re.fullmatch(rf"{re.escape(prefix)}\s+\d+", str(key)) and str(value).strip()
        ]
        if not matches:
            errors.append(f"CONFIG Case fields must contain at least one {prefix} n field")

    raw_topic_fields = {
        key: value
        for key, value in case_fields.items()
        if V6_TOPIC_CASE_FIELD.fullmatch(str(key)) and str(value).strip()
    }
    if not 1 <= len(raw_topic_fields) <= 3:
        errors.append("CONFIG Case fields must contain 1 to 3 non-empty 主题 n fields")

    derived_sources = config.get("derived_field_sources")
    expected_derived_sources = {
        "brand_name": "品牌名称",
        "category_label": "品类",
        "official_domain": "官方域名",
    }
    if derived_sources != expected_derived_sources:
        errors.append("CONFIG derived_field_sources must trace brand, category, and domain to Case fields")
    brand = str(config.get("brand_name") or "").strip()
    category = str(config.get("category_label") or "").strip()
    official_domain = str(config.get("official_domain") or "").strip()
    object_type = str(config.get("brand_object_type") or "").strip()
    if not brand or brand != str(case_fields.get("品牌名称") or "").strip():
        errors.append("CONFIG brand_name must equal Case field 品牌名称")
    if not category:
        errors.append("CONFIG category_label must be a non-empty English normalization of 品类")
    if not official_domain or official_domain != str(case_fields.get("官方域名") or "").strip():
        errors.append("CONFIG official_domain must equal Case field 官方域名")
    if object_type not in {"company", "product"}:
        errors.append("CONFIG brand_object_type must equal company or product")

    topics: dict[str, dict] = {}
    raw_topics = config.get("topics")
    if not isinstance(raw_topics, list) or not 1 <= len(raw_topics) <= 3:
        errors.append("CONFIG topics must contain 1 to 3 topics in v6")
        raw_topics = raw_topics if isinstance(raw_topics, list) else []
    used_topic_sources: Counter = Counter()
    for index, topic in enumerate(raw_topics):
        prefix = f"CONFIG topics[{index}]"
        if not isinstance(topic, dict):
            errors.append(f"{prefix} must be an object")
            continue
        if "topic_type" in topic:
            errors.append(f"{prefix}.topic_type is retired in v6")
        topic_retired = sorted((set(topic) & V6_RETIRED_FIELDS) - {"topic_type"})
        if topic_retired:
            errors.append(f"{prefix} retired v6 fields are not allowed {topic_retired}")
        topic_id = normalize_label(topic.get("topic_id"))
        topic_text = str(topic.get("topic") or "").strip()
        source_field = str(topic.get("source_field") or "").strip()
        source_value = str(topic.get("source_value") or "").strip()
        if not topic_id or topic_id in topics:
            errors.append(f"{prefix}.topic_id must be non-empty and unique")
            continue
        if not topic_text:
            errors.append(f"{prefix}.topic must be a non-empty English normalization")
        if source_field not in raw_topic_fields:
            errors.append(f"{prefix}.source_field must reference an existing 主题 n Case field")
        elif source_value != str(raw_topic_fields[source_field]).strip():
            errors.append(f"{prefix}.source_value must equal Case field {source_field}")
        used_topic_sources[source_field] += 1
        topics[topic_id] = topic
    if used_topic_sources != Counter(raw_topic_fields.keys()):
        errors.append("CONFIG topics must map each non-empty 主题 n Case field exactly once")

    topic_count = len(raw_topics)
    attribute_plans = (
        _validate_v7_attribute_plan(config, topics, case_fields, errors, warnings)
        if require_attribute_plan
        else {}
    )
    competitors = _v6_competitors(config, case_fields, errors, set(topics))
    competitor_names = [item["name"] for item in competitors if item.get("name")]
    expected_competitors_by_topic: dict[str, list[str]] = {
        topic_id: [
            item["name"]
            for item in competitors
            if item.get("name") and topic_id in item.get("topic_ids", set())
        ]
        for topic_id in topics
    }
    for topic_id, names in expected_competitors_by_topic.items():
        if not 1 <= len(names) <= 3:
            errors.append(
                f"CONFIG topic.{topic_id} must have 1 to 3 applicable formal competitors"
            )

    quotas = config.get("quotas")
    if not isinstance(quotas, dict):
        errors.append("CONFIG quotas must be an object in v6")
        quotas = {}
    base_topic_quota = quotas.get("per_topic")
    if not flexible_topic_quotas and base_topic_quota != V6_PER_TOPIC_QUOTAS:
        errors.append("CONFIG quotas.per_topic must preserve the default 14/3/1/0/1/1 quota")
        base_topic_quota = dict(V6_PER_TOPIC_QUOTAS)
    elif flexible_topic_quotas:
        if not isinstance(base_topic_quota, dict) or set(base_topic_quota) != set(V6_PER_TOPIC_QUOTAS):
            errors.append("CONFIG quotas.per_topic must contain all six diagnostic intents")
            base_topic_quota = dict(V6_PER_TOPIC_QUOTAS)
        elif any(
            isinstance(value, bool) or not isinstance(value, int)
            for value in base_topic_quota.values()
        ):
            errors.append("CONFIG quotas.per_topic values must be integers")
            base_topic_quota = dict(V6_PER_TOPIC_QUOTAS)
        else:
            base_topic_quota = dict(base_topic_quota)
    else:
        base_topic_quota = dict(V6_PER_TOPIC_QUOTAS)
    raw_overrides = quotas.get("topic_overrides", {})
    if not isinstance(raw_overrides, dict):
        errors.append("CONFIG quotas.topic_overrides must be an object")
        raw_overrides = {}
    normalized_overrides = {
        normalize_label(topic_id): quota for topic_id, quota in raw_overrides.items()
    }
    if len(normalized_overrides) != len(raw_overrides):
        errors.append("CONFIG quotas.topic_overrides topic ids must be unique after normalization")
    unknown_overrides = sorted(set(normalized_overrides) - set(topics))
    if unknown_overrides:
        errors.append(f"CONFIG quotas.topic_overrides references unknown topics {unknown_overrides}")

    expected_topic_quotas: dict[str, dict[str, int]] = {}
    for topic_id in topics:
        applicable_competitor_count = len(expected_competitors_by_topic.get(topic_id, []))
        has_override = topic_id in normalized_overrides
        if not flexible_topic_quotas and not has_override and applicable_competitor_count != 3:
            errors.append(
                f"CONFIG quotas.topic_overrides.{topic_id} must declare the Topic-specific "
                "competitor quota and Discovery reallocation"
            )
            topic_quota = dict(V6_PER_TOPIC_QUOTAS)
            topic_quota["competitor"] = applicable_competitor_count
            topic_quota["discovery"] = 17 - applicable_competitor_count
        else:
            topic_quota = normalized_overrides.get(topic_id, base_topic_quota)
        quota_path = (
            f"CONFIG quotas.topic_overrides.{topic_id}"
            if has_override
            else "CONFIG quotas.per_topic"
        )
        if not isinstance(topic_quota, dict) or set(topic_quota) != set(V6_PER_TOPIC_QUOTAS):
            errors.append(f"{quota_path} must contain all six diagnostic intents")
            topic_quota = dict(V6_PER_TOPIC_QUOTAS)
        elif any(isinstance(value, bool) or not isinstance(value, int) for value in topic_quota.values()):
            errors.append(f"{quota_path} values must be integers")
            topic_quota = dict(V6_PER_TOPIC_QUOTAS)
        else:
            if topic_quota["discovery"] < 1:
                errors.append(f"{quota_path}.discovery must be at least 1")
            fixed_counts = {
                "competitor": applicable_competitor_count,
                "verification": (
                    0 if fixed_v8_presales_quotas else topic_quota.get("verification", 1)
                ),
                "accuracy": 0,
                "evaluation": (
                    1 + applicable_competitor_count
                    if fixed_v8_presales_quotas
                    else 1
                ),
                "category_awareness": 1,
            }
            if fixed_v8_presales_quotas:
                fixed_counts["discovery"] = 23 - 2 * applicable_competitor_count
            for intent, fixed_count in fixed_counts.items():
                if topic_quota[intent] != fixed_count:
                    errors.append(f"{quota_path}.{intent} must remain {fixed_count}")
            if flexible_topic_quotas and not fixed_v8_presales_quotas:
                non_discovery_total = sum(
                    count
                    for intent, count in topic_quota.items()
                    if intent != "discovery"
                )
                if topic_quota["discovery"] <= non_discovery_total:
                    errors.append(
                        f"{quota_path}.discovery must be a strict majority for {topic_id}: "
                        f"got {topic_quota['discovery']} Discovery and {non_discovery_total} "
                        "non-Discovery Prompts"
                    )
        expected_topic_quotas[topic_id] = dict(topic_quota)
        if fixed_v8_presales_quotas and sum(topic_quota.values()) != 25:
            errors.append(f"{quota_path} must total exactly 25 Prompts for {topic_id}")

    expected_intent_counter: Counter = Counter()
    for topic_quota in expected_topic_quotas.values():
        expected_intent_counter.update(topic_quota)
    expected_intent_quotas = dict(expected_intent_counter)
    expected_total = sum(expected_intent_counter.values())
    if config.get("expected_total") != expected_total:
        errors.append(f"CONFIG expected_total must equal the active Topic quotas ({expected_total})")
    max_total = V8_MAX_TOTAL if fixed_v8_presales_quotas else V6_MAX_TOTAL
    if expected_total > max_total:
        errors.append(f"CONFIG batch total must not exceed {max_total}")
    if quotas.get("diagnosis_intent") != expected_intent_quotas:
        errors.append("CONFIG quotas.diagnosis_intent must equal the sum of active Topic quotas")

    required_fields = {
        "question_id",
        "topic_id",
        "diagnosis_intent",
        "formal_visibility_eligible",
        "intent_key",
        "user_question",
        "zh_translation",
        "monitoring_prompt",
        "quality_checks",
    }
    question_ids: set[str] = set()
    intent_keys: set[str] = set()
    diagnostic_counts: Counter = Counter()
    topic_counts: dict[str, Counter] = {topic_id: Counter() for topic_id in topics}
    competitor_coverage: dict[str, Counter] = {topic_id: Counter() for topic_id in topics}
    evaluation_coverage: dict[str, Counter] = {topic_id: Counter() for topic_id in topics}
    competitor_templates: dict[str, list[str]] = {topic_id: [] for topic_id in topics}
    normalized_questions: Counter = Counter()
    validation_item_total = 0

    for index, row in enumerate(questions):
        prefix = f"QUESTION[{index}]"
        if not isinstance(row, dict):
            errors.append(f"{prefix} must be an object")
            continue
        missing = sorted(required_fields - set(row))
        if missing:
            errors.append(f"{prefix} missing fields {missing}")
            continue
        present_retired = sorted(V6_RETIRED_FIELDS & set(row))
        if present_retired:
            errors.append(f"{prefix} retired v6 fields are not allowed {present_retired}")
        question_id = str(row.get("question_id") or "").strip()
        if not question_id or question_id in question_ids:
            errors.append(f"{prefix}.question_id must be non-empty and unique")
        question_ids.add(question_id)
        intent_key = normalize_label(row.get("intent_key"))
        if not intent_key or intent_key in intent_keys:
            errors.append(f"{prefix}.intent_key must be non-empty and unique")
        intent_keys.add(intent_key)
        topic_id = normalize_label(row.get("topic_id"))
        if topic_id not in topics:
            errors.append(f"{prefix} {question_id}: unknown topic_id {row.get('topic_id')!r}")
        intent = str(row.get("diagnosis_intent") or "").strip()
        if intent not in V6_PER_TOPIC_QUOTAS:
            errors.append(f"{prefix} {question_id}: unsupported diagnosis_intent {intent!r}")
        else:
            diagnostic_counts[intent] += 1
            if topic_id in topic_counts:
                topic_counts[topic_id][intent] += 1
            expected_analysis = V6_ANALYSIS_TYPES[intent]
            if expected_analysis is None:
                if "analysis_type" in row and row["analysis_type"] not in (None, ""):
                    errors.append(
                        f"{prefix} {question_id}: analysis_type must be empty or omitted for {intent}"
                    )
            elif "analysis_type" not in row:
                errors.append(f"{prefix} {question_id}: missing fields ['analysis_type']")
            elif row.get("analysis_type") != expected_analysis:
                errors.append(
                    f"{prefix} {question_id}: analysis_type must equal {expected_analysis} for {intent}"
                )
            expected_eligible = intent in {"discovery", "category_awareness"}
            if row.get("formal_visibility_eligible") is not expected_eligible:
                errors.append(
                    f"{prefix} {question_id}: formal_visibility_eligible must equal {expected_eligible} for {intent}"
                )

        text = str(row.get("user_question") or "").strip()
        if not text:
            errors.append(f"{prefix} {question_id}: user_question is empty")
        else:
            normalized_questions[normalize(text)] += 1
        if str(row.get("monitoring_prompt") or "").strip() != text:
            errors.append(f"{prefix} {question_id}: monitoring_prompt must equal user_question")
        translation = str(row.get("zh_translation") or "").strip()
        if not translation or not CJK_CHARACTER.search(translation):
            errors.append(f"{prefix} {question_id}: zh_translation must contain Chinese characters")
        if intent == "evaluation":
            if V6_EVALUATION_META_TOPIC.search(text):
                errors.append(
                    f"{prefix} {question_id}: evaluation user_question must not contain "
                    "the meta word 'topic'"
                )
        quality = row.get("quality_checks")
        if not isinstance(quality, dict) or not quality or any(value is not True for value in quality.values()):
            errors.append(f"{prefix} {question_id}: all supplied quality_checks must pass")

        mentioned = [name for name in competitor_names if _contains_v6_entity(text, name)]
        has_target = bool(brand) and _contains_v6_entity(text, brand)
        if intent in {"discovery", "category_awareness"}:
            if has_target or mentioned:
                errors.append(f"{prefix} {question_id}: {intent} must not name configured brands")
            if intent == "discovery" and not _v6_requests_concrete_candidates(text):
                errors.append(f"{prefix} {question_id}: discovery must request concrete candidates")
        elif intent == "competitor":
            if not has_target or len(mentioned) != 1:
                errors.append(f"{prefix} {question_id}: competitor must name target and exactly one competitor")
            elif topic_id in competitor_coverage:
                if mentioned[0] not in expected_competitors_by_topic.get(topic_id, []):
                    errors.append(
                        f"{prefix} {question_id}: competitor {mentioned[0]!r} is not applicable "
                        f"to {topic_id}"
                    )
                else:
                    competitor_coverage[topic_id][mentioned[0]] += 1
                    controlled = _replace_v6_entity(text, mentioned[0], "<COMPETITOR>")
                    competitor_templates[topic_id].append(controlled)
        elif intent in {"verification", "accuracy"}:
            if not has_target or mentioned:
                errors.append(f"{prefix} {question_id}: {intent} must name only the target brand")
        elif intent == "evaluation":
            if fixed_v8_presales_quotas:
                applicable = expected_competitors_by_topic.get(topic_id, [])
                named_brands = ([brand] if has_target else []) + mentioned
                if len(named_brands) != 1:
                    errors.append(
                        f"{prefix} {question_id}: evaluation must name exactly one target or "
                        "applicable competitor brand"
                    )
                elif named_brands[0] != brand and named_brands[0] not in applicable:
                    errors.append(
                        f"{prefix} {question_id}: evaluation brand {named_brands[0]!r} "
                        f"is not applicable to {topic_id}"
                    )
                elif topic_id in evaluation_coverage:
                    evaluation_coverage[topic_id][named_brands[0]] += 1
            elif not has_target or mentioned:
                errors.append(f"{prefix} {question_id}: evaluation must name only the target brand")

        topic_text = str(topics.get(topic_id, {}).get("topic") or "")
        if intent == "verification":
            items = row.get("validation_items")
            if not isinstance(items, list) or not 3 <= len(items) <= 5:
                errors.append(f"{prefix} {question_id}: validation_items must contain 3 to 5 items")
                items = items if isinstance(items, list) else []
            if items and not _v6_translation_has_ordered_item_markers(translation, len(items)):
                errors.append(
                    f"{prefix} {question_id}: verification zh_translation must include "
                    "an ordered Chinese translation for every validation item"
                )
            validation_item_total += len(items)
            for item_index, item in enumerate(items):
                item_prefix = f"{prefix} {question_id}: validation_items[{item_index}]"
                if not isinstance(item, dict):
                    errors.append(f"{item_prefix} must be an object")
                    continue
                expected_item_fields = {"source_field", "source_value", "statement"}
                if set(item) != expected_item_fields:
                    errors.append(
                        f"{item_prefix} must contain exactly source_field, source_value, and statement"
                    )
                source_field = str(item.get("source_field") or "").strip()
                if (
                    source_field not in case_fields
                    or not V6_ATTRIBUTE_SOURCE_FIELD.fullmatch(source_field)
                ):
                    errors.append(
                        f"{item_prefix}.source_field must reference an existing supported Case field"
                    )
                elif str(item.get("source_value") or "").strip() != str(
                    case_fields[source_field]
                ).strip():
                    errors.append(f"{item_prefix}.source_value must equal its Case field")
                if not str(item.get("statement") or "").strip():
                    errors.append(f"{prefix} {question_id}: each validation item needs an atomic statement")
                elif normalize_template_text(item["statement"]) not in normalize_template_text(text):
                    errors.append(
                        f"{prefix} {question_id}: every validation item statement must appear in the Prompt"
                    )
            template_terms = (
                "determine whether each statement is true",
                "yes / no / unknown",
                "explain the basis for your judgment",
            )
            lowered = text.casefold()
            if not all(term in lowered for term in template_terms):
                errors.append(f"{prefix} {question_id}: must use the batch Yes / No / Unknown template")
            if items and all(
                isinstance(item, dict) and str(item.get("statement") or "").strip()
                for item in items
            ):
                expected_validation = build_v6_validation_prompt(brand, items)
                if text != expected_validation:
                    errors.append(
                        f"{prefix} {question_id}: must exactly equal the batch Validation template"
                    )
            if require_attribute_plan and topic_id in attribute_plans:
                expected_p1_items = [
                    {
                        "source_field": entry.get("source_field"),
                        "source_value": entry.get("source_value"),
                        "statement": entry.get("verification_statement"),
                    }
                    for entry in attribute_plans[topic_id].get("P1", [])
                ]
                if items != expected_p1_items:
                    errors.append(
                        f"{prefix} {question_id}: validation_items must exactly match "
                        "the ordered P1 attribute plan for its Topic"
                    )
        if intent == "evaluation" and topic_id in topics:
            evaluation_brand = brand
            if fixed_v8_presales_quotas:
                named_brands = ([brand] if has_target else []) + mentioned
                if len(named_brands) == 1:
                    evaluation_brand = named_brands[0]
            expected = build_v6_sentiment_prompt(
                category, object_type, evaluation_brand, topic_text
            )
            if text != expected:
                errors.append(f"{prefix} {question_id}: must equal the fixed sentiment template")
        if intent == "category_awareness" and topic_id in topics:
            expected = build_v6_market_perception_prompt(category, topic_text)
            if text != expected:
                errors.append(
                    f"{prefix} {question_id}: must equal the category-first market perception template"
                )

    if len(questions) != expected_total:
        errors.append(f"COUNT expected {expected_total}, got {len(questions)}")
    if len(questions) > max_total:
        errors.append(f"COUNT batch total must not exceed {max_total}")
    duplicate_texts = sorted(text for text, count in normalized_questions.items() if text and count > 1)
    if duplicate_texts:
        errors.append(f"DUPLICATE normalized user_question values must be unique {duplicate_texts}")
    check_quota(errors, "diagnosis_intent", diagnostic_counts, expected_intent_quotas)
    for topic_id in topics:
        check_quota(errors, f"topic.{topic_id}", topic_counts[topic_id], expected_topic_quotas[topic_id])
        expected_competitor_coverage = Counter({
            name: 1 for name in expected_competitors_by_topic.get(topic_id, [])
        })
        if competitor_coverage[topic_id] != expected_competitor_coverage:
            errors.append(
                f"COVERAGE topic.{topic_id}.competitors must cover each applicable competitor exactly once"
            )
        if fixed_v8_presales_quotas:
            expected_evaluation_coverage = Counter({
                name: 1
                for name in [brand, *expected_competitors_by_topic.get(topic_id, [])]
            })
            if evaluation_coverage[topic_id] != expected_evaluation_coverage:
                errors.append(
                    f"COVERAGE topic.{topic_id}.evaluations must cover the target and each "
                    "applicable competitor exactly once"
                )
        templates = competitor_templates[topic_id]
        if len(templates) >= 2 and len(set(templates)) != 1:
            errors.append(f"QUESTION topic.{topic_id}: competitor questions must keep the same wording")

    summary = {
        "total": len(questions),
        "topic_count": topic_count,
        "diagnosis_intent": dict(diagnostic_counts),
        "analysis_type": dict(Counter(
            row.get("analysis_type")
            for row in questions
            if isinstance(row, dict) and isinstance(row.get("analysis_type"), str)
        )),
        "topic_diagnosis_intent": {
            topic_id: dict(counts) for topic_id, counts in topic_counts.items()
        },
        "validation_item_count": validation_item_total,
        "visibility_module_total": sum(
            1 for row in questions
            if isinstance(row, dict)
            and (
                row.get("analysis_type") == "visibility"
                or row.get("analysis_type") == "visibility,sentiment"
                or (
                    row.get("analysis_type") is None
                    and row.get("formal_visibility_eligible") is True
                )
            )
        ),
        "formal_visibility_total": sum(
            1 for row in questions
            if isinstance(row, dict) and row.get("formal_visibility_eligible") is True
        ),
        "topic_competitor_coverage": {
            topic_id: dict(coverage) for topic_id, coverage in competitor_coverage.items()
        },
        "topic_evaluation_coverage": {
            topic_id: dict(coverage) for topic_id, coverage in evaluation_coverage.items()
        },
    }
    if require_attribute_plan:
        summary["attribute_priority_counts"] = {
            topic_id: {
                priority: len(plan.get(priority, []))
                for priority in V7_ATTRIBUTE_PRIORITIES
            }
            for topic_id, plan in attribute_plans.items()
        }
        summary["excluded_attribute_candidates"] = {
            topic_id: len(plan.get("excluded", []))
            for topic_id, plan in attribute_plans.items()
        }
    return errors, warnings, summary


def validate_v5(data: dict) -> tuple[list[str], list[str], dict]:
    """Validate the attribute-aware, three-topic presales question-bank contract."""

    errors: list[str] = []
    warnings: list[str] = []
    config = data.get("config")
    if not isinstance(config, dict):
        return ["SCHEMA config must be an object in v5"], warnings, {}
    questions = data.get("questions")
    if not isinstance(questions, list):
        return ["SCHEMA questions must be an array"], warnings, {}

    if "observed_associations" in config or "observed_associations" in data:
        errors.append(
            "CONFIG observed_associations 属于回答采集结果，不得写入评测集 Case 配置"
        )
    if config.get("expected_total") != 51:
        errors.append("CONFIG expected_total must equal 51 in v5")

    raw_quotas = config.get("quotas")
    if not isinstance(raw_quotas, dict):
        errors.append("CONFIG quotas must be an object in v5")
        raw_quotas = {}
    if raw_quotas.get("diagnostic_intent") != V5_DEFAULT_QUOTAS["diagnostic_intent"]:
        errors.append("CONFIG quotas.diagnostic_intent must equal the v5 30/9/3/3/3/3 allocation")
    if raw_quotas.get("per_topic") != V5_PER_TOPIC_QUOTAS:
        errors.append("CONFIG quotas.per_topic must equal discovery=10 and 3/1/1/1/1 for every topic")

    topic_ids: set[str] = set()
    topic_types: dict[str, str] = {}
    raw_topics = config.get("topics")
    if not isinstance(raw_topics, list) or len(raw_topics) != 3:
        errors.append("CONFIG topics must contain exactly 3 topics in v5")
        raw_topics = raw_topics if isinstance(raw_topics, list) else []
    for index, topic in enumerate(raw_topics):
        prefix = f"CONFIG topics[{index}]"
        if not isinstance(topic, dict):
            errors.append(f"{prefix} must be an object")
            continue
        topic_id = normalize_label(topic.get("topic_id"))
        topic_type = str(topic.get("topic_type") or "").strip().casefold()
        topic_text = str(topic.get("topic") or "").strip()
        if not topic_id or topic_id in topic_ids:
            errors.append(f"{prefix}.topic_id must be non-empty and unique")
            continue
        topic_ids.add(topic_id)
        topic_types[topic_id] = topic_type
        if topic_type not in {"coverage", "depth"}:
            errors.append(f"{prefix}.topic_type must equal coverage or depth")
        if not topic_text:
            errors.append(f"{prefix}.topic must be a non-empty string")
        topic_quota = topic.get("prompt_quota")
        if topic_quota is not None and topic_quota != V5_PER_TOPIC_QUOTAS:
            errors.append(f"{prefix}.prompt_quota must equal the v5 per-topic allocation")

    attribute_ids: set[str] = set()
    attribute_topics: dict[str, set[str]] = {}
    raw_attributes = config.get("target_attributes")
    if not isinstance(raw_attributes, list) or not raw_attributes:
        errors.append("CONFIG target_attributes must contain at least one selected attribute")
        raw_attributes = []
    for index, attribute in enumerate(raw_attributes):
        prefix = f"CONFIG target_attributes[{index}]"
        if not isinstance(attribute, dict):
            errors.append(f"{prefix} must be an object")
            continue
        attribute_id = str(attribute.get("attribute_id") or "").strip()
        if not attribute_id or attribute_id in attribute_ids:
            errors.append(f"{prefix}.attribute_id must be non-empty and unique")
            continue
        attribute_ids.add(attribute_id)
        attribute_type = str(attribute.get("attribute_type") or "").strip()
        if attribute_type not in V5_ATTRIBUTE_TYPES:
            errors.append(f"{prefix}.attribute_type is not supported")
        if not str(attribute.get("attribute") or "").strip():
            errors.append(f"{prefix}.attribute must be a non-empty string")
        if not str(attribute.get("business_relevance") or "").strip():
            errors.append(f"{prefix}.business_relevance must be a non-empty string")
        sources = attribute.get("evidence_sources")
        if not isinstance(sources, list) or not sources:
            errors.append(f"{prefix}.evidence_sources must contain at least one source")
        else:
            for source_index, source in enumerate(sources):
                if not isinstance(source, dict):
                    errors.append(f"{prefix}.evidence_sources[{source_index}] must be an object")
                    continue
                if source.get("evidence_type") not in V5_EVIDENCE_TYPES:
                    errors.append(f"{prefix}.evidence_sources[{source_index}].evidence_type is invalid")
                if not str(source.get("detail") or "").strip():
                    errors.append(f"{prefix}.evidence_sources[{source_index}].detail must be non-empty")
        mapped_topics = attribute.get("topic_ids")
        if not isinstance(mapped_topics, list) or not mapped_topics:
            errors.append(f"{prefix}.topic_ids must contain at least one topic_id")
            mapped_topics = []
        normalized_topics = {normalize_label(item) for item in mapped_topics if normalize_label(item)}
        unknown_topics = normalized_topics - topic_ids
        if unknown_topics:
            errors.append(f"{prefix}.topic_ids contains unknown topics {sorted(unknown_topics)}")
        attribute_topics[attribute_id] = normalized_topics

    brand = str(config.get("brand_name") or "").strip()
    if not brand:
        errors.append("CONFIG brand_name must be a non-empty string in v5")
    competitors = _v5_competitor_names(config, errors)

    question_ids: set[str] = set()
    intent_keys: set[str] = set()
    question_by_id: dict[str, dict] = {}
    diagnostic_counts: Counter = Counter()
    topic_counts: dict[str, Counter] = {topic_id: Counter() for topic_id in topic_ids}
    competitor_coverage: dict[str, Counter] = {topic_id: Counter() for topic_id in topic_ids}
    validation_rows: list[dict] = []

    required_fields = {
        "question_id",
        "topic_id",
        "topic_type",
        "diagnostic_intent",
        "metric_scopes",
        "attribute_ids",
        "intent_key",
        "user_question",
        "zh_translation",
        "monitoring_prompt",
        "quality_checks",
    }
    for index, row in enumerate(questions):
        prefix = f"QUESTION[{index}]"
        if not isinstance(row, dict):
            errors.append(f"{prefix} must be an object")
            continue
        missing = sorted(required_fields - set(row))
        if missing:
            errors.append(f"{prefix} missing fields {missing}")
            continue
        question_id = str(row.get("question_id") or "").strip()
        if not question_id or question_id in question_ids:
            errors.append(f"{prefix}.question_id must be non-empty and unique")
        else:
            question_ids.add(question_id)
            question_by_id[question_id] = row
        intent_key = normalize_label(row.get("intent_key"))
        if not intent_key or intent_key in intent_keys:
            errors.append(f"{prefix}.intent_key must be non-empty and unique")
        else:
            intent_keys.add(intent_key)
        topic_id = normalize_label(row.get("topic_id"))
        if topic_id not in topic_ids:
            errors.append(f"{prefix} {question_id}: unknown topic_id {row.get('topic_id')!r}")
        elif str(row.get("topic_type") or "").strip().casefold() != topic_types.get(topic_id):
            errors.append(f"{prefix} {question_id}: topic_type does not match config.topics")
        diagnostic_intent = str(row.get("diagnostic_intent") or "").strip()
        if diagnostic_intent not in V5_PER_TOPIC_QUOTAS:
            errors.append(f"{prefix} {question_id}: unsupported diagnostic_intent {diagnostic_intent!r}")
        else:
            diagnostic_counts[diagnostic_intent] += 1
            if topic_id in topic_counts:
                topic_counts[topic_id][diagnostic_intent] += 1
            expected_scopes = list(V5_METRIC_SCOPES[diagnostic_intent])
            if row.get("metric_scopes") != expected_scopes:
                errors.append(
                    f"{prefix} {question_id}: metric_scopes must equal {expected_scopes} "
                    f"for diagnostic_intent={diagnostic_intent}"
                )

        row_attribute_ids = row.get("attribute_ids")
        if not isinstance(row_attribute_ids, list) or not row_attribute_ids:
            errors.append(f"{prefix} {question_id}: attribute_ids must contain at least one target attribute")
            row_attribute_ids = []
        for attribute_id in row_attribute_ids:
            if attribute_id not in attribute_ids:
                errors.append(f"{prefix} {question_id}: unknown attribute_id {attribute_id!r}")
            elif topic_id not in attribute_topics.get(attribute_id, set()):
                errors.append(
                    f"{prefix} {question_id}: attribute_id {attribute_id!r} is not mapped to topic {topic_id!r}"
                )

        user_question = str(row.get("user_question") or "").strip()
        if not user_question:
            errors.append(f"{prefix} {question_id}: user_question is empty")
        if str(row.get("monitoring_prompt") or "").strip() != user_question:
            errors.append(f"{prefix} {question_id}: monitoring_prompt must equal user_question")
        translation = str(row.get("zh_translation") or "").strip()
        if not translation or not CJK_CHARACTER.search(translation):
            errors.append(f"{prefix} {question_id}: zh_translation must contain Chinese characters")
        quality = row.get("quality_checks")
        if not isinstance(quality, dict) or any(value is not True for value in quality.values()) or not quality:
            errors.append(f"{prefix} {question_id}: all supplied quality_checks must pass")

        mentioned_competitors = [name for name in competitors if contains_entity_name(user_question, name)]
        has_target = bool(brand) and contains_entity_name(user_question, brand)
        if diagnostic_intent in {"discovery", "market_perception"}:
            if has_target or mentioned_competitors:
                errors.append(f"{prefix} {question_id}: {diagnostic_intent} must not name configured brands")
        elif diagnostic_intent == "competitor":
            if not has_target or len(mentioned_competitors) != 1:
                errors.append(f"{prefix} {question_id}: competitor must name target and exactly one formal competitor")
            elif topic_id in competitor_coverage:
                competitor_coverage[topic_id][mentioned_competitors[0]] += 1
        elif diagnostic_intent in {"validation", "accuracy", "sentiment"}:
            if not has_target or mentioned_competitors:
                errors.append(f"{prefix} {question_id}: {diagnostic_intent} must name only the target brand")

        if diagnostic_intent == "validation":
            paired_ids = row.get("paired_discovery_ids")
            if not isinstance(paired_ids, list) or not paired_ids:
                errors.append(f"{prefix} {question_id}: validation requires paired_discovery_ids")
            validation_rows.append(row)
        if diagnostic_intent == "accuracy":
            for field in ("fact_value", "official_source_url", "fact_checked_at"):
                if not str(row.get(field) or "").strip():
                    errors.append(f"{prefix} {question_id}: accuracy requires non-empty {field}")

    if len(questions) != 51:
        errors.append(f"COUNT expected 51, got {len(questions)}")
    check_quota(errors, "diagnostic_intent", diagnostic_counts, V5_DEFAULT_QUOTAS["diagnostic_intent"])
    for topic_id in topic_ids:
        check_quota(errors, f"topic.{topic_id}", topic_counts[topic_id], V5_PER_TOPIC_QUOTAS)
        if competitors and competitor_coverage[topic_id] != Counter({name: 1 for name in competitors}):
            errors.append(f"COVERAGE topic.{topic_id}.competitors must cover each formal competitor exactly once")

    for row in validation_rows:
        question_id = str(row.get("question_id") or "")
        paired_ids = row.get("paired_discovery_ids") or []
        for paired_id in paired_ids:
            paired = question_by_id.get(str(paired_id))
            if not paired or paired.get("diagnostic_intent") != "discovery":
                errors.append(f"QUESTION {question_id}: paired_discovery_id {paired_id!r} is not a discovery question")
                continue
            if normalize_label(paired.get("topic_id")) != normalize_label(row.get("topic_id")):
                errors.append(f"QUESTION {question_id}: paired discovery must use the same topic")
            if not set(row.get("attribute_ids") or []) & set(paired.get("attribute_ids") or []):
                errors.append(f"QUESTION {question_id}: paired discovery must share a target attribute")

    summary = {
        "total": len(questions),
        "diagnostic_intent": dict(diagnostic_counts),
        "topic_diagnostic_intent": {
            topic_id: dict(counts) for topic_id, counts in topic_counts.items()
        },
        "target_attribute_count": len(attribute_ids),
        "metric_scope_policy": {key: list(value) for key, value in V5_METRIC_SCOPES.items()},
    }
    return errors, warnings, summary


def validate(data: dict) -> tuple[list[str], list[str], dict]:
    errors: list[str] = []
    warnings: list[str] = []
    config = data.get("config") or {}
    schema_version = str(data.get("schema_version") or config.get("schema_version") or "").strip()
    if schema_version == V8_SCHEMA_VERSION:
        return validate_v8(data)
    if schema_version == V7_SCHEMA_VERSION:
        return validate_v6(data, require_attribute_plan=True)
    if schema_version == V6_SCHEMA_VERSION:
        return validate_v6(data)
    if schema_version == V5_SCHEMA_VERSION:
        return validate_v5(data)
    if schema_version and schema_version not in {CURRENT_SCHEMA_VERSION, *LEGACY_SCHEMA_VERSIONS}:
        errors.append(f"SCHEMA unsupported schema_version {schema_version}")
    is_v4_schema = schema_version == CURRENT_SCHEMA_VERSION
    # Keep v3 readable and validated for existing banks while v4 becomes the
    # generation target. v3 does not require the six diagnostic-intent fields.
    is_current_schema = schema_version in {COMPATIBLE_V3_SCHEMA_VERSION, CURRENT_SCHEMA_VERSION}
    is_legacy_v2 = schema_version == "overseas-geo-question-bank/v2"
    requires_term_assessment = is_current_schema or is_legacy_v2
    schema_label = "v4" if is_v4_schema else "v3"
    questions = data.get("questions")
    if not isinstance(questions, list):
        return ["SCHEMA questions must be an array"], warnings, {}

    expected_total = config.get("expected_total", 50)
    quotas = config.get("quotas") or (V4_DEFAULT_QUOTAS if is_v4_schema else DEFAULT_QUOTAS)
    if is_current_schema:
        configured_funnels = set((quotas.get("funnel_intent") or {}).keys())
        if "awareness" in configured_funnels:
            errors.append("CONFIG funnel_intent.awareness is retired in v3; use recommendation")
    brand = str(config.get("brand_name") or "").strip()
    product = str(config.get("product_name") or "").strip()
    raw_aliases = config.get("aliases") or []
    if not isinstance(raw_aliases, list):
        errors.append("CONFIG aliases must be an array")
        raw_aliases = []
    aliases = [str(item).strip() for item in raw_aliases if str(item).strip()]
    if is_current_schema and not brand:
        errors.append("CONFIG brand_name must be a non-empty string in v3")
    competitors = [str(item) for item in config.get("competitors", []) if str(item).strip()]
    formal_competitor_terms: list[str] = []
    formal_competitor_profiles: list[dict[str, object]] = []
    formal_competitor_tiers: Counter = Counter()
    raw_competitor_selection = config.get("competitor_selection")
    if raw_competitor_selection is not None:
        if not isinstance(raw_competitor_selection, dict):
            errors.append("CONFIG competitor_selection must be an object")
        else:
            if raw_competitor_selection.get("status") != "frozen":
                errors.append("CONFIG competitor_selection.status must equal frozen")
            if raw_competitor_selection.get("selection_count") != 3:
                errors.append("CONFIG competitor_selection.selection_count must equal 3")
            formal_competitors = raw_competitor_selection.get("formal_competitors")
            if not isinstance(formal_competitors, list) or len(formal_competitors) != 3:
                errors.append("CONFIG competitor_selection.formal_competitors must contain exactly 3 items")
                formal_competitors = []
            formal_name_keys: set[str] = set()
            for index, item in enumerate(formal_competitors, start=1):
                prefix = f"CONFIG competitor_selection.formal_competitors[{index}]"
                if not isinstance(item, dict):
                    errors.append(f"{prefix} must be an object")
                    continue
                name = str(item.get("name") or "").strip()
                if not name:
                    errors.append(f"{prefix}.name must be a non-empty string")
                else:
                    name_key = normalize(name)
                    if name_key in formal_name_keys:
                        errors.append(f"{prefix}.name duplicates another formal competitor")
                    formal_name_keys.add(name_key)
                    formal_competitor_terms.append(name)
                item_aliases = item.get("aliases") or []
                if not isinstance(item_aliases, list):
                    errors.append(f"{prefix}.aliases must be an array")
                    item_aliases = []
                formal_competitor_terms.extend(
                    str(alias).strip() for alias in item_aliases if str(alias).strip()
                )
                formal_competitor_profiles.append({
                    "name": name or f"formal_competitor_{index}",
                    "terms": [name, *item_aliases] if name else list(item_aliases),
                })
                tier = str(item.get("comparability_tier") or "").strip()
                if tier not in {"direct", "adjacent", "fallback"}:
                    errors.append(f"{prefix}.comparability_tier must be direct, adjacent, or fallback")
                else:
                    formal_competitor_tiers[tier] += 1
                policy = item.get("comparison_policy")
                if not isinstance(policy, dict):
                    errors.append(f"{prefix}.comparison_policy must be an object")
                    continue
                allowed_dimensions = policy.get("allowed_dimensions")
                if not isinstance(allowed_dimensions, list):
                    errors.append(f"{prefix}.comparison_policy.allowed_dimensions must be an array")
                mode = policy.get("mode")
                expected_mode = (
                    "standard_evidence_based" if tier == "direct" else "neutral_shared_dimensions_only"
                )
                if tier in {"direct", "adjacent", "fallback"} and mode != expected_mode:
                    errors.append(
                        f"{prefix}.comparison_policy.mode must equal {expected_mode} "
                        f"for comparability_tier={tier}"
                    )
    excluded = [str(item) for item in config.get("excluded_categories", []) if str(item).strip()]
    category_expression_set = config.get("category_expression_set")
    configured_topic_ids: set[str] = set()
    configured_topics: dict[str, str] = {}
    brand_evaluation_specs: dict[str, tuple[str, list[str]]] = {}
    raw_topics = config.get("topics")
    if is_current_schema:
        if not isinstance(raw_topics, list) or not raw_topics:
            errors.append("CONFIG topics must be a non-empty array in v3")
        else:
            for index, topic in enumerate(raw_topics):
                prefix = f"CONFIG topics[{index}]"
                if not isinstance(topic, dict):
                    errors.append(f"{prefix} must be an object")
                    continue
                topic_id = normalize_label(topic.get("topic_id"))
                topic_text = str(topic.get("topic") or "").strip()
                evaluation_subject = str(topic.get("brand_evaluation_subject") or "").strip()
                raw_evaluation_dimensions = topic.get("brand_evaluation_dimensions")
                if not topic_id:
                    errors.append(f"{prefix}.topic_id must be a non-empty string")
                elif topic_id in configured_topic_ids:
                    errors.append(f"{prefix}.topic_id duplicates another topic")
                else:
                    configured_topic_ids.add(topic_id)
                    configured_topics[topic_id] = topic_text
                if not topic_text:
                    errors.append(f"{prefix}.topic must be a non-empty string")
                if not evaluation_subject and not is_v4_schema:
                    errors.append(f"{prefix}.brand_evaluation_subject must be a non-empty string")
                if not isinstance(raw_evaluation_dimensions, list):
                    if not is_v4_schema:
                        errors.append(f"{prefix}.brand_evaluation_dimensions must be an array")
                    evaluation_dimensions: list[str] = []
                else:
                    evaluation_dimensions = [
                        str(item).strip()
                        for item in raw_evaluation_dimensions
                        if str(item).strip()
                    ]
                    if not is_v4_schema and len(evaluation_dimensions) < 2:
                        errors.append(
                            f"{prefix}.brand_evaluation_dimensions must contain at least 2 "
                            "concrete dimensions"
                        )
                    normalized_dimensions = [normalize(item) for item in evaluation_dimensions]
                    if not is_v4_schema and len(set(normalized_dimensions)) != len(normalized_dimensions):
                        errors.append(
                            f"{prefix}.brand_evaluation_dimensions must not contain duplicates"
                        )
                    abstract_dimensions = [
                        item
                        for item in evaluation_dimensions
                        if normalize(item) in ABSTRACT_EVALUATION_LABELS
                    ]
                    if abstract_dimensions and not is_v4_schema:
                        errors.append(
                            f"{prefix}.brand_evaluation_dimensions uses abstract labels "
                            f"{abstract_dimensions}; expand them into concrete decision factors"
                        )
                if topic_id and ((is_v4_schema and topic_text) or (evaluation_subject and len(evaluation_dimensions) >= 2)):
                    brand_evaluation_specs[topic_id] = (
                        evaluation_subject,
                        evaluation_dimensions,
                    )
    category_terms: dict[str, list[str]] = {
        "core_terms": [],
        "product_terms": [],
        "placeholder_blacklist": [],
    }
    if is_current_schema:
        if not isinstance(category_expression_set, dict):
            errors.append("CONFIG category_expression_set must be an object in v3")
        else:
            for field in category_terms:
                value = category_expression_set.get(field) or []
                if not isinstance(value, list):
                    errors.append(f"CONFIG category_expression_set.{field} must be an array")
                    value = []
                category_terms[field] = [str(item).strip() for item in value if str(item).strip()]
            if not any(
                category_terms[field]
                for field in ("core_terms", "product_terms")
            ):
                errors.append(
                    "CONFIG category_expression_set needs core_terms or product_terms"
                )
    category_label = str(config.get("category_label") or "").strip()
    brand_object_type = str(config.get("brand_object_type") or "").strip().casefold()
    if is_current_schema:
        if not category_label:
            errors.append("CONFIG category_label must be a non-empty string in v3")
        elif category_expression_set and not any(
            contains_name(category_label, term) or contains_name(term, category_label)
            for term in (*category_terms["core_terms"], *category_terms["product_terms"])
        ):
            errors.append(
                "CONFIG category_label must match a configured core_terms or product_terms expression"
            )
        if brand_object_type not in {"company", "product"}:
            errors.append("CONFIG brand_object_type must equal company or product in v3")
        if not is_v4_schema:
            branded_quota = int(((quotas.get("question_type") or {}).get("branded", 0)) or 0)
            if configured_topics and len(configured_topics) > branded_quota:
                errors.append(
                    "CONFIG topics cannot exceed the Branded question quota because each Topic "
                    "requires one brand sentiment question"
                )
    if is_current_schema and "min_geo_intent_counts" in config:
        errors.append("CONFIG min_geo_intent_counts is retired in v3; do not generate questions to fill angle quotas")
    if is_v4_schema:
        if expected_total != 50:
            errors.append("CONFIG expected_total must equal 50 in v4")
        if not isinstance(raw_topics, list) or len(raw_topics) != 1:
            errors.append("CONFIG topics must contain exactly 1 topic in v4")
        configured_question_quotas = (quotas.get("question_type") or {})
        if configured_question_quotas != V4_DEFAULT_QUOTAS["question_type"]:
            errors.append(
                "CONFIG quotas.question_type must equal visibility=40, sentiment=10 in v4"
            )
        configured_diagnostic_quotas = (quotas.get("diagnostic_intent") or {})
        if configured_diagnostic_quotas != V4_DEFAULT_QUOTAS["diagnostic_intent"]:
            errors.append(
                "CONFIG quotas.diagnostic_intent must equal the single-topic v4 allocation"
            )
        configured_funnel_quotas = (quotas.get("funnel_intent") or {})
        if configured_funnel_quotas != V4_DEFAULT_QUOTAS["funnel_intent"]:
            errors.append(
                "CONFIG quotas.funnel_intent must equal recommendation=18, comparison=19, "
                "decision=13 in v4"
            )
    raw_target_audiences = config.get("target_audiences")
    target_audiences: dict[str, str] = {}
    if raw_target_audiences is not None:
        if not isinstance(raw_target_audiences, list):
            errors.append("CONFIG target_audiences must be an array")
        else:
            for index, audience in enumerate(raw_target_audiences):
                label = str(audience).strip()
                key = normalize_label(label)
                if not key:
                    errors.append(f"CONFIG target_audiences[{index}] must be a non-empty string")
                elif key in target_audiences:
                    errors.append(f"CONFIG target_audiences[{index}] duplicates another target audience")
                else:
                    target_audiences[key] = label
    if requires_term_assessment and "required_term_coverage" not in config:
        errors.append(
            f"CONFIG required_term_coverage must be present in {schema_label}, even when empty"
        )
    raw_term_specs = config.get("required_term_coverage") or {}
    term_specs: dict[str, dict] = {}
    if not isinstance(raw_term_specs, dict):
        errors.append("CONFIG required_term_coverage must be an object")
    else:
        for concept, raw_spec in raw_term_specs.items():
            prefix = f"CONFIG required_term_coverage.{concept}"
            if not isinstance(raw_spec, dict):
                errors.append(f"{prefix} must be an object")
                continue
            terms = raw_spec.get("terms")
            if not isinstance(terms, list) or not [term for term in terms if str(term).strip()]:
                errors.append(f"{prefix}.terms must contain at least one term")
                continue
            spec = dict(raw_spec)
            spec["terms"] = [str(term).strip() for term in terms if str(term).strip()]
            for list_field in ("context_terms",):
                value = spec.get(list_field) or []
                if not isinstance(value, list):
                    errors.append(f"{prefix}.{list_field} must be an array")
                    value = []
                spec[list_field] = [str(term).strip() for term in value if str(term).strip()]
            for count_field in (
                "min_total", "min_generic", "min_branded", "min_visibility", "min_sentiment",
                "min_expanded", "min_acronym",
            ):
                value = spec.get(count_field, 0)
                if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                    errors.append(f"{prefix}.{count_field} must be a non-negative integer")
                    value = 0
                spec[count_field] = value
            spec["expanded_form"] = str(spec.get("expanded_form") or "").strip()
            spec["acronym"] = str(spec.get("acronym") or "").strip()
            if spec["min_expanded"] and not spec["expanded_form"]:
                errors.append(f"{prefix}.expanded_form is required when min_expanded is positive")
            if spec["min_acronym"] and not spec["acronym"]:
                errors.append(f"{prefix}.acronym is required when min_acronym is positive")
            term_specs[str(concept)] = spec

    term_assessment = config.get("professional_term_assessment")
    assessed_required_concepts: set[str] = set()
    if requires_term_assessment:
        if not isinstance(term_assessment, dict):
            errors.append(
                f"CONFIG professional_term_assessment must be an object in {schema_label}"
            )
        else:
            if term_assessment.get("status") != "completed":
                errors.append("CONFIG professional_term_assessment.status must equal completed")
            decisions = term_assessment.get("decisions")
            if not isinstance(decisions, list):
                errors.append("CONFIG professional_term_assessment.decisions must be an array")
                decisions = []
            if not decisions and not str(
                term_assessment.get("no_required_terms_reason") or ""
            ).strip():
                errors.append(
                    "CONFIG professional_term_assessment.no_required_terms_reason must be "
                    "non-empty when decisions is empty"
                )
            seen_decisions: set[str] = set()
            for index, decision in enumerate(decisions):
                prefix = f"CONFIG professional_term_assessment.decisions[{index}]"
                if not isinstance(decision, dict):
                    errors.append(f"{prefix} must be an object")
                    continue
                concept = str(decision.get("concept") or "").strip()
                outcome = str(decision.get("decision") or "").strip()
                source = str(decision.get("source") or "").strip()
                reason = str(decision.get("reason") or "").strip()
                if not concept or concept in seen_decisions:
                    errors.append(f"{prefix}.concept must be non-empty and unique")
                    continue
                seen_decisions.add(concept)
                if outcome not in {"required", "excluded"}:
                    errors.append(f"{prefix}.decision must equal required or excluded")
                if source not in {"input_explicit", "category_core", "candidate"}:
                    errors.append(
                        f"{prefix}.source must equal input_explicit, category_core, or candidate"
                    )
                if not reason:
                    errors.append(f"{prefix}.reason must be non-empty")
                if outcome == "required":
                    assessed_required_concepts.add(concept)
            configured_concepts = set(term_specs)
            if assessed_required_concepts != configured_concepts:
                errors.append(
                    "CONFIG professional_term_assessment required concepts must exactly match "
                    f"required_term_coverage keys; assessed={sorted(assessed_required_concepts)}, "
                    f"configured={sorted(configured_concepts)}"
                )
    min_distinct = config.get("min_distinct_counts")
    if min_distinct is None:
        min_distinct = {
            "audience_roles": 3,
            "scenarios": 3,
            "constraints": 2,
        } if expected_total >= 18 else {}
    elif is_current_schema and "geo_intents" in min_distinct:
        errors.append("CONFIG min_distinct_counts.geo_intents is retired in v3")
        min_distinct = {key: value for key, value in min_distinct.items() if key != "geo_intents"}

    if len(questions) != expected_total:
        errors.append(f"COUNT expected {expected_total}, got {len(questions)}")

    ids: list[str] = []
    normalized_questions: list[str] = []
    question_types: Counter = Counter()
    funnel_intents: Counter = Counter()
    diagnostic_intents: Counter = Counter()
    analysis_types: Counter = Counter()
    topic_types: Counter = Counter()
    topic_diagnostic_counts: dict[str, Counter] = {}
    topic_type_by_id: dict[str, str] = {}
    cross: dict[str, Counter] = {"generic": Counter(), "branded": Counter()}
    legacy_geo_intents: Counter = Counter()
    audience_roles: Counter = Counter()
    scenarios: Counter = Counter()
    constraints: Counter = Counter()
    clusters: Counter = Counter()
    opening_words: Counter = Counter()
    promotional_question_ids: list[str] = []
    low_confidence_promotional_ids: list[str] = []
    term_coverage: dict[str, Counter] = {concept: Counter() for concept in term_specs}
    intent_keys: dict[str, list[str]] = {}
    category_visible_ids: list[str] = []
    formal_competitor_question_coverage: dict[str, Counter] = {
        str(profile["name"]): Counter() for profile in formal_competitor_profiles
    }
    branded_comparison_non_solo_count = 0
    target_audience_coverage: dict[str, Counter] = {
        label: Counter() for label in target_audiences.values()
    }
    brand_evaluation_by_topic: Counter = Counter()

    for index, row in enumerate(questions, start=1):
        prefix = f"ROW {index}"
        if not isinstance(row, dict):
            errors.append(f"{prefix}: must be an object")
            continue
        row_required_fields = (
            V4_REQUIRED_FIELDS
            if is_v4_schema
            else (REQUIRED_FIELDS + ("topic_id", "intent_key") if is_current_schema else LEGACY_REQUIRED_FIELDS)
        )
        missing = [field for field in row_required_fields if field not in row]
        missing_translation_field = "zh_translation" in missing
        if missing:
            errors.append(f"{prefix}: missing fields {missing}")
            fatal_missing = [field for field in missing if field != "zh_translation"]
            if fatal_missing:
                continue

        question_id = str(row["question_id"])
        ids.append(question_id)
        question_type = str(row["question_type"])
        funnel = str(row["funnel_intent"])
        diagnostic_intent = str(row.get("diagnostic_intent") or "")
        analysis_type = str(row.get("analysis_type") or "")
        topic_type = str(row.get("topic_type") or "")
        if is_v4_schema:
            if diagnostic_intent not in V4_DIAGNOSTIC_INTENTS:
                errors.append(
                    f"{prefix} {question_id}: invalid v4 diagnostic_intent {diagnostic_intent!r}"
                )
            if analysis_type not in V4_ANALYSIS_TYPES:
                errors.append(
                    f"{prefix} {question_id}: invalid v4 analysis_type {analysis_type!r}"
                )
            if topic_type not in V4_TOPIC_TYPES:
                errors.append(
                    f"{prefix} {question_id}: invalid v4 topic_type {topic_type!r}"
                )
            expected_question_type = (
                "sentiment" if diagnostic_intent in {"competitor", "sentiment"} else "visibility"
            )
            if question_type != expected_question_type:
                errors.append(
                    f"{prefix} {question_id}: diagnostic_intent={diagnostic_intent!r} must map to "
                    f"question_type={expected_question_type!r}"
                )
            expected_analysis = (
                "sentiment" if diagnostic_intent in {"competitor", "sentiment"}
                else "accuracy" if diagnostic_intent == "accuracy"
                else "visibility"
            )
            if analysis_type != expected_analysis:
                errors.append(
                    f"{prefix} {question_id}: diagnostic_intent={diagnostic_intent!r} must map to "
                    f"analysis_type={expected_analysis!r}"
                )
            if diagnostic_intent in V4_FUNNEL_MAPPING and funnel != V4_FUNNEL_MAPPING[diagnostic_intent]:
                errors.append(
                    f"{prefix} {question_id}: diagnostic_intent={diagnostic_intent!r} must map to "
                    f"funnel_intent={V4_FUNNEL_MAPPING[diagnostic_intent]!r}"
                )
            if diagnostic_intent == "discovery" and funnel not in REQUIRED_COMMERCIAL_INTENTS:
                errors.append(
                    f"{prefix} {question_id}: discovery funnel_intent must be one of "
                    f"{sorted(REQUIRED_COMMERCIAL_INTENTS)}"
                )
        if is_current_schema and funnel == "awareness":
            errors.append(f"{prefix} {question_id}: awareness is retired; use recommendation")
        if is_current_schema and funnel not in {"recommendation", "comparison", "decision"}:
            errors.append(f"{prefix} {question_id}: invalid v3 funnel_intent {funnel!r}")
        if is_current_schema:
            topic_id = normalize_label(row.get("topic_id"))
            if topic_id not in configured_topic_ids:
                errors.append(
                    f"{prefix} {question_id}: topic_id {row.get('topic_id')!r} is not in config.topics"
                )
            decision_stage = normalize_label(row.get("decision_stage"))
            if decision_stage not in V3_DECISION_STAGES:
                errors.append(
                    f"{prefix} {question_id}: invalid v3 decision_stage {row.get('decision_stage')!r}; "
                    f"allowed={sorted(V3_DECISION_STAGES)}"
                )
        if is_current_schema:
            retired_fields = [field for field in RETIRED_V3_INTENT_FIELDS if field in row]
            if retired_fields:
                errors.append(
                    f"{prefix} {question_id}: retired v3 intent fields {retired_fields}; express price, risk, "
                    "alternatives, and adoption as conditions under the three commercial intents"
                )
        legacy_geo = str(row.get("geo_intent") or "")
        user_question = str(row["user_question"]).strip()
        expected_brand_evaluation = ""
        if is_current_schema and topic_id in brand_evaluation_specs:
            evaluation_subject, evaluation_dimensions = brand_evaluation_specs[topic_id]
            expected_brand_evaluation = (
                build_v4_sentiment_prompt(
                    category_label,
                    brand_object_type,
                    brand,
                    configured_topics[topic_id],
                )
                if is_v4_schema
                else build_brand_evaluation_prompt(brand, evaluation_subject, evaluation_dimensions)
            )
        is_brand_evaluation = is_current_schema and (
            (
                is_v4_schema
                and diagnostic_intent == "sentiment"
                and normalize_template_text(user_question)
                == normalize_template_text(expected_brand_evaluation)
            )
            or (not is_v4_schema and normalize_template_text(user_question).startswith("evaluate the "))
            or (not is_v4_schema and normalize_template_text(user_question).startswith(
                normalize_template_text(f"How well does {brand} perform as ")
            ))
        )
        zh_translation = row.get("zh_translation")
        normalized_user = normalize(user_question)
        normalized_questions.append(normalized_user)
        question_types[question_type] += 1
        funnel_intents[funnel] += 1
        if is_v4_schema:
            diagnostic_intents[diagnostic_intent] += 1
            analysis_types[analysis_type] += 1
            topic_types[topic_type] += 1
            topic_diagnostic_counts.setdefault(topic_id, Counter())[diagnostic_intent] += 1
            previous_topic_type = topic_type_by_id.setdefault(topic_id, topic_type)
            if previous_topic_type != topic_type:
                errors.append(
                    f"{prefix} {question_id}: topic_id {topic_id!r} mixes topic_type "
                    f"{previous_topic_type!r} and {topic_type!r}"
                )
        if question_type in cross:
            cross[question_type][funnel] += 1
        if legacy_geo:
            legacy_geo_intents[legacy_geo] += 1
        audience_role = str(row["audience_role"])
        audience_roles[audience_role] += 1
        scenarios[normalize_label(row["scenario"])] += 1
        constraints[normalize_label(row["constraint"])] += 1
        clusters[normalize_label(row["cluster"])] += 1
        if normalized_user:
            opening_words[normalized_user.split()[0]] += 1
        if PROMOTIONAL_DRIVER.search(user_question):
            promotional_question_ids.append(question_id)
        elif LOW_CONFIDENCE_PROMOTIONAL.search(user_question):
            low_confidence_promotional_ids.append(question_id)

        matched_formal_profiles = [
            profile
            for profile in formal_competitor_profiles
            if any(
                contains_entity_name(user_question, str(term))
                for term in profile["terms"]
                if str(term).strip()
            )
        ]
        for profile in matched_formal_profiles:
            formal_competitor_question_coverage[str(profile["name"])]["all_questions"] += 1
        if (
            (is_v4_schema and diagnostic_intent == "competitor")
            or (not is_v4_schema and question_type == "branded" and funnel == "comparison")
        ):
            if len(matched_formal_profiles) == 1:
                name = str(matched_formal_profiles[0]["name"])
                formal_competitor_question_coverage[name]["solo_branded_comparison"] += 1
            else:
                branded_comparison_non_solo_count += 1
                for profile in matched_formal_profiles:
                    formal_competitor_question_coverage[str(profile["name"])]["multi_brand_comparison"] += 1

        target_audience_key = normalize_label(audience_role)
        if (
            (is_v4_schema and diagnostic_intent == "discovery")
            or (not is_v4_schema and question_type == "generic")
        ) and target_audience_key in target_audiences:
            target_label = target_audiences[target_audience_key]
            target_audience_coverage[target_label]["generic_total"] += 1
            target_audience_coverage[target_label][f"generic_{funnel}"] += 1

        if not user_question:
            errors.append(f"{prefix} {question_id}: user_question is empty")
        if missing_translation_field:
            pass
        elif not isinstance(zh_translation, str) or not zh_translation.strip():
            errors.append(f"{prefix} {question_id}: zh_translation must be a non-empty string")
        elif not CJK_CHARACTER.search(zh_translation):
            errors.append(f"{prefix} {question_id}: zh_translation must contain Chinese characters")
        if user_question and not (CONVERSATIONAL_START.search(user_question) or is_brand_evaluation):
            errors.append(f"{prefix} {question_id}: user_question is not a recognized natural question/request")
        if BARE_ACTION.search(user_question):
            errors.append(f"{prefix} {question_id}: bare real-world action command")
        if (
            is_current_schema
            and not (
                is_v4_schema
                and diagnostic_intent in {"market_perception", "accuracy", "sentiment", "validation"}
            )
            and NON_COMMERCIAL_GENERIC.search(user_question)
        ):
            errors.append(
                f"{prefix} {question_id}: generic question is explanatory or purchase-process wording; "
                "its answer must name concrete brand/supplier/product candidates"
            )
        if AMBIGUOUS_CATEGORY.search(user_question) and not CATEGORY_CLARIFIER.search(user_question):
            errors.append(f"{prefix} {question_id}: ambiguous brand tracking/monitoring lacks an AI-search qualifier")

        for concept, spec in term_specs.items():
            if any(contains_name(user_question, term) for term in spec["terms"]):
                term_coverage[concept]["total"] += 1
                term_coverage[concept][question_type] += 1
            expanded_form = spec["expanded_form"]
            acronym = spec["acronym"]
            has_expanded = bool(expanded_form) and contains_name(user_question, expanded_form)
            has_acronym = bool(acronym) and contains_name(user_question, acronym)
            if has_expanded:
                term_coverage[concept]["expanded"] += 1
            if has_acronym:
                term_coverage[concept]["acronym"] += 1
            if has_acronym and not has_expanded:
                context_terms = spec["context_terms"]
                if not any(contains_name(user_question, term) for term in context_terms):
                    errors.append(
                        f"{prefix} {question_id}: acronym {acronym} lacks its expanded form "
                        f"or configured category context"
                    )

        if str(row["monitoring_prompt"]).strip() != user_question:
            errors.append(f"{prefix} {question_id}: root monitoring_prompt must equal user_question")
        for other in ("retrieval_rewrite", "evidence_query", "title_seed"):
            if normalize(str(row[other])) == normalized_user:
                errors.append(f"{prefix} {question_id}: user_question duplicates {other}")

        quality = row.get("quality_checks")
        if not isinstance(quality, dict):
            errors.append(f"{prefix} {question_id}: quality_checks must be an object")
        else:
            required_quality_fields = V3_QUALITY_FIELDS if is_current_schema else QUALITY_FIELDS
            failed = [field for field in required_quality_fields if quality.get(field) is not True]
            if failed:
                errors.append(f"{prefix} {question_id}: quality checks not passed {failed}")

        if is_current_schema:
            if is_brand_evaluation:
                if normalize_template_text(user_question) != normalize_template_text(expected_brand_evaluation):
                    errors.append(
                        f"{prefix} {question_id}: invalid brand evaluation template; expected "
                        f"{expected_brand_evaluation!r}"
                    )
                expected_sentiment_type = "sentiment" if is_v4_schema else "branded"
                if question_type != expected_sentiment_type:
                    errors.append(
                        f"{prefix} {question_id}: brand evaluation question must use "
                        f"question_type={expected_sentiment_type!r}"
                    )
                if funnel != BRAND_EVALUATION_INTENT:
                    errors.append(
                        f"{prefix} {question_id}: brand evaluation question must use "
                        f"funnel_intent='{BRAND_EVALUATION_INTENT}'"
                    )
                sentiment_competitors = sorted({
                    name
                    for name in (*competitors, *formal_competitor_terms)
                    if name and contains_entity_name(user_question, name)
                })
                if sentiment_competitors:
                    errors.append(
                        f"{prefix} {question_id}: brand evaluation question names competitors "
                        f"{sentiment_competitors}"
                    )
                if topic_id in configured_topic_ids:
                    brand_evaluation_by_topic[topic_id] += 1
                if is_v4_schema and diagnostic_intent != "sentiment":
                    errors.append(
                        f"{prefix} {question_id}: v4 brand evaluation question must use "
                        "diagnostic_intent='sentiment'"
                    )

            if is_v4_schema and diagnostic_intent == "accuracy":
                for field in ("fact_value", "official_source_url", "fact_checked_at"):
                    if not str(row.get(field) or "").strip():
                        errors.append(
                            f"{prefix} {question_id}: accuracy question requires non-empty {field}"
                        )

            matched_category_groups = [
                group
                for group in ("core_terms", "product_terms")
                if any(contains_name(user_question, term) for term in category_terms[group])
            ]
            placeholder_hits = [
                term
                for term in category_terms["placeholder_blacklist"]
                if contains_name(user_question, term)
            ]
            if placeholder_hits:
                errors.append(
                    f"{prefix} {question_id}: contains category-placeholder terms {placeholder_hits}; "
                    "replace them with the actual product category"
                )
            if matched_category_groups:
                category_visible_ids.append(question_id)
            else:
                errors.append(
                    f"{prefix} {question_id}: category is not visible in the standalone question; "
                    "use a category term, natural variant, or category-specific product term"
                )

            intent_key = normalize_label(row.get("intent_key"))
            if not intent_key:
                errors.append(f"{prefix} {question_id}: intent_key must be a non-empty string")
            else:
                intent_keys.setdefault(intent_key, []).append(question_id)

        configured_names: list[str] = []
        configured_name_keys: set[str] = set()
        for name in (brand, product, *aliases, *competitors, *formal_competitor_terms):
            key = normalize(name)
            if key and key not in configured_name_keys:
                configured_names.append(name)
                configured_name_keys.add(key)
        mentioned_configured = [
            name for name in configured_names if contains_entity_name(user_question, name)
        ]
        if is_v4_schema:
            has_target_brand = bool(brand) and contains_entity_name(user_question, brand)
            mentioned_competitors = sorted({
                name
                for name in (*competitors, *formal_competitor_terms)
                if name and contains_entity_name(user_question, name)
            })
            if diagnostic_intent in {"discovery", "market_perception"} and mentioned_configured:
                errors.append(
                    f"{prefix} {question_id}: {diagnostic_intent} question names configured "
                    f"brand/product/alias/competitor terms {mentioned_configured}"
                )
            if diagnostic_intent in {"competitor", "validation", "accuracy", "sentiment"} and not has_target_brand:
                errors.append(
                    f"{prefix} {question_id}: {diagnostic_intent} question does not name {brand}"
                )
            if diagnostic_intent == "competitor" and len(matched_formal_profiles) != 1:
                errors.append(
                    f"{prefix} {question_id}: competitor question must name exactly one formal competitor"
                )
            if diagnostic_intent in {"validation", "accuracy", "sentiment"} and mentioned_competitors:
                errors.append(
                    f"{prefix} {question_id}: {diagnostic_intent} question names competitors "
                    f"{mentioned_competitors}"
                )
        else:
            if question_type == "generic" and mentioned_configured:
                errors.append(
                    f"{prefix} {question_id}: generic question names configured "
                    f"brand/product/alias/competitor terms {mentioned_configured}"
                )
            if question_type == "branded" and brand and not contains_entity_name(user_question, brand):
                errors.append(f"{prefix} {question_id}: branded question does not name {brand}")

        if not row.get("boundary_question", False):
            drift = [term for term in excluded if contains_name(user_question, term)]
            if drift:
                errors.append(f"{prefix} {question_id}: contains excluded-category terms {drift}")

    duplicate_ids = [key for key, count in Counter(ids).items() if count > 1]
    if duplicate_ids:
        errors.append(f"DUPLICATE question_id values {duplicate_ids}")
    duplicate_questions = [key for key, count in Counter(normalized_questions).items() if key and count > 1]
    if duplicate_questions:
        errors.append(f"DUPLICATE normalized user_question values {duplicate_questions}")
    if is_current_schema:
        for question_ids in intent_keys.values():
            if len(question_ids) > 1:
                errors.append(
                    "DUPLICATE intent conditions: "
                    f"question_ids={question_ids}; changing only English wording does not create a new intent"
                )
        for topic_id, topic_text in configured_topics.items():
            actual = brand_evaluation_by_topic.get(topic_id, 0)
            if actual != 1:
                errors.append(
                    f"COVERAGE brand_evaluation.{topic_id}: expected exactly 1 for topic "
                    f"{topic_text!r}, got {actual}"
                )

    check_quota(errors, "question_type", question_types, quotas.get("question_type", {}))
    if is_v4_schema:
        check_quota(
            errors,
            "diagnostic_intent",
            diagnostic_intents,
            quotas.get("diagnostic_intent", V4_DEFAULT_QUOTAS["diagnostic_intent"]),
        )
        expected_by_analysis = {"visibility": 39, "sentiment": 10, "accuracy": 1}
        check_quota(errors, "analysis_type", analysis_types, expected_by_analysis)
        check_quota(
            errors,
            "funnel_intent",
            funnel_intents,
            quotas.get("funnel_intent", V4_DEFAULT_QUOTAS["funnel_intent"]),
        )
        if topic_types and set(topic_types) - V4_TOPIC_TYPES:
            errors.append(f"QUOTA topic_type: unexpected values {sorted(set(topic_types) - V4_TOPIC_TYPES)}")
        expected_topic_diagnostics = {
            "discovery": 37,
            "competitor": 3,
            "validation": 1,
            "accuracy": 1,
            "sentiment": 7,
            "market_perception": 1,
        }
        for topic_id in configured_topic_ids:
            actual_counts = topic_diagnostic_counts.get(topic_id, Counter())
            for intent, expected in expected_topic_diagnostics.items():
                if actual_counts.get(intent, 0) != expected:
                    errors.append(
                        f"QUOTA topic.{topic_id}.{intent}: expected {expected}, "
                        f"got {actual_counts.get(intent, 0)}"
                    )
    if is_current_schema:
        for intent in sorted(REQUIRED_COMMERCIAL_INTENTS):
            if funnel_intents.get(intent, 0) < 1:
                errors.append(
                    f"COVERAGE funnel_intent.{intent}: expected at least 1, got 0"
                )
    else:
        check_quota(errors, "funnel_intent", funnel_intents, quotas.get("funnel_intent", {}))
        for question_type, expected in quotas.get("cross", {}).items():
            check_quota(errors, f"cross.{question_type}", cross.get(question_type, Counter()), expected)
    branded_comparison_count = cross["branded"].get("comparison", 0)
    if (
        not is_v4_schema
        and len(formal_competitor_profiles) == 3
        and branded_comparison_count >= 3
    ):
        for profile in formal_competitor_profiles:
            name = str(profile["name"])
            solo_count = formal_competitor_question_coverage[name].get("solo_branded_comparison", 0)
            if solo_count < 1:
                errors.append(
                    "COVERAGE formal_competitor."
                    f"{name}.solo_branded_comparison: expected at least 1, got {solo_count}"
                )
        if branded_comparison_count >= 5 and branded_comparison_non_solo_count < 2:
            errors.append(
                "COVERAGE branded_comparison_3_plus_2: expected at least 2 key-factor or "
                f"multi-brand questions, got {branded_comparison_non_solo_count}"
            )
    term_minimum_fields = {
        "min_total": "total",
        **(
            {"min_visibility": "visibility", "min_sentiment": "sentiment"}
            if is_v4_schema
            else {"min_generic": "generic", "min_branded": "branded"}
        ),
        "min_expanded": "expanded",
        "min_acronym": "acronym",
    }
    for concept, spec in term_specs.items():
        for config_field, actual_field in term_minimum_fields.items():
            minimum = spec[config_field]
            actual = term_coverage[concept].get(actual_field, 0)
            if actual < minimum:
                errors.append(
                    f"COVERAGE term.{concept}.{actual_field}: expected at least {minimum}, got {actual}"
                )
    distinct_actual = {
        "audience_roles": len(audience_roles),
        "scenarios": len(scenarios),
        "constraints": len(constraints),
    }
    for dimension, minimum in min_distinct.items():
        if distinct_actual.get(dimension, 0) < minimum:
            errors.append(
                f"COVERAGE distinct.{dimension}: expected at least {minimum}, "
                f"got {distinct_actual.get(dimension, 0)}"
            )

    generic_total = question_types.get("generic", 0)
    validated_total = len(normalized_questions)
    promotional_ratio = len(promotional_question_ids) / validated_total if validated_total else 0.0
    if validated_total >= MIN_BATCH_FOR_STYLE_WARNINGS and promotional_ratio > MAX_PROMOTIONAL_DRIVER_RATIO:
        warnings.append(
            "DIVERSITY WARNING commercial_openers: "
            f"{len(promotional_question_ids)}/{validated_total} questions "
            f"({promotional_ratio:.1%}) use best/top/ranking/review wording; "
            "review intent diversity but do not reject these forms mechanically"
        )

    singleton_cluster_count = sum(1 for count in clusters.values() if count == 1)
    singleton_cluster_ratio = singleton_cluster_count / validated_total if validated_total else 0.0
    singleton_scenario_count = sum(1 for count in scenarios.values() if count == 1)
    singleton_scenario_ratio = singleton_scenario_count / validated_total if validated_total else 0.0
    singleton_constraint_count = sum(1 for count in constraints.values() if count == 1)
    singleton_constraint_ratio = singleton_constraint_count / validated_total if validated_total else 0.0
    common_opener_count = sum(opening_words.get(word, 0) for word in COMMON_QUESTION_OPENERS)
    common_opener_ratio = common_opener_count / validated_total if validated_total else 0.0
    if validated_total >= MIN_BATCH_FOR_STYLE_WARNINGS:
        if singleton_cluster_ratio > WARN_SINGLETON_CLUSTER_RATIO:
            severity = (
                "HIGH_RISK"
                if singleton_cluster_ratio > HIGH_RISK_SINGLETON_CLUSTER_RATIO
                else "WARNING"
            )
            warnings.append(
                f"DIVERSITY {severity} cluster_singleton_ratio: "
                f"{singleton_cluster_count}/{validated_total} questions "
                f"({singleton_cluster_ratio:.1%}) use a cluster that appears only once; "
                f"review clusters for pseudo-diversity (warning threshold {WARN_SINGLETON_CLUSTER_RATIO:.0%})"
            )
        for dimension, count, ratio in (
            ("scenario", singleton_scenario_count, singleton_scenario_ratio),
            ("constraint", singleton_constraint_count, singleton_constraint_ratio),
        ):
            if ratio >= WARN_METADATA_SINGLETON_RATIO:
                warnings.append(
                    f"DIVERSITY WARNING {dimension}_singleton_ratio: {count}/{validated_total} questions "
                    f"({ratio:.1%}) use a {dimension} label that appears only once; "
                    "review metadata granularity"
                )
        if common_opener_ratio > MAX_COMMON_OPENER_RATIO:
            severity = (
                "HIGH_RISK"
                if common_opener_ratio > HIGH_RISK_COMMON_OPENER_RATIO
                else "WARNING"
            )
            warnings.append(
                f"DIVERSITY {severity} common_question_openers: "
                f"{common_opener_count}/{validated_total} questions "
                f"({common_opener_ratio:.1%}) start with How/What/Which; "
                f"review sentence-pattern diversity (warning threshold {MAX_COMMON_OPENER_RATIO:.0%})"
            )
        if opening_words:
            dominant_opener, dominant_count = opening_words.most_common(1)[0]
            dominant_ratio = dominant_count / validated_total
            if dominant_ratio > MAX_SINGLE_OPENER_RATIO:
                warnings.append(
                    f"DIVERSITY WARNING dominant_opener: {dominant_count}/{validated_total} questions "
                    f"({dominant_ratio:.1%}) start with {dominant_opener.title()}"
                )
        low_confidence_ratio = len(low_confidence_promotional_ids) / validated_total
        if low_confidence_ratio > MAX_PROMOTIONAL_DRIVER_RATIO:
            warnings.append(
                "COVERAGE WARNING low_confidence_promotional_terms: "
                f"{len(low_confidence_promotional_ids)}/{validated_total} questions contain "
                "ambiguous most/review uses; inspect context instead of treating them as hard failures"
            )

    summary = {
        "total": len(questions),
        "question_type": dict(question_types),
        "funnel_intent": dict(funnel_intents),
        "diagnostic_intent": dict(diagnostic_intents),
        "analysis_type": dict(analysis_types),
        "topic_type": dict(topic_types),
        "term_coverage": {concept: dict(counts) for concept, counts in term_coverage.items()},
        "category_visible_count": len(category_visible_ids),
        "commercial_intent_review_count": sum(
            1
            for row in questions
            if isinstance(row, dict)
            and isinstance(row.get("quality_checks"), dict)
            and row["quality_checks"].get("commercial_intent") is True
        ),
        "brand_evaluation_by_topic": dict(brand_evaluation_by_topic),
        "distinct": distinct_actual,
        "quality_patterns": {
            "promotional_driver_count": len(promotional_question_ids),
            "promotional_driver_ratio": round(promotional_ratio, 4),
            "singleton_cluster_count": singleton_cluster_count,
            "singleton_cluster_ratio": round(singleton_cluster_ratio, 4),
            "singleton_scenario_count": singleton_scenario_count,
            "singleton_scenario_ratio": round(singleton_scenario_ratio, 4),
            "singleton_constraint_count": singleton_constraint_count,
            "singleton_constraint_ratio": round(singleton_constraint_ratio, 4),
            "opening_words": dict(opening_words),
            "how_what_which_count": common_opener_count,
            "how_what_which_ratio": round(common_opener_ratio, 4),
            "low_confidence_promotional_count": len(low_confidence_promotional_ids),
            "low_confidence_promotional_ratio": round(
                len(low_confidence_promotional_ids) / validated_total if validated_total else 0.0,
                4,
            ),
        },
        "formal_competitor_tiers": dict(formal_competitor_tiers),
        "formal_competitor_question_coverage": {
            name: dict(counts) for name, counts in formal_competitor_question_coverage.items()
        },
        "branded_comparison_non_solo_count": branded_comparison_non_solo_count,
        "target_audience_coverage": {
            audience: {
                **dict(counts),
                "generic_share": round(
                    counts.get("generic_total", 0) / question_types.get("generic", 0)
                    if question_types.get("generic", 0)
                    else 0.0,
                    4,
                ),
            }
            for audience, counts in target_audience_coverage.items()
        },
    }
    if not is_current_schema:
        summary["geo_intent"] = dict(legacy_geo_intents)
    if not schema_version:
        warnings.append(
            "LEGACY schema_version is missing; professional_term_assessment and mandatory "
            "required_term_coverage were not enforced"
        )
    elif is_legacy_v2:
        warnings.append(
            "LEGACY schema_version v2 uses awareness; migrate new banks to v3 "
            "recommendation/comparison/decision"
        )
    if not excluded:
        warnings.append("CONFIG excluded_categories is empty; category-drift checks are limited")
    return errors, warnings, summary


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python3 scripts/validate_question_bank.py <question-bank.json>", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"valid": False, "errors": [str(exc)]}, indent=2))
        return 2
    errors, warnings, summary = validate(data)
    print(json.dumps({"valid": not errors, "errors": errors, "warnings": warnings, "summary": summary}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
