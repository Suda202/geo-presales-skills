#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


PROTOCOL_VERSION = "overseas-geo-backend-report-task/v1"
PAYLOAD_VERSION = "overseas-geo-backend-report-input/v1"
RESULT_VERSION = "overseas-geo-backend-report-result/v1"

SUMMARY_KEYS = {
    "M01": "summary_overview",
    "M02": "summary_competitor_performance",
    "M03": "summary_citation_sources",
    "M04": "summary_brand_expression",
    "M05": "summary_category_actions",
    "M06": "summary_priority_opportunities",
    "M10": "summary_final",
}

MODULE_ORDER = {"M02": 20, "M03": 30, "M04": 40, "M05": 50, "M01": 60, "M06": 70, "M10": 80}
BASE_MODULES = ("M02", "M03", "M04", "M05")
RESOLVED_STATUSES = {"accepted", "degraded"}
CUSTOMER_BANNED = re.compile(r"P[012]|p[012]|赋能|深度赋能|全面提升|优化升级|建议您|我们应该|严重落后|毫无建树|被动挨打")
ACTION_BANNED = re.compile(r"建议|应该|应当|需要|需|优先补齐|创建|新建|检查并完善|建设页面|强化内容")
NUMBER_RE = re.compile(r"(?<![A-Za-z0-9_])-?\d+(?:\.\d+)?%?")


