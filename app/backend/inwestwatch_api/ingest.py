"""Read collector files (D12–D15 records, firm websites, monitor output) into normalized dicts."""
import hashlib
import json
import re
from datetime import datetime, timezone

from .config import EXPORT_DIR, MONITOR_DIR, SAMPLES_DIR

PLATFORM = {
    "google_ads_transparency": "google_ads", "meta_ad_library": "meta_ads", "microsoft_ad_library": "bing_ads",
    "youtube": "youtube", "tiktok": "tiktok", "firm_website": "website",
}
CHANNEL = {"google_ads": "ad", "meta_ads": "ad", "bing_ads": "ad", "youtube": "social", "tiktok": "social", "website": "website"}
LOSS_PCT = re.compile(r"(\d{2})(?:,\d+)?\s?%\s*(?:rachunk|of\s+retail|retail|inwestor|klient)", re.I)


def iso(ts):
    if not ts:
        return None
    try:
        d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def item_id(url):
    return "itm_" + hashlib.sha1(url.encode()).hexdigest()[:12]


def _jsonl(path):
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def _text(raw):
    if isinstance(raw, dict):
        return {k: v for k, v in raw.items() if isinstance(v, str) and v.strip()}
    out = {}
    for part in raw or []:
        t, s = part.get("type"), part.get("text")
        if t and isinstance(s, str) and s.strip():
            out[t] = (out[t] + "\n" + s) if t in out else s
    return out


def _risk_warning(rec):
    rw_text = (rec.get("text") or {}).get("risk_disclaimer") if isinstance(rec.get("text"), dict) else None
    vp = ((rec.get("source_meta") or {}).get("risk_by_viewport") or {}).get("375") or {}
    disc = vp.get("disclaimer") or {}
    m = LOSS_PCT.search(rw_text or "")
    return {"present": bool(rw_text), "cfd_loss_pct": int(m.group(1)) if m else None,
            "text": rw_text, "above_fold": disc.get("above_fold") if disc else None}


def normalize(rec):
    platform = PLATFORM.get(rec.get("source"))
    if not platform or not rec.get("source_url"):
        return None
    text = _text(rec.get("text"))
    if not text and rec.get("title"):
        text = {"title": rec["title"]}
    if not text:
        return None
    if platform == "website" and rec.get("title"):
        text = {"title": rec["title"], **text}
    sm = dict(rec.get("source_meta") or {})
    if platform == "website":
        sm = {"risk_warning": _risk_warning(rec), "html_lang": sm.get("html_lang")}
    return {
        "id": item_id(rec["source_url"]), "channel": CHANNEL[platform], "platform": platform,
        "source_url": rec["source_url"], "author": rec.get("author"), "sponsor": rec.get("sponsor"),
        "links": rec.get("links") or [], "published_at": iso(rec.get("published_at")),
        "fetched_at": iso(rec.get("fetched_at")), "query_keywords": rec.get("query_keywords") or [],
        "text": text, "media": rec.get("media") or [], "source_meta": sm, "mock": False,
    }


def load_records():
    """Export files first (normalized D12–D15), then entity samples for records not exported (deduped by source_url)."""
    files = sorted(EXPORT_DIR.glob("*/records.jsonl")) + sorted(SAMPLES_DIR.glob("*_entities_v1.jsonl")) + [SAMPLES_DIR / "firm_web_v1.jsonl"]
    seen, out = set(), []
    for f in files:
        for rec in _jsonl(f):
            n = normalize(rec)
            if n and n["source_url"] not in seen:
                seen.add(n["source_url"])
                out.append(n)
    return out


def firm_pages(entity_of_url):
    """Pages + one real snapshot each, from data/samples/firm_web_v1.jsonl (used until the monitor writes its own)."""
    pages, snaps = [], []
    for rec in _jsonl(SAMPLES_DIR / "firm_web_v1.jsonl"):
        url = rec["source_url"]
        eid = entity_of_url(url)
        if not eid:
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", url.split("//", 1)[-1].lower()).strip("-")
        page_id = f"{eid}-{slug}"[:120]
        text = (rec.get("text") or {}).get("page") or ""
        pages.append({"page_id": page_id, "entity_id": eid, "url": url, "label": rec.get("title"), "mock": False})
        snaps.append({"id": "snp_" + hashlib.sha1(f"{page_id}|{rec.get('fetched_at')}".encode()).hexdigest()[:12],
                      "page_id": page_id, "entity_id": eid, "url": url, "fetched_at": iso(rec.get("fetched_at")),
                      "text_sha256": hashlib.sha256(text.encode()).hexdigest(), "text": text,
                      "risk_warning": _risk_warning(rec), "mock": False})
    return pages, snaps


def monitor_files():
    """(pages, snapshots, changes) from data/monitor/*; empty lists when the monitor has not run yet."""
    pages = []
    p = MONITOR_DIR / "pages.json"
    if p.exists():
        try:
            pages = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pages = []
    snaps = _jsonl(MONITOR_DIR / "snapshots.jsonl")
    changes = _jsonl(MONITOR_DIR / "changes.jsonl")
    for s in snaps:
        s["fetched_at"] = iso(s.get("fetched_at"))
    for c in changes:
        c["detected_at"] = iso(c.get("detected_at"))
    return pages, snaps, changes
