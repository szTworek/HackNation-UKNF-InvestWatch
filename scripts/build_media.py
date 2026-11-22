"""Media store for the PoC: collector images (git-ignored originals) -> committed `data/media/<sha>.webp` thumbnails
plus legibility measurements of every OCR line of the original image.

Images are matched to records by file name (the collectors name them after the content hash), so renamed or moved
result folders in old samples do not matter. Resumable: entries already in the index are skipped.

Usage: python scripts/build_media.py [--limit N]
Output: data/media/<sha>.webp, data/media/index.json (image file name -> thumbnail + measurements), read by
`adapters/google_ads.py` and `adapters/meta_ads.py`.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "preprocessing" / "ocr"))

import rapid  # noqa: E402

from preprocessing import legibility as lg  # noqa: E402

THUMB_PX = 600
WEBP_QUALITY = 75
RES = ROOT / "scrapers" / "poc" / "results"
IMAGE_DIRS = (RES / "google_ads.atc_rpc" / "images", RES / "fb_ads.ad_library_web" / "images")
SAMPLES = ("data/samples/ads_sample_v3b.jsonl", "data/samples/ads_sample_v3.jsonl", "data/samples/ads_sample_v1.jsonl",
           "data/samples/meta_ads_entities_v1.jsonl", "data/samples/meta_ads_sample_v1.jsonl",
           "scrapers/poc/results/google_ads.atc_rpc/20261121-172343-docs.json")
OUT = ROOT / "data" / "media"
INDEX = OUT / "index.json"


def file_name(ref):
    return ref.replace("\\", "/").rsplit("/", 1)[-1]


def load(path):
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]
    return json.loads(path.read_text(encoding="utf-8"))


def referenced():
    """{image file name: path in the collector results} for every image used by a sample record."""
    have = {p.name: p for d in IMAGE_DIRS if d.exists() for p in d.iterdir() if p.is_file()}
    out, missing = {}, set()
    for sample in SAMPLES:
        for doc in load(ROOT / sample):
            for ref in (doc.get("source_meta") or {}).get("image_refs") or []:
                name = file_name(ref)
                if name in have:
                    out[name] = have[name]
                else:
                    missing.add(name)
    return out, sorted(missing), len(have)


def measure(path):
    """(image size, dominant line height, OCR lines with legibility measurements) of the original image."""
    px = np.asarray(Image.open(path).convert("RGB"))
    boxes = rapid.ocr_boxes(str(path))
    dom = lg.dominant([b[3] for _, b, _ in boxes], [len(t) for t, _, _ in boxes])
    lines = []
    for text, (x, y, w, h), _score in boxes:
        patch = px[max(0, y):y + h, max(0, x):x + w]
        lines.append({"text": text, "box": [x, y, w, h], "box_height_px": h, "rel_font_size": lg.rel_size(h, dom),
                      "contrast_ratio": lg.patch_contrast(patch) if patch.size else None,
                      "is_disclosure": lg.is_disclosure(text)})
    return (px.shape[1], px.shape[0]), dom, lines


def thumbnail(path, key):
    img = Image.open(path).convert("RGB")
    img.thumbnail((THUMB_PX, THUMB_PX))
    img.save(OUT / key, "WEBP", quality=WEBP_QUALITY, method=6)
    return img.size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    index = json.loads(INDEX.read_text(encoding="utf-8")) if INDEX.exists() else {}
    paths, missing, total = referenced()
    todo = [(n, p) for n, p in sorted(paths.items()) if n not in index or not (OUT / index[n]["key"]).exists()]
    print(f"{len(paths)} images referenced by samples ({total} on disk), {len(missing)} missing, {len(todo)} to build", flush=True)
    for i, (name, path) in enumerate(todo[:a.limit] if a.limit else todo, 1):
        key = Path(name).stem + ".webp"
        (tw, th), dom, lines = measure(path)
        size = thumbnail(path, key)
        index[name] = {"key": key, "width": size[0], "height": size[1], "image_width": tw, "image_height": th,
                       "dominant_line_px": dom, "ocr_lines": lines}
        if i % 25 == 0 or i == len(todo):
            INDEX.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
            print(f"{i}/{len(todo)}", flush=True)
    INDEX.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    mb = sum(f.stat().st_size for f in OUT.glob("*.webp")) / 1024 / 1024
    disclosure = sum(1 for e in index.values() if any(l["is_disclosure"] for l in e["ocr_lines"]))
    print(json.dumps({"images": len(index), "with_disclosure_line": disclosure, "missing_files": len(missing),
                      "webp_mb": round(mb, 1), "index_kb": round(INDEX.stat().st_size / 1024)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
