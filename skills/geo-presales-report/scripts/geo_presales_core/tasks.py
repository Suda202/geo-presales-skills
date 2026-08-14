from __future__ import annotations

import re
from pathlib import Path

from . import TASK_PROTOCOL_VERSION
from .deterministic import SOURCE_TYPES
from .store import record_event, save_manifest
from .util import ContractError, get_path, now_iso, read_json, sha256_file, sha256_obj, stable_id, write_json


ALLOWED_RESULT_STATUS = {"completed", "partial", "cannot_complete"}
ALLOWED_SENTIMENT = {"positive", "neutral", "negative"}
ALLOWED_SOURCE_TYPES = set(SOURCE_TYPES)


def _resource(root: Path, relative_path: str) -> dict:
    path = root / relative_path
    return {"path": relative_path, "sha256": sha256_file(path)}


def _task_id(kind: str, mode: str, task_input: dict, attempt: int) -> str:
    return stable_id(f"T-{kind.replace('_', '-')}", {"kind": kind, "mode": mode, "input": task_input, "attempt": attempt})


def create_task(
    root: Path,
    manifest: dict,
    *,
    kind: str,
    task_input: dict,
    resources: dict | None = None,
    blocking: bool,
    mode: str = "initial",
    attempt: int = 1,
    depends_on: list[str] | None = None,
    review: dict | None = None,
) -> dict:
    task_id = _task_id(kind, mode, task_input, attempt)
    if task_id in manifest.get("tasks", {}):
        return read_json(root / manifest["tasks"][task_id]["path"])
    task = {
        "protocol_version": TASK_PROTOCOL_VERSION,
        "run_id": manifest["run_id"],
        "task_id": task_id,
        "kind": kind,
        "mode": mode,
        "attempt": attempt,
        "blocking": blocking,
        "depends_on": depends_on or [],
        "contract": {
            "name": kind,
            "version": "1.0",
            "reference": "references/ai-task-contracts.md",
        },
        "resources": resources or {},
        "input": task_input,
        "review": review,
        "created_at": now_iso(),
    }
    task["task_digest"] = sha256_obj(task)
    relative = f"tasks/{task_id}.json"
    write_json(root / relative, task)
    manifest.setdefault("tasks", {})[task_id] = {
        "kind": kind,
        "mode": mode,
        "attempt": attempt,
        "blocking": blocking,
        "status": "pending",
        "path": relative,
        "result_path": None,
        "depends_on": depends_on or [],
    }
    record_event(manifest, "task_created", task_id=task_id, kind=kind, mode=mode)
    save_manifest(root, manifest)
    return task


def create_prepare_tasks(root: Path, manifest: dict, config: dict, answers_doc: dict) -> list[dict]:
    sentiment_items = {}
    resources = {}
    target_id = config["target_object_id"]
    for answer in answers_doc["answers"]:
        if not answer["selected_for_report"] or answer["validity"] != "valid":
            continue
        target = next(item for item in answer["objects"] if item["object_id"] == target_id)
        if not target["mentioned"]:
            continue
        sentiment_items[answer["answer_id"]] = {
            "query": answer["question_text"],
            "answer_ref": f"answer:{answer['answer_id']}",
            "target": {
                "canonical_name": target["canonical_name"],
                "matched_aliases": target["matched_aliases"],
            },
            "language": "en-US",
        }
        resources[f"answer:{answer['answer_id']}"] = _resource(root, answer["evidence_ref"])

    created = []
    batch_size = 10
    item_pairs = list(sentiment_items.items())
    for offset in range(0, len(item_pairs), batch_size):
        chunk = dict(item_pairs[offset:offset + batch_size])
        chunk_resources = {f"answer:{key}": resources[f"answer:{key}"] for key in chunk}
        created.append(create_task(
            root,
            manifest,
            kind="sentiment_batch",
            task_input={
                "items": chunk,
                "confidence_threshold": config["sentiment_confidence_threshold"],
                "instruction": "只判断监测对象的情绪。禁止推断顺序、提及、竞品、来源、翻译、指标或报告文案。",
            },
            resources=chunk_resources,
            blocking=True,
        ))

    unknown = answers_doc.get("unknown_source_items") or {}
    if unknown:
        created.append(create_task(
            root,
            manifest,
            kind="source_classification_batch",
            task_input={
                "items": unknown,
                "allowed_source_types": list(SOURCE_TYPES),
                "confidence_threshold": 0.80,
                "instruction": "只分类未知 host。禁止分配品牌官网或竞品官网类型，官网域名由程序规则处理。",
            },
            blocking=False,
        ))
    return created


