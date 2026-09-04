from __future__ import annotations

from collections import Counter

from .util import ContractError, find_alias_spans, normalize_text, sha256_obj


QUESTION_TYPE_MAP = {
    "generic": "generic",
    "category": "generic",
    "branded": "branded",
    "brand": "branded",
    "brand_related": "branded",
}

INTENT_MAP = {
    "recommendation": "recommendation",
    "推荐": "recommendation",
    "awareness": "recommendation",
    "informational": "recommendation",
    "了解": "recommendation",
    "comparison": "comparison",
    "commercial": "comparison",
    "比较": "comparison",
    "decision": "decision",
    "transactional": "decision",
    "决策": "decision",
}
REQUIRED_COMMERCIAL_INTENTS = {"recommendation", "comparison", "decision"}
DIAGNOSTIC_SCOPES = {
    "discovery": ["visibility", "citation"],
    "competitor": ["comparison"],
    "validation": ["attribute_validation"],
    "accuracy": ["accuracy"],
    "sentiment": ["sentiment"],
    "market_perception": ["market_perception"],
}


def _question_text(raw: dict) -> str:
    for key in ("monitoring_prompt", "user_question", "question_text", "question", "standalone_rewrite"):
        value = str(raw.get(key) or "").strip()
        if value:
            return value
    return ""


