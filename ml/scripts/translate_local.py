"""Lokalne tłumaczenie EN -> PL (NLLB na GPU, bez limitów API). Tylko dane treningowe, meta.synthetic=True.

Źródła: brakujące posty MAFB, Fraud-R1 (inwestycje), VideoConviction (rekomendacje finfluencerów).
Wznawialne. Licencje: NLLB i VideoConviction CC BY-NC, MAFB CC BY-NC-SA, Fraud-R1 bez podanej licencji.

  uv run python scripts/translate_local.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import pandas as pd
import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

from investwatch_ml.schema import Doc, append_jsonl, existing_ids

ML_DIR = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
MODEL = "facebook/nllb-200-distilled-600M"
POOL = ML_DIR / "data/pool"


def log(m: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {m}", flush=True)


def sentences(text: str, max_chars: int) -> list[str]:
    """NLLB gubi kolejne zdania w jednym wejściu, więc tłumaczymy zdanie po zdaniu."""
    out = []
    for s in re.split(r"(?<=[.!?…])\s+|\n+", text[:max_chars]):
        s = s.strip()
        while len(s) > 350:
            cut = s.rfind(" ", 0, 350)
            cut = cut if cut > 0 else 350
            out.append(s[:cut])
            s = s[cut:].strip()
        if s:
            out.append(s)
    return out


def mafb_items() -> list[dict]:
    df = pd.read_parquet(ML_DIR / "data/raw/mafb_full.parquet").reset_index(names="row")
    inv = df[df["category"] == "Consumer Investment Fraud"].sample(frac=1, random_state=1).head(1900)
    oth = df[df["category"] != "Consumer Investment Fraud"].sample(n=300, random_state=1)
    return [{"file": "mafb_pl.jsonl", "id": f"mafb:{r['row']}", "source": "mafb", "author": f"mafb_{r['username']}", "kind": "post",
             "text": r["content"], "meta": {"license": "CC BY-NC-SA 4.0", "category": r["category"], "subcategory": r["leaf_subcategory"],
                                            "deception_type": r["deception_type"], "weak_is_scam": True,
                                            "weak_investment": r["category"] == "Consumer Investment Fraud"}}
            for _, r in pd.concat([inv, oth]).iterrows()]


def fraud_items() -> list[dict]:
    rows = json.loads((ML_DIR / "data/raw/fraud_r1/dataset/FP-base-full/FP-base-English.json").read_text(encoding="utf-8"))
    out = []
    for x in rows:
        if x["subcategory"] != "investment and financial management":
            continue
        for kind, field in (("raw", "raw_data"), ("gen", "generated text")):
            if x.get(field):
                out.append({"file": "fraud_r1_pl.jsonl", "id": f"fraudr1:{x['id']}:{kind}", "source": "fraud_r1",
                            "author": f"fraudr1_{x['id']}", "kind": "post", "text": str(x[field]),
                            "meta": {"license": "unspecified", "weak_is_scam": True, "weak_investment": True}})
    return out


def video_items() -> list[dict]:
    df = pd.read_csv(ML_DIR / "data/raw/videoconviction/VideoConviction.csv")
    df = df[df["segment_transcript"].notna()].drop_duplicates("segment_transcript")
    return [{"file": "videoconviction_pl.jsonl", "id": f"vconv:{r['id']}:{r['derived_inner_id']}", "source": "videoconviction",
             "author": str(r["channelTitle"]), "kind": "transcript", "text": str(r["segment_transcript"]),
             "meta": {"license": "CC BY-NC 4.0", "action": r["action"], "is_rec_present": r["is_rec_present"],
                      "conviction": None if pd.isna(r["conviction_score"]) else float(r["conviction_score"])}}
            for _, r in df.iterrows()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=24)
    ap.add_argument("--max-chars", type=int, default=2500)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    groups = [fraud_items(), video_items(), mafb_items()]  # najpierw małe, cenne źródła
    done = {f: existing_ids(POOL / f) for f in ("mafb_pl.jsonl", "fraud_r1_pl.jsonl", "videoconviction_pl.jsonl")}
    items = [x for g in groups for x in g if x["id"] not in done[x["file"]]]
    items = items[: args.limit] if args.limit else items
    log(f"do tłumaczenia: {len(items)} dokumentów")
    tok = AutoTokenizer.from_pretrained(MODEL, src_lang="eng_Latn")
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL, torch_dtype=torch.float16).to("cuda").eval()
    bos = tok.convert_tokens_to_ids("pol_Latn")

    def translate(sents: list[str]) -> list[str]:
        res: list[str] = []
        for i in range(0, len(sents), args.batch):
            x = tok(sents[i: i + args.batch], return_tensors="pt", padding=True, truncation=True, max_length=200).to("cuda")
            with torch.inference_mode():
                o = model.generate(**x, forced_bos_token_id=bos, max_new_tokens=220, num_beams=2)
            res += tok.batch_decode(o, skip_special_tokens=True)
        return res

    n = failed = 0
    for k, it in enumerate(items, 1):
        try:
            parts = sentences(it["text"], args.max_chars)
            text = " ".join(translate(parts)).strip()
            if len(text) < 15:
                raise ValueError("puste tłumaczenie")
            doc = Doc(id=it["id"], source=it["source"], platform="other", kind=it["kind"], author=it["author"], text=text,
                      meta={**it["meta"], "synthetic": True, "translated_by": "nllb-200-distilled-600M"})
            append_jsonl(POOL / it["file"], [doc.model_dump()])
            n += 1
        except Exception as e:
            failed += 1
            torch.cuda.empty_cache()
            log(f"{it['id']}: {type(e).__name__}: {str(e)[:100]}")
        if k % 50 == 0 or k == len(items):
            log(f"{k}/{len(items)} | zapisane {n}, błędy {failed}")
    log(f"koniec: +{n}")


if __name__ == "__main__":
    main()
