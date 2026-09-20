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

# 竞品情感矩阵的行（Theme）。Theme 从各品牌 claims 的 label 归一，
# 取客户真正拿来横向比较的产品属性维度；匹配不到关键词的 label 归入「其他」，
# 「其他」不进入矩阵展示（含综合推荐、口碑、营销等非属性维度）。
THEME_KEYWORDS = {
    "安装与部署": ["免安装", "零管线", "需接管道", "安装受限", "免接管", "接管", "安装"],
    "体积与空间": ["机身超薄", "省空间", "机身深度", "体积笨重", "机身过深", "紧凑",
                 "纤薄", "超薄", "占空间", "深度", "空间", "体积", "机身", "摆放", "小户型"],
    "过滤与水质": ["过滤", "净水", "矿化", "净化", "滤芯", "ro", "去除矿物质", "碱性",
                 "口感", "水质", "矿物质"],
    "温控与出水": ["控温", "温控", "即热", "热水", "出水", "多温", "冷热", "冲奶"],
    "成本与价格": ["成本", "价格", "滤芯成本", "租赁成本", "价格透明", "实惠", "耗材",
                 "负担", "性价比", "加水"],
    "服务与售后": ["服务", "售后", "维护", "提醒"],
}
THEMES = list(THEME_KEYWORDS.keys())


def load_theme_keywords(path) -> dict:
    """从 JSON 覆盖 Theme 关键词表（换品类必做）。

    格式：{"<Theme 名>": ["关键词", ...], ...}。未提供时用内置的净水器品类词表。
    """
    if path is None:
        return dict(THEME_KEYWORDS)
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not payload:
        raise SystemExit(f"主题词表 {path} 应为非空 JSON 对象：{{\"<Theme>\": [关键词...]}}")
    for theme, keywords in payload.items():
        if not isinstance(keywords, list) or not keywords:
            raise SystemExit(f"主题词表 {path} 的「{theme}」缺少关键词数组")
    return {theme: [str(k) for k in keywords] for theme, keywords in payload.items()}


def theme_of(label: str, keywords: dict) -> str:
    """按关键词把 claims 的 label 归一到 Theme；匹配不到归入「其他」（不入矩阵）。"""
    lowered = (label or "").casefold()
    for theme, words in keywords.items():
        for keyword in words:
            if keyword.casefold() in lowered:
                return theme
    return "其他"


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
                      predicate, target: str) -> dict:
    """顶部「竞品情感占比」数据：每个品牌在给定切片下的正向情感占比。

    判读是按整句给方向的，没有逐句的属性标注；这里只按品牌汇总，
    用于 04 板块顶部的迷你条形图，不做大数字表格。
    """
    return {
        "columns": ["正向占比"],
        "rows": [
            {
                "brand": brand,
                "target": brand == target,
                "values": [rate(counts[brand][0], counts[brand][1])],
            }
            for brand in brands
        ],
    }


def build_theme_matrix(all_claims: dict, brands: list[str], predicate, theme_keywords: dict) -> dict:
    """竞品情感矩阵（Theme × 品牌）。

    对每个品牌，把它的 claims 按 Theme 归一；用 sliced_claims 的过滤逻辑
    统计当前切片内每个 Theme × 品牌的正负句数。「其他」不入矩阵。
    每个单元格取该 Theme 下计数最高的 claim 标签作为代表描述，并记录其方向。
    """
    themes = list(theme_keywords.keys())
    matrix: dict[str, dict[str, dict]] = {theme: {} for theme in themes}
    for brand in brands:
        groups = all_claims.get(brand) or {"pos": [], "neg": []}
        for direction, key in (("pos", "pos"), ("neg", "neg")):
            sliced = sliced_claims(groups[key], predicate)
            for group in sliced:
                theme = theme_of(group["label"], theme_keywords)
                if theme not in themes:
                    continue
                cell = matrix[theme].setdefault(brand, {
                    "pos": 0, "neg": 0, "top_claim": "", "top_count": 0, "top_dir": "",
                })
                cell[direction] += group["count"]
                # 取计数最高的 claim 作为该 Theme 的代表描述
                if group["count"] > cell["top_count"]:
                    cell["top_claim"] = group["label"]
                    cell["top_count"] = group["count"]
                    cell["top_dir"] = direction
    for theme in themes:
        for brand in brands:
            cell = matrix[theme].setdefault(brand, {
                "pos": 0, "neg": 0, "top_claim": "", "top_count": 0, "top_dir": "",
            })
            cell["rate"] = rate(cell["pos"], cell["neg"])
    return {"themes": themes, "brands": list(brands), "matrix": matrix}


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