def pending_tasks(root: Path, manifest: dict, ready_only: bool = True) -> list[dict]:
    accepted = {task_id for task_id, meta in manifest.get("tasks", {}).items() if meta["status"] in {"accepted", "accepted_with_review", "unresolved", "degraded"}}
    result = []
    for task_id, meta in manifest.get("tasks", {}).items():
        if meta["status"] != "pending":
            continue
        if ready_only and any(dep not in accepted for dep in meta.get("depends_on") or []):
            continue
        result.append(read_json(root / meta["path"]))
    result.sort(key=lambda item: (not item["blocking"], item["created_at"], item["task_id"]))
    return result


def _validate_envelope(task: dict, result: dict) -> dict:
    if result.get("protocol_version") != TASK_PROTOCOL_VERSION:
        raise ContractError("Result protocol_version mismatch")
    for key in ("run_id", "task_id", "kind", "task_digest"):
        if result.get(key) != task.get(key):
            raise ContractError(f"Result {key} does not match task")
    if result.get("status") not in ALLOWED_RESULT_STATUS:
        raise ContractError(f"Invalid result status: {result.get('status')!r}")
    if result["status"] == "cannot_complete":
        return {}
    output = result.get("output")
    if not isinstance(output, dict):
        raise ContractError("Completed/partial result must contain output object")
    return output


def _validate_resources(root: Path, task: dict) -> None:
    for resource_id, resource in (task.get("resources") or {}).items():
        path = root / resource["path"]
        if not path.exists():
            raise ContractError(f"Task resource is missing: {resource_id}")
        if sha256_file(path) != resource.get("sha256"):
            raise ContractError(f"Task resource changed after emission: {resource_id}")


def _answer_map(answers_doc: dict) -> dict[str, dict]:
    return {item["answer_id"]: item for item in answers_doc["answers"]}


def _sentiment_label(score: float) -> str:
    if score > 0.1:
        return "positive"
    if score < -0.1:
        return "negative"
    return "neutral"


def _validate_sentiment(task: dict, output: dict, answers_doc: dict) -> tuple[dict, list[str]]:
    items = output.get("items")
    expected = task["input"]["items"]
    if not isinstance(items, dict) or set(items) != set(expected):
        raise ContractError("Sentiment result items must exactly match task item IDs")
    answers = _answer_map(answers_doc)
    validated = {}
    low_confidence = []
    for answer_id, item in items.items():
        if not isinstance(item, dict):
            raise ContractError(f"Sentiment item {answer_id} is not an object")
        label = item.get("label") or ((item.get("sentiment") or {}).get("label") if isinstance(item.get("sentiment"), dict) else None)
        score = item.get("score")
        if score is None and isinstance(item.get("sentiment"), dict):
            score = item["sentiment"].get("score")
        try:
            score = float(score)
            confidence = float(item.get("confidence"))
        except (TypeError, ValueError):
            raise ContractError(f"Sentiment item {answer_id} has invalid score/confidence")
        if label not in ALLOWED_SENTIMENT or not -1 <= score <= 1 or not 0 <= confidence <= 1:
            raise ContractError(f"Sentiment item {answer_id} has out-of-range values")
        if _sentiment_label(score) != label:
            raise ContractError(f"Sentiment label/score mismatch for {answer_id}")
        evidence_raw = item.get("evidence") or item.get("quotes") or []
        if not isinstance(evidence_raw, list) or not evidence_raw:
            raise ContractError(f"Sentiment item {answer_id} must contain evidence quotes")
        quotes = []
        answer_text = answers[answer_id]["answer_text"] or ""
        for evidence in evidence_raw:
            quote = evidence.get("quote") if isinstance(evidence, dict) else evidence
            quote = str(quote or "").strip()
            if not quote or quote not in answer_text:
                raise ContractError(f"Sentiment evidence for {answer_id} is not an exact answer substring")
            quotes.append({"quote": quote, "verified": True})
        validated[answer_id] = {
            "label": label,
            "score": score,
            "confidence": confidence,
            "evidence": quotes,
            "flags": [str(flag) for flag in item.get("flags") or []],
        }
        if confidence < float(task["input"]["confidence_threshold"]):
            low_confidence.append(answer_id)
    return validated, low_confidence


