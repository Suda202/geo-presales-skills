#!/usr/bin/env python3
"""海外 GEO 售前诊断报告 · 数据层校验

独立复算 ``report-data.json`` 里的关键数字，与产物逐项对账：

- 目标品牌提及率、声量份额、引用份额、平均提及位置、提及率排名（逐切片）
- 每个切片的 records 条数、competition 行集合、矩阵行集合
- 内部一致性：引用分类计数与总引用数、share 数组与 mention 行同序

复算完全不调用 ``build_report_data.py``；它直接从采集目录读原始 JSON，
用共享的品牌识别入口 ``find_alias_spans`` 与 ``meta.objects`` 里声明的别名
重新算一遍。``--self-test`` 会对产物做突变，确认校验能发现错误。

退出码 0 = 全部通过；非 0 = 有对账失败。
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

# 兄弟 skill 按相对位置定位：本脚本在 <skills>/<skill>/scripts/ 下。
# 脱离整套 skill 单独部署时，用 GEO_PRESALES_SKILLS_ROOT 指向 skills 根目录。
SKILLS_ROOT = Path(os.environ.get(
    "GEO_PRESALES_SKILLS_ROOT", str(Path(__file__).resolve().parents[2])))
CORE_DIR = SKILLS_ROOT / "geo-presales-report-editor" / "scripts"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from geo_presales_core.util import (  # noqa: E402
    domain_matches,
    find_alias_spans,
    normalize_host,
    normalize_text,
    normalize_url as core_normalize_url,
)

import geo_presales_core.util as core_util  # noqa: E402

# 品牌匹配必须与数据层一致地跑在去引用正文上，否则复算会重现「被引文章标题里的品牌
# 被算成提及」的旧行为，与本模块要校验的数据层对不上。见 build_report_data.py 的说明。
_AUDIT_SCRIPTS = SKILLS_ROOT / "geo-presales-report-audit" / "scripts"
if str(_AUDIT_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_AUDIT_SCRIPTS))
import de_cite_crawl as de_cite  # noqa: E402

core_util.COMMON_MULTI_LABEL_SUFFIXES |= {
    "com.my", "net.my", "org.my", "gov.my", "edu.my", "com.sg", "net.sg", "org.sg",
    "com.ph", "net.ph", "co.th", "or.th", "com.vn", "com.id", "co.id", "com.bn",
}
INGEST_TRACKING_KEYS = set(core_util.TRACKING_QUERY_KEYS) | {
    "srsltid", "gbraid", "wbraid", "yclid", "igshid", "gad_source", "gclsrc",
    "msclkid", "ref_src", "ref_url", "guccounter", "guce_referrer", "spm", "scm",
}

PLATFORM_DIR_BY_LABEL = {"AIO": "overview", "Gemini": "gemini",
                         "ChatGPT": "chatgpt", "Perplexity": "perplexity"}
# 回答正文与引用字段的已知映射。平台清单是发现出来的，未登记的平台回落到
# 默认字段名（正文 result_text、无独立引用字段），不因新平台直接崩。
DEFAULT_ANSWER_FIELD = "result_text"
ANSWER_FIELD = {"overview": "content", "gemini": "result_text",
                "chatgpt": "result_text", "perplexity": "result_text"}
CITATION_FIELD = {"overview": "source", "gemini": "citations",
                  "chatgpt": "content_references", "perplexity": "web_results"}


def answer_field(platform_dir: str) -> str:
    return ANSWER_FIELD.get(platform_dir, DEFAULT_ANSWER_FIELD)


def citation_field(platform_dir: str):
    return CITATION_FIELD.get(platform_dir)
# 正文引用标记。口径必须与 build_report_data.py 同步（正文优先、字段按位置回退），
# 但刻意独立实现：两侧都改才算一致，一侧漂移会在门禁里暴露。
BODY_REF_DEF = re.compile(r"^\s*\[(\d+)\]:\s*(\S+?)(?:\s+\"([^\"]*)\")?\s*$", re.M)
BODY_REF_MARKER = re.compile(r"\(\[([^\]\n]{1,80})\]\[(\d+)\]\)")
BODY_REF_MARKER_BARE = re.compile(r"(?<!\[)\[([^\]\n]{1,80})\]\[(\d+)\]")
PLATFORM_INTERNAL_HOSTS = {
    "google.com", "google.com.sg", "google.com.my", "google.co", "google.com.hk",
    "gstatic.com", "googleusercontent.com", "bing.com", "chatgpt.com", "openai.com",
    "perplexity.ai", "gemini.google.com",
}
DISCOVERY_LABEL = "发现"

TOLERANCE = 0.051  # 百分比 1 位小数的舍入余量


# ------------------------------------------------------------------ 复算

class Recomputer:
    """从采集目录重建切片口径，不依赖 build_report_data。"""

    def __init__(self, collect: Path, report: dict):
        self.collect = Path(collect)
        self.meta = report["meta"]
        self.objects = self.meta["objects"]
        self.questions = self.meta["questions"]
        self.regions = self.meta["regions"]
        self.platforms = self.meta["platforms"]
        self.topics = self.meta["topics"]
        # 平台清单随产物携带（数据层从采集目录发现）；旧产物没有该字段时回落内置映射
        self.platform_dirs = dict(self.meta.get("platform_dirs")
                                  or PLATFORM_DIR_BY_LABEL)
        self._text_cache: dict[tuple, str] = {}
        self._spans_cache: dict[tuple, list] = {}
        self._citations_cache: dict[tuple, list] = {}
        self._recompute_cache: dict[tuple, dict] = {}
        self._files_cache: dict[tuple, list] = {}

    # --- 原始读取 ---

    def sample_files(self, region: str, platform_dir: str, qid: int) -> list[Path]:
        """该题在该平台×市场下的采集文件，按文件名排序；索引即重复序号。

        归属优先按 ``task_result.prompt`` 与题库正文比对；**题面为空时回退文件名题号**。
        必须回退的原因与数据层一致：AIO 的响应没有 ``prompt`` 字段（100/100 为空）、
        ChatGPT 有 73/100 为空，只按题面归属会让这两条平台整批取不到文件，复算分母
        与数据层对不上。文件名回退只在题面为空时启用；题面存在但对不上任何题的仍
        视为错位，不靠文件名兜底。
        """
        key = (region, platform_dir, qid)
        if key not in self._files_cache:
            folder = self.collect / f"scraper.{platform_dir}" / region
            paths: list[Path] = []
            if folder.is_dir():
                by_prompt = {
                    normalize_text(q.get("en") or ""): f"{int(q['qid']):04d}"
                    for q in self.questions if q.get("en")
                }
                known = {f"{int(q['qid']):04d}" for q in self.questions}
                for path in sorted(folder.glob("*.json")):
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    result = payload.get("task_result") or {}
                    prompt = str(result.get("prompt") or "").strip()
                    matched = by_prompt.get(normalize_text(prompt)) if prompt else None
                    if not matched and not prompt:
                        stem = path.stem.strip()
                        if stem in known:
                            matched = stem
                        elif stem.isdigit() and stem.zfill(4) in known:
                            matched = stem.zfill(4)
                    # qid 在本模块是整数行号，matched 是补零字符串，统一后比较
                    if matched and str(matched).zfill(4) == str(qid).zfill(4):
                        paths.append(path)
            self._files_cache[key] = paths
        return self._files_cache[key]

    def repeat_count(self, region: str, platform_dir: str, qid: int) -> int:
        return len(self.sample_files(region, platform_dir, qid))

    def answer_text(self, region: str, platform_dir: str, qid: int, repeat: int = 1) -> str:
        key = (region, platform_dir, qid, repeat)
        if key not in self._text_cache:
            paths = self.sample_files(region, platform_dir, qid)
            text = ""
            if 0 < repeat <= len(paths):
                payload = json.loads(paths[repeat - 1].read_text(encoding="utf-8"))
                result = payload.get("task_result") or {}
                text = str(result.get(answer_field(platform_dir)) or "")
            self._text_cache[key] = text
        return self._text_cache[key]

    def mentions(self, region: str, platform_dir: str, qid: int, object_id: str,
                 repeat: int = 1) -> bool:
        return bool(self._spans(region, platform_dir, qid, object_id, repeat))

    def _spans(self, region: str, platform_dir: str, qid: int, object_id: str,
               repeat: int = 1) -> list[dict]:
        key = (region, platform_dir, qid, object_id, repeat)
        if key not in self._spans_cache:
            text = self.answer_text(region, platform_dir, qid, repeat)
            obj = next(o for o in self.objects if o["object_id"] == object_id)
            found = []
            if text.strip():
                # 与数据层同口径：先剥引用标记与商品卡商家列，再匹配品牌
                matching = de_cite.blank_merchant_columns(de_cite.strip_citations(text))
                found = find_alias_spans(matching, obj.get("aliases") or [obj["name"]])
            self._spans_cache[key] = found
        return self._spans_cache[key]

    def citations(self, region: str, platform_dir: str, qid: int,
                  repeat: int = 1) -> list[dict]:
        """引用次数 = 正文 pill（`([来源名][N])`）的出现次数。

        正文没有 pill 的回答计 0 条，不拿供应商字段充数。缺定义行的 pill 按位置
        回退解析 URL（解析，不是计数来源）；解析不出也**照样计入次数**，只是没有
        host/canonical_url——分母必须与数据层一致，否则门禁会报假差异。
        """
        key = (region, platform_dir, qid, repeat)
        if key not in self._citations_cache:
            paths = self.sample_files(region, platform_dir, qid)
            rows = []
            if 0 < repeat <= len(paths):
                payload = json.loads(paths[repeat - 1].read_text(encoding="utf-8"))
                result = payload.get("task_result") or {}
                text = str(result.get(answer_field(platform_dir)) or "")
                definitions = {}
                for number, url, _title in BODY_REF_DEF.findall(text):
                    definitions[number] = url
                spans, occurrences = [], []
                for match in BODY_REF_MARKER.finditer(text):
                    spans.append(match.span())
                    occurrences.append((match.group(2), match.start()))
                for match in BODY_REF_MARKER_BARE.finditer(text):
                    if any(start <= match.start() < end for start, end in spans):
                        continue
                    occurrences.append((match.group(2), match.start()))
                raw_items = result.get(citation_field(platform_dir))
                raw_items = raw_items if isinstance(raw_items, list) else []

                seen_canonical: set[str] = set()  # 仅 Gemini：同一 canonical 只计一次
                for number, position in occurrences:
                    line_start = text.rfind("\n", 0, position) + 1
                    in_table = text[line_start:].lstrip().startswith("|")
                    raw_url = definitions.get(number)
                    if not raw_url and number.isdigit() and 0 < int(number) <= len(raw_items):
                        item = raw_items[int(number) - 1]
                        if isinstance(item, dict):
                            raw_url = str(item.get("url") or item.get("link")
                                          or item.get("href") or "").strip()
                    url = _clean_url(raw_url) if raw_url else ""
                    host = normalize_host(url) if url else ""
                    if host and _is_platform_internal(host):
                        continue
                    # 去重键必须与数据层一致：core 的 canonical_url 会去掉 www. 与尾斜杠。
                    normalized = core_normalize_url(url) if url else None
                    canonical = (normalized or {}).get("canonical_url") or (url or None)
                    # Gemini 片段折叠：同一 canonical 只计一次（与 build_report_data 的
                    # _citation_entries 完全同口径），否则门禁会报假差异。解析不出 URL 的
                    # pill 无 canonical，照常各计一次。
                    if platform_dir == "gemini" and canonical:
                        if canonical in seen_canonical:
                            continue
                        seen_canonical.add(canonical)
                    rows.append({
                        "url": url or None,
                        "host": host or None,
                        "canonical_url": canonical,
                        "position": position,
                        "in_table_row": in_table,
                    })
            self._citations_cache[key] = rows
        return self._citations_cache[key]

    # --- 切片级复算 ---

    def slice_questions(self, topic: str) -> list[dict]:
        if not topic:
            return list(self.questions)
        return [q for q in self.questions if q["topic"] == topic]

    def slice_platforms(self, platform: str) -> list[str]:
        return [platform] if platform else list(self.platforms)

    def slice_regions(self, region: str) -> list[str]:
        """region 为 "" 表示「全部国家」：各市场样本合池。"""
        return [region] if region else list(self.regions)

    def recompute(self, region: str, platform: str, topic: str) -> dict:
        cache_key = (region, platform, topic)
        if cache_key in self._recompute_cache:
            return self._recompute_cache[cache_key]
        result = self._recompute(region, platform, topic)
        self._recompute_cache[cache_key] = result
        return result

    def _recompute(self, region: str, platform: str, topic: str) -> dict:
        question_ids = [q["qid"] for q in self.slice_questions(topic)]
        discovery_ids = [q["qid"] for q in self.slice_questions(topic)
                         if q["intent"] == DISCOVERY_LABEL]

        discovery_answers = 0          # 有效 discovery 回答数（分母）
        mention_counts: Counter = Counter()
        target_ranks: list[int] = []
        raw_citations = 0
        target_citations = 0
        own_citations: Counter = Counter()
        answer_unique_total = 0
        table_row_markers = 0
        unique_citation_urls: set[str] = set()
        target = next(o for o in self.objects if o["object_id"] == "target")

        for platform_label in self.slice_platforms(platform):
            platform_dir = self.platform_dirs[platform_label]
            for market in self.slice_regions(region):
                for qid in question_ids:
                    # 每题可能采了多次；每条有效回答都进分母
                    for repeat in range(1, self.repeat_count(market, platform_dir, qid) + 1):
                        if not self.answer_text(market, platform_dir, qid, repeat).strip():
                            continue  # 空答案不进任何分母
                        is_discovery = qid in discovery_ids
                        mentioned = [o["object_id"] for o in self.objects
                                     if self.mentions(market, platform_dir, qid,
                                                      o["object_id"], repeat)]
                        if is_discovery:
                            discovery_answers += 1
                            for object_id in mentioned:
                                mention_counts[object_id] += 1
                            if "target" in mentioned:
                                target_ranks.append(
                                    self._rank_of(market, platform_dir, qid,
                                                  target["object_id"], repeat))
                            seen_in_answer = set()
                            for citation in self.citations(market, platform_dir, qid, repeat):
                                raw_citations += 1
                                if citation.get("in_table_row"):
                                    table_row_markers += 1
                                # 解析不出 URL 的 pill 仍计入次数，但不进「去重来源」
                                if citation.get("canonical_url"):
                                    seen_in_answer.add(citation["canonical_url"])
                                    unique_citation_urls.add(citation["canonical_url"])
                                owner = self._official_owner(citation["host"])
                                if owner:
                                    own_citations[owner] += 1
                                    if owner == "target":
                                        target_citations += 1
                            answer_unique_total += len(seen_in_answer)

        total_mentions = sum(mention_counts.values())
        target_mentions = mention_counts.get("target", 0)
        order = sorted(self.objects,
                       key=lambda o: (-mention_counts.get(o["object_id"], 0), o["name"]))
        rank_lookup, last_value, last_rank = {}, None, 0
        for index, obj in enumerate(order, 1):
            value = mention_counts.get(obj["object_id"], 0)
            if value != last_value:
                last_rank, last_value = index, value
            rank_lookup[obj["object_id"]] = last_rank

        # 每个对象的独立口径，供逐行对账 competition.mention / matrix
        object_stats = {}
        own_ranks: dict[str, list[int]] = defaultdict(list)
        for platform_label in self.slice_platforms(platform):
            platform_dir = self.platform_dirs[platform_label]
            for market in self.slice_regions(region):
                for qid in discovery_ids:
                    for repeat in range(1, self.repeat_count(market, platform_dir, qid) + 1):
                        if not self.answer_text(market, platform_dir, qid, repeat).strip():
                            continue
                        for obj in self.objects:
                            if self._spans(market, platform_dir, qid, obj["object_id"], repeat):
                                own_ranks[obj["object_id"]].append(
                                    self._rank_of(market, platform_dir, qid,
                                                  obj["object_id"], repeat))
        for obj in self.objects:
            object_id = obj["object_id"]
            count = mention_counts.get(object_id, 0)
            ranks = own_ranks.get(object_id, [])
            object_stats[obj["name"]] = {
                "mention_rate": _pct(count / discovery_answers) if discovery_answers else "—",
                "share_of_voice": _pct(count / total_mentions) if total_mentions else "—",
                "average_rank": f"{sum(ranks) / len(ranks):.1f}" if ranks else "—",
                "mention_rank": str(rank_lookup[object_id]),
                "citation_share": (_pct(own_citations.get(object_id, 0) / raw_citations)
                                   if raw_citations else "—"),
                "mention_count": count,
            }

        return {
            "records": len(question_ids),
            "mention_rate": _pct(target_mentions / discovery_answers) if discovery_answers else "—",
            "share_of_voice": _pct(target_mentions / total_mentions) if total_mentions else "—",
            "official_share": _pct(target_citations / raw_citations) if raw_citations else "—",
            "average_rank": (f"{sum(target_ranks) / len(target_ranks):.1f}"
                             if target_ranks else "—"),
            "mention_rank": str(rank_lookup["target"]),
            "total_citations": None,   # 去重后条数，产物内自证
            "discovery_answers": discovery_answers,
            "object_stats": object_stats,
            "citation_units": {
                "occurrences": raw_citations,
                "unique_sources": len(unique_citation_urls),
                "occurrences_in_table_rows": table_row_markers,
            },
        }

    def _official_owner(self, host: str) -> str | None:
        """与后端 _classify_official 一致：按纳入对象顺序，第一个域名命中的胜出。"""
        for obj in self.objects:
            for domain in obj["domains"]:
                if domain_matches(host, domain):
                    return obj["object_id"]
        return None

    def _rank_of(self, region: str, platform_dir: str, qid: int, object_id: str,
                 repeat: int = 1) -> int:
        """目标品牌在该答案内的首次出现次序（按正文位置，同位置按配置顺序）。"""
        positioned = [
            (self._spans(region, platform_dir, qid, obj["object_id"], repeat)[0]["start"], index,
             obj["object_id"])
            for index, obj in enumerate(self.objects)
            if self._spans(region, platform_dir, qid, obj["object_id"], repeat)
        ]
        positioned.sort(key=lambda item: (item[0], item[1]))
        order = [item[2] for item in positioned]
        return order.index(object_id) + 1


def _clean_url(raw_url: str) -> str:
    try:
        parts = urlsplit(str(raw_url))
        pairs = parse_qsl(parts.query, keep_blank_values=True)
    except ValueError:
        return str(raw_url)
    if not pairs:
        return str(raw_url)
    kept = [(k, v) for k, v in pairs if k.casefold() not in INGEST_TRACKING_KEYS]
    if len(kept) == len(pairs):
        return str(raw_url)
    from urllib.parse import urlencode, urlunsplit
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(kept), parts.fragment))


def _is_platform_internal(host: str) -> bool:
    return any(host == h or host.endswith("." + h) for h in PLATFORM_INTERNAL_HOSTS)


def _pct(frac) -> str:
    return f"{frac * 100:.1f}%"


def _num(value) -> float | None:
    if value is None:
        return None
    text = str(value).replace("%", "").replace("—", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _close(actual, expected) -> bool:
    a, e = _num(actual), _num(expected)
    if a is None or e is None:
        return a is None and e is None
    return abs(a - e) <= TOLERANCE


# ------------------------------------------------------------------ 校验

def run_checks(report: dict, collect: Path) -> list[str]:
    failures: list[str] = []
    if report.get("schema") != "geo-presales-report-data/v1":
        failures.append(f"schema 非法：{report.get('schema')!r}")

    meta = report.get("meta") or {}
    for field in ("brand", "brand_display", "official_domain", "category", "generated_at",
                  "regions", "platforms", "topics", "intents", "tags",
                  "questions"):
        if field not in meta:
            failures.append(f"meta 缺少字段 {field}")
    # 情感由 attach_sentiment.py 单独接入：接入前标 pending，接入后标 complete。
    # 只在「标了 complete 却没有任何情感数据」时报错，避免占位数据冒充成果。
    status = meta.get("sentiment_claims_status")
    if status not in {"pending", "complete"}:
        failures.append(f"meta.sentiment_claims_status 取值异常：{status!r}")
    elif status == "complete":
        has_sentiment = any(
            (slice_value.get("sentiment") or {}).get("summary", {}).get("total")
            for slice_value in report.get("slices", {}).values()
        )
        if not has_sentiment:
            failures.append("sentiment_claims_status=complete 但全部切片情感样本为 0")
    # 题数由题库决定：按采集次数展开是 75 行、按真实题目是 5 行，都不是固定值。
    # 这里只校验结构自洽，不写死条数（旧版写死 50 是 Bewinch 案例的形态）。
    questions = meta.get("questions") or []
    if not questions:
        failures.append("meta.questions 为空")
    else:
        qids = [q.get("qid") for q in questions]
        if any(qid is None for qid in qids):
            failures.append("meta.questions 存在缺失 qid 的条目")
        elif sorted(qids) != list(range(1, len(qids) + 1)):
            failures.append(f"meta.questions 的 qid 应为 1..{len(qids)} 连续")
        incomplete = [q.get("qid") for q in questions
                      if not str(q.get("en") or "").strip()
                      or not str(q.get("topic") or "").strip()]
        if incomplete:
            failures.append(f"meta.questions 缺 en/topic：{incomplete[:5]}")
        question_topics = {q.get("topic") for q in questions}
        if question_topics != set(meta.get("topics") or []):
            failures.append("meta.questions 覆盖的主题与 meta.topics 不一致")

    recomputer = Recomputer(collect, report)
    slices = report.get("slices") or {}

    expected_keys = set()
    for region in [""] + list(meta["regions"]):
        for platform in [""] + meta["platforms"]:
            for topic in [""] + meta["topics"]:
                expected_keys.add(f"{region}|{platform}|{topic}")
    missing = expected_keys - set(slices)
    extra = set(slices) - expected_keys
    if missing:
        failures.append(f"缺少切片 {sorted(missing)[:5]}（共 {len(missing)}）")
    if extra:
        failures.append(f"多出切片 {sorted(extra)[:5]}（共 {len(extra)}）")

    for region in [""] + list(meta["regions"]):
        for platform in [""] + meta["platforms"]:
            for topic in [""] + meta["topics"]:
                key = f"{region}|{platform}|{topic}"
                slc = slices.get(key)
                if slc is None:
                    continue
                failures.extend(_check_slice(key, slc, recomputer, region, platform, topic, meta))

    # 全局：每个 region 的全量切片必须齐备，sentiment 结构完整
    for key, slc in slices.items():
        sentiment = slc.get("sentiment") or {}
        if "summary" not in sentiment or "claims" not in sentiment or "matrix" not in sentiment:
            failures.append(f"{key}: sentiment 结构不完整")
        for metric in ("mention", "share", "rank", "sent", "official"):
            if metric not in (slc.get("matrix") or {}):
                failures.append(f"{key}: matrix 缺少 {metric}")

    # 内容规划的官网清单按「目标品牌本该出现却没进回答」取，判据必须与已校验的
    # mention_rate 自洽——两者矛盾时清单会静默换一批题，页面看不出问题。
    for key, slc in slices.items():
        for record in slc.get("records") or []:
            qid = record.get("qid")
            for flag in ("discovery", "target_in_question"):
                if not isinstance(record.get(flag), bool):
                    failures.append(f"{key}: 题 {qid} 的 {flag} 不是布尔值")
            rate, mentioned = record.get("mention_rate"), record.get("mentioned")
            if rate == "—":
                if mentioned is not None:
                    failures.append(f"{key}: 题 {qid} 无有效答案，mentioned 应为 null")
            elif not isinstance(mentioned, bool):
                failures.append(f"{key}: 题 {qid} 的 mentioned 不是布尔值")
            elif mentioned != (rate != "0.0%"):
                failures.append(f"{key}: 题 {qid} 的 mentioned={mentioned} 与 "
                                f"mention_rate={rate} 矛盾")
    return failures


def _check_slice(key, slc, recomputer, region, platform, topic, meta) -> list[str]:
    out = []
    expected = recomputer.recompute(region, platform, topic)
    kpis = slc.get("kpis") or {}

    if len(slc.get("records") or []) != expected["records"]:
        out.append(f"{key}: records 条数 {len(slc.get('records') or [])} != 期望 {expected['records']}")
    for field in ("mention_rate", "share_of_voice", "official_share", "average_rank",
                  "mention_rank"):
        if not _close(kpis.get(field), expected[field]):
            out.append(f"{key}: kpis.{field} {kpis.get(field)!r} != 复算 {expected[field]!r}")

    competition = slc.get("competition") or {}
    mention = competition.get("mention") or []
    share = competition.get("share") or []
    if len(mention) != len(share):
        out.append(f"{key}: competition.mention 与 share 行数不一致")
    if not mention:
        out.append(f"{key}: competition.mention 为空")
    else:
        stats = expected["object_stats"]
        for row in mention:
            name = str(row[0]).replace("★", "").strip()
            peer = stats.get(name)
            if peer is None:
                out.append(f"{key}: competition.mention 出现未纳入对象 {name!r}")
                continue
            if not _close(row[2], peer["mention_rate"]):
                out.append(f"{key}: competition.mention[{name}].rate {row[2]!r} "
                           f"!= 复算 {peer['mention_rate']!r}")
            if str(row[5]) != peer["mention_rank"]:
                out.append(f"{key}: competition.mention[{name}].rank {row[5]!r} "
                           f"!= 复算 {peer['mention_rank']!r}")
        target_row = next((r for r in mention if str(r[0]).endswith("★")), None)
        if target_row is None:
            out.append(f"{key}: competition.mention 缺少目标品牌行")
        rates = [_num(r[2]) or 0 for r in mention]
        if any(rates[i] < rates[i + 1] - TOLERANCE for i in range(len(rates) - 1)):
            out.append(f"{key}: competition.mention 未按提及率降序")
        # 开放品牌词表允许无域名（参考词表 96 个里 43 个为空），展示行因此可以为空。
        # 只有该对象在词表里声明了域名、展示行却为空时才算缺陷。
        if not all(normalize_text(r[1]) for r in mention):
            objects = meta.get("objects") or []
            if not objects:
                out.append(f"{key}: competition.mention 存在空域名")
            else:
                declared = {
                    str(o.get("name") or "").strip()
                    for o in objects
                    if any(str(d).strip() for d in (o.get("domains") or []))
                }
                lacking = [
                    str(r[0]).replace("★", "").strip()
                    for r in mention
                    if not normalize_text(r[1])
                    and str(r[0]).replace("★", "").strip() in declared
                ]
                if lacking:
                    out.append(f"{key}: competition.mention 展示行缺域名（词表内有域名）：{lacking}")
        for index, row in enumerate(mention):
            name = str(row[0]).replace("★", "").strip()
            peer = stats.get(name)
            if peer is None or index >= len(share):
                continue
            if not _close(share[index], peer["share_of_voice"]):
                out.append(f"{key}: competition.share[{name}] {share[index]!r} "
                           f"!= 复算 {peer['share_of_voice']!r}")

    rank_rows = competition.get("rank") or []
    stats = expected["object_stats"]
    if len(rank_rows) != len(mention):
        out.append(f"{key}: competition.rank 行数 {len(rank_rows)} != competition.mention "
                   f"{len(mention)}")
    for row in rank_rows:
        name = str(row[0]).replace("★", "").strip()
        peer = stats.get(name)
        if peer is None:
            out.append(f"{key}: competition.rank 出现未纳入对象 {name!r}")
            continue
        if not _close(row[2], peer["average_rank"]):
            out.append(f"{key}: competition.rank[{name}] {row[2]!r} "
                       f"!= 复算 {peer['average_rank']!r}")
        if len(row) > 3 and row[3] != "target":
            out.append(f"{key}: competition.rank 第 4 项只能是 target，得到 {row[3]!r}")
        if len(row) > 3 and not str(row[0]).endswith("★"):
            out.append(f"{key}: competition.rank 标记 target 的行品牌名未带 ★")

    sources = slc.get("sources") or {}
    types = sources.get("types") or []
    if len(types) != 7:
        out.append(f"{key}: sources.types 应为 7 类，实际 {len(types)}")
    else:
        counts = sum(int(r[2]) for r in types)
        if counts != sources.get("total_citations"):
            out.append(f"{key}: sources.types 计数和 {counts} != total_citations "
                       f"{sources.get('total_citations')}")
        pct_sum = sum(_num(r[1]) or 0 for r in types)
        if abs(pct_sum - 100) > 0.5:
            out.append(f"{key}: sources.types 百分比合计 {pct_sum:.1f} != 100")

    # 引用两种计法：次数按标记出现、来源清单去重。两者必须同时给出且各自可复算。
    units = sources.get("citation_units") or {}
    expected_units = (expected or {}).get("citation_units") or {}
    if not units:
        out.append(f"{key}: sources.citation_units 缺失")
    else:
        for field in ("occurrences", "unique_sources", "occurrences_in_table_rows"):
            if units.get(field) != expected_units.get(field):
                out.append(f"{key}: sources.citation_units.{field} "
                           f"{units.get(field)!r} != 复算 {expected_units.get(field)!r}")
    if not _close(sources.get("official_share"), expected["official_share"]):
        out.append(f"{key}: sources.official_share {sources.get('official_share')!r} "
                   f"!= 复算 {expected['official_share']!r}")

    matrix = slc.get("matrix") or {}
    if (matrix.get("platforms") or []) != meta["platforms"]:
        out.append(f"{key}: matrix.platforms 与 meta.platforms 不一致")
    metric_field = {"mention": "mention_rate", "share": "share_of_voice",
                    "rank": "average_rank", "official": "citation_share"}
    for metric in ("mention", "share", "rank", "sent", "official"):
        rows = matrix.get(metric) or []
        if len(rows) != len(mention):
            out.append(f"{key}: matrix.{metric} 行数 {len(rows)} != competition {len(mention)}")
        for row in rows:
            vals = row.get("vals") or []
            if len(vals) != len(meta["platforms"]):
                out.append(f"{key}: matrix.{metric} 某行 vals 长度不符")
                break
            name = str(row.get("name") or "").replace("★", "").strip()
            if metric == "sent":
                if any(value is not None for value in vals):
                    out.append(f"{key}: matrix.sent 应为空（判读待补）")
                continue
            for index, platform_label in enumerate(meta["platforms"]):
                peer = recomputer.recompute(region, platform_label, topic)["object_stats"].get(name)
                if peer is None:
                    continue
                if not _close(vals[index], peer[metric_field[metric]]):
                    out.append(f"{key}: matrix.{metric}[{name}][{platform_label}] "
                               f"{vals[index]!r} != 复算 {peer[metric_field[metric]]!r}")
    return out


# ------------------------------------------------------------------ 突变测试

def _mutations(base: dict):
    def mutate(description, path, action):
        target = copy.deepcopy(base)
        node = target
        for part in path:
            node = node[part]
        action(node)
        return description, target

    # 切片键从产物本身取，不写死市场与主题：旧版写死 MY / SG / 台式净饮机，
    # 换一个市场或主题的 Case（如 US + LED 驱动电源）会直接 KeyError。
    slices = base.get("slices") or {}
    meta = base.get("meta") or {}
    markets = [str(m) for m in (meta.get("regions") or [])]
    platforms = [str(p) for p in (meta.get("platforms") or [])]
    topics = [str(t) for t in (meta.get("topics") or [])]

    def first_key(candidates):
        return next((k for k in candidates if k in slices and slices[k]), None)

    market_keys = [f"{m}||" for m in markets]
    key_a = first_key(market_keys) or first_key(slices.keys())
    key_b = first_key(market_keys[1:]) or key_a
    key_plat_topic = first_key(
        [f"|{p}|{t}" for p in platforms for t in topics]) or key_a
    key_market_plat_topic = first_key(
        [f"{m}|{p}|{t}" for m in markets for p in platforms for t in topics]) or key_a
    key_all = "||" if "||" in slices else key_a

    def has(keys, field):
        return next((k for k in keys
                     if slices.get(k) and slices[k].get(field)), None)

    key_rank = has([key_plat_topic, key_a, key_b, key_all], "competition") or key_a
    key_types = has([key_market_plat_topic, key_plat_topic, key_a], "sources") or key_a

    def matrix_index(keys, metric, want):
        """找一个 vals 长度 > want 的切片，避免单平台 Case 越界。"""
        for key in keys:
            rows = ((slices.get(key) or {}).get("matrix") or {}).get(metric) or []
            if rows and len(rows[0].get("vals") or []) > want:
                return key, want
        for key in keys:
            rows = ((slices.get(key) or {}).get("matrix") or {}).get(metric) or []
            if rows and rows[0].get("vals"):
                return key, 0
        return key_a, 0

    key_matrix_mention, idx_matrix_mention = matrix_index(
        [key_a, key_b, key_all], "mention", 0)
    key_matrix_rank, idx_matrix_rank = matrix_index(
        [key_b, key_a, key_all], "rank", 1)
    rows_with_target = next(
        (k for k in slices
         if any(str(r[0]).endswith("★") for r in
                (slices[k].get("competition") or {}).get("mention") or [])),
        key_a)

    return [
        mutate(f"把 {key_a} 全量提及率改高", ["slices", key_a, "kpis"],
               lambda n: n.__setitem__("mention_rate", "99.0%")),
        mutate(f"把 {key_b} 声量份额改高", ["slices", key_b, "kpis"],
               lambda n: n.__setitem__("share_of_voice", "40.0%")),
        mutate(f"把 {key_a} 引用份额改高", ["slices", key_a, "kpis"],
               lambda n: n.__setitem__("official_share", "20.0%")),
        mutate(f"把 {key_b} 平均提及位置改成 1.2", ["slices", key_b, "kpis"],
               lambda n: n.__setitem__("average_rank", "1.2")),
        mutate(f"把 {key_a} 提及率排名改成 1", ["slices", key_a, "kpis"],
               lambda n: n.__setitem__("mention_rank", "1")),
        mutate(f"删掉 {key_a} 全量切片的一行 records", ["slices", key_a, "records"],
               lambda n: n.pop() if n else None),
        mutate(f"篡改 {rows_with_target} 竞品条里目标品牌的提及率",
               ["slices", rows_with_target, "competition", "mention"],
               lambda n: n[[i for i, r in enumerate(n) if str(r[0]).endswith("★")][0]]
               .__setitem__(2, "88.0%")),
        mutate(f"篡改 {key_a} 竞品条里开放品牌的提及率",
               ["slices", key_a, "competition", "mention"],
               lambda n: n[0].__setitem__(2, "88.0%")),
        mutate(f"篡改 {key_b} 声量份额数组第一项",
               ["slices", key_b, "competition", "share"],
               lambda n: n.__setitem__(0, 45.0)),
        mutate(f"篡改 {key_matrix_mention} 平台矩阵的提及率",
               ["slices", key_matrix_mention, "matrix", "mention"],
               lambda n: n[0]["vals"].__setitem__(idx_matrix_mention, 99.0)),
        mutate(f"把 {key_matrix_rank} 平台矩阵的平均位置改成 1.0",
               ["slices", key_matrix_rank, "matrix", "rank"],
               lambda n: n[0]["vals"].__setitem__(idx_matrix_rank, 1.0)),
        mutate(f"删掉 {key_rank} 切片 competition.rank 一行",
               ["slices", key_rank, "competition", "rank"],
               lambda n: n.pop() if n else None),
        mutate(f"把 {key_b} 切片引用总数加 7", ["slices", key_b, "sources"],
               lambda n: n.__setitem__("total_citations", n["total_citations"] + 7)),
        mutate(f"删掉 {key_types} 切片 sources.types 一行",
               ["slices", key_types, "sources", "types"],
               lambda n: n.pop() if n else None),
        mutate(f"改高「全部国家」全量切片提及率", ["slices", key_all, "kpis"],
               lambda n: n.__setitem__("mention_rate", "66.0%")),
        mutate("改高「全部国家」平台×主题切片声量份额",
               ["slices", key_plat_topic, "kpis"],
               lambda n: n.__setitem__("share_of_voice", "30.0%")),
        mutate("删掉「全部国家」全量切片一行 records", ["slices", key_all, "records"],
               lambda n: n.pop() if n else None),
        mutate("篡改「全部国家」切片引用总数", ["slices", key_all, "sources"],
               lambda n: n.__setitem__("total_citations", n["total_citations"] - 5)),
        mutate("把 sentiment_claims_status 改成 done", ["meta"],
               lambda n: n.__setitem__("sentiment_claims_status", "done")),
        mutate(f"把 {key_a} 某题的 discovery 改成字符串", ["slices", key_a, "records"],
               lambda n: n[0].__setitem__("discovery", "yes") if n else None),
        mutate(f"把 {key_a} 某题的 target_in_question 改成字符串",
               ["slices", key_a, "records"],
               lambda n: n[0].__setitem__("target_in_question", "yes") if n else None),
        mutate(f"把 {key_a} 某题的 mentioned 改成字符串", ["slices", key_a, "records"],
               lambda n: n[0].__setitem__("mentioned", "yes") if n else None),
    ]


def self_test(report_path: Path, collect: Path) -> int:
    base = json.loads(report_path.read_text(encoding="utf-8"))
    original = run_checks(base, collect)
    print(f"baseline: {'通过' if not original else '失败：' + str(original[:2])}")
    if original:
        print("基线未通过，突变测试失去意义", file=sys.stderr)
        return 1

    failed = []
    with tempfile.TemporaryDirectory(prefix="geoverify-") as tmp:
        for index, (description, mutated) in enumerate(_mutations(base), 1):
            path = Path(tmp) / f"mutated-{index}.json"
            path.write_text(json.dumps(mutated, ensure_ascii=False), encoding="utf-8")
            problems = run_checks(json.loads(path.read_text(encoding="utf-8")), collect)
            status = "检出" if problems else "漏检"
            print(f"  突变 {index:2d} [{status}] {description}")
            if not problems:
                failed.append(description)
    if failed:
        print(f"突变测试失败：{len(failed)} 个错误未被发现 -> {failed}", file=sys.stderr)
        return 1
    print(f"突变测试通过：{len(_mutations(base))} 个注入错误全部检出")
    return 0


# ------------------------------------------------------------------ 主流程

def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="校验 report-data.json")
    parser.add_argument("--report", type=Path, required=True,
                        help="待校验的 report-data.json")
    parser.add_argument("--collect", type=Path, required=True,
                        help="产出该报告的采集目录，用于独立复算")
    parser.add_argument("--self-test", action="store_true",
                        help="对产物做突变，确认校验能发现错误")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if not args.report.exists():
        print(f"找不到产物：{args.report}", file=sys.stderr)
        return 1
    if args.self_test:
        return self_test(args.report, args.collect)

    report = json.loads(args.report.read_text(encoding="utf-8"))
    failures = run_checks(report, args.collect)
    slices = report.get("slices") or {}
    recomputer = Recomputer(args.collect, report)
    print(f"切片 {len(slices)} 个；对象 {len(recomputer.objects)} 个")
    for region in [""] + list(report["meta"]["regions"]):
        key = f"{region}||"
        expected = recomputer.recompute(region, "", "")
        kpis = slices.get(key, {}).get("kpis", {})
        print(f"  {key:8s}: 提及率 {kpis.get('mention_rate')}（复算 {expected['mention_rate']}）  "
              f"声量份额 {kpis.get('share_of_voice')}（复算 {expected['share_of_voice']}）  "
              f"引用份额 {kpis.get('official_share')}（复算 {expected['official_share']}）  "
              f"discovery 分母 {expected['discovery_answers']}")
    if failures:
        print(f"\n校验失败 {len(failures)} 项：", file=sys.stderr)
        for item in failures[:40]:
            print(f"  - {item}", file=sys.stderr)
        return 1
    print(f"\n校验通过：{len(slices)} 个切片全部与独立复算一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
