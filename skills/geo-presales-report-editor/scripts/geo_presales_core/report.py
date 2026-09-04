from __future__ import annotations

import re
from pathlib import Path

from .store import record_event, save_manifest
from .tasks import create_task
from .util import ContractError, format_display, get_path, now_iso, read_json, sha256_file, sha256_obj, write_json
from .metrics import _is_sentiment_answer


MODULE_TITLES = {
    "M01": "数据总览",
    "M02": "竞品表现",
    "M03": "引用来源与官网覆盖",
    "M04": "品牌表达与风险",
    "M05": "品牌进入机会",
}


def _task_for(manifest: dict, root: Path, kind: str, predicate=None):
    for task_id, meta in manifest.get("tasks", {}).items():
        if meta["kind"] != kind:
            continue
        task = read_json(root / meta["path"])
        if predicate is None or predicate(task):
            return task_id, meta, task
    return None, None, None


def _sentiment_evidence(answers_doc: dict) -> dict:
    evidence = {}
    for answer in answers_doc["answers"]:
        if not answer["selected_for_report"] or answer["validity"] != "valid":
            continue
        if not _is_sentiment_answer(answer):
            continue
        target = next(item for item in answer["objects"] if item["role"] == "target")
        if target.get("sentiment_status") != "accepted":
            continue
        for index, item in enumerate(target.get("sentiment_evidence") or [], 1):
            evidence_id = f"E-{answer['answer_id']}-{index:02d}"
            evidence[evidence_id] = {
                "answer_id": answer["answer_id"],
                "question_id": answer["question_id"],
                "query": answer["question_text"],
                "sentiment": target["sentiment"],
                "quote": item["quote"],
            }
    return evidence


def _module_instruction(module_id: str) -> str:
    instructions = {
        "M01": "用中文解释确定性数据总览和采集覆盖情况。不要把限定范围的结果外推为整体市场结论。",
        "M02": "用中文解释监测对象与竞品的提及率、声量占比和平均提及位置。禁止把平均提及位置称为语义推荐排名。",
        "M03": "用中文解释来源结构和实际被引用的官网页面。禁止从未观察到引用推断某类页面不存在。",
        "M04": "用中文解释已经校验的正向、中性和负向表达证据。禁止虚构主题或把未提及当成中性。",
        "M05": "只用中文解释脚本已经完成的机会分档。禁止重新分类问题或向客户暴露内部枚举。",
    }
    return instructions[module_id]


def _write_fact_pack(root: Path, module_id: str, metrics: dict, themes: dict | None) -> str:
    pack = dict(metrics)
    pack["module_id"] = module_id
    pack["module_title"] = MODULE_TITLES[module_id]
    if module_id == "M04":
        pack["brand_expression_themes"] = themes or {"positive": [], "risk": []}
    relative = f"artifacts/facts/{module_id}.json"
    write_json(root / relative, pack)
    return relative


