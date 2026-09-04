#!/usr/bin/env python3
"""Prepare, validate, and safely patch GEO structured-result JSON files.

This tool intentionally does not discover brands or judge natural-language
sentiment. Those remain reviewed semantic decisions. It makes the brittle
parts deterministic: citation removal, schema checks, rank validation,
multi-value question-type routing, diff reporting, and atomic output.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable

try:
    from bs4 import BeautifulSoup
except ImportError as exc:  # pragma: no cover - environment-specific failure
    raise SystemExit(
        "缺少 BeautifulSoup4；请使用工作区依赖运行时或隔离环境安装后重试。"
    ) from exc


ALLOWED_SENTIMENTS = {"positive", "neutral", "negative"}
ALLOWED_PATCH_FIELDS = {"wordid", "platform", "brand_rankings"}
REQUIRED_ROW_FIELDS = {"wordid", "platform", "sentiment", "brand_rankings"}
ALLOWED_QUESTION_TYPES = {"visibility", "sentiment"}
QUESTION_TYPE_METRIC_SCOPES = {
    "visibility": ("visibility", "citation"),
    "sentiment": ("sentiment",),
}
KNOWN_DIAGNOSTIC_METRIC_SCOPES = {
    "discovery": (),
    "competitor": ("comparison",),
    "validation": ("attribute_validation",),
    "accuracy": ("accuracy",),
    "sentiment": (),
    "market_perception": ("market_perception",),
}
PRODUCT_CARD_SELECTORS = (
    '[data-testid*="product-card"]',
    '[data-testid^="shopping-product-metadata-"]',
    '[data-component*="product-card"]',
    '[class*="product-card"]',
    '[class*="product_card"]',
)


class AuditValidationError(ValueError):
    """Raised when a structured-result contract is violated."""


def read_json(path: Path) -> Any:
    try:
        with path.open(encoding="utf-8") as source:
            return json.load(source)
    except FileNotFoundError as exc:
        raise AuditValidationError(f"文件不存在：{path}") from exc
    except json.JSONDecodeError as exc:
        raise AuditValidationError(f"不是有效 JSON：{path}：{exc}") from exc


def write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_path = tempfile.mkstemp(
        prefix=f".{path.stem}-", suffix=".json", dir=path.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as target:
            json.dump(payload, target, ensure_ascii=False, indent=2)
            target.write("\n")
        os.replace(temporary_path, path)
    finally:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)


def parse_wordids(spec: str | None) -> set[int] | None:
    if spec is None:
        return None
    result: set[int] = set()
    for raw_part in spec.split(","):
        part = raw_part.strip()
        if not part:
            continue
        if re.fullmatch(r"\d+", part):
            result.add(int(part))
            continue
        match = re.fullmatch(r"(\d+)\s*-\s*(\d+)", part)
        if not match:
            raise AuditValidationError(f"无法解析记录号范围：{part}")
        start, end = map(int, match.groups())
        if end < start:
            raise AuditValidationError(f"记录号范围倒序：{part}")
        result.update(range(start, end + 1))
    return result


def remove_citations(answer_html: str) -> tuple[str, list[str]]:
    """Return body text after removing citation UI and citation anchors.

    Product-card anchors are unwrapped rather than deleted because their visible
    title is answer content, not a citation source label.
    """

    soup = BeautifulSoup(answer_html or "", "html.parser")
    removed: list[str] = []

    citation_nodes = list(soup.select('[data-testid="webpage-citation-pill"]'))
    for node in citation_nodes:
        text = " ".join(node.get_text(" ", strip=True).split())
        if text:
            removed.append(text)
        node.decompose()

    # Gemini renders source names in non-anchor UI containers. They are citation
    # chrome, not answer-body brand mentions, and must be removed before ranking.
    for node in list(
        soup.select(
            ".source-inline-chip-container, sources-carousel-inline, source-inline-chip"
        )
    ):
        text = " ".join(node.get_text(" ", strip=True).split())
        if text:
            removed.append(text)
        node.decompose()

    product_card_anchors: set[int] = set()
    for selector in PRODUCT_CARD_SELECTORS:
        for container in soup.select(selector):
            product_card_anchors.update(id(anchor) for anchor in container.find_all("a"))

    for anchor in list(soup.find_all("a")):
        if id(anchor) in product_card_anchors:
            anchor.unwrap()
            continue
        text = " ".join(anchor.get_text(" ", strip=True).split())
        if text:
            removed.append(text)
        anchor.decompose()

    cleaned = " ".join(soup.get_text(" ", strip=True).split())
    return cleaned, removed


def normalized_name(value: str) -> str:
    return " ".join(value.split()).casefold()


def row_key(row: dict[str, Any]) -> tuple[str, int]:
    return str(row["platform"]), row["wordid"]


def row_label(row: dict[str, Any]) -> str:
    platform, wordid = row_key(row)
    return f"{platform} / wordid {wordid}"


def normalized_string_set(value: Any, field_name: str) -> tuple[str, ...]:
    """Normalize a current scalar or future multi-value field without duplicates."""

    if value is None:
        return ()
    raw_values = value.split(",") if isinstance(value, str) else value
    if not isinstance(raw_values, list) or not all(isinstance(item, str) for item in raw_values):
        raise AuditValidationError(f"{field_name} 必须是字符串或字符串数组")
    normalized: list[str] = []
    for item in raw_values:
        candidate = item.strip().casefold()
        if not candidate:
            raise AuditValidationError(f"{field_name} 不能包含空标签")
        if candidate not in normalized:
            normalized.append(candidate)
    return tuple(normalized)


def question_types_from_row(row: dict[str, Any]) -> tuple[str, ...]:
    plural = row.get("question_types")
    singular = row.get("question_type")
    # Legacy exports use Chinese display labels in question_type. When a
    # machine-readable question_types field is present, the display label is
    # descriptive only and must not override routing.
    if plural is not None and isinstance(singular, str) and singular.strip().casefold() not in ALLOWED_QUESTION_TYPES:
        singular = None
    if plural is None and isinstance(singular, str) and singular.strip().casefold() not in ALLOWED_QUESTION_TYPES:
        singular = None
    if plural is not None and singular is not None:
        plural_types = normalized_string_set(plural, "question_types")
        singular_types = normalized_string_set(singular, "question_type")
        if set(plural_types) != set(singular_types):
            raise AuditValidationError("question_type 与 question_types 冲突")
        result = plural_types
    else:
        result = normalized_string_set(
            plural if plural is not None else singular, "question_types"
        )
    unknown = set(result) - ALLOWED_QUESTION_TYPES
    if unknown:
        raise AuditValidationError(f"未知问题类型：{sorted(unknown)}")
    return result


def diagnostic_intents_from_row(row: dict[str, Any]) -> tuple[str, ...]:
    plural = row.get("diagnostic_intents")
    singular = row.get("diagnostic_intent")
    if plural is not None and singular is not None:
        plural_tags = normalized_string_set(plural, "diagnostic_intents")
        singular_tags = normalized_string_set(singular, "diagnostic_intent")
        if set(plural_tags) != set(singular_tags):
            raise AuditValidationError("diagnostic_intent 与 diagnostic_intents 冲突")
        return plural_tags
    return normalized_string_set(
        plural if plural is not None else singular, "diagnostic_intents"
    )


def metric_scopes_for_dimensions(
    question_types: Any, diagnostic_intents: Any = None
) -> tuple[str, ...]:
    types = normalized_string_set(question_types, "question_types")
    unknown_types = set(types) - ALLOWED_QUESTION_TYPES
    if unknown_types:
        raise AuditValidationError(f"未知问题类型：{sorted(unknown_types)}")
    intents = normalized_string_set(diagnostic_intents, "diagnostic_intents")
    scopes: list[str] = []
    for item in types:
        scopes.extend(QUESTION_TYPE_METRIC_SCOPES[item])
    for intent in intents:
        scopes.extend(KNOWN_DIAGNOSTIC_METRIC_SCOPES.get(intent, ()))
    return tuple(dict.fromkeys(scopes))


def validate_metric_scopes(
    question_types: Any, diagnostic_intents: Any, metric_scopes: Any
) -> tuple[str, ...]:
    if not isinstance(metric_scopes, list) or not all(
        isinstance(scope, str) and scope.strip() for scope in metric_scopes
    ):
        raise AuditValidationError("metric_scopes 必须是非空字符串数组")
    actual = tuple(scope.strip().casefold() for scope in metric_scopes)
    if len(actual) != len(set(actual)):
        raise AuditValidationError("metric_scopes 不能包含重复值")
    required = metric_scopes_for_dimensions(question_types, diagnostic_intents)
    missing = set(required) - set(actual)
    if missing:
        raise AuditValidationError(
            f"诊断范围缺失：问题类型和已知诊断标签至少需要 {list(required)}，实际为 {metric_scopes!r}"
        )
    return actual


def validate_brand_rankings(wordid: int, rankings: Any) -> None:
    if not isinstance(rankings, list):
        raise AuditValidationError(f"wordid {wordid} 的 brand_rankings 必须是数组")
    names: list[str] = []
    ranks: list[int] = []
    for index, item in enumerate(rankings):
        if not isinstance(item, dict) or set(item) != {"brand_name", "rank_pos"}:
            raise AuditValidationError(
                f"wordid {wordid} 的第 {index + 1} 个品牌必须只含 brand_name/rank_pos"
            )
        name = item["brand_name"]
        rank = item["rank_pos"]
        if not isinstance(name, str) or not name.strip():
            raise AuditValidationError(f"wordid {wordid} 存在空品牌名")
        if not isinstance(rank, int) or isinstance(rank, bool):
            raise AuditValidationError(f"wordid {wordid} 的 rank_pos 必须是整数")
        names.append(normalized_name(name))
        ranks.append(rank)
    if len(names) != len(set(names)):
        raise AuditValidationError(f"wordid {wordid} 同一品牌重复出现")
    if ranks != list(range(1, len(rankings) + 1)):
        raise AuditValidationError(f"wordid {wordid} 的排名不从 1 连续：{ranks}")


def validate_payload(
    payload: Any,
    *,
    sentiment_wordids: set[int] | None = None,
    require_question_types: bool = False,
) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise AuditValidationError("JSON 顶层必须是对象")
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise AuditValidationError("JSON 顶层 rows 必须是数组")

    seen: set[tuple[str, int]] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise AuditValidationError(f"第 {index + 1} 条记录必须是对象")
        missing = REQUIRED_ROW_FIELDS - set(row)
        if missing:
            raise AuditValidationError(
                f"第 {index + 1} 条记录缺少字段：{sorted(missing)}"
            )
        wordid = row["wordid"]
        if not isinstance(wordid, int) or isinstance(wordid, bool):
            raise AuditValidationError(f"第 {index + 1} 条记录 wordid 必须是整数")
        platform = row["platform"]
        if not isinstance(platform, str) or not platform.strip():
            raise AuditValidationError(f"wordid {wordid} 的 platform 必须是非空字符串")
        identity = row_key(row)
        if identity in seen:
            raise AuditValidationError(f"记录键重复：{row_label(row)}")
        seen.add(identity)
        if row.get("answer_text") is not None and not isinstance(row.get("answer_text"), str):
            raise AuditValidationError(f"wordid {wordid} 的 answer_text 必须是字符串或 null")
        sentiment = row["sentiment"]
        if sentiment not in ALLOWED_SENTIMENTS:
            raise AuditValidationError(f"wordid {wordid} 的 sentiment 非法：{sentiment!r}")
        validate_brand_rankings(wordid, row["brand_rankings"])

        question_types = question_types_from_row(row)
        if not question_types and sentiment_wordids is not None:
            question_types = (
                ("sentiment",) if wordid in sentiment_wordids else ("visibility",)
            )
        if require_question_types and not question_types:
            raise AuditValidationError(
                f"wordid {wordid} 缺少问题类型；请提供 question_type(s)"
            )
        diagnostic_intents = diagnostic_intents_from_row(row)
        metric_scopes = row.get("metric_scopes")
        if metric_scopes is not None:
            validate_metric_scopes(question_types, diagnostic_intents, metric_scopes)

    if sentiment_wordids is not None:
        seen_wordids = {wordid for _, wordid in seen}
        unknown = sentiment_wordids - seen_wordids
        if unknown:
            raise AuditValidationError(f"情绪问题记录号不在输入中：{sorted(unknown)}")
    return rows


def build_review_bundle(payload: dict[str, Any], target_brand: str | None) -> dict[str, Any]:
    rows = validate_payload(payload)
    review_rows = []
    for row in rows:
        answer_text = row.get("answer_text")
        has_answer_text = isinstance(answer_text, str) and bool(answer_text.strip())
        cleaned_text, removed_link_texts = remove_citations(answer_text or "")
        review_rows.append(
            {
                "wordid": row["wordid"],
                "platform": row["platform"],
                "diagnostic_intents": list(diagnostic_intents_from_row(row)),
                "metric_scopes": row.get("metric_scopes"),
                "question_types": list(question_types_from_row(row)),
                "semantic_review_available": has_answer_text,
                "cleaned_text": cleaned_text,
                "removed_link_texts": removed_link_texts,
                "current_brand_rankings": copy.deepcopy(row["brand_rankings"]),
                "review": {
                    "candidate_entities": [],
                    "proposed_brand_rankings": None,
                    "included_entities": [],
                    "excluded_entities": [],
                    "uncertainties": [],
                },
            }
        )
    return {
        "source_version": payload.get("version"),
        "task_id": payload.get("task_id"),
        "target_brand": target_brand,
        "rules": {
            "ranking": "first_eligible_brand_mention_after_citation_removal",
            "visibility": "question_types_contains_visibility",
            "citation": "question_types_contains_visibility",
            "comparison": "diagnostic_intents_contains_competitor",
            "attribute_validation": "diagnostic_intents_contains_validation",
            "accuracy": "official_truth_vs_answer_claim",
            "diagnostic_intents": "open_multi_value_tags_with_six_legacy_values",
        },
        "rows": review_rows,
    }


def compare_payloads(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    before_rows = validate_payload(before)
    after_rows = validate_payload(after)
    if set(before) != set(after):
        raise AuditValidationError("顶层字段集合发生变化")
    for key in before:
        if key != "rows" and before[key] != after[key]:
            raise AuditValidationError(f"非目标顶层字段发生变化：{key}")

    before_by_id = {row_key(row): row for row in before_rows}
    after_by_id = {row_key(row): row for row in after_rows}
    if set(before_by_id) != set(after_by_id):
        raise AuditValidationError("输入输出 platform + wordid 记录集合不一致")

    changes: list[dict[str, Any]] = []
    for identity in sorted(before_by_id):
        old = before_by_id[identity]
        new = after_by_id[identity]
        platform, wordid = identity
        if set(old) != set(new):
            raise AuditValidationError(f"wordid {wordid} 的字段集合发生变化")
        for key in old:
            if key != "brand_rankings" and old[key] != new[key]:
                raise AuditValidationError(f"wordid {wordid} 的非目标字段发生变化：{key}")
        for field in ("brand_rankings",):
            if old[field] != new[field]:
                changes.append(
                    {
                        "platform": platform,
                        "wordid": wordid,
                        "field": field,
                        "before": old[field],
                        "after": new[field],
                    }
                )
    return changes


def apply_reviewed_patch(
    payload: dict[str, Any], patch_payload: Any
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = validate_payload(payload)
    if not isinstance(patch_payload, dict) or not isinstance(patch_payload.get("rows"), list):
        raise AuditValidationError("补丁必须是含 rows 数组的 JSON 对象")

    result = copy.deepcopy(payload)
    result_by_key = {row_key(row): row for row in result["rows"]}
    platforms_by_wordid: dict[int, set[str]] = {}
    for row in result["rows"]:
        platforms_by_wordid.setdefault(row["wordid"], set()).add(row["platform"])
    seen_patch_ids: set[tuple[str, int]] = set()
    for item in patch_payload["rows"]:
        if not isinstance(item, dict):
            raise AuditValidationError("补丁 rows 中每项必须是对象")
        extra = set(item) - ALLOWED_PATCH_FIELDS
        target_fields = set(item) & {"brand_rankings"}
        if extra or "wordid" not in item or not target_fields:
            raise AuditValidationError(
                f"补丁项只允许 platform/wordid/brand_rankings，且必须修改 brand_rankings：{item}"
            )
        wordid = item["wordid"]
        platform = item.get("platform")
        available_platforms = platforms_by_wordid.get(wordid, set())
        if platform is None:
            if len(available_platforms) != 1:
                raise AuditValidationError(
                    f"补丁 wordid {wordid} 对应多个平台，必须显式提供 platform"
                )
            platform = next(iter(available_platforms))
        identity = (str(platform), wordid)
        if identity in seen_patch_ids:
            raise AuditValidationError(f"补丁记录键重复：{platform} / wordid {wordid}")
        seen_patch_ids.add(identity)
        if identity not in result_by_key:
            raise AuditValidationError(f"补丁 wordid 不在输入中：{wordid}")
        if "brand_rankings" in item:
            validate_brand_rankings(wordid, item["brand_rankings"])
            result_by_key[identity]["brand_rankings"] = copy.deepcopy(item["brand_rankings"])
    validate_payload(result)
    return result, compare_payloads(payload, result)


def alias_position(text: str, alias: str) -> int | None:
    """Find an alias without matching it inside a longer ASCII token."""

    candidate = alias.strip().casefold()
    if not candidate:
        return None
    prefix = r"(?<![a-z0-9])" if candidate[0].isascii() and candidate[0].isalnum() else ""
    suffix = r"(?![a-z0-9])" if candidate[-1].isascii() and candidate[-1].isalnum() else ""
    match = re.search(prefix + re.escape(candidate) + suffix, text.casefold())
    return match.start() if match else None


def earliest_alias_position(text: str, aliases: Iterable[str]) -> int | None:
    positions = [alias_position(text, alias) for alias in aliases]
    valid = [position for position in positions if position is not None]
    return min(valid) if valid else None


def rank_from_catalog(
    cleaned_text: str, entity_catalog: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Rank an already-reviewed batch catalog by first body occurrence."""

    found: list[tuple[int, int, str]] = []
    for order, entity in enumerate(entity_catalog):
        if not entity.get("eligible", False):
            continue
        canonical = entity.get("canonical_name")
        aliases = entity.get("aliases", [])
        if not isinstance(canonical, str) or not canonical.strip() or not isinstance(aliases, list):
            raise AuditValidationError(f"实体词典格式错误：{entity}")
        position = earliest_alias_position(cleaned_text, [canonical, *aliases])
        if position is not None:
            found.append((position, order, canonical.strip()))

    found.sort(key=lambda item: (item[0], item[1]))
    seen: set[str] = set()
    rankings: list[dict[str, Any]] = []
    for _, _, canonical in found:
        key = normalized_name(canonical)
        if key in seen:
            continue
        seen.add(key)
        rankings.append({"brand_name": canonical, "rank_pos": len(rankings) + 1})
    return rankings


