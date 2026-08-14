from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from .config import normalize_config
from .crawler import import_crawl
from .deterministic import prepare_answers
from .metrics import compute_metrics
from .questions import normalize_question_bank
from .report import finalize_report, prepare_report_tasks
from .store import create_run_dir, record_event, require_run, save_manifest
from .tasks import create_prepare_tasks, pending_tasks, submit_task
from .util import ContractError, read_json, write_json


def _emit(value) -> None:
    json.dump(value, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def _copy_source(source: str | Path, target: Path) -> None:
    source_path = Path(source).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if source_path != target.resolve():
        shutil.copy2(source_path, target)


def cmd_create_run(args):
    raw = read_json(args.config)
    config = normalize_config(raw)
    manifest = create_run_dir(args.run_dir, config, args.config)
    _emit({"run_dir": str(Path(args.run_dir).expanduser().resolve()), "run_id": config["run_id"], "state": manifest["state"]})


def cmd_import_questions(args):
    root, manifest = require_run(args.run_dir)
    config = read_json(root / manifest["paths"]["config"])
    bank = normalize_question_bank(read_json(args.questions), config)
    write_json(root / "canonical/questions.json", bank)
    _copy_source(args.questions, root / "input/questions.source.json")
    manifest["paths"]["questions"] = "canonical/questions.json"
    manifest["state"] = "QUESTIONS_IMPORTED"
    record_event(manifest, "questions_imported", count=len(bank["questions"]), question_bank_hash=bank["question_bank_hash"])
    save_manifest(root, manifest)
    _emit({"state": manifest["state"], "questions": len(bank["questions"]), "warnings": bank["warnings"]})


def cmd_import_crawl(args):
    root, manifest = require_run(args.run_dir)
    if not manifest["paths"].get("questions"):
        raise ContractError("Import questions before importing crawl data")
    bank = read_json(root / manifest["paths"]["questions"])
    crawl = import_crawl(read_json(args.crawl), bank, Path(args.crawl).expanduser().resolve())
    write_json(root / "canonical/crawl.json", crawl)
    _copy_source(args.crawl, root / "input/crawl.source.json")
    manifest["paths"]["crawl"] = "canonical/crawl.json"
    manifest["state"] = "CRAWL_IMPORTED"
    record_event(manifest, "crawl_imported", **crawl["counts"])
    save_manifest(root, manifest)
    _emit({"state": manifest["state"], "counts": crawl["counts"], "issues": crawl["issues"]})


def cmd_prepare(args):
    root, manifest = require_run(args.run_dir)
    if not manifest["paths"].get("questions") or not manifest["paths"].get("crawl"):
        raise ContractError("Import questions and crawl data before prepare")
    config = read_json(root / manifest["paths"]["config"])
    bank = read_json(root / manifest["paths"]["questions"])
    crawl = read_json(root / manifest["paths"]["crawl"])
    answers_path = root / "canonical/answers.json"
    if answers_path.exists():
        answers_doc = read_json(answers_path)
    else:
        answers_doc = prepare_answers(root, config, bank, crawl)
        write_json(answers_path, answers_doc)
        manifest["paths"]["answers"] = "canonical/answers.json"
    tasks = create_prepare_tasks(root, manifest, config, answers_doc)
    manifest["state"] = "WAITING_BLOCKING_SEMANTICS" if pending_tasks(root, manifest) else "PREPARED"
    record_event(manifest, "answers_prepared", answer_count=len(answers_doc["answers"]), task_count=len(tasks))
    save_manifest(root, manifest)
    _emit({
        "state": manifest["state"],
        "answers": len(answers_doc["answers"]),
        "created_tasks": [task["task_id"] for task in tasks],
        "next_tasks": [task["task_id"] for task in pending_tasks(root, manifest)],
    })


def cmd_next_task(args):
    root, manifest = require_run(args.run_dir)
    tasks = pending_tasks(root, manifest)
    if not tasks:
        _emit({"state": manifest["state"], "task": None})
        return
    task = tasks[0]
    _emit({
        "state": "WAITING_AGENT",
        "task_id": task["task_id"],
        "kind": task["kind"],
        "blocking": task["blocking"],
        "task_path": str(root / manifest["tasks"][task["task_id"]]["path"]),
        "suggested_result_path": str(root / "results" / f"{task['task_id']}.inbox.json"),
        "task": task if args.inline else None,
    })


def cmd_submit_task(args):
    root, manifest = require_run(args.run_dir)
    receipt = submit_task(root, manifest, args.task_id, args.result)
    _, refreshed = require_run(args.run_dir)
    _emit({"receipt": receipt, "next_tasks": [task["task_id"] for task in pending_tasks(root, refreshed)]})


def cmd_compute(args):
    root, manifest = require_run(args.run_dir)
    preparation_pending = [task_id for task_id, meta in manifest.get("tasks", {}).items() if meta["status"] == "pending"]
    if preparation_pending:
        raise ContractError("Semantic preparation tasks remain pending: " + ", ".join(preparation_pending))
    config = read_json(root / manifest["paths"]["config"])
    bank = read_json(root / manifest["paths"]["questions"])
    answers_doc = read_json(root / manifest["paths"]["answers"])
    metrics = compute_metrics(config, bank, answers_doc)
    write_json(root / "artifacts/metrics.json", metrics)
    manifest["paths"]["metrics"] = "artifacts/metrics.json"
    manifest["state"] = "AGGREGATED"
    record_event(manifest, "metrics_computed", metrics_hash=metrics["metrics_hash"])
    save_manifest(root, manifest)
    _emit({
        "state": manifest["state"],
        "coverage": metrics["coverage"],
        "unresolved_sentiment_answer_ids": metrics["sentiment"]["unresolved_answer_ids"],
        "action_directions": metrics["action_directions"],
    })


def cmd_prepare_report_tasks(args):
    root, manifest = require_run(args.run_dir)
    if not manifest["paths"].get("metrics"):
        raise ContractError("Compute metrics before preparing report tasks")
    config = read_json(root / manifest["paths"]["config"])
    answers_doc = read_json(root / manifest["paths"]["answers"])
    metrics = read_json(root / manifest["paths"]["metrics"])
    created = prepare_report_tasks(root, manifest, config, answers_doc, metrics)
    manifest["state"] = "WAITING_REPORT_TASKS" if pending_tasks(root, manifest) else "READY_TO_FINALIZE"
    record_event(manifest, "report_tasks_prepared", created_count=len(created))
    save_manifest(root, manifest)
    _emit({
        "state": manifest["state"],
        "created_tasks": [task["task_id"] for task in created],
        "next_tasks": [task["task_id"] for task in pending_tasks(root, manifest)],
    })


def cmd_finalize(args):
    root, manifest = require_run(args.run_dir)
    if not manifest["paths"].get("metrics"):
        raise ContractError("Compute metrics before finalize")
    config = read_json(root / manifest["paths"]["config"])
    bank = read_json(root / manifest["paths"]["questions"])
    answers_doc = read_json(root / manifest["paths"]["answers"])
    metrics = read_json(root / manifest["paths"]["metrics"])
    report, audit = finalize_report(root, manifest, config, bank, answers_doc, metrics)
    _emit({
        "state": "COMPLETE",
        "report_path": str(root / "artifacts/report-data.json"),
        "audit_path": str(root / "artifacts/audit.json"),
        "report_hash": report["artifact_hash"],
        "publishable": report["publish_check"]["publishable"],
    })


def cmd_status(args):
    root, manifest = require_run(args.run_dir)
    counts = {}
    for meta in manifest.get("tasks", {}).values():
        key = f"{meta['kind']}:{meta['status']}"
        counts[key] = counts.get(key, 0) + 1
    ready = pending_tasks(root, manifest)
    _emit({
        "run_id": manifest["run_id"],
        "state": manifest["state"],
        "paths": manifest["paths"],
        "task_counts": counts,
        "next_task_ids": [task["task_id"] for task in ready],
    })


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="geo_presales",
        description="Deterministic overseas GEO presales report core for Codex and Claude Code.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create-run", help="Validate and freeze one report configuration")
    create.add_argument("--config", required=True)
    create.add_argument("--run-dir", required=True)
    create.set_defaults(func=cmd_create_run)

    questions = sub.add_parser("import-questions", help="Validate and import a fixed question bank")
    questions.add_argument("--run-dir", required=True)
    questions.add_argument("--questions", required=True)
    questions.set_defaults(func=cmd_import_questions)

    crawl = sub.add_parser("import-crawl", help="Import ChatGPT crawler batch or raw results")
    crawl.add_argument("--run-dir", required=True)
    crawl.add_argument("--crawl", required=True)
    crawl.set_defaults(func=cmd_import_crawl)

    prepare = sub.add_parser("prepare", help="Run deterministic extraction and emit semantic tasks")
    prepare.add_argument("--run-dir", required=True)
    prepare.set_defaults(func=cmd_prepare)

    next_task = sub.add_parser("next-task", help="Return the next ready semantic task")
    next_task.add_argument("--run-dir", required=True)
    next_task.add_argument("--inline", action="store_true")
    next_task.set_defaults(func=cmd_next_task)

    submit = sub.add_parser("submit-task", help="Validate and accept one Agent-produced result JSON")
    submit.add_argument("--run-dir", required=True)
    submit.add_argument("--task-id", required=True)
    submit.add_argument("--result", required=True)
    submit.set_defaults(func=cmd_submit_task)

    compute = sub.add_parser("compute", help="Compute metrics, buckets, benchmarks, and action states")
    compute.add_argument("--run-dir", required=True)
    compute.set_defaults(func=cmd_compute)

    report_tasks = sub.add_parser("prepare-report-tasks", help="Emit theme, module, and action-writing tasks")
    report_tasks.add_argument("--run-dir", required=True)
    report_tasks.set_defaults(func=cmd_prepare_report_tasks)

    finalize = sub.add_parser("finalize", help="Run publish checks and build report/audit artifacts")
    finalize.add_argument("--run-dir", required=True)
    finalize.set_defaults(func=cmd_finalize)

    status = sub.add_parser("status", help="Show run state and ready tasks")
    status.add_argument("--run-dir", required=True)
    status.set_defaults(func=cmd_status)
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
        return 0
    except (ContractError, FileNotFoundError, json.JSONDecodeError, KeyError) as error:
        _emit({"error": type(error).__name__, "message": str(error)})
        return 2