def prepare_report_tasks(root: Path, manifest: dict, config: dict, answers_doc: dict, metrics: dict) -> list[dict]:
    created = []
    evidence = _sentiment_evidence(answers_doc)
    theme_task_id, theme_meta, _ = _task_for(manifest, root, "brand_expression_themes")
    if evidence and not theme_task_id:
        theme_task = create_task(
            root,
            manifest,
            kind="brand_expression_themes",
            task_input={
                "evidence": evidence,
                "instruction": "仅将已校验原文归纳为简洁的中文正向主题和风险主题。support_count 由程序根据 evidence_ids 计算。",
            },
            blocking=False,
        )
        theme_task_id = theme_task["task_id"]
        theme_meta = manifest["tasks"][theme_task_id]
        created.append(theme_task)

    themes_path = root / "artifacts/brand-expression-themes.json"
    themes = read_json(themes_path) if themes_path.exists() else None
    module_ids = ["M01", "M02", "M03", "M05"]
    if not evidence or (theme_meta and theme_meta["status"] in {"accepted", "degraded"}):
        module_ids.append("M04")
    for module_id in module_ids:
        existing_id, _, _ = _task_for(manifest, root, "report_module", lambda task, mid=module_id: task["input"].get("module_id") == mid)
        if existing_id:
            continue
        fact_pack_ref = _write_fact_pack(root, module_id, metrics, themes)
        depends_on = [theme_task_id] if module_id == "M04" and theme_task_id else []
        task = create_task(
            root,
            manifest,
            kind="report_module",
            task_input={
                "module_id": module_id,
                "fact_pack_ref": fact_pack_ref,
                "instruction": _module_instruction(module_id),
                "claim_contract": "所有数字使用 {{fact:path}}；refs 必须与 token 完全一致。用中文返回一至五条观点和可选结论。",
            },
            resources={f"facts:{module_id}": {"path": fact_pack_ref, "sha256": sha256_file(root / fact_pack_ref)}},
            blocking=False,
            depends_on=depends_on,
        )
        created.append(task)

    module_tasks = []
    for module_id in MODULE_TITLES:
        item = _task_for(manifest, root, "report_module", lambda task, mid=module_id: task["input"].get("module_id") == mid)
        if item[0]:
            module_tasks.append(item)
    all_modules_resolved = len(module_tasks) == 5 and all(meta["status"] in {"accepted", "degraded"} for _, meta, _ in module_tasks)
    action_task_id, _, _ = _task_for(manifest, root, "next_actions")
    if all_modules_resolved and metrics["action_directions"] and not action_task_id:
        action_task = create_task(
            root,
            manifest,
            kind="next_actions",
            task_input={
                "directions": metrics["action_directions"],
                "instruction": "为每个给定方向写一条中文客户行动建议。禁止增加方向，或补写事实中不存在的数字承诺、渠道、频率和期限。",
            },
            resources={"facts:metrics": {"path": "artifacts/metrics.json", "sha256": sha256_file(root / "artifacts/metrics.json")}},
            blocking=False,
            depends_on=[task_id for task_id, _, _ in module_tasks],
        )
        created.append(action_task)
    return created


FACT_TOKEN_RE = re.compile(r"\{\{fact:([a-zA-Z0-9_.-]+)\}\}")


def _render_template(template: str, facts: dict) -> str:
    def replace(match):
        return format_display(get_path(facts, match.group(1)))
    return FACT_TOKEN_RE.sub(replace, str(template or ""))


def _render_module(artifact: dict | None, facts: dict, module_id: str) -> dict:
    if not artifact:
        return {"module_id": module_id, "title": MODULE_TITLES[module_id], "status": "degraded", "points": [], "conclusion": None}
    return {
        "module_id": module_id,
        "title": artifact["title"] or MODULE_TITLES[module_id],
        "status": "valid",
        "points": [
            {
                "text": _render_template(item["text_template"], facts),
                "evidence_refs": item.get("refs") or [],
            }
            for item in artifact["points"]
        ],
        "conclusion": _render_template(artifact["conclusion"]["text_template"], facts) if artifact.get("conclusion") else None,
    }


def _render_actions(artifact: dict | None, facts: dict, directions: list[dict]) -> dict:
    if not directions:
        return {"status": "not_applicable", "summary": None, "actions": []}
    if not artifact:
        return {"status": "degraded", "summary": None, "actions": []}
    return {
        "status": "valid",
        "summary": _render_template(artifact["summary"]["text_template"], facts) if artifact.get("summary") else None,
        "actions": [
            {
                **item,
                "evidence": _render_template(item.get("evidence_template"), facts),
                "expected_impact": _render_template(item.get("expected_impact_template"), facts),
            }
            for item in artifact["actions"]
        ],
    }