class ContractError(ValueError):
    pass


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path):
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path, value):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temp_name, target)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def digest(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def file_digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            value.update(chunk)
    return "sha256:" + value.hexdigest()


def parse_json_field(value, field, expected_type):
    parsed = value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ContractError(f"{field} 不能为空")
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as error:
            raise ContractError(f"{field} 不是合法 JSON string") from error
    if not isinstance(parsed, expected_type):
        expected = "对象" if expected_type is dict else "数组"
        raise ContractError(f"{field} 必须是 JSON {expected}或对应 JSON string")
    return parsed


def collect_values(value, keys, found):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in keys and child not in (None, ""):
                found.add(str(child))
            collect_values(child, keys, found)
    elif isinstance(value, list):
        for child in value:
            collect_values(child, keys, found)


def normalize_action_context(raw):
    if raw in (None, ""):
        return {"directions": [], "source": "not_provided"}
    context = parse_json_field(raw, "action_context", dict)
    directions = context.get("directions") or []
    if not isinstance(directions, list):
        raise ContractError("action_context.directions 必须是数组")
    normalized = []
    for index, item in enumerate(directions, 1):
        if not isinstance(item, dict):
            raise ContractError("action_context.directions 项必须是对象")
        direction = str(item.get("direction") or "").strip()
        state = str(item.get("state") or "").strip()
        posture = str(item.get("posture") or "").strip()
        evidence = str(item.get("key_evidence") or item.get("evidence") or "").strip()
        template = str(item.get("action_template") or "").strip()
        if not all((direction, state, posture, evidence, template)):
            raise ContractError("每个行动方向必须提供 direction、state、posture、key_evidence 和 action_template")
        normalized.append({
            **item,
            "direction_id": str(item.get("direction_id") or f"ACT-{index:03d}"),
            "direction": direction,
            "state": state,
            "posture": posture,
            "key_evidence": evidence,
            "action_template": template,
        })
    if len(normalized) > 3:
        raise ContractError("action_context.directions 最多三个")
    return {**context, "directions": normalized, "source": context.get("source") or "backend"}


def normalize_payload(raw):
    required_text = ("brand_name", "corp_name", "core_topic", "market", "language", "task_id")
    common = {}
    for field in required_text:
        value = str(raw.get(field) or "").strip()
        if not value:
            raise ContractError(f"缺少必填字段 {field}")
        common[field] = value
    common["product_name"] = str(raw.get("product_name") or "").strip() or None

    normalized = {
        "schema_version": PAYLOAD_VERSION,
        **common,
        "overview": parse_json_field(raw.get("overview"), "overview", dict),
        "competitor": parse_json_field(raw.get("competitor"), "competitor", dict),
        "citation": parse_json_field(raw.get("citation"), "citation", dict),
        "brand_expression": parse_json_field(raw.get("brand_expression"), "brand_expression", list),
        "category_actions": parse_json_field(raw.get("category_actions"), "category_actions", dict),
        "question_details": parse_json_field(raw.get("question_details"), "question_details", list),
    }

    for index, item in enumerate(normalized["brand_expression"], 1):
        if not isinstance(item, dict):
            raise ContractError("brand_expression 每一项必须是对象")
        item.setdefault("evidence_id", f"BE-{index:03d}")
    evidence_ids = [str(item["evidence_id"]) for item in normalized["brand_expression"]]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ContractError("brand_expression.evidence_id 必须唯一")

    action_raw = raw.get("action_context")
    if action_raw in (None, ""):
        action_raw = normalized["overview"].get("action_context")
    if action_raw in (None, ""):
        action_raw = normalized["category_actions"].get("action_context")
    normalized["action_context"] = normalize_action_context(action_raw)

    nested_task_ids = set()
    collect_values(normalized, {"task_id"}, nested_task_ids)
    if nested_task_ids and nested_task_ids != {common["task_id"]}:
        raise ContractError("后端统计包内存在与顶层 task_id 不一致的数据")

    batch_ids = set()
    collect_values(normalized, {"batch_id", "report_batch_id"}, batch_ids)
    explicit_batch = str(raw.get("batch_id") or "").strip()
    if explicit_batch:
        batch_ids.add(explicit_batch)
    if len(batch_ids) > 1:
        raise ContractError("后端统计包混入多个 batch_id")
    normalized["batch_id"] = next(iter(batch_ids), common["task_id"])
    normalized["input_hash"] = digest(normalized)
    return normalized


def manifest_path(root):
    return root / "manifest.json"


def load_run(run_dir):
    root = Path(run_dir).expanduser().resolve()
    if not manifest_path(root).exists():
        raise ContractError(f"运行目录不存在或未初始化：{root}")
    return root, read_json(manifest_path(root))


def save_manifest(root, manifest):
    manifest["updated_at"] = now_iso()
    write_json(manifest_path(root), manifest)


def module_result_path(module_id):
    return f"results/{module_id}.accepted.json"


def module_resolved(manifest, module_id):
    return (manifest.get("modules", {}).get(module_id) or {}).get("status") in RESOLVED_STATUSES


def primary_fact_path(module_id):
    return {
        "M01": "canonical/overview.json",
        "M02": "canonical/competitor.json",
        "M03": "canonical/citation.json",
        "M04": "canonical/brand_expression.json",
        "M05": "canonical/category_actions.json",
        "M06": "canonical/action_context.json",
    }.get(module_id)


def module_dependencies(module_id):
    return {
        "M01": ["M05"],
        "M02": [],
        "M03": [],
        "M04": [],
        "M05": [],
        "M06": ["M02", "M03", "M04", "M05"],
        "M10": ["M01", "M02", "M03", "M04", "M05", "M06"],
    }[module_id]


def output_contract(module_id):
    return {
        "M01": {"content": {"title": "string", "points": "string[3..5]", "conclusion": "string"}},
        "M02": {"content": "string[3]，顺序固定为提及率、声量占比、平均排名"},
        "M03": {"content": "string[3]，顺序固定为来源结构、官网引用事实、改进方向"},
        "M04": {"content": {"positive_evidence": "{keyword,explain}[0..5]", "risk_evidence": "{keyword,explain}[0..5]", "analysis_items": "string[3]"}},
        "M05": {"content": {"p0": "string", "p1": "string", "p2": "string"}},
        "M06": {"content": {"summary": "string", "actions": "{direction_id,source_module,title,evidence,action,expected_impact}[]"}},
        "M10": {"content": {"title": "string", "summary": "string", "points": "string[3..5]", "conclusion": "string"}},
    }[module_id]


def module_purpose(module_id):
    return {
        "M01": "只解释后端数据总览与已定稿品牌进入机会，不计算任何指标或重新分档。",
        "M02": "只解释后端竞品表现数据，固定输出提及率、声量占比、平均排名三条结论。",
        "M03": "只解释后端引用来源数据，承认已有官网引用事实，再描述覆盖缺口。",
        "M04": "只从后端给出的本品表达证据中归纳正向与风险关键词。",
        "M05": "只解释后端已经分好的三档问题，不重新分档，不输出行动建议。",
        "M06": "只把后端给出的行动方向写成客户可读行动，不重新判状态或新增方向。",
        "M10": "只综合已定稿模块，不引入任何新事实或新数字。",
    }[module_id]


def create_task(root, manifest, payload, module_id):
    if module_id in manifest["modules"]:
        return
    resources = {}
    fact_path = primary_fact_path(module_id)
    if fact_path:
        resources["facts"] = {"path": fact_path, "sha256": file_digest(root / fact_path)}
    for dependency in module_dependencies(module_id):
        path = module_result_path(dependency)
        resources[f"module:{dependency}"] = {"path": path, "sha256": file_digest(root / path)}
    task_seed = {"module_id": module_id, "input_hash": payload["input_hash"], "resources": resources}
    task_id = f"T-{module_id}-{digest(task_seed).split(':', 1)[1][:12]}"
    task = {
        "protocol_version": PROTOCOL_VERSION,
        "run_id": manifest["run_id"],
        "task_id": task_id,
        "kind": "backend_report_module",
        "module_id": module_id,
        "blocking": True,
        "depends_on": module_dependencies(module_id),
        "resources": resources,
        "input": {
            "brand_name": payload["brand_name"],
            "corp_name": payload["corp_name"],
            "product_name": payload["product_name"],
            "core_topic": payload["core_topic"],
            "market": payload["market"],
            "language": payload["language"],
            "purpose": module_purpose(module_id),
            "output_contract": output_contract(module_id),
            "evidence_rule": "output.evidence_refs 必须覆盖每个非空结论，并引用 fact:/JSON指针、module:Mxx:/JSON指针、evidence:BE-xxx 或 action:ACT-xxx。",
            "global_rules": [
                "输入文件是唯一事实源，禁止自行计算、补数或根据品牌常识扩写。",
                "输出客户文案固定为中文，保持第三方、客观、结论先行。",
                "不得出现 Markdown、内部编码、夸张措辞或承诺具体提升结果。",
            ],
        },
        "created_at": now_iso(),
    }
    task["task_digest"] = digest(task)
    path = f"tasks/{task_id}.json"
    write_json(root / path, task)
    manifest["tasks"][task_id] = {
        "module_id": module_id,
        "status": "pending",
        "path": path,
        "result_path": None,
    }
    manifest["modules"][module_id] = {"status": "pending", "task_id": task_id, "result_path": None}


def create_degraded_actions(root, manifest):
    content = {"summary": "", "actions": []}
    result = {
        "schema_version": RESULT_VERSION,
        "module_id": "M06",
        "status": "degraded",
        "content": content,
        "evidence_refs": {},
        "reason": "后端未提供 action_context，正式报告不在本地重新计算行动状态。",
    }
    write_json(root / module_result_path("M06"), result)
    manifest["modules"]["M06"] = {
        "status": "degraded",
        "task_id": None,
        "result_path": module_result_path("M06"),
    }
    manifest["warnings"].append(result["reason"])


def ensure_tasks(root, manifest, payload):
    for module_id in BASE_MODULES:
        create_task(root, manifest, payload, module_id)
    if module_resolved(manifest, "M05"):
        create_task(root, manifest, payload, "M01")
    if all(module_resolved(manifest, module_id) for module_id in ("M02", "M03", "M04", "M05")) and "M06" not in manifest["modules"]:
        if payload["action_context"]["directions"]:
            create_task(root, manifest, payload, "M06")
        else:
            create_degraded_actions(root, manifest)
    if all(module_resolved(manifest, module_id) for module_id in ("M01", "M02", "M03", "M04", "M05", "M06")):
        create_task(root, manifest, payload, "M10")


def refresh_state(manifest):
    pending = [item for item in manifest["modules"].values() if item["status"] == "pending"]
    if manifest.get("state") == "COMPLETE":
        return
    manifest["state"] = "WAITING_AGENT" if pending else ("READY_TO_FINALIZE" if module_resolved(manifest, "M10") else "PREPARED")


def prepare_run(input_path, run_dir):
    root = Path(run_dir).expanduser().resolve()
    if root.exists() and any(root.iterdir()):
        raise ContractError(f"运行目录非空：{root}")
    root.mkdir(parents=True, exist_ok=True)
    source = Path(input_path).expanduser().resolve()
    payload = normalize_payload(read_json(source))
    (root / "input").mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, root / "input/backend-payload.source.json")
    write_json(root / "canonical/backend-payload.json", payload)
    for field in ("overview", "competitor", "citation", "brand_expression", "category_actions", "question_details", "action_context"):
        write_json(root / f"canonical/{field}.json", payload[field])
    manifest = {
        "schema_version": "overseas-geo-backend-report-run/v1",
        "run_id": payload["task_id"],
        "batch_id": payload["batch_id"],
        "input_hash": payload["input_hash"],
        "state": "PREPARED",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "modules": {},
        "tasks": {},
        "warnings": [],
    }
    ensure_tasks(root, manifest, payload)
    refresh_state(manifest)
    save_manifest(root, manifest)
    return root, manifest


