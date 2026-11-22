from .common import build, media, split_title, to_text


def to_record(raw: dict) -> dict:
    text = to_text(raw, lambda r: split_title(r.get("text"), None, "ad_body"))
    # video ads have no still creative in the Ad Library card, only the player poster
    source = "thumbnail" if (raw.get("source_meta") or {}).get("image_source") == "thumbnail" else "creative"
    return build(raw, text, *media(raw, text, source))
