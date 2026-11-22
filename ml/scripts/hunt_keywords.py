"""Polowanie na podejrzane reklamy: celowane hasła -> nowe wyniki z API -> ocena regułami (bez LLM) -> log haseł.

Źródła: Meta Ad Library (kolektor kolegi, Playwright), Microsoft Ad Library (bez klucza), YouTube Data API (klucz z .env).
Wyjście (poza gitem):
  ml/data/raw/scraper_live/hunt_<źródło>/records.jsonl  – nowe rekordy w formacie kolektora
  ml/data/skill/keyword_hits.json                         – skuteczność haseł (ile podejrzanych trafień)
  ml/data/skill/suspicious.jsonl                          – podejrzane rekordy z powodami

  python ml/scripts/hunt_keywords.py --sources meta,bing,youtube --yt-budget 3000
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml/src"))
sys.path.insert(0, str(ROOT / "scripts"))
from investwatch_ml import heuristics, indicators, knf  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
POC = ROOT / "scrapers/poc"
POC_PY = POC / ".venv/Scripts/python.exe"
LIVE = ROOT / "ml/data/raw/scraper_live"
SKILL = ROOT / "ml/data/skill"
YT_API = "https://www.googleapis.com/youtube/v3"
BING_API = "https://adlibrary.api.bingads.microsoft.com/api/v1/Ads"

KEYWORDS = {
    "scam": ["gwarantowany zysk", "zysk bez ryzyka", "bot inwestycyjny", "sztuczna inteligencja inwestuje",
             "zarabiaj na kryptowalutach", "pasywny dochód inwestycja", "inwestycja od 250 euro", "platforma inwestycyjna AI",
             "odzyskanie pieniędzy od brokera", "podwój swoje pieniądze", "dochód z inwestycji miesięcznie",
             "inwestycja w ropę", "akcje orlen inwestycja", "baltic pipe inwestycja"],
    "m3": ["sygnały forex", "sygnały krypto", "grupa inwestycyjna whatsapp", "grupa vip trading", "mentoring tradingowy",
           "konsultacje inwestycyjne", "zarządzanie kapitałem", "kopiuj transakcje", "typy giełdowe"],
    "push": ["akcje które warto kupić", "spółka która wystrzeli", "kryptowaluta 100x", "najlepsza inwestycja 2026"],
    "realestate": ["apartament inwestycyjny gwarantowany zysk", "inwestycja w nieruchomości zwrot", "flip mieszkania zysk"],
    "impersonation": ["xtb społeczność", "mbank inwestycje", "revolut inwestycje", "pko inwestycje", "giełda papierów wartościowych"],
}
BING_WORDS = ["gwarantowany", "sygnaly", "bot", "zarabiaj", "kryptowaluty", "pasywny", "mentoring", "apartament"]
KNOWN_BRANDS = re.compile(r"\b(xtb|mbank|revolut|pko|pekao|orlen|santander|ing|etoro|plus500|bossa|gpw|alior|millennium)\b", re.I)
CONTACT = re.compile(r"whatsapp|wa\.me|telegram|t\.me/|napisz (do nas|na priv|wiadomość)|zostaw (numer|telefon)|send message|wyślij wiadomość", re.I)
WARNING = re.compile(r"czerwon\w* flag|ostrzeg|ostrzeż|oszust|scam|uwaga na|nie daj się|jak rozpozna|piramid\w* finansow|naciąg|fałszyw|uważaj|pułapk|mit|mity", re.I)
INVEST = re.compile(r"inwest|krypto|bitcoin|token|forex|akcj[eiay]|giełd|trading|trader|portfel inwest|sygnał|lokowan\w* kapitał|stop[aęy] zwrotu|launchpad|staking|copy ?trad", re.I)


def log(m: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {m}", flush=True)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def known_urls() -> set[str]:
    urls = set()
    for f in glob.glob(str(ROOT / "data/export/*/records.jsonl")) + glob.glob(str(LIVE / "*/records.jsonl")):
        for line in open(f, encoding="utf-8"):
            if line.strip():
                urls.add(json.loads(line).get("source_url"))
    return urls


def assess(rec: dict) -> tuple[int, list[str]]:
    """Ocena regułami (bez LLM). Wynik to punkty i powody; >= 3 = podejrzane, do weryfikacji."""
    text = "\n".join(str(v) for v in rec["text"].values())
    author = rec.get("author") or ""
    if not INVEST.search(text):
        return 0, []
    pred = heuristics.predict(text)
    reasons, score = [], 0
    hits = [k for k in heuristics.SCAM_FLAGS if pred["flags"][k]["evidence"]]
    if hits:
        score += 2 * len(hits)
        reasons.append("sygnały: " + ", ".join(hits))
    if CONTACT.search(text):
        score += 2
        reasons.append("kontakt poza platformą")
    if author and KNOWN_BRANDS.search(author):
        status = knf.register().lookup(author)["status"]
        if status != "REGISTERED":
            score += 3
            reasons.append(f"nazwa marki w profilu „{author}”, brak w rejestrze KNF (możliwe podszywanie)")
    elif author:
        status = knf.register().lookup(author)["status"]
        if status != "REGISTERED" and re.search(r"zysk|zarab|dochód|zwrot", text, re.I):
            score += 1
            reasons.append("nieznany reklamodawca obiecuje zysk")
    if re.search(r"\d+\s*%.{0,25}(miesięcz|tygodni|dzien|dzienn|w miesiąc|w tydzień)|x\s?\d{2,}", text, re.I):
        score += 2
        reasons.append("wysoka stopa zwrotu w krótkim czasie")
    if pred["scamText"] >= 0.5:
        score += 1
    if re.search(r"(zysk|ryzyk|bot|zwrot|pewn)[^.!\n]{0,40}\?", text, re.I):  # pytanie w tytule = zwykle edukacja
        score -= 2
        reasons.append("teza postawiona jako pytanie")
    if WARNING.search(text):  # ostrzeżenie lub edukacja o oszustwach, nie oferta
        score -= 4
        reasons.append("wygląda na ostrzeżenie lub edukację")
    return score, reasons


def meta_search(q: str) -> list[dict]:
    from convert_fb_ads_web import parse_ad  # skrypt kolegi
    before = set(glob.glob(str(POC / "results/fb_ads.ad_library_web/*-docs.json")))
    subprocess.run([str(POC_PY), "-m", "registry", "fb_ads.ad_library_web", q], cwd=POC, capture_output=True, timeout=240,
                   env={**os.environ, "PYTHONUTF8": "1"})
    new = sorted(set(glob.glob(str(POC / "results/fb_ads.ad_library_web/*-docs.json"))) - before)
    out = []
    for f in new:
        for d in json.load(open(f, encoding="utf-8")):
            try:
                start, meta, body, title, desc, cta, domain = parse_ad("\n".join(s["text"] for s in d["text"]))
            except Exception:
                continue
            text = {k: v for k, v in (("ad_body", "\n".join(body)), ("title", title), ("link_description", desc), ("cta", cta)) if v}
            if text:
                out.append({"source": "meta_ad_library", "source_url": d["source_url"], "author": d["author"], "published_at": start,
                            "fetched_at": d["fetched_at"], "query_keywords": [q], "content_keywords": [], "text": text,
                            "sponsor": d.get("sponsor"), "links": [f"https://{domain.lower()}"] if domain else [],
                            "content_type": "ad", "source_meta": {**meta, "collector": "fb_ads.ad_library_web", "hunt": True}})
    return out


def bing_search(http: httpx.Client, q: str) -> list[dict]:
    out = []
    for page in range(3):
        for attempt in range(4):
            r = http.get(BING_API, params={"searchText": q, "top": 10, "skip": page * 10, "countryCodes": 151})
            if r.status_code != 429:
                break
            time.sleep(120 * (attempt + 1))
        if r.status_code != 200:
            break
        rows = r.json().get("value", [])
        for a in rows:
            text = {k: v.strip() for k, v in (("title", a.get("Title")), ("ad_body", a.get("Description"))) if isinstance(v, str) and v.strip()}
            out.append({"source": "microsoft_ad_library", "source_url": f"https://adlibrary.ads.microsoft.com/ad/{a.get('AdId')}",
                        "author": a.get("AdvertiserName"), "published_at": None, "fetched_at": now(), "query_keywords": [q],
                        "content_keywords": [], "text": text, "sponsor": a.get("AdvertiserName"),
                        "links": [u for u in (a.get("DestinationUrl"),) if u], "content_type": "ad",
                        "source_meta": {"ad_id": a.get("AdId"), "display_url": a.get("DisplayUrl"), "hunt": True}})
        time.sleep(20)
        if len(rows) < 10:
            break
    return out


def youtube_key() -> str | None:
    for env in (ROOT / ".env", ROOT / "ml/.env"):
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                if line.startswith("YOUTUBE_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"')
    return None


def youtube_search(http: httpx.Client, q: str) -> list[dict]:
    s = http.get(f"{YT_API}/search", params={"part": "snippet", "q": q, "type": "video", "maxResults": 25, "regionCode": "PL",
                                              "relevanceLanguage": "pl", "order": "date"})
    if s.status_code != 200:
        raise RuntimeError(f"YouTube search HTTP {s.status_code}")
    ids = [i["id"]["videoId"] for i in s.json().get("items", [])]
    if not ids:
        return []
    v = http.get(f"{YT_API}/videos", params={"part": "snippet,contentDetails,paidProductPlacementDetails", "id": ",".join(ids)})
    v.raise_for_status()
    out = []
    for it in v.json().get("items", []):
        sn = it["snippet"]
        out.append({"source": "youtube", "source_url": f"https://www.youtube.com/watch?v={it['id']}", "author": sn.get("channelTitle"),
                    "published_at": sn.get("publishedAt"), "fetched_at": now(), "query_keywords": [q], "content_keywords": [],
                    "text": {k: v for k, v in (("title", sn.get("title")), ("description", sn.get("description"))) if v},
                    "sponsor": None, "links": indicators.URL_RE.findall(sn.get("description") or "")[:20], "content_type": "video",
                    "source_meta": {"video_id": it["id"], "channel_id": sn.get("channelId"), "hunt": True,
                                    "paid": it.get("paidProductPlacementDetails", {}).get("hasPaidProductPlacement")}})
    return out


def rescore() -> None:
    sus, stats = [], {}
    hits_path = SKILL / "keyword_hits.json"
    old = json.loads(hits_path.read_text(encoding="utf-8")) if hits_path.exists() else {}
    for f in sorted(glob.glob(str(LIVE / "hunt_*/records.jsonl"))):
        source = Path(f).parent.name[5:]
        rows = [json.loads(l) for l in open(f, encoding="utf-8") if l.strip()]
        for r in rows:
            q = (r.get("query_keywords") or ["?"])[0]
            score, reasons = assess(r)
            r["source_meta"]["hunt_score"], r["source_meta"]["hunt_reasons"] = score, reasons
            k = stats.setdefault(q, {"group": old.get(q, {}).get("group", source), "runs": old.get(q, {}).get("runs", 1), "results": old.get(q, {}).get("results", 0),
                                     "new": 0, "suspicious": 0, "sources": {}, "examples": []})
            src = k["sources"].setdefault(source, {"new": 0, "suspicious": 0})
            k["new"] += 1; src["new"] += 1
            if score >= 3:
                k["suspicious"] += 1; src["suspicious"] += 1
                text = " ".join(" | ".join(str(v) for v in r["text"].values()).split())[:500]
                k["examples"] = (k["examples"] + [f"{r.get('author')}: {text[:120]}"])[:5]
                sus.append({"keyword": q, "group": k["group"], "source": source, "score": score, "reasons": reasons,
                            "author": r.get("author"), "url": r["source_url"], "text": text})
        Path(f).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    (SKILL / "suspicious.jsonl").write_text("".join(json.dumps(s, ensure_ascii=False) + "\n" for s in sus), encoding="utf-8")
    hits_path.write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"przeliczono: podejrzane {len(sus)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", default="meta,bing,youtube")
    ap.add_argument("--yt-budget", type=int, default=3000)
    ap.add_argument("--meta-delay", type=float, default=25)
    ap.add_argument("--rescore", action="store_true", help="tylko przelicz ocenę pobranych rekordów")
    args = ap.parse_args()
    if args.rescore:
        rescore()
        return
    sources = args.sources.split(",")
    SKILL.mkdir(parents=True, exist_ok=True)
    hits_path = SKILL / "keyword_hits.json"
    stats = json.loads(hits_path.read_text(encoding="utf-8")) if hits_path.exists() else {}
    seen = known_urls()
    yt_http = httpx.Client(timeout=30, headers={"X-Goog-Api-Key": youtube_key() or ""})
    bing_http = httpx.Client(timeout=30, headers={"User-Agent": "investwatch-research"})
    yt_used = 0

    def handle(source: str, group: str, q: str, recs: list[dict]) -> None:
        new = [r for r in recs if r["source_url"] not in seen]
        seen.update(r["source_url"] for r in new)
        sus = []
        for r in new:
            score, reasons = assess(r)
            r["source_meta"]["hunt_score"], r["source_meta"]["hunt_reasons"] = score, reasons
            if score >= 3:
                sus.append({"keyword": q, "group": group, "source": source, "score": score, "reasons": reasons,
                            "author": r.get("author"), "url": r["source_url"],
                            "text": " ".join(" | ".join(str(v) for v in r["text"].values()).split())[:500]})
        out = LIVE / f"hunt_{source}"
        out.mkdir(parents=True, exist_ok=True)
        with open(out / "records.jsonl", "a", encoding="utf-8") as f:
            f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in new)
        with open(SKILL / "suspicious.jsonl", "a", encoding="utf-8") as f:
            f.writelines(json.dumps(s, ensure_ascii=False) + "\n" for s in sus)
        k = stats.setdefault(q, {"group": group, "runs": 0, "results": 0, "new": 0, "suspicious": 0, "sources": {}, "examples": []})
        k["runs"] = k.get("runs", 0) + 1; k["results"] = k.get("results", 0) + len(recs); k["new"] += len(new); k["suspicious"] += len(sus)
        src = k["sources"].setdefault(source, {})
        for key in ("results", "new", "suspicious"):
            src.setdefault(key, 0)
            k.setdefault(key, 0)
        src["results"] += len(recs); src["new"] += len(new); src["suspicious"] += len(sus)
        k["examples"] = (k["examples"] + [f"{s['author']}: {s['text'][:120]}" for s in sus])[:5]
        k["last_run"] = now()
        hits_path.write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
        log(f"[{source}] {group} | {q}: wyniki {len(recs)}, nowe {len(new)}, PODEJRZANE {len(sus)}")

    for group, words in KEYWORDS.items():
        for q in words:
            if "youtube" in sources and yt_used + 101 <= args.yt_budget:
                try:
                    handle("youtube", group, q, youtube_search(yt_http, q))
                    time.sleep(4)
                    yt_used += 101
                except Exception as e:
                    log(f"[youtube] {q}: {e}; wyłączam YouTube")
                    sources = [s for s in sources if s != "youtube"]
            if "meta" in sources:
                try:
                    handle("meta", group, q, meta_search(q))
                except Exception as e:
                    log(f"[meta] {q}: {type(e).__name__}: {str(e)[:100]}")
                time.sleep(args.meta_delay)
    if "bing" in sources:
        for q in BING_WORDS:
            handle("bing", "bing", q, bing_search(bing_http, q))
    top = sorted(stats.items(), key=lambda x: -x[1]["suspicious"])
    log("najskuteczniejsze hasła: " + "; ".join(f"{q} ({v['suspicious']})" for q, v in top[:10]))


if __name__ == "__main__":
    main()