def load_claim_groups(claims_dir: Path, sentences_path: Path, brand: str) -> dict:
    """读该品牌的「观点归纳」并挂回判读句子。

    归纳文件给出 label / count / indices / evidence，indices 指向
    judged-sentences.json 里该品牌同方向数组的下标。这里把它们展开成
    「每组携带自己的成员句子」，便于按切片过滤。
    """
    claims_path = claims_dir / f"{brand}-claims.json"
    if not claims_path.exists():
        raise SystemExit(f"缺少观点归纳文件：{claims_path}")
    groups = json.loads(claims_path.read_text(encoding="utf-8"))
    sentences = json.loads(sentences_path.read_text(encoding="utf-8"))[brand]
    out = {}
    for direction, key in (("pos", "positive"), ("neg", "negative")):
        members = sentences[key]
        built = []
        for group in groups.get(key) or []:
            picked = [members[i] for i in group.get("indices") or [] if 0 <= i < len(members)]
            built.append({
                "label": group.get("label") or "",
                "indices": group.get("indices") or [],
                "evidence": group.get("evidence") or (picked[0] if picked else {}),
                "members": picked,
            })
        out[direction] = built
    return out


def load_all_claim_groups(claims_dir: Path, sentences_path: Path, brands: list[str]) -> dict:
    """加载全部品牌的 claims 归纳；某品牌缺文件时给空组，不阻断其他品牌。"""
    out = {}
    for brand in brands:
        claims_path = claims_dir / f"{brand}-claims.json"
        if not claims_path.exists():
            out[brand] = {"pos": [], "neg": []}
            continue
        out[brand] = load_claim_groups(claims_dir, sentences_path, brand)
    return out


def sliced_claims(groups: list[dict], predicate) -> list[dict]:
    """按当前切片过滤观点组，并用切片内的成员重算计数。

    归纳是全局做的，某个切片里可能一条都不含某组；那种组直接不出现，
    否则计数会把别国别平台的数据算进来。
    """
    out = []
    for group in groups:
        inside = [m for m in group["members"] if predicate(m)]
        if not inside:
            continue
        evidence = group["evidence"] if predicate(group["evidence"]) else inside[0]
        out.append({
            "label": group["label"],
            "count": len(inside),
            "evidence": {
                "sentence": evidence.get("sentence") or "",
                "region": evidence.get("region"),
                "platform": evidence.get("platform"),
                "question_id": evidence.get("question_id"),
            },
        })
    out.sort(key=lambda g: (-g["count"], g["label"]))
    return out



# details 里 brands 的名字可能带「★」目标标记，匹配时去掉
STAR_SUFFIXES = (" ★", "★")


def _strip_brand_star(name: str) -> str:
    text = str(name or "").strip()
    for suffix in STAR_SUFFIXES:
        if text.endswith(suffix):
            text = text[: -len(suffix)].strip()
    return text


