#!/usr/bin/env python3
"""Create or validate a Bad Case draft without writing to Lark Base."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = [
    "Bad Case",
    "错误类型",
    "模块",
    "问题与影响",
    "复现证据",
    "建议",
    "状态",
    "优先级",
    "问题截图",
    "来源报告",
]

PLACEHOLDER = "【待填写】"
TASK_PATTERN = re.compile(r"Task\s+\d+", re.IGNORECASE)
RECORD_PATTERN = re.compile(r"#\d+")
ABSTRACT_TITLES = {
    "题目跑偏",
    "品牌提及存在问题",
    "问题生成错误",
    "情绪识别错误",
    "排名错误",
    "引用解析错误",
}


def read_json(path: str) -> dict[str, Any]:
    source = Path(path).expanduser().resolve()
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"找不到草稿：{source}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"草稿不是有效 JSON：{exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit("草稿顶层必须是 JSON 对象。")
    return data


def write_json(path: str, data: dict[str, Any]) -> None:
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已生成 Bad Case 草稿：{target}")


def is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip() or PLACEHOLDER in value
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def validate(data: dict[str, Any], allow_draft: bool) -> list[str]:
    errors: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"缺少字段：{field}")
        elif not allow_draft and is_empty(data[field]):
            errors.append(f"字段未填写：{field}")

    title = str(data.get("Bad Case", "")).strip()
    if title and not TASK_PATTERN.search(title):
        errors.append("Bad Case 标题缺少 Task 编号。")
    report_level = bool(data.get("报告级问题", False))
    if title and not report_level and not RECORD_PATTERN.search(title):
        errors.append("记录级 Bad Case 标题缺少 #记录编号。")
    if title in ABSTRACT_TITLES or len(title) < 18:
        errors.append("Bad Case 标题过于抽象；写清本来应该什么、实际变成什么。")

    details = str(data.get("问题与影响", ""))
    if details and PLACEHOLDER not in details:
        if "问题：" not in details:
            errors.append("问题与影响缺少‘问题：’段落。")
        if "影响：" not in details:
            errors.append("问题与影响缺少‘影响：’段落。")

    evidence = str(data.get("复现证据", ""))
    if evidence and PLACEHOLDER not in evidence:
        for marker in ("原题：", "实际：", "预期："):
            if marker not in evidence:
                errors.append(f"复现证据缺少‘{marker}’。")
        if not TASK_PATTERN.search(evidence):
            errors.append("复现证据缺少 Task 编号。")
        if not report_level and not RECORD_PATTERN.search(evidence):
            errors.append("记录级复现证据缺少 #记录编号。")

    screenshot = data.get("问题截图")
    if screenshot and not isinstance(screenshot, (str, list, dict)):
        errors.append("问题截图应为本地路径、附件数组或附件对象。")
    source_report = str(data.get("来源报告", "")).strip()
    if source_report and PLACEHOLDER not in source_report and not re.match(r"https?://", source_report):
        errors.append("来源报告必须是当前报告的 http/https 链接。")
    return errors


def command_new(args: argparse.Namespace) -> None:
    if args.record is None and not args.report_level:
        raise SystemExit("记录级 Case 必须提供 --record；报告级问题请加 --report-level。")
    prefix = f"Task {args.task}"
    if args.record is not None:
        prefix += f" #{args.record}"
    data: dict[str, Any] = {
        "Bad Case": f"{prefix}：{args.summary.strip()}",
        "错误类型": PLACEHOLDER,
        "模块": PLACEHOLDER,
        "问题与影响": "问题：【写明本来要评估什么，实际出现什么】\n影响：【写明哪个指标或客户判断会失真】",
        "复现证据": f"{prefix}\n原题：【粘贴关键原文】\n实际：【粘贴回答、结构化结果或页面数字】\n预期：【写明正确结果】",
        "建议": "【写成可实现、可用当前样本回归的规则】",
        "状态": PLACEHOLDER,
        "优先级": PLACEHOLDER,
        "问题截图": [],
        "来源报告": PLACEHOLDER,
        "报告级问题": bool(args.report_level),
    }
    write_json(args.output, data)


def command_validate(args: argparse.Namespace) -> None:
    data = read_json(args.input)
    errors = validate(data, args.allow_draft)
    if errors:
        print("Bad Case 草稿校验失败：")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("Bad Case 草稿结构校验通过。仍需人工复核语义、错误类型和截图标注。")


def main() -> None:
    parser = argparse.ArgumentParser(description="创建或校验 Bad Case 草稿；不会写入飞书。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    new_parser = subparsers.add_parser("new", help="创建字段齐全的草稿")
    new_parser.add_argument("--task", required=True, type=int, help="Task 编号")
    new_parser.add_argument("--record", type=int, help="记录编号，不带 #")
    new_parser.add_argument("--report-level", action="store_true", help="报告级问题，没有单条记录号")
    new_parser.add_argument("--summary", required=True, help="人话说明本来应该什么、实际变成什么")
    new_parser.add_argument("--output", required=True, help="输出 JSON 路径")
    new_parser.set_defaults(func=command_new)

    validate_parser = subparsers.add_parser("validate", help="校验现有草稿")
    validate_parser.add_argument("--input", required=True, help="草稿 JSON 路径")
    validate_parser.add_argument("--allow-draft", action="store_true", help="允许待填写占位符，只检查结构")
    validate_parser.set_defaults(func=command_validate)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