def ready_tasks(root, manifest):
    ready = []
    for task_id, meta in manifest["tasks"].items():
        if meta["status"] != "pending":
            continue
        task = read_json(root / meta["path"])
        if all(module_resolved(manifest, dependency) for dependency in task["depends_on"]):
            ready.append(task)
    ready.sort(key=lambda item: (MODULE_ORDER[item["module_id"]], item["task_id"]))
    return ready


def pointer_get(value, pointer):
    if pointer in ("", "/"):
        return value
    if not pointer.startswith("/"):
        raise ContractError(f"JSON 指针格式错误：{pointer}")
    current = value
    for raw_part in pointer[1:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError) as error:
                raise ContractError(f"JSON 指针不存在：{pointer}") from error
        elif isinstance(current, dict) and part in current:
            current = current[part]
        else:
            raise ContractError(f"JSON 指针不存在：{pointer}")
    return current


def statement_pointers(module_id, content):
    if module_id in {"M02", "M03"}:
        return [f"/{index}" for index in range(len(content))]
    if module_id == "M04":
        result = []
        for group in ("positive_evidence", "risk_evidence"):
            result.extend(f"/{group}/{index}" for index in range(len(content[group])))
        result.extend(f"/analysis_items/{index}" for index in range(len(content["analysis_items"])))
        return result
    if module_id == "M05":
        return [f"/{key}" for key in ("p0", "p1", "p2") if content[key]]
    if module_id == "M06":
        result = ["/summary"] if content["summary"] else []
        result.extend(f"/actions/{index}" for index in range(len(content["actions"])))
        return result
    if module_id == "M01":
        return ["/title", *[f"/points/{index}" for index in range(len(content["points"]))], "/conclusion"]
    if module_id == "M10":
        return ["/title", "/summary", *[f"/points/{index}" for index in range(len(content["points"]))], "/conclusion"]
    raise ContractError(f"未知模块：{module_id}")


