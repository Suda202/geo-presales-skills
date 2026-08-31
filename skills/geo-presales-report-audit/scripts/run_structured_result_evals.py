#!/usr/bin/env python3
"""Execute structured-result golden fixtures against the deterministic helpers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from structured_result_audit import (
    rank_from_catalog,
    remove_citations,
    sentiment_from_review,
)


def load_cases(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as source:
        payload = json.load(source)
    if not isinstance(payload, dict):
        raise ValueError("fixture 顶层必须是对象")
    return payload


def check_equal(name: str, actual: Any, expected: Any) -> str | None:
    if actual == expected:
        return None
    return f"{name}: expected={expected!r}, actual={actual!r}"


def run_cases(payload: dict[str, Any]) -> list[str]:
    failures: list[str] = []

    for case in payload.get("citation_cases", []):
        cleaned, removed = remove_citations(case["input_html"])
        for suffix, actual, expected in (
            ("cleaned", cleaned, case["expected_cleaned"]),
            ("removed", removed, case["expected_removed"]),
        ):
            failure = check_equal(f"{case['name']}[{suffix}]", actual, expected)
            if failure:
                failures.append(failure)

    for case in payload.get("ranking_cases", []):
        actual = rank_from_catalog(case["cleaned_text"], case["entity_catalog"])
        failure = check_equal(case["name"], actual, case["expected"])
        if failure:
            failures.append(failure)

    for case in payload.get("sentiment_cases", []):
        actual = sentiment_from_review(
            case["question_types"], case["dominant_polarity"]
        )
        failure = check_equal(case["name"], actual, case["expected"])
        if failure:
            failures.append(failure)

    return failures


def count_cases(payload: dict[str, Any]) -> int:
    return sum(len(payload.get(key, [])) for key in (
        "citation_cases", "ranking_cases", "sentiment_cases"
    ))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixtures",
        default=str(
            Path(__file__).resolve().parents[1]
            / "evals"
            / "fixtures"
            / "structured_result_cases.json"
        ),
    )
    args = parser.parse_args()
    try:
        payload = load_cases(Path(args.fixtures))
        failures = run_cases(payload)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"fixture_error={exc}", file=sys.stderr)
        return 2

    total = count_cases(payload)
    print(f"structured_result_cases={total}")
    print(f"passed={total - len(failures)}")
    print(f"failed={len(failures)}")
    for failure in failures:
        print(f"FAIL {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
