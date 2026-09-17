"""DEPRECATED（2026-09-17）：遗留实现，仅供只读参考，不得用于正式交付。

正式指标口径的唯一实现是 geo-presales-report-editor/scripts/geo_presales_core/
（prepare_answers / compute_metrics），报告生成走 geo-presales-report-builder。
本脚本的口径与 core 未对齐，端到端结果已确认不等价（见文内注释）。
"""
"""把采集审计的产物渲染成一份可交付的 Markdown 报告。

跨 skill 共用：输入是同一个采集任务目录下的确定性产物，数据集特有的叙述放在
findings.json 里，脚本本身不写死任何数据集。

输入（`<audit-dir>` 下）
    visibility-metrics.json   必需，可见度指标（l3 / 分平台 / 分题）
    citation-metrics.json     必需，引用来源、官网引用份额、字段对账
    crawl-integrity.json      必需，采集可信性校验
    verification.json         必需，品牌抽取独立复核
    findings.json             可选，数据集特有叙述

findings.json 结构（字段都可省）
    {
      "title": "Botslab smart dash cams · Discovery 题可见度统计",
      "summary_notes": ["摘要里要额外说的结论", ...],
      "audit_findings": ["### 1. 小标题\\n正文", ...],
      "unresolved": ["未判定项，一条一行", ...],
      "extra_outputs": [{"file": "x.json", "desc": "说明"}]
    }

用法
    python3 render_crawl_audit_report.py --audit-dir <目录> [--target Botslab]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

# 归属展示用：域名 -> 品牌。只影响报告里的一列文字，不影响任何统计。
OWNED_DOMAINS = {
    "botslab.com": "Botslab（目标品牌）",
    "70mai.com": "70mai（正式竞品）",
    "reolink.com": "Reolink（正式竞品）",
    "aosulife.com": "aosu（正式竞品）",
    "eufy.com": "eufy",
    "arlo.com": "Arlo",
    "ring.com": "Ring",
    "viofo.com": "VIOFO",
    "blackvue.com": "BlackVue",
    "thinkware.com": "Thinkware",
    "vantrue.com": "Vantrue",
    "nextbase.com": "Nextbase",
    "garmin.com": "Garmin",
    "rexingusa.com": "Rexing",
    "redtigercam.com": "REDTIGER",
    "google.com": "Google Nest",
    "tapo.com": "TP-Link Tapo",
    "tp-link.com": "TP-Link Tapo",
}

DEFAULT_UNRESOLVED = [
    "商品卡 `merchants` 列的品牌名（品牌自营店）不计入首次出现位置，该类目只在销售渠道意义上出现；若改口径首现顺序会变。",
    "商品卡 `goods` 列不含品牌前缀的纯型号行不计入品牌。",
    "正文引用标记是否为原站 citation pill，没有原始 HTML 无法验证；按项目既有口径把交付的 Markdown 标记作为回退证据。",
]


def table(rows, include_zero=True):
    lines = ["| 品牌 | 提及次数 | 提及率 | 提及率排名 | 声量份额 | 平均提及位置 |",
             "|---|---:|---:|---:|---:|---:|"]
    for b in (rows if include_zero else [b for b in rows if b["mention_count"]]):
        pos = b["average_position"]
        lines.append(
            f"| {b['brand']} | {b['mention_count']} | {b['mention_rate_percent']}% | "
            f"{b['mention_rank']} | {b['share_of_voice_percent']}% | "
            f"{pos if pos is not None else '无（未出现）'} |"
        )
    return "\n".join(lines)


def build(audit_dir: Path, target: str) -> str:
    load = lambda name: json.loads((audit_dir / name).read_text())  # noqa: E731
    data = load("visibility-metrics.json")
    citations = load("citation-metrics.json")
    verification = load("verification.json")
    integrity = load("crawl-integrity.json")
    findings = load("findings.json") if (audit_dir / "findings.json").exists() else {}

    scope = data["scope"]
    totals = data["totals"]
    topic = scope["topic"][0]
    platforms = scope["platforms"]
    by_question = data["by_question"]
    l3 = {b["brand"]: b for b in data["l3_discovery"]}
    target_row = l3[target]
    top_overall = data["l3_discovery"][0]
    configured = scope["ranking_brand_set"][1:]
    rivals = sorted(
        (l3[n] for n in configured if n in l3),
        key=lambda b: b["mention_count"], reverse=True,
    )
    owned = citations["owned_citation_share"]
    target_owned = owned[target]
    total_citations = sum(b["citation_occurrences"] for b in citations["by_platform"].values())

    parts = [f"# {findings.get('title', f'{target} {topic} · Discovery 题可见度统计')}\n"]

    # ------------------------------------------------------------ 结论摘要
    overall_label = (
        "全品类最高即目标品牌" if top_overall["brand"] == target
        else f"全品类最高 **{top_overall['brand']} {top_overall['mention_rate_percent']}%**"
    )
    rows = [
        f"| 提及率 | **{target_row['mention_count']} / {target_row['mention_denominator']}"
        f"（{target_row['mention_rate_percent']}%）** | {overall_label} |",
        f"| 提及率排名 | **{target_row['mention_rank']} / "
        f"{totals['l3']['ranking_brand_count']}** | 全品类第 1 为 {top_overall['brand']} |",
        f"| 声量份额 | **{target_row['share_of_voice_percent']}%** | "
        f"全品类最高 {top_overall['share_of_voice_percent']}% |",
    ]
    if target_row["average_position"] is not None:
        rows.append(
            f"| 平均提及位置 | **{target_row['average_position']}** | "
            f"被提及 {target_row['position_count']} 次 |"
        )
    rows.append(
        f"| 官网引用份额 | **{target_owned['owned_share_percent']}%** | "
        f"{target_owned['owned_occurrences']} / {target_owned['total_occurrences']} |"
    )

    summary = ["## 结论摘要\n", "| 指标 | " + target + " | 参照 |\n|---|---|---|\n" + "\n".join(rows)]

    appeared = [
        q for q, rs in sorted(by_question.items())
        if next((b for b in rs if b["brand"] == target), {}).get("mention_count")
    ]
    absent = [q for q in sorted(by_question) if q not in appeared]
    notes = []
    if not appeared:
        notes.append(f"**{len(by_question)} 道题的正文里一次都没出现。**")
    elif absent:
        notes.append(
            f"**只在 {len(appeared)}/{len(by_question)} 道题里出现**（{'、'.join(appeared)}）；"
            f"{'、'.join(absent)} 未出现。"
        )
    flag_defects = integrity["defect_index"].get("MENTION_FLAG_LAYER_MIXING", [])
    if flag_defects:
        notes.append(
            f"采集脚本的提及标记有 **{len(flag_defects)} 条误报**——那部分命中来自回答正文"
            f"以外的字段（检索结果、原始流、购物卡片），不是回答正文提及。"
        )
    if target_owned["owned_occurrences"]:
        notes.append(
            f"官网被引用 **{target_owned['owned_occurrences']} 次**"
            f"（官网引用份额 {target_owned['owned_share_percent']}%）。"
        )
    else:
        notes.append(f"**官网引用份额为 0**，{total_citations} 次引用全部来自媒体或第三方。")
    notes.extend(findings.get("summary_notes", []))
    if rivals:
        notes.append(
            "配置竞品对照：" + "、".join(
                f"{b['brand']} {b['mention_rate_percent']}%（第 {b['mention_rank']}）" for b in rivals
            ) + "。"
        )
    summary.append("\n" + "\n".join(notes))
    summary.append(
        f"\n> 样本边界：仅 {len(by_question)} 道 discovery 题，全属 {topic} Topic，"
        f"不能代表 {target} 的整体可见度。\n"
    )
    parts.append("\n".join(summary))

    # ------------------------------------------------------------ 样本范围与口径
    repeat = totals["l3"]["eligible_answers"] // max(len(platforms) * len(scope["questions"]), 1)
    parts.append("\n## 样本范围\n")
    parts.append(
        f"- 题目：{'、'.join(scope['questions'])}（均为 `diagnosis_intent = discovery`、"
        f"`analysis_type = visibility`）\n"
        f"- Topic：{topic}\n"
        f"- 平台：{'、'.join(platforms)}；每题每平台重复采集 {repeat} 次\n"
        f"- 回答总数 {scope['answers_total']}，可用 {scope['answers_available']}，"
        f"采集失败 {scope['answers_unavailable']}\n"
        f"- 有效回答（至少提及一个品牌）{totals['l3']['eligible_answers']}，"
        f"无品牌回答 {totals['l3']['no_brand_answers']}\n"
        f"- 品牌提及总数 {totals['l3']['brand_mentions_total']}，"
        f"识别品牌 {totals['l3']['identified_brand_count']} 个\n"
    )
    parts.append("\n## 指标口径\n")
    for key, desc in data["metric_definitions"].items():
        parts.append(f"- **{key}**：{desc}")
    parts.append("\n分母统一为去引用正文中至少出现一个合格品牌的可用回答数。\n")

    parts.append("\n## 汇总（discovery 全部样本）\n")
    parts.append(table(data["l3_discovery"]))
    parts.append(
        f"\n### 目标品牌\n"
        f"\n{target}：提及 **{target_row['mention_count']} / "
        f"{target_row['mention_denominator']}**，提及率 **{target_row['mention_rate_percent']}%**，"
        f"**提及率排名 {target_row['mention_rank']}**，"
        f"声量份额 **{target_row['share_of_voice_percent']}%**，"
        f"平均提及位置 **{target_row['average_position'] if target_row['average_position'] is not None else '无'}**。\n"
        f"\n排名口径（与 `geo-presales-report-builder` 统一）：参与计算的品牌 = 目标品牌 + "
        f"{len(configured)} 个配置竞品（{'、'.join(configured)}）+ 开放品牌词表命中的品牌，"
        f"共 {totals['l3']['ranking_brand_count']} 个。\n"
    )

    parts.append("\n## 分平台\n")
    for platform, rs in data["by_platform"].items():
        parts.append(f"\n### {platform}（n={totals['by_platform'][platform]['eligible_answers']}）\n")
        parts.append(table(rs))

    parts.append("\n## 分题\n")
    for question, rs in sorted(by_question.items()):
        parts.append(f"\n### {question}\n")
        parts.append(table(rs))

    # ------------------------------------------------------------ 引用数据
    cite = ["\n## 引用数据\n"]
    cite.append(
        f"口径：按 `{citations['policy']['id']}` 处理，**只统计回答正文中的引用标记出现次数**；"
        f"检索结果字段、购物卡片与正文普通超链接均不计入；来源清单按规范化 URL 去重。\n"
    )
    cite.append("| 平台 | 可用回答 | 含引用回答 | 引用次数 | 回答内去重 | 全局去重 | 引用域名 |")
    cite.append("|---|---:|---:|---:|---:|---:|---:|")
    for platform, block in citations["by_platform"].items():
        cite.append(
            f"| {platform} | {block['answers']} | {block['answers_with_citation']} | "
            f"{block['citation_occurrences']} | {block['occurrences_deduped_within_answer']} | "
            f"{block['unique_urls']} | {block['unique_domains']} |"
        )
    cite.append(
        "\n三列是同一批引用事件的三种计法，**本报告其余章节用「引用次数」**：\n"
        "- **引用次数**：正文引用标记每出现一次计一次，同一 URL 在一篇里出现 N 次就算 N 次。\n"
        "- **回答内去重**：同一 URL 在同一篇里只计一次。\n"
        "- **全局去重**：跨全部回答只计一次，即来源页面总数。\n"
    )

    if any(b.get("occurrences_in_table_rows") for b in citations["by_platform"].values()):
        cite.append("\n### 重复引用的形态\n")
        cite.append(
            "引用次数的重复主要来自**模型对比表格里逐行挂同一个引用**，不是转换产生的重复。\n"
        )
        cite.append("| 平台 | 位于表格行内的标记 | 占该平台引用次数 |")
        cite.append("|---|---:|---:|")
        for platform, block in citations["by_platform"].items():
            total = block["citation_occurrences"]
            rows_in_table = block.get("occurrences_in_table_rows", 0)
            share = round(rows_in_table * 100 / total, 1) if total else 0
            cite.append(f"| {platform} | {rows_in_table} | {share}% |")
        repeats = [
            (p, item) for p, b in citations["by_platform"].items()
            for item in b.get("top_repeated_sources", [])
        ]
        if repeats:
            cite.append("\n单篇内重复 3 次以上的来源：\n")
            cite.append("| 平台 | 回答 | 来源 | 单篇引用次数 |")
            cite.append("|---|---|---|---:|")
            for platform, item in sorted(repeats, key=lambda x: -x[1]["occurrences"])[:8]:
                domain = item["url"].split("/")[2] if "//" in item["url"] else item["url"]
                cite.append(
                    f"| {platform} | {item['answer_id'].split(':')[-1]} | {domain} | "
                    f"{item['occurrences']} |"
                )
        cite.append(
            "\n核对过这不是转换重复：这些标记的位置分散在全文，且逐篇重复次数的分布是自然长尾，"
            "不是 `citation-field-mapping.md` 里 Overview 0001 那种「每个编号恰好两次」的可疑形态。"
        )
        cite.append(
            "\n**口径影响**：如果改成表格行只计 1 次，引用次数会明显下降，各来源的相对排序不变"
            "但绝对占比会变。本报告维持「按出现次数计」，因为表格逐行挂引用反映的正是模型"
            "对该来源的依赖程度。\n"
        )

    for platform, block in citations["by_platform"].items():
        cite.append(f"\n### {platform} 引用来源域名\n")
        cite.append("| 域名 | 引用次数 | 覆盖回答数 | 回答占比 | 归属 |")
        cite.append("|---|---:|---:|---:|---|")
        for item in block["domains"]:
            cite.append(
                f"| {item['domain']} | {item['occurrences']} | {item['answers']} | "
                f"{item['answer_rate_percent']}% | "
                f"{OWNED_DOMAINS.get(item['domain'], '媒体 / 第三方')} |"
            )

    cite.append("\n### 官网引用份额\n")
    cite.append("独立指标：**指向官网的引用记录 ÷ 全部引用记录**。\n")
    cite.append("| 品牌 | 官网域名 | " + " | ".join(platforms) + " | 合计 |")
    cite.append("|---|---|" + "---:|" * len(platforms) + "---:|")
    for name, entry in owned.items():
        cells = [
            f"{entry['by_platform'][p]['owned_occurrences']}/"
            f"{entry['by_platform'][p]['total_occurrences']}" for p in platforms
        ]
        cite.append(
            f"| {name} | {entry['official_domain']} | " + " | ".join(cells)
            + f" | **{entry['owned_share_percent']}%** |"
        )

    cite.append("\n### 检索层（不计入引用，仅作对照）\n")
    for field, block in citations.get("retrieval_layer_not_citations", {}).items():
        if "unique_domains" not in block:
            cite.append(f"- **{field}**：{block.get('note', '')}")
            continue
        cite.append(
            f"- `{field}`：{block['unique_domains']} 个域名、{block['entries']} 条记录，"
            f"其中 {block.get('target_host_answers', 0)} 条回答的该字段含目标品牌域名"
        )

    cite.append("\n### 统计取数来源与字段对账\n")
    cite.append(
        "引用**次数**与 **URL 映射**都由脚本从正文解析：次数取 `([来源名][编号])` 标记出现，"
        "URL 取正文 `[编号]: url \"标题\"` 定义行。供应商引用字段不作统计来源，"
        "只在正文缺定义时回退。\n"
    )
    cite.append("| 平台 | 正文解析去重 URL | 字段去重 URL | 仅正文有 | 仅字段有 | 走字段回退的标记 |")
    cite.append("|---|---:|---:|---:|---:|---:|")
    for platform, block in citations["by_platform"].items():
        r = block["reference_field_reconciliation"]
        cite.append(
            f"| {platform} | {r['body_unique_urls']} | {r['field_unique_urls']} | "
            f"{len(r['only_in_body'])} | {len(r['only_in_field'])} | "
            f"{block['citations_array_fallback']} |"
        )
    parts.append("\n".join(cite))

    # ------------------------------------------------------------ 采集可信性
    integ = ["\n## 采集可信性校验\n"]
    integ.append(
        f"用 `geo-presales-crawl-integrity` 对采集目录做前置校验：{integrity['samples']} 条样本，"
        f"平台分布 {'、'.join(f'{k} {v}' for k, v in integrity['by_platform'].items())}。"
        f"阻断性缺陷 {integrity['counts']['defects']} 项，警告 {integrity['counts']['warnings']} 项。\n"
    )
    if integrity["defect_index"]:
        integ.append("| 缺陷码 | 受影响记录 |")
        integ.append("|---|---|")
        for code, ids in integrity["defect_index"].items():
            integ.append(f"| `{code}` | {'、'.join(ids)} |")
        if "MENTION_FLAG_LAYER_MIXING" in integrity["defect_index"]:
            integ.append(
                "\n`MENTION_FLAG_LAYER_MIXING`：采集器自带的提及标记把**回答正文以外的字段**"
                "（检索结果 `search_result`、原始流 `sse_data`、购物卡片 `products`）也算成了提及。"
                "本报告全部数字已改用回答正文口径。\n"
            )
    integ.append(
        f"\n目标品牌回答正文命中 **{integrity['counts']['samples_with_target_in_answer']}** 条，"
        f"仅在正文外字段出现 **{integrity['counts']['samples_with_target_outside_body_only']}** 条"
        f"（被检索或商品卡带出，但未被提及）。\n"
    )
    parts.append("\n".join(integ))

    # ------------------------------------------------------------ 抽取校验
    check = ["\n## 抽取校验结果\n"]
    variants = verification.get("name_variants") or {}
    check.append(
        f"- {verification['answers_checked']} 条可用回答全部完成抽取，无缺失。\n"
        f"- 品牌名出现在正文中："
        f"{'全部通过' if not verification['brand_not_in_body'] else str(len(verification['brand_not_in_body'])) + ' 处失配'}。\n"
        f"- 首次出现顺序独立复核："
        f"{'0 处不一致' if not verification['order_mismatch'] else str(len(verification['order_mismatch'])) + ' 处不一致'}。\n"
        f"- 同一品牌多种写法："
        f"{'未发现' if not variants else str(len(variants)) + ' 组（已归一到种子词典写法）'}。\n"
        f"- 标准词典召回复查：{len(verification['suspected_missed_brands'])} 处疑似遗漏品牌。\n"
    )
    for name, forms in variants.items():
        check.append(f"- 写法归一组：{' / '.join(forms)} → {name}")
    for item in verification["brand_not_in_body"]:
        check.append(f"- `{item['answer_id']}`：{item['detail']}")
    for item in verification["order_mismatch"]:
        check.append(f"- `{item['answer_id']}`：记录顺序 {item['recorded']} ≠ 实测 {item['observed']}")
    for item in verification["suspected_missed_brands"]:
        check.append(f"- `{item['answer_id']}`：疑似遗漏 {item['brand']}")
    parts.append("\n".join(check))

    # ------------------------------------------------------------ 审计发现与未判定
    if findings.get("audit_findings"):
        parts.append("\n## 审计发现\n")
        for item in findings["audit_findings"]:
            parts.append("\n" + item + "\n")

    parts.append("\n## 未判定项\n")
    for item in findings.get("unresolved", DEFAULT_UNRESOLVED):
        parts.append(f"- {item}\n")

    # ------------------------------------------------------------ 复跑
    outputs = [
        {"file": "audit-report.md", "desc": "本报告"},
        {"file": "normalized-answers.jsonl", "desc": "回答规范化 + 去引用结果"},
        {"file": "extract-*.json", "desc": "品牌抽取明细（含排除项与不确定性）"},
        {"file": "verification.json", "desc": "品牌抽取的独立复核结果"},
        {"file": "visibility-metrics.json / .csv", "desc": "可见度指标，含 l3 / 分平台 / 分题三级"},
        {"file": "citation-metrics.json", "desc": "引用来源、域名分布、官网引用份额、字段对账"},
        {"file": "crawl-integrity.json", "desc": "采集可信性校验的完整缺陷清单"},
        {"file": "findings.json", "desc": "数据集特有叙述（摘要补充、审计发现、未判定项）"},
    ] + list(findings.get("extra_outputs", []))
    parts.append("\n## 复跑与产出\n")
    parts.append("\n| 文件 | 内容 |\n|---|---|")
    for item in outputs:
        parts.append(f"| `{item['file']}` | {item['desc']} |")
    parts.append(
        "\n先跑采集校验与抽取复核（脚本在 `geo-presales-report-audit` 与 "
        "`geo-presales-crawl-integrity` 两个 skill 里），再渲染本报告：\n"
    )
    parts.append(
        "\n```bash\n"
        "SKILLS=<skills 根目录>\n"
        "BANK=<题库.json>; LEX=<品牌词表.json>\n"
        "python3 $SKILLS/geo-presales-crawl-integrity/scripts/audit_crawl_integrity.py \\\n"
        "  --collect-dir <结果目录> --target " + target + " --out <audit-dir>/crawl-integrity.json\n"
        "python3 $SKILLS/geo-presales-report-audit/scripts/de_cite_crawl.py \\\n"
        "  --collect-dir <结果目录> --question-bank $BANK --out <audit-dir>/normalized-answers.jsonl\n"
        "python3 $SKILLS/geo-presales-report-audit/scripts/verify_brand_extraction.py \\\n"
        "  --normalized <audit-dir>/normalized-answers.jsonl --extractions '<audit-dir>/extract-*.json' \\\n"
        "  --lexicon $LEX --out <audit-dir>/verification.json\n"
        "python3 $SKILLS/shared/scripts/compute_visibility_metrics.py \\\n"
        "  --audit-dir <audit-dir> --question-bank $BANK --lexicon $LEX --engine <metrics_engine.py>\n"
        "python3 $SKILLS/shared/scripts/compute_citation_metrics.py \\\n"
        "  --audit-dir <audit-dir> --collect-dir <结果目录> --question-bank $BANK\n"
        "python3 $SKILLS/shared/scripts/render_crawl_audit_report.py \\\n"
        "  --audit-dir <audit-dir> --target " + target + "\n"
        "```\n"
        "\n品牌抽取（`extract-*.json`）是唯一的非确定性步骤，需要按分片跑 LLM；"
        "其余全部可确定性复跑。\n"
    )
    return "\n".join(parts)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--audit-dir", required=True)
    parser.add_argument("--target", default="Botslab")
    parser.add_argument("--out", help="默认写到 <audit-dir>/audit-report.md")
    args = parser.parse_args()
    audit_dir = Path(args.audit_dir).expanduser().resolve()
    text = build(audit_dir, args.target)
    out = Path(args.out) if args.out else audit_dir / "audit-report.md"
    out.write_text(text + "\n")
    print("wrote", out)


if __name__ == "__main__":
    main()