def require_string(value, field, allow_empty=False, max_length=120):
    if not isinstance(value, str):
        raise ContractError(f"{field} 必须是字符串")
    if not allow_empty and not value.strip():
        raise ContractError(f"{field} 不能为空")
    if len(value) > max_length:
        raise ContractError(f"{field} 超过 {max_length} 字符")
    if "```" in value or CUSTOMER_BANNED.search(value):
        raise ContractError(f"{field} 含禁止表达或内部编码")


def validate_exact_keys(value, keys, field):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ContractError(f"{field} 字段必须严格为 {sorted(keys)}")


def validate_content(module_id, content, payload):
    if module_id in {"M02", "M03"}:
        if not isinstance(content, list) or len(content) != 3:
            raise ContractError(f"{module_id}.content 必须是固定三条字符串数组")
        for index, item in enumerate(content):
            require_string(item, f"{module_id}.content[{index}]", max_length=90)
    elif module_id == "M04":
        validate_exact_keys(content, {"positive_evidence", "risk_evidence", "analysis_items"}, "M04.content")
        for group in ("positive_evidence", "risk_evidence"):
            if not isinstance(content[group], list) or len(content[group]) > 5:
                raise ContractError(f"M04.{group} 必须是最多五项数组")
            for index, item in enumerate(content[group]):
                validate_exact_keys(item, {"keyword", "explain"}, f"M04.{group}[{index}]")
                require_string(item["keyword"], f"M04.{group}[{index}].keyword", max_length=16)
                require_string(item["explain"], f"M04.{group}[{index}].explain", max_length=60)
        if not isinstance(content["analysis_items"], list) or len(content["analysis_items"]) != 3:
            raise ContractError("M04.analysis_items 必须固定三条")
        for index, item in enumerate(content["analysis_items"]):
            require_string(item, f"M04.analysis_items[{index}]", max_length=80)
    elif module_id == "M05":
        validate_exact_keys(content, {"p0", "p1", "p2"}, "M05.content")
        groups = payload["category_actions"]
        for key in ("p0", "p1", "p2"):
            require_string(content[key], f"M05.{key}", allow_empty=True, max_length=90)
            has_input = bool(groups.get(key) or [])
            if has_input != bool(content[key].strip()):
                raise ContractError(f"M05.{key} 必须与后端该档是否为空保持一致")
            if content[key] and ACTION_BANNED.search(content[key]):
                raise ContractError(f"M05.{key} 只能写现状，不能写行动建议")
    elif module_id == "M01":
        validate_exact_keys(content, {"title", "points", "conclusion"}, "M01.content")
        require_string(content["title"], "M01.title", max_length=60)
        if not isinstance(content["points"], list) or not 3 <= len(content["points"]) <= 5:
            raise ContractError("M01.points 必须是三至五条")
        for index, item in enumerate(content["points"]):
            require_string(item, f"M01.points[{index}]", max_length=90)
        require_string(content["conclusion"], "M01.conclusion", max_length=90)
    elif module_id == "M06":
        validate_exact_keys(content, {"summary", "actions"}, "M06.content")
        require_string(content["summary"], "M06.summary", max_length=70)
        directions = payload["action_context"]["directions"]
        if not isinstance(content["actions"], list) or len(content["actions"]) != len(directions):
            raise ContractError("M06.actions 必须与后端行动方向一一对应")
        direction_map = {item["direction_id"]: item for item in directions}
        seen = set()
        for index, item in enumerate(content["actions"]):
            validate_exact_keys(item, {"direction_id", "source_module", "title", "evidence", "action", "expected_impact"}, f"M06.actions[{index}]")
            direction_id = str(item["direction_id"])
            if direction_id not in direction_map or direction_id in seen:
                raise ContractError("M06.actions.direction_id 必须唯一对应后端方向")
            seen.add(direction_id)
            for field, limit in (("source_module", 20), ("title", 24), ("evidence", 70), ("action", 90), ("expected_impact", 50)):
                require_string(item[field], f"M06.actions[{index}].{field}", max_length=limit)
    elif module_id == "M10":
        validate_exact_keys(content, {"title", "summary", "points", "conclusion"}, "M10.content")
        require_string(content["title"], "M10.title", max_length=40)
        require_string(content["summary"], "M10.summary", max_length=100)
        if not isinstance(content["points"], list) or not 3 <= len(content["points"]) <= 5:
            raise ContractError("M10.points 必须是三至五条")
        for index, item in enumerate(content["points"]):
            require_string(item, f"M10.points[{index}]", max_length=70)
        require_string(content["conclusion"], "M10.conclusion", max_length=100)
    else:
        raise ContractError(f"未知模块：{module_id}")


