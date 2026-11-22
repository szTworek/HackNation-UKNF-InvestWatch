"""Text normalization (stable diffs), risk-warning extraction and legibility measurements of text blocks.
Regexes are JS-compatible (used in the browser too)."""
import hashlib
import io
import json
import re

import numpy as np
from PIL import Image

from preprocessing import legibility

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
RGB_RE = re.compile(r"rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\)")
STYLE_FIELDS = ("font_size_px", "font_weight", "color", "background_color", "opacity")
MAX_BLOCKS = 400
MAX_DISCLOSURE_BLOCKS = 20
MOBILE_MAX_WIDTH = 480
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


def hex_color(c):
    m = RGB_RE.match(c or "")
    if not m:
        return c
    *rgb, a = m.groups()
    out = "#" + "".join(f"{round(float(v)):02x}" for v in rgb)
    return out if a is None or float(a) >= 1 else out + f"{round(float(a) * 255):02x}"


def screenshot_pixels(png):
    return None if not png else np.asarray(Image.open(io.BytesIO(png)).convert("RGB"))


def block_contrast(b, pixels):
    """(ratio, source): CSS colours when the background is a solid colour, screenshot pixels when it is an image."""
    css = legibility.css_contrast(b["color"], b["background_color"], b["opacity"])
    if css is not None and not b.get("background_image"):
        return css, "css"
    if pixels is not None:
        patch = pixels[b["y"]:b["y"] + b["h"], b["x"]:b["x"] + b["w"]]
        sampled = legibility.patch_contrast(patch) if patch.size else None
        if sampled is not None:
            return sampled, "screenshot"
    return (css, "css") if css is not None else (None, None)


def style_blocks(raw, screenshot=None):
    """Browser blocks -> normalized text, px rounded, colours as hex, legibility measurements; capped at MAX_BLOCKS.

    screenshot: full-page PNG bytes, sampled when the background cannot be read from CSS (background image).
    """
    out = []
    for b in raw or []:
        t = normalize([b["text"]])
        if not t:
            continue
        out.append({**b, "text": t[0], "font_size_px": round(b["font_size_px"]), "color": hex_color(b["color"]),
                    "background_color": hex_color(b["background_color"]), "opacity": round(b["opacity"], 2)})
    out = out[:MAX_BLOCKS]
    dominant = dominant_font_px(out)
    pixels = screenshot_pixels(screenshot)
    for b in out:
        b["rel_font_size"] = legibility.rel_size(b["font_size_px"], dominant)
        b["contrast_ratio"], b["contrast_source"] = block_contrast(b, pixels)
        b["is_disclosure"] = legibility.is_disclosure(b["text"])
    return out


def dominant_font_px(blocks):
    """Prevailing font size of the page: block font size, weighted by how much text is set in it."""
    return legibility.dominant([b["font_size_px"] for b in blocks], [len(b["text"]) for b in blocks])


def page_legibility(blocks):
    """blocks: {viewport: [block]} -> ({viewport: {dominant_font_px, disclosure_blocks}}, legibility_check)."""
    per_vp, checks = {}, []
    for vp, bl in (blocks or {}).items():
        w, h = (int(x) for x in vp.split("x"))
        rows = [{"text": b["text"][:200], "font_size_px": b["font_size_px"], "rel_font_size": b["rel_font_size"],
                 "contrast_ratio": b["contrast_ratio"], "contrast_source": b["contrast_source"],
                 "y": b["y"], "above_fold": b["y"] < h} for b in bl if b.get("is_disclosure")][:MAX_DISCLOSURE_BLOCKS]
        per_vp[vp] = {"dominant_font_px": dominant_font_px(bl), "disclosure_blocks": rows}
        min_px = legibility.MIN_FONT_PX_MOBILE if w <= MOBILE_MAX_WIDTH else legibility.MIN_FONT_PX_DESKTOP
        checks.append(legibility.check([{**r, "font_px": r["font_size_px"]} for r in rows], min_px))
    status = ("problem" if any(c["status"] == "problem" for c in checks) else
              "ok" if any(c["status"] == "ok" for c in checks) else "no_disclosure")
    return per_vp, {"status": status, "failures": [f for c in checks for f in c["failures"]]}


def style_sha256(blocks):
    """blocks: {viewport "WxH": [block]}. Hash of text + style fields + above/below the fold per block."""
    key = {vp: [[b["text"], *(b[f] for f in STYLE_FIELDS), b["y"] < int(vp.split("x")[1])] for b in bl] for vp, bl in blocks.items()}
    return sha256(json.dumps(key, ensure_ascii=False, sort_keys=True))
