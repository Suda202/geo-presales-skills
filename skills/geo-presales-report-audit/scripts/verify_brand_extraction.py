"""独立复核品牌抽取：不信任抽取结果，自己从正文重算一遍。

四项检查，全部确定性：
  1. 名称在正文中——每个记录的品牌名必须能在该条正文里找到；
  2. 首现顺序——记录顺序必须等于正文中首次出现的先后；
  3. 标准名一致性——同一品牌不得因大小写/写法差异被拆成多个名字；
  4. 召回——词典里命中的品牌不得在记录中缺失（需 --lexicon）。

第 3 项是本 skill 的硬性前置：分片抽取时不同分片可能各写一种大小写，
不在算排名前归一会让同一品牌占两个名次。

用法
    python3 verify_brand_extraction.py --normalized <normalized-answers.jsonl> \
        --extractions <目录或 glob> [--lexicon <品牌别名表.json>] --out <verification.json>
"""

from __future__ import annotations

import argparse
import glob
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path


def fold(text: str) -> str:
    return unicodedata.normalize("NFKC", str(text or "")).lower()


def surface_forms(brand: str, lexicon: dict) -> list[str]:
    forms = lexicon.get(brand)
    if forms:
        return [fold(f) for f in forms]
    return [fold(brand)]


def first_offset(body: str, brand: str, lexicon: dict) -> int | None:
    low = fold(body)
    best = None
    for form in surface_forms(brand, lexicon):
        if not form:
            continue
        pattern = r"(?<![a-z0-9])" + re.escape(form) + r"(?![a-z0-9])"
        match = re.search(pattern, low)
        if match and (best is None or match.start() < best):
            best = match.start()
    return best


def load_extractions(target: Path) -> dict:
    paths = []
    if target.is_dir():
        paths = sorted(target.glob("extract-*.json"))
    else:
        paths = sorted(Path(p) for p in glob.glob(str(target)))
    if not paths:
        raise SystemExit(f"未找到抽取文件：{target}")
    out = {}
    for path in paths:
        for record in json.loads(path.read_text()):
            key = record["answer_id"]
            if key in out:
                raise SystemExit(f"{key} 在多个分片里重复出现")
            out[key] = record
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--normalized", required=True, help="de_cite_crawl.py 的产出")
    parser.add_argument("--extractions", required=True, help="抽取结果文件或目录")
    parser.add_argument("--lexicon", help="标准名→别名表 JSON，提供后启用召回检查")
    parser.add_argument("--out", help="复核结果输出路径")
    args = parser.parse_args()

    rows = [json.loads(line) for line in
            Path(args.normalized).expanduser().read_text().splitlines() if line.strip()]
    extractions = load_extractions(Path(args.extractions).expanduser())
    lexicon = json.loads(Path(args.lexicon).expanduser().read_text()) if args.lexicon else {}
    # 下划线开头的键是词表元信息（注释、版本），不是品牌
    lexicon = {k: v for k, v in lexicon.items() if not k.startswith("_")}

    not_in_body, order_mismatch, missed, missing_extraction = [], [], [], []
    name_variants = defaultdict(set)

    for row in rows:
        if row["answer_status"] != "available":
            continue
        record = extractions.get(row["answer_id"])
        if record is None:
            missing_extraction.append(row["answer_id"])
            continue
        # 排名用 body_ranking（商品卡 merchants 列已清空）；缺失时退回 body_markdown
        body = row.get("body_ranking") or row["body_markdown"]
        recorded = [b["brand"] for b in record.get("brands", [])]
        for name in recorded:
            name_variants[fold(name)].add(name)
        offsets = []
        for name in recorded:
            offset = first_offset(body, name, lexicon)
            if offset is None:
                not_in_body.append({"answer_id": row["answer_id"], "brand": name})
            else:
                offsets.append((offset, name))
        observed = [name for _, name in sorted(offsets)]
        if observed != recorded:
            order_mismatch.append({
                "answer_id": row["answer_id"], "recorded": recorded, "observed": observed,
            })
        if lexicon:
            recorded_low = {fold(n) for n in recorded}
            for brand in lexicon:
                if fold(brand) in recorded_low:
                    continue
                if first_offset(body, brand, lexicon) is not None:
                    missed.append({"answer_id": row["answer_id"], "brand": brand})

    collisions = {k: sorted(v) for k, v in name_variants.items() if len(v) > 1}

    print(f"检查回答数: {sum(1 for r in rows if r['answer_status'] == 'available')}")
    print(f"  1 名称不在正文: {len(not_in_body)}")
    for item in not_in_body[:10]:
        print(f"      {item['answer_id']} | {item['brand']}")
    print(f"  2 首现顺序不一致: {len(order_mismatch)}")
    for item in order_mismatch[:10]:
        print(f"      {item['answer_id']}")
        print(f"        记录 {item['recorded']}")
        print(f"        实测 {item['observed']}")
    print(f"  3 同一品牌多种写法: {len(collisions)}")
    for key, names in collisions.items():
        print(f"      {names} —— 算排名前必须归一到其中一种")
    print(f"  4 词典命中但未记录: {len(missed)}")
    for item in missed[:20]:
        print(f"      {item['answer_id']} | {item['brand']}")
    if missing_extraction:
        print(f"  抽取缺失: {len(missing_extraction)} —— {missing_extraction[:5]}")

    report = {
        "answers_checked": sum(1 for r in rows if r["answer_status"] == "available"),
        "brand_not_in_body": not_in_body,
        "order_mismatch": order_mismatch,
        "name_variants": collisions,
        "suspected_missed_brands": missed,
        "missing_extraction": missing_extraction,
        "lexicon_used": bool(lexicon),
    }
    if args.out:
        Path(args.out).expanduser().write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print("wrote", args.out)

    blocking = bool(not_in_body or order_mismatch or collisions or missing_extraction)
    return 2 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())