def resource_values(root, task):
    return {name: read_json(root / meta["path"]) for name, meta in task["resources"].items()}


def validate_evidence_refs(root, task, content, refs, payload):
    pointers = statement_pointers(task["module_id"], content)
    if not isinstance(refs, dict) or set(refs) != set(pointers):
        raise ContractError("evidence_refs 必须逐条覆盖全部非空结论，且不能多写或漏写")
    resources = resource_values(root, task)
    expression_ids = {str(item["evidence_id"]) for item in payload["brand_expression"]}
    action_ids = {str(item["direction_id"]) for item in payload["action_context"]["directions"]}
    for pointer, items in refs.items():
        if not isinstance(items, list) or not items:
            raise ContractError(f"{pointer} 至少需要一个证据引用")
        for ref in items:
            if not isinstance(ref, str):
                raise ContractError("证据引用必须是字符串")
            if ref.startswith("fact:"):
                if "facts" not in resources:
                    raise ContractError(f"当前模块没有事实资源：{ref}")
                pointer_get(resources["facts"], ref[5:])
            elif ref.startswith("module:"):
                match = re.fullmatch(r"module:(M\d{2}):(.*)", ref)
                if not match or f"module:{match.group(1)}" not in resources:
                    raise ContractError(f"模块证据引用不可用：{ref}")
                module_result = resources[f"module:{match.group(1)}"]
                pointer_get(module_result["content"], match.group(2))
            elif ref.startswith("evidence:"):
                if ref.split(":", 1)[1] not in expression_ids:
                    raise ContractError(f"表达证据 ID 不存在：{ref}")
            elif ref.startswith("action:"):
                if ref.split(":", 1)[1] not in action_ids:
                    raise ContractError(f"行动方向 ID 不存在：{ref}")
            else:
                raise ContractError(f"未知证据引用格式：{ref}")


