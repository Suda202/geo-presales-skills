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
    parser.add_argument("--strict-length", action="store_true",
                        help="疑似截断从警告升级为报错")
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

    # 截断门禁：翻译代理截断长回答后键仍齐全，只有长度比能暴露
    # （Bewinch 案例：8 条 5-7.5K 字符回答被截到约 55-65%，正常条目
    # 译文/原文 HTML 长度比中位约 0.5，截断条目掉到 0.29 附近）。
    ratios = {key: len(details[key]["answer_zh_html"]) / len(details[key]["answer_html"])
              for key in translated
              if details[key].get("answer_html") and len(details[key]["answer_html"]) >= 1500}
    suspected = []
    if len(ratios) >= 10:
        median = sorted(ratios.values())[len(ratios) // 2]
        suspected = sorted((k for k, r in ratios.items() if r < median * 0.6),
                           key=lambda k: ratios[k])
        if suspected:
            print(f"⚠ {len(suspected)} 条译文疑似截断（长度比 < 全批中位 {median:.2f} 的 60%）：")
            for key in suspected[:10]:
                print(f"  {key}: ratio={ratios[key]:.2f}, 原文 {len(details[key]['answer_html'])} 字符")
            if args.strict_length:
                raise SystemExit("疑似截断（--strict-length），请重翻上述条目后重跑")
            print("  复核无误可忽略；重翻后重跑本命令覆盖。")

    report["details"] = details
    meta = report.setdefault("meta", {})
    meta["translation_status"] = "complete" if not missing else f"partial ({len(missing)} missing)"
    if suspected:
        meta["translation_length_suspects"] = suspected
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    chars = sum(len(value) for value in translated.values())
    print(f"回填 {filled}/{len(details)} 条译文，译文源文本 {chars} 字符")
    if missing:
        print(f"未覆盖 {len(missing)} 条：{missing[:5]}")
    print(f"写出 {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
