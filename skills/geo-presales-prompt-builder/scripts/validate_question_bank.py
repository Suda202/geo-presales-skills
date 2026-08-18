#!/usr/bin/env python3
"""Deterministic validation for Overseas GEO question-bank JSON files."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path


DEFAULT_QUOTAS = {
    "question_type": {"generic": 40, "branded": 10},
}
REQUIRED_COMMERCIAL_INTENTS = {"recommendation", "comparison", "decision"}
BRAND_SENTIMENT_INTENT = "decision"
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
CURRENT_SCHEMA_VERSION = "overseas-geo-question-bank/v3"
LEGACY_SCHEMA_VERSIONS = {"overseas-geo-question-bank/v2"}
NON_COMMERCIAL_GENERIC = re.compile(
    r"^(?:what\s+is\s+(?!(?:the\s+)?(?:best|top|recommended|right|better|good)\b)|"
    r"how\s+do(?:es)?\b.{0,120}\bwork|what\s+is\s+the\s+difference\s+between|"
    r"what\s+should\s+(?:i|we|buyers|a\s+buyer)\s+(?:look\s+for|consider|evaluate|assess)|"
    r"where\s+to\s+buy|how\s+to\s+buy|where\s+can\s+i\s+buy)\b",
    re.IGNORECASE,
)


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


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


def normalize_label(value: object) -> str:
    return normalize(str(value))


def check_quota(errors: list[str], label: str, actual: Counter, expected: dict) -> None:
    for key, count in expected.items():
        if actual.get(key, 0) != count:
            errors.append(f"QUOTA {label}.{key}: expected {count}, got {actual.get(key, 0)}")
    unexpected = sorted(set(actual) - set(expected))
    if unexpected:
        errors.append(f"QUOTA {label}: unexpected values {unexpected}")


def validate(data: dict) -> tuple[list[str], list[str], dict]:
    errors: list[str] = []
    warnings: list[str] = []
    config = data.get("config") or {}
    schema_version = str(data.get("schema_version") or config.get("schema_version") or "").strip()
    if schema_version and schema_version not in {CURRENT_SCHEMA_VERSION, *LEGACY_SCHEMA_VERSIONS}:
        errors.append(f"SCHEMA unsupported schema_version {schema_version}")
    is_current_schema = schema_version == CURRENT_SCHEMA_VERSION
    is_legacy_v2 = schema_version in LEGACY_SCHEMA_VERSIONS
    requires_term_assessment = is_current_schema or is_legacy_v2
    schema_label = "v3" if is_current_schema else "v2"
    questions = data.get("questions")
    if not isinstance(questions, list):
        return ["SCHEMA questions must be an array"], warnings, {}

    expected_total = config.get("expected_total", 50)
    quotas = config.get("quotas") or DEFAULT_QUOTAS
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
                if not topic_id:
                    errors.append(f"{prefix}.topic_id must be a non-empty string")
                elif topic_id in configured_topic_ids:
                    errors.append(f"{prefix}.topic_id duplicates another topic")
                else:
                    configured_topic_ids.add(topic_id)
                    configured_topics[topic_id] = topic_text
                if not topic_text:
                    errors.append(f"{prefix}.topic must be a non-empty string")
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
        branded_quota = int(((quotas.get("question_type") or {}).get("branded", 0)) or 0)
        if configured_topics and len(configured_topics) > branded_quota:
            errors.append(
                "CONFIG topics cannot exceed the Branded question quota because each Topic "
                "requires one brand sentiment question"
            )
    if is_current_schema and "min_geo_intent_counts" in config:
        errors.append("CONFIG min_geo_intent_counts is retired in v3; do not generate questions to fill angle quotas")
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
            for count_field in ("min_total", "min_generic", "min_branded", "min_expanded", "min_acronym"):
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
    brand_sentiment_by_topic: Counter = Counter()

    for index, row in enumerate(questions, start=1):
        prefix = f"ROW {index}"
        if not isinstance(row, dict):
            errors.append(f"{prefix}: must be an object")
            continue
        row_required_fields = (
            REQUIRED_FIELDS + ("topic_id", "intent_key")
            if is_current_schema
            else LEGACY_REQUIRED_FIELDS
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
        is_brand_sentiment = (
            is_current_schema
            and normalize_template_text(user_question).startswith("evaluate the ")
        )
        zh_translation = row.get("zh_translation")
        normalized_user = normalize(user_question)
        normalized_questions.append(normalized_user)
        question_types[question_type] += 1
        funnel_intents[funnel] += 1
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
        if question_type == "branded" and funnel == "comparison":
            if len(matched_formal_profiles) == 1:
                name = str(matched_formal_profiles[0]["name"])
                formal_competitor_question_coverage[name]["solo_branded_comparison"] += 1
            else:
                branded_comparison_non_solo_count += 1
                for profile in matched_formal_profiles:
                    formal_competitor_question_coverage[str(profile["name"])]["multi_brand_comparison"] += 1

        target_audience_key = normalize_label(audience_role)
        if question_type == "generic" and target_audience_key in target_audiences:
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
        if user_question and not (CONVERSATIONAL_START.search(user_question) or is_brand_sentiment):
            errors.append(f"{prefix} {question_id}: user_question is not a recognized natural question/request")
        if BARE_ACTION.search(user_question):
            errors.append(f"{prefix} {question_id}: bare real-world action command")
        if is_current_schema and NON_COMMERCIAL_GENERIC.search(user_question):
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
            if is_brand_sentiment:
                topic_text = configured_topics.get(topic_id, "")
                expected_sentiment = (
                    f"Evaluate the {category_label} {brand_object_type} {brand} on {topic_text}"
                )
                if normalize_template_text(user_question) != normalize_template_text(expected_sentiment):
                    errors.append(
                        f"{prefix} {question_id}: invalid brand sentiment template; expected "
                        f"{expected_sentiment!r}"
                    )
                if question_type != "branded":
                    errors.append(
                        f"{prefix} {question_id}: brand sentiment question must use question_type='branded'"
                    )
                if funnel != BRAND_SENTIMENT_INTENT:
                    errors.append(
                        f"{prefix} {question_id}: brand sentiment question must use "
                        f"funnel_intent='{BRAND_SENTIMENT_INTENT}'"
                    )
                sentiment_competitors = sorted({
                    name
                    for name in (*competitors, *formal_competitor_terms)
                    if name and contains_entity_name(user_question, name)
                })
                if sentiment_competitors:
                    errors.append(
                        f"{prefix} {question_id}: brand sentiment question names competitors "
                        f"{sentiment_competitors}"
                    )
                if topic_id in configured_topic_ids:
                    brand_sentiment_by_topic[topic_id] += 1

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
            actual = brand_sentiment_by_topic.get(topic_id, 0)
            if actual != 1:
                errors.append(
                    f"COVERAGE brand_sentiment.{topic_id}: expected exactly 1 for topic "
                    f"{topic_text!r}, got {actual}"
                )

    check_quota(errors, "question_type", question_types, quotas.get("question_type", {}))
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
        len(formal_competitor_profiles) == 3
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
        "min_generic": "generic",
        "min_branded": "branded",
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
        "term_coverage": {concept: dict(counts) for concept, counts in term_coverage.items()},
        "category_visible_count": len(category_visible_ids),
        "commercial_intent_review_count": sum(
            1
            for row in questions
            if isinstance(row, dict)
            and isinstance(row.get("quality_checks"), dict)
            and row["quality_checks"].get("commercial_intent") is True
        ),
        "brand_sentiment_by_topic": dict(brand_sentiment_by_topic),
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
