"""Text normalization (stable diffs) and risk-warning extraction. Regexes are JS-compatible (used in the browser too)."""
import hashlib
import re

L = "[a-ząćęłńóśźż]*"
WARNING_RE = re.compile(
    rf"rachunk{L} inwestor{L} detaliczn|trac{L} pieni|retail investor accounts lose|lose money"
    rf"|kontrakty cfd s[aą] z[lł]o[zż]on|cfds are complex|kapita[lł] jest zagro[zż]on|capital (?:is )?at risk"
    rf"|inwestowanie wi[aą][zż]e si[eę] z ryzykiem|warto[sś][cć] (?:twoich |twojej )?inwestycj{L} mo[zż]e",
    re.I)
LOSS_PCT_RE = re.compile(r"(\d{1,2}(?:[.,]\d{1,2})?)\s?%\s*(?:of\s+)?(?:rachunk|retail|inwestor)", re.I)
COOKIE_RE = re.compile(r"cookie|ciasteczk", re.I)
DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?\b|\b\d{1,2}[./]\d{1,2}[./]\d{2,4}\b"
                     r"|\b\d{1,2}:\d{2}(?::\d{2})?\b|\b\d+\s+(?:sek\w*|min\w*|godz\w*|dni|seconds?|minutes?|hours?)\s+(?:temu|ago)\b", re.I)
# Quotes / prices / daily moves: signed or decimal numbers, optionally with % or currency.
QUOTE_RE = re.compile(r"[+\-−]?\d{1,3}(?:[  ]\d{3})*[.,]\d+\s?%?|[+\-−]\d+(?:[.,]\d+)?\s?%")


def normalize(lines):
    out, seen = [], set()
    for raw in lines:
        t = re.sub(r"\s+", " ", raw).strip()
        if len(t) < 2 or (COOKIE_RE.search(t) and not WARNING_RE.search(t)):
            continue
        t = DATE_RE.sub("<DATE>", t)
        if not WARNING_RE.search(t):
            t = QUOTE_RE.sub("<NUM>", t)
        if re.fullmatch(r"[<>NUMDATE\s%$€zł|/·-]*", t):
            continue
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _trim(block):
    if len(block) <= 600:
        return block
    sents = re.split(r"(?<=[.!?])\s+", block)
    keep = [s for s in sents if WARNING_RE.search(s) or LOSS_PCT_RE.search(s)]
    return " ".join(keep)[:600] or block[:600]


def loss_pct(text):
    m = LOSS_PCT_RE.search(text or "")
    if not m:
        return None
    v = float(m.group(1).replace(",", "."))
    return int(v) if v.is_integer() else v


def risk_warning(lines, warn_geo=None, vh=None):
    """lines: normalized page lines. warn_geo: [{text, top}] from the browser (None -> above_fold null)."""
    hits = [t for t in lines if WARNING_RE.search(t)]
    if not hits:
        return {"present": False, "cfd_loss_pct": None, "text": None, "above_fold": None if warn_geo is None else False}
    best = next((t for t in hits if loss_pct(t) is not None), hits[0])
    above = None
    if warn_geo is not None and vh:
        above = any(g["top"] < vh for g in warn_geo)
    return {"present": True, "cfd_loss_pct": loss_pct(best), "text": _trim(best), "above_fold": above}
