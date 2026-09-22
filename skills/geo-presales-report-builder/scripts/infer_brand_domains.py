"""从引用来源推断开放品牌的官网域名。

用法：
    python3 infer_brand_domains.py --collect <采集目录> --lexicon <词表.json> \
        --out <推断结果.json> [--candidates <候选清单.json>]

为什么需要这一步：引用分类里「竞品网站」按对象官网域名判定（core 的
`_classify_official`），但词表里只有目标与配置竞品通常带域名，开放品牌的官网
一律落进「其他」——实测一份视频流媒体报告里 mgtv.com / viu.com / bilibili.tv
共 160+ 条引用被误归「其他」。

高置信规则：引用的**注册域名标签**与品牌名/别名的归一化形式相同
（`viu.com`↔Viu、`bilibili.tv`↔Bilibili、`netflix.com`↔Netflix）。
推不出的（如 `mgtv.com`↔「Mango TV」这类缩写）写进候选清单，交搜索或人工确认——
**不得**用模糊相似度硬猜，猜错会把别家官网算成竞品网站。
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]
                       / "geo-presales-report-editor" / "scripts"))
from geo_presales_core.util import normalize_host, registrable_domain  # noqa: E402

# 这些标签过于通用，与品牌同名也不足以判定为官网
STOP_LABELS = {"tv", "app", "www", "com", "net", "plus", "video", "stream", "online", "go"}


def norm_alias(text: str) -> str:
    """别名归一：只留字母数字，小写。中文别名按原样保留。"""
    return re.sub(r"[^0-9a-z一-鿿]+", "", str(text).casefold())


def collect_hosts(collect_dir: Path) -> collections.Counter:
    """从采集 JSON 里抓出所有引用 host（宽松匹配 URL，不做引用口径判定）。"""
    hosts: collections.Counter = collections.Counter()
    for path in collect_dir.glob("scraper.*/*/*.json"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in re.finditer(r'https?://([^/\\"\s]+)', text):
            host = normalize_host(match.group(1))
            if host:
                hosts[host] += 1
    return hosts


def load_lexicon(path: Path) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    brands = raw.get("brands") if isinstance(raw, dict) else raw
    if not isinstance(brands, list) or not brands:
        raise SystemExit(f"{path} 缺少非空的 brands 数组")
    return brands


def infer(hosts: collections.Counter, brands: list[dict]) -> tuple[dict, list[dict]]:
    """返回 (高置信推断 {品牌名: [域名]}, 候选清单)。"""
    label_counts: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for host, count in hosts.items():
        domain = registrable_domain(host) or host
        label = domain.split(".")[0]
        if label and label not in STOP_LABELS:
            label_counts[label][domain] += count

    taken = {d for brand in brands for d in (brand.get("official_domains") or [])}
    inferred: dict[str, list[str]] = {}
    for brand in brands:
        if brand.get("official_domains"):
            continue                      # 已声明域名的（通常目标与配置竞品）不动
        names = {norm_alias(brand.get("name"))} | {norm_alias(a) for a in brand.get("aliases") or []}
        names.discard("")
        for label, domains in label_counts.items():
            if label in names:
                found = [d for d in domains if d not in taken]
                if found:
                    inferred[brand["name"]] = sorted(found)
                    taken.update(found)

    candidates = []
    for host, count in hosts.most_common():
        domain = registrable_domain(host) or host
        if domain in taken or any(domain in ds for ds in inferred.values()):
            continue
        candidates.append({"host": host, "domain": domain, "count": count})
    return inferred, candidates[:60]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collect", required=True, type=Path)
    parser.add_argument("--lexicon", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path, help="高置信推断结果 {品牌: [域名]}")
    parser.add_argument("--candidates", type=Path, default=None, help="推不出的候选清单")
    args = parser.parse_args(argv)

    hosts = collect_hosts(args.collect)
    brands = load_lexicon(args.lexicon)
    inferred, candidates = infer(hosts, brands)

    args.out.write_text(json.dumps(inferred, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"引用 host {len(hosts)} 个 → 高置信推断出 {len(inferred)} 个品牌的官网：")
    for name, domains in sorted(inferred.items()):
        print(f"  {name}: {', '.join(domains)}")
    if args.candidates:
        args.candidates.write_text(json.dumps(candidates, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
        print(f"推不出的高频 host 候选 {len(candidates)} 个写入 {args.candidates}（交搜索/人工确认）")
    print(f"写入 {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
