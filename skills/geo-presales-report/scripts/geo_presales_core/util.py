from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TRACKING_QUERY_KEYS = {
    "gclid",
    "fbclid",
    "msclkid",
    "mc_cid",
    "mc_eid",
}

# Standard-library-only approximation used for display aggregation. Official-domain
# matching never depends on this list. The audit artifact exposes this limitation.
COMMON_MULTI_LABEL_SUFFIXES = {
    "co.uk", "org.uk", "ac.uk", "gov.uk",
    "com.au", "net.au", "org.au",
    "co.jp", "ne.jp", "or.jp",
    "com.cn", "net.cn", "org.cn", "gov.cn",
    "com.sg", "com.hk", "com.tw", "co.nz",
    "com.br", "com.mx", "co.in", "co.kr",
}


class ContractError(ValueError):
    """Raised when an input or task result violates a frozen contract."""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: str | Path):
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_obj(value) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def write_json(path: str | Path, value) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=False)
            handle.write("\n")
        os.replace(temp_name, target)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def write_text(path: str | Path, value: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(value)
        os.replace(temp_name, target)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    text = re.sub(r"[\u2010-\u2015\u2212]", "-", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_alias(value: str) -> str:
    text = normalize_text(value)
    text = re.sub(r"[^\w]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def find_alias_spans(text: str, aliases: list[str]) -> list[dict]:
    normalized = unicodedata.normalize("NFKC", str(text or ""))
    matches: list[dict] = []
    for raw_alias in sorted({str(a).strip() for a in aliases if str(a).strip()}, key=len, reverse=True):
        alias = unicodedata.normalize("NFKC", raw_alias)
        escaped = re.escape(alias).replace(r"\ ", r"[\s\-_\.]*")
        left = r"(?<![\w])" if alias[:1].isalnum() else ""
        right = r"(?![\w])" if alias[-1:].isalnum() else ""
        pattern = re.compile(left + escaped + right, re.IGNORECASE | re.UNICODE)
        for found in pattern.finditer(normalized):
            matches.append({
                "alias": raw_alias,
                "matched_text": found.group(0),
                "start": found.start(),
                "end": found.end(),
            })
    matches.sort(key=lambda item: (item["start"], -(item["end"] - item["start"]), item["alias"].casefold()))
    deduped: list[dict] = []
    seen = set()
    for item in matches:
        key = (item["start"], item["end"], item["alias"].casefold())
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped


def normalize_host(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = "https://" + raw
    try:
        host = (urlsplit(raw).hostname or "").rstrip(".").lower()
        host = host.encode("idna").decode("ascii")
    except (ValueError, UnicodeError):
        return ""
    if host.startswith("www."):
        host = host[4:]
    return host


def domain_matches(host: str, official_domain: str) -> bool:
    host = normalize_host(host)
    domain = normalize_host(official_domain)
    return bool(host and domain and (host == domain or host.endswith("." + domain)))


def registrable_domain(host: str) -> str:
    host = normalize_host(host)
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    suffix2 = ".".join(parts[-2:])
    if suffix2 in COMMON_MULTI_LABEL_SUFFIXES and len(parts) >= 3:
        return ".".join(parts[-3:])
    return suffix2


def normalize_url(raw_url: str) -> dict | None:
    raw = str(raw_url or "").strip().replace("\\/", "/")
    if not raw:
        return None
    if not re.match(r"^https?://", raw, re.IGNORECASE):
        return None
    try:
        parsed = urlsplit(raw)
        host = normalize_host(raw)
        if not host:
            return None
        port = parsed.port
        netloc = host
        if port and not ((parsed.scheme.lower() == "http" and port == 80) or (parsed.scheme.lower() == "https" and port == 443)):
            netloc += f":{port}"
        removed: list[str] = []
        kept: list[tuple[str, str]] = []
        for key, value in parse_qsl(parsed.query, keep_blank_values=True):
            low = key.casefold()
            if low.startswith("utm_") or low in TRACKING_QUERY_KEYS:
                removed.append(key)
            else:
                kept.append((key, value))
        kept.sort(key=lambda pair: (pair[0], pair[1]))
        path = parsed.path or "/"
        if path != "/":
            path = path.rstrip("/") or "/"
        canonical = urlunsplit((parsed.scheme.lower(), netloc, path, urlencode(kept), ""))
        return {
            "canonical_url": canonical,
            "host": host,
            "registrable_domain": registrable_domain(host),
            "removed_query_params": sorted(removed),
        }
    except (ValueError, UnicodeError):
        return None


def extract_urls(text: str) -> list[str]:
    urls = re.findall(r"https?://[^\s)\]>\"']+", str(text or ""), flags=re.IGNORECASE)
    return [url.rstrip(".,;:") for url in urls]


def stable_id(prefix: str, value) -> str:
    return f"{prefix}-{sha256_obj(value).split(':', 1)[1][:16]}"


def get_path(value, dotted: str):
    current = value
    for part in dotted.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            raise KeyError(dotted)
    return current


def format_display(value) -> str:
    if isinstance(value, dict) and "display" in value:
        return str(value["display"])
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "是" if value else "否"
    return str(value)

