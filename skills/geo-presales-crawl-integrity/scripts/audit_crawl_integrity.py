"""Pre-metric integrity gate over raw overseas GEO crawler output.

Runs before any visibility or citation metric is computed. It does not score,
correct or rank anything: it only answers "can this collection be trusted as
input", and names the exact records that cannot.

Exit codes
    0  clean
    1  warnings only (citation-count drift,口径 reminders)
    2  blocking defects (would corrupt mention rate or a denominator)

Usage
    python3 audit_crawl_integrity.py --collect-dir <dir> --target <Brand> [--out report.json]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit, parse_qsl, urlencode, urlunsplit

# Platform field contract. Every entry names where each of the four distinct
# data layers physically lives. See references/layer-contract.md.
PLATFORM_CONTRACT = {
    "chatgpt": {
        "answer": ["result_text"],
        "body_citations": ["content_references"],
        "retrieval": ["search_result", "links"],
        # 没有独立来源面板字段：右侧分开展示 content_references（引用）与
        # search_result（来源），不要为了"补齐"把 search_result 挪进本层。
        "answer_sources": [],
    },
    "gemini": {
        "answer": ["result_text"],
        "body_citations": ["citations"],
        "retrieval": [],
        "answer_sources": ["citations"],
    },
    "aimode": {
        "answer": ["result_md", "result_text"],
        "body_citations": ["citations"],
        "retrieval": ["search_result"],
        "answer_sources": ["citations"],
        "raw_html": ["result_html"],
    },
    "overview": {
        "answer": ["content", "rawtext"],
        "body_citations": ["source"],
        "retrieval": ["web_source"],
        "answer_sources": ["source"],
    },
    "perplexity": {
        "answer": ["result_text"],
        "body_citations": ["web_results"],
        "retrieval": [],
        "answer_sources": ["web_results"],
    },
}

# 失败页签名表**只在 geo_presales_core 定义一次**，本脚本引用它，不再复制一份。
# 复制过的后果实测过：本地的表含 `could you try again`，而 core 当时没有，
# 同一条回答在两个 skill 里判定相反。
SKILLS_ROOT = Path(os.environ.get(
    "GEO_PRESALES_SKILLS_ROOT", str(Path(__file__).resolve().parents[2])))
CORE_DIR = SKILLS_ROOT / "geo-presales-report-editor" / "scripts"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))
from geo_presales_core.crawler import answer_validity  # noqa: E402

REF_DEF = re.compile(r"^\s*\[(\d+)\]:\s*(\S+?)(?:\s+\"([^\"]*)\")?\s*$", re.M)
MARKER_PAREN = re.compile(r"\(\[([^\]\n]{1,80})\]\[(\d+)\]\)")
MARKER_BARE = re.compile(r"(?<!\()\[([^\]\n]{1,80})\]\[(\d+)\]")
MARKER_ANY = re.compile(r"\[([^\]\n]{1,80})\]\[(\d+)\]")
# D6 — 采集在改写字词。这些是实测抓到的损坏，不是启发式猜测：
# 带连字符的词被替换成不成词的片段。新增案例请追加，不要用正则去猜——
# 产品名与型号（G3-Pro、Waterdrop-A1）与真损坏无法靠形状区分。
KNOWN_TEXT_CORRUPTION = {
    "plug-and-dline": "plug-and-play",
    "faucet-mipe": "faucet-mounted",
    "faucet-ted": "faucet-connected",
    "side-t mounted": "side-tank mounted",
    "greenhouse of model options": "gamut/range of model options",
}

# 模型内部结构泄漏进正文（渲染残留）
RENDER_RESIDUE = [
    (re.compile(r"product\[\"turn\d+product\d+\"", re.I), "商品对象字面量"),
    (re.compile(r"<Elicitation", re.I), "Elicitation 标签"),
    (re.compile(r"ElicitationsGroup", re.I), "ElicitationsGroup 残留"),
    (re.compile(r"<FollowUp\b", re.I), "FollowUp 标签"),
]

# 正文尾部被截断：以孤立标题符、连字符结尾，或以极短残词收尾且无句末标点
TAIL_HEADING = re.compile(r"#{1,6}\s*$")
# 表格行以竖线收尾也是完整结尾，不能算截断
SENTENCE_END = re.compile(r"[.!?。！？:)\]】”\"|]$")

TRACKING_PREFIXES = ("utm_", "gclid", "fbclid", "mc_", "ref_", "_gl", "igshid", "srsltid")
TRACKING_EXACT = {"fp", "fs", "smid", "source", "campaign"}


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


def dig(payload, key):
    """Read a dotted key, tolerating a missing task_result wrapper."""
    node = payload
    for part in ("task_result", key):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return None
    return node


def first_present(payload, keys):
    for key in keys:
        value = dig(payload, key)
        if value not in (None, "", [], {}):
            return value
    return None


def as_text(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(as_text(v) for v in value)
    if isinstance(value, dict):
        return "\n".join(as_text(v) for v in value.values())
    return str(value)


def urls_in(value):
    """Collect source URLs from a citation field, structure-aware.

    Deliberately does not regex the serialised blob: a citation record also
    carries favicon URLs, thumbnails and query strings, and sweeping those in
    would invent sources the answer never cited.
    """
    found = set()

    def visit(node):
        if isinstance(node, dict):
            for key, item in node.items():
                if key in ("url", "link", "href") and isinstance(item, str):
                    url = normalize_url(item)
                    if url:
                        found.add(url)
                elif key in ("favicon", "thumbnail", "icon", "image", "snippet", "title", "summary"):
                    continue
                else:
                    visit(item)
        elif isinstance(node, list):
            for item in node:
                visit(item)
        elif isinstance(node, str):
            url = normalize_url(node)
            if url:
                found.add(url)

    visit(value)
    return found


def parse_body(text):
    definitions = {}
    for number, url, _title in REF_DEF.findall(text):
        definitions[number] = normalize_url(url)
    spans = []
    markers = []
    for match in MARKER_PAREN.finditer(text):
        spans.append(match.span())
        markers.append(match.group(2))
    for match in MARKER_BARE.finditer(text):
        if any(start <= match.start() < end for start, end in spans):
            continue
        markers.append(match.group(2))
    return definitions, markers


CONTRACT_OVERRIDE = Path(__file__).resolve().parent.parent / "references" / "platform-contract.json"


def load_platform_contract() -> dict:
    """内置默认 + 外部 platform-contract.json 覆盖合并。

    新增平台只要在 JSON 里加一条，不用改脚本。
    """
    contract = {name: dict(spec) for name, spec in PLATFORM_CONTRACT.items()}
    if CONTRACT_OVERRIDE.exists():
        overrides = json.loads(CONTRACT_OVERRIDE.read_text(encoding="utf-8"))
        for name, spec in overrides.items():
            if name.startswith("_"):  # _note 之类的说明字段，不是平台
                continue
            if not isinstance(spec, dict):
                raise SystemExit(f"platform-contract.json 的 {name} 应为对象")
            merged = dict(contract.get(name, {}))
            merged.update(spec)
            contract[name] = merged
    return contract


def detect_platform(directory: Path, contract: dict):
    """产出采集目录下的全部平台，未登记契约的也产出，由调用方报缺陷。"""
    for child in sorted(directory.iterdir()):
        if child.is_dir() and child.name.startswith("scraper."):
            name = child.name.split(".", 1)[1]
            yield name, child, name in contract


def iter_samples(root: Path, contract: dict):
    for platform, platform_dir, _known in detect_platform(root, contract):
        for path in sorted(platform_dir.rglob("*.json")):
            yield platform, path


def audit_sample(platform, path, target, contract):
    payload = json.loads(path.read_text())
    result = payload.get("task_result") or {}
    answer = as_text(first_present(payload, contract["answer"]))
    identity = f"{platform}:{path.parent.name}/{path.name}"

    defects = []
    warnings = []
    infos = []

    lowered = answer.strip().lower()
    if not lowered:
        defects.append({"code": "EMPTY_ANSWER", "detail": "回答正文为空"})
    else:
        valid, reason = answer_validity(answer)
        if not valid:
            defects.append({
                "code": "FAILED_ANSWER",
                "detail": f"模型失败页（{reason}）：{answer.strip()[:60]!r}",
            })

    # D1 — the mention flag must reflect the answer body only. Anything outside
    # it (retrieval results, raw stream, shopping cards, ads, metadata) is a
    # different layer and must never stand in for a body mention. Confirmed
    # sources of false positives so far: search_result, sse_data, products.
    body_fields = set(contract["answer"])
    outside = {key: value for key, value in result.items() if key not in body_fields}
    outside.pop("sse_data", None)
    outside_text = as_text(outside)
    retrieval_text = "\n".join(as_text(result.get(key)) for key in contract["retrieval"])
    stream_text = as_text(result.get("sse_data"))
    flag_key = f"mentioned_{target.lower()}"
    flag = payload.get(flag_key)
    if flag is None:
        flag = payload.get("mentioned_" + target.lower().replace(" ", "_"))
    in_answer = len(re.findall(re.escape(target), answer, re.I))
    in_retrieval = len(re.findall(re.escape(target), retrieval_text + "\n" + stream_text, re.I))
    in_outside = len(re.findall(re.escape(target), outside_text + "\n" + stream_text, re.I))
    outside_fields = sorted(
        key for key, value in result.items()
        if key not in body_fields and re.search(re.escape(target), as_text(value), re.I)
    )
    if in_answer == 0 and in_outside > 0 and flag:
        defects.append({
            "code": "MENTION_FLAG_LAYER_MIXING",
            "detail": f"{flag_key}=True，但回答正文 0 次；"
                      f"字段 {'、'.join(outside_fields) or 'sse_data'} 内 {in_outside} 次",
        })
    if in_answer == 0 and in_outside > 0:
        infos.append({
            "code": "TARGET_OUTSIDE_BODY_ONLY",
            "detail": f"回答正文 0 次，字段 {'、'.join(outside_fields) or 'sse_data'} 内 {in_outside} 次"
                      "（被检索/被商品卡带出，未被提及）",
            "fields": outside_fields,
        })

    # D2 — markers whose reference definition never reached the delivered body.
    definitions, markers = parse_body(answer)
    if markers:
        missing = sorted({n for n in markers if n not in definitions}, key=lambda x: (len(x), x))
        if missing:
            field = first_present(payload, contract["body_citations"])
            recoverable = []
            if isinstance(field, list):
                for number in missing:
                    if number.isdigit() and 0 < int(number) <= len(field):
                        recoverable.append(number)
            warnings.append({
                "code": "MISSING_REFERENCE_DEFINITION",
                "detail": f"标记编号 {missing} 在正文缺定义行",
                "recoverable_from_field": recoverable,
            })
        # D3 — the delivered citation field lost records the body still has.
        field = first_present(payload, contract["body_citations"])
        if field in (None, [], {}) :
            warnings.append({
                "code": "EMPTY_CITATION_FIELD",
                "detail": f"{contract['body_citations'][0]} 为空，但正文有 {len(markers)} 次引用标记、"
                          f"{len(definitions)} 条定义",
            })
        else:
            field_urls = urls_in(field)
            body_urls = {u for u in definitions.values() if u}
            only_body = sorted(body_urls - field_urls)
            only_field = sorted(field_urls - body_urls)
            if only_body or only_field:
                warnings.append({
                    "code": "CITATION_FIELD_BODY_MISMATCH",
                    "detail": f"仅正文有 {len(only_body)} 个 URL，仅字段有 {len(only_field)} 个 URL",
                    "only_in_body": only_body[:5],
                    "only_in_field": only_field[:5],
                })

    # D6 — 采集改写了正文本身。字段层面全部正常，只有逐字读正文才会发现，
    # 而它会直接污染报告里引用的原句与译文。
    lowered = answer.lower()
    corrupted = sorted(k for k in KNOWN_TEXT_CORRUPTION if k in lowered)
    tail = answer.rstrip()
    last_token = tail.split()[-1] if tail.split() else ""
    truncated = bool(
        tail
        and (
            TAIL_HEADING.search(tail)
            or tail.endswith("-")
            or (len(last_token) <= 3 and not SENTENCE_END.search(tail))
        )
    )
    if corrupted or truncated:
        parts = []
        if corrupted:
            parts.append("损坏词 " + "、".join(
                f"{w}→{KNOWN_TEXT_CORRUPTION[w]}" for w in corrupted))
        if truncated:
            parts.append(f"尾部截断（结尾 {tail[-24:]!r}）")
        warnings.append({
            "code": "TEXT_CORRUPTION",
            "detail": "；".join(parts),
            "corrupted_words": corrupted,
            "truncated_tail": truncated,
        })

    # 平台自带的标记混进正文。这是各平台已知的输出形态，不是采集缺陷，
    # 但下游做句子切分、翻译、引用解析时必须先剥掉，因此单列提示。
    residues = sorted({label for pattern, label in RENDER_RESIDUE if pattern.search(answer)})
    if residues:
        infos.append({
            "code": "PLATFORM_MARKUP_IN_BODY",
            "detail": "正文含平台标记：" + "、".join(residues),
        })

    # D4 — occurrences and unique sources are two different units; both must
    # travel together or a downstream reader will pick the wrong one.
    unique_sources = len({u for u in definitions.values() if u})
    infos.append({
        "code": "CITATION_UNITS",
        "detail": f"引用出现 {len(markers)} 次 / 去重来源 {unique_sources} 个",
    })

    return {
        "identity": identity,
        "platform": platform,
        "answer_chars": len(answer),
        "markers": len(markers),
        "unique_sources": unique_sources,
        "target_in_answer": in_answer,
        "target_in_retrieval": in_retrieval,
        "defects": defects,
        "warnings": warnings,
        "infos": infos,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--collect-dir", required=True)
    parser.add_argument("--target", required=True, help="目标品牌名，用于提及分层检查")
    parser.add_argument("--out", help="缺陷报告输出路径")
    args = parser.parse_args()

    root = Path(args.collect_dir).expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f"采集目录不存在: {root}")

    contract = load_platform_contract()
    contract["_platforms"] = {name: spec for name, spec in contract.items() if name != "_platforms"}

    unknown_platforms = []
    scanned = 0
    samples = []
    for platform, path in iter_samples(root, contract):
        if platform not in contract:
            if platform not in unknown_platforms:
                unknown_platforms.append(platform)
            continue
        scanned += 1
        try:
            samples.append(audit_sample(platform, path, args.target, contract[platform]))
        except Exception as exc:  # a malformed file is itself a defect
            samples.append({
                "identity": f"{platform}:{path.parent.name}/{path.name}",
                "platform": platform,
                "defects": [{"code": "UNREADABLE_SAMPLE", "detail": repr(exc)}],
                "warnings": [], "infos": [],
            })

    if unknown_platforms:
        samples.append({
            "identity": "scraper." + "、scraper.".join(unknown_platforms),
            "platform": "(未登记)",
            "defects": [{
                "code": "UNKNOWN_PLATFORM_CONTRACT",
                "detail": f"这些平台目录没有字段契约，未被审计：{unknown_platforms}。"
                          "请在 references/platform-contract.json 补契约后重跑，"
                          "未审计的平台不得计入「采集可信」的结论。",
            }],
            "warnings": [], "infos": [],
        })

    by_code = defaultdict(list)
    for sample in samples:
        for item in sample["defects"]:
            by_code[item["code"]].append(sample["identity"])
        for item in sample["warnings"]:
            by_code[item["code"]].append(sample["identity"])

    report = {
        "collect_dir": str(root),
        "target": args.target,
        "samples": len(samples),
        "unknown_platforms": unknown_platforms,
        "by_platform": dict(Counter(s["platform"] for s in samples)),
        "defect_index": {code: sorted(ids) for code, ids in sorted(by_code.items())},
        "counts": {
            "defects": sum(len(s["defects"]) for s in samples),
            "warnings": sum(len(s["warnings"]) for s in samples),
            "samples_with_target_outside_body_only": sum(
                1 for s in samples
                if any(i["code"] == "TARGET_OUTSIDE_BODY_ONLY" for i in s["infos"])
            ),
            "samples_with_target_in_answer": sum(1 for s in samples if s.get("target_in_answer")),
        },
        "details": samples,
    }

    if args.out:
        Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print("报告已写入", args.out)

    print(f"\n样本 {report['samples']} 条，平台分布 {report['by_platform']}")
    print(f"阻断性缺陷 {report['counts']['defects']} 项，警告 {report['counts']['warnings']} 项")
    for code, ids in report["defect_index"].items():
        head = "、".join(ids[:3])
        more = f" 等 {len(ids)} 条" if len(ids) > 3 else ""
        print(f"  {code}: {head}{more}")
    print(f"目标品牌回答正文命中 {report['counts']['samples_with_target_in_answer']} 条；"
          f"仅在正文外字段出现 {report['counts']['samples_with_target_outside_body_only']} 条")

    if report["counts"]["defects"]:
        return 2
    if report["counts"]["warnings"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
