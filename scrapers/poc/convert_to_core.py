"""Convert JSON/JSONL records from older envelopes (url + string text, or text + sections) to the D12-D15 core
in place, no refetch: source_url, query_keywords, content_keywords, text = list of sections.
Usage: python convert_to_core.py <file.jsonl|file.json> ..."""
import json
import sys
from pathlib import Path

from common import CORE, missing_core

SECTION = {"ad": "ad_body", "post": "post", "video": "description", "image": "post", "profile": "description"}


def convert(d):
    if isinstance(d.get("text"), list):
        return d
    meta = d.get("source_meta") or {}
    if "sections" in d:
        sections = d.pop("sections")
    else:
        stype = "ocr" if meta.get("text_source") == "ocr" else SECTION.get(d.get("content_type"), "post")
        sections = ([{"type": "title", "text": d["title"]}] if d.get("title") else []) + \
                   ([{"type": stype, "text": d["text"]}] if d.get("text") else [])
    q = meta.get("query") or meta.get("via") or meta.get("domain")
    core = {"source": d["source"], "source_url": d.pop("url", None) or d.get("source_url"), "author": d.get("author"),
            "published_at": d.get("published_at"), "fetched_at": d.get("fetched_at"),
            "query_keywords": d.get("query_keywords") or ([q] if q else []),
            "content_keywords": d.get("content_keywords") or [], "text": sections}
    return {"schema_version": d.get("schema_version")} | core | {k: v for k, v in d.items() if k not in core}


def main(paths):
    for p in map(Path, paths):
        raw = p.read_text(encoding="utf-8")
        if p.suffix == ".jsonl":
            docs = [convert(json.loads(l)) for l in raw.splitlines() if l.strip()]
            p.write_text("".join(json.dumps(d, ensure_ascii=False) + "\n" for d in docs), encoding="utf-8")
        else:
            docs = [convert(d) for d in json.loads(raw)]
            p.write_text(json.dumps(docs, ensure_ascii=False, indent=1), encoding="utf-8")
        print(p, len(docs), "records, missing core:", sum(1 for d in docs if missing_core(d)), "core:", CORE)


if __name__ == "__main__":
    main(sys.argv[1:])