def collect_allowed_numbers(value, result):
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, (int, float)):
        variants = {f"{value:g}"}
        if 0 <= abs(float(value)) <= 1:
            variants.update({f"{value * 100:g}", f"{value * 100:g}%"})
        result.update(variants)
    elif isinstance(value, str):
        result.update(NUMBER_RE.findall(value))
        result.update(token.rstrip("%") for token in NUMBER_RE.findall(value))
    elif isinstance(value, list):
        result.add(str(len(value)))
        for item in value:
            collect_allowed_numbers(item, result)
    elif isinstance(value, dict):
        for item in value.values():
            collect_allowed_numbers(item, result)


def validate_numbers(root, task, content):
    allowed = set()
    for value in resource_values(root, task).values():
        collect_allowed_numbers(value, allowed)
    output_numbers = NUMBER_RE.findall(json.dumps(content, ensure_ascii=False))
    for token in output_numbers:
        if token not in allowed and token.rstrip("%") not in allowed:
            raise ContractError(f"输出出现事实资源中不存在的数字：{token}")


def validate_result_envelope(task, result):
    for key in ("protocol_version", "run_id", "task_id", "kind", "module_id", "task_digest"):
        if result.get(key) != task.get(key):
            raise ContractError(f"result.{key} 与任务不一致")
    if result.get("status") != "completed":
        raise ContractError("正式报告模块只接受 status=completed；无法完成时应保留任务并说明问题")
    output = result.get("output")
    validate_exact_keys(output, {"content", "evidence_refs"}, "result.output")
    return output


