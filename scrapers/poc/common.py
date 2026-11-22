"""Shared helpers for PoC collectors: RawDocument envelope (D2), run logging, saved login sessions.

Collector interface: collect(query: str, notes: dict) -> Iterable[RawDocument]."""
import json
import os
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

POC_DIR = Path(__file__).resolve().parent
RESULTS = POC_DIR / "results"
SESSIONS = POC_DIR.parents[1] / ".secrets"  # Playwright storage_state per platform, gitignored
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:144.0) Gecko/20100101 Firefox/144.0",
]

try:
    from dotenv import load_dotenv

    load_dotenv(POC_DIR.parents[1] / ".env")
except ImportError:
    pass


def ua() -> str:
    return random.choice(USER_AGENTS)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def url_key(url: str) -> str:
    p = urlsplit(url.strip())
    return urlunsplit((p.scheme.lower(), p.netloc.lower().removeprefix("www."), p.path.rstrip("/"), p.query, ""))


DEFAULT_SECTION = {"ad": "ad_body", "post": "post", "video": "description", "image": "post", "profile": "description"}


def sections_of(text, content_type, title=None):
    out = [{"type": "title", "text": title}] if title and not (text or "").startswith(title) else []
    if text:
        out.append({"type": DEFAULT_SECTION.get(content_type, "post"), "text": text})
    return out


CORE = ["source", "source_url", "author", "published_at", "fetched_at", "query_keywords", "content_keywords", "text"]


def missing_core(doc: dict) -> list[str]:
    """Core fields absent, or `text` not a list of {type, text} sections (D12, D14)."""
    miss = [k for k in CORE if k not in doc]
    t = doc.get("text")
    if not isinstance(t, list) or not all(isinstance(s, dict) and "type" in s and "text" in s for s in t):
        miss.append("text:sections")
    return miss


def plain_text(doc: dict) -> str:
    return "\n\n".join(s["text"] for s in doc.get("text") or [] if s.get("text"))


# Polish markers compared without diacritics, because OCR often drops them ("DOLACZ", "srodki").
PL_WORDS = {"i", "w", "z", "na", "dla", "bez", "sie", "jest", "nie", "oraz", "twoje", "twoich", "swoim", "konto",
            "zl", "dolacz", "srodki", "pieniadze", "inwestuj", "inwestujesz", "inwestowanie", "inwestycje",
            "prowizji", "oplat", "ryzyko", "rachunek", "rachunkow", "zarabiaj", "kup", "akcje", "kupuj", "otworz",
            "nota", "prawna", "wiecej", "informacji", "pomysl", "okazje", "zlecen", "rejestr", "inwestowaniu"}
PL_LETTERS = re.compile("[ąęłśźżćń]")  # absent from Czech and Slovak; strong Polish signal on its own


def pl_score(text: str) -> int:
    import unicodedata
    low = text.lower()
    plain = unicodedata.normalize("NFKD", low.replace("ł", "l"))
    plain = "".join(c for c in plain if not unicodedata.combining(c))
    return sum(1 for w in re.findall(r"[a-z]+", plain) if w in PL_WORDS) + (2 if PL_LETTERS.search(low) else 0)


def envelope(*, url, source, collector, content_type, text=None, sections=None, query_keywords=None,
             published_at=None, title=None, links=None, author=None, sponsor=None, source_meta=None) -> dict:
    """Record core (D12-D15): source, source_url, author, published_at, fetched_at, query_keywords,
    content_keywords (filled by preprocessing), text = list of sections {type, text[, start, end]}; rest optional.
    Collectors pass either sections=[...] or a plain text string (wrapped into one default-typed section)."""
    meta = source_meta or {}
    if sections is None:
        sections = sections_of(text, content_type, title)
    sections = [s for s in sections if s.get("text")]
    if query_keywords is None:
        q = meta.get("query") or meta.get("via")
        query_keywords = [q] if q else []
    return {
        "schema_version": "rawdocument.v1-poc",
        "source": source,
        "source_url": url,
        "author": author,
        "published_at": published_at,
        "fetched_at": now(),
        "query_keywords": query_keywords,
        "content_keywords": [],
        "text": sections,
        "url_key": url_key(url),
        "collector": collector,
        "content_type": content_type,
        "lang": None,
        "title": title,
        "links": links or [],
        "sponsor": sponsor,
        "source_meta": meta,
    }


def session_file(platform: str) -> Path:
    p = SESSIONS / f"{platform}_state.json"
    if not p.exists():
        raise RuntimeError(f"no saved session {p}; run: python -m login {platform}")
    return p


def env(name: str) -> str | None:
    return os.environ.get(name) or None


def run(name: str, collect, query: str):
    """Run collect(query, notes) -> Iterable[RawDocument]; store docs and a run summary in results/<name>/."""
    out = RESULTS / name
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    docs, notes, error = [], {}, None
    try:
        for d in collect(query, notes):
            docs.append(d)
    except Exception as e:  # PoC: record failure instead of crashing
        error = f"{type(e).__name__}: {e}"[:800]
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    summary = {
        "collector": name,
        "query": query,
        "run_at": now(),
        "seconds": round(time.perf_counter() - t0, 1),
        "records": len(docs),
        "error": error,
        "notes": notes,
        "sample": docs[0] if docs else None,
        "missing_core": sum(1 for d in docs if missing_core(d)),
    }
    (out / f"{stamp}-docs.json").write_text(json.dumps(docs, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / f"{stamp}-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("collector", "query", "seconds", "records", "missing_core", "error", "notes")},
                     ensure_ascii=False)[:1500])
    return summary
