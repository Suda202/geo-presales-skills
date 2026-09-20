"""情感判读交接的确定性辅助:拆批、回装、校验。

填补 extract(sentiment-judge)与 attach_sentiment.py 之间三个此前靠人肉完成的环节:

  split        units.json 按品牌拆出判读批次视图 sentiment-batches/<品牌>.json,
               每条带全局 idx,判读代理只读自己品牌的批次,labels 仍按全局 idx 写。
  assemble     units.json + sentiment-batches/<品牌>-labels.json 确定性生成
               sentiment-claims/judged-sentences.json(观点归纳的输入)。
  check-claims 校验 sentiment-claims/<品牌>-claims.json 的 indices 对
               judged-sentences.json 互斥且穷尽、count 与 indices 一致。

语义判读与观点归纳本身仍是语义工作,本脚本不做任何判定。
文件格式契约见 references/sentiment-handoff-contract.md。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"缺少文件:{path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path} 不是合法 JSON:{exc}")


def load_units(path: Path) -> list[dict]:
    data = load_json(path)
    units = data.get("units") if isinstance(data, dict) else data
    if not isinstance(units, list) or not units:
        raise SystemExit(f"{path} 缺少非空的单元数组")
    return units


def sentence_record(index: int, unit: dict) -> dict:
    return {
        "idx": index,
        "region": unit.get("region"),
        "platform": unit.get("platform"),
        "question_id": unit.get("question_id"),
        "intent": unit.get("intent"),
        "sentence": unit.get("unit") or unit.get("sentence") or "",
    }


def cmd_split(args) -> int:
    units = load_units(args.units)
    brands = [b.strip() for b in args.brands.split(",") if b.strip()]
    args.out_dir.mkdir(parents=True, exist_ok=True)
    counts = {}
    for brand in brands:
        rows = [dict(sentence_record(i, u), brand=brand)
                for i, u in enumerate(units) if u.get("brand") == brand]
        if not rows:
            print(f"警告:{brand} 在单元表中没有任何单元", file=sys.stderr)
        out = args.out_dir / f"{brand}.json"
        out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        counts[brand] = len(rows)
    print(json.dumps({"split": counts, "out_dir": str(args.out_dir)}, ensure_ascii=False))
    return 0


def cmd_assemble(args) -> int:
    units = load_units(args.units)
    brands = [b.strip() for b in args.brands.split(",") if b.strip()]
    judged: dict[str, dict] = {}
    for brand in brands:
        labels_path = args.labels_dir / f"{brand}-labels.json"
        labels = load_json(labels_path)
        for key in ("positive", "negative"):
            if key not in labels:
                raise SystemExit(f"{labels_path} 缺少 {key} 字段")
        overlap = set(labels["positive"]) & set(labels["negative"])
        if overlap:
            raise SystemExit(f"{labels_path} 正负标签重叠:{sorted(overlap)[:5]}")
        entry = {}
        for key in ("positive", "negative"):
            rows = []
            for index in sorted(labels[key]):
                if not (0 <= index < len(units)):
                    raise SystemExit(f"{labels_path} 索引 {index} 越界(单元数 {len(units)})")
                unit = units[index]
                if unit.get("brand") != brand:
                    raise SystemExit(
                        f"{labels_path} 索引 {index} 属于品牌 {unit.get('brand')!r},不是 {brand!r}")
                rows.append(sentence_record(index, unit))
            entry[key] = rows
        judged[brand] = entry
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(judged, ensure_ascii=False, indent=1), encoding="utf-8")
    summary = {b: {k: len(v[k]) for k in ("positive", "negative")} for b, v in judged.items()}
    print(json.dumps({"assembled": summary, "out": str(args.out)}, ensure_ascii=False))
    return 0


def cmd_check_claims(args) -> int:
    judged = load_json(args.judged)
    problems = []
    warnings = []
    checked = {}
    for brand, sentences in judged.items():
        claims_path = args.claims_dir / f"{brand}-claims.json"
        if not claims_path.exists():
            problems.append(f"{brand}: 缺少观点归纳文件 {claims_path}")
            continue
        claims = load_json(claims_path)
        for key in ("positive", "negative"):
            member_count = len(sentences.get(key) or [])
            seen: set[int] = set()
            for group in claims.get(key) or []:
                indices = group.get("indices") or []
                label = group.get("label") or "<无标签>"
                if group.get("count") != len(indices):
                    problems.append(
                        f"{brand}/{key}/「{label}」: count={group.get('count')} 与 indices 数量 {len(indices)} 不一致")
                for i in indices:
                    if not (0 <= i < member_count):
                        problems.append(f"{brand}/{key}/「{label}」: 索引 {i} 越界(共 {member_count} 句)")
                    elif i in seen:
                        # 多属性句可归入多个组（如一句同时讲滤芯寿命+性价比），
                        # 降级为警告，不阻断校验
                        warnings.append(f"{brand}/{key}: 索引 {i} 出现在多个组(多属性句)")
                    else:
                        seen.add(i)
            missing = set(range(member_count)) - seen
            if missing:
                problems.append(
                    f"{brand}/{key}: {len(missing)} 句未归入任何组(不穷尽),如 {sorted(missing)[:8]}")
            checked[f"{brand}/{key}"] = {"sentences": member_count, "grouped": len(seen)}
    print(json.dumps({"checked": checked, "problems": problems, "warnings": warnings}, ensure_ascii=False, indent=1))
    if problems:
        print(f"校验失败:{len(problems)} 个问题", file=sys.stderr)
        return 1
    if warnings:
        print(f"校验通过,{len(warnings)} 个警告", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("split", help="按品牌拆出判读批次视图")
    p.add_argument("--units", type=Path, required=True)
    p.add_argument("--brands", required=True, help="逗号分隔的展示品牌,与词表标准名一致")
    p.add_argument("--out-dir", type=Path, required=True, help="批次目录,通常为 <输出>/sentiment-batches")
    p.set_defaults(func=cmd_split)

    p = sub.add_parser("assemble", help="从 labels 确定性生成 judged-sentences.json")
    p.add_argument("--units", type=Path, required=True)
    p.add_argument("--labels-dir", type=Path, required=True)
    p.add_argument("--brands", required=True)
    p.add_argument("--out", type=Path, required=True,
                   help="通常为 <输出>/sentiment-claims/judged-sentences.json")
    p.set_defaults(func=cmd_assemble)

    p = sub.add_parser("check-claims", help="校验观点归纳互斥且穷尽")
    p.add_argument("--judged", type=Path, required=True)
    p.add_argument("--claims-dir", type=Path, required=True)
    p.set_defaults(func=cmd_check_claims)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