def sentiment_from_review(question_types: Any, dominant_polarity: str) -> str:
    """Map reviewed polarity when the question-type set includes sentiment."""

    normalized_types = normalized_string_set(question_types, "question_types")
    unknown = set(normalized_types) - ALLOWED_QUESTION_TYPES
    if unknown:
        raise AuditValidationError(f"未知问题类型：{sorted(unknown)}")
    if "sentiment" not in normalized_types:
        raise AuditValidationError("问题类型不含 sentiment，不能生成情绪标签")
    polarity = dominant_polarity.strip().casefold()
    mapping = {
        "positive_dominant": "positive",
        "balanced_or_insufficient": "neutral",
        "negative_dominant": "negative",
    }
    if polarity not in mapping:
        raise AuditValidationError(f"未知主导情绪：{dominant_polarity}")
    return mapping[polarity]


def print_changes(changes: list[dict[str, Any]]) -> None:
    changed_records = {(change["platform"], change["wordid"]) for change in changes}
    print(f"actual_changed_record_count={len(changed_records)}")
    print(f"actual_field_change_count={len(changes)}")
    for change in changes:
        print(json.dumps(change, ensure_ascii=False, sort_keys=True))


def command_prepare(args: argparse.Namespace) -> None:
    payload = read_json(Path(args.input))
    target_brand = args.target_brand.strip() if args.target_brand else None
    if args.target_brand and not target_brand:
        raise AuditValidationError("--target-brand 不能为空")
    bundle = build_review_bundle(payload, target_brand)
    write_json_atomic(Path(args.output), bundle)
    print(f"prepared_rows={len(bundle['rows'])}")
    print(f"output={Path(args.output).resolve()}")


