#!/usr/bin/env python3
"""Validate an after-sales Prompt set without presales quota assumptions.

Historical v8 banks omit ``config.generation_stage`` and retain their legacy
shape checks. New Discovery/Diagnostic artifacts opt into stage-aware checks.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path


INTENTS = {
    "Discovery",
    "Competitor",
    "Evaluation",
    "Verification",
    "Category Awareness",
    "Accuracy",
}
STAGES = {"discovery", "diagnostic"}
LIFECYCLE_STATES = {
    "hypothesis",
    "customer_confirmed",
    "locked",
    "formal_baseline",
    "active",
}


def fail(message: str, errors: list[str]) -> None:
    errors.append(message)


def normalized_intent(row: dict, errors: list[str]) -> str:
    """Normalize explicit intent and inherited presales Intent tags."""
    explicit = str(row.get("intent") or "").strip()
    intent_key = str(row.get("intent_key") or "").strip()
    tag_intents = {
        str(tag).split(":", 1)[1].strip()
        for tag in row.get("tags") or []
        if str(tag).strip().startswith("Intent:")
    }
    if len(tag_intents) > 1:
        fail(f"{row.get('question_id')}: conflicting Intent tags", errors)
    tag_intent = next(iter(tag_intents), "")
    if explicit and explicit not in INTENTS:
        fail(f"{row.get('question_id')}: unsupported intent {explicit!r}", errors)
    if explicit and tag_intent and explicit != tag_intent:
        fail(f"{row.get('question_id')}: explicit intent conflicts with Intent tag", errors)
    if explicit:
        return explicit
    if tag_intent:
        if intent_key in INTENTS and intent_key != tag_intent:
            fail(f"{row.get('question_id')}: intent_key conflicts with Intent tag", errors)
        return tag_intent
    if intent_key in INTENTS:
        return intent_key
    return ""


def main() -> int:
    if len(sys.argv) not in {2, 3}:
        print("usage: validate_after_sales_set.py BANK.json [MONITORING.csv]")
        return 2

    json_path = Path(sys.argv[1])
    data = json.loads(json_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    config = data.get("config") or {}
    topics = config.get("topics") or []
    questions = data.get("questions") or []
    stage = config.get("generation_stage")
    legacy_full_bank = stage is None
    if stage is not None and (not isinstance(stage, str) or stage not in STAGES):
        fail(f"config.generation_stage must be one of {sorted(STAGES)}", errors)

    mode = data.get("mode")
    if mode != "after-sales-strategic-topics":
        fail("root mode must be after-sales-strategic-topics", errors)
    if not topics:
        fail("config.topics must contain at least one Topic", errors)
    if len(questions) != config.get("expected_total"):
        fail("config.expected_total must equal question count", errors)

    topic_ids = {topic.get("topic_id") for topic in topics if topic.get("topic_id")}
    if len(topic_ids) != len(topics):
        fail("Topic IDs must be unique", errors)
    if any(not str(topic.get("topic") or "").strip() for topic in topics):
        fail("Topic names must be non-empty", errors)
    if legacy_full_bank and any(len(str(topic.get("topic") or "")) > 48 for topic in topics):
        fail("Topic names are too long", errors)

    role_counts: Counter[str] = Counter()
    topic_counts: Counter[str] = Counter()
    normalized_queries: set[str] = set()
    question_ids: set[str] = set()
    for row in questions:
        question_id = str(row.get("question_id") or "").strip()
        if not question_id:
            fail("question_id is required", errors)
        elif question_id in question_ids:
            fail(f"{question_id}: duplicate question_id", errors)
        question_ids.add(question_id)
        topic_id = row.get("topic_id")
        if topic_id not in topic_ids:
            fail(f"{question_id}: unknown topic_id", errors)
        topic_counts[topic_id] += 1
        intent = normalized_intent(row, errors)
        role_counts[intent] += 1
        if not intent:
            fail(f"{question_id}: missing intent", errors)
        elif intent not in INTENTS:
            fail(f"{question_id}: unsupported intent {intent!r}", errors)
        if not str(row.get("region") or "").strip():
            fail(f"{question_id}: missing region", errors)
        user_question = str(row.get("user_question") or "").strip()
        if not user_question:
            fail(f"{question_id}: user_question is required", errors)
        if not str(row.get("zh_translation") or "").strip():
            fail(f"{question_id}: zh_translation is required", errors)
        if "monitoring_prompt" not in row:
            fail(f"{question_id}: monitoring_prompt is required", errors)
        elif row.get("monitoring_prompt") != row.get("user_question"):
            fail(f"{question_id}: monitoring_prompt mismatch", errors)
        if not row.get("tags"):
            fail(f"{question_id}: tags must be non-empty", errors)
        query_key = " ".join(user_question.casefold().split())
        if query_key in normalized_queries:
            fail(f"{row.get('question_id')}: duplicate query", errors)
        normalized_queries.add(query_key)

    if stage == "discovery" and any(
        intent != "Discovery" for intent in role_counts if intent
    ):
        fail("discovery stage must contain Discovery Prompts only", errors)
    lifecycle = config.get("lifecycle_status")
    if lifecycle is not None and lifecycle not in LIFECYCLE_STATES:
        fail(f"config.lifecycle_status must be one of {sorted(LIFECYCLE_STATES)}", errors)

    # Unstaged historical v8 remains compatible with the old complete-bank
    # validator. New staged artifacts do not inherit its fixed quotas.
    if legacy_full_bank:
        if not 3 <= len(topics) <= 10:
            fail(f"legacy first-stage Topic count must be 3-10, got {len(topics)}", errors)
        if any(count < 5 or count > 15 for count in topic_counts.values()):
            fail(f"legacy Topic counts must be 5-15: {dict(topic_counts)}", errors)
        if role_counts.get("Competitor", 0) > 0 and role_counts["Competitor"] != 1:
            fail("legacy starter set expects one Competitor Prompt", errors)
        if role_counts.get("Category Awareness", 0) > 1:
            fail("legacy Category Awareness must not be duplicated by default", errors)
    elif lifecycle in {"customer_confirmed", "locked", "formal_baseline", "active"}:
        short_topics = {
            topic_id: count
            for topic_id, count in topic_counts.items()
            if count < 5
        }
        missing_topics = topic_ids - topic_counts.keys()
        if missing_topics:
            short_topics.update({topic_id: 0 for topic_id in missing_topics})
        if short_topics:
            fail(
                "formal staged set requires at least 5 Prompts per Topic; "
                f"short Topics need merge, Tag treatment, or evidence-gap report: {short_topics}",
                errors,
            )

    evidence_status = config.get("evidence_status")
    if evidence_status in {"hypothesis", "after_sales_signal"} and lifecycle in {
        "locked",
        "formal_baseline",
        "active",
    }:
        fail("hypothesis or after_sales_signal evidence cannot be marked formal-ready", errors)

    confirmation = config.get("customer_confirmation") or {}
    if lifecycle in {"customer_confirmed", "locked", "formal_baseline", "active"}:
        if confirmation.get("status") not in {"confirmed", "locked"}:
            fail("customer confirmation is required before formal-ready lifecycle states", errors)

    prompt_version = config.get("prompt_version")
    if lifecycle in {"locked", "formal_baseline", "active"} and not str(prompt_version or "").strip():
        fail("prompt_version is required before formal baseline", errors)

    baseline = config.get("baseline") or {}
    formal_collection = baseline.get("status") in {"formal", "active"}
    if formal_collection and lifecycle not in {"locked", "formal_baseline", "active"}:
        fail("formal baseline metadata requires a locked or formal lifecycle", errors)
    if formal_collection and evidence_status in {"hypothesis", "after_sales_signal"}:
        fail("formal baseline metadata requires confirmed evidence", errors)
    if formal_collection and (confirmation.get("status") not in {"confirmed", "locked"}):
        fail("formal baseline metadata requires customer confirmation", errors)
    if formal_collection and not str(prompt_version or "").strip():
        fail("formal baseline metadata requires prompt_version", errors)
    if lifecycle == "formal_baseline" and baseline.get("status") not in {"formal", "active"}:
        fail("formal_baseline lifecycle requires baseline.status formal or active", errors)
    if formal_collection:
        if baseline.get("window_days") not in {7, 14}:
            fail("formal baseline window_days must be 7 or diagnosed 14", errors)
        if baseline.get("calendar_days") is not True:
            fail("formal baseline must use consecutive calendar days", errors)
        if baseline.get("window_days") == 14 and not str(
            baseline.get("anomaly_diagnosis") or ""
        ).strip():
            fail("14-day baseline requires anomaly_diagnosis", errors)
        if not str(baseline.get("conditions_key") or "").strip():
            fail("formal baseline requires conditions_key", errors)
        if baseline.get("valid_samples_only") is not True:
            fail("formal baseline must compare valid samples only", errors)
        if baseline.get("failures_as_zero") is True:
            fail("collection failures must not be counted as zero", errors)

    collection = config.get("collection_config") or {}
    if baseline.get("status") in {"formal", "active"}:
        for field in ("market", "language"):
            if not str(collection.get(field) or "").strip():
                fail(f"formal baseline requires collection_config.{field}", errors)
        if not collection.get("platforms"):
            fail("formal baseline requires collection_config.platforms", errors)

    if len(sys.argv) == 3:
        csv_path = Path(sys.argv[2])
        with csv_path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        expected = {"query", "question_zh", "topic", "region", "intent", "tags", "cadence"}
        if rows and set(rows[0]) != expected:
            fail(f"monitoring CSV headers must equal {sorted(expected)}", errors)
        if len(rows) != len(questions):
            fail("monitoring CSV row count must equal JSON question count", errors)
        if any(len(str(row.get("tags") or "")) >= 200 for row in rows):
            fail("monitoring CSV tags must be shorter than 200 characters", errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print(
        json.dumps(
            {
                "topics": len(topics),
                "prompts": len(questions),
                "prompts_per_topic": dict(topic_counts),
                "intents": dict(role_counts),
                "generation_stage": stage or "legacy_full_bank",
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
