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

    # 截断门禁(Bewinch 2026-09-17 校准):长回答译文/原文**纯文本**长度比
    # < 全批中位的 60% 即列疑似。必须剥标签后再比——比渲染 HTML 会被标记膨胀
    # 失真(引用 pill 每个 ~150 字符,原文有 pill、译文省略时比例被拉低,实测
    # 一次改动让误报从 2 涨到 17)。该信号召回可靠(实测 6 中 4 真,含只翻 16%、
    # 断尾+乱码、链接全丢),但纯散文的完整中译也会天然压到 ~0.3(英文词
    # ≈1.7 汉字),因此默认只警告,清单必须人工复核:对照原文核 URL 集合、
    # 数字锚点与末段是否语义对齐。机械化 URL/pill 比对已试过并否决——
    # 实测 155/379 条译文存在正常的链接省略,误报远高于截断本身。
    import re as _re
    def _text_len(html: str) -> int:
        return len(_re.sub(r"<[^>]+>", "", html or ""))
    ratios = {key: _text_len(details[key]["answer_zh_html"]) / _text_len(details[key]["answer_html"])
              for key in translated
              if details[key].get("answer_html") and _text_len(details[key]["answer_html"]) >= 1200}
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
                raise SystemExit("疑似截断（--strict-length），请逐条复核/重翻后重跑")
            print("  人工复核:对照原文核 URL 集合、数字锚点、末段语义对齐;纯散文低比例可为正常。重翻后重跑覆盖。")

    report["details"] = details
    meta = report.setdefault("meta", {})
    meta["translation_status"] = "complete" if not missing else f"partial ({len(missing)} missing)"
    # 无论有无疑似都要写：只在有疑似时写会让上一轮的清单残留在 meta 里
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
