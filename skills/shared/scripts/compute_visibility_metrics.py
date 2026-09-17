"""DEPRECATED（2026-09-17）：遗留实现，仅供只读参考，不得用于正式交付。

正式指标口径的唯一实现是 geo-presales-report-editor/scripts/geo_presales_core/
（prepare_answers / compute_metrics），报告生成走 geo-presales-report-builder。
本脚本的口径与 core 未对齐，端到端结果已确认不等价（见文内注释）。
"""
"""从审计目录的抽取结果计算可见度指标（提及率 / 提及率排名 / 声量份额 / 平均提及位置）。

跨 skill 共用：不写死任何数据集，题库、词典、引擎路径都从参数来。

口径
    品牌集合 = 目标品牌 + 题库里的配置竞品 + 自由品牌词表命中的品牌（与
    `geo-presales-report-builder` 一致）。声量份额与平均提及位置的分母都是这一整集，
    不是只展示的几个。正式可见度只用 `diagnosis_intent = discovery` 的样本。

依赖
    指标定义来自 `--engine` 指向的引擎文件。正式实现是
    `geo-presales-report-editor/scripts/geo_presales_core`。

    **公式层已实测等价**（2026-09-16，Botslab 两个 Topic 共 21 个品牌，
    提及率/声量/平均位置 0 差异，差异只在输出舍入位数）。

    **但两边的输入正文不同，端到端结果不等价**：本管线在去引用正文上识别品牌；
    `geo-presales-report-builder/scripts/build_report_data.py:739` 把**原始未去引用正文**
    交给 GPC 的别名匹配，于是被引文章的标题（如
    `"...the finest car cameras by Garmin, Nextbase, 70mai and more"`）里的品牌会被算成提及。
    实测行车记录仪 150 条：GPC 多算 31 次、涉及 7 个品牌，且只多算不少算；
    配置竞品 70mai 的提及率因此从 26.0% 虚增到 36.0%。
    详见 `geo-presales-report-audit` 的错误类型「引用锚文本公司名误计为品牌」。

用法
    python3 compute_visibility_metrics.py --audit-dir <目录> --question-bank <题库.json> \
        --engine <metrics_engine.py> [--lexicon <品牌词典.json>]
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
from pathlib import Path


def load_engine(path: Path):
    spec = importlib.util.spec_from_file_location("metrics_engine", path)
    engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    return engine


def configured_brands(engine, question_bank: Path, target: str):
    """目标品牌 + 题库里的配置竞品。竞品按 Case 取，不按 Topic 过滤。"""
    bank = json.loads(question_bank.read_text())
    names = [c["name"] for c in bank["config"]["competitor_selection"]["formal_competitors"]]
    return (target, *names)


def load_rows(audit_dir: Path, canonical: dict):
    rows = [
        json.loads(line)
        for line in (audit_dir / "normalized-answers.jsonl").read_text().splitlines()
    ]
    extractions = {}
    for path in sorted(audit_dir.glob("extract-*.json")):
        for record in json.loads(path.read_text()):
            key = record["answer_id"]
            if key in extractions:
                raise SystemExit(f"duplicate extraction for {key} across chunks")
            extractions[key] = record
    missing = [
        r["answer_id"] for r in rows
        if r["answer_status"] == "available" and r["answer_id"] not in extractions
    ]
    if missing:
        raise SystemExit(f"{len(missing)} answers lack an extraction, e.g. {missing[:5]}")
    unknown = set(extractions) - {r["answer_id"] for r in rows}
    if unknown:
        raise SystemExit(f"extraction references unknown answers: {sorted(unknown)[:5]}")
    for row in rows:
        record = extractions.get(row["answer_id"]) or {}
        brands = record.get("brands") or []
        # 归一标准名并按首次出现顺序去重后重新编号：顺序不变，只折叠同名的重复项，
        # 避免同一品牌在一篇内占两个位置、在聚合里占两个名次。
        ordered = []
        evidence = {}
        for entry in brands:
            name = canonical.get(entry["brand"], entry["brand"])
            evidence.setdefault(name, entry.get("evidence", ""))
            if name not in ordered:
                ordered.append(name)
        row["brands"] = {name: position for position, name in enumerate(ordered, start=1)}
        row["brand_evidence"] = evidence
        row["excluded_entities"] = record.get("excluded_entities") or []
        row["uncertainties"] = record.get("uncertainties") or []
        row["citation_events"] = []
        row["claims"] = []
    return rows


BRAND_FIELDS = (
    "brand", "mention_count", "mention_denominator", "mention_rate_percent",
    "mention_rate_model_average_percent", "mention_rank",
    "share_of_voice_numerator", "share_of_voice_denominator", "share_of_voice_percent",
    "position_sum", "position_count", "average_position", "positions",
)


def brand_table(agg):
    return [{k: b[k] for k in BRAND_FIELDS} for b in agg["brands"]]


def write_csv(path: Path, levels):
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["scope_kind", "scope"] + list(BRAND_FIELDS))
        for kind, scopes in (
            ("l3", {"discovery": levels["l3"]}),
            ("by_platform", levels["by_platform"]),
            ("by_question", levels["l2"]),
        ):
            for scope, agg in scopes.items():
                for row in brand_table(agg):
                    writer.writerow([kind, scope] + [
                        json.dumps(row[c], ensure_ascii=False) if isinstance(row[c], list) else row[c]
                        for c in BRAND_FIELDS
                    ])


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--audit-dir", required=True)
    parser.add_argument("--question-bank", required=True)
    parser.add_argument("--lexicon", help="品牌词典；只取 _canonical 作为写法归一表")
    parser.add_argument("--engine", required=True,
                        help="指标引擎 metrics_engine.py 的路径")
    parser.add_argument("--target", default="Botslab")
    args = parser.parse_args()

    audit_dir = Path(args.audit_dir).expanduser().resolve()
    question_bank = Path(args.question_bank).expanduser().resolve()
    engine_path = Path(args.engine).expanduser().resolve()
    if not engine_path.exists():
        raise SystemExit(f"指标引擎不存在：{engine_path}（用 --engine 指定）")

    canonical = {}
    if args.lexicon:
        canonical = json.loads(Path(args.lexicon).expanduser().read_text()).get("_canonical", {})

    engine = load_engine(engine_path)
    rows = load_rows(audit_dir, canonical)
    platforms = list(dict.fromkeys(r["platform"] for r in rows))
    configured = configured_brands(engine, question_bank, args.target)
    engine.CONFIGURED = configured
    levels = engine.build_levels(rows, platforms)

    payload = {
        "scope": {
            "questions": sorted({r["question_id"] for r in rows}),
            "diagnosis_intent": "discovery",
            "topic": sorted({r["topic"] for r in rows}),
            "topic_ids": sorted({r["topic_id"] for r in rows}),
            "platforms": platforms,
            "ranking_brand_set": list(configured),
            "answers_total": len(rows),
            "answers_available": sum(r["answer_status"] == "available" for r in rows),
            "answers_unavailable": sum(r["answer_status"] != "available" for r in rows),
            "answers_with_brands": sum(
                r["answer_status"] == "available" and bool(r["brands"]) for r in rows
            ),
            "canonical_name_fixes": canonical,
            "engine": str(engine_path),
        },
        "metric_definitions": {
            "mention_rate_percent": "提及该品牌的合格回答数 / 合格回答数(去重后至少提及一个品牌)",
            "mention_rank": "按提及次数降序的位次，1 = 提及次数最多",
            "share_of_voice_percent": "该品牌提及次数 / 范围内全部品牌提及次数",
            "average_position": "该品牌在回答中首次出现位置的平均值，1 = 最先被提及",
        },
        "l3_discovery": brand_table(levels["l3"]),
        "by_platform": {p: brand_table(a) for p, a in levels["by_platform"].items()},
        "by_question": {q: brand_table(a) for q, a in levels["l2"].items()},
        "totals": {
            "l3": {
                "eligible_answers": levels["l3"]["eligible_brand_answer_count"],
                "no_brand_answers": levels["l3"]["no_brand_answer_count"],
                "brand_mentions_total": levels["l3"]["brand_mentions_total"],
                "identified_brand_count": levels["l3"]["identified_brand_count"],
                "ranking_brand_count": levels["l3"]["ranking_brand_count"],
            },
            "by_platform": {
                p: {
                    "eligible_answers": a["eligible_brand_answer_count"],
                    "no_brand_answers": a["no_brand_answer_count"],
                    "brand_mentions_total": a["brand_mentions_total"],
                }
                for p, a in levels["by_platform"].items()
            },
        },
    }
    (audit_dir / "visibility-metrics.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2)
    )
    write_csv(audit_dir / "visibility-metrics.csv", levels)

    print(f"n={payload['totals']['l3']['eligible_answers']}  "
          f"品牌集合 {len(configured)} 个，参与排名 {payload['totals']['l3']['ranking_brand_count']} 个")
    for b in payload["l3_discovery"]:
        if b["mention_count"] or b["brand"] in configured:
            print(f"  {b['brand']:<16}{b['mention_count']:>4}  "
                  f"{b['mention_rate_percent']:>7}%  rank={b['mention_rank']:<3}"
                  f"sov={b['share_of_voice_percent']:>6}%  pos={b['average_position']}")
    print("wrote", audit_dir / "visibility-metrics.json", "和 .csv")


if __name__ == "__main__":
    main()
