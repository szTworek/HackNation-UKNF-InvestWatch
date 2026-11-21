"""Zbieranie polskich filmów z YouTube (opis + transkrypcja) do puli danych.

Wyszukuje filmy dla zestawu zapytań (inwestycje, promocje, trading, krypto, „szybki zarobek”, doradztwo,
ostrzeżenia, finanse ogólne, treści niefinansowe), pobiera polską transkrypcję i pełny opis (linki afiliacyjne,
#reklama). Wynik: data/pool/youtube.jsonl (format Doc). Wznawialne.

YouTube szybko blokuje IP przy zbyt wielu zapytaniach o transkrypcje (IpBlocked / 429 / „confirm you're not a bot”).
Dlatego: jeden wątek, przerwy między filmami, a przy blokadzie wykładnicze czekanie i ponowienie tego samego filmu
(zablokowane filmy NIE trafiają na listę pominiętych). Wyniki wyszukiwania są cache'owane.

  uv run python scripts/collect_youtube.py --per-query 15 --delay 4
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    IpBlocked,
    NoTranscriptFound,
    RequestBlocked,
    TranscriptsDisabled,
    VideoUnavailable,
)

from investwatch_ml.schema import Doc, append_jsonl, existing_ids, read_jsonl
from investwatch_ml.text import normalize

ML_DIR = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

QUERIES: dict[str, list[str]] = {
    "edu": [
        "jak zacząć inwestować", "inwestowanie dla początkujących", "ETF dla początkujących",
        "IKE IKZE jak inwestować", "obligacje skarbowe czy warto", "dywidendy spółki GPW",
        "fundusze inwestycyjne czy warto", "analiza techniczna giełda",
    ],
    "promo": [
        "konto maklerskie który broker wybrać", "najlepszy broker do inwestowania", "aplikacja inwestycyjna recenzja",
        "darmowa akcja na start kod polecający", "giełda kryptowalut jak założyć konto", "jak kupić bitcoina krok po kroku",
    ],
    "trading": [
        "forex zarabianie", "trading na forex strategia", "jak zarabiać na tradingu", "CFD złoto trading",
        "day trading Polska",
    ],
    "crypto": ["kryptowaluty w co zainwestować", "altcoiny które zrobią 100x", "bitcoin prognoza", "memecoin zarobek"],
    "scamish": [
        "zarabianie w internecie bez wysiłku", "pasywny dochód 10000 zł miesięcznie", "bot tradingowy AI zarabia",
        "inwestycja gwarantowany zysk", "jak szybko zarobić dużo pieniędzy", "sygnały tradingowe telegram",
    ],
    "advisory": [
        "doradca inwestycyjny konsultacje", "zarządzanie majątkiem family office", "niezależny doradca finansowy",
        "mentoring tradingowy kurs",
    ],
    "warning": ["oszustwa inwestycyjne jak rozpoznać", "fałszywe reklamy inwestycyjne", "oszustwo na kryptowaluty"],
    "fin_other": [
        "kredyt hipoteczny porady", "najlepsze konto oszczędnościowe", "jak oszczędzać pieniądze", "jak rozliczyć PIT",
    ],
    "non_fin": ["przepis na szybki obiad", "vlog z podróży po Polsce", "recenzja telefonu", "trening w domu",
                "recenzja gry"],
    "shorts": ["inwestowanie #shorts", "kryptowaluty #shorts", "zarabianie pieniędzy #shorts", "giełda #shorts",
               "trading #shorts"],
}

URL_RE = re.compile(r"https?://[^\s)\]>\"']+")
YDL_BASE = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "ignore_no_formats_error": True,
    "http_headers": {"Accept-Language": "pl-PL,pl;q=0.9"},  # oryginalne tytuły zamiast tłumaczeń
}
BLOCK_MARKERS = ("not a bot", "429", "Too Many Requests", "blocking requests", "IpBlocked", "RequestBlocked")


class Blocked(Exception):
    pass


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def search(query: str, n: int) -> list[dict]:
    with yt_dlp.YoutubeDL({**YDL_BASE, "extract_flat": "in_playlist"}) as ydl:
        res = ydl.extract_info(f"ytsearch{n}:{query}", download=False)
    keep = ("id", "title", "channel", "channel_id", "uploader", "duration", "description", "view_count", "live_status")
    return [{k: e.get(k) for k in keep} for e in (res.get("entries") or [])
            if e and e.get("id") and e.get("live_status") != "is_live"]


def load_candidates(path: Path, groups: list[str], per_query: int, refresh: bool) -> list[dict]:
    cached = list(read_jsonl(path))
    done_queries = {c["query"] for c in cached}
    if refresh:
        cached, done_queries = [], set()
    for g in groups:
        for q in QUERIES[g]:
            if q in done_queries:
                continue
            try:
                ents = search(q, per_query)
            except Exception as ex:
                log(f"[search] {q!r}: BŁĄD {str(ex)[:150]}")
                continue
            rows = [{**e, "group": g, "query": q} for e in ents]
            append_jsonl(path, rows)
            cached.extend(rows)
            log(f"[search] {g:9s} {q!r}: {len(ents)} wyników")
            time.sleep(1.5)
    seen, out = set(), []
    for c in cached:
        if c["id"] not in seen and c["group"] in groups:
            seen.add(c["id"])
            out.append(c)
    return out


def transcript(api: YouTubeTranscriptApi, video_id: str) -> tuple[str, bool] | None:
    """(tekst, czy auto-generowana) | None gdy brak PL. Rzuca Blocked przy blokadzie IP."""
    try:
        tr = api.fetch(video_id, languages=["pl"])
    except (IpBlocked, RequestBlocked) as ex:
        raise Blocked(type(ex).__name__) from ex
    except (NoTranscriptFound, TranscriptsDisabled, VideoUnavailable):
        return None
    except Exception as ex:
        if any(m in str(ex) for m in BLOCK_MARKERS):
            raise Blocked(str(ex)[:100]) from ex
        return None
    text = " ".join(s["text"].replace("\n", " ") for s in tr.to_raw_data())
    return text, bool(tr.is_generated)


def full_meta(ydl: yt_dlp.YoutubeDL, video_id: str) -> dict | None:
    try:
        return ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False, process=False)
    except Exception:
        return None  # przy blokadzie zostaje opis z wyników wyszukiwania


def build_doc(entry: dict, tr: tuple[str, bool], meta: dict | None, args) -> Doc:
    vid = entry["id"]
    tr_text, generated = tr
    description = (meta or {}).get("description") or entry.get("description") or ""
    title = (meta or {}).get("title") or entry.get("title") or ""
    desc = normalize(description)[: args.max_desc_chars]
    tr_norm = normalize(tr_text)
    full_len = len(tr_norm)
    tr_norm = tr_norm[: args.max_transcript_chars]
    body = f"{desc}\n\n[TRANSKRYPCJA]\n{tr_norm}" if desc else tr_norm
    duration = (meta or {}).get("duration") or entry.get("duration")
    upload = (meta or {}).get("upload_date")
    return Doc(
        id=f"yt:{vid}", source="youtube", platform="youtube", kind="transcript",
        url=f"https://www.youtube.com/watch?v={vid}",
        author=(meta or {}).get("channel") or entry.get("channel") or entry.get("uploader"),
        title=title, text=body,
        published_at=f"{upload[:4]}-{upload[4:6]}-{upload[6:]}" if upload and len(upload) == 8 else None,
        outbound_links=sorted(set(URL_RE.findall(description)))[:50],
        meta={
            "query": entry.get("query"), "query_group": entry.get("group"), "channel_id": entry.get("channel_id"),
            "duration": duration, "is_short": bool(duration and duration <= 70),
            "views": (meta or {}).get("view_count") or entry.get("view_count"),
            "transcript_generated": generated, "transcript_full_chars": full_len,
            "description_source": "full" if meta else "search_snippet",
        },
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-query", type=int, default=15)
    ap.add_argument("--out", default="data/pool/youtube.jsonl")
    ap.add_argument("--delay", type=float, default=4.0, help="sekundy przerwy między filmami")
    ap.add_argument("--max-transcript-chars", type=int, default=9000)
    ap.add_argument("--max-desc-chars", type=int, default=2000)
    ap.add_argument("--no-full-meta", dest="full_meta", action="store_false")
    ap.add_argument("--groups", default=None, help="np. scamish,promo (domyślnie wszystkie)")
    ap.add_argument("--refresh-search", action="store_true")
    ap.add_argument("--max-block-wait-min", type=int, default=180, help="po tylu min. blokady kończymy")
    args = ap.parse_args()

    out = ML_DIR / args.out
    skip_path = out.with_name("youtube_skipped.jsonl")
    cand_path = out.with_name("youtube_candidates.jsonl")
    done = existing_ids(out) | existing_ids(skip_path)
    groups = args.groups.split(",") if args.groups else list(QUERIES)
    cands = [c for c in load_candidates(cand_path, groups, args.per_query, args.refresh_search)
             if f"yt:{c['id']}" not in done]
    # przeplot grup, żeby przy przerwaniu mieć po trochu z każdej
    by_group: dict[str, list[dict]] = {}
    for c in cands:
        by_group.setdefault(c["group"], []).append(c)
    order = []
    while any(by_group.values()):
        for g in list(by_group):
            if by_group[g]:
                order.append(by_group[g].pop(0))
    log(f"[collect] do pobrania: {len(order)} filmów (już mam {len(done)})")

    api = YouTubeTranscriptApi()
    ydl = yt_dlp.YoutubeDL(YDL_BASE)
    n_ok = n_skip = 0
    blocked_total = 0.0
    backoff = 10 * 60
    i = 0
    while i < len(order):
        e = order[i]
        try:
            tr = transcript(api, e["id"])
        except Blocked as b:
            if blocked_total / 60 >= args.max_block_wait_min:
                log(f"[collect] blokada trwa > {args.max_block_wait_min} min – kończę (wznowisz później tym samym poleceniem)")
                break
            log(f"[collect] YouTube blokuje ({b}); czekam {backoff // 60} min i ponawiam")
            time.sleep(backoff)
            blocked_total += backoff
            backoff = min(backoff * 2, 60 * 60)
            api = YouTubeTranscriptApi()
            continue
        backoff = 10 * 60
        if tr is None:
            append_jsonl(skip_path, [{"id": f"yt:{e['id']}", "reason": "brak PL transkrypcji"}])
            n_skip += 1
        else:
            meta = full_meta(ydl, e["id"]) if args.full_meta else None
            append_jsonl(out, [build_doc(e, tr, meta, args).model_dump()])
            n_ok += 1
        i += 1
        if i % 20 == 0:
            log(f"[collect] {i}/{len(order)} | zapisane {n_ok}, bez PL {n_skip}")
        time.sleep(args.delay)
    total = sum(1 for _ in read_jsonl(out))
    log(f"[collect] koniec: +{n_ok} filmów, w puli {total} -> {out}")


if __name__ == "__main__":
    main()
