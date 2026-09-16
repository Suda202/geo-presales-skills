"""把原始爬虫输出规范化为可审计的回答记录，并做确定性去引用。

这是在「报告 JSON 层」之前的一步：结构化结果审计（structured_result_audit.py）
消费已经带 wordid / brand_rankings 的 JSON；本脚本消费的是采集目录里的原始响应，
产出与采集方无关的正文，供品牌抽取与后续审计使用。

只做确定性清洗，不识别品牌、不判情绪。

用法
    python3 de_cite_crawl.py --collect-dir <采集目录> --question-bank <题库.json> \
        --out <输出>/normalized-answers.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

# 回答正文在哪里。清洗与分层检查都以此为准。
PLATFORM_ANSWER_FIELD = {
    "chatgpt": ["result_text"],
    "gemini": ["result_text"],
    "aimode": ["result_md", "result_text"],
    "overview": ["content", "rawtext"],
    "perplexity": ["result_text"],
}

# 正文引用标记的两种形态，四平台一致
REF_DEF = re.compile(r"^\s*\[\d+\]:\s*\S+.*$", re.M)
REF_MARKER_PAREN = re.compile(r"\(\[[^\]\n]{1,80}\]\[\d+\]\)")
REF_MARKER_BARE = re.compile(r"\[[^\]\n]{1,80}\]\[\d+\]")
IMAGE = re.compile(r"!\[[^\]\n]*\]\([^)\n]*\)")
MD_LINK = re.compile(r"\[([^\]\n]*)\]\([^)\n]*\)")
HTML_TAG = re.compile(r"<[^>]{1,300}>")

# 失败页判定统一走 geo_presales_core 的唯一实现，不在下游复刻一份签名表。
# 该目录归 geo-presales-report-editor 所有，签名与长度阈值由它定义。
SKILLS_ROOT = Path(os.environ.get(
    "GEO_PRESALES_SKILLS_ROOT", str(Path(__file__).resolve().parents[2])))
CORE_DIR = SKILLS_ROOT / "geo-presales-report-editor" / "scripts"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from geo_presales_core.crawler import answer_validity  # noqa: E402


def dig(payload: dict, key: str):
    node = payload
    for part in ("task_result", key):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return None
    return node


def answer_text(payload: dict, platform: str) -> str:
    for key in PLATFORM_ANSWER_FIELD.get(platform, ["result_text"]):
        value = dig(payload, key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def strip_citations(text: str) -> str:
    """去掉引用标记与来源名称，保留正文与商品卡可见标题。

    商品卡形如 `| id | goods | price | rating | merchants | picture |`：
    `goods` 列是可见产品名，保留；`merchants` 列是销售渠道，由
    blank_merchant_columns 另行清空，避免渠道名被当成正文品牌。
    """
    text = REF_DEF.sub("", text)
    text = REF_MARKER_PAREN.sub("", text)
    text = REF_MARKER_BARE.sub("", text)
    text = IMAGE.sub("", text)
    text = MD_LINK.sub(r"\1", text)
    text = HTML_TAG.sub("", text)
    text = text.replace("\\$", "$")
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{4,}", "\n\n\n", text).strip()


def blank_merchant_columns(markdown: str) -> str:
    """清空商品卡 merchants 列。

    该列只会出现销售渠道（Best Buy，或品牌自营店），不构成采购候选，
    因此不能用来决定一个品牌的首次出现位置。
    """
    lines = markdown.split("\n")
    merchant_index = None
    out = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            merchant_index = None
            out.append(line)
            continue
        cells = stripped.strip("|").split("|")
        if merchant_index is None:
            header = [c.strip().lower() for c in cells]
            if "merchants" in header:
                merchant_index = header.index("merchants")
            elif all(set(c) <= set("-: ") for c in cells):
                continue
        if merchant_index is not None and merchant_index < len(cells):
            cells[merchant_index] = ""
            out.append("|" + "|".join(cells) + "|")
        else:
            out.append(line)
    return "\n".join(out)


def to_plain(markdown: str) -> str:
    text = markdown.replace("**", "").replace("*", "")
    text = re.sub(r"^\s*\|", " ", text, flags=re.M)
    return re.sub(r"[ \t]{2,}", " ", text)


def load_question_index(bank_path: Path) -> dict:
    bank = json.loads(bank_path.read_text())
    topics = {t["topic_id"]: t["topic"] for t in bank["config"].get("topics", [])}
    index = {}
    for q in bank["questions"]:
        prompt = (q.get("monitoring_prompt") or q.get("user_question") or "").strip()
        analysis = q.get("analysis_type", "visibility")
        types = ["visibility", "sentiment"] if analysis == "visibility" else ["sentiment"]
        index[prompt] = {
            "question_id": q["question_id"],
            "topic_id": q.get("topic_id"),
            "topic": topics.get(q.get("topic_id"), q.get("topic_id")),
            "diagnosis_intent": q.get("diagnosis_intent"),
            "question_types": types,
            "analysis_type": analysis,
            "formal_visibility_eligible": q.get("formal_visibility_eligible"),
            "question_en": q.get("user_question", prompt),
            "question_zh": q.get("zh_translation", ""),
        }
    return index


def detect_platforms(collect_dir: Path):
    for child in sorted(collect_dir.iterdir()):
        if child.is_dir() and child.name.startswith("scraper."):
            yield child.name.split(".", 1)[1], child


def normalize(collect_dir: Path, bank_path: Path):
    question_index = load_question_index(bank_path)
    rows, unknown = [], set()
    for platform, platform_dir in detect_platforms(collect_dir):
        for path in sorted(platform_dir.rglob("*.json")):
            raw = json.loads(path.read_text())
            prompt = str(dig(raw, "prompt") or "").strip()
            meta = question_index.get(prompt)
            if meta is None:
                unknown.add(prompt)
                continue
            source = answer_text(raw, platform)
            body = strip_citations(source)
            valid, invalid_code = answer_validity(body)
            rows.append({
                "answer_id": f"{platform}:{meta['question_id']}:{path.stem}",
                "question_id": meta["question_id"],
                "topic": meta["topic"],
                "topic_id": meta["topic_id"],
                "diagnosis_intent": meta["diagnosis_intent"],
                "question_types": meta["question_types"],
                "analysis_type": meta["analysis_type"],
                "formal_visibility_eligible": meta["formal_visibility_eligible"],
                "question_en": meta["question_en"],
                "question_zh": meta["question_zh"],
                "platform": platform,
                "repeat": int(path.stem) if path.stem.isdigit() else path.stem,
                "source_file": str(path),
                "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
                "capture_status": raw.get("status"),
                "answer_status": "available" if valid else "unavailable",
                "invalid_code": invalid_code,
                "body_markdown": body,
                "body_ranking": blank_merchant_columns(body),
                "body_plain": to_plain(body),
            })
    if unknown:
        raise SystemExit(
            "以下 prompt 不在题库中，先确认题库版本："
            + "；".join(sorted(unknown)[:5])
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--collect-dir", required=True)
    parser.add_argument("--question-bank", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    rows = normalize(Path(args.collect_dir).expanduser().resolve(),
                     Path(args.question_bank).expanduser().resolve())
    out = Path(args.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    available = [r for r in rows if r["answer_status"] == "available"]
    print(f"rows={len(rows)} available={len(available)} unavailable={len(rows) - len(available)}")
    print("by platform:", dict(Counter(r["platform"] for r in rows)))
    print("by intent:", dict(Counter(r["diagnosis_intent"] for r in rows)))
    print("wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
