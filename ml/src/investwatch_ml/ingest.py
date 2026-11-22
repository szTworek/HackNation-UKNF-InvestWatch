"""Adapter scraper -> ai-service: rekord kolektora (docs/DECYZJE.md, D12-D15) na `Item` dla /analyze.

Import całego eksportu bez uruchamiania serwera:
  uv run python -m investwatch_ml.ingest --export ../data/export --out data/findings.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from langdetect import DetectorFactory, detect_langs

from .text import normalize

DetectorFactory.seed = 0

PLATFORMS = {
    "meta_ad_library": "facebook", "facebook": "facebook", "instagram": "instagram", "tiktok": "tiktok",
    "youtube": "youtube", "x": "x", "google_ads_transparency": "web", "microsoft_ad_library": "web", "web": "web",
}
BODY_SECTIONS = ("post", "ad_body", "description", "link_description", "cta", "transcript", "ocr")
# adresy kreacji i miniatur, nie strony docelowe
MEDIA_HOSTS = ("googlesyndication.com", "googleusercontent.com", "fbcdn.net", "ytimg.com", "tiktokcdn.com", "gstatic.com")
MIN_WORDS = 3


def _sections(record: dict[str, Any]) -> dict[str, str]:
    raw = record.get("text")
    if isinstance(raw, str):
        raw = {"post": raw}
    if not isinstance(raw, dict):
        return {}
    return {k: t for k, v in raw.items() if isinstance(v, str) and (t := normalize(v))}


def _links(values: Iterable[Any]) -> list[str]:
    out: list[str] = []
    for value in values or []:
        if not isinstance(value, str) or not value.strip():
            continue
        url = value.strip() if "://" in value else f"https://{value.strip()}"
        host = (urlsplit(url).hostname or "").lower()
        if host and "." in host and not host.endswith(MEDIA_HOSTS) and url not in out:
            out.append(url)
    return out


def _is_polish(text: str, meta: dict[str, Any]) -> bool:
    if meta.get("lang_hint_pl") is True or str(meta.get("default_audio_language", "")).startswith("pl"):
        return True
    try:
        return next((x.prob for x in detect_langs(text[:3000]) if x.lang == "pl"), 0.0) >= 0.7
    except Exception:
        return False


def to_item(record: dict[str, Any]) -> dict[str, Any] | None:
    """Zwraca `Item` albo None, gdy rekord nie ma adresu lub treści do analizy."""
    url = record.get("source_url") or record.get("url")
    source = record.get("source")
    sections = _sections(record)
    title = sections.get("title")
    body = "\n\n".join(sections[k] for k in BODY_SECTIONS if k in sections)
    if not body:
        body = "\n\n".join(v for k, v in sections.items() if k != "title")
    words = re.findall(r"\w+", f"{title or ''} {body}")
    if not url or not source or len(words) < MIN_WORDS:
        return None
    meta = record.get("source_meta") if isinstance(record.get("source_meta"), dict) else {}
    author = record.get("author") if isinstance(record.get("author"), str) else None
    sponsor = record.get("sponsor") if isinstance(record.get("sponsor"), str) else None
    full = f"{title}\n\n{body}" if title and body else (title or body)
    return {
        "id": "scr-" + hashlib.sha256(f"{source}|{url}|{full}".encode()).hexdigest()[:20],
        "platform": PLATFORMS.get(source, "other"),
        "kind": "transcript" if "transcript" in sections else "post",
        "url": url,
        "title": title,
        "text": body,
        "outboundLinks": _links(record.get("links") or []),
        "author": {"handle": author or sponsor or "nieznany", "displayName": author or sponsor},
        "publisher": sponsor or author,
        "isSponsored": record.get("content_type") == "ad" or meta.get("has_paid_product_placement") is True,
        "isPolish": _is_polish(full, meta),
        "hashtags": sorted(set(re.findall(r"#\w+", full))),
        "publishedAt": record.get("published_at"),
        "fetchedAt": record.get("fetched_at"),
        "source": source,
        "queryKeywords": record.get("query_keywords") or [],
    }


def to_items(records: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], Counter]:
    """Adaptuje rekordy, usuwa duplikaty treści i zlicza odrzucone."""
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    stats: Counter = Counter()
    for record in records:
        stats["received"] += 1
        item = to_item(record)
        if item is None:
            stats["rejected"] += 1
        elif item["id"] in seen:
            stats["duplicates"] += 1
        else:
            seen.add(item["id"])
            items.append(item)
            stats["accepted"] += 1
    return items, stats


def read_export(export: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(export.glob("*/records.jsonl")):  # bez zagnieżdżonych kopii paczek próbek
        with path.open(encoding="utf-8") as f:
            rows += [json.loads(line) for line in f if line.strip()]
    return rows


def main() -> None:
    from .api import Item, _analyze

    ap = argparse.ArgumentParser()
    ap.add_argument("--export", type=Path, default=Path("../data/export"))
    ap.add_argument("--out", type=Path, default=Path("data/findings.jsonl"))
    args = ap.parse_args()
    items, stats = to_items(read_export(args.export))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    modules: Counter = Counter()
    with args.out.open("w", encoding="utf-8") as f:
        for item in items:
            analysis = _analyze(Item(**item))
            modules.update(analysis["modules"] or ["none"])
            f.write(json.dumps({"item": item, "analysis": analysis}, ensure_ascii=False) + "\n")
    print(json.dumps({"stats": stats, "modules": {str(k): v for k, v in modules.items()}, "out": str(args.out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