def submit_result(run_dir, task_id, result_path):
    root, manifest = load_run(run_dir)
    if task_id not in manifest["tasks"]:
        raise ContractError(f"未知 task_id：{task_id}")
    meta = manifest["tasks"][task_id]
    if meta["status"] != "pending":
        raise ContractError(f"任务已经处理：{task_id}")
    task = read_json(root / meta["path"])
    for resource in task["resources"].values():
        if file_digest(root / resource["path"]) != resource["sha256"]:
            raise ContractError("任务资源在发出后发生变化")
    result = read_json(result_path)
    output = validate_result_envelope(task, result)
    payload = read_json(root / "canonical/backend-payload.json")
    validate_content(task["module_id"], output["content"], payload)
    validate_evidence_refs(root, task, output["content"], output["evidence_refs"], payload)
    validate_numbers(root, task, output["content"])
    accepted = {
        "schema_version": RESULT_VERSION,
        "module_id": task["module_id"],
        "status": "accepted",
        "content": output["content"],
        "evidence_refs": output["evidence_refs"],
        "accepted_at": now_iso(),
        "task_id": task_id,
        "task_digest": task["task_digest"],
    }
    target = root / module_result_path(task["module_id"])
    write_json(target, accepted)
    meta["status"] = "accepted"
    meta["result_path"] = module_result_path(task["module_id"])
    manifest["modules"][task["module_id"]]["status"] = "accepted"
    manifest["modules"][task["module_id"]]["result_path"] = module_result_path(task["module_id"])
    ensure_tasks(root, manifest, payload)
    refresh_state(manifest)
    save_manifest(root, manifest)
    return root, manifest, accepted


def clean_dify_content(module_id, content):
    if module_id != "M06":
        return content
    return {
        "summary": content["summary"],
        "actions": [
            {key: value for key, value in item.items() if key != "direction_id"}
            for item in content["actions"]
        ],
    }


def finalize_run(run_dir):
    root, manifest = load_run(run_dir)
    required = ("M01", "M02", "M03", "M04", "M05", "M06", "M10")
    unresolved = [module_id for module_id in required if not module_resolved(manifest, module_id)]
    if unresolved:
        raise ContractError("仍有未完成模块：" + ", ".join(unresolved))
    payload = read_json(root / "canonical/backend-payload.json")
    modules = {module_id: read_json(root / module_result_path(module_id)) for module_id in required}
    normalized = {
        "schema_version": "overseas-geo-presales-report/v1",
        "task_id": payload["task_id"],
        "batch_id": payload["batch_id"],
        "brand_name": payload["brand_name"],
        "corp_name": payload["corp_name"],
        "product_name": payload["product_name"],
        "core_topic": payload["core_topic"],
        "market": payload["market"],
        "language": payload["language"],
        "backend_input_hash": payload["input_hash"],
        "modules": {SUMMARY_KEYS[module_id]: modules[module_id]["content"] for module_id in required},
        "warnings": manifest["warnings"],
        "generated_at": now_iso(),
    }
    normalized["report_hash"] = digest(normalized)
    dify = {
        SUMMARY_KEYS[module_id]: json.dumps(clean_dify_content(module_id, modules[module_id]["content"]), ensure_ascii=False)
        for module_id in required
    }
    audit = {
        "schema_version": "overseas-geo-presales-report-audit/v1",
        "task_id": payload["task_id"],
        "batch_id": payload["batch_id"],
        "backend_input_hash": payload["input_hash"],
        "report_hash": normalized["report_hash"],
        "module_status": {module_id: modules[module_id]["status"] for module_id in required},
        "evidence_refs": {module_id: modules[module_id]["evidence_refs"] for module_id in required},
        "warnings": manifest["warnings"],
        "production_fact_owner": "company_backend",
        "local_metric_recalculation": False,
    }
    write_json(root / "artifacts/report.json", normalized)
    write_json(root / "artifacts/dify-compatible-output.json", dify)
    write_json(root / "artifacts/audit.json", audit)
    manifest["state"] = "COMPLETE"
    manifest["artifacts"] = {
        "report": "artifacts/report.json",
        "dify_compatible_output": "artifacts/dify-compatible-output.json",
        "audit": "artifacts/audit.json",
    }
    save_manifest(root, manifest)
    return root, manifest, normalized


