"""Więcej danych z oficjalnych API, słowa kluczowe celowane w rzadkie klasy (doradztwo, rekomendacje, oferty, scam).

- Microsoft Ad Library (bez klucza) -> data/raw/scraper_live/bing_ads/records.jsonl (potem ingest_scraper.py)
- YouTube Data API -> nowe filmy w data/pool/youtube_candidates.jsonl (potem collect_youtube_asr.py)

YouTube: limit 10 000 jednostek dziennie, search = 100; domyślnie zużywa maks. 4000, bo klucz jest współdzielony.

  uv run python scripts/collect_api.py
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path

import httpx

from investwatch_ml.schema import append_jsonl, read_jsonl

ML_DIR = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
SCRAPER_ENV = ML_DIR.parents[1] / "HackNation-UKNF-InvestWatch" / ".env"
YT_API = "https://www.googleapis.com/youtube/v3"
BING_API = "https://adlibrary.api.bingads.microsoft.com/api/v1/Ads"

QUERIES: dict[str, list[str]] = {
    "advisory": ["sygnały tradingowe telegram", "płatna grupa inwestycyjna", "kopiuj moje transakcje",
                 "mentoring inwestycyjny", "indywidualne doradztwo inwestycyjne", "zarządzanie kapitałem klienta",
                 "pomnożę twoje pieniądze", "kurs tradingu mentoring", "portfel inwestycyjny dla ciebie"],
    "reco": ["jaką spółkę kupić teraz", "akcje warte kupienia", "krypto które wystrzeli", "altcoin 100x",
             "w co inwestować teraz", "kupuję te akcje"],
    "scam": ["zarabianie bez ryzyka", "bot tradingowy zysk", "automatyczny trading zarabiaj",
             "inwestycja gwarantowany zysk", "zainwestuj 1000 zł", "fałszywy broker", "piramida finansowa",
             "oszustwo inwestycyjne", "platforma inwestycyjna wypłata"],
    "promo": ["kod polecający broker", "załóż konto u brokera bonus", "bonus giełda kryptowalut", "prop trading firma",
              "współpraca reklamowa inwestowanie", "najlepszy broker forex", "lokata inwestycyjna wysoki zysk"],
}
YT_PRIORITY = ("advisory", "reco", "scam", "promo")
# Microsoft Ad Library nie znajduje fraz wielowyrazowych (0 wyników), więc tu pojedyncze słowa
BING_WORDS: dict[str, list[str]] = {
    "advisory": ["sygnały", "mentoring", "doradztwo", "portfel", "kapitał"],
    "reco": ["akcje", "giełda", "kryptowaluty", "bitcoin", "etf", "obligacje"],
    "scam": ["zarabianie", "zarabiaj", "dochód", "zysk", "inwestuj"],
    "promo": ["inwestycje", "inwestowanie", "broker", "trading", "fundusz", "złoto", "lokata"],
}


def log(m: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {m}", flush=True)


def youtube_key() -> str | None:
    if os.environ.get("YOUTUBE_API_KEY"):
        return os.environ["YOUTUBE_API_KEY"]
    if SCRAPER_ENV.exists():
        for line in SCRAPER_ENV.read_text(encoding="utf-8").splitlines():
            if line.startswith("YOUTUBE_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"')
    return None


def iso_seconds(v: str) -> int:
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", v or "")
    if not m:
        return 0
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def collect_bing(pages: int, delay: float) -> int:
    out = ML_DIR / "data/raw/scraper_live/bing_ads/records.jsonl"
    seen = {r["source_url"] for r in read_jsonl(out)}
    added = 0
    with httpx.Client(timeout=30, headers={"User-Agent": "investwatch-research"}) as http:
        for group, queries in BING_WORDS.items():
            for q in queries:
                n_q = 0
                for page in range(pages):
                    for attempt in range(5):  # limit Binga: czekaj zamiast dobijać się do API
                        r = http.get(BING_API, params={"searchText": q, "top": 10, "skip": page * 10, "countryCodes": 151})
                        time.sleep(delay)
                        if r.status_code != 429:
                            break
                        wait = float(r.headers.get("retry-after") or 120 * (attempt + 1))
                        log(f"[bing] limit 429; czekam {wait:.0f}s")
                        time.sleep(min(wait, 600))
                    if r.status_code != 200:
                        log(f"[bing] {q}: HTTP {r.status_code}")
                        break
                    js = r.json()
                    rows = js.get("value", js if isinstance(js, list) else [])
                    new = []
                    for a in rows:
                        url = f"https://adlibrary.ads.microsoft.com/ad/{a.get('AdId')}"
                        if url in seen:
                            continue
                        seen.add(url)
                        text = {k: v.strip() for k, v in (("title", a.get("Title")), ("ad_body", a.get("Description")))
                                if isinstance(v, str) and v.strip()}
                        new.append({"source": "microsoft_ad_library", "source_url": url, "author": a.get("AdvertiserName"),
                                    "published_at": None, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                    "query_keywords": [q], "content_keywords": [], "text": text,
                                    "sponsor": a.get("AdvertiserName"),
                                    "links": [u for u in (a.get("DestinationUrl"),) if u], "content_type": "ad",
                                    "source_meta": {"query": q, "group": group, "ad_id": a.get("AdId"),
                                                    "advertiser_id": a.get("AdvertiserId"),
                                                    "display_url": a.get("DisplayUrl"), "country_code": 151}})
                    append_jsonl(out, new)
                    n_q += len(new)
                    if len(rows) < 10:
                        break
                added += n_q
                log(f"[bing] {group} | {q}: +{n_q}")
    return added


def collect_youtube(budget: int, delay: float) -> int:
    key = youtube_key()
    if not key:
        log("[yt] brak YOUTUBE_API_KEY")
        return 0
    out = ML_DIR / "data/pool/youtube_candidates.jsonl"
    seen = {str(r["id"]) for r in read_jsonl(out)}
    headers = {"X-Goog-Api-Key": key}  # klucz w nagłówku, żeby nie trafił do logów z adresem URL
    used = added = 0
    # po kolei z każdej grupy, żeby limit nie skończył się na jednej klasie
    ordered = [(g, QUERIES[g][i]) for i in range(max(map(len, QUERIES.values()))) for g in YT_PRIORITY if i < len(QUERIES[g])]
    with httpx.Client(timeout=30, headers=headers) as http:
        for group, q in ordered:
            for length in ("short", "medium"):
                if used + 102 > budget:
                    log(f"[yt] budżet wyczerpany: {used} jednostek")
                    return added
                s = http.get(f"{YT_API}/search", params={"part": "snippet", "q": q, "type": "video", "maxResults": 50,
                                                         "regionCode": "PL", "relevanceLanguage": "pl",
                                                         "videoDuration": length})
                used += 100
                if s.status_code != 200:
                    reason = (s.json().get("error", {}).get("errors") or [{}])[0].get("reason", "?")
                    log(f"[yt] search HTTP {s.status_code}: {reason}; kończę")
                    return added
                ids = [i["id"]["videoId"] for i in s.json().get("items", []) if i["id"]["videoId"] not in seen]
                new = []
                if ids:
                    v = http.get(f"{YT_API}/videos", params={"part": "snippet,statistics,contentDetails", "id": ",".join(ids[:50])})
                    used += 1
                    v.raise_for_status()
                    for it in v.json().get("items", []):
                        sn, dur = it["snippet"], iso_seconds(it["contentDetails"].get("duration", ""))
                        lang = (sn.get("defaultAudioLanguage") or sn.get("defaultLanguage") or "pl").lower()
                        if not lang.startswith("pl") or not 20 <= dur <= 900:
                            continue
                        seen.add(it["id"])
                        new.append({"id": it["id"], "title": sn.get("title"), "channel": sn.get("channelTitle"),
                                    "channel_id": sn.get("channelId"), "uploader": sn.get("channelTitle"), "duration": dur,
                                    "description": sn.get("description"),
                                    "view_count": int(it.get("statistics", {}).get("viewCount") or 0),
                                    "live_status": None, "group": group, "query": q})
                    append_jsonl(out, new)
                added += len(new)
                log(f"[yt] {group} | {q} ({length}): +{len(new)} | jednostki {used}")
                time.sleep(delay)
    return added


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--yt-budget", type=int, default=4000)
    ap.add_argument("--bing-pages", type=int, default=5)
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--bing-delay", type=float, default=20.0)
    ap.add_argument("--only", choices=("all", "bing", "youtube"), default="all")
    args = ap.parse_args()
    bing = collect_bing(args.bing_pages, args.bing_delay) if args.only in ("all", "bing") else 0
    yt = collect_youtube(args.yt_budget, args.delay) if args.only in ("all", "youtube") else 0
    log(f"koniec: Bing +{bing} reklam, YouTube +{yt} kandydatów")


if __name__ == "__main__":
    main()
