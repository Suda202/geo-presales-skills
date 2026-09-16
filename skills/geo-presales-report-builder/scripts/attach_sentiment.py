"""把句级情感判读结果接入 report-data.json 的情感板块。

流程：读分品牌判读标签 → 按报告切片（国家 / 平台 / 主题）统计正负句 → 写入每个切片的
sentiment 字段。正向率口径为 正向句 ÷（正向句 + 负向句），排除中性。

头部切片的数字会与 sentiment-judge 的 `compute` 对账一次，确保没有各自算各自的。

用法：
    python3 attach_sentiment.py --report report-data.json \
        --units sentiment-units.json --labels-dir sentiment-batches \
        --brands "Bewinch,Coway,Sterra,Novita,Waterdrop" --target Bewinch \
        --out report-data.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

# 兄弟 skill 按相对位置定位：本脚本在 <skills>/<skill>/scripts/ 下。
# 脱离整套 skill 单独部署时，用 GEO_PRESALES_SKILLS_ROOT 指向 skills 根目录。
SKILLS_ROOT = Path(os.environ.get(
    "GEO_PRESALES_SKILLS_ROOT", str(Path(__file__).resolve().parents[2])))
JUDGE_SCRIPTS = SKILLS_ROOT / "geo-presales-sentiment-judge" / "scripts"

# 报告平台显示名 → 采集目录里的平台名
PLATFORM_INTERNAL = {
    "AIO": "overview",
    "Google AI Overviews": "overview",
    "Gemini": "gemini",
    "ChatGPT": "chatgpt",
    "Perplexity": "perplexity",
}

# 竞品情感矩阵的行（属性点）。取自 Case 的产品特性与差异化优势，
# 是客户真正拿来横向比较的维度。
ATTRIBUTE_KEYWORDS = {
    "免安装": ["no plumbing", "no installation", "plug-and-play", "plug and play", "免安装", "免接水管",
             "without plumbing", "installation-free"],
    "机身深度": ["26 cm", "26cm", "slim", "shallow", "depth", "compact footprint", "narrow counter",
              "space-saving", "footprint"],
    "即热控温": ["instant hot", "temperature", "heating", "hot water", "temperature settings", "boiling"],
    "RO 过滤": ["reverse osmosis", "filtration", "filter", "purification", "ro system"],
    "矿化": ["mineral", "remineral", "alkaline", "mineralization"],
    "容量水箱": ["tank", "litre", "liter", "capacity", "reservoir"],
}


def load_labels(labels_dir: Path, brand: str) -> dict:
    path = labels_dir / f"{brand}-labels.json"
    if not path.exists():
        raise SystemExit(f"缺少 {brand} 的判读标签：{path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    for key in ("positive", "negative"):
        if key not in payload:
            raise SystemExit(f"{path} 缺少 {key} 字段")
    overlap = set(payload["positive"]) & set(payload["negative"])
    if overlap:
        raise SystemExit(f"{path} 正负标签重叠：{sorted(overlap)[:5]}")
    return payload


def merge_labels(labels_dir: Path, brands: list[str]) -> dict:
    """把分品牌标签合并到单元表位置上的统一标签，并校验互不重叠。"""
    merged = {"positive": [], "negative": []}
    owner: dict[int, str] = {}
    for brand in brands:
        payload = load_labels(labels_dir, brand)
        for key in ("positive", "negative"):
            for index in payload[key]:
                if index in owner:
                    raise SystemExit(f"单元 {index} 被 {owner[index]} 与 {brand} 重复标注")
                owner[index] = brand
                merged[key].append(index)
    merged["positive"].sort()
    merged["negative"].sort()
    return merged


def verify_against_judge(units_path: Path, labels_dir: Path, target: str, expected: dict) -> None:
    """用 sentiment-judge 的 compute 对账头部聚合，避免两处各算各的。

    compute 拒绝跨品牌标签，所以这里传该品牌自己的标签文件，而不是合并后的。
    """
    with tempfile.TemporaryDirectory() as tmp:
        labels_path = Path(tmp) / "labels.json"
        labels_path.write_text((labels_dir / f"{target}-labels.json").read_text(encoding="utf-8"),
                               encoding="utf-8")
        metrics_path = Path(tmp) / "metrics.json"
        subprocess.run(
            [sys.executable, str(JUDGE_SCRIPTS / "sentiment_sentences.py"), "compute",
             "--units", str(units_path), "--labels", str(labels_path), "--brand", target,
             "--out-csv", str(Path(tmp) / "s.csv"), "--out-metrics", str(metrics_path)],
            check=True, capture_output=True, text=True,
        )
        authoritative = json.loads(metrics_path.read_text(encoding="utf-8"))
    for key in ("positive", "negative"):
        if int(authoritative.get(key) or 0) != expected[key]:
            raise SystemExit(
                f"与 sentiment-judge 对账不一致：{target} {key} "
                f"本脚本 {expected[key]} vs compute {authoritative.get(key)}"
            )


def clean_text(value: str) -> str:
    """去掉 markdown 记号，判读句里常见 **加粗**、无序列表符与反引号。"""
    text = str(value or "")
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"\1", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"^\s*[-*+]\s+", "", text)
    text = re.sub(r"^\s*#+\s*", "", text)
    return re.sub(r"\s+", " ", text).strip()


def rate(pos: int, neg: int) -> str:
    rated = pos + neg
    return f"{pos * 100 / rated:.1f}%" if rated else "—"


def excerpt(sentence: str, keywords: list[str], width: int = 46) -> str:
    """截取关键词附近的短句，避免把整段塞进矩阵格。"""
    lowered = sentence.casefold()
    for keyword in keywords:
        position = lowered.find(keyword)
        if position < 0:
            continue
        start = max(0, position - width // 2)
        end = min(len(sentence), start + width)
        piece = sentence[start:end].strip()
        return ("…" if start else "") + piece + ("…" if end < len(sentence) else "")
    return sentence[:width].strip()


def build_brand_table(units: list[dict], merged: dict, brands: list[str], counts: dict,
                      predicate) -> dict:
    """竞品情感对比表。

    不做「属性 × 品牌」矩阵：判读是按整句给方向的，没有逐句的属性标注，
    按关键词把长句切到属性格子里会同时错配品牌与方向（例如把「Winner: Bewinch」
    的片段填进竞品格），给客户看会误导。这里只按品牌汇总，代表证据句要求点名该品牌。
    """
    return {
        "columns": ["正向率", "正向句", "负向句"],
        "rows": [
            {
                "brand": brand,
                "target": brand == "Bewinch",
                "values": [
                    rate(counts[brand][0], counts[brand][1]),
                    str(counts[brand][0]),
                    str(counts[brand][1]),
                ],
            }
            for brand in brands
        ],
    }


def top_claims(units: list[dict], merged: dict, brand: str, direction: str, predicate, limit=3) -> list[dict]:
    picked = []
    for index in merged[direction]:
        unit = units[index]
        if unit.get("brand") != brand or not predicate(unit):
            continue
        sentence = clean_text(unit.get("unit"))
        if not sentence:
            continue
        picked.append({"text": sentence[:24], "claim": sentence[:90], "evidence": sentence[:200]})
        if len(picked) >= limit:
            break
    return picked


def main() -> int:
    parser = argparse.ArgumentParser(description="把情感判读结果接入报告数据")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--units", type=Path, required=True)
    parser.add_argument("--labels-dir", type=Path, required=True)
    parser.add_argument("--brands", required=True, help="逗号分隔的展示品牌")
    parser.add_argument("--target", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    brands = [b.strip() for b in args.brands.split(",") if b.strip()]
    units = json.loads(args.units.read_text(encoding="utf-8"))["units"]
    merged = merge_labels(args.labels_dir, brands)

    report = json.loads(args.report.read_text(encoding="utf-8"))
    meta = report.get("meta", {})

    # question_id → 主题；units 里的 question_id 是补零字符串，meta.questions 用整数
    topic_of = {f"{int(q['qid']):04d}": q.get("topic") for q in meta.get("questions", [])}

    pos_sets = {b: set() for b in brands}
    neg_sets = {b: set() for b in brands}
    for index in merged["positive"]:
        pos_sets[units[index]["brand"]].add(index)
    for index in merged["negative"]:
        neg_sets[units[index]["brand"]].add(index)

    def make_predicate(region: str, platform_display: str, topic: str):
        internal = PLATFORM_INTERNAL.get(platform_display) if platform_display else None
        def predicate(unit: dict) -> bool:
            if region and unit.get("region") != region:
                return False
            if internal and unit.get("platform") != internal:
                return False
            if topic and topic_of.get(str(unit.get("question_id"))) != topic:
                return False
            return True
        return predicate

    for key, slice_value in report["slices"].items():
        region, platform_display, topic = (key.split("|") + ["", "", ""])[:3]
        predicate = make_predicate(region, platform_display, topic)
        counts = {
            b: (
                sum(1 for i in pos_sets[b] if predicate(units[i])),
                sum(1 for i in neg_sets[b] if predicate(units[i])),
            )
            for b in brands
        }
        target_pos, target_neg = counts[args.target]
        slice_value["sentiment"] = {
            "summary": {
                "total": target_pos + target_neg,
                "pos": target_pos, "neu": 0, "neg": target_neg,
                "pos_rate": rate(target_pos, target_neg),
                "neg_rate": rate(target_neg, target_pos),
            },
            "claims": {
                "pos": top_claims(units, merged, args.target, "positive", predicate),
                "neg": top_claims(units, merged, args.target, "negative", predicate),
            },
            "matrix": build_brand_table(units, merged, brands, counts, predicate),
            "by_brand": {
                b: {"positive": counts[b][0], "negative": counts[b][1],
                    "pos_rate": rate(counts[b][0], counts[b][1])}
                for b in brands
            },
        }

    headline = report["slices"].get("||")
    if headline:
        by_brand = headline["sentiment"]["by_brand"]
        verify_against_judge(
            args.units, args.labels_dir, args.target,
            {"positive": by_brand[args.target]["positive"],
             "negative": by_brand[args.target]["negative"]},
        )

    meta["sentiment_claims_status"] = "complete"
    meta["sentiment_brands"] = brands
    meta["sentiment_note"] = (
        "情感仅判读了报告中展示的 %d 个品牌；其余开放品牌未判读。"
        "正向率 = 正向句 ÷（正向句 + 负向句），排除中性；代表证据句取自该品牌自己的判读句。" % len(brands)
    )
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    head = report["slices"].get("||", report["slices"][next(iter(report["slices"]))])
    print("情感已接入 45 个切片；头部切片（全部国家/全部平台/全部主题）：")
    for brand in brands:
        row = head["sentiment"]["by_brand"][brand]
        print(f"  {brand:12s} 正 {row['positive']:>3}  负 {row['negative']:>3}  正向率 {row['pos_rate']}")
    print(f"写出 {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
