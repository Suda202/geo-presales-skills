#!/usr/bin/env python3
"""Validate one or more GEO presales evaluation Case tables in Markdown."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse

CASE_RE = re.compile(
    r"^##\s+(?:\d+\.\s+)?[^\n]+\n[ \t]*\n"
    r"(?P<body>\|\s*字段\s*\|\s*填写内容\s*\|\n\|\s*-+\s*\|\s*-+\s*\|.*?)(?=^##\s+|\Z)",
    re.MULTILINE | re.DOTALL,
)
ROW_RE = re.compile(r"^\|\s*([^|]+?)\s*\|\s*(.*?)\s*\|$")
HAN_RE = re.compile(r"[\u4e00-\u9fff]")
TOPIC_QUESTION_RE = re.compile(
    r"(?:[?？]$|^(?:what|which|who|where|when|why|how)\b|^(?:什么|哪些|哪种|如何|怎么|为什么|是否))",
    re.IGNORECASE,
)
TOPIC_RANKING_RE = re.compile(r"(?:\bbest\b|\btop\b|最佳|最好)", re.IGNORECASE)

SINGLE_REQUIRED = {
    "品牌名称",
    "业务模式",
    "品类",
    "适用边界",
    "官方域名",
}
OPTIONAL_SINGLE = {"公司名", "业务 / 产品名称", "补充内容"}
MULTI_VALUE_FIELDS = {"目标客户", "痛点", "使用场景", "产品特性", "差异化优势", "主题"}
MULTI_VALUE_RANGES = {
    "目标客户": (1, 5),
    "痛点": (2, 5),
    "使用场景": (2, 5),
    "产品特性": (2, 5),
    "差异化优势": (1, 5),
    "主题": (2, 2),
}
ENGLISH_FIELDS = {"公司名", "业务 / 产品名称", "品牌名称"}
MODES = {"B2B", "B2C", "B2B / B2C"}


def parse_rows(body: str) -> list[tuple[str, str]]:
    rows = []
    for line in body.splitlines():
        match = ROW_RE.fullmatch(line)
        if not match:
            continue
        key, value = (part.strip() for part in match.groups())
        if key in {"字段", "---"}:
            continue
        rows.append((key, value))
    return rows


def valid_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def validate_case(index: int, body: str) -> list[str]:
    errors: list[str] = []
    if "| 字段 | 填写内容 |" not in body or "|---|---|" not in body:
        errors.append("必须使用‘字段 / 填写内容’两列表")
    if "英文输入" in body or "中文翻译/说明" in body:
        errors.append("不得保留中英文镜像列")

    rows = parse_rows(body)
    keys = [key for key, _ in rows]
    values = dict(rows)
    for key in SINGLE_REQUIRED:
        if keys.count(key) != 1 or not values.get(key):
            errors.append(f"缺少或重复必填字段：{key}")
    for key in OPTIONAL_SINGLE:
        if keys.count(key) > 1:
            errors.append(f"选填字段重复：{key}")

    mode = values.get("业务模式")
    if mode and mode not in MODES:
        errors.append("业务模式只允许 B2B，B2C，B2B / B2C")
    if mode in {"B2B", "B2B / B2C"} and (keys.count("垂直行业") != 1 or not values.get("垂直行业")):
        errors.append("B2B Case 必须填写垂直行业")
    if mode == "B2C" and keys.count("垂直行业") > 0:
        errors.append("纯 B2C Case 的垂直行业必须留空；Markdown 中应省略该行")

    for field in MULTI_VALUE_FIELDS:
        if keys.count(field) != 1 or not values.get(field):
            errors.append(f"缺少或重复多值字段：{field}；应合并为一行并用‘，’分隔")
            continue
        if "、" in values[field]:
            errors.append(f"{field}不得使用顿号‘、’；多个值统一用逗号‘，’分隔")
        items = [item.strip() for item in re.split(r"[，、]", values[field])]
        if any(not item for item in items):
            errors.append(f"{field}包含空值；多个值之间只能用逗号‘，’分隔")
        low, high = MULTI_VALUE_RANGES[field]
        if not low <= len(items) <= high:
            errors.append(f"{field}数量必须为 {low}–{high}，当前为 {len(items)}")

    target_customers = values.get("目标客户", "")
    if "——" in target_customers or "关注" in target_customers:
        errors.append("目标客户只写角色或人群，不写‘关注什么’；请将关注点归入痛点、使用场景、产品特性或主题")

    for key in keys:
        if re.fullmatch(r"(?:目标客户|痛点|使用场景|产品特性) [1-5]", key):
            errors.append(f"{key}必须合并到不带序号的同名字段，并用‘，’分隔")

    if keys.count("主题") != 1 or not values.get("主题"):
        errors.append("缺少或重复多值字段：主题；应合并为一行并用‘，’分隔")
    else:
        if re.search(r"（(?:宽泛|细分)）", values["主题"]):
            errors.append("主题只写名称，不得标注（宽泛）或（细分）")
        topics = [item.strip() for item in re.split(r"[，、]", values["主题"])]
        for topic in topics:
            if TOPIC_QUESTION_RE.search(topic):
                errors.append(f"主题必须是简洁名称，不得写成完整问题：{topic}")
            if TOPIC_RANKING_RE.search(topic):
                errors.append(f"主题不得包含 Best / Top 或同义排名词：{topic}")

    for key in keys:
        if re.fullmatch(r"主题 [123]（(?:宽泛|细分)）", key):
            errors.append(f"{key}必须合并到不带序号的主题字段，并用‘，’分隔")

    for i in range(1, 4):
        competitor = f"竞品 {i}"
        domain = f"竞品 {i} 官网域名"
        if keys.count(competitor) != 1 or not values.get(competitor):
            errors.append(f"缺少或重复必填字段：{competitor}")
        if keys.count(domain) != 1 or not values.get(domain):
            errors.append(f"缺少或重复必填字段：{domain}")

    for key, value in rows:
        if not value:
            errors.append(f"字段为空：{key}；选填字段无内容时应省略整行")
        if key in ENGLISH_FIELDS or re.fullmatch(r"竞品 [123]", key):
            if HAN_RE.search(value):
                errors.append(f"{key}必须使用英文规范名称")
        elif key not in {"业务模式", "官方域名"} and not re.fullmatch(r"竞品 [123] 官网域名", key):
            if not HAN_RE.search(value):
                errors.append(f"{key}必须使用中文描述")
        if "、" in value:
            errors.append(f"{key}不得使用顿号‘、’；字段值之间使用逗号‘，’")
        if key not in MULTI_VALUE_FIELDS and "，" in value and key not in {"公司名", "业务 / 产品名称", "品牌名称"}:
            errors.append(f"{key}包含逗号‘，’；只有多值字段可用逗号分隔，单个值请改用‘和’、‘或’或‘；’")

    for key in ["官方域名", "竞品 1 官网域名", "竞品 2 官网域名", "竞品 3 官网域名"]:
        value = values.get(key)
        if value and not valid_url(value):
            errors.append(f"{key}必须是 http 或 https URL")

    supplement = values.get("补充内容", "")
    if supplement and len(supplement) < 12:
        errors.append("补充内容过短；若没有其他字段无法承接的重要信息，应省略该行")

    return [f"Case {index}: {error}" for error in errors]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("markdown", help="Case Markdown 或完整评测集路径")
    args = parser.parse_args()
    path = Path(args.markdown)
    text = path.read_text(encoding="utf-8")
    cases = [match.group("body") for match in CASE_RE.finditer(text)]
    if not cases:
        raise SystemExit("未找到标题为 ‘## Brand’ 或兼容旧格式 ‘## 1. Brand’ 的 Case 两列表")

    errors = []
    for index, case in enumerate(cases, 1):
        errors.extend(validate_case(index, case))
    report = {"ok": not errors, "case_count": len(cases), "errors": errors}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if not errors else 2)


if __name__ == "__main__":
    main()