def emit(value):
    json.dump(value, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def cmd_prepare(args):
    root, manifest = prepare_run(args.input, args.run_dir)
    emit({
        "run_dir": str(root),
        "state": manifest["state"],
        "ready_modules": [task["module_id"] for task in ready_tasks(root, manifest)],
        "warnings": manifest["warnings"],
    })


def cmd_next_task(args):
    root, manifest = load_run(args.run_dir)
    tasks = ready_tasks(root, manifest)
    selected = tasks if args.all_ready else tasks[:1]
    emit({
        "state": manifest["state"],
        "tasks": [
            {
                "task_id": task["task_id"],
                "module_id": task["module_id"],
                "task_path": str(root / manifest["tasks"][task["task_id"]]["path"]),
                "suggested_result_path": str(root / "results" / f"{task['task_id']}.inbox.json"),
                "task": task if args.inline else None,
            }
            for task in selected
        ],
    })


def cmd_submit(args):
    root, manifest, accepted = submit_result(args.run_dir, args.task_id, args.result)
    emit({
        "accepted_module": accepted["module_id"],
        "state": manifest["state"],
        "ready_modules": [task["module_id"] for task in ready_tasks(root, manifest)],
        "warnings": manifest["warnings"],
    })


def cmd_status(args):
    root, manifest = load_run(args.run_dir)
    emit({
        "run_id": manifest["run_id"],
        "batch_id": manifest["batch_id"],
        "state": manifest["state"],
        "modules": manifest["modules"],
        "ready_modules": [task["module_id"] for task in ready_tasks(root, manifest)],
        "warnings": manifest["warnings"],
        "artifacts": manifest.get("artifacts") or {},
    })


def cmd_finalize(args):
    root, manifest, report = finalize_run(args.run_dir)
    emit({
        "state": manifest["state"],
        "report_hash": report["report_hash"],
        "report": str(root / manifest["artifacts"]["report"]),
        "dify_compatible_output": str(root / manifest["artifacts"]["dify_compatible_output"]),
        "audit": str(root / manifest["artifacts"]["audit"]),
        "warnings": manifest["warnings"],
    })


def build_parser():
    parser = argparse.ArgumentParser(prog="backend_report", description="基于公司后端统计包生成海外 GEO 售前报告结论")
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare", help="校验并冻结后端统计包，生成首批报告任务")
    prepare.add_argument("--input", required=True)
    prepare.add_argument("--run-dir", required=True)
    prepare.set_defaults(func=cmd_prepare)
    next_task = sub.add_parser("next-task", help="读取下一个或全部当前可执行的报告任务")
    next_task.add_argument("--run-dir", required=True)
    next_task.add_argument("--inline", action="store_true")
    next_task.add_argument("--all-ready", action="store_true")
    next_task.set_defaults(func=cmd_next_task)
    submit = sub.add_parser("submit-task", help="校验并接收一个报告模块结果")
    submit.add_argument("--run-dir", required=True)
    submit.add_argument("--task-id", required=True)
    submit.add_argument("--result", required=True)
    submit.set_defaults(func=cmd_submit)
    status = sub.add_parser("status", help="查看模块依赖、待处理任务与降级状态")
    status.add_argument("--run-dir", required=True)
    status.set_defaults(func=cmd_status)
    finalize = sub.add_parser("finalize", help="生成正式报告、Dify 兼容输出与审计文件")
    finalize.add_argument("--run-dir", required=True)
    finalize.set_defaults(func=cmd_finalize)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
        return 0
    except (ContractError, FileNotFoundError, json.JSONDecodeError, KeyError) as error:
        emit({"error": type(error).__name__, "message": str(error)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