def build_answer_sentiment(units: list[dict], merged: dict, brands: list[str],
                           all_claims: dict, judged: dict,
                           qid: str, region: str, platform_internal: str) -> dict:
    """单条回答的品牌情感：该回答里每个被提及品牌的正/负标签与依据句。

    units 的数组位置是全局下标；judged-sentences 里的 `idx` 也是全局下标，
    claims 的 `indices` 指向「该品牌 judged-sentences 同方向数组」的下标。
    映射链：unit 位置 → judged idx → (品牌, 方向, 数组内下标) → claims label。
    """
    judged_set = set(merged["positive"]) | set(merged["negative"])

    # unit 位置 → (品牌, 方向, 品牌内下标)
    position_map: dict[int, tuple[str, str, int]] = {}
    for brand in brands:
        payload = judged.get(brand) or {}
        for direction, key in (("pos", "positive"), ("neg", "negative")):
            for inner_idx, member in enumerate(payload.get(key) or []):
                position_map[member.get("idx")] = (brand, direction, inner_idx)

    # claims 组查 label：品牌 + 方向 + 品牌内下标 → label
    label_of: dict[tuple[str, str, int], str] = {}
    for brand in brands:
        groups = (all_claims.get(brand) or {"pos": [], "neg": []})
        for direction, key in (("pos", "pos"), ("neg", "neg")):
            for group in groups.get(key) or []:
                for inner_idx in group.get("indices") or []:
                    label_of[(brand, direction, inner_idx)] = group.get("label") or ""

    out_brands: dict[str, dict] = {}
    for pos_i in sorted(judged_set):
        unit = units[pos_i]
        if (str(unit.get("question_id")) != qid
                or unit.get("region") != region
                or unit.get("platform") != platform_internal):
            continue
        brand, direction, inner_idx = position_map[pos_i]
        sentence = clean_text(unit.get("unit"))
        if not sentence:
            continue
        entry = out_brands.setdefault(brand, {"brand": brand, "pos_claims": [], "neg_claims": []})
        label = label_of.get((brand, direction, inner_idx)) or "其他"
        bucket = entry["pos_claims"] if direction == "pos" else entry["neg_claims"]
        bucket.append({"label": label, "sentence": sentence})

    ordered = [out_brands[b] for b in brands if b in out_brands]
    return {"brands": ordered}



