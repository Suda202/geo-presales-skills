from __future__ import annotations

import re
from pathlib import Path

from .util import ContractError, extract_urls, normalize_text, sha256_obj


INVALID_SIGNATURES = [
    ("LOGIN_REQUIRED", re.compile(r"\b(log in|login|sign in|sign up)\b.{0,80}\b(chatgpt|account|continue)\b", re.I | re.S)),
    ("ERROR_PAGE", re.compile(r"\b(something went wrong|internal server error|bad gateway|service unavailable|try again later)\b", re.I)),
    ("REFUSAL", re.compile(r"^(i['’]?m sorry[, ]+but |i (?:can(?:not|'t)|won't) (?:help|assist|provide)|unable to comply)", re.I)),
    ("PLACEHOLDER", re.compile(r"^(n/?a|no answer|placeholder|loading\.{0,3})$", re.I)),
]


def answer_validity(text: str) -> tuple[bool, str | None]:
    value = str(text or "").strip()
    if not value:
        return False, "EMPTY_ANSWER"
    for code, pattern in INVALID_SIGNATURES:
        if pattern.search(value):
            return False, code
    return True, None


def _question_catalog(question_bank: dict) -> dict[str, dict]:
    catalog = {}
    for item in question_bank["questions"]:
        key = item["question_id"].casefold()
        if key in catalog:
            raise ContractError(f"Duplicate question_id in catalog: {item['question_id']}")
        catalog[key] = item
    return catalog


def _question_for(source: dict, catalog: dict[str, dict]) -> dict:
    question_id = str(source.get("question_id") or "").strip()
    if not question_id:
        sample_id = str(source.get("sample_id") or "")
        matched = re.match(r"(.+)-r\d+$", sample_id, flags=re.I)
        if matched:
            question_id = matched.group(1)
    item = catalog.get(question_id.casefold())
    if not item:
        raise ContractError(f"Crawler sample references unknown question_id: {question_id!r}")
    source_question = str(source.get("question") or "").strip()
    if source_question and normalize_text(source_question) != normalize_text(item["question_text"]):
        raise ContractError(f"Question text mismatch for {question_id}")
    return item


def _citation_records(sample_id: str, result: dict | None, answer_text: str) -> tuple[list[dict], list[dict]]:
    citations: list[dict] = []
    issues: list[dict] = []
    reference_block = (result or {}).get("references") or {}
    items = reference_block.get("items") or []
    if not isinstance(items, list):
        items = []
        issues.append({"code": "INVALID_REFERENCE_ITEMS", "sample_id": sample_id})
    declared_count = reference_block.get("count")
    if isinstance(declared_count, int) and declared_count != len(items):
        issues.append({
            "code": "REFERENCE_COUNT_MISMATCH",
            "sample_id": sample_id,
            "declared": declared_count,
            "actual": len(items),
        })
    seen_platform_urls = set()
    for index, item in enumerate(items, 1):
        if not isinstance(item, dict):
            issues.append({"code": "INVALID_REFERENCE_ITEM", "sample_id": sample_id, "index": index})
            continue
        raw_url = str(item.get("url") or item.get("link") or item.get("href") or "").strip()
        if raw_url:
            seen_platform_urls.add(raw_url)
        citations.append({
            "raw_citation_id": f"C-{sample_id}-{len(citations)+1:03d}",
            "source": "platform",
            "source_order": index,
            "raw_url": raw_url or None,
            "source_name": item.get("source") or item.get("name"),
            "domain_hint": item.get("domain"),
            "title": item.get("title"),
            "date": item.get("date"),
            "summary": item.get("summary"),
            "source_position": item.get("source_position"),
            "positions": item.get("positions") or [],
            "extraction_method": item.get("extraction_method"),
        })
    for raw_url in extract_urls(answer_text):
        if raw_url in seen_platform_urls:
            continue
        citations.append({
            "raw_citation_id": f"C-{sample_id}-{len(citations)+1:03d}",
            "source": "body_link",
            "source_order": len(citations) + 1,
            "raw_url": raw_url,
            "source_name": None,
            "domain_hint": None,
            "title": None,
            "date": None,
            "summary": None,
            "source_position": None,
            "positions": [],
            "extraction_method": "answer_url_regex",
        })
    return citations, issues


