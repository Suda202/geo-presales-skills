#!/usr/bin/env python3
"""海外 GEO 售前诊断报告 · 数据层

把爬虫采集的原始 JSON（多市场 × 多平台 × 多题）算成渲染层直接消费的
``report-data.json``（契约见 ../references/report-data-contract.md）。

设计要点
--------
1. **复用后端指标实现**：可见度 / 声量 / 平均提及位置 / 引用，全部走
   ``geo_presales_core`` 的 ``prepare_answers`` 与 ``compute_metrics``，
   不重写任何指标逻辑。品牌识别唯一入口是 ``util.find_alias_spans``。
2. **绕过输入校验层**：``normalize_config`` / ``normalize_question_bank`` 硬性
   拒绝非美国市场和非 ChatGPT 平台（config.py:139-147）。本任务为 MY + SG
   两个市场、AIO/Gemini/ChatGPT/Perplexity 四个平台，因此这里直接构造它们
   产出的内部结构（``config`` 与 ``question_bank`` 两个 dict 的最终形态），
   再交给后端函数使用。
3. **区域维度**：``compute_metrics`` 本身没有国家概念。按 (region, platform,
   topic) 组合分别取样本子集跑，切片键见契约。
4. **空答案不进分母**：正文 strip 后为空 → ``analysis_eligible=False`` →
   该答案 ``validity=invalid``，被 ``_valid_answers`` 过滤掉，不进 discovery
   集，也不进任何比率分母。
6. **重复采集全部进分母**：每题采多次时，每条有效回答都进指标分母；
   ``selected_for_report`` 只标记「明细展示哪一条」，不决定算哪几条。
5. **开放品牌集**：``config["objects"]`` = 目标品牌 + 3 个配置竞品 + 开放品牌
   词表中的品牌。词表由另一任务生成，可能尚不存在；不存在时只用配置品牌跑通。

用法::

    python3 build_report_data.py \
        --collect  <采集目录> \
        --questions <题库 CSV> \
        --case <Case JSON> \
        --lexicon <品牌词表 JSON> \
        --out <report-data.json 输出路径>
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# ---------------------------------------------------------------- 后端指标实现

# 兄弟 skill 按相对位置定位：本脚本在 <skills>/<skill>/scripts/ 下。
# 脱离整套 skill 单独部署时，用 GEO_PRESALES_SKILLS_ROOT 指向 skills 根目录。
SKILLS_ROOT = Path(os.environ.get(
    "GEO_PRESALES_SKILLS_ROOT", str(Path(__file__).resolve().parents[2])))
CORE_DIR = SKILLS_ROOT / "geo-presales-report-editor" / "scripts"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

import geo_presales_core.util as core_util  # noqa: E402
from geo_presales_core.config import all_objects
from geo_presales_core.deterministic import prepare_answers  # noqa: E402
from geo_presales_core.crawler import answer_validity
from geo_presales_core.metrics import compute_metrics  # noqa: E402
from geo_presales_core.util import (  # noqa: E402
    normalize_host,
    normalize_text,
    sha256_obj,
    write_json,
)

# 去引用清洗：品牌匹配必须跑在剥离了引用标记与商品卡商家列的正文上，否则被引文章的
# 标题（如 "...car cameras by Garmin, Nextbase, 70mai and more"）里的品牌会被
# find_alias_spans 当成提及——这是 geo-presales-report-audit 已记录的错误类型
# 「引用锚文本公司名误计为品牌」。引用统计仍用原文，标记要被解出来。
AUDIT_SCRIPTS = SKILLS_ROOT / "geo-presales-report-audit" / "scripts"
if str(AUDIT_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(AUDIT_SCRIPTS))
import de_cite_crawl as de_cite  # noqa: E402

# 后端 registrable_domain 只用「常见多级后缀表」做展示层聚合，表里缺 SEA 市场的
# 二级后缀（如 .com.my）。缺了会把所有马来西亚站点并成一个 "com.my" 桶。这里把
# 后端自己声明为近似的这张表补全；官方域名匹配走注意 domain_matches，不依赖此表，
# 因此本扩充只影响展示层的域名聚合，**不改变任何指标**。
core_util.COMMON_MULTI_LABEL_SUFFIXES |= {
    "com.my", "net.my", "org.my", "gov.my", "edu.my", "com.sg", "net.sg", "org.sg",
    "com.ph", "net.ph", "co.th", "or.th", "com.vn", "com.id", "co.id", "com.bn",
}

# 后端 normalize_url 会剥离 utm_* 与一组跟踪参数，但缺 srsltid 等 Google 新参数。
# 采集侧在入口补齐同类跟踪参数，避免同一页面被计成多条引用。
INGEST_TRACKING_KEYS = set(core_util.TRACKING_QUERY_KEYS) | {
    "srsltid", "gbraid", "wbraid", "yclid", "igshid", "gad_source", "gclsrc",
    "msclkid", "ref_src", "ref_url", "guccounter", "guce_referrer", "spm", "scm",
}

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DOMAIN_CACHE = SKILL_DIR / "assets" / "domain-categories.json"
SCHEMA = "geo-presales-report-data/v1"
# 运行标识，写进产物 meta 供人工追溯；不参与任何计算与校验。
RUN_ID = os.environ.get("GEO_PRESALES_RUN_ID", "")

# platform 目录名 -> 平台显示名（渲染层 tab 顺序）
# 平台展示名。只登记「目录名 → 展示名」的已知映射，平台清单本身从采集目录发现，
# 不在这里写死要采哪几个平台；未知目录直接用它自己的目录名当展示名。
KNOWN_PLATFORM_LABELS = {
    "overview": "AIO",
    "gemini": "Gemini",
    "chatgpt": "ChatGPT",
    "perplexity": "Perplexity",
    "aimode": "AI Mode",
    "doubao": "豆包",
    "deepseek": "DeepSeek",
}


def discover_platforms(collect_dir: Path) -> list[tuple[str, str]]:
    """从采集目录发现平台：存在哪些 scraper.<name> 就以哪些为准。"""
    found = []
    for child in sorted(Path(collect_dir).iterdir()):
        if not child.is_dir() or not child.name.startswith("scraper."):
            continue
        name = child.name.split(".", 1)[1]
        if name:
            found.append((name, KNOWN_PLATFORM_LABELS.get(name, name)))
    if not found:
        raise SystemExit(f"采集目录里没有任何 scraper.<平台> 子目录：{collect_dir}")
    return found


def discover_regions(collect_dir: Path, platforms: list[tuple[str, str]]) -> list[str]:
    """从采集目录发现市场代码，按首次出现顺序。"""
    regions: list[str] = []
    for name, _label in platforms:
        platform_dir = Path(collect_dir) / f"scraper.{name}"
        for child in sorted(platform_dir.iterdir()):
            if child.is_dir() and child.name not in regions:
                regions.append(child.name)
    if not regions:
        raise SystemExit(f"采集目录下没有市场子目录：{collect_dir}")
    return regions


def configure_platforms(platforms: list[tuple[str, str]]) -> None:
    """按实际采集目录设定平台集合。

    本模块的切片、矩阵与元信息都由模块级常量取平台列表，这里集中重绑一次，
    避免把同一份清单穿进六处函数签名。
    """
    global PLATFORMS, PLATFORM_DIRS, PLATFORM_LABELS, LABEL_TO_DIR, DIR_TO_LABEL
    PLATFORMS = list(platforms)
    PLATFORM_DIRS = [name for name, _ in PLATFORMS]
    PLATFORM_LABELS = [label for _, label in PLATFORMS]
    LABEL_TO_DIR = {label: name for name, label in PLATFORMS}
    DIR_TO_LABEL = {name: label for name, label in PLATFORMS}


PLATFORMS: list[tuple[str, str]] = []
PLATFORM_DIRS: list[str] = []
PLATFORM_LABELS: list[str] = []
LABEL_TO_DIR: dict[str, str] = {}
DIR_TO_LABEL: dict[str, str] = {}

# 正文字段：overview 用 content，其余用 result_text
ANSWER_FIELD = {"overview": "content", "gemini": "result_text",
                "chatgpt": "result_text", "perplexity": "result_text"}
# 引用字段：逐平台不同
CITATION_FIELD = {"overview": "source", "gemini": "citations",
                  "chatgpt": "content_references", "perplexity": "web_results"}

# 正文引用标记。四平台格式一致：定义行 `[3]: https://… "标题"`，行内标记 `([来源名][3])`。
_BODY_REF_DEF = re.compile(r"^\s*\[(\d+)\]:\s*(\S+?)(?:\s+\"([^\"]*)\")?\s*$", re.M)
_BODY_REF_MARKER = re.compile(r"\(\[([^\]\n]{1,80})\]\[(\d+)\]\)")
_BODY_REF_MARKER_BARE = re.compile(r"(?<!\[)\[([^\]\n]{1,80})\]\[(\d+)\]")

# 平台站内跳转 / 聚合页链接，按契约丢弃
PLATFORM_INTERNAL_HOSTS = {
    "google.com", "google.com.sg", "google.com.my", "google.co", "google.com.hk",
    "gstatic.com", "googleusercontent.com", "bing.com", "chatgpt.com", "openai.com",
    "perplexity.ai", "gemini.google.com",
}

# 题库 diagnosis_intent -> 后端 diagnostic_intent（意图口径 shared/canonical-intent-mapping.md）
# 题库 diagnosis_intent -> 后端 diagnostic_intent。
# 键取 shared/canonical-intent-mapping.md 的全集，两种拼写都收：规范表写的是
# `Intent: Verification`，但题库实际用的是 `verification`，缺了会直接中断构建
# （Bewinch 题库只有 4 种意图，换到 edgelight 的 6 种才暴露）。
CSV_INTENT_MAP = {
    "discovery": "discovery",
    "competitor": "competitor",
    "validation": "validation",
    "verification": "validation",
    "accuracy": "accuracy",
    "evaluation": "sentiment",
    "sentiment": "sentiment",
    "category_awareness": "market_perception",
    "market_perception": "market_perception",
}
# 后端 diagnostic_intent -> 中文客户标签
INTENT_LABEL = {
    "discovery": "发现",
    "competitor": "竞品",
    "validation": "验证",
    "accuracy": "准确性",
    "sentiment": "评价",
    "market_perception": "品类认知",
}
INTENT_ORDER = ["discovery", "competitor", "validation", "accuracy", "sentiment",
                "market_perception"]
# questions.py 的 v5 推导：competitor->comparison，validation/accuracy/sentiment->decision
FUNNEL_OVERRIDE = {"competitor": "comparison", "validation": "decision",
                   "accuracy": "decision", "sentiment": "decision"}

# 后端 source_type -> 契约固定 7 类中文名 + 填充色
# 后端 source_type -> 报告展示的 7 类（以现行《引用来源分类》定义为准，不得增删）
SOURCE_BUCKET = {
    "brand_official": ("自有网站", "green"),
    "competitor_official": ("竞品网站", "amber"),
    "media_review": ("媒体网站", "cyan"),
    "ugc": ("社交平台", "blue"),
    "press_release": ("新闻稿平台", "red"),
    "institutional": ("机构网站", ""),
    "other": ("其他", ""),
    # 兼容旧值：历史数据或缓存里可能仍有这两个键
    "corporate_site": ("其他", ""),
    "encyclopedia_reference": ("机构网站", ""),
}
SOURCE_BUCKET_ORDER = ["自有网站", "社交平台", "媒体网站", "竞品网站", "新闻稿平台",
                       "机构网站", "其他"]
COMPETITION_FILLS = ["blue", "cyan", "green", "amber", "red"]


# ------------------------------------------------------------------ 小工具

def readable_tags(raw_tags):
    """把 Prompt Bank 的原始 tag 串转成报告里可读的标签。

    `Intent: X` 已单独成列，这里丢弃；`Brand Scope: Branded/Non-Branded`
    转成「品牌词 / 非品牌词」；其余自定义 tag 原样保留。
    """
    labels = []
    for item in raw_tags:
        tag = str(item or "").strip()
        if not tag:
            continue
        if tag.startswith("Intent:"):
            continue
        if tag.startswith("Brand Scope:"):
            scope = tag.split(":", 1)[1].strip().casefold()
            label = "非品牌词" if scope.startswith("non") else "品牌词"
        else:
            label = tag
        if label not in labels:
            labels.append(label)
    return labels


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fmt_pct(frac, digits: int = 1) -> str:
    if frac is None:
        return "—"
    return f"{frac * 100:.{digits}f}%"


def fmt_num(value, digits: int = 1) -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f}"


def bar_width(value, max_value) -> str:
    if value is None or not max_value or max_value <= 0:
        return "0%"
    pct = value / max_value * 100
    return "100%" if pct >= 99.95 else f"{pct:.1f}%"


def pct_num(value):
    return None if value is None else round(value * 100, 1)


def round1(value):
    return None if value is None else round(value, 1)


def is_platform_internal(host: str) -> bool:
    return any(host == h or host.endswith("." + h) for h in PLATFORM_INTERNAL_HOSTS)


def clean_url(raw_url: str) -> str:
    """入口侧剥离跟踪参数（后端 normalize_url 同类行为的补集），保留路径与分片。"""
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
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(kept), parts.fragment))


# ------------------------------------------------------------------ 输入读取

def load_case(path: Path) -> dict:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))

    def pick(*names):
        for name in names:
            value = raw.get(name)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    brand, domain, category = pick("品牌名称"), pick("官方域名"), pick("品类")
    competitors = []
    for index in (1, 2, 3):
        name, comp_domain = pick(f"竞品 {index}"), pick(f"竞品 {index} 官网域名")
        if name and comp_domain:
            competitors.append({"name": name, "domain": comp_domain})
    if not brand or not domain:
        raise SystemExit("Case JSON 缺少品牌名称或官方域名")
    return {
        "brand": brand,
        "official_domain": domain,
        "category": category or "",
        "competitors": competitors,
        "topics_raw": pick("主题") or "",
    }


def load_domain_cache(path) -> dict:
    """读取引用来源域名类别缓存。

    分类不是封闭集合：内置白名单之外的域名按运行时缓存判读，缓存随每次运行生长。
    读不到时返回空字典，未登记域名回落「其他」，不阻塞构建。
    """
    if not path:
        return {}
    cache_path = Path(path)
    if not cache_path.exists():
        print(f"提示：域名类别缓存不存在（{cache_path}），未登记域名将回落「其他」")
        return {}
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"域名类别缓存格式应为扁平映射 {{域名: 类别}}，实际为 {type(payload).__name__}")
    valid = {"media_review", "ugc", "institutional", "press_release", "other"}
    unknown = {k: v for k, v in payload.items() if v not in valid}
    if unknown:
        sample = ", ".join(f"{k}={v}" for k, v in list(unknown.items())[:3])
        raise SystemExit(f"域名类别缓存含未知类别（{sample}），允许值：{'/'.join(sorted(valid))}")
    return payload


def load_question_rows(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise SystemExit(f"题库为空：{path}")
    for index, row in enumerate(rows, 1):
        if not str(row.get("query") or "").strip():
            raise SystemExit(f"题库第 {index} 行缺少 query")
    return rows


def load_lexicon(path) -> tuple[list[dict], set[str], str]:
    """读取品牌词表，返回 ([{name, domains, aliases, type}], 排除名单, status)。

    词表结构容忍多种写法（``{"brands": [...]}`` / 裸列表 / name->info 映射）。
    ``uncertain`` 中的名字按词表约定排除在声量分母之外。
    """
    empty: tuple[list[dict], set[str], str] = ([], set(), "absent")
    if not path:
        return empty
    path = Path(path)
    if not path.exists():
        return empty
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [], set(), f"unreadable:{exc.__class__.__name__}"

    uncertain = set()
    if isinstance(raw, dict):
        for item in raw.get("uncertain") or []:
            name = item.get("name") if isinstance(item, dict) else item
            if name:
                uncertain.add(normalize_text(str(name)))

    if isinstance(raw, dict) and isinstance(raw.get("brands"), list):
        source = raw["brands"]
    elif isinstance(raw, list):
        source = raw
    elif isinstance(raw, dict):
        # 兼容「标准名 → 别名 list」的 dict 型词表（report-audit / shared），别名必须保留；
        # 以 `_` 开头的键（_comment/_canonical 等）是元数据，不是品牌。
        source = []
        for key, value in raw.items():
            if key in {"uncertain", "stopwords"} or key.startswith("_"):
                continue
            if isinstance(value, dict):
                source.append(dict(value, name=key))
            elif isinstance(value, list):
                source.append({"name": key, "aliases": [key, *value]})
            else:
                source.append({"name": key})
    else:
        return [], set(), "unsupported-shape"

    def as_list(value):
        if value is None:
            return []
        return value if isinstance(value, list) else [value]

    entries = []
    for item in source:
        if isinstance(item, str):
            item = {"name": item}
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("brand") or item.get("canonical_name") or "").strip()
        if not name or normalize_text(name) in uncertain:
            continue
        domains = [normalize_host(str(d)) for d in as_list(
            item.get("official_domains") or item.get("domains") or item.get("domain"))]
        aliases = [str(a).strip() for a in as_list(item.get("aliases")) if str(a).strip()]
        entries.append({
            "name": name,
            "domains": [d for d in domains if d],
            "aliases": aliases or [name],
            "type": str(item.get("type") or "competitor_open").strip(),
        })
    return entries, uncertain, "loaded"


# ------------------------------------------------------------ 构造内部结构

def build_config(case: dict, topics: list[str], lexicon_entries: list[dict],
                 domain_cache: dict | None = None) -> dict:
    """构造 config（normalize_config 的内部产物形态）。

    对象集 = 目标品牌 + Case 里的 3 个配置竞品 + 词表中的开放品牌。
    词表中命中目标/配置竞品的条目只做别名与域名合并，不重复计入。
    别名按首次登记者归属，跨对象重名的别名被丢弃，避免同一写法记到两个品牌。
    """
    objects: list[dict] = []
    alias_owner: dict[str, str] = {}

    def add(name, domains, aliases, role, order):
        object_id = ("target" if role == "target"
                     else f"competitor-{order:02d}" if role == "competitor"
                     else f"open-{order:02d}")
        obj = {
            "object_id": object_id,
            "role": role,
            "display_order": order,
            "canonical_name": name,
            "official_domains": [d for d in (normalize_host(x) for x in domains) if d],
            "aliases": [],
            "object_scope": "brand",
        }
        merge_lexicon(obj, aliases, domains, alias_owner)
        if name not in obj["aliases"]:
            obj["aliases"].insert(0, name)
            alias_owner.setdefault(normalize_text(name), object_id)
        objects.append(obj)
        return obj

    add(case["brand"], [case["official_domain"]], [case["brand"]], "target", 0)
    for index, comp in enumerate(case["competitors"][:3], 1):
        add(comp["name"], [comp["domain"]], [comp["name"]], "competitor", index)

    # 一遍：把词表条目并入已存在的目标 / 配置竞品（按 type、名称、域名匹配）
    unresolved = []
    for entry in lexicon_entries:
        match = None
        entry_domains = {normalize_host(d) for d in entry["domains"] if d}
        entry_name = normalize_text(entry["name"])
        for obj in objects:
            if entry["type"] == "target" and obj["object_id"] == "target":
                match = obj
                break
            if entry_name == normalize_text(obj["canonical_name"]):
                match = obj
                break
            if entry_domains & set(obj["official_domains"]):
                match = obj
                break
        if match:
            merge_lexicon(match, entry["aliases"], entry["domains"], alias_owner)
        else:
            unresolved.append(entry)

    # 二遍：其余条目作为开放品牌，排在配置竞品之后
    for entry in unresolved:
        add(entry["name"], entry["domains"], entry["aliases"], "open",
            3 + len([o for o in objects if o["role"] == "open"]) + 1)

    config = {
        "schema_version": "geo-presales-config/v1",
        "run_id": RUN_ID,
        "config_version": "1",
        "topic": " / ".join(topics),
        "topics": [{"topic_id": topic,
                    "topic_type": "coverage" if index == 0 else "depth",
                    "topic": topic} for index, topic in enumerate(topics)],
        "target_attributes": [],
        "market": "SEA",
        "language": "en",
        "platform": "multi",
        "audiences": [],
        "supplemental_context": "",
        "avoid_expressions": [],
        "objects": objects,
        "target_object_id": "target",
        "quotas": {"total": 0},
        "sample_policy": "first_valid_per_question",
        "rank_policy": "configured_objects_first_appearance_v1",
        "source_taxonomy_version": "prd-8-types-v1",
        # 引用来源分类不是封闭集合：内置白名单之外，按运行时缓存判读
        "domain_category_cache": dict(domain_cache or {}),
        "sentiment_confidence_threshold": 0.78,
        "ruleset_version": "report-builder-v1",
        "frozen_at": now_iso(),
    }
    config["config_hash"] = sha256_obj(config)
    return config


def merge_lexicon(obj: dict, aliases, domains, alias_owner: dict) -> None:
    """把词表的别名与域名并入对象；跨对象重名的别名丢弃。"""
    for domain in domains:
        normalized = normalize_host(domain)
        if normalized and normalized not in obj["official_domains"]:
            obj["official_domains"].append(normalized)
    for alias in aliases:
        alias = str(alias).strip()
        if not alias:
            continue
        key = normalize_text(alias)
        owner = alias_owner.get(key)
        if owner and owner != obj["object_id"]:
            continue
        alias_owner[key] = obj["object_id"]
        if alias not in obj["aliases"]:
            obj["aliases"].append(alias)


def build_question_bank(rows: list[dict], config: dict, topics: list[str]) -> dict:
    topic_index = {topic: index for index, topic in enumerate(topics)}
    questions = []
    for index, row in enumerate(rows, 1):
        question_id = f"{index:04d}"
        topic = str(row.get("topic") or "").strip()
        if topic not in topic_index:
            raise SystemExit(f"题库第 {index} 行主题 {topic!r} 不在 Case 主题内：{topics}")
        csv_intent = str(row.get("diagnosis_intent") or "").strip()
        backend_intent = CSV_INTENT_MAP.get(
            str(csv_intent).strip().casefold().removeprefix("intent:").strip())
        if not backend_intent:
            raise SystemExit(f"题库第 {index} 行诊断意图无法映射：{csv_intent!r}")
        # analysis_type 取题库 question_types（Discovery 为 visibility,sentiment）
        analysis_type = str(row.get("question_types") or "").strip() or None
        tags = [t.strip() for t in str(row.get("tags") or "").split(",") if t.strip()]
        questions.append({
            "question_id": question_id,
            "generation_sequence": index,
            "question_text": str(row["query"]).strip(),
            "question_zh": str(row.get("question_zh") or "").strip() or None,
            "question_type": "generic" if backend_intent in {"discovery", "market_perception"} else "branded",
            "funnel_intent": FUNNEL_OVERRIDE.get(backend_intent, "recommendation"),
            "diagnostic_intent": backend_intent,
            "analysis_type": analysis_type,
            "metric_scopes": None,
            "topic_id": topic,
            "topic_type": "coverage" if topic_index[topic] == 0 else "depth",
            "attribute_ids": [],
            "source": {"claimed_intent": csv_intent, "claimed_question_types": analysis_type,
                       "tags": tags},
        })
    return {
        "schema_version": "geo-presales-question-bank/v1",
        "run_id": config["run_id"],
        "quotas": config["quotas"],
        "questions": questions,
        "question_bank_hash": sha256_obj(questions),
        "warnings": [],
    }


# --------------------------------------------------------------- 采集数据加载

def _platform_citation_entries(task_result: dict, field: str) -> list[dict]:
    """供应商引用字段的条目。字段是回退来源，不是首选来源。"""
    items = task_result.get(field) or []
    if not isinstance(items, list):
        return []
    out = []
    for order, raw in enumerate(items, 1):
        if not isinstance(raw, dict):
            continue
        url = str(raw.get("url") or raw.get("link") or raw.get("href") or "").strip()
        if not url:
            continue
        url = clean_url(url)
        host = normalize_host(url)
        if not host or is_platform_internal(host):
            continue
        title = (raw.get("title") or raw.get("name") or raw.get("attribution")
                 or raw.get("website_name") or "")
        out.append({
            "raw_citation_id": None,
            "source": "platform",
            "source_order": order,
            "raw_url": url,
            "source_name": raw.get("website_name") or raw.get("attribution"),
            "domain_hint": host,
            "title": str(title).strip() or None,
            "date": raw.get("date"),
            "summary": raw.get("snippet") or raw.get("summary"),
            "source_position": None,
            "positions": raw.get("positions") or [],
            "extraction_method": field,
            "platform_reported_type": raw.get("type"),
        })
    return out


def _body_citation_occurrences(text: str) -> tuple[dict, list]:
    """从回答正文解析引用定义行与标记出现。

    定义行形如 `[3]: https://… "标题"`，行内标记形如 `([来源名][3])`。
    标记出现次数才是「引用次数」的计数单位：同一 URL 在一篇里出现 N 次就计 N 次。
    """
    definitions = {}
    for number, url, title in _BODY_REF_DEF.findall(text or ""):
        definitions[number] = {"url": url, "title": title}
    spans, occurrences = [], []
    for match in _BODY_REF_MARKER.finditer(text or ""):
        spans.append(match.span())
        occurrences.append((match.group(1).strip(), match.group(2), match.start()))
    for match in _BODY_REF_MARKER_BARE.finditer(text or ""):
        if any(start <= match.start() < end for start, end in spans):
            continue
        occurrences.append((match.group(1).strip(), match.group(2), match.start()))
    occurrences.sort(key=lambda item: item[2])
    return definitions, occurrences


def _citation_entries(platform: str, task_result: dict, answer_text: str = "") -> list[dict]:
    """引用条目 = 正文 pill 标记的出现次数。

    计数单位是「出现次数」：同一编号在一篇里出现 N 次就计 N 次，不做回答内去重。
    正文没有 pill 的回答计 0 条。某条 pill 缺定义行时，URL 按位置回退到供应商字段的
    第 N 条——那是**解析 URL**，不是计数的来源；URL 仍解析不出时记 unresolved，
    只贡献次数、不贡献来源。
    """
    field = CITATION_FIELD.get(platform)
    definitions, occurrences = _body_citation_occurrences(answer_text)

    if not occurrences:
        # 引用次数只计正文 pill（`([来源名][N])`）的出现次数。
        # 正文一条 pill 都没有就是 0 条引用——不拿供应商字段的来源清单充数，
        # 那是「回答引用了哪些来源」的另一个口径（Suda 2026-09-16）。
        return []

    raw_items = task_result.get(field)
    fallback_items = raw_items if isinstance(raw_items, list) else []
    out = []
    for label, number, position in occurrences:
        line_start = answer_text.rfind("\n", 0, position) + 1
        in_table_row = answer_text[line_start:].lstrip().startswith("|")
        definition = definitions.get(number)
        raw_url = definition["url"] if definition else None
        title = definition["title"] if definition else None
        mapping = "body_definition"
        if not raw_url and number.isdigit() and 0 < int(number) <= len(fallback_items):
            item = fallback_items[int(number) - 1]
            if isinstance(item, dict):
                raw_url = str(item.get("url") or item.get("link") or item.get("href") or "").strip()
                title = title or item.get("title") or item.get("name")
                mapping = "platform_field_positional"
        if not raw_url:
            mapping = "unresolved"
        url = clean_url(raw_url) if raw_url else ""
        host = normalize_host(url) if url else None
        if host and is_platform_internal(host):
            continue
        out.append({
            "raw_citation_id": None,
            "source": "body_marker",
            "source_order": len(out) + 1,
            "raw_url": url or None,
            "source_name": label,
            "domain_hint": host,
            "title": str(title).strip() if title else None,
            "date": None,
            "summary": None,
            "source_position": position,
            "positions": [],
            "extraction_method": "body_reference_marker",
            "platform_reported_type": None,
            "reference_number": number,
            "mapping_method": mapping,
            "in_table_row": in_table_row,
        })
    return out


def discover_sample_files(folder: Path, questions: list[dict]):
    """把一个平台×市场的采集文件归属到题。

    归属优先看 ``task_result.prompt`` 与题库正文的比对；**题面缺失时回退到文件名题号**。
    两种布局都能吃：

    - **按题号命名**：``0001.json``…``00NN.json``，文件名即题号。
    - **按题面标识命名**：``BOT-T1-D01.json``，靠题面比对归属，同一题多份按文件名排重复序号。

    为什么必须回退：AIO 的响应里**没有 ``prompt`` 字段**（100/100 为空）、ChatGPT 有 73/100 为空，
    只按题面归属会把这两个平台整批丢成 ``UNMATCHED_SAMPLE_FILE``——实测 AIO 归零、全量分母从
    264 掉到 152。这类缺失是平台结构决定的，不是采集错误。

    为什么回退要留痕：文件名题号**不总是**题号（botslab 那批是 5 题 × 15 次重复，``0001.json``
    不是第 1 题）。所以回退只在「题面为空」时启用，且必须记 ``FILENAME_FALLBACK``，不静默错配；
    题面存在但对不上任何题时仍报 ``UNMATCHED_SAMPLE_FILE``，那才是真错位。

    返回 ``(files, issues)``，``files`` 为 ``[(path, question_id, repeat_index)]``。
    """
    by_prompt = {
        normalize_text(q["question_text"]): q["question_id"]
        for q in questions if q.get("question_text")
    }
    known_qids = {q["question_id"] for q in questions}
    grouped: dict[str, list[Path]] = defaultdict(list)
    issues: list[dict] = []
    fallbacks: list[dict] = []

    for path in sorted(folder.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        result = payload.get("task_result") or {}
        prompt = str(result.get("prompt") or "").strip()
        qid = by_prompt.get(normalize_text(prompt)) if prompt else None
        if qid:
            grouped[qid].append(path)
            continue
        if not prompt:
            # 题面缺失：回退到文件名题号，留痕
            stem = path.stem.strip()
            candidate = stem if stem in known_qids else (
                stem.zfill(4) if stem.isdigit() and stem.zfill(4) in known_qids else None)
            if candidate:
                grouped[candidate].append(path)
                fallbacks.append({"code": "FILENAME_FALLBACK", "file": str(path),
                                  "question_id": candidate})
                continue
        issues.append({
            "code": "UNMATCHED_SAMPLE_FILE", "file": str(path),
            "prompt": prompt[:120] or None,
        })

    if fallbacks:
        issues.extend(fallbacks)

    files: list[tuple[Path, str, int]] = []
    for qid, paths in grouped.items():
        for index, path in enumerate(sorted(paths), 1):
            files.append((path, qid, index))
    files.sort(key=lambda item: (item[1], item[2]))
    return files, issues


def load_samples(collect_dir: Path, region: str, platform: str,
                 questions: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    folder = collect_dir / f"scraper.{platform}" / region
    if not folder.is_dir():
        # 平台×市场的组合可以缺：市场是按各平台并集发现的，缺席记一条 issue 即可，
        # 不因为某个平台没采某个市场就中断整次构建。
        return [], [{
            "code": "PLATFORM_REGION_ABSENT",
            "platform": platform, "region": region, "folder": str(folder),
        }], []
    text_field = ANSWER_FIELD[platform]
    files, discover_issues = discover_sample_files(folder, questions)
    issues = [*discover_issues]
    order_issues: list[dict] = []
    repeat_totals = Counter(qid for _, qid, _ in files)

    # 把归属结果按题分组，供「缺文件」判定与题面顺序核对
    found_questions = {qid for _, qid, _ in files}
    for question in questions:
        if question["question_id"] not in found_questions:
            issues.append({
                "code": "MISSING_SAMPLE_FILE",
                "sample_id": f"{platform}-{region}-{question['question_id']}",
            })

    samples: list[dict] = []
    for path, qid, repeat_index in files:
        sample_id = f"{platform}-{region}-{qid}-r{repeat_index:02d}"
        question = next(q for q in questions if q["question_id"] == qid)
        payload = json.loads(path.read_text(encoding="utf-8"))
        task_result = payload.get("task_result") or {}
        text = str(task_result.get(text_field) or "")

        reported_prompt = str(task_result.get("prompt") or "").strip()
        if reported_prompt and normalize_text(reported_prompt) != normalize_text(question["question_text"]):
            order_issues.append({
                "code": "PROMPT_ORDER_MISMATCH", "platform": platform, "region": region,
                "question_id": qid, "file": path.name,
            })

        citations = _citation_entries(platform, task_result, text)
        for index, citation in enumerate(citations, 1):
            citation["raw_citation_id"] = f"C-{platform}-{region}-{qid}-r{repeat_index:02d}-{index:03d}"

        # 品牌匹配用去引用正文（剥引用标记 + 清商品卡商家列）；引用统计仍用原文。
        ranking_text = de_cite.blank_merchant_columns(de_cite.strip_citations(text))
        # 失败页判定走 core 的唯一实现，不在这里复刻签名表。
        # 只判空串会漏掉模型失败页（"I encountered an error doing what you asked.
        # Could you try again?" 之类），把失败页当成正常回答计入分母——静默稀释、不报错。
        eligible, invalid_code = answer_validity(text)
        samples.append({
            "sample_id": sample_id,
            "question_id": qid,
            "repeat_index": repeat_index,
            "repeat_total": repeat_totals[qid],
            "engine": platform,
            "status": str(payload.get("status") or "success"),
            "analysis_eligible": eligible,
            "answer_text": text,
            "ranking_text": ranking_text,
            "citations": citations,
            "error_code": invalid_code,
            "error_message": None,
            "provenance": {"source_shape": "platform_json", "source_file": str(path),
                           "platform": platform, "region": region},
        })
    return samples, issues, order_issues


def build_answers_index(collect_dir: Path, config: dict, bank: dict, run_root: Path,
                        regions: list[str]):
    """每个 (region, platform) 跑一次 prepare_answers，缓存答案文档。"""
    index: dict[tuple[str, str], dict] = {}
    issues, order_issues = [], []
    for region in regions:
        for platform in PLATFORM_DIRS:
            samples, sample_issues, order = load_samples(collect_dir, region, platform,
                                                         bank["questions"])
            issues.extend(sample_issues)
            order_issues.extend(order)
            index[(region, platform)] = prepare_answers(run_root, config, bank,
                                                        {"samples": samples})
    return index, issues, order_issues


# --------------------------------------------------------------- 切片产出

def collect_answers(index: dict, region: str, platform: str, topic: str,
                    regions: list[str]) -> list[dict]:
    """platform 为平台显示名（""=全部平台），index 按平台目录名索引。

    region 为 "" 表示「全部国家」：把各市场样本合池后按同样的 (platform, topic)
    口径计算。sample_id 内含 market 与平台，合池后 answer_id 仍唯一。
    """
    platforms = [LABEL_TO_DIR[platform]] if platform else PLATFORM_DIRS
    markets = [region] if region else regions
    out = []
    for name in platforms:
        for market in markets:
            for answer in index[(market, name)]["answers"]:
                if topic and answer.get("topic_id") != topic:
                    continue
                out.append(answer)
    return out


def answers_doc(answers: list[dict]) -> dict:
    return {
        "schema_version": "geo-presales-answers/v1",
        "run_id": RUN_ID,
        "answers": answers,
        "answers_hash": sha256_obj(answers),
        "rank_policy": "configured_objects_first_appearance_v1",
        "sample_policy": "first_valid_per_question",
    }


def target_of(answer: dict, target_id: str = "target") -> dict:
    return next(item for item in answer["objects"] if item["object_id"] == target_id)


def is_valid(answer: dict) -> bool:
    return answer.get("validity") == "valid"


def is_discovery(answer: dict) -> bool:
    return answer.get("diagnostic_intent") == "discovery"


def is_sentiment_question(answer: dict) -> bool:
    """情绪样本 = analysis_type 含 sentiment 的题（口径：canonical-intent-mapping）。"""
    return "sentiment" in str(answer.get("analysis_type") or "").casefold()


def build_slice(region: str, platform: str, topic: str, config: dict, bank: dict,
                index: dict, per_platform: dict, regions: list[str]) -> dict:
    answers = collect_answers(index, region, platform, topic, regions)
    metrics = compute_metrics(config, bank, answers_doc(answers))
    # 引用口径与 compute_metrics 一致：只用 Discovery 有效答案的引用记录
    citation_scope = [a for a in answers if is_valid(a) and is_discovery(a)]

    rows = []
    for obj in config["objects"]:
        entry = metrics["overview"]["objects"][obj["object_id"]]
        rows.append({
            "object_id": obj["object_id"],
            "role": obj["role"],
            "name": obj["canonical_name"],
            "domain": (obj["official_domains"] or [""])[0],
            "mention_rate": entry["mention_rate"]["raw"],
            "share_of_voice": entry["share_of_voice"]["raw"],
            "average_rank": entry["average_rank"]["raw"],
            "citation_share": official_share(citation_scope, obj["object_id"]),
        })
    row_by_id = {row["object_id"]: row for row in rows}

    # 展示集合：目标 + 3 配置竞品 + 提及率最高的 1 个开放品牌
    configured = [r for r in rows if r["object_id"] == "target" or r["role"] == "competitor"]
    open_rows = sorted([r for r in rows if r["role"] == "open"],
                       key=lambda r: (-(r["mention_rate"] or 0), r["name"]))
    display = configured + open_rows[:1]
    by_mention = sorted(display, key=lambda r: (-(r["mention_rate"] or 0), r["role"] != "target"))
    rank_lookup = rank_lookup_of(rows)
    max_rate = max([r["mention_rate"] or 0 for r in by_mention] or [0])

    mention_rows, share_values, fill_index = [], [], 0
    for row in by_mention:
        if row["object_id"] == "target":
            fill, label = "gold", f"{row['name']} ★"
        else:
            fill = COMPETITION_FILLS[fill_index % len(COMPETITION_FILLS)]
            fill_index += 1
            label = row["name"]
        mention_rows.append([
            label, row["domain"], fmt_pct(row["mention_rate"]),
            bar_width(row["mention_rate"], max_rate), fill,
            rank_lookup.get(row["object_id"]),
        ])
        share_values.append(round((row["share_of_voice"] or 0) * 100, 1))

    rank_rows = []
    for row in sorted(display, key=lambda r: (r["average_rank"] if r["average_rank"] is not None else 999)):
        label = f"{row['name']} ★" if row["object_id"] == "target" else row["name"]
        item = [label, row["domain"], fmt_num(row["average_rank"])]
        if row["object_id"] == "target":
            item.append("target")
        rank_rows.append(item)

    # matrix：列 = meta.platforms，值取同 region + 同 topic 的逐平台切片
    matrix = {"platforms": list(PLATFORM_LABELS)}
    for metric in ("mention", "share", "rank", "sent", "official"):
        matrix[metric] = []
    for row in by_mention:
        object_id = row["object_id"]
        label = f"{row['name']} ★" if object_id == "target" else row["name"]
        values = {"mention": [], "share": [], "rank": [], "sent": [], "official": []}
        for platform_label in PLATFORM_LABELS:
            sub = (per_platform.get((region, platform_label, topic)) or {}).get("_rows", {})
            peer = sub.get(object_id, {})
            values["mention"].append(pct_num(peer.get("mention_rate")))
            values["share"].append(pct_num(peer.get("share_of_voice")))
            values["rank"].append(round1(peer.get("average_rank")))
            values["sent"].append(None)  # 句级情感判读待补
            values["official"].append(pct_num(peer.get("citation_share")))
        for metric, vals in values.items():
            matrix[metric].append({"name": label, "target": object_id == "target",
                                   "vals": vals})

    target = row_by_id["target"]
    return {
        "kpis": {
            "mention_rate": fmt_pct(target["mention_rate"]),
            # 排名不存在为「—」：未进入榜单即视为末位（纳入对象总数）
            "mention_rank": str(rank_lookup.get("target", len(rows))),
            "share_of_voice": fmt_pct(target["share_of_voice"]),
            "average_rank": fmt_num(target["average_rank"]),
            "official_share": fmt_pct(metrics["citations"]["official_share"]["raw"]),
        },
        "competition": {"mention": mention_rows, "share": share_values, "rank": rank_rows},
        "matrix": matrix,
        "sources": build_sources(metrics, answers),
        "sentiment": build_sentiment(answers),
        "records": build_records(answers, bank["questions"], topic, all_objects(config)),
        "_rows": {row["object_id"]: row for row in rows},
        "_counts": {
            "answers": len(answers),
            "valid_answers": sum(1 for a in answers if is_valid(a)),
            "discovery_answers": sum(1 for a in answers if is_valid(a) and is_discovery(a)),
        },
    }


def rank_lookup_of(rows: list[dict]) -> dict:
    """按提及率降序的并列名次（1,2,2,4），目标品牌与全部纳入对象一起排序。"""
    ordered = sorted(rows, key=lambda r: (-(r["mention_rate"] or 0), r["name"]))
    lookup, last_value, last_rank = {}, None, 0
    for index, row in enumerate(ordered, 1):
        if row["mention_rate"] != last_value:
            last_rank, last_value = index, row["mention_rate"]
        lookup[row["object_id"]] = last_rank
    return lookup


def official_share(answers: list[dict], object_id: str):
    citations = [c for answer in answers for c in answer["citations"]]
    if not citations:
        return None
    own = sum(1 for c in citations if c.get("matched_official_object_id") == object_id)
    return own / len(citations)


def build_sources(metrics: dict, answers: list[dict]) -> dict:
    """引用来源结构。页/域名统计只取 Discovery 有效答案，与 compute_metrics 口径一致。"""
    discovery = [a for a in answers if is_valid(a) and is_discovery(a)]
    page_answers: dict[str, set] = defaultdict(set)
    page_meta: dict[str, dict] = {}
    domain_types: dict[str, Counter] = defaultdict(Counter)
    raw_page_counts: Counter = Counter()
    target_mention_by_answer: dict[str, bool] = {}
    for answer in discovery:
        target_mention_by_answer[answer["answer_id"]] = target_of(answer)["mentioned"]
        for citation in answer["citations"]:
            canonical = citation.get("canonical_url")
            if not canonical:
                continue
            source_type = citation.get("source_type") or "other"
            domain = citation.get("registrable_domain") or citation.get("host") or ""
            if domain:
                domain_types[domain][source_type] += 1
            page_meta.setdefault(canonical, {"type": source_type})
            page_answers[canonical].add(answer["answer_id"])
            raw_page_counts[canonical] += 1

    raw_total = metrics["citations"]["raw_count"]

    # 引用一律按「实际引用次数」统计：同一 URL 在一篇里被引两次就算两次。
    # 去重只用于右侧来源清单的展示，不作为任何指标的分母。
    bucket_counts: Counter = Counter()
    for answer in discovery:
        for citation in answer["citations"]:
            source_type = citation.get("source_type") or "other"
            bucket_counts[SOURCE_BUCKET.get(source_type, ("其他", ""))[0]] += 1
    # 按引用条数降序展示，数值相同的按固定类别顺序兜底，保证结果稳定可复算。
    types_rows = []
    for bucket in sorted(SOURCE_BUCKET_ORDER, key=lambda name: (-bucket_counts.get(name, 0),
                                                               SOURCE_BUCKET_ORDER.index(name))):
        count = bucket_counts.get(bucket, 0)
        fill = next(f for name, f in SOURCE_BUCKET.values() if name == bucket)
        types_rows.append([bucket,
                           fmt_pct(count / raw_total) if raw_total else "—",
                           str(count), fill])

    domain_rows = []
    for entry in metrics["citations"]["top_domains"]:
        counter = domain_types.get(entry["domain"])
        bucket = SOURCE_BUCKET.get(counter.most_common(1)[0][0], ("其他", ""))[0] if counter else "其他"
        domain_rows.append([entry["domain"], str(entry["answer_count"]), bucket])

    page_rows = []
    for entry in metrics["citations"]["top_pages"]:
        url = entry["url"]
        source_type = (page_meta.get(url) or {}).get("type", "other")
        mentioned = any(target_mention_by_answer.get(aid) for aid in page_answers.get(url, ()))
        share = raw_page_counts.get(url, 0) / raw_total if raw_total else None
        page_rows.append([url, SOURCE_BUCKET.get(source_type, ("其他", ""))[0],
                          "提及" if mentioned else "未提及", fmt_pct(share)])

    official_rows = [
        [entry["url"],
         fmt_pct(raw_page_counts.get(entry["url"], 0) / raw_total) if raw_total else "—"]
        for entry in metrics["citations"]["official_pages"]
    ]

    # 引用按「实际引用次数」计，不做回答内去重；unique_sources 只用于来源清单展示。
    table_row_markers = 0
    unique_sources: set[str] = set()
    for answer in discovery:
        for citation in answer["citations"]:
            if citation.get("in_table_row"):
                table_row_markers += 1
            canonical = citation.get("canonical_url")
            if canonical:
                unique_sources.add(canonical)

    return {
        "total_citations": raw_total,
        "official_share": fmt_pct(metrics["citations"]["official_share"]["raw"]),
        "types": types_rows,
        "domains": domain_rows,
        "pages": page_rows,
        "official_pages": official_rows,
        "citation_units": {
            "occurrences": raw_total,
            "unique_sources": len(unique_sources),
            "occurrences_in_table_rows": table_row_markers,
        },
    }


def build_sentiment(answers: list[dict]) -> dict:
    """句级情感判读尚未接入：claims / matrix 出空，summary 计数为 0。"""
    labels: Counter = Counter()
    for answer in answers:
        if not is_valid(answer) or not is_sentiment_question(answer):
            continue
        target = target_of(answer)
        if target.get("sentiment_status") == "accepted" and target.get("sentiment"):
            labels[target["sentiment"]] += 1
    pos, neu, neg = labels["positive"], labels["neutral"], labels["negative"]
    denominator = pos + neg
    return {
        "summary": {
            "total": pos + neu + neg,
            "pos": pos,
            "neu": neu,
            "neg": neg,
            "pos_rate": fmt_pct(pos / denominator) if denominator else "—",
            "neg_rate": fmt_pct(neg / denominator) if denominator else "—",
        },
        "claims": {"pos": [], "neg": []},
        "matrix": {"attributes": [], "brands": [], "cells": []},
    }


def build_records(answers: list[dict], questions: list[dict], topic: str,
                  objects: list[dict]) -> list[dict]:
    object_count = len(objects)
    # 题面是否点名目标品牌，用与正文识别同一套别名匹配，不在渲染层另写一套。
    target_aliases = next(
        (list(o["aliases"]) for o in objects if o["role"] == "target"), [])
    by_question: dict[str, list[dict]] = defaultdict(list)
    for answer in answers:
        by_question[answer["question_id"]].append(answer)
    records = []
    for question in questions:
        if topic and question.get("topic_id") != topic:
            continue
        qid = question["question_id"]
        valid = [a for a in by_question.get(qid, []) if is_valid(a)]
        row = {
            "qid": int(qid),
            "en": question["question_text"],
            "zh": question.get("question_zh") or "",
            "topic": question.get("topic_id"),
            "intent": INTENT_LABEL.get(question.get("diagnostic_intent"), ""),
            "tag": "、".join(readable_tags(question["source"].get("tags") or [])) or "—",
            "mention_rate": "—",
            "rank": "—",
            "share": "—",
            "citation_share": "—",
            "sentiment": None,
            # 内容规划取「目标品牌本该出现却没进回答」的题去补官网内容。判据是
            # 该题的目标品牌是否为被期待对象：题面不点名任何品牌（发现题），或
            # 题面点名目标品牌，都算；题面只点名竞品、或问品类选择标准的不算。
            # 显式给出三个布尔，不让渲染层去比中文标签或百分比字符串。
            "discovery": question.get("diagnostic_intent") == "discovery",
            "target_in_question": bool(
                core_util.find_alias_spans(question["question_text"], target_aliases)),
            "mentioned": None,
            # 该题下每个纳入品牌的口径，供审计报告的分题全品牌表使用。
            # 之前只带目标品牌一行，审计侧只能自己再算一遍，形成第二份指标实现。
            "brands": [],
        }
        if valid:
            mentions = [a for a in valid if target_of(a)["mentioned"]]
            total_mentions = sum(1 for a in valid for o in a["objects"] if o["mentioned"])
            citation_total = sum(len(a["citations"]) for a in valid)
            citation_own = sum(1 for a in valid for c in a["citations"]
                               if c.get("matched_official_object_id") == "target")
            row["mention_rate"] = fmt_pct(len(mentions) / len(valid))
            row["share"] = fmt_pct(len(mentions) / total_mentions) if total_mentions else "—"
            row["citation_share"] = fmt_pct(citation_own / citation_total) if citation_total else "—"
            row["mentioned"] = bool(mentions)
            if mentions:
                average = sum(target_of(a)["report_rank"] for a in mentions) / len(mentions)
                row["rank"] = fmt_num(average)
            else:
                # 排名只有分母为 0 才显示「—」，未提及按末位计。
                row["rank"] = str(object_count)
            # 该题下每个纳入品牌的口径。分题粒度，不等于切片级的 competition/matrix：
            # 靠它才能看出「某品牌只在某道题有存在感、在其余题被谁挤掉」。
            # 算提及率排名本来就要遍历全部对象，这里不增加计算量，只是把已算出的结果留下。
            counts = Counter()
            rank_sum = defaultdict(float)
            rank_n = Counter()
            for answer in valid:
                for obj in answer["objects"]:
                    if obj["mentioned"]:
                        counts[obj["object_id"]] += 1
                        if obj.get("report_rank"):
                            rank_sum[obj["object_id"]] += obj["report_rank"]
                            rank_n[obj["object_id"]] += 1
            row["brands"] = [
                {
                    "object_id": obj["object_id"],
                    "name": obj["canonical_name"],
                    "role": obj["role"],
                    "mention_count": counts[obj["object_id"]],
                    "mention_rate": counts[obj["object_id"]] / len(valid),
                    "share_of_voice": (counts[obj["object_id"]] / total_mentions
                                       if total_mentions else None),
                    "average_rank": (rank_sum[obj["object_id"]] / rank_n[obj["object_id"]]
                                     if rank_n[obj["object_id"]] else None),
                }
                for obj in objects
            ]
        records.append(row)
    return records


# --------------------------------------------------------------------- 主流程

def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="构建海外 GEO 售前诊断报告数据层")
    parser.add_argument("--collect", type=Path, required=True,
                        help="采集目录，形如 <collect>/scraper.<platform>/<REGION>/<NNNN>.json")
    parser.add_argument("--questions", type=Path, required=True,
                        help="题库 CSV，至少含 query/question_zh/topic/diagnosis_intent/tags/question_types")
    parser.add_argument("--case", type=Path, required=True,
                        help="Case 记录 JSON，含品牌、官网域名、3 个配置竞品及域名、品类")
    parser.add_argument("--lexicon", type=Path, default=None,
                        help="开放品牌词表；缺省时只用 Case 里的配置品牌跑通")
    parser.add_argument("--domain-cache", type=Path, default=DEFAULT_DOMAIN_CACHE,
                        help="引用来源域名类别缓存；缺失时未登记域名回落「其他」")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--regions", default="",
                        help="逗号分隔的市场代码；留空则从采集目录发现（推荐）")
    return parser.parse_args(argv)


def build_meta(case, rows, config, topics, regions, lexicon_status, collect_dir,
               sample_issues, order_issues, lexicon_brands, lexicon_uncertain) -> dict:
    intents, seen = [], set()
    for row in rows:
        backend = CSV_INTENT_MAP.get(str(row.get("diagnosis_intent") or "").strip())
        if backend and backend not in seen:
            seen.add(backend)
            intents.append(backend)
    intents.sort(key=INTENT_ORDER.index)
    intents = [INTENT_LABEL[key] for key in intents]

    tags = []
    for row in rows:
        for label in readable_tags(str(row.get("tags") or "").split(",")):
            if label not in tags:
                tags.append(label)

    questions = []
    for index, row in enumerate(rows, 1):
        backend = CSV_INTENT_MAP.get(str(row.get("diagnosis_intent") or "").strip())
        questions.append({
            "qid": index,
            "en": str(row["query"]).strip(),
            "zh": str(row.get("question_zh") or "").strip(),
            "topic": str(row.get("topic") or "").strip(),
            "intent": INTENT_LABEL.get(backend, ""),
            "tag": "、".join(readable_tags(str(row.get("tags") or "").split(","))) or "—",
        })

    return {
        "brand": case["brand"],
        "brand_display": f"{case['brand']} ★",
        "official_domain": normalize_host(case["official_domain"]),
        "category": case["category"],
        "generated_at": now_iso(),
        "regions": regions,
        "platforms": list(PLATFORM_LABELS),
        # 展示名 → 采集目录名。平台是从目录发现的，校验侧据此还原，不各写一份清单。
        "platform_dirs": dict(LABEL_TO_DIR),
        "topics": topics,
        "intents": intents,
        "tags": tags,
        "questions": questions,
        "run_id": RUN_ID,
        "source_collection": str(collect_dir),
        "sentiment_claims_status": "pending",
        "sentiment_note": "句级情感判读（sentiment.claims / sentiment.matrix）尚无数据源，待接入后重算。",
        "lexicon_status": lexicon_status,
        "lexicon_brands": lexicon_brands,
        "lexicon_uncertain": lexicon_uncertain,
        "objects": [{"object_id": o["object_id"], "role": o["role"],
                     "name": o["canonical_name"], "domains": o["official_domains"],
                     "aliases": o["aliases"]}
                    for o in config["objects"]],
        "sample_issues": sample_issues,
        "question_order_check": {
            "mismatches": order_issues,
            "note": "chatgpt / overview 的 prompt 字段缺失或为空，按题号对齐；"
                    "gemini / perplexity 已逐条比对 query，无错位。",
        },
        "methodology": {
            "visibility_scope": "正式可见度只用 Discovery 意图（diagnostic_intent=discovery）",
            "share_of_voice_denominator": "有效 Discovery 回答中各纳入对象提及次数之和",
            "citation_scope": "diagnostic_intent=discovery 的全量引用记录",
            "region_dimension": "按 (region, platform, topic) 切片分别计算；全平台/全主题切片为池化口径",
            "configured_competitors": "以客户确认版 Case 为准："
                                      + " / ".join(o["canonical_name"] for o in config["objects"]
                                                   if o["role"] == "competitor"),
            "object_set": "目标品牌 + 3 个配置竞品 + 词表 competitor_open；词表命中配置对象的条目只并入别名与域名",
            "source_type_note": "开放品牌官网域名由后端规则归入「竞品网站」，与配置竞品官网同桶；"
                                "后端已知域名表覆盖有限，评测站/媒体站多落入「其他」",
            "url_tracking_params": "入口侧补剥 srsltid 等跟踪参数（后端 normalize_url 同类行为），"
                                   "避免同页被计成多条引用；只影响去重与展示，不改变提及率/声量/平均位置",
            "registrable_domain_note": "后端多级后缀表缺 .com.my 等 SEA 后缀，会误并成 'com.my' 桶；"
                                       "已补全该表，仅影响展示层域名聚合，官方域名匹配与全部指标不变",
        },
    }




# 回答正文里混着平台的原始 HTML。转义前必须按类型处理，否则会被当文本显示——
# 实测 `<img src="data:image/jpeg;base64,...">` 一出现就是几百字，把表格单元撑爆。
_HTML_IMG = re.compile(r"<img\b[^>]*>", re.I)
_HTML_IMAGE_ALT = re.compile(r"<image\b[^>]*>", re.I)
# 平台给的交互建议块（追问、相关推荐），不是回答内容，整块去掉
_HTML_PLATFORM_BLOCK = re.compile(
    r"<\s*/?\s*(?:Elicitations?Group|Elicitations?|FollowUp)\b[^>]*>", re.I)
# 商品卡：标题在产品语义上是有用信息，保留为文本
_HTML_ENTITY_CARD = re.compile(r"<EntityCard\b[^>]*\btitle=\"([^\"]*)\"[^>]*/?>", re.I)
_HTML_ENTITY_CARD_BARE = re.compile(r"<\s*/?\s*EntityCard\b[^>]*>", re.I)
# 布局与排版标签：只去标签、留文字
_HTML_UNWRAP = re.compile(
    r"<\s*/?\s*(?:div|span|a|p|ul|ol|li|strong|em|b|i|table|thead|tbody|tr|td|th"
    r"|ProductComparisonTable)\b[^>]*>", re.I)
_HTML_BR = re.compile(r"<\s*br\s*/?\s*>", re.I)
_HTML_LEFT = re.compile(r"<\s*/?\s*[a-zA-Z][a-zA-Z0-9]*\b[^>]*>")


def normalize_answer_html(text: str) -> str:
    """把回答里的原始 HTML 归一成 markdown 能处理的纯文本。

    处理顺序有讲究：先去掉整块（图片、平台建议块），再把商品卡换成标题，
    最后才展开布局标签——顺序反了会留下孤立属性。
    """
    value = str(text or "")
    value = _HTML_IMG.sub("", value)
    value = _HTML_IMAGE_ALT.sub("", value)
    value = _HTML_PLATFORM_BLOCK.sub("", value)
    value = _HTML_ENTITY_CARD.sub(r"\1", value)
    value = _HTML_ENTITY_CARD_BARE.sub("", value)
    # 表格单元格里的 <br> 不能换成换行——会把一行表格拆成多行导致解析失败。
    # 换成「 / 」分隔符，保留多链接可读性。
    lines = value.split("\n")
    lines = [
        _HTML_BR.sub(" / ", line) if line.strip().startswith("|") else line
        for line in lines
    ]
    value = "\n".join(lines)
    value = _HTML_BR.sub("\n", value)
    value = _HTML_UNWRAP.sub("", value)
    value = _HTML_LEFT.sub("", value)      # 兜底：任何残留标签
    return value


_HTML_TAG_SPLIT = re.compile(r"(<[^>]+>)")


def _highlight_text_only(html_chunk: str, names: list[str]) -> str:
    """只给**文本**加品牌高亮，绝不碰标签属性。

    高亮原先作用在整串上，结果把 `<span>` 插进了 href 里：
    `<a href="https://<span class="brand-hl">Coway</span>-new.com/...">`——
    href 被截断，浏览器把后半段当正文显示。凡 URL 里含品牌名都会中招。
    """
    if not names:
        return html_chunk
    heads = [re.escape(name.split()[0]) for name in names if name]
    if not heads:
        return html_chunk
    pattern = re.compile(r"(?<![\w>])(" + "|".join(heads) + r")(?![\w<])", re.IGNORECASE)
    parts = _HTML_TAG_SPLIT.split(html_chunk)
    return "".join(
        part if part.startswith("<") else pattern.sub(r'<span class="brand-hl">\1</span>', part)
        for part in parts
    )


def markdown_to_html(text: str, highlight: list[str] | None = None) -> str:
    """把 AI 回答的 markdown 转成可直接注入的 HTML。

    只支持回答里实际出现的语法：标题、表格、有序/无序列表、加粗、行内代码、
    链接与裸 URL。先转义再逐段转换，避免回答内容里的标签被执行。
    """
    import html as _html
    import re as _re

    lines = _html.escape(normalize_answer_html(text)).replace("\r\n", "\n").split("\n")
    out: list[str] = []
    i = 0
    list_stack: list[str] = []

    # 先收集脚注定义（[N]: url "标题"），供正文引用 pill 链接；定义行本身仍从正文移除
    footnotes: dict[str, str] = {}
    for _line in lines:
        m = _re.match(r"^\[(\d+)\]:\s*(\S+)", _line.strip())
        if m:
            footnotes[m.group(1)] = m.group(2)

    def close_lists() -> None:
        while list_stack:
            out.append(f"</{list_stack.pop()}>")

    def _pill(match: "_re.Match[str]") -> str:
        name, num = match.group(1).strip(), match.group(2)
        url = footnotes.get(num, "")
        label = f'<span class="cite-pill-num">{num}</span>'
        if url:
            return (f'<a class="cite-pill" href="{url}" target="_blank" '
                    f'rel="noopener noreferrer" title="{name}">{name}{label}</a>')
        return f'<span class="cite-pill" title="{name}">{name}{label}</span>'

    def inline(chunk: str) -> str:
        chunk = _re.sub(r"`([^`]+)`", r"<code>\1</code>", chunk)
        chunk = _re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", chunk)
        chunk = _re.sub(r"(?<![\*\w])\*([^*\n]+)\*(?![\*\w])", r"<em>\1</em>", chunk)
        # 引用 pill：([来源名][N]) 或 [来源名][N]，链接到脚注 URL。要在普通链接之前处理。
        chunk = _re.sub(r"\(\[([^\]\[]+)\]\[(\d+)\]\)", _pill, chunk)
        chunk = _re.sub(r"\[([^\]\[]+)\]\[(\d+)\]", _pill, chunk)
        # URL 里允许一层括号（如 .../product(tk-cs200-hma)?utm=...），否则链接在首个 ) 提前闭合，
        # 尾巴 `?utm_source=...)` 会漏成可见文本。
        chunk = _re.sub(r"\[([^\]]+)\]\(((?:[^()\s]|\([^()\s]*\))+)\)",
                        r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>', chunk)
        chunk = _re.sub(r"(?<![\"'=])(https?://[^\s<]+)", r'<a href="\1" target="_blank" rel="noopener noreferrer">\1</a>', chunk)
        # 成对加粗已转换，剩下的连续星号都是跨单元格断裂的碎片（**LG…/…Wa**），删掉
        chunk = _re.sub(r"\*{2,}", "", chunk)
        return _highlight_text_only(chunk, highlight or [])

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if _re.match(r"^\|.*\|\s*$", stripped) and i + 1 < len(lines) and _re.match(r"^\|[\s:|-]+\|\s*$", lines[i + 1].strip()):
            close_lists()
            header = [cell.strip() for cell in stripped.strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lines) and _re.match(r"^\|.*\|\s*$", lines[i].strip()):
                rows.append([cell.strip() for cell in lines[i].strip().strip("|").split("|")])
                i += 1
            # 行对齐表头列数。列数**多于**表头说明源行含未转义的 `|`（URL、
            # AIO 的 run-on 长单元格都常见）。整行丢弃会静默吞内容——实测一条
            # AIO 回答 80% 的正文都在一个 6 格的超宽行里。改为把溢出格合并进
            # 最后一列：前 width-1 列对齐保持正确，内容一个字不丢；少列的行补空。
            width = len(header)
            aligned = []
            for row in rows:
                if len(row) > width:
                    row = row[: width - 1] + [" | ".join(row[width - 1:])]
                aligned.append((row + [""] * width)[:width])
            rows = aligned
            # 商品卡空位在源数据里是「****」「⭐ 0.0」占位行，整行没有实义内容，
            # 显示出来像乱码。所有格子都只含星号/评分符号/短数字的行直接丢弃。
            def _placeholder_row(row: list[str]) -> bool:
                if any(len(cell) >= 12 for cell in row):
                    return False
                return all(_re.fullmatch(r"[\*⭐☆\s\d.%-]*", cell) for cell in row)
            rows = [row for row in rows if not _placeholder_row(row)]
            # 整列为空的丢掉：回答里的商品表常有 picture 之类全空列，
            # 剥掉图片后它只剩个空表头，看起来像数据缺失。
            if rows:
                keep = [idx for idx in range(len(header))
                        if any(idx < len(row) and row[idx] for row in rows)]
                if keep and len(keep) < len(header):
                    header = [header[idx] for idx in keep]
                    rows = [[row[idx] if idx < len(row) else "" for idx in keep] for row in rows]
            # 有些表只剩评分占位符（`****`、`0.0`）之类的空壳。
            # 没有任何一格 ≥12 字且总内容极少才整表丢弃；内容多而无长单元格
            # 的表降级为段落输出——降级难看但无损，静默丢弃才是事故。
            substantive = [row for row in rows if any(len(cell) >= 12 for cell in row)]
            if not substantive:
                total_chars = sum(len(cell) for row in rows for cell in row)
                if total_chars >= 120:
                    for row in rows:
                        line_text = " | ".join(cell for cell in row if cell)
                        if line_text:
                            out.append(f"<p>{inline(line_text)}</p>")
                continue
            table = ["<table class=\"answer-table\"><thead><tr>"]
            table += [f"<th>{inline(cell)}</th>" for cell in header]
            table.append("</tr></thead><tbody>")
            for row in rows:
                table.append("<tr>" + "".join(f"<td>{inline(cell)}</td>" for cell in row) + "</tr>")
            table.append("</tbody></table>")
            # 套一层横向滚动容器：回答里的商品表列多，不套会被压成一列一个词。
            out.append('<div class="answer-table-wrap">' + "".join(table) + "</div>")
            continue

        heading = _re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading:
            close_lists()
            level = min(6, len(heading.group(1)) + 2)
            out.append(f"<h{level}>{inline(heading.group(2))}</h{level}>")
            i += 1
            continue

        bullet = _re.match(r"^[-*+]\s+(.*)$", stripped)
        ordered = _re.match(r"^\d+[.)]\s+(.*)$", stripped)
        if bullet or ordered:
            tag = "ul" if bullet else "ol"
            if not list_stack or list_stack[-1] != tag:
                close_lists()
                out.append(f"<{tag}>")
                list_stack.append(tag)
            out.append(f"<li>{inline((bullet or ordered).group(1))}</li>")
            i += 1
            continue

        if not stripped:
            close_lists()
            i += 1
            continue

        # 参考定义行（[1]: https://… "标题"）单独成行、右侧引用来源面板已列全，正文里去掉。
        if _re.match(r"^\[\d+\]:\s*\S+", stripped):
            i += 1
            continue

        close_lists()
        out.append(f"<p>{inline(stripped)}</p>")
        i += 1

    close_lists()
    return "".join(out)


def build_details(collect_dir: Path, config: dict, regions: list[str], bank: dict,
                  display_objects: list[dict]) -> dict:
    """逐「国家 × 平台 × 题号」准备抽屉所需的明细。

    放在顶层而不是切片里：同一题的答案会在多个切片出现，放进切片会让文件成倍膨胀。
    抽屉按当前国家与平台查找；「全部国家」时取该平台第一个可用市场。
    """
    from geo_presales_core.util import domain_matches, find_alias_spans, normalize_url

    text_field = {"overview": "content"}
    citation_field = {
        "overview": "source", "gemini": "citations",
        "chatgpt": "content_references", "perplexity": "web_results",
    }
    target = next((obj for obj in config["objects"] if obj["object_id"] == "target"), None)
    target_domains = list((target or {}).get("official_domains") or [])
    question_zh = {}
    for question in bank["questions"]:
        key = str(question.get("question_id") or "").strip()
        if key:
            question_zh[key.zfill(4)] = question.get("question_zh") or ""
    details: dict[str, dict] = {}

    for platform_dir, label in DIR_TO_LABEL.items():
        for market in regions:
            folder = collect_dir / f"scraper.{platform_dir}" / market
            if not folder.is_dir():
                continue
            for path in sorted(folder.glob("*.json")):
                qid = path.stem
                result = (json.loads(path.read_text(encoding="utf-8")).get("task_result") or {})
                answer = str(result.get(text_field.get(platform_dir, "result_text")) or "").strip()
                if not answer:
                    continue
                ranked = []
                for obj in display_objects:
                    spans = find_alias_spans(answer, obj["aliases"])
                    if spans:
                        ranked.append((spans[0]["start"], obj))
                ranked.sort(key=lambda item: item[0])
                brands = [
                    {
                        "name": obj["canonical_name"] + (" ★" if obj["object_id"] == "target" else ""),
                        "domain": (obj["official_domains"] or [""])[0],
                        "rank": index,
                        "target": obj["object_id"] == "target",
                    }
                    for index, (_, obj) in enumerate(ranked, 1)
                ]
                # 单条回答的引用份额：该回答正文 pill 出现次数中，指向本品官网的比例。
                # 这是「单个回答」层的口径；切片级（多回答/多平台）与平台级由
                # build_slice 分别给出，三层都保留，不做合并。
                definitions, occurrences = _body_citation_occurrences(answer)
                own_occurrences = 0
                citations = []
                # 注意：这里不能用 label 作循环变量——外层循环的 label 是平台标签，
                # 遮蔽后会把平台标签写成引用来源名。
                for source_name, number, _position in occurrences:
                    definition = definitions.get(number) or {}
                    raw_url = definition.get("url") or ""
                    normalized = normalize_url(raw_url) if raw_url else None
                    host = normalized["host"] if normalized else ""
                    if host and any(domain_matches(host, domain) for domain in target_domains):
                        own_occurrences += 1
                    if normalized:
                        citations.append({
                            "title": str(definition.get("title") or "").strip() or normalized["host"],
                            "url": normalized["canonical_url"],
                            "host": normalized["host"],
                            "source_name": source_name,
                        })
                details[f"{market}|{label}|{qid}"] = {
                    "question_zh": question_zh.get(qid, ""),
                    "answer_html": markdown_to_html(
                        answer[:6000], [obj["canonical_name"] for obj in display_objects]),
                    "brands": brands,
                    "citations": citations,
                    "citation_occurrences": len(occurrences),
                    "citation_share": (f"{own_occurrences * 100 / len(occurrences):.1f}%"
                                       if occurrences else "—"),
                }
    return details



def build_scope_notes(slices: dict, platforms: list[str]) -> list[dict]:
    """口径降级说明。

    采集侧未触发回答（AIO 不是每次都会触发）按降级口径处理：不计入任何分母，
    也不计为「未提及」。这会让各平台的可见度分母不等，必须在报告里写明，
    否则客户会拿不同分母的比率直接横比。
    """
    counts = {}
    for platform in platforms:
        payload = (slices.get(f"|{platform}|") or {}).get("_counts")
        if payload:
            counts[platform] = payload
    degraded = {p: c["answers"] - c["valid_answers"] for p, c in counts.items()
                if c["answers"] > c["valid_answers"]}
    if not degraded:
        return []
    parts = "、".join(f"{p} {n} 条" for p, n in degraded.items())
    denominators = " / ".join(
        f"{p} {counts[p]['discovery_answers']}" for p in platforms if p in counts)
    return [{
        "code": "DEGRADED_DENOMINATOR",
        "label": "口径降级",
        "detail": f"{parts}未触发回答（模型未产出正文），已按降级口径处理："
                  f"不计入任何分母，也不计为「未提及」。可见度分母因此为 {denominators}。",
        "platforms": sorted(degraded),
    }]


def main(argv=None) -> int:
    args = parse_args(argv)
    platforms = discover_platforms(args.collect)
    configure_platforms(platforms)
    requested_regions = [r.strip() for r in args.regions.split(",") if r.strip()]
    regions = requested_regions or discover_regions(args.collect, platforms)
    print(f"发现平台：{'、'.join(f'{d}({label})' for d, label in platforms)}；"
          f"市场：{'、'.join(regions)}")

    case = load_case(args.case)
    rows = load_question_rows(args.questions)
    lexicon_entries, lexicon_uncertain, lexicon_status = load_lexicon(args.lexicon)

    topics = [t.strip() for t in str(case["topics_raw"]).replace("，", ",").split(",") if t.strip()]
    if not topics:
        topics = list(dict.fromkeys(str(r.get("topic") or "").strip() for r in rows))

    config = build_config(case, topics, lexicon_entries, load_domain_cache(args.domain_cache))
    bank = build_question_bank(rows, config, topics)

    run_root = Path(tempfile.mkdtemp(prefix="georeport-"))
    try:
        index, sample_issues, order_issues = build_answers_index(
            args.collect, config, bank, run_root, regions)

        slices: dict[str, dict] = {}
        # region 为 "" 的合并国家切片：把各市场样本合池，口径不变
        for region in regions + [""]:
            per_platform = {}
            for platform_label in PLATFORM_LABELS:
                for topic in [""] + topics:
                    per_platform[(region, platform_label, topic)] = build_slice(
                        region, platform_label, topic, config, bank, index, {}, regions)
            for platform_label in [""] + PLATFORM_LABELS:
                for topic in [""] + topics:
                    result = build_slice(region, platform_label, topic, config, bank,
                                         index, per_platform, regions)
                    result.pop("_rows", None)
                    slices[f"{region}|{platform_label}|{topic}"] = result

        meta = build_meta(case, rows, config, topics, regions, lexicon_status,
                          args.collect, sample_issues, order_issues,
                          len(lexicon_entries), len(lexicon_uncertain))
        # 抽屉里展示与主榜一致的 5 个品牌：目标 + 3 配置竞品 + 提及率最高的开放品牌
        headline = slices.get("||") or next(iter(slices.values()))
        shown = [row[0].replace(" ★", "") for row in headline["competition"]["mention"]]
        configured_names = {config["objects"][0]["canonical_name"],
                            *[o["canonical_name"] for o in config["objects"] if o["role"] == "competitor"]}
        wanted = configured_names | {name for name in shown if name not in configured_names}
        display_objects = [obj for obj in all_objects(config) if obj["canonical_name"] in wanted]
        display_objects.sort(key=lambda o: (o["object_id"] != "target", o["display_order"]))
        meta["scope_notes"] = build_scope_notes(slices, list(PLATFORM_LABELS))
        details = build_details(args.collect, config, regions, bank, display_objects)
        write_json(args.out, {"schema": SCHEMA, "meta": meta, "slices": slices,
                              "details": details})
    finally:
        shutil.rmtree(run_root, ignore_errors=True)

    print(f"写出 {args.out}")
    print(f"切片 {len(slices)} 个；对象 {len(config['objects'])} 个；品牌词表 {lexicon_status}")
    for region in regions + [""]:
        base = slices[f"{region}||"]
        kpi, counts = base["kpis"], base["_counts"]
        print(f"  {region or '全部国家'}: 提及率 {kpi['mention_rate']}  排名 {kpi['mention_rank']}  "
              f"声量份额 {kpi['share_of_voice']}  平均位置 {kpi['average_rank']}  "
              f"引用份额 {kpi['official_share']}  "
              f"(有效答案 {counts['valid_answers']}/{counts['answers']}，"
              f"discovery {counts['discovery_answers']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
