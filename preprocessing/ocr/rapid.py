"""OCR preprocessing step (like D7 whisper fallback): for RawDocuments with image_refs and no text sections,
set `text` = [{"type": "ocr", "text": ...}] and `source_meta.ocr` = {engine, model, mean_confidence, lines, seconds}.
Engine: RapidOCR (ONNX, CPU), PP-OCRv5 Latin mobile recogniser (covers Polish diacritics)."""
import sys
import time

from rapidocr import LangRec, ModelType, OCRVersion, RapidOCR

_engine = None


def engine():
    global _engine
    if _engine is None:
        _engine = RapidOCR(params={"Rec.lang_type": LangRec.LATIN, "Rec.ocr_version": OCRVersion.PPOCRV5,
                                   "Rec.model_type": ModelType.MOBILE})
    return _engine


def ocr_image(path):
    t0 = time.perf_counter()
    res = engine()(path)
    txts, scores = list(res.txts or []), list(res.scores or [])
    return {"text": "\n".join(txts), "engine": "rapidocr", "model": "PP-OCRv5 latin mobile",
            "mean_confidence": round(sum(scores) / len(scores), 3) if scores else None,
            "lines": len(txts), "seconds": round(time.perf_counter() - t0, 2)}


def ocr_boxes(path):
    """[(text, [x, y, w, h], score)] per recognised line; box = axis-aligned bounds of the detected quad."""
    res = engine()(path)
    out = []
    for quad, txt, score in zip(res.boxes if res.boxes is not None else [], res.txts or [], res.scores or []):
        xs, ys = [p[0] for p in quad], [p[1] for p in quad]
        out.append((txt, [int(min(xs)), int(min(ys)), int(max(xs) - min(xs)), int(max(ys) - min(ys))], float(score)))
    return out


def has_text(doc):
    t = doc.get("text")
    return any(s.get("text") for s in t) if isinstance(t, list) else bool(t)


def enrich(doc):
    refs = doc.get("source_meta", {}).get("image_refs") or []
    if has_text(doc) or not refs:
        return doc
    r = ocr_image(refs[0])
    txt = r.pop("text")
    doc["text"] = [{"type": "ocr", "text": txt}] if txt else []
    doc["source_meta"]["ocr"] = r
    doc["source_meta"]["text_source"] = "ocr" if txt else None
    return doc


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(p, ocr_image(p))
