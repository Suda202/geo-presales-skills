from __future__ import annotations

import shutil
from pathlib import Path

from . import RULESET_VERSION, SCHEMA_VERSION
from .util import ContractError, now_iso, read_json, sha256_obj, write_json


MANIFEST_NAME = "manifest.json"


def run_path(run_dir: str | Path) -> Path:
    return Path(run_dir).expanduser().resolve()


def manifest_path(run_dir: str | Path) -> Path:
    return run_path(run_dir) / MANIFEST_NAME


def require_run(run_dir: str | Path) -> tuple[Path, dict]:
    root = run_path(run_dir)
    path = root / MANIFEST_NAME
    if not path.exists():
        raise ContractError(f"Run manifest not found: {path}")
    return root, read_json(path)


def save_manifest(root: Path, manifest: dict) -> None:
    manifest["updated_at"] = now_iso()
    write_json(root / MANIFEST_NAME, manifest)


def create_run_dir(run_dir: str | Path, config: dict, source_config: str | Path) -> dict:
    root = run_path(run_dir)
    if root.exists() and any(root.iterdir()):
        raise ContractError(f"Run directory already exists and is not empty: {root}")
    root.mkdir(parents=True, exist_ok=True)
    for relative in (
        "input",
        "canonical",
        "evidence/answers",
        "tasks",
        "results",
        "artifacts/facts",
    ):
        (root / relative).mkdir(parents=True, exist_ok=True)
    write_json(root / "input/config.json", config)
    try:
        shutil.copy2(Path(source_config), root / "input/config.source.json")
    except shutil.SameFileError:
        pass
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "run_id": config["run_id"],
        "state": "CREATED",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "ruleset_version": RULESET_VERSION,
        "config_hash": sha256_obj(config),
        "paths": {
            "config": "input/config.json",
            "questions": None,
            "crawl": None,
            "answers": None,
            "metrics": None,
            "report": None,
        },
        "tasks": {},
        "events": [
            {"at": now_iso(), "event": "run_created", "config_hash": sha256_obj(config)}
        ],
    }
    save_manifest(root, manifest)
    return manifest


def record_event(manifest: dict, event: str, **fields) -> None:
    manifest.setdefault("events", []).append({"at": now_iso(), "event": event, **fields})

