"""从审计目录计算引用指标：正文引用标记、来源分布、官网引用份额、字段对账。

跨 skill 共用：不写死任何数据集。

口径（`citation_pill_sources_only_v1`，2026-09-14 确认）
  * 只统计回答正文里的引用标记 `([来源名][编号])` 的出现次数；
  * 检索结果字段（`search_result` / `links`）、购物卡片（`products`）与正文普通超链接
    都不是引用；
  * 同一 URL 在一篇里出现 N 次就算 N 次（occurrences），来源清单另按规范化 URL 去重；
  * 正文缺 `[编号]: url` 定义行时，回退到供应商引用字段的同序号成员，并记录回退次数。

用法
    python3 compute_citation_metrics.py --audit-dir <目录> --collect-dir <采集目录> \
        --question-bank <题库.json>
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit, parse_qsl, urlencode, urlunsplit

REF_DEF = re.compile(r"^\s*\[(\d+)\]:\s*(\S+?)(?:\s+\"([^\"]*)\")?\s*$", re.M)
MARKER_PAREN = re.compile(r"\(\[([^\]\n]{1,80})\]\[(\d+)\]\)")
MARKER_BARE = re.compile(r"(?<!\()\[([^\]\n]{1,80})\]\[(\d+)\]")
TRACKING_PREFIXES = ("utm_", "gclid", "fbclid", "mc_", "ref_", "_gl", "igshid", "srsltid")
TRACKING_EXACT = {"fp", "fs", "smid", "source", "campaign"}

# 每个平台把回答正文与供应商引用字段放在哪
PLATFORM_CONTRACT = {
    "chatgpt": {
        "answer": ["result_text"],
        "citation_field": ["content_references"],
        "retrieval": ["search_result", "links"],
    },
    "gemini": {"answer": ["result_text"], "citation_field": ["citations"], "retrieval": []},
    "aimode": {
        "answer": ["result_md", "result_text"],
        "citation_field": ["citations"],
        "retrieval": ["search_result"],
    },
    "overview": {
        "answer": ["content", "rawtext"],
        "citation_field": ["source"],
        "retrieval": [],
    },
    "perplexity": {
        "answer": ["result_text"],
        "citation_field": ["web_results"],
        "retrieval": [],
    },
}


def normalize_url(raw):
    if not raw or not isinstance(raw, str):
        return None
    parts = urlsplit(raw.strip())
    if parts.scheme not in ("http", "https"):
        return None
    query = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith(TRACKING_PREFIXES) and k.lower() not in TRACKING_EXACT
    ]
    return urlunsplit((parts.scheme, parts.netloc.lower(),
                       parts.path.rstrip("/") or "/", urlencode(query), ""))


def domain_of(url):
    return urlsplit(url).netloc.lower().removeprefix("www.") if url else None


def parse_answer(text):
    definitions = {}
    for number, url, _title in REF_DEF.findall(text):
        definitions[number] = normalize_url(url)
    spans, occurrences = [], []
    for match in MARKER_PAREN.finditer(text):
        spans.append(match.span())
        occurrences.append((match.group(1).strip(), match.group(2), match.start()))
    for match in MARKER_BARE.finditer(text):
        if any(s <= match.start() < e for s, e in spans):
            continue
        occurrences.append((match.group(1).strip(), match.group(2), match.start()))
    occurrences.sort(key=lambda item: item[2])
    return definitions, occurrences


def pick(node, keys):
    for key in keys:
        value = node.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def as_text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(as_text(v) for v in value)
    if isinstance(value, dict):
        return "\n".join(as_text(v) for v in value.values())
    return "" if value is None else str(value)


def urls_anywhere(value):
    """递归取一个非正文字段里的 URL（结构感知，不扫序列化文本）。"""
    found = []

    def visit(node, key=None):
        if isinstance(node, dict):
            for k, v in node.items():
                visit(v, k)
        elif isinstance(node, list):
            for item in node:
                visit(item, key)
        elif isinstance(node, str):
            if key in ("url", "link", "href") or key is None:
                url = normalize_url(node)
                if url:
                    found.append(url)

    visit(value)
    return found


def official_domains(question_bank: Path):
    config = json.loads(question_bank.read_text())["config"]
    entries = [(config["brand_name"], config.get("official_domain"))]
    for competitor in config["competitor_selection"]["formal_competitors"]:
        entries.append((competitor["name"], competitor.get("official_domain")))
    out = []
    for name, domain in entries:
        if not domain:
            continue
        out.append((
            name,
            # 与 domain_of() 同样去掉 www.，否则一边带 www. 会永远比不相等
            domain.replace("https://", "").replace("http://", "")
            .strip("/").lower().removeprefix("www."),
        ))
    return out


def load_answers(audit_dir: Path, collect_dir: Path):
    rows = [
        json.loads(line)
        for line in (audit_dir / "normalized-answers.jsonl").read_text().splitlines()
    ]
    answers = []
    for row in rows:
        relative = row["source_file"].split(str(collect_dir.name) + "/", 1)[-1]
        raw = json.loads((collect_dir / relative).read_text())
        result = raw.get("task_result") or {}
        answers.append({
            "answer_id": row["answer_id"],
            "platform": row["platform"],
            "question_id": row["question_id"],
            "answer_status": row["answer_status"],
            "result": result,
        })
    return answers


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--audit-dir", required=True)
    parser.add_argument("--collect-dir", required=True)
    parser.add_argument("--question-bank", required=True)
    args = parser.parse_args()

    audit_dir = Path(args.audit_dir).expanduser().resolve()
    collect_dir = Path(args.collect_dir).expanduser().resolve()
    question_bank = Path(args.question_bank).expanduser().resolve()

    answers = load_answers(audit_dir, collect_dir)
    platforms = list(dict.fromkeys(a["platform"] for a in answers))
    domains = official_domains(question_bank)
    target_host = dict(domains).get(
        json.loads(question_bank.read_text())["config"]["brand_name"], ""
    )

    report = {
        "policy": {
            "id": "citation_pill_sources_only_v1",
            "counted_unit": "回答正文中的引用标记出现次数",
            "excluded": ["检索结果字段", "补充链接", "购物卡片", "正文普通超链接"],
            "display_dedup": "来源清单按规范化 URL 去重（去追踪参数与 fragment）",
        },
        "by_platform": {},
    }

    for platform in platforms:
        contract = PLATFORM_CONTRACT.get(platform)
        if not contract:
            continue
        selected = [
            a for a in answers
            if a["platform"] == platform and a["answer_status"] == "available"
        ]
        total = deduped_in_answer = in_table = unresolved = with_citation = 0
        unique_urls = set()
        url_occurrences, url_answers = Counter(), defaultdict(set)
        domain_occurrences, domain_answers = Counter(), defaultdict(set)
        fallback_total = 0
        per_answer, repeats = [], []
        for answer in selected:
            body = as_text(pick(answer["result"], contract["answer"]))
            definitions, occurrences = parse_answer(body)
            fallback = pick(answer["result"], contract["citation_field"]) or []
            if not isinstance(fallback, list):
                fallback = []
            if occurrences:
                with_citation += 1
            answer_urls, answer_counts, used_fallback = set(), Counter(), 0
            for _label, number, position in occurrences:
                total += 1
                line_start = body.rfind("\n", 0, position) + 1
                if body[line_start:].lstrip().startswith("|"):
                    in_table += 1
                url = definitions.get(number)
                if not url and number.isdigit() and 0 < int(number) <= len(fallback):
                    item = fallback[int(number) - 1]
                    url = normalize_url(item if isinstance(item, str) else item.get("url"))
                    if url:
                        used_fallback += 1
                if not url:
                    unresolved += 1
                    continue
                answer_urls.add(url)
                answer_counts[url] += 1
                url_occurrences[url] += 1
                url_answers[url].add(answer["answer_id"])
                domain = domain_of(url)
                domain_occurrences[domain] += 1
                domain_answers[domain].add(answer["answer_id"])
            unique_urls |= answer_urls
            deduped_in_answer += len(answer_urls)
            fallback_total += used_fallback
            per_answer.append({
                "answer_id": answer["answer_id"],
                "occurrences": len(occurrences),
                "unique_urls": len(answer_urls),
                "citations_array_fallback": used_fallback,
            })
            for url, count in answer_counts.items():
                if count >= 3:
                    repeats.append(
                        {"answer_id": answer["answer_id"], "url": url, "occurrences": count}
                    )

        # 正文解析 vs 供应商字段的双向对账
        body_urls, field_urls = set(), set()
        field_empty_but_body = []
        for answer in selected:
            body = as_text(pick(answer["result"], contract["answer"]))
            definitions, _ = parse_answer(body)
            body_set = {u for u in definitions.values() if u}
            raw_field = pick(answer["result"], contract["citation_field"]) or []
            field_set = set()
            for item in (raw_field if isinstance(raw_field, list) else []):
                url = normalize_url(item if isinstance(item, str) else item.get("url"))
                if url:
                    field_set.add(url)
            body_urls |= body_set
            field_urls |= field_set
            if body_set and not field_set:
                field_empty_but_body.append(answer["answer_id"])

        report["by_platform"][platform] = {
            "answers": len(selected),
            "answers_with_citation": with_citation,
            "citation_occurrences": total,
            "occurrences_deduped_within_answer": deduped_in_answer,
            "occurrences_in_table_rows": in_table,
            "unresolved_occurrences": unresolved,
            "citations_array_fallback": fallback_total,
            "unique_urls": len(unique_urls),
            "unique_domains": len(domain_occurrences),
            "domains": [
                {
                    "domain": d,
                    "occurrences": c,
                    "answers": len(domain_answers[d]),
                    "answer_rate_percent": round(len(domain_answers[d]) * 100 / len(selected), 2),
                }
                for d, c in sorted(domain_occurrences.items(), key=lambda x: (-x[1], x[0]))
            ],
            "pages": [
                {"url": u, "occurrences": c, "answers": len(url_answers[u])}
                for u, c in sorted(url_occurrences.items(), key=lambda x: (-x[1], x[0]))
            ],
            "top_repeated_sources": sorted(
                repeats, key=lambda x: (-x["occurrences"], x["answer_id"])
            )[:10],
            "per_answer": per_answer,
            "reference_field_reconciliation": {
                "field": contract["citation_field"][0],
                "body_unique_urls": len(body_urls),
                "field_unique_urls": len(field_urls),
                "only_in_body": sorted(body_urls - field_urls),
                "only_in_field": sorted(field_urls - body_urls),
                "field_empty_while_body_has_definitions": field_empty_but_body,
            },
        }

    # 检索层：不是引用，只作对照，用来回答「被检索到但没被引用」
    retrieval = {}
    for platform in platforms:
        contract = PLATFORM_CONTRACT.get(platform)
        if not contract:
            continue
        fields = contract.get("retrieval") or []
        if not fields:
            retrieval[platform] = {
                "note": f"{platform} 未公开独立检索结果字段；来源面板与 related_queries 都不算",
                "top_domains": [],
            }
            continue
        selected = [
            a for a in answers
            if a["platform"] == platform and a["answer_status"] == "available"
        ]
        for field in fields:
            dom_occ, dom_answers = Counter(), defaultdict(set)
            for answer in selected:
                for url in urls_anywhere(answer["result"].get(field)):
                    domain = domain_of(url)
                    dom_occ[domain] += 1
                    dom_answers[domain].add(answer["answer_id"])
            retrieval[field] = {
                "unique_domains": len(dom_occ),
                "entries": sum(dom_occ.values()),
                "target_host_answers": len(dom_answers.get(target_host, set())),
                "top_domains": [
                    {"domain": d, "entries": c, "answers": len(dom_answers[d])}
                    for d, c in sorted(dom_occ.items(), key=lambda x: (-x[1], x[0]))[:15]
                ],
            }
    report["retrieval_layer_not_citations"] = retrieval

    # 官网引用份额：指向官网的引用记录 ÷ 全部引用记录
    owned = {}
    for name, domain in domains:
        entry = {"brand": name, "official_domain": domain, "by_platform": {}}
        total_owned = total_all = 0
        for platform, block in report["by_platform"].items():
            hits = sum(
                item["occurrences"] for item in block["domains"]
                if item["domain"] == domain or item["domain"].endswith("." + domain)
            )
            overall = block["citation_occurrences"]
            total_owned += hits
            total_all += overall
            entry["by_platform"][platform] = {
                "owned_occurrences": hits,
                "total_occurrences": overall,
                "owned_share_percent": round(hits * 100 / overall, 2) if overall else None,
            }
        entry["owned_occurrences"] = total_owned
        entry["total_occurrences"] = total_all
        entry["owned_share_percent"] = round(total_owned * 100 / total_all, 2) if total_all else None
        owned[name] = entry
    report["owned_citation_share"] = owned

    (audit_dir / "citation-metrics.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2)
    )
    for platform, block in report["by_platform"].items():
        print(f"{platform}: 引用 {block['citation_occurrences']} 次 / "
              f"回答内去重 {block['occurrences_deduped_within_answer']} / "
              f"全局去重 {block['unique_urls']}；表格行内 {block['occurrences_in_table_rows']}")
    for name, entry in owned.items():
        print(f"  官网引用份额 {name:<9}{entry['official_domain']:<16}"
              f"{entry['owned_share_percent']}%  "
              f"({entry['owned_occurrences']}/{entry['total_occurrences']})")
    print("wrote", audit_dir / "citation-metrics.json")


if __name__ == "__main__":
    main()