def publish_checks(config: dict, question_bank: dict, answers_doc: dict, metrics: dict, manifest: dict) -> list[dict]:
    checks = []

    def add(code: str, passed: bool, severity: str, message: str):
        checks.append({"code": code, "passed": bool(passed), "severity": severity, "message": message})

    quotas = config["quotas"]
    add("CONFIG_FROZEN", bool(config.get("config_hash") and config.get("frozen_at")), "blocking", "配置已经冻结并记录版本")
    add("QUESTION_TOTAL", len(question_bank["questions"]) == quotas["total"], "blocking", "问题总数符合冻结配额")
    add("VALID_ANSWER_PRESENT", metrics["coverage"]["valid_answers"] > 0, "blocking", "至少存在一条有效回答")
    add("BATCH_CONSISTENT", len({config["run_id"], question_bank["run_id"], answers_doc["run_id"], metrics["run_id"], manifest["run_id"]}) == 1, "blocking", "全部产物使用同一个 run_id")
    add(
        "METRIC_INPUT_HASHES",
        metrics.get("input_hashes") == {
            "config_hash": config["config_hash"],
            "question_bank_hash": question_bank["question_bank_hash"],
            "answers_hash": answers_doc["answers_hash"],
        },
        "blocking",
        "指标输入哈希与当前冻结产物一致",
    )

    unresolved = metrics["sentiment"]["unresolved_answer_ids"]
    add("TARGET_SENTIMENT_COMPLETE", not unresolved, "blocking", "所有入选有效回答中的监测对象提及都具备已校验情绪")
    generic_count = metrics["coverage"].get(
        "valid_discovery_answers",
        metrics["coverage"].get("valid_generic_answers", 0),
    )
    bucket_count = sum(metrics["opportunity"]["counts"].values())
    add("OPPORTUNITY_PARTITION", bucket_count == generic_count, "blocking", "每条有效发现类问题回答恰好进入一个机会档位")

    voices = [item["share_of_voice"]["raw"] for item in metrics["overview"]["objects"].values()]
    non_null_voices = [value for value in voices if value is not None]
    voice_ok = not non_null_voices or abs(sum(non_null_voices) - 1.0) < 1e-9
    add("VOICE_INVARIANT", voice_ok, "blocking", "声量占比分母非零时，各对象占比之和为一")

    pending = [task_id for task_id, meta in manifest.get("tasks", {}).items() if meta["status"] == "pending"]
    add("TASKS_RESOLVED", not pending, "blocking", "所有已生成语义任务都已解决")
    module_resolution = {}
    for module_id in MODULE_TITLES:
        task_id, meta, _ = _task_for(manifest, Path(manifest.get("_root", ".")), "report_module", lambda task, mid=module_id: task["input"].get("module_id") == mid) if manifest.get("_root") else (None, None, None)
        module_resolution[module_id] = bool(meta and meta["status"] in {"accepted", "degraded"})
    # Module structure is checked again in finalize where the run root is available.
    add("TRACEABILITY_PRESENT", bool(answers_doc.get("answers_hash") and metrics.get("metrics_hash")), "blocking", "规范化回答和指标均带有追溯哈希")
    return checks


