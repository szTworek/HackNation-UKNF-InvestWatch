"""Pomiary układu tekstu na grafice reklamy (D3 dla obrazów): OCR z ramkami + kontrast z pikseli.

Dla rekordu z grafiką (link do pliku w `links` albo `source_meta.image_refs`) zapisuje `source_meta.ocr_layout`:
  {"image": {"w", "h"}, "lines": [{"text", "x", "y", "w", "h", "conf", "contrast"}]}
`h` to wysokość ramki linii w pikselach (przybliżenie wielkości czcionki), `contrast` to kontrast WCAG
między jasnym i ciemnym percentylem pikseli w ramce. Werdykty reguł 4–6 i 10 liczy ai-service (ml/src/investwatch_ml/visual.py).

Uruchamiaj w środowisku kolektorów (RapidOCR):
  scrapers/poc/.venv/Scripts/python preprocessing/ocr/layout.py IN.jsonl OUT.jsonl [--limit N]
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import httpx
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rapid import engine  # noqa: E402

CACHE = Path(__file__).resolve().parents[2] / "scrapers/poc/results/ocr_layout_images"
IMG_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp")


def _lin(c):
    c = c / 255.0
    return np.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def contrast(img: np.ndarray, box) -> float:
    """Kontrast WCAG między tekstem i tłem w ramce: 10. i 90. percentyl luminancji."""
    x0, y0, x1, y1 = box
    crop = img[max(0, y0):y1, max(0, x0):x1]
    if crop.size == 0:
        return 0.0
    rgb = _lin(crop[..., :3].astype(float))
    lum = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    lo, hi = np.percentile(lum, 10), np.percentile(lum, 90)
    return round(float((hi + 0.05) / (lo + 0.05)), 2)


def image_url(rec: dict) -> str | None:
    refs = (rec.get("source_meta") or {}).get("image_refs") or []
    for u in list(refs) + list(rec.get("links") or []):
        if isinstance(u, str) and (u.lower().split("?")[0].endswith(IMG_EXT) or "simgad" in u):
            return u
    return None


def fetch(url: str, http: httpx.Client) -> Path | None:
    if not url.startswith("http"):
        p = Path(url)
        return p if p.exists() else None
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / (hashlib.sha1(url.encode()).hexdigest()[:20])
    if not path.exists():
        r = http.get(url, follow_redirects=True)
        if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image"):
            return None
        path.write_bytes(r.content)
    return path


def measure(path: Path) -> dict | None:
    with Image.open(path) as im:
        img = np.asarray(im.convert("RGB"))
    res = engine()(img)
    if not res.boxes is not None and not len(res.boxes or []):
        return None
    lines = []
    for box, txt, conf in zip(res.boxes if res.boxes is not None else [], res.txts or [], res.scores or []):
        pts = np.asarray(box)
        x0, y0 = pts.min(axis=0).astype(int)
        x1, y1 = pts.max(axis=0).astype(int)
        lines.append({"text": txt, "x": int(x0), "y": int(y0), "w": int(x1 - x0), "h": int(y1 - y0),
                      "conf": round(float(conf), 3), "contrast": contrast(img, (x0, y0, x1, y1))})
    return {"image": {"w": int(img.shape[1]), "h": int(img.shape[0])}, "lines": lines}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    out, n_ok, n = [], 0, 0
    with httpx.Client(timeout=30, headers={"User-Agent": "investwatch-research"}) as http:
        for line in open(args.input, encoding="utf-8"):
            if not line.strip():
                continue
            rec = json.loads(line)
            url = image_url(rec)
            if url and (args.limit is None or n < args.limit):
                n += 1
                try:
                    path = fetch(url, http)
                    layout = measure(path) if path else None
                    if layout:
                        rec.setdefault("source_meta", {})["ocr_layout"] = layout
                        n_ok += 1
                except Exception as e:  # pojedyncza grafika nie przerywa przebiegu
                    print(f"{url[:80]}: {type(e).__name__}: {e}", file=sys.stderr)
            out.append(rec)
    Path(args.output).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out), encoding="utf-8")
    print(f"grafiki: {n}, zmierzone: {n_ok} -> {args.output}")


if __name__ == "__main__":
    main()
