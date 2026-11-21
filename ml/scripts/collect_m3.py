"""Celowane zbieranie pod M3 (doradztwo, zarządzanie, sygnały, płatne grupy, mentoring).

YouTube Data API: zapisuje tytuł + opis filmów, w których opis wygląda na ofertę -> data/pool/m3_youtube.jsonl.
Microsoft Ad Library: reklamy po słowach M3 -> data/raw/scraper_live/bing_ads (potem ingest_scraper.py).

  uv run python scripts/collect_m3.py --yt-budget 2000
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
import collect_api  # noqa: E402
from ingest_scraper import p_polish  # noqa: E402

from investwatch_ml.schema import Doc, append_jsonl, existing_ids  # noqa: E402
from investwatch_ml.text import normalize  # noqa: E402

ML_DIR = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
YT_QUERIES = ["konsultacje inwestycyjne 1:1", "grupa premium sygnały forex", "płatne sygnały krypto",
              "zarządzanie portfelem klienta", "doradca inwestycyjny konsultacja", "mentoring tradingowy",
              "program mentoringowy giełda", "audyt portfela inwestycyjnego", "prywatna grupa inwestorów discord",
              "kanał vip telegram trading", "ułożę ci portfel inwestycyjny", "newsletter inwestycyjny premium",
              "copy trading kopiuj transakcje", "inwestuję za klientów", "społeczność inwestorów premium",
              "akademia tradingu", "indywidualna strategia inwestycyjna", "sygnały giełdowe abonament"]
BING_M3 = {"advisory": ["konsultacje", "doradca", "mentor", "sygnaly", "akademia", "newsletter", "strategie", "analizy"]}
OFFER = re.compile(r"konsultac|mentoring|mentor\b|1\s*[:na]\s*1|sygna[łl]|grup[aęy] (vip|premium|zamkni)|\bvip\b|premium|"
                   r"zarządza|doradz|doradc|audyt portfel|portfel.{0,30}(dla ciebie|indywidual)|telegram|discord|"
                   r"copy ?trading|kopiuj|newsletter|akademi|zapisz się|umów|napisz do mnie|priv", re.I)
INVEST = re.compile(r"inwest|gie[łl]d|akcj|forex|trad|krypto|bitcoin|portfel|etf|obligac|spółk", re.I)


def log(m: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {m}", flush=True)


def collect_youtube(budget: int) -> int:
    key = collect_api.youtube_key()
    if not key:
        log("[m3] brak YOUTUBE_API_KEY")
        return 0
    out = ML_DIR / "data/pool/m3_youtube.jsonl"
    seen = existing_ids(out)
    used = added = 0
    with httpx.Client(timeout=30, headers={"X-Goog-Api-Key": key}) as http:
        for q in YT_QUERIES:
            if used + 101 > budget:
                break
            s = http.get(f"{collect_api.YT_API}/search", params={"part": "snippet", "q": q, "type": "video", "maxResults": 50,
                                                                  "regionCode": "PL", "relevanceLanguage": "pl"})
            used += 100
            if s.status_code != 200:
                log(f"[m3] search HTTP {s.status_code}; kończę YouTube")
                break
            ids = [i["id"]["videoId"] for i in s.json().get("items", []) if f"m3yt:{i['id']['videoId']}" not in seen]
            docs = []
            if ids:
                v = http.get(f"{collect_api.YT_API}/videos", params={"part": "snippet", "id": ",".join(ids[:50])})
                used += 1
                if v.status_code != 200:
                    log(f"[m3] videos HTTP {v.status_code}")
                    continue
                for it in v.json().get("items", []):
                    sn = it["snippet"]
                    title, desc = normalize(sn.get("title") or ""), normalize(sn.get("description") or "")[:2500]
                    full = f"{title}\n{desc}"
                    if len(desc) < 80 or not OFFER.search(full) or not INVEST.search(full) or p_polish(full) < 0.7:
                        continue
                    doc_id = f"m3yt:{it['id']}"
                    seen.add(doc_id)
                    docs.append(Doc(id=doc_id, source="scraper_m3", platform="youtube", kind="post",
                                    url=f"https://www.youtube.com/watch?v={it['id']}", author=sn.get("channelTitle"),
                                    title=title, text=desc, published_at=sn.get("publishedAt"),
                                    meta={"query": q, "query_group": "advisory", "channel_id": sn.get("channelId"),
                                          "description_only": True}).model_dump())
                append_jsonl(out, docs)
            added += len(docs)
            log(f"[m3] {q}: +{len(docs)} | jednostki {used}")
            time.sleep(1)
    return added


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--yt-budget", type=int, default=2000)
    ap.add_argument("--bing-pages", type=int, default=5)
    args = ap.parse_args()
    yt = collect_youtube(args.yt_budget)
    collect_api.BING_WORDS = BING_M3
    bing = collect_api.collect_bing(args.bing_pages, 20.0)
    log(f"koniec M3: YouTube +{yt}, Bing +{bing}")


if __name__ == "__main__":
    main()
