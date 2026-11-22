import json
from pathlib import Path

from preprocessing import legibility

CORE_FIELDS = ("source", "source_url", "author", "published_at", "fetched_at", "query_keywords", "content_keywords", "text", "media")
OPTIONAL_FIELDS = ("sponsor", "links", "content_type", "source_meta")
LOCAL_PATH_KEYS = ("image_refs",)
MEDIA_INDEX = Path(__file__).resolve().parents[1] / "data" / "media" / "index.json"
_media_index = None


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


def media_index():
    """data/media/index.json (scripts/build_media.py): image file name -> thumbnail + legibility measurements."""
    global _media_index
    if _media_index is None:
        _media_index = json.loads(MEDIA_INDEX.read_text(encoding="utf-8")) if MEDIA_INDEX.exists() else {}
    return _media_index


def media(raw, text, source="creative"):
    """source_meta.image_refs (local paths, matched by file name) -> ([MediaRef], source_meta additions).

    Additions come from the first OCR'd image: `ocr_lines` (per line), `legibility` (counts) and `legibility_check`
    (fixed thresholds). A disclosure repeated in the record text sections makes the material marked anyway (R02).
    """
    idx, refs, first = media_index(), [], None
    for ref in (raw.get("source_meta") or {}).get("image_refs") or []:
        entry = idx.get(ref.replace("\\", "/").rsplit("/", 1)[-1])
        if not entry:
            continue
        refs.append({"type": "image", "key": entry["key"], "width": entry["width"], "height": entry["height"],
                     "ocr": bool(entry["ocr_lines"]), "source": source})
        if first is None and entry["ocr_lines"]:
            first = entry
    if not refs:
        return [], {}
    in_text = any(legibility.is_disclosure(v) for k, v in text.items() if k != "ocr")
    lines = first["ocr_lines"] if first else []
    scale = legibility.IMAGE_WIDTH_PX / first["image_width"] if first else 1
    disclosures = [{"text": l["text"], "contrast_ratio": l["contrast_ratio"], "rel_font_size": l["rel_font_size"],
                    "font_px": round(l["box_height_px"] * scale, 1)} for l in lines if l["is_disclosure"]]
    return refs, {
        "ocr_lines": lines,
        "legibility": {"disclosure_in_text": in_text, "disclosure_on_image": bool(disclosures),
                       "image_width": first["image_width"] if first else None,
                       "image_height": first["image_height"] if first else None,
                       "dominant_line_px": first["dominant_line_px"] if first else None,
                       "lines": len(lines), "disclosure_lines": len(disclosures)},
        "legibility_check": legibility.check(disclosures, in_text=in_text),
    }


def build(raw, text, media_refs=(), meta_extra=None):
    meta = {k: v for k, v in (raw.get("source_meta") or {}).items() if k not in LOCAL_PATH_KEYS}
    if raw.get("collector"):
        meta["collector"] = raw["collector"]
    meta.update(meta_extra or {})
    return {
        "source": raw.get("source"),
        "source_url": raw.get("source_url") or raw.get("url"),
        "author": raw.get("author"),
        "published_at": raw.get("published_at") or None,
        "fetched_at": raw.get("fetched_at") or None,
        "query_keywords": query_keywords(raw),
        "content_keywords": list(raw.get("content_keywords") or []),
        "text": text,
        "media": list(media_refs),
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
    if not isinstance(rec.get("media"), list):
        errors.append("media not list")
    return errors
