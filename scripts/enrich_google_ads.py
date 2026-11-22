"""Add countries where each Google creative was shown (GetCreativeById) and a diacritics-insensitive Polish
language flag to an existing ads sample, without re-downloading creatives or re-running OCR.

Sequential and resumable: Google answers HTTP 429 when queried in parallel, so requests go one by one with a
pause, back off on errors, and records that already have regions in `dst` are not queried again.

Usage: python scripts/enrich_google_ads.py data/samples/ads_sample_v1.jsonl data/samples/ads_sample_v2.jsonl
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scrapers" / "poc"))

from common import pl_score, plain_text  # noqa: E402
from google_ads.atc_rpc import creative_regions  # noqa: E402

PAUSE_S = 1.5
BACKOFF_S = [30, 60, 120, 300, 600]


def save(dst, docs):
    with open(ROOT / dst, "w", encoding="utf-8", newline="\n") as f:
        for d in docs:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")


def main(src, dst):
    docs = [json.loads(line) for line in open(ROOT / src, encoding="utf-8") if line.strip()]
    done = {}
    if (ROOT / dst).exists():
        for line in open(ROOT / dst, encoding="utf-8"):
            if line.strip():
                d = json.loads(line)
                if "regions_iso_numeric" in d["source_meta"]:
                    done[d["source_meta"]["creative_id"]] = d["source_meta"]
    for i, doc in enumerate(docs):
        m = doc["source_meta"]
        m.pop("region", None)
        if m["creative_id"] in done:
            m.update({k: v for k, v in done[m["creative_id"]].items() if k.startswith(("regions", "pl_"))})
        else:
            for wait in [0] + BACKOFF_S:
                time.sleep(wait)
                try:
                    m.update(creative_regions(m["advertiser_id"], m["creative_id"]))
                    m.pop("region_error", None)
                    break
                except Exception as e:
                    m["region_error"] = str(e)[:100]
                    print(f"{i}: {m['region_error']}, next wait", flush=True)
            time.sleep(PAUSE_S)
        m["lang_hint_pl"] = pl_score(plain_text(doc)) >= 2
        if i % 20 == 0:
            save(dst, docs)
            print(f"{i + 1}/{len(docs)}", flush=True)
    save(dst, docs)
    m = [d["source_meta"] for d in docs]
    print(json.dumps({"records": len(docs), "region_errors": sum("region_error" in x for x in m),
                      "shown_in_pl": sum(616 in x.get("regions_iso_numeric", []) for x in m),
                      "pl_only": sum(bool(x.get("pl_only")) for x in m),
                      "lang_pl": sum(x["lang_hint_pl"] for x in m),
                      "lang_pl_or_pl_only": sum(x["lang_hint_pl"] or bool(x.get("pl_only")) for x in m)}))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
