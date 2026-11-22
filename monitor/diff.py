"""PageChange from two PageSnapshots (contract: contracts/app_api.md)."""
import difflib
import hashlib

from monitor.extract import STYLE_FIELDS

MAX_LINES = 50


def change_id(page_id, to_snapshot):
    return "chg_" + hashlib.sha1(f"{page_id}|{to_snapshot}".encode()).hexdigest()[:12]


def measured(a, b):
    """Legibility measurements of the matched block, only when they differ (absent on snapshots without them)."""
    out = {}
    for name, field in (("contrast", "contrast_ratio"), ("rel_size", "rel_font_size")):
        if a.get(field) != b.get(field):
            out[name + "_before"], out[name + "_after"] = a.get(field), b.get(field)
    return out


def style_changes(prev, cur):
    """Blocks matched by normalized text (n-th occurrence to n-th occurrence) per viewport; viewports missing in prev are skipped."""
    out = []
    for vp, blocks in cur.items():
        fold = int(vp.split("x")[1])
        before = {}
        for b in prev.get(vp) or []:
            before.setdefault(b["text"], []).append(b)
        seen = {}
        for b in blocks:
            i = seen[b["text"]] = seen.get(b["text"], -1) + 1
            olds = before.get(b["text"]) or []
            if i >= len(olds):
                continue
            a = olds[i]
            for f in STYLE_FIELDS + ("above_fold",):
                va, vb = (a["y"] < fold, b["y"] < fold) if f == "above_fold" else (a[f], b[f])
                if va != vb:
                    out.append({"text": b["text"][:120], "viewport": vp, "field": f, "before": va, "after": vb, **measured(a, b)})
    return out


def compare(prev, cur, detected_at, mock=False):
    """Return PageChange dict or None when text_sha256 is equal and style_sha256 is equal or unknown (no blocks)."""
    styled = bool(prev.get("style_sha256") and cur.get("style_sha256"))
    if prev["text_sha256"] == cur["text_sha256"] and (not styled or prev["style_sha256"] == cur["style_sha256"]):
        return None
    a, b = prev["text"].splitlines(), cur["text"].splitlines()
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    added, removed = [], []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op in ("replace", "delete"):
            removed += a[i1:i2]
        if op in ("replace", "insert"):
            added += b[j1:j2]
    styles = style_changes(prev["blocks"], cur["blocks"]) if styled else []
    return {"id": change_id(cur["page_id"], cur["id"]), "page_id": cur["page_id"], "entity_id": cur["entity_id"],
            "from_snapshot": prev["id"], "to_snapshot": cur["id"], "detected_at": detected_at,
            "summary": f"{len(added)} lines added, {len(removed)} removed, {len(styles)} style changes",
            "added_lines": added[:MAX_LINES], "removed_lines": removed[:MAX_LINES], "style_changes": styles[:MAX_LINES],
            "assessment": None, "mock": mock}