def _apply_sentiment(answers_doc: dict, validated: dict, status: str = "accepted") -> None:
    answers = _answer_map(answers_doc)
    for answer_id, result in validated.items():
        target = next(item for item in answers[answer_id]["objects"] if item["role"] == "target")
        target.update({
            "sentiment": result["label"],
            "sentiment_score": result["score"],
            "sentiment_confidence": result["confidence"],
            "sentiment_evidence": result["evidence"],
            "sentiment_status": status,
        })


def _validate_source(output: dict, task: dict) -> dict:
    items = output.get("items")
    expected = task["input"]["items"]
    if not isinstance(items, dict) or set(items) != set(expected):
        raise ContractError("Source result items must exactly match task item IDs")
    validated = {}
    for item_id, item in items.items():
        if not isinstance(item, dict):
            raise ContractError(f"Source item {item_id} is not an object")
        source_type = item.get("source_type")
        if source_type not in ALLOWED_SOURCE_TYPES - {"brand_official", "competitor_official"}:
            raise ContractError(f"Source item {item_id} has invalid source_type")
        try:
            confidence = float(item.get("confidence"))
        except (TypeError, ValueError):
            raise ContractError(f"Source item {item_id} has invalid confidence")
        if not 0 <= confidence <= 1:
            raise ContractError(f"Source item {item_id} confidence must be 0..1")
        validated[item_id] = {"source_type": source_type, "confidence": confidence}
    return validated


def _apply_source(answers_doc: dict, task: dict, validated: dict) -> None:
    by_citation = {}
    for item_id, source in task["input"]["items"].items():
        decision = validated[item_id]
        source_type = decision["source_type"] if decision["confidence"] >= task["input"]["confidence_threshold"] else "other"
        for citation_id in source.get("citation_ids") or []:
            by_citation[citation_id] = (source_type, decision["confidence"])
    for answer in answers_doc["answers"]:
        for citation in answer["citations"]:
            if citation["raw_citation_id"] in by_citation and citation["classification_source"] == "default_other":
                source_type, confidence = by_citation[citation["raw_citation_id"]]
                citation.update({
                    "source_type": source_type,
                    "source_type_name": SOURCE_TYPES[source_type],
                    "classification_source": "model_fallback" if source_type != "other" else "default_other",
                    "classification_confidence": confidence,
                })


def _validate_themes(output: dict, answers_doc: dict) -> dict:
    valid_evidence = {}
    for answer in answers_doc["answers"]:
        target = next(item for item in answer["objects"] if item["role"] == "target")
        for index, evidence in enumerate(target.get("sentiment_evidence") or [], 1):
            evidence_id = f"E-{answer['answer_id']}-{index:02d}"
            valid_evidence[evidence_id] = {"answer_id": answer["answer_id"], "label": target.get("sentiment")}
    result = {"positive": [], "risk": []}
    for polarity in result:
        rows = output.get(polarity) or []
        if not isinstance(rows, list):
            raise ContractError(f"Theme output {polarity} must be a list")
        for row in rows:
            if not isinstance(row, dict):
                raise ContractError("Theme row must be an object")
            evidence_ids = row.get("evidence_ids") or []
            if not evidence_ids or any(item not in valid_evidence for item in evidence_ids):
                raise ContractError("Theme evidence_ids must reference verified sentiment evidence")
            answer_ids = sorted({valid_evidence[item]["answer_id"] for item in evidence_ids})
            if polarity == "positive" and any(valid_evidence[item]["label"] != "positive" for item in evidence_ids):
                raise ContractError("Positive theme references non-positive evidence")
            if polarity == "risk" and any(valid_evidence[item]["label"] not in {"negative", "neutral"} for item in evidence_ids):
                raise ContractError("Risk theme references unsupported evidence polarity")
            result[polarity].append({
                "label": str(row.get("label") or "").strip(),
                "summary": str(row.get("summary") or row.get("explanation") or "").strip(),
                "evidence_ids": evidence_ids,
                "supporting_answer_ids": answer_ids,
                "support_count": len(answer_ids),
                "confidence": float(row.get("confidence", 0)),
            })
            if not result[polarity][-1]["label"] or not result[polarity][-1]["summary"]:
                raise ContractError("Theme label and summary are required")
    return result


