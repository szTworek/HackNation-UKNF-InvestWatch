from .common import build, media, split_title, to_text


def _from_string(raw):
    key = "ocr" if (raw.get("source_meta") or {}).get("text_source") == "ocr" else "ad_body"
    return split_title(raw.get("text"), raw.get("title"), key)


def to_record(raw: dict) -> dict:
    text = to_text(raw, _from_string)
    return build(raw, text, *media(raw, text, "creative"))