def normalize_question_bank(raw: dict | list, config: dict) -> dict:
    source_questions = raw.get("questions") if isinstance(raw, dict) else raw
    if not isinstance(source_questions, list):
        raise ContractError("Question bank must be a list or an object containing questions[]")
    normalized: list[dict] = []
    ids = set()
    all_objects = config["objects"]
    target = next(obj for obj in all_objects if obj["object_id"] == config["target_object_id"])
    competitors = [obj for obj in all_objects if obj["role"] == "competitor"]
    is_v5 = "diagnostic_intent" in config["quotas"]

    for index, item in enumerate(source_questions, 1):
        if not isinstance(item, dict):
            raise ContractError(f"Question at index {index} is not an object")
        question_id = str(item.get("question_id") or item.get("id") or f"q{index:02d}").strip()
        key = question_id.casefold()
        if key in ids:
            raise ContractError(f"Duplicate question_id: {question_id}")
        ids.add(key)
        text = _question_text(item)
        if not text:
            raise ContractError(f"Question {question_id} has no monitoring text")
        diagnostic_intent = str(item.get("diagnostic_intent") or "").strip()
        if is_v5:
            if diagnostic_intent not in DIAGNOSTIC_SCOPES:
                raise ContractError(f"Question {question_id} has invalid diagnostic_intent: {diagnostic_intent!r}")
            if item.get("metric_scopes") != DIAGNOSTIC_SCOPES[diagnostic_intent]:
                raise ContractError(f"Question {question_id} has invalid metric_scopes for {diagnostic_intent}")
            question_type = "generic" if diagnostic_intent in {"discovery", "market_perception"} else "branded"
            intent = {
                "competitor": "comparison",
                "validation": "decision",
                "accuracy": "decision",
                "sentiment": "decision",
                "market_perception": "recommendation",
            }.get(diagnostic_intent, INTENT_MAP.get(str(item.get("funnel_intent") or "recommendation").strip(), "recommendation"))
            claimed_type = str(item.get("question_type") or question_type)
            claimed_intent = str(item.get("funnel_intent") or intent)
        else:
            claimed_type = str(item.get("question_type") or item.get("type") or "").strip()
            question_type = QUESTION_TYPE_MAP.get(claimed_type)
            if not question_type:
                raise ContractError(f"Question {question_id} has invalid question_type: {claimed_type!r}")
            claimed_intent = str(item.get("funnel_intent") or item.get("intent") or item.get("purchase_intent") or "").strip()
            intent = INTENT_MAP.get(claimed_intent)
            if not intent:
                raise ContractError(f"Question {question_id} has invalid funnel intent: {claimed_intent!r}")

        target_hits = find_alias_spans(text, target["aliases"])
        competitor_hits = [
            {"object_id": obj["object_id"], "spans": find_alias_spans(text, obj["aliases"])}
            for obj in competitors
        ]
        competitor_hits = [hit for hit in competitor_hits if hit["spans"]]
        if question_type == "generic" and (target_hits or competitor_hits):
            names = [target["canonical_name"]] if target_hits else []
            names.extend(next(obj["canonical_name"] for obj in competitors if obj["object_id"] == hit["object_id"]) for hit in competitor_hits)
            raise ContractError(f"Generic question {question_id} contains monitored object aliases: {', '.join(names)}")
        if question_type == "branded" and not target_hits:
            raise ContractError(f"Branded question {question_id} does not mention the target object")
        if is_v5 and diagnostic_intent == "competitor" and len(competitor_hits) != 1:
            raise ContractError(f"Competitor question {question_id} must mention exactly one formal competitor")
        if is_v5 and diagnostic_intent in {"validation", "accuracy", "sentiment"} and competitor_hits:
            raise ContractError(f"Question {question_id} must not mention a formal competitor")
        if not any(char.isalpha() and ord(char) < 128 for char in text):
            raise ContractError(f"Question {question_id} is not an English question")

        normalized.append({
            "question_id": question_id,
            "generation_sequence": int(item.get("generation_sequence") or item.get("index") or index),
            "question_text": text,
            "question_zh": str(item.get("question_zh") or "").strip() or None,
            "question_type": question_type,
            "funnel_intent": intent,
            "diagnostic_intent": diagnostic_intent or None,
            "analysis_type": item.get("analysis_type"),
            "metric_scopes": item.get("metric_scopes") if is_v5 else None,
            "topic_id": item.get("topic_id"),
            "topic_type": item.get("topic_type"),
            "attribute_ids": item.get("attribute_ids") or [],
            "decision_stage": item.get("decision_stage"),
            "cluster": item.get("cluster"),
            "audience_hint": item.get("audience_role") or item.get("persona_name"),
            "scenario": item.get("scenario") or item.get("scene_name"),
            "constraint": item.get("constraint"),
            "evidence_need": item.get("evidence_need"),
            "source": {
                "claimed_question_type": claimed_type,
                "claimed_intent": claimed_intent,
            },
        })

    quotas = config["quotas"]
    if len(normalized) != quotas["total"]:
        raise ContractError(f"Question bank has {len(normalized)} questions; expected {quotas['total']}")
    if is_v5:
        diagnostic_counts = Counter(item["diagnostic_intent"] for item in normalized)
        if dict(diagnostic_counts) != quotas["diagnostic_intent"]:
            raise ContractError(f"Diagnostic-intent quota mismatch: got {dict(diagnostic_counts)}, expected {quotas['diagnostic_intent']}")
        topic_counts = Counter(item["topic_id"] for item in normalized)
        if len(topic_counts) != 3 or set(topic_counts.values()) != {17}:
            raise ContractError(f"Each of three topics must contain 17 questions; got {dict(topic_counts)}")
        for topic_id in topic_counts:
            counts = Counter(item["diagnostic_intent"] for item in normalized if item["topic_id"] == topic_id)
            if dict(counts) != quotas["per_topic"]:
                raise ContractError(f"主题 {topic_id} diagnostic quota mismatch: got {dict(counts)}")
    else:
        type_counts = Counter(item["question_type"] for item in normalized)
        intent_counts = Counter(item["funnel_intent"] for item in normalized)
        if dict(type_counts) != {key: value for key, value in quotas["question_type"].items() if value}:
            raise ContractError(f"Question-type quota mismatch: got {dict(type_counts)}, expected {quotas['question_type']}")
        missing_intents = sorted(REQUIRED_COMMERCIAL_INTENTS - set(intent_counts))
        if missing_intents:
            raise ContractError(
                "Question bank must contain recommendation, comparison, and decision intents; "
                f"missing {missing_intents}"
            )

    normalized.sort(key=lambda item: (item["generation_sequence"], item["question_id"].casefold()))
    return {
        "schema_version": "geo-presales-question-bank/v1",
        "run_id": config["run_id"],
        "quotas": quotas,
        "questions": normalized,
        "question_bank_hash": sha256_obj(normalized),
        "warnings": [
            {
                "code": "MISSING_CHINESE_TRANSLATION",
                "question_id": item["question_id"],
                "message": "缺少 question_zh 中文释义；不影响采集和指标计算",
            }
            for item in normalized if not item["question_zh"]
        ] + [
            {
                "code": "LEGACY_AWARENESS_MIGRATED",
                "question_id": item["question_id"],
                "message": "历史 awareness/了解标签已迁移为 recommendation/推荐；请确保题目本身具有商业推荐意图",
            }
            for item in normalized
            if item["source"]["claimed_intent"] in {"awareness", "informational", "了解"}
        ],
    }
