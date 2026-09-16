#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mine an open-brand candidate table from Scrapeless GEO answer JSON.

Why this exists
---------------
The presales report computes share-of-voice with a denominator of *every brand
named in an AI answer*, not just the three pre-configured competitors. That is
only possible if brand names can be recovered from free-form English prose and
separated from the technical abbreviations, media names, place names and
product-model fragments that share the same capitalisation.

This script does the mechanical half of that job:

  1. Walk a collection directory laid out as
     ``<collect_dir>/scraper.<platform>/<REGION>/<NNNN>.json``.
  2. Pull the answer body (``task_result.content`` for ``overview``,
     ``task_result.result_text`` for the other platforms).
  3. Clean the body (see CLEANING below).
  4. Extract capitalised candidates: single tokens and 1-2 word runs.
  5. Classify each candidate against a brand lexicon and emit the rest as
     ``unknown`` so a human can rule on them.

It is re-runnable: point ``--collect-dir`` at a fresh collection and rerun to
re-mine, or pass ``--lexicon`` to check a curation against new data.

CLEANING
--------
Markdown/Scrapeless artefacts are removed *without* discarding brand evidence:

  * ``<EntityCard ... title="X"/>`` -> the ``title`` text is kept, the tag goes.
  * markdown link targets ``[text](url)`` -> ``text`` is kept.
  * reference definition lines ``[N]: url "title"`` -> dropped entirely.
  * bare URLs / ``www.`` hosts -> dropped.
  * the Scrapeless anchor artefact ``Go to product viewer dialog for this
    item.`` -> dropped (it is glued onto product names and would otherwise
    create junk tokens such as ``DispenserGo``).

Usage
-----
    python3 mine_brand_lexicon.py                       # mine with defaults
    python3 mine_brand_lexicon.py --min-count 2 --top 300
    python3 mine_brand_lexicon.py --collect-dir /path/to/collect --out /tmp/x.csv
    python3 mine_brand_lexicon.py --lexicon assets/brand_lexicon.water-purifier-sea.json