FACT_TOKEN_RE = re.compile(r"\{\{fact:([a-zA-Z0-9_.-]+)\}\}")


def _validate_claim(text_template: str, refs: list[str], facts: dict) -> None:
    tokens = FACT_TOKEN_RE.findall(text_template)
    normalized_refs = [ref.removeprefix("fact:") for ref in refs]
    if sorted(set(tokens)) != sorted(set(normalized_refs)):
        raise ContractError("Claim refs must exactly match fact tokens")
    for dotted in tokens:
        try:
            get_path(facts, dotted)
        except KeyError:
            raise ContractError(f"Claim references unknown fact: {dotted}")
    without_tokens = FACT_TOKEN_RE.sub("", text_template)
    if re.search(r"\d", without_tokens):
        raise ContractError("Numeric claims must use {{fact:...}} tokens")


def _validate_report_module(output: dict, task: dict, root: Path) -> dict:
    module_id = task["input"]["module_id"]
    if output.get("module_id") != module_id:
        raise ContractError("Report module_id mismatch")
    facts = read_json(root / task["input"]["fact_pack_ref"])
    points = output.get("points") or []
    if not isinstance(points, list) or not 1 <= len(points) <= 5:
        raise ContractError("Report module points must contain 1 to 5 claims")
    for point in points:
        if not isinstance(point, dict):
            raise ContractError("Report module point must be an object")
        _validate_claim(str(point.get("text_template") or ""), point.get("refs") or [], facts)
    conclusion = output.get("conclusion") or {}
    if conclusion:
        _validate_claim(str(conclusion.get("text_template") or ""), conclusion.get("refs") or [], facts)
    return {
        "module_id": module_id,
        "title": str(output.get("title") or "").strip(),
        "points": points,
        "conclusion": conclusion or None,
    }


def _validate_actions(output: dict, task: dict, facts: dict) -> dict:
    directions = {item["direction_id"]: item for item in task["input"]["directions"]}
    actions = output.get("actions") or []
    if not isinstance(actions, list) or set(item.get("direction_id") for item in actions) != set(directions):
        raise ContractError("Action result must contain exactly the provided direction IDs")
    for action in actions:
        if action.get("source_module") != directions[action["direction_id"]]["source_module"]:
            raise ContractError("Action source_module mismatch")
        refs = action.get("refs") or []
        templates = [str(action.get(key) or "") for key in ("evidence_template", "expected_impact_template")]
        tokens = []
        for template in templates:
            tokens.extend(FACT_TOKEN_RE.findall(template))
            if re.search(r"\d", FACT_TOKEN_RE.sub("", template)):
                raise ContractError("Numeric action claims must use {{fact:...}} tokens")
        normalized_refs = [ref.removeprefix("fact:") for ref in refs]
        if sorted(set(tokens)) != sorted(set(normalized_refs)):
            raise ContractError("Action refs must exactly match fact tokens across evidence and impact templates")
        for dotted in tokens:
            try:
                get_path(facts, dotted)
            except KeyError:
                raise ContractError(f"Action references unknown fact: {dotted}")
        if re.search(r"\d", str(action.get("action") or "")):
            raise ContractError("Action prose must not invent numeric commitments")
    summary = output.get("summary") or None
    if summary:
        _validate_claim(str(summary.get("text_template") or ""), summary.get("refs") or [], facts)
    return {"summary": summary, "actions": actions}


