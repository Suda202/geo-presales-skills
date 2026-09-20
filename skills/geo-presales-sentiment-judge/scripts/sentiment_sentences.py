#!/usr/bin/env python3
"""Deterministic helpers for sentence-level brand sentiment in GEO presales.

This tool does NOT judge sentiment. It makes the brittle parts deterministic:
sample-scope selection (analysis_type / question_types contains "sentiment"),
prompt-to-question integrity checks, citation/UI stripping, sentence/table-cell
unit splitting, brand-alias matching, label validation, and metric aggregation.
The semantic judgment (which units are positive/negative) remains a reviewed
decision that is recorded as an explicit labels file and replayed by `compute`.

Subcommands:
  extract  crawler answers + v8 bank + brand lexicon -> brand-mention units JSON
  compute  units JSON + labels JSON                 -> per-sentence CSV + metrics

Brand sources (extract takes exactly one):
  --aliases 'A,B,C'   single-brand mode, kept for backward compatibility
  --lexicon <json>    multi-brand mode; reads brands[].name/aliases/type so
                      every unit carries the brand it is judged for (competitor
                      sentiment matrix). Alias matching is identical in both
                      modes (see alias_pattern).
"""
from __future__ import annotations

import argparse
import collections
import csv
import glob
import json
import os
import re
import sys
import urllib.parse



# ---------- de-cite / UI strip (markdown crawler exports) ----------

def strip_answer_text(text: str) -> str:
    """Remove citation markup and widget UI so only body prose remains.

    Handles ChatGPT-style markdown pills ``([Source][N])``, reference
    definition lines ``[N]: url "title"``, stray ``[N]`` markers, and Gemini
    ``<FollowUp .../>`` widgets plus simple HTML tags such as ``<br>``.
    """
    t = re.sub(r"<FollowUp\b[^>]*/?>", "", text)
    t = re.sub(r"<br\s*/?>", " ", t)
    t = re.sub(r"<[A-Za-z][^>]{0,60}>", " ", t)
    t = re.sub(r"\(\s*\[[^\]]{0,80}\]\s*\[\s*\d+\s*\]\s*\)", "", t)
    t = re.sub(r"^\s*\[\d+\]:\s*\S.*$", "", t, flags=re.M)
    t = re.sub(r"\[\s*\d+\s*\]", "", t)
    return t


def split_units(text: str) -> list[str]:
    """Split cleaned text into judgment units: lines, and table rows into cells."""
    out: list[str] = []
    for line in strip_answer_text(text).split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("|") and line.count("|") >= 2:
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue  # header separator row
            out.extend(c for c in cells if c)
        else:
            out.append(line)
    return out


# ---------- brand alias matching ----------

def alias_pattern(alias: str) -> re.Pattern[str]:
    """Latin aliases get word-boundary guards (case-insensitive); other scripts literal."""
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9\+\.\' ]*", alias):
        esc = re.escape(alias).replace(r"\ ", r"\s*")
        return re.compile(r"(?<![A-Za-z0-9])" + esc + r"(?![A-Za-z0-9])", re.I)
    return re.compile(re.escape(alias))


def compile_aliases(aliases: list[str]) -> list[re.Pattern[str]]:
    cleaned = [a.strip() for a in aliases if a.strip()]
    if not cleaned:
        raise SystemExit("必须提供至少一个品牌别名（--aliases）")
    return [alias_pattern(a) for a in cleaned]