"""

from __future__ import annotations

import argparse
import collections
import csv
import glob
import html
import json
import os
import re
import sys

# --------------------------------------------------------------------------
# Defaults (override on the command line)
# --------------------------------------------------------------------------

DEFAULT_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "build", "brand_candidates.csv")

PLATFORMS = ["overview", "gemini", "chatgpt", "perplexity"]
REGIONS = ["MY", "SG"]

# ``overview`` keeps its prose in ``content``; the chat-shaped platforms use
# ``result_text``.
TEXT_FIELD = {"overview": "content"}
TEXT_FIELD_DEFAULT = "result_text"

# --------------------------------------------------------------------------
# Cleaning
# --------------------------------------------------------------------------

PRODUCT_VIEWER_NOISE = "Go to product viewer dialog for this item."


def clean_text(raw: str) -> str:
    """Strip Scrapeless/markdown wrapping while preserving brand-bearing text."""
    if not raw:
        return ""
    t = html.unescape(raw)

    # Keep the EntityCard title, discard the tag.
    t = re.sub(r'<EntityCard\b[^>]*?\btitle="([^"]*)"[^>]*?/>', r" \1 ", t)
    t = re.sub(r"<EntityCard\b[^>]*?/>", " ", t)
    t = re.sub(r"<EntityCard\b[^>]*?>", " ", t)
    # Any other HTML/XML-ish tag (img, br, span, ...).
    t = re.sub(r"<[^>]{0,400}>", " ", t)

    # Scrapeless anchor artefact glued onto product names.
    t = t.replace(PRODUCT_VIEWER_NOISE, " ")

    # Reference definition lines: [1]: https://... "Title"  (whole line goes).
    t = re.sub(r'^[ \t]*\[\d+\]:[ \t]*\S+.*$', "", t, flags=re.M)
    t = re.sub(r'^[ \t]*\[\d+\]:[ \t]*$', "", t, flags=re.M)

    # Markdown links -> keep the visible text. Handles nested brackets too.
    prev = None
    while prev != t:
        prev = t
        t = re.sub(r"\[([^\[\]]*)\]\((?:[^()]*)\)", r"\1", t)
        t = re.sub(r"\[([^\[\]]*)\]\[[^\[\]]*\]", r"\1", t)

    # Bare URLs and www hosts.
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"\bwww\.\S+", " ", t)

    # Collapse whitespace.
    t = re.sub(r"[ \t ]+", " ", t)
    t = re.sub(r"\n{2,}", "\n", t)
    return t


# --------------------------------------------------------------------------
# Candidate extraction
# --------------------------------------------------------------------------

# A capitalised word: leading capital, then letters/digits; allows the usual
# brand-joiners found in this corpus ( - & . ' + ).
WORD = r"[A-Z][A-Za-z0-9]*(?:[&.'+][A-Za-z0-9]+)*"
TOKEN_RE = re.compile(r"\b" + WORD + r"\b")
# 2- and 3-word runs of capitalised words (e.g. "Coway Malaysia",
# "Water Filter Guru", "British Berkefeld").
NGRAM_RE = re.compile(r"\b" + WORD + r"(?:\s+" + WORD + r"){1,2}\b")


def usable(cand: str) -> bool:
    """Drop single stray capitals ('A', 'I') that are never brand evidence.

    All-caps tokens (RO, TDS, LG, PUR) are kept on purpose: they are exactly
    what the stopword layer exists to absorb, and keeping them in the table
    lets a reviewer see that they were classified rather than silently lost.
    """
    return len(cand) >= 2


def iter_docs(collect_dir: str):
    """Yield (platform, region, path, body_text) for every collected answer."""
    for platform in PLATFORMS:
        for region in REGIONS:
            pattern = os.path.join(collect_dir, f"scraper.{platform}",
                                   region, "*.json")
            for path in sorted(glob.glob(pattern)):
                try:
                    with open(path, encoding="utf-8") as fh:
                        payload = json.load(fh)
                except (OSError, ValueError):
                    continue
                task = payload.get("task_result") or {}
                field = TEXT_FIELD.get(platform, TEXT_FIELD_DEFAULT)
                body = task.get(field) or ""
                yield platform, region, path, clean_text(body)


def mine(collect_dir: str):
    """Return (occurrences, doc_count, sample_sentences, stats)."""
    occ = collections.Counter()
    docs = collections.Counter()
    samples = {}

    n_files = 0
    for platform, region, path, text in iter_docs(collect_dir):
        n_files += 1
        seen = set()
        for regex in (TOKEN_RE, NGRAM_RE):
            for m in regex.finditer(text):
                cand = m.group(0).strip()
                if not usable(cand):
                    continue
                occ[cand] += 1
                seen.add(cand)
                if cand not in samples:
                    a = max(0, m.start() - 60)
                    b = min(len(text), m.end() + 80)
                    samples[cand] = re.sub(r"\s+", " ", text[a:b]).strip()
        for cand in seen:
            docs[cand] += 1
    return occ, docs, samples, {"files": n_files}


# --------------------------------------------------------------------------
# Lexicon matching
# --------------------------------------------------------------------------

def load_lexicon(path: str):
    """Return (alias->brand, stopword set) lowercased, longest alias first."""
    with open(path, encoding="utf-8") as fh:
        lex = json.load(fh)
    alias_map = {}
    for brand in lex.get("brands", []):
        name = brand["name"]
        for alias in [name, *brand.get("aliases", [])]:
            if alias:
                alias_map[alias.lower()] = name
    for entry in lex.get("uncertain", []):
        name = entry.get("name") if isinstance(entry, dict) else entry
        if name:
            alias_map.setdefault(name.lower(), f"uncertain:{name}")
    stop = {w.lower() for w in lex.get("stopwords", []) if w}
    return alias_map, stop


def classify(cand: str, alias_map, stop):
    """Return a verdict string for one candidate.

    Longest-alias-first so that "Aqua Kent Singapore" resolves to the brand
    "Aqua Kent" instead of being swallowed by the bare "Aqua" stopword, and
    "Bewinch's" resolves via possessive stripping.
    """
    low = cand.lower().strip()
    if low.endswith("'s"):
        low = low[:-2]
    if low in alias_map:
        return alias_map[low]
    if low in stop:
        return "stopword"
    # Any alias that is a whole-word prefix of the candidate ("Aqua Kent
    # Singapore", "Velta HydroFirst+").
    for alias, brand in alias_map.items():
        if len(alias) < len(low) and low.startswith(alias) and \
                low[len(alias)] in " -+/&":
            return brand
    # An n-gram whose head word is a known brand ("Coway Malaysia").
    parts = low.split()
    if len(parts) > 1 and parts[0] in alias_map:
        return alias_map[parts[0]]
    if len(parts) > 1 and parts[0] in stop:
        return "stopword"
    return "unknown"


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--collect-dir", required=True,
                    help="directory holding scraper.<platform>/<REGION>/*.json")
    ap.add_argument("--out", default=DEFAULT_OUT, help="candidate CSV path")
    ap.add_argument("--lexicon", default=None,
                    help="brand lexicon JSON used for classification; "
                         "omitted = classify without it")
    ap.add_argument("--min-count", type=int, default=2,
                    help="drop candidates below this occurrence count "
                         "(default 2; singletons are mostly citation artefacts)")
    ap.add_argument("--top", type=int, default=0,
                    help="only emit the N most frequent candidates (0 = all)")
    ap.add_argument("--show-unknown", type=int, default=40,
                    help="how many unknown candidates to print to stdout")
    args = ap.parse_args(argv)

    if not os.path.isdir(args.collect_dir):
        ap.error(f"collect dir not found: {args.collect_dir}")

    alias_map, stop = {}, set()
    if args.lexicon and os.path.isfile(args.lexicon):
        alias_map, stop = load_lexicon(args.lexicon)
    elif args.lexicon:
        print(f"[warn] lexicon not found, classifying without it: "
              f"{args.lexicon}", file=sys.stderr)

    occ, docs, samples, stats = mine(args.collect_dir)

    rows = []
    for cand, count in occ.most_common():
        if count < args.min_count:
            continue
        rows.append({
            "candidate": cand,
            "occurrences": count,
            "doc_count": docs[cand],
            "words": len(cand.split()),
            "verdict": classify(cand, alias_map, stop),
            "sample": samples.get(cand, ""),
        })
    if args.top:
        rows = rows[:args.top]

    out_path = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["candidate", "occurrences", "doc_count", "words",
                            "verdict", "sample"])
        writer.writeheader()
        writer.writerows(rows)

    verdicts = collections.Counter(r["verdict"].split(":")[0] for r in rows)
    n_stop = verdicts.get("stopword", 0)
    n_unknown = verdicts.get("unknown", 0)
    print(f"files scanned : {stats['files']}")
    print(f"candidates    : {len(occ)} distinct, {len(rows)} emitted")
    print(f"  brand-name  : {len(rows) - n_stop - n_unknown}")
    print(f"  stopword    : {n_stop}")
    print(f"  unknown     : {n_unknown}")
    print(f"csv           : {out_path}")

    unknown = [r for r in rows if r["verdict"] == "unknown"]
    if unknown and args.show_unknown:
        print(f"\ntop {args.show_unknown} unclassified candidates "
              f"(rule these in/out, then add to the lexicon):")
        for r in unknown[:args.show_unknown]:
            print(f"  {r['occurrences']:>5}  {r['candidate']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