def command_validate(args: argparse.Namespace) -> None:
    payload = read_json(Path(args.input))
    rows = validate_payload(payload)
    print(f"valid_rows={len(rows)}")
    if args.before:
        before = read_json(Path(args.before))
        changes = compare_payloads(before, payload)
        print_changes(changes)


def command_apply(args: argparse.Namespace) -> None:
    input_path = Path(args.input)
    output_path = Path(args.output)
    payload = read_json(input_path)
    patch_payload = read_json(Path(args.patch))
    result, changes = apply_reviewed_patch(payload, patch_payload)
    validate_payload(result)
    if args.backup:
        backup_path = Path(args.backup)
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(input_path, backup_path)
        print(f"backup={backup_path.resolve()}")
    write_json_atomic(output_path, result)
    print(f"output={output_path.resolve()}")
    print_changes(changes)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="生成去引用正文审核包")
    prepare.add_argument("--input", required=True)
    prepare.add_argument("--output", required=True)
    prepare.add_argument(
        "--target-brand",
        help="品牌审核的目标品牌；写入审核包，避免靠正文或现有排名猜测",
    )
    prepare.set_defaults(handler=command_prepare)

    validate = subparsers.add_parser("validate", help="校验 JSON 及可选前后差异")
    validate.add_argument("--input", required=True)
    validate.add_argument("--before")
    validate.set_defaults(handler=command_validate)

    apply_parser = subparsers.add_parser("apply", help="安全应用人工审核补丁")
    apply_parser.add_argument("--input", required=True)
    apply_parser.add_argument("--patch", required=True)
    apply_parser.add_argument("--output", required=True)
    apply_parser.add_argument("--backup")
    apply_parser.set_defaults(handler=command_apply)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.handler(args)
    except AuditValidationError as exc:
        print(f"校验失败：{exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
