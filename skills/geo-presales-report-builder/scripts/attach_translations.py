"""把翻译好的中文译文回填进 report-data.json 的抽屉明细。

用法：
    python3 attach_translations.py --report report-data.json \
        --batches <输出>/translation-batches --out report-data.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import importlib.util

SKILL_SCRIPTS = Path(__file__).resolve().parent


def load_markdown_converter():
    """复用数据层的 markdown 转换，保证原文与译文渲染口径一致。"""
    spec = importlib.util.spec_from_file_location(
        "build_report_data", SKILL_SCRIPTS / "build_report_data.py")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except SystemExit:  # 该模块入口不执行任何逻辑，这里只是取函数
        pass
    return module.markdown_to_html


def main() -> int:
    parser = argparse.ArgumentParser(description="回填中文译文")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--batches", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--allow-partial", action="store_true",
                        help="允许部分条目缺译文，缺的保持原文回退")
    args = parser.parse_args()

    markdown_to_html = load_markdown_converter()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    details = report.get("details") or {}
    if not details:
        raise SystemExit("report-data.json 里没有 details，无法回填译文")

    translated: dict[str, str] = {}
    for path in sorted(args.batches.glob("batch-*-zh.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise SystemExit(f"{path.name} 应为 {{\"<key>\": \"<中文>\"}} 映射")
        for key, value in payload.items():
            if not str(value).strip():
                continue
            if key in translated:
                raise SystemExit(f"键 {key} 在多个批次里重复出现")
            translated[key] = str(value)

    missing = [key for key in details if key not in translated]
    unknown = [key for key in translated if key not in details]
    if unknown:
        raise SystemExit(f"译文里有 {len(unknown)} 个键不在 details 中，例如 {unknown[:3]}")
    if missing and not args.allow_partial:
        raise SystemExit(f"还有 {len(missing)} 条没有译文，例如 {missing[:3]}；"
                         "确需部分交付请加 --allow-partial")

    filled = 0
    for key, value in translated.items():
        details[key]["answer_zh_html"] = markdown_to_html(value)
        filled += 1

    report["details"] = details
    meta = report.setdefault("meta", {})
    meta["translation_status"] = "complete" if not missing else f"partial ({len(missing)} missing)"
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    chars = sum(len(value) for value in translated.values())
    print(f"回填 {filled}/{len(details)} 条译文，译文源文本 {chars} 字符")
    if missing:
        print(f"未覆盖 {len(missing)} 条：{missing[:5]}")
    print(f"写出 {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
