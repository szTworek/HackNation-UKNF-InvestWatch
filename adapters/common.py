CORE_FIELDS = ("source", "source_url", "author", "published_at", "fetched_at", "query_keywords", "content_keywords", "text")
OPTIONAL_FIELDS = ("sponsor", "links", "content_type", "source_meta")
LOCAL_PATH_KEYS = ("image_refs",)


def merge_sections(sections):
    """[{type, text, start?, end?}] -> {type: text}; same-type sections joined in order."""
    parts = {}
    for s in sections or []:
        if not isinstance(s, dict):
            continue
        t = (s.get("text") or "").strip()
        if t:
            parts.setdefault(s.get("type") or "text", []).append(t)
    return {k: ("\n" if k != "transcript" else " ").join(v) for k, v in parts.items()}


def split_title(raw_text, title, body_key):
    """Old string shape: 'title\\nbody' or plain body -> {title?, body_key?}."""
    text = (raw_text or "").strip()
    title = (title or "").strip()
    out = {}
    if title:
        out["title"] = title
        if text.startswith(title):
            text = text[len(title):].strip()
    if text and text != title:
        out[body_key] = text
    return out


def to_text(raw, string_to_text):
    """Handles all three historical shapes of raw['text']."""
    t = raw.get("text")
    if isinstance(t, dict):
        return {k: v.strip() for k, v in t.items() if isinstance(v, str) and v.strip()}
    if isinstance(t, list):
        return merge_sections(t)
    if raw.get("sections"):
        return merge_sections(raw["sections"])
    return string_to_text(raw)


def query_keywords(raw):
    q = raw.get("query_keywords")
    if q:
        return list(q)
    meta = raw.get("source_meta") or {}
    q = meta.get("query") or meta.get("domain")
    return [q] if q else []


def build(raw, text):
    meta = {k: v for k, v in (raw.get("source_meta") or {}).items() if k not in LOCAL_PATH_KEYS}
    if raw.get("collector"):
        meta["collector"] = raw["collector"]
    return {
        "source": raw.get("source"),
        "source_url": raw.get("source_url") or raw.get("url"),
        "author": raw.get("author"),
        "published_at": raw.get("published_at") or None,
        "fetched_at": raw.get("fetched_at") or None,
        "query_keywords": query_keywords(raw),
        "content_keywords": list(raw.get("content_keywords") or []),
        "text": text,
        "sponsor": raw.get("sponsor"),
        "links": list(raw.get("links") or []),
        "content_type": raw.get("content_type"),
        "source_meta": meta,
    }


def validate(rec):
    """Returns list of problems; empty list = valid core."""
    errors = [f"missing {f}" for f in CORE_FIELDS if f not in rec]
    if "sections" in rec:
        errors.append("has sections")
    if not rec.get("source") or not rec.get("source_url"):
        errors.append("empty source/source_url")
    if not isinstance(rec.get("query_keywords"), list) or not isinstance(rec.get("content_keywords"), list):
        errors.append("keywords not list")
    t = rec.get("text")
    if not isinstance(t, dict) or not t or not all(isinstance(v, str) and v.strip() for v in t.values()):
        errors.append("text not non-empty {str: str}")
    return errors