def load_lexicon(path: str) -> list[dict]:
    """Load brands[] from a brand lexicon JSON and compile each brand's aliases.

    Every entry is normalised to {name, type, patterns}. Alias matching reuses
    ``compile_aliases`` so a multi-brand run matches exactly as a single-brand
    run would for the same alias list (no divergent case/boundary handling).
    """
    data = json.load(open(path))
    brands = data.get("brands") if isinstance(data, dict) else None
    if brands is None and isinstance(data, dict):
        # 兼容「标准名 → 别名 list」的 dict 型词表（report-audit / shared 落点）。
        # `_` 开头的键（_comment/_canonical 等）是元数据；标准名自身也算一个别名。
        converted = [
            {"name": key, "aliases": [key, *value]}
            for key, value in data.items()
            if not key.startswith("_") and key not in {"uncertain", "stopwords"}
            and isinstance(value, list)
        ]
        if converted:
            brands = converted
    if not isinstance(brands, list) or not brands:
        raise SystemExit(f"词表 {path} 缺少非空的 brands 数组")
    compiled: list[dict] = []
    seen: set[str] = set()
    for entry in brands:
        name = str(entry.get("name") or "").strip()
        aliases = [str(a) for a in (entry.get("aliases") or []) if str(a).strip()]
        if not name:
            raise SystemExit(f"词表 {path} 存在缺少 name 的品牌条目")
        if not aliases:
            raise SystemExit(f"词表 {path} 的品牌 {name} 没有任何别名")
        if name in seen:
            raise SystemExit(f"词表 {path} 出现重复品牌名：{name}")
        seen.add(name)
        compiled.append({
            "name": name,
            "type": str(entry.get("type") or "").strip() or None,
            "patterns": compile_aliases(aliases),
        })
    return compiled



# ---------- extract ----------