def main() -> int:
    parser = argparse.ArgumentParser(description="把情感判读结果接入报告数据")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--units", type=Path, required=True)
    parser.add_argument("--labels-dir", type=Path, required=True)
    parser.add_argument("--brands", required=True, help="逗号分隔的展示品牌")
    parser.add_argument("--target", required=True)
    parser.add_argument("--theme-keywords", type=Path,
                        help="主题关键词表 JSON（{\"<Theme>\": [关键词...]}）；换品类必须提供，"
                             "缺省用内置的净水器品类词表，其他品类会整块落入「其他」不入矩阵")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    brands = [b.strip() for b in args.brands.split(",") if b.strip()]
    units = json.loads(args.units.read_text(encoding="utf-8"))["units"]
    merged = merge_labels(args.labels_dir, brands)

    report = json.loads(args.report.read_text(encoding="utf-8"))
    meta = report.get("meta", {})

    # question_id → 主题；units 里的 question_id 是补零字符串，meta.questions 用整数
    topic_of = {f"{int(q['qid']):04d}": q.get("topic") for q in meta.get("questions", [])}
    # question_id → 后端 diagnostic_intent；情感列只回写「sentiment 适用范围」的题
    # （口径 shared/canonical-intent-mapping.md：discovery / competitor / sentiment，
    # 对应中文 发现 / 竞品 / 评价），验证 / 准确性 / 品类认知题显示「—」。
    intent_of = {f"{int(q['qid']):04d}": q.get("diagnostic_intent")
                 for q in meta.get("questions", [])}
    SENTIMENT_INTENTS = {"discovery", "competitor", "sentiment"}

    claims_dir = args.labels_dir.parent / "sentiment-claims"
    sentences_path = claims_dir / "judged-sentences.json"
    target_groups = None
    all_claims: dict = {}
    if sentences_path.exists():
        target_groups = load_claim_groups(claims_dir, sentences_path, args.target)
        all_claims = load_all_claim_groups(claims_dir, sentences_path, brands)
    theme_keywords = load_theme_keywords(args.theme_keywords)
    if args.theme_keywords is None:
        print("提示: 未提供 --theme-keywords,主题矩阵使用内置净水器品类词表;"
              "换品类时未命中关键词的观点会整块落入「其他」而不进矩阵。")
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
                "pos": sliced_claims(target_groups["pos"], predicate) if target_groups
                      else top_claims(units, merged, args.target, "positive", predicate),
                "neg": sliced_claims(target_groups["neg"], predicate) if target_groups
                      else top_claims(units, merged, args.target, "negative", predicate),
            },
            "matrix": build_brand_table(units, merged, brands, counts, predicate, args.target),
            "theme_matrix": build_theme_matrix(all_claims, brands, predicate, theme_keywords)
                            if all_claims else None,
            "by_brand": {
                b: {
                    "positive": counts[b][0], "negative": counts[b][1],
                    "pos_rate": rate(counts[b][0], counts[b][1]),
                    # 观点数口径：去重后的 claim 组数，同一观点多句只算一次
                    **({
                        "pos_claims": len(sliced_claims(all_claims[b]["pos"], predicate)),
                        "neg_claims": len(sliced_claims(all_claims[b]["neg"], predicate)),
                        "claim_pos_rate": rate(
                            len(sliced_claims(all_claims[b]["pos"], predicate)),
                            len(sliced_claims(all_claims[b]["neg"], predicate)),
                        ),
                    } if all_claims.get(b) else {}),
                }
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

    # 明细表「正向情感占比」列：按切片口径聚目标品牌在该题下的正负句。
    # 单 region+单平台切片 → 只算该 (region, platform, qid)；
    # 混合切片（全部国家/全部平台）→ 对该 qid 的所有 units 做池化聚合。
    from collections import defaultdict
    by_rpq: dict[tuple[str, str, str], tuple[int, int]] = defaultdict(lambda: (0, 0))
    by_qid: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))
    by_region_qid: dict[tuple[str, str], tuple[int, int]] = defaultdict(lambda: (0, 0))
    by_platform_qid: dict[tuple[str, str], tuple[int, int]] = defaultdict(lambda: (0, 0))
    for i in pos_sets[args.target]:
        u = units[i]
        r_, p_, q_ = u.get("region", ""), u.get("platform", ""), str(u.get("question_id", ""))
        for d, k in ((by_rpq, (r_, p_, q_)), (by_qid, q_),
                     (by_region_qid, (r_, q_)), (by_platform_qid, (p_, q_))):
            pos_n, neg_n = d[k]
            d[k] = (pos_n + 1, neg_n)
    for i in neg_sets[args.target]:
        u = units[i]
        r_, p_, q_ = u.get("region", ""), u.get("platform", ""), str(u.get("question_id", ""))
        for d, k in ((by_rpq, (r_, p_, q_)), (by_qid, q_),
                     (by_region_qid, (r_, q_)), (by_platform_qid, (p_, q_))):
            pos_n, neg_n = d[k]
            d[k] = (pos_n, neg_n + 1)

    filled_records = 0
    for slice_key, slice_value in report["slices"].items():
        region, platform_display, _ = (slice_key.split("|") + ["", "", ""])[:3]
        internal = PLATFORM_INTERNAL.get(platform_display) if platform_display else None
        for rec in slice_value.get("records", []):
            qid_str = str(rec["qid"]).zfill(4)
            if intent_of.get(qid_str) not in SENTIMENT_INTENTS:
                rec["sentiment"] = None
                continue
            if region and internal:
                pos_n, neg_n = by_rpq.get((region, internal, qid_str), (0, 0))
            elif region:
                pos_n, neg_n = by_region_qid.get((region, qid_str), (0, 0))
            elif internal:
                pos_n, neg_n = by_platform_qid.get((internal, qid_str), (0, 0))
            else:
                pos_n, neg_n = by_qid.get(qid_str, (0, 0))
            if pos_n + neg_n > 0:
                rec["sentiment"] = f"{pos_n * 100 / (pos_n + neg_n):.1f}%"
                filled_records += 1
            else:
                rec["sentiment"] = None

    # 抽屉「品牌情感」面板：按单条回答（region|平台显示名|qid）挂每个品牌的
    # 正/负标签与依据句。judged-sentences 缺失时跳过，面板显示「无判读数据」。
    if sentences_path.exists():
        judged = json.loads(sentences_path.read_text(encoding="utf-8"))
        for detail_key, detail_value in report.get("details", {}).items():
            region, platform_display, qid = (detail_key.split("|") + ["", "", ""])[:3]
            internal = PLATFORM_INTERNAL.get(platform_display) if platform_display else None
            if not (region and internal and qid):
                continue
            detail_value["sentiment"] = build_answer_sentiment(
                units, merged, brands, all_claims, judged, qid, region, internal)

    meta["sentiment_claims_status"] = "complete"
    meta["sentiment_brands"] = brands
    meta["sentiment_note"] = (
        "情感仅判读了报告中展示的 %d 个品牌；其余开放品牌未判读。"
        "正向率 = 正向句 ÷（正向句 + 负向句），排除中性；"
        "观点数口径 = 去重后的正向观点组数 ÷（正向+负向观点组数），"
        "同一观点多句只算一次；"
        "观点标签与计数来自句子级判读的归纳，计数为该切片内的出现次数。" % len(brands)
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
