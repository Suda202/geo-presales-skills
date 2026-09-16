"""收集引用来源里尚未登记的域名，供人工/模型判读类别。

引用来源分类不是封闭集合：`geo_presales_core` 的 `KNOWN_HOST_TYPES` 只放稳定的高频域名，
其余走 `assets/domain-categories.json` 缓存。本脚本负责找出缓存里还没有的域名，
连同页面标题一起输出，判读后写回缓存，下次运行即命中。

用法：
    python3 collect_domain_candidates.py --collect <采集目录> --case <Case.json> \
        --cache assets/domain-categories.json --out build/domain-candidates.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

REPO_SCRIPTS = Path(os.environ.get(
    "GEO_PRESALES_SKILLS_ROOT", str(Path(__file__).resolve().parents[2])
)) / "geo-presales-report-editor" / "scripts"

CITATION_FIELD = {
    "overview": "source",
    "gemini": "citations",
    "chatgpt": "content_references",
    "perplexity": "web_results",
}
PLATFORM_HOST_SUFFIXES = ("google.com", "gstatic.com", "googleusercontent.com")

# Case 字段（飞书表头）→ 归一化用
CASE_BRAND_KEYS = ("品牌名称", "brand", "品牌")
CASE_DOMAIN_KEYS = ("官方域名", "official_domain", "品牌官网")
CASE_COMPETITOR_KEYS = ("竞品 1", "竞品 2", "竞品 3", "competitors")
CASE_COMPETITOR_DOMAIN_KEYS = ("竞品 1 官网域名", "竞品 2 官网域名", "竞品 3 官网域名")


def normalize_host(value: str) -> str:
    host = str(value or "").strip().casefold()
    host = host.split("//")[-1].split("/")[0].split("?")[0]
    for prefix in ("www.", "m.", "amp."):
        if host.startswith(prefix):
            host = host[len(prefix):]
    return host


def load_case(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    brand = next((raw[k] for k in CASE_BRAND_KEYS if raw.get(k)), "")

    domains = [normalize_host(raw[k]) for k in CASE_DOMAIN_KEYS if raw.get(k)]
    if isinstance(raw.get("official_domain"), list):
        domains = [normalize_host(d) for d in raw["official_domain"]]

    competitors = []
    for key in CASE_COMPETITOR_KEYS[:3]:
        name = str(raw.get(key) or "").strip()
        domain = normalize_host(raw.get(f"{key} 官网域名") or raw.get(f"{key.replace('竞品 ', 'competitor_')}_domain") or "")
        if name:
            competitors.append({"name": name, "domain": domain})
    for item in raw.get("competitors") or []:
        name = str(item.get("name") or "").strip()
        if name and not any(c["name"] == name for c in competitors):
            competitors.append({"name": name, "domain": normalize_host(item.get("domain") or "")})

    return {
        "brand": str(brand).strip(),
        "domains": [d for d in domains if d],
        "competitors": competitors,
    }


def load_cache(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def matches(host: str, domain: str) -> bool:
    if not host or not domain:
        return False
    return host == domain or host.endswith("." + domain)


def scan(collect_dir: Path, case: dict, cache: dict) -> list[dict]:
    sys.path.insert(0, str(REPO_SCRIPTS))
    from geo_presales_core.deterministic import KNOWN_HOST_TYPES  # noqa: E402

    known = set(KNOWN_HOST_TYPES) | set(cache)
    owned = list(case["domains"]) + [c["domain"] for c in case["competitors"] if c["domain"]]

    found: dict[str, dict] = defaultdict(lambda: {"count": 0, "titles": []})
    for platform, field in CITATION_FIELD.items():
        platform_dir = collect_dir / f"scraper.{platform}"
        if not platform_dir.is_dir():
            continue
        for region_dir in sorted(p for p in platform_dir.iterdir() if p.is_dir()):
            for path in sorted(region_dir.glob("*.json")):
                result = (json.loads(path.read_text(encoding="utf-8")).get("task_result") or {})
                for entry in result.get(field) or []:
                    raw_url = str(entry.get("url") or "").strip()
                    if not raw_url:
                        continue
                    host = normalize_host(urlsplit(raw_url).netloc)
                    if not host or any(host == s or host.endswith("." + s) for s in PLATFORM_HOST_SUFFIXES):
                        continue
                    if any(matches(host, d) for d in owned):
                        continue
                    if any(matches(host, d) for d in known):
                        continue
                    found[host]["count"] += 1
                    title = str(entry.get("title") or entry.get("name") or entry.get("attribution") or "").strip()
                    if title and title not in found[host]["titles"] and len(found[host]["titles"]) < 2:
                        found[host]["titles"].append(title[:90])

    return [
        {"domain": host, "count": item["count"], "titles": item["titles"]}
        for host, item in sorted(found.items(), key=lambda pair: (-pair[1]["count"], pair[0]))
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="收集未登记的引用域名")
    parser.add_argument("--collect", type=Path, required=True)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    case = load_case(args.case)
    cache = load_cache(args.cache)
    candidates = scan(args.collect, case, cache)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(candidates, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    covered = sum(item["count"] for item in candidates)
    print(f"缓存已登记 {len(cache)} 个域名；本次新增候选 {len(candidates)} 个，涉及 {covered} 条引用")
    print(f"写出 {args.out}")
    if candidates:
        print("判读后写回 " + str(args.cache) + "，格式为扁平映射 {域名: 类别}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