def finalize_report(root: Path, manifest: dict, config: dict, question_bank: dict, answers_doc: dict, metrics: dict) -> tuple[dict, dict]:
    manifest_for_checks = dict(manifest)
    manifest_for_checks["_root"] = str(root)
    checks = publish_checks(config, question_bank, answers_doc, metrics, manifest_for_checks)
    module_artifacts = {}
    for module_id in MODULE_TITLES:
        path = root / f"artifacts/{module_id}.json"
        module_artifacts[module_id] = read_json(path) if path.exists() else None
        task_id, meta, _ = _task_for(manifest, root, "report_module", lambda task, mid=module_id: task["input"].get("module_id") == mid)
        checks.append({
            "code": f"{module_id}_RESOLVED",
            "passed": bool(task_id and meta["status"] in {"accepted", "degraded"}),
            "severity": "blocking",
            "message": f"{module_id} 任务已接受或已明确降级",
        })
    directions = metrics["action_directions"]
    action_path = root / "artifacts/next-actions.json"
    action_artifact = read_json(action_path) if action_path.exists() else None
    action_task_id, action_meta, _ = _task_for(manifest, root, "next_actions")
    checks.append({
        "code": "NEXT_ACTIONS_RESOLVED",
        "passed": not directions or bool(action_task_id and action_meta["status"] in {"accepted", "degraded"}),
        "severity": "blocking",
        "message": "存在确定性行动方向时，下一步行动任务已经解决",
    })
    blocking_failures = [item for item in checks if item["severity"] == "blocking" and not item["passed"]]
    publish = {
        "schema_version": "geo-presales-publish-check/v1",
        "run_id": config["run_id"],
        "checked_at": now_iso(),
        "publishable": not blocking_failures,
        "checks": checks,
        "blocking_failures": blocking_failures,
    }
    write_json(root / "artifacts/publish-check.json", publish)
    if blocking_failures:
        raise ContractError("Publish check failed: " + ", ".join(item["code"] for item in blocking_failures))

    themes_path = root / "artifacts/brand-expression-themes.json"
    themes = read_json(themes_path) if themes_path.exists() else {"positive": [], "risk": []}
    report = {
        "schema_version": "geo-presales-report-data/v1",
        "run_id": config["run_id"],
        "generated_at": now_iso(),
        "scope": {
            "topic": config["topic"],
            "market": config["market"],
            "language": config["language"],
            "platform": config["platform"],
            "disclaimer": "本报告基于固定主题、问题集和采集范围，用于观察该范围内的品牌与竞品表现，不代表全部用户需求、搜索量或市场份额。",
        },
        "metrics": metrics,
        "modules": {
            module_id: _render_module(module_artifacts[module_id], metrics, module_id)
            for module_id in MODULE_TITLES
        },
        "brand_expression_themes": themes,
        "next_actions": _render_actions(action_artifact, metrics, directions),
        "details": [
            {
                "answer_id": answer["answer_id"],
                "question_id": answer["question_id"],
                "question": answer["question_text"],
                "question_zh": answer.get("question_zh"),
                "question_type": answer["question_type"],
                "funnel_intent": answer["funnel_intent"],
                "diagnostic_intent": answer.get("diagnostic_intent"),
                "topic_id": answer.get("topic_id"),
                "attribute_ids": answer.get("attribute_ids") or [],
                "selected_for_report": answer["selected_for_report"],
                "validity": answer["validity"],
                "validity_reason": answer["validity_reason"],
                "answer_text": answer["answer_text"],
                "answer_zh": answer["answer_zh"],
                "objects": answer["objects"],
                "citations": answer["citations"],
                "provenance": answer["provenance"],
            }
            for answer in answers_doc["answers"]
        ],
        "publish_check": publish,
    }
    report["artifact_hash"] = sha256_obj(report)
    audit = {
        "schema_version": "geo-presales-audit/v1",
        "run_id": config["run_id"],
        "config_hash": config["config_hash"],
        "question_bank_hash": question_bank["question_bank_hash"],
        "answers_hash": answers_doc["answers_hash"],
        "metrics_hash": metrics["metrics_hash"],
        "report_hash": report["artifact_hash"],
        "ruleset_version": config["ruleset_version"],
        "rank_policy": config["rank_policy"],
        "sample_policy": config["sample_policy"],
        "question_warnings": question_bank.get("warnings") or [],
        "answer_issues": answers_doc.get("issues") or [],
        "task_receipts": {
            task_id: {
                "kind": meta["kind"],
                "status": meta["status"],
                "result_path": meta.get("result_path"),
                "receipt_path": meta.get("receipt_path"),
            }
            for task_id, meta in manifest.get("tasks", {}).items()
        },
        "known_limitations": [
            "report_rank 表示已配置对象的平均提及位置依据（正文首次提及顺序），不是语义推荐排名",
            "可注册域名聚合使用内置常见多级后缀表，而不是完整 Public Suffix List",
            "未知来源分类可能降级为 other；官网域名匹配始终由确定性规则完成",
        ],
    }
    write_json(root / "artifacts/report-data.json", report)
    write_json(root / "artifacts/audit.json", audit)
    manifest["state"] = "COMPLETE"
    manifest["paths"]["report"] = "artifacts/report-data.json"
    manifest["completed_at"] = now_iso()
    record_event(manifest, "run_finalized", report_hash=report["artifact_hash"])
    save_manifest(root, manifest)
    return report, audit
