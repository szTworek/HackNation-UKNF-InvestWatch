from .common import build, split_title, to_text


def to_record(raw: dict) -> dict:
    return build(raw, to_text(raw, lambda r: split_title(r.get("text"), r.get("title"), "page")))
