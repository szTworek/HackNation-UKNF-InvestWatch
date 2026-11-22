"""MultiAgentFraudBench (syntetyczne posty oszustów, CC BY-NC-SA 4.0) → tłumaczenie na polski (Gemini, tylko dane).

Posty trafiają do data/pool/mafb_pl.jsonl jako source="mafb" (meta.synthetic=True → tylko trening, nigdy test).
  uv run python scripts/translate_mafb.py --invest 1900 --other 300
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx
import pandas as pd

from investwatch_ml.schema import Doc, append_jsonl, existing_ids
from investwatch_ml.teacher import load_env

ML_DIR = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
URL = "https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"
PROMPT = """Przetłumacz poniższe posty z mediów społecznościowych na naturalny polski, tak jakby napisał je polski \
użytkownik Facebooka / Instagrama / TikToka. Zachowaj emoji, hashtagi (możesz je spolszczyć), tickery i styl. \
Kwoty w USD w mniej więcej połowie postów zamień na złotówki (realistycznie). Nie łagodź treści i nie dodawaj komentarzy. \
Zwróć wyłącznie tablicę JSON z tłumaczeniami w tej samej kolejności i tej samej liczbie elementów.

POSTY:
"""


def log(m: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {m}", flush=True)


def translate(http: httpx.Client, key: str, model: str, texts: list[str]) -> list[str]:
    body = {"contents": [{"role": "user", "parts": [{"text": PROMPT + json.dumps(texts, ensure_ascii=False)}]}],
            "generationConfig": {"temperature": 0.4, "responseMimeType": "application/json"}}
    for attempt in range(6):
        for net_try in range(60):  # przerwy w sieci: czekaj do 30 min zamiast tracić paczkę
            try:
                r = http.post(URL.format(m=model), json=body, headers={"x-goog-api-key": key})
                break
            except httpx.TransportError:
                if net_try == 59:
                    raise
                time.sleep(30)
        if r.status_code in (429, 500, 503):
            time.sleep(min(15 * (attempt + 1), 90))
            continue
        r.raise_for_status()
        out = json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])
        if isinstance(out, list) and len(out) == len(texts):
            return [str(x) for x in out]
        raise ValueError(f"zła liczba tłumaczeń: {len(out)} vs {len(texts)}")
    raise RuntimeError("limit Gemini")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--invest", type=int, default=1900)
    ap.add_argument("--other", type=int, default=300)
    ap.add_argument("--batch", type=int, default=10)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--model", default="gemini-3.5-flash-lite")
    args = ap.parse_args()
    load_env()
    key = os.environ["GEMINI_API_KEY"]
    out = ML_DIR / "data/pool/mafb_pl.jsonl"
    done = existing_ids(out)

    df = pd.read_parquet(ML_DIR / "data/raw/mafb_full.parquet").reset_index(names="row")
    inv = df[df["category"] == "Consumer Investment Fraud"].sample(frac=1, random_state=1).head(args.invest)
    oth = df[df["category"] != "Consumer Investment Fraud"].sample(n=args.other, random_state=1)
    rows = [r for _, r in pd.concat([inv, oth]).iterrows() if f"mafb:{r['row']}" not in done]
    random.Random(2).shuffle(rows)
    batches = [rows[i: i + args.batch] for i in range(0, len(rows), args.batch)]
    log(f"do tłumaczenia: {len(rows)} postów w {len(batches)} paczkach")

    http = httpx.Client(timeout=120)
    n = 0

    def work(batch):
        pl = translate(http, key, args.model, [r["content"] for r in batch])
        return [Doc(id=f"mafb:{r['row']}", source="mafb", platform="other", kind="post", author=f"mafb_{r['username']}",
                    text=t.strip(), meta={"synthetic": True, "license": "CC BY-NC-SA 4.0", "category": r["category"],
                                          "subcategory": r["leaf_subcategory"], "deception_type": r["deception_type"],
                                          "weak_is_scam": True, "weak_investment": r["category"] == "Consumer Investment Fraud"})
                for r, t in zip(batch, pl)]

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(work, b) for b in batches]
        for i, f in enumerate(as_completed(futs), 1):
            try:
                docs = f.result()
                append_jsonl(out, [d.model_dump() for d in docs])
                n += len(docs)
            except Exception as e:
                log(f"paczka: {type(e).__name__}: {str(e)[:120]}")
            if i % 10 == 0 or i == len(futs):
                log(f"{i}/{len(futs)} paczek | przetłumaczone {n}")
    log(f"koniec: +{n} -> {out}")


if __name__ == "__main__":
    main()
