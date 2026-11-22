"""Import eksportu scrapera (records.jsonl, repo HackNation-UKNF-InvestWatch) do puli: data/pool/scraper.jsonl.

Zostają tylko polskie teksty, bez duplikatów treści i bez filmów, które już są w puli YouTube.
Wznawialne: uruchom ponownie po nowym eksporcie, labelery z --follow same podejmą nowe dokumenty.

  uv run python scripts/ingest_scraper.py
  uv run python scripts/ingest_scraper.py --export ../../HackNation-UKNF-InvestWatch/data/export --dry-run
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from collections import Counter
from pathlib import Path

from langdetect import DetectorFactory, detect_langs

from investwatch_ml.schema import Doc, append_jsonl, existing_ids, read_jsonl
from investwatch_ml.text import normalize

ML_DIR = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
DetectorFactory.seed = 0
DEFAULT_EXPORT = ML_DIR.parents[1] / "HackNation-UKNF-InvestWatch" / "data" / "export"
PLATFORMS = {"meta_ad_library": "facebook", "google_ads_transparency": "web", "microsoft_ad_library": "web",
             "tiktok": "tiktok", "youtube": "youtube"}
BODY_SECTIONS = ("ad_body", "post", "description", "link_description", "cta", "transcript", "ocr")
MIN_WORDS = 5


def p_polish(text: str) -> float:
    try:
        return next((x.prob for x in detect_langs(text[:3000]) if x.lang == "pl"), 0.0)
    except Exception:
        return 0.0


def fingerprint(text: str) -> str:
    return hashlib.sha1(" ".join(re.findall(r"\w+", text.lower())).encode("utf-8")).hexdigest()


def to_doc(r: dict) -> Doc | None:
    sections = r.get("text") if isinstance(r.get("text"), dict) else {"post": str(r.get("text") or "")}
    title = normalize(sections.get("title") or "") or None
    body = "\n\n".join(normalize(sections[k]) for k in BODY_SECTIONS if sections.get(k))
    if not body and not title:
        return None
    src, url = r.get("source") or "unknown", r.get("source_url") or ""
    meta = r.get("source_meta") or {}
    doc_id = f"yt:{meta['video_id']}" if src == "youtube" and meta.get("video_id") else \
        f"scr:{src}:{hashlib.sha1(f'{url}|{body}'.encode('utf-8')).hexdigest()[:16]}"
    return Doc(id=doc_id, source="scraper", platform=PLATFORMS.get(src, "other"),
               kind="transcript" if sections.get("transcript") else "post", url=url or None, author=r.get("author"),
               title=title, text=body or title, published_at=r.get("published_at"),
               outbound_links=list(r.get("links") or []),
               meta={"scraper_source": src, "sponsor": r.get("sponsor"), "is_paid_ad": r.get("content_type") == "ad",
                     "sections": sorted(sections), "has_ocr": bool(sections.get("ocr")),
                     "query_keywords": r.get("query_keywords") or [], "fetched_at": r.get("fetched_at")})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", type=Path, default=DEFAULT_EXPORT)
    ap.add_argument("--min-polish", type=float, default=0.7)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    pool = ML_DIR / "data/pool"
    out = pool / "scraper.jsonl"
    known = existing_ids(out) | existing_ids(pool / "youtube.jsonl")
    seen_text = {fingerprint(Doc(**x).full_text()) for x in read_jsonl(out)}
    stats: Counter = Counter()
    kept: list[dict] = []
    for f in sorted(args.export.glob("*/records.jsonl")):  # bez zagnieżdżonych kopii paczek próbek
        for r in read_jsonl(f):
            src = r.get("source") or f.parent.name
            stats[f"{src}|wczytane"] += 1
            doc = to_doc(r)
            if doc is None or len(re.findall(r"\w+", doc.full_text())) < MIN_WORDS:
                stats[f"{src}|za krótkie"] += 1
            elif doc.id in known:
                stats[f"{src}|już w puli"] += 1
            elif p_polish(doc.full_text()) < args.min_polish:
                stats[f"{src}|nie po polsku"] += 1
            elif (fp := fingerprint(doc.full_text())) in seen_text:
                stats[f"{src}|duplikat"] += 1
            else:
                seen_text.add(fp)
                known.add(doc.id)
                kept.append(doc.model_dump())
                stats[f"{src}|dodane"] += 1
    for k in sorted(stats):
        print(f"{k}: {stats[k]}")
    if args.dry_run:
        print(f"dry-run: dodałbym {len(kept)}")
        for d in kept[:6]:
            print(" -", d["meta"]["scraper_source"], "|", d["author"], "|", d["text"][:110].replace("\n", " "))
        return
    append_jsonl(out, kept)
    print(f"dodano {len(kept)} -> {out}")


if __name__ == "__main__":
    main()
