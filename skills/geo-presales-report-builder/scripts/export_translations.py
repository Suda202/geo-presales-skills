"""导出待翻译的回答原文，供翻译后回填中文译文。

采集数据本身不含译文，译文需要单独一轮翻译。本脚本把每条回答的
**markdown 原文**（不是渲染后的 HTML）按批次导出，翻译后再由
`attach_translations.py` 回填。

用法：
    python3 export_translations.py --collect <采集目录> --case <Case.json> \
        --regions MY,SG --batch-size 40 --out-dir <输出>/translation-batches
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

TEXT_FIELD = {"overview": "content"}
PLATFORM_LABELS = {"overview": "AIO", "gemini": "Gemini",
                   "chatgpt": "ChatGPT", "perplexity": "Perplexity"}
# 与 details 的键保持同序，回填时才能对上
PLATFORM_ORDER = ["overview", "gemini", "chatgpt", "perplexity"]


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="导出待翻译的回答原文")
    parser.add_argument("--collect", type=Path, required=True)
    parser.add_argument("--regions", default="MY,SG")
    parser.add_argument("--batch-size", type=int, default=40)
    parser.add_argument("--max-chars", type=int, default=4000,
                        help="单条回答截断长度，与数据层保持一致")
    parser.add_argument("--out-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    regions = [r.strip() for r in args.regions.split(",") if r.strip()]

    entries = []
    for platform_dir in PLATFORM_ORDER:
        for market in regions:
            folder = args.collect / f"scraper.{platform_dir}" / market
            if not folder.is_dir():
                continue
            for path in sorted(folder.glob("*.json")):
                result = json.loads(path.read_text(encoding="utf-8")).get("task_result") or {}
                answer = str(result.get(TEXT_FIELD.get(platform_dir, "result_text")) or "").strip()
                if not answer:
                    continue
                entries.append({
                    "key": f"{market}|{PLATFORM_LABELS[platform_dir]}|{path.stem}",
                    "answer": answer[:args.max_chars],
                })

    args.out_dir.mkdir(parents=True, exist_ok=True)
    batches = [entries[i:i + args.batch_size] for i in range(0, len(entries), args.batch_size)]
    for index, batch in enumerate(batches, 1):
        path = args.out_dir / f"batch-{index:02d}.json"
        path.write_text(json.dumps(batch, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    total = sum(len(item["answer"]) for item in entries)
    print(f"待翻译 {len(entries)} 条，共 {total} 字符，拆成 {len(batches)} 批 -> {args.out_dir}")
    print("每批翻译后写成 batch-NN-zh.json，格式 {\"<key>\": \"<中文 markdown>\"}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