def _import_batch(raw: dict, question_bank: dict, source_file: str) -> dict:
    catalog = _question_catalog(question_bank)
    samples = raw.get("samples")
    if not isinstance(samples, list):
        raise ContractError("Batch crawler input must contain samples[]")
    plan = raw.get("plan") if isinstance(raw.get("plan"), list) else []
    imported: list[dict] = []
    issues: list[dict] = []
    sample_ids = set()

    def append_sample(source: dict, pending: bool = False):
        question = _question_for(source, catalog)
        sample_id = str(source.get("sample_id") or f"{question['question_id']}-r{int(source.get('repeat_index') or 1):02d}")
        if sample_id in sample_ids:
            raise ContractError(f"Duplicate sample_id: {sample_id}")
        sample_ids.add(sample_id)
        result = source.get("result") if isinstance(source.get("result"), dict) else None
        answer_text = str((((result or {}).get("answer") or {}).get("text") or "")).strip()
        envelope_ok = source.get("ok") is True
        status_value = str(source.get("status") or "").casefold()
        result_ok = (result or {}).get("ok") is not False
        valid_text, validity_reason = answer_validity(answer_text)
        if pending:
            status = "pending"
            eligible = False
            error_code = "PENDING"
        elif status_value == "failed" or not envelope_ok:
            status = "failed"
            eligible = False
            error_code = "SOURCE_FAILED"
        elif result is None:
            status = "invalid"
            eligible = False
            error_code = "MISSING_RESULT"
        elif not result_ok:
            status = "failed"
            eligible = False
            error_code = "SOURCE_FAILED"
        elif not valid_text:
            status = "invalid"
            eligible = False
            error_code = validity_reason
        else:
            status = "success"
            eligible = True
            error_code = None
        citations, citation_issues = _citation_records(sample_id, result, answer_text)
        issues.extend(citation_issues)
        imported.append({
            "sample_id": sample_id,
            "question_id": question["question_id"],
            "question_index": source.get("question_index") or question["generation_sequence"],
            "question": question["question_text"],
            "repeat_index": int(source.get("repeat_index") or 1),
            "repeat_total": int(source.get("repeat_total") or 1),
            "engine": str((raw.get("run") or {}).get("engine") or "chatgpt"),
            "status": status,
            "analysis_eligible": eligible,
            "answer_text": answer_text if result is not None else None,
            "citations": citations if eligible else [],
            "error_code": error_code,
            "error_message": str(source.get("error") or "").strip() or None,
            "provenance": {
                "source_shape": "batch_v1",
                "source_file": source_file,
                "raw_path": source.get("raw_path"),
                "log_path": source.get("log_path"),
            },
        })

    for source in samples:
        if not isinstance(source, dict):
            raise ContractError("Crawler samples[] must contain objects")
        append_sample(source)
    for planned in plan:
        if isinstance(planned, dict) and str(planned.get("sample_id") or "") not in sample_ids:
            append_sample(planned, pending=True)

    represented_question_ids = {item["question_id"].casefold() for item in imported}
    for question in question_bank["questions"]:
        if question["question_id"].casefold() not in represented_question_ids:
            append_sample({
                "sample_id": f"{question['question_id']}-r01",
                "question_id": question["question_id"],
                "question_index": question["generation_sequence"],
                "repeat_index": 1,
                "repeat_total": 1,
                "question": question["question_text"],
            }, pending=True)

    imported.sort(key=lambda item: (item["question_index"] or 0, item["repeat_index"], item["sample_id"]))
    return _import_result(imported, max(len(plan), len(imported)), issues, raw, question_bank)


def _import_raw_collection(raw: dict | list, question_bank: dict, source_file: str) -> dict:
    catalog = _question_catalog(question_bank)
    entries = raw if isinstance(raw, list) else raw.get("results") or [raw]
    if not isinstance(entries, list):
        raise ContractError("Raw collection must be an object, list, or object containing results[]")
    wrapped_samples = []
    for index, entry in enumerate(entries, 1):
        if not isinstance(entry, dict):
            raise ContractError("Raw result collection contains a non-object")
        meta = entry.get("manifest") if isinstance(entry.get("manifest"), dict) else entry
        question_id = meta.get("question_id")
        sample_id = str(meta.get("sample_id") or "")
        if not question_id and sample_id:
            matched = re.match(r"(.+)-r\d+$", sample_id, flags=re.I)
            question_id = matched.group(1) if matched else None
        if not question_id:
            question_text = str(entry.get("question") or "").strip()
            candidates = [q for q in catalog.values() if normalize_text(q["question_text"]) == normalize_text(question_text)]
            if len(candidates) != 1:
                raise ContractError(f"Cannot map raw result {index} to one question_id")
            question_id = candidates[0]["question_id"]
        question = catalog.get(str(question_id).casefold())
        if not question:
            raise ContractError(f"Raw result references unknown question_id: {question_id}")
        wrapped_samples.append({
            "sample_id": sample_id or f"{question['question_id']}-r01",
            "question_id": question["question_id"],
            "question_index": question["generation_sequence"],
            "repeat_index": int(meta.get("repeat_index") or 1),
            "repeat_total": int(meta.get("repeat_total") or 1),
            "question": question["question_text"],
            "ok": entry.get("ok") is not False,
            "status": "done" if entry.get("ok") is not False else "failed",
            "error": entry.get("error"),
            "raw_path": meta.get("raw_path"),
            "log_path": meta.get("log_path"),
            "result": entry,
        })
    batch = {"run": {"engine": "chatgpt"}, "samples": wrapped_samples, "plan": []}
    result = _import_batch(batch, question_bank, source_file)
    for sample in result["samples"]:
        sample["provenance"]["source_shape"] = "raw_result_collection"
    result["source_shape"] = "raw_result_collection"
    return result


def _import_result(samples: list[dict], planned: int, issues: list[dict], raw: dict, question_bank: dict) -> dict:
    counts = {
        "planned_count": planned,
        "completed_count": sum(item["status"] != "pending" for item in samples),
        "valid_count": sum(item["analysis_eligible"] for item in samples),
        "failed_count": sum(item["status"] == "failed" for item in samples),
        "invalid_count": sum(item["status"] == "invalid" for item in samples),
        "pending_count": sum(item["status"] == "pending" for item in samples),
    }
    return {
        "schema_version": "geo-presales-crawl-import/v1",
        "run_id": question_bank["run_id"],
        "source_schema_version": raw.get("schema_version") if isinstance(raw, dict) else None,
        "source_shape": "batch_v1",
        "counts": counts,
        "issues": issues,
        "samples": samples,
        "import_hash": sha256_obj(samples),
    }


def import_crawl(raw: dict | list, question_bank: dict, source_file: str | Path) -> dict:
    if isinstance(raw, dict) and isinstance(raw.get("samples"), list):
        return _import_batch(raw, question_bank, str(source_file))
    return _import_raw_collection(raw, question_bank, str(source_file))