def load_bank(path: str) -> list[dict]:
    """Load the question bank from JSON (v8 bank) or the flat upload CSV.

    Both forms are normalised to the same record shape: ``user_question``,
    ``analysis_type``, ``tags`` (list), ``question_id``. The CSV has no id
    column, so ids are the 1-based row number padded to 4 digits — the same
    scheme the batch stats engine uses, keeping idx/question_id aligned across
    the two pipelines.
    """
    if path.lower().endswith(".csv"):
        with open(path, encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        if not rows:
            raise SystemExit(f"题库 CSV {path} 没有数据行")
        questions = []
        for i, row in enumerate(rows, start=1):
            tags = [t.strip() for t in str(row.get("tags") or "").split(",") if t.strip()]
            questions.append({
                "question_id": (row.get("question_id") or f"{i:04d}").strip(),
                "user_question": (row.get("query") or row.get("user_question") or "").strip(),
                "analysis_type": row.get("question_types") or row.get("analysis_type") or "",
                "tags": tags,
            })
    else:
        bank = json.load(open(path))
        questions = bank["questions"]
    if not isinstance(questions, list) or not questions:
        raise SystemExit("题库 questions 为空或非数组")
    return questions


# Crawler exports put the answer body under different keys per platform; the
# mapping mirrors the batch stats engine's ANSWER_FIELD so the two pipelines
# read the same text. Unknown platforms fall back to result_text.
ANSWER_FIELD = {
    "overview": "content",
    "gemini": "result_text",
    "chatgpt": "result_text",
    "perplexity": "result_text",
}

# Scrapeless 锚点残留文案：它紧贴在商品名后（`AquaTru CarafeGo to product
# viewer dialog for this item.`），会让证据句带着平台 UI 文案交付给客户。
# 与 geo-presales-report-builder 的渲染清洗共用同一常量。
PRODUCT_VIEWER_NOISE = "Go to product viewer dialog for this item."


def answer_text(task: dict, platform: str) -> str:
    field = ANSWER_FIELD.get(platform, "result_text")
    text = task.get(field)
    if text is None and field != "result_text":
        text = task.get("result_text")
    # 换成空格而非直接删：它粘在商品名后，删掉会把两个名字拼成一个词。
    return str(text or "").replace(PRODUCT_VIEWER_NOISE, " ")


def answer_prompt(task: dict) -> str:
    """Best-available prompt text for the integrity check, or "" if unknown.

    Some exports omit ``prompt`` entirely (every AIO/overview record, part of
    ChatGPT). The AIO export carries the same question verbatim in the ``q=``
    parameter of ``metadata.rawUrl``, so recover it there. Returning "" means
    "cannot verify", which is reported separately from a genuine mismatch.
    """
    prompt = str(task.get("prompt") or "").strip()
    if prompt:
        return prompt
    meta = task.get("metadata")
    if isinstance(meta, dict):
        url = str(meta.get("rawUrl") or meta.get("url") or "")
        if url:
            values = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get("q") or []
            if values and values[0].strip():
                return values[0].strip()
    return ""



def question_intent(question: dict) -> str:
    tags = [t for t in question.get("tags", []) if t.startswith("Intent: ")]
    return tags[0][len("Intent: "):] if tags else ""


def in_sentiment_scope(question: dict) -> bool:
    analysis = question.get("analysis_type")
    return isinstance(analysis, str) and "sentiment" in analysis


def iter_crawl_files(crawl_dir: str):
    """Yield (platform, region, idx, path) in deterministic path order.

    ``region`` is the ``<REGION>`` directory in ``scraper.<platform>/<REGION>/
    <NNNN>.json`` (e.g. MY / SG). Layouts without a region directory yield None.
    """
    files = sorted(
        glob.glob(os.path.join(crawl_dir, "scraper.*", "*", "*.json"))
        + glob.glob(os.path.join(crawl_dir, "scraper.*", "*.json"))
    )
    if not files:
        raise SystemExit(f"在 {crawl_dir} 下未找到 scraper.*/ 采集文件")
    for path in files:
        rel = os.path.relpath(path, crawl_dir)
        parts = rel.split(os.sep)
        platform = parts[0].split(".", 1)[1]
        region = parts[1] if len(parts) >= 3 else None
        idx = int(os.path.splitext(os.path.basename(path))[0])
        yield platform, region, idx, path


def resolve_brands(args: argparse.Namespace) -> list[dict]:
    """Build the [{name, type, patterns}] brand list from --lexicon or --aliases."""
    if args.lexicon and args.aliases:
        raise SystemExit("--lexicon 与 --aliases 互斥，请只提供其一")
    if args.lexicon:
        return load_lexicon(args.lexicon)
    if not args.aliases:
        raise SystemExit("必须提供 --aliases（单品牌）或 --lexicon（多品牌词表）")
    aliases = [a.strip() for a in args.aliases.split(",") if a.strip()]
    name = (args.brand or "").strip() or aliases[0]
    return [{"name": name, "type": args.brand_type or None,
             "patterns": compile_aliases(aliases)}]


def cmd_extract(args: argparse.Namespace) -> None:
    questions = load_bank(args.bank)
    brands = resolve_brands(args)

    units: list[dict] = []
    mismatches: list[str] = []
    unverified: list[str] = []
    scope_answers = 0
    mentioned_answers = 0
    distinct_units = 0
    brand_answers: collections.Counter = collections.Counter()
    for platform, region, idx, path in iter_crawl_files(args.crawl_dir):
        if not 1 <= idx <= len(questions):
            mismatches.append(f"{platform} {idx:04d}: 编号超出题库范围 1..{len(questions)}")
            continue
        question = questions[idx - 1]
        data = json.load(open(path))
        task = data.get("task_result") or {}
        expected = str(question.get("user_question") or "").strip()
        prompt = answer_prompt(task)
        if prompt:
            if prompt != expected:
                mismatches.append(f"{platform} {idx:04d}: 采集题面与题库不一致")
                continue
        else:
            unverified.append(f"{platform} {idx:04d}")
        if not in_sentiment_scope(question):
            continue
        scope_answers += 1
        matched_here: set[str] = set()
        for unit in split_units(answer_text(task, platform)):
            matched = [b for b in brands if any(p.search(unit) for p in b["patterns"])]
            if not matched:
                continue
            distinct_units += 1
            for brand in matched:
                matched_here.add(brand["name"])
                units.append({
                    "platform": platform,
                    "region": region,
                    "idx": idx,
                    "question_id": question.get("question_id"),
                    "intent": question_intent(question),
                    "brand": brand["name"],
                    "brand_type": brand["type"],
                    "unit": unit,
                })
        if matched_here:
            mentioned_answers += 1
            for name in matched_here:
                brand_answers[name] += 1

    if mismatches:
        for m in mismatches:
            print("题面完整性失败:", m, file=sys.stderr)
        raise SystemExit("采集数据与题库映射不一致，停止抽取；请先核对题库版本")
    if unverified:
        print(f"警告：{len(unverified)} 条回答缺题面字段且无法从 metadata.rawUrl 还原，"
              f"已按编号映射抽取但未做题面校验（如 {', '.join(unverified[:5])}）",
              file=sys.stderr)

    by_brand = collections.Counter(u["brand"] for u in units)
    by_brand_type = collections.Counter(u["brand_type"] for u in units)

    payload = {
        "meta": {
            "bank": os.path.abspath(args.bank),
            "crawl_dir": os.path.abspath(args.crawl_dir),
            "brand_mode": "lexicon" if args.lexicon else "aliases",
            "lexicon": os.path.abspath(args.lexicon) if args.lexicon else None,
            "aliases": args.aliases,
            "brand_count": len(brands),
            "scope_answers": scope_answers,
            "mentioned_answers": mentioned_answers,
            "unit_count": len(units),
            "distinct_unit_count": distinct_units,
            "unverified_prompt_answers": len(unverified),
            "by_brand_type": dict(by_brand_type),
            "by_brand": dict(by_brand),
            "by_brand_answers": dict(brand_answers),
        },
        "units": units,
    }
    json.dump(payload, open(args.output, "w"), ensure_ascii=False, indent=1)

    print(f"情绪样本回答 {scope_answers} 条 | 提到任一品牌 {mentioned_answers} 条 | "
          f"判读单元 {len(units)} 个（去重句 {distinct_units}）")
    if args.lexicon:
        print(f"待判读品牌 {len(brands)} 个；按品牌分层单元数：")
        for btype, count in sorted(by_brand_type.items(), key=lambda kv: -kv[1]):
            print(f"  {btype or '(未标注类型)':<22} 单元 {count}")
        ranked = sorted(by_brand.items(), key=lambda kv: (-kv[1], kv[0]))
        print("  各品牌明细（单元数降序）：")
        for name, count in ranked:
            print(f"    {name:<22} {count}")
    print(f"写入 {args.output}")


# ---------- compute ----------

def cmd_compute(args: argparse.Namespace) -> None:
    payload = json.load(open(args.units))
    units = payload["units"]
    meta = payload.get("meta", {})
    labels = json.load(open(args.labels))
    positive = set(labels.get("positive", []))
    negative = set(labels.get("negative", []))
    all_brands = {u.get("brand") for u in units if u.get("brand")}
    if len(all_brands) > 1 and not args.brand:
        print(f"警告：本单元集含 {len(all_brands)} 个品牌，正向率将把各品牌混算；"
              f"分品牌指标请用 --brand 逐个运行", file=sys.stderr)

    overlap = positive & negative
    if overlap:
        raise SystemExit(f"同一单元不能既正又负：{sorted(overlap)}")
    out_of_range = [i for i in positive | negative if not 0 <= i < len(units)]
    if out_of_range:
        raise SystemExit(f"标签索引越界：{sorted(out_of_range)}（单元数 {len(units)}）")
    if args.brand:
        wrong_brand = [i for i in positive | negative if units[i].get("brand") != args.brand]
        if wrong_brand:
            raise SystemExit(f"标签含不属于品牌 {args.brand} 的单元：{sorted(wrong_brand)}")

    extracted = []
    for i, unit in enumerate(units):
        if i in positive:
            extracted.append({**unit, "sentiment": "P"})
        elif i in negative:
            extracted.append({**unit, "sentiment": "G"})

    p, g = len(positive), len(negative)
    denom = p + g
    if denom == 0:
        raise SystemExit("没有任何正负句；无法计算正向率（0/0 属于无样本，须如实报告）")

    # 键必须含 region：采集按 scraper.<platform>/<REGION>/NNNN.json 分层，
    # idx 是区域内编号，同一平台的港/新同题回答 idx 相同，
    # 只用 (platform, idx) 会把两地回答合并、低报含正负句的回答数
    # （实测 Trip.Biz 港新报 38、实为 52）。region 缺失时回落空串，不改变旧数据行为。
    docs_with_pg = {(u.get("region", ""), u["platform"], u["idx"]) for u in extracted}
    print(f"情绪样本回答 {meta.get('scope_answers', '?')} 条")
    print(f"  提到品牌的回答 {meta.get('mentioned_answers', '?')} 条")
    print(f"  含正负句的回答 {len(docs_with_pg)} 条")
    print(f"提取出的正负句 {denom} 句（正 {p} / 负 {g}）")
    print(f"\n正向率 = {p}/{denom} = {p / denom * 100:.1f}%")
    print(f"负面率 = {g}/{denom} = {g / denom * 100:.1f}%")

    def breakdown(key: str, title: str) -> dict:
        grouped: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
        for u in extracted:
            grouped[u[key]][u["sentiment"]] += 1
        print(f"\n=== {title} ===")
        result = {}
        for name, counter in sorted(grouped.items()):
            d = counter["P"] + counter["G"]
            rate = counter["P"] / d if d else None
            result[name] = {"P": counter["P"], "G": counter["G"], "positive_rate": rate}
            print(f"  {name:<12} 正={counter['P']:<3} 负={counter['G']:<3} 正向率={rate * 100:.1f}%")
        return result

    by_intent = breakdown("intent", "按 Intent")
    by_platform = breakdown("platform", "按平台")

    with open(args.out_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["platform", "region", "idx", "question_id", "intent", "brand",
                         "sentiment", "sentence"])
        for u in extracted:
            writer.writerow([u["platform"], u.get("region", ""), u["idx"], u["question_id"],
                             u["intent"], u.get("brand", ""), u["sentiment"], u["unit"]])
    print(f"\n写入 {args.out_csv}（{denom} 行正负句）")

    if args.out_metrics:
        metrics = {
            "funnel": {
                "scope_answers": meta.get("scope_answers"),
                "mentioned_answers": meta.get("mentioned_answers"),
                "answers_with_pg": len(docs_with_pg),
                "unit_count": len(units),
            },
            "positive": p, "negative": g,
            "positive_rate": p / denom,
            "by_intent": by_intent, "by_platform": by_platform,
        }
        if args.brand:
            metrics["brand"] = args.brand
        json.dump(metrics, open(args.out_metrics, "w"), ensure_ascii=False, indent=1)
        print(f"写入 {args.out_metrics}")


def _load_claims(path: str) -> list[dict]:
    payload = json.load(open(path))
    claims = payload.get("claims") if isinstance(payload, dict) else payload
    if not isinstance(claims, list):
        raise SystemExit(f"{path} 应为 claims 数组，或 {{\"claims\": [...]}}")
    return claims


def cmd_claims_assemble(args: argparse.Namespace) -> None:
    """把模型抽出的 Claim 层回装成带完整上下文的记录。

    输入：units.json（extract 产出，提供 evidence_text 与平台/地区/题号/意图上下文）
        + claims-raw.json（语义环节产出，每条只需给出 unit_index / brand / claim /
          attribute / theme / sentiment）。
    输出：claims.json —— 每条补齐 evidence_text 与上下文，供统计与明细展示使用。
    """
    units = json.load(open(args.units))["units"]
    raw = _load_claims(args.claims)
    out = []
    problems = []
    for i, item in enumerate(raw):
        # 注意：unit_index 可以是 0，不能用 `or ""` 判空（会把 0 当缺失）。
        missing = [f for f in ("brand", "claim", "attribute", "theme", "sentiment")
                   if not str(item.get(f) or "").strip()]
        if item.get("unit_index") is None:
            missing.insert(0, "unit_index")
        if missing:
            problems.append(f"第 {i} 条缺字段:{'、'.join(missing)}")
            continue
        unit_index = item["unit_index"]
        if not isinstance(unit_index, int) or not 0 <= unit_index < len(units):
            problems.append(f"第 {i} 条 unit_index 越界:{unit_index}")
            continue
        unit = units[unit_index]
        if item["brand"] != unit.get("brand"):
            problems.append(
                f"第 {i} 条品牌不符:claim 写 {item['brand']!r}，unit {unit_index} 属于 {unit.get('brand')!r}")
            continue
        direction = str(item["sentiment"]).strip()
        if direction not in ("positive", "negative", "正向", "负向"):
            problems.append(f"第 {i} 条 sentiment 只允许 positive/negative:{direction!r}")
            continue
        out.append({
            "unit_index": unit_index,
            "idx": unit.get("idx"),
            "region": unit.get("region"),
            "platform": unit.get("platform"),
            "question_id": unit.get("question_id"),
            "intent": unit.get("intent"),
            "brand": item["brand"],
            "brand_type": unit.get("brand_type"),
            "claim": str(item["claim"]).strip(),
            "attribute": str(item["attribute"]).strip(),
            "theme": str(item["theme"]).strip(),
            "sentiment": "positive" if direction in ("positive", "正向") else "negative",
            "evidence_text": unit.get("unit", ""),
        })
    if problems:
        for p in problems[:20]:
            print("校验失败:", p, file=sys.stderr)
        if len(problems) > 20:
            print(f"... 另有 {len(problems) - 20} 条", file=sys.stderr)
        raise SystemExit(f"claims 校验未通过（{len(problems)} 条问题）")
    json.dump({"meta": {"unit_source": args.units, "claim_count": len(out)},
               "claims": out}, open(args.output, "w"), ensure_ascii=False, indent=1)
    by_dir = collections.Counter(c["sentiment"] for c in out)
    print(f"回装 {len(out)} 条 claim（正向 {by_dir.get('positive', 0)} / 负向 {by_dir.get('negative', 0)}）")
    print(f"写入 {args.output}")


def _norm_claim_text(text) -> str:
    """去重用的 claim 文本归一：压空白 + casefold。语义级归一是抽取环节的职责。"""
    return " ".join(str(text or "").split()).casefold()


def cmd_claims_metrics(args: argparse.Namespace) -> None:
    """按设计的统计口径计算 Claim / Attribute / Theme 三层指标。

    口径（2026-09-20 设计定稿）：
      * 最小结构化单位 = Prompt × 平台 × 回答 × Brand × Claim；
      * 同一回答内、同一品牌 × 同一 semantic claim 只计 1 次
        （语义归一由抽取环节完成，这里按 claim 文本兜底去重）；
        同一 Attribute 下不同 Claim 各计一次；**跨回答分别计数**；
      * 正向占比 = 正向 Claim 信号数 ÷ 正负向 Claim 信号数合计；
      * 跨平台先算各平台占比，再对**有有效信号的平台等权平均**，无信号平台不补 0。
    """
    claims = _load_claims(args.claims)
    brands = [b.strip() for b in args.brands.split(",") if b.strip()] if args.brands else \
        sorted({c["brand"] for c in claims})
    if args.brand:
        claims = [c for c in claims if c["brand"] == args.brand]
        brands = [args.brand]

    def answer_key(c: dict) -> tuple:
        return (c.get("region", ""), c.get("platform", ""), c.get("idx"))

    # 回答内去重：同品牌 × 同 semantic claim 在一条回答里只算一次（按 claim 文本兜底）
    signal_keys: set[tuple] = set()
    per_brand_attr: dict[tuple, dict] = {}
    per_theme: dict[tuple, dict] = {}
    per_platform: dict[tuple, dict] = {}
    for c in claims:
        key = (c["brand"], answer_key(c), _norm_claim_text(c.get("claim")), c["sentiment"])
        if key in signal_keys:
            continue
        signal_keys.add(key)
        pk = (c["brand"], c.get("platform", ""))
        bucket = per_platform.setdefault(pk, {"pos": 0, "neg": 0})
        bucket["pos" if c["sentiment"] == "positive" else "neg"] += 1
        attr_key = (c["brand"], c["attribute"], c["sentiment"])
        per_brand_attr[attr_key] = per_brand_attr.get(attr_key, 0) + 1
        theme_key = (c["brand"], c["theme"], c["sentiment"])
        per_theme[theme_key] = per_theme.get(theme_key, 0) + 1

    def rate(pos: int, neg: int) -> str:
        total = pos + neg
        return f"{pos / total * 100:.1f}%" if total else "—"

    by_brand = {}
    for brand in brands:
        pos = sum(v for (b, _t, s), v in per_theme.items() if b == brand and s == "positive")
        neg = sum(v for (b, _t, s), v in per_theme.items() if b == brand and s == "negative")
        platform_rates = []
        for (b, plat), bucket in sorted(per_platform.items()):
            if b != brand or bucket["pos"] + bucket["neg"] == 0:
                continue
            platform_rates.append(bucket["pos"] / (bucket["pos"] + bucket["neg"]))
        by_brand[brand] = {
            "signal_total": pos + neg,
            "positive_signals": pos,
            "negative_signals": neg,
            "pos_rate": rate(pos, neg),
            "platforms_with_signal": len(platform_rates),
            "pos_rate_cross_platform": (
                f"{sum(platform_rates) / len(platform_rates) * 100:.1f}%" if platform_rates else "—"),
            "by_platform": {
                plat: {"positive": b["pos"], "negative": b["neg"], "pos_rate": rate(b["pos"], b["neg"])}
                for (brand_name, plat), b in sorted(per_platform.items()) if brand_name == brand
            },
            "by_attribute": sorted(
                ({"attribute": a, "sentiment": s, "occurrence": v}
                 for (b, a, s), v in per_brand_attr.items() if b == brand),
                key=lambda x: (-x["occurrence"], x["attribute"])),
            "by_theme": sorted(
                ({"theme": t, "sentiment": s, "occurrence": v}
                 for (b, t, s), v in per_theme.items() if b == brand),
                key=lambda x: x["theme"]),
        }

    metrics = {
        "brands": brands,
        "claim_total": len(claims),
        "deduped_signal_total": len(signal_keys),
        "by_brand": by_brand,
    }
    json.dump(metrics, open(args.out_metrics, "w"), ensure_ascii=False, indent=1)
    for brand in brands:
        s = by_brand[brand]
        print(f"{brand}: 信号 {s['signal_total']}（正 {s['positive_signals']} / 负 {s['negative_signals']}）"
              f" 正向占比 {s['pos_rate']}，跨平台等权 {s['pos_rate_cross_platform']}"
              f"（有信号平台 {s['platforms_with_signal']} 个）")
    print(f"写入 {args.out_metrics}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_extract = sub.add_parser("extract", help="抽取各品牌的判读单元（单品牌或词表多品牌）")
    p_extract.add_argument("--bank", required=True, help="题库：v8 JSON 或 upload CSV（query/question_types/tags）")
    p_extract.add_argument("--crawl-dir", required=True, help="采集目录（含 scraper.*/<区域>/NNNN.json）")
    p_extract.add_argument("--aliases", default=None,
                           help="单品牌模式：逗号分隔别名，须含当地文字转写，如 'YOUKU,优酷,ยูคุ,ยูคู'")
    p_extract.add_argument("--lexicon", default=None,
                           help="多品牌模式：品牌词表 JSON（brands[].name/aliases/type），每条单元带 brand")
    p_extract.add_argument("--brand", default=None, help="单品牌模式下写入 brand 字段的品牌名（默认取首个别名）")
    p_extract.add_argument("--brand-type", default=None, dest="brand_type",
                           help="单品牌模式下写入 brand_type 字段的类型（可选）")
    p_extract.add_argument("--output", required=True)

    p_compute = sub.add_parser("compute", help="按人工标签计算正负指标")
    p_compute.add_argument("--units", required=True, help="extract 产出的单元 JSON")
    p_compute.add_argument("--labels", required=True,
                           help='标签 JSON：{"positive": [索引...], "negative": [索引...]}')
    p_compute.add_argument("--brand", default=None,
                           help="只计算该品牌的单元（多品牌单元集分品牌出指标时使用）")
    p_compute.add_argument("--out-csv", required=True)
    p_compute.add_argument("--out-metrics", default=None)

    # Claim 层（四层结构：evidence_text → Claim → Attribute → Theme）
    p_assemble = sub.add_parser("claims-assemble",
                                help="把模型抽出的 Claim 回装成带证据与上下文的记录")
    p_assemble.add_argument("--units", required=True, help="extract 产出的单元 JSON")
    p_assemble.add_argument("--claims", required=True,
                            help="语义环节产出的 claims-raw JSON（unit_index/brand/claim/attribute/theme/sentiment）")
    p_assemble.add_argument("--output", required=True)

    p_cm = sub.add_parser("claims-metrics", help="按 Claim 信号口径统计正负与跨平台等权占比")
    p_cm.add_argument("--claims", required=True, help="claims-assemble 产出的 claims JSON")
    p_cm.add_argument("--brands", default=None, help="逗号分隔的品牌；缺省取 claim 里出现的全部品牌")
    p_cm.add_argument("--brand", default=None, help="只统计该品牌")
    p_cm.add_argument("--out-metrics", required=True)

    args = parser.parse_args()
    if args.command == "extract":
        cmd_extract(args)
    elif args.command == "compute":
        cmd_compute(args)
    elif args.command == "claims-assemble":
        cmd_claims_assemble(args)
    else:
        cmd_claims_metrics(args)


if __name__ == "__main__":
    main()
