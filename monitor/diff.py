"""PageChange from two PageSnapshots (contract: contracts/app_api.md)."""
import difflib
import hashlib

MAX_LINES = 50


def change_id(page_id, to_snapshot):
    return "chg_" + hashlib.sha1(f"{page_id}|{to_snapshot}".encode()).hexdigest()[:12]


def _short(t, n=80):
    return t if len(t) <= n else t[: n - 1] + "…"


def compare(prev, cur, detected_at, mock=False):
    """Return PageChange dict or None when text_sha256 is equal."""
    if prev["text_sha256"] == cur["text_sha256"]:
        return None
    a, b = prev["text"].splitlines(), cur["text"].splitlines()
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    added, removed = [], []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op in ("replace", "delete"):
            removed += a[i1:i2]
        if op in ("replace", "insert"):
            added += b[j1:j2]
    rp, rc = prev["risk_warning"], cur["risk_warning"]
    kinds, parts = [], []
    removed_page = not cur["text"] and cur.get("http_status") in (404, 410)
    if removed_page:
        kinds.append("page_removed")
        parts.append(f"Page removed (HTTP {cur.get('http_status')})")
    else:
        kinds.append("text")
    if rp["present"] and not rc["present"] and not removed_page:
        kinds.append("risk_warning_removed")
        parts.append("Risk warning removed")
    elif rc["present"] and not rp["present"]:
        kinds.append("risk_warning_changed")
        parts.append("Risk warning added")
    elif rp["present"] and rc["present"] and (rp["text"] != rc["text"] or rp["cfd_loss_pct"] != rc["cfd_loss_pct"]):
        kinds.append("risk_warning_changed")
        if rp["cfd_loss_pct"] != rc["cfd_loss_pct"]:
            parts.append(f"CFD loss percentage {rp['cfd_loss_pct']}% -> {rc['cfd_loss_pct']}%")
        if rp["text"] != rc["text"]:
            la, lb = len(rp["text"] or ""), len(rc["text"] or "")
            verb = "shortened" if lb < la * 0.8 else "extended" if lb > la * 1.2 else "changed"
            parts.append(f"Risk warning text {verb} ({la} -> {lb} chars)")
    if rp.get("above_fold") is True and rc.get("above_fold") is False:
        parts.append("Risk warning moved below the fold")
    if not removed_page:
        txt = f"{len(added)} lines added, {len(removed)} removed"
        if added and len(parts) == 0:
            txt += f": \"{_short(added[0])}\""
        parts.append(txt)
    return {"id": change_id(cur["page_id"], cur["id"]), "page_id": cur["page_id"], "entity_id": cur["entity_id"],
            "from_snapshot": prev["id"], "to_snapshot": cur["id"], "detected_at": detected_at,
            "kinds": kinds, "summary": "; ".join(parts),
            "added_lines": added[:MAX_LINES], "removed_lines": removed[:MAX_LINES], "mock": mock}
