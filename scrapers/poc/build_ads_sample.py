"""One-off: build UKNF/data/samples/ads_sample_v1.jsonl from Google Ads Transparency (region PL):
google_ads.atc_rpc (content.js text + images) -> preprocessing/ocr/rapid.py for image creatives.
Keeps records with non-empty text."""
import collections
import json
import sys
import time

from common import POC_DIR, pl_score, plain_text
from google_ads.atc_rpc import collect

sys.path.insert(0, str(POC_DIR.parents[1] / "preprocessing" / "ocr"))
from rapid import enrich  # noqa: E402

DOMAINS = ["xtb.com", "etoro.com", "plus500.com", "mbank.pl", "bossa.pl", "revolut.com", "ing.pl", "pkobp.pl",
           "trading212.com", "capital.com", "ig.com", "interactivebrokers.com", "freedom24.com", "home.saxo",
           "degiro.pl", "finax.eu", "avatrade.com", "saxotrader.com"]
OUT = POC_DIR.parents[1] / "data" / "samples" / "ads_sample_v1.jsonl"
if len(sys.argv) > 2:  # python build_ads_sample.py xtb.com,etoro.com data/samples/ads_sample_v3.jsonl [pages]
    DOMAINS, OUT = sys.argv[1].split(","), POC_DIR.parents[1] / sys.argv[2]
PAGES = int(sys.argv[3]) if len(sys.argv) > 3 else 2


def main():
    t0, notes, kept, stats = time.perf_counter(), {}, [], collections.Counter()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("", encoding="utf-8")
    for d in DOMAINS:
        start = len(kept)
        n = {}
        try:
            for doc in collect(d, n, pages=PAGES, workers=3):
                if not plain_text(doc):
                    try:
                        enrich(doc)
                    except Exception as e:
                        doc["source_meta"]["ocr_error"] = str(e)[:100]
                stats[(doc["source_meta"]["format"], doc["source_meta"]["text_source"] or "none")] += 1
                if plain_text(doc).strip():
                    doc["source_meta"]["lang_hint_pl"] = pl_score(plain_text(doc)) >= 2
                    kept.append(doc)
        except Exception as e:
            n["error"] = str(e)[:150]
        notes[d] = n
        with OUT.open("a", encoding="utf-8") as f:
            for doc in kept[start:]:
                f.write(json.dumps(doc, ensure_ascii=False) + "\n")
        print(d, n.get("pages"), n.get("error", ""), "kept so far", len(kept), round(time.perf_counter() - t0), "s", flush=True)
        if "429" in n.get("error", ""):
            break
    summary = {"records": len(kept), "seconds": round(time.perf_counter() - t0),
               "by_sponsor": collections.Counter(d["sponsor"] for d in kept).most_common(),
               "by_format_textsource": {f"{k[0]}/{k[1]}": v for k, v in stats.items()},
               "pl_hint": sum(d["source_meta"]["lang_hint_pl"] for d in kept), "notes": notes}
    (OUT.parent / (OUT.stem + ".summary.json")).write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("records", "seconds", "pl_hint", "by_format_textsource")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
