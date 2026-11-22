"""Legibility of risk / advertising disclosures: deterministic measurements and fixed thresholds (no LLM).

Rules (`pliki_dc/markdown/ZASÓB DLA UCZESTNIKÓW - InvestWatch - kryteria oceny informacji o ryzyku.md`):
R02 material unambiguously marked as advertising, R04 disclosure font size vs the dominant font of the material,
R05 exposure and contrast of the disclosure, R06 risk hidden in low-visibility places, R08 legibility on different
screen sizes. Measurements live next to the data (`source_meta.ocr_lines`, `PageSnapshot.blocks`), the verdict is
`check()`; an LLM later judges content and legal context, never these numbers.
"""
import re

import numpy as np

MIN_CONTRAST_RATIO = 4.5    # R05: WCAG 2.x AA for normal text
MIN_REL_FONT_SIZE = 0.7     # R04: disclosure size / dominant text size of the same material
MIN_FONT_PX_DESKTOP = 12    # R04 + R08: 1366 px wide viewport
MIN_FONT_PX_MOBILE = 11     # R04 + R08: 375 px wide viewport
IMAGE_WIDTH_PX = 1080       # R08: image line heights are scaled to this width before MIN_FONT_PX_DESKTOP
MIN_DISCLOSURE_CHARS = 25   # "CFD" alone is a product name (navigation, tile), not risk information
OTSU_BINS = 64

# Advertising / sponsorship label; counts on its own, these phrases are short by design.
LABEL_RE = re.compile(r"sponsorowan|sponsored|reklam|advertis|#ad\b|materia[lł] promocyjn|promotional material"
                      r"|wsp[oó][lł]prac|paid partnership", re.I)
RISK_RE = re.compile(r"ryzyk|risk|\d{1,3}(?:[.,]\d+)?\s?% (?:rachunk|of retail|retail)"
                     r"|kapita[lł] (?:jest )?zagro[zż]on|capital (?:is )?at risk|lose money|trac\w* pieni", re.I)
CFD_RE = re.compile(r"\bcfd", re.I)
RGBA_RE = re.compile(r"rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:[,/\s]+([\d.]+))?")


def is_disclosure(text, min_chars=MIN_DISCLOSURE_CHARS):
    """Advertising label (also standalone) or risk information; a bare product mention is not risk information."""
    t = text or ""
    return bool(LABEL_RE.search(t) or RISK_RE.search(t)) or (len(t) >= min_chars and bool(CFD_RE.search(t)))


def rgba(color):
    """CSS colour ('#rrggbb', '#rrggbbaa', 'rgb(…)', 'rgba(…)') -> (r, g, b, alpha 0-1); None when unparsable."""
    c = (color or "").strip()
    if c.startswith("#") and len(c) in (7, 9):
        v = [int(c[i:i + 2], 16) for i in range(1, len(c), 2)]
        return (*v[:3], (v[3] / 255) if len(v) == 4 else 1.0)
    m = RGBA_RE.match(c)
    if not m:
        return None
    return (float(m[1]), float(m[2]), float(m[3]), 1.0 if m[4] is None else float(m[4]))


def over(color, background):
    """Alpha-composite an (r, g, b, a) colour over an opaque (r, g, b) background."""
    return tuple(c * color[3] + b * (1 - color[3]) for c, b in zip(color[:3], background[:3]))


def luminance(rgb):
    """WCAG relative luminance of (r, g, b), 0-255 per channel."""
    lin = [(c / 255) / 12.92 if c / 255 <= 0.03928 else (((c / 255) + 0.055) / 1.055) ** 2.4 for c in rgb[:3]]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def ratio(lum_a, lum_b):
    """WCAG contrast ratio between two relative luminances."""
    hi, lo = max(lum_a, lum_b), min(lum_a, lum_b)
    return round((hi + 0.05) / (lo + 0.05), 2)


def css_contrast(color, background, opacity=1.0):
    """Contrast between a text colour and its background, both CSS strings; None when either is unparsable."""
    fg, bg = rgba(color), rgba(background)
    if fg is None or bg is None:
        return None
    bg_rgb = over(bg, (255, 255, 255))
    fg_rgb = over((*fg[:3], fg[3] * opacity), bg_rgb)
    return ratio(luminance(fg_rgb), luminance(bg_rgb))


def _luminance_map(rgb):
    lin = rgb.astype(np.float32) / 255
    lin = np.where(lin <= 0.03928, lin / 12.92, ((lin + 0.055) / 1.055) ** 2.4)
    return lin[..., 0] * 0.2126 + lin[..., 1] * 0.7152 + lin[..., 2] * 0.0722


def _otsu(lum):
    hist, edges = np.histogram(lum, bins=OTSU_BINS, range=(0.0, 1.0))
    centers = (edges[:-1] + edges[1:]) / 2
    weight, moment = np.cumsum(hist), np.cumsum(hist * centers)
    total, mean = weight[-1], moment[-1]
    below, above = weight[:-1], total - weight[:-1]
    ok = (below > 0) & (above > 0)
    if not ok.any():
        return None
    mb, ma = moment[:-1] / np.maximum(below, 1), (mean - moment[:-1]) / np.maximum(above, 1)
    var = np.where(ok, below * above * (mb - ma) ** 2, -1.0)
    return float(edges[1:][int(np.argmax(var))])


def patch_contrast(rgb):
    """Text vs background contrast inside an image patch (uint8 array h×w×3): Otsu split of per-pixel relative
    luminance, median of each class (medians ignore anti-aliased edge pixels). None when the patch is flat."""
    lum = _luminance_map(rgb)
    t = _otsu(lum)
    if t is None:
        return None
    dark, light = lum[lum <= t], lum[lum > t]
    if not dark.size or not light.size:
        return None
    return ratio(float(np.median(light)), float(np.median(dark)))


def dominant(sizes, weights):
    """Dominant text size of a material: median size weighted by text length; None when empty."""
    pairs = sorted((s, w) for s, w in zip(sizes, weights) if w > 0)
    total = sum(w for _, w in pairs)
    if not total:
        return None
    seen = 0
    for size, w in pairs:
        seen += w
        if seen >= total / 2:
            return size
    return pairs[-1][0]


def rel_size(size, dominant_size):
    return round(size / dominant_size, 2) if dominant_size else None


def check(disclosures, min_font_px=MIN_FONT_PX_DESKTOP, in_text=False):
    """Verdict for one record or page against the fixed thresholds.

    disclosures: [{text, contrast_ratio, rel_font_size, font_px}] — only the lines / blocks that are a disclosure.
    in_text: the disclosure is also in the record text or description, so the material is marked regardless of how
    the image renders it (R02); a disclosure that exists only on the image and misses a threshold is hidden (R06).
    -> {"status": "ok|problem|no_disclosure", "failures": [{rule, metric, value, threshold, text}]}
    """
    failures = []
    for d in disclosures:
        for rule, metric, threshold in (("R05", "contrast_ratio", MIN_CONTRAST_RATIO),
                                        ("R04", "rel_font_size", MIN_REL_FONT_SIZE),
                                        ("R08", "font_px", min_font_px)):
            value = d.get(metric)
            if value is not None and value < threshold:
                failures.append({"rule": rule, "metric": metric, "value": value, "threshold": threshold,
                                 "text": (d.get("text") or "")[:120]})
    if not disclosures and not in_text:
        return {"status": "no_disclosure", "failures": []}
    return {"status": "problem" if failures and not in_text else "ok", "failures": failures}