def submit_task(root: Path, manifest: dict, task_id: str, result_path: str | Path) -> dict:
    meta = manifest.get("tasks", {}).get(task_id)
    if not meta:
        raise ContractError(f"Unknown task_id: {task_id}")
    task = read_json(root / meta["path"])
    result = read_json(result_path)
    _validate_resources(root, task)
    output = _validate_envelope(task, result)
    answers_path = root / "canonical/answers.json"
    answers_doc = read_json(answers_path) if answers_path.exists() else None
    decision = "accepted"
    validation_codes = []

    if result["status"] == "cannot_complete":
        if task["blocking"]:
            raise ContractError("Blocking task cannot be submitted as cannot_complete")
        decision = "degraded"
        accepted_output = None
    elif task["kind"] == "sentiment_batch":
        accepted_output, low_confidence = _validate_sentiment(task, output, answers_doc)
        high = {key: value for key, value in accepted_output.items() if key not in low_confidence}
        _apply_sentiment(answers_doc, high)
        if low_confidence and task["attempt"] < 2:
            review_input = dict(task["input"])
            review_input["items"] = {key: task["input"]["items"][key] for key in low_confidence}
            review_resources = {f"answer:{key}": task["resources"][f"answer:{key}"] for key in low_confidence}
            review_task = create_task(
                root,
                manifest,
                kind="sentiment_batch",
                task_input=review_input,
                resources=review_resources,
                blocking=True,
                mode="review",
                attempt=task["attempt"] + 1,
                depends_on=[task_id],
                review={"parent_task_id": task_id, "item_ids": low_confidence, "reason_codes": ["LOW_CONFIDENCE"]},
            )
            decision = "accepted_with_review"
            validation_codes.append("LOW_CONFIDENCE_REVIEW_CREATED")
        elif low_confidence:
            unresolved = {key: accepted_output[key] for key in low_confidence}
            _apply_sentiment(answers_doc, unresolved, status="unresolved")
            decision = "unresolved"
            validation_codes.append("LOW_CONFIDENCE_AFTER_REVIEW")
        else:
            _apply_sentiment(answers_doc, accepted_output)
        answers_doc["answers_hash"] = sha256_obj(answers_doc["answers"])
        write_json(answers_path, answers_doc)
    elif task["kind"] == "source_classification_batch":
        accepted_output = _validate_source(output, task)
        _apply_source(answers_doc, task, accepted_output)
        answers_doc["answers_hash"] = sha256_obj(answers_doc["answers"])
        write_json(answers_path, answers_doc)
    elif task["kind"] == "brand_expression_themes":
        accepted_output = _validate_themes(output, answers_doc)
        write_json(root / "artifacts/brand-expression-themes.json", accepted_output)
    elif task["kind"] == "report_module":
        accepted_output = _validate_report_module(output, task, root)
        write_json(root / f"artifacts/{accepted_output['module_id']}.json", accepted_output)
    elif task["kind"] == "next_actions":
        facts = read_json(root / "artifacts/metrics.json")
        accepted_output = _validate_actions(output, task, facts)
        write_json(root / "artifacts/next-actions.json", accepted_output)
    else:
        raise ContractError(f"Unsupported task kind: {task['kind']}")

    receipt = {
        "task_id": task_id,
        "decision": decision,
        "validation_codes": validation_codes,
        "accepted_at": now_iso(),
        "result_hash": sha256_obj(result),
    }
    result_relative = f"results/{task_id}.result.json"
    receipt_relative = f"results/{task_id}.receipt.json"
    write_json(root / result_relative, result)
    write_json(root / receipt_relative, receipt)
    meta.update({"status": decision, "result_path": result_relative, "receipt_path": receipt_relative})
    record_event(manifest, "task_submitted", task_id=task_id, decision=decision)
    save_manifest(root, manifest)
    return receipt
