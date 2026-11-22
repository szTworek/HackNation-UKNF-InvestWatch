"""Realne strony oszustw inwestycyjnych: domeny z listy ostrzeżeń CERT Polska → archiwalne kopie z Wayback Machine.

Nie odwiedzamy żywych stron scamowych – pobieramy wyłącznie zarchiwizowany HTML z web.archive.org (bez JS).
Domeny filtrujemy słowami kluczowymi typowymi dla fałszywych inwestycji (krypto, AI, giełda, marki energetyczne...),
odrzucając typowy phishing paczkowy / marketplace. Wynik: data/pool/cert_wayback.jsonl (format Doc). Wznawialne.

  uv run python scripts/collect_scam_landings.py --max-domains 1500
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from langdetect import DetectorFactory, detect

from investwatch_ml.schema import Doc, append_jsonl, existing_ids
from investwatch_ml.text import normalize

ML_DIR = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
DetectorFactory.seed = 0

CERT_URL = "https://hole.cert.pl/domains/v2/domains.json"
INVEST_RE = re.compile(
    r"invest|inwest|crypto|krypto|bitcoin|btc|coin|trade|trading|trader|profit|zysk|capital|kapital|financ|finans|"
    r"forex|gpw|akcj|dochod|zarob|wealth|fundusz|orlen|pge|lotos|pkn|baltic|energ|petro|quantum|immediate|"
    r"exchange|yield|stock|broker|income|millionaire|milioner|pasyw|gielda|gielda|bogac|dywidend|obligac|"
    r"ai-?trad|bot-?trad|tokeny|token|staking|lokat"
)
PHISH_RE = re.compile(
    r"olx|vinted|allegro|inpost|dpd|dhl|poczta|pocztex|gls|fedex|ups|orlen-paczka|paczk|przesyl|dostaw|"
    r"blik|mbank|pkobp|ipko|santander|pekao|ing-|millennium|login|logowanie|verify|weryfik|oferta|offerta|"
    r"zamow|zamovien|order|payment|platnosc|oplata|facebook|instagram|whatsapp|netflix|mandat|epuap|gov|"
    r"pge-oplata|tauron|energa-oplat|faktur"
)
PL_RE = re.compile(r"\.pl$|-pl|pl-|polsk|inwest|zysk|zarob|dochod|bogac|kapital|finans|orlen|pge|lotos|pkn|"
                   r"gielda|akcje|lokat|oszczed|emerytur|polska|warszaw|krakow|zloty|zlot")
WB_AVAIL = "https://archive.org/wayback/available"
WB_RAW = "https://web.archive.org/web/{ts}id_/{url}"


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def load_cert(cache: Path) -> list[dict]:
    if not cache.exists() or time.time() - cache.stat().st_mtime > 6 * 3600:
        log("[cert] pobieram listę domen CERT Polska...")
        r = httpx.get(CERT_URL, timeout=120)
        r.raise_for_status()
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(r.content)
    return json.loads(cache.read_text(encoding="utf-8"))


def candidate_domains(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        d = (r.get("DomainAddress") or "").lower().strip()
        if not d or PHISH_RE.search(d) or not INVEST_RE.search(d):
            continue
        out.append({"domain": d, "insert": r.get("InsertDate"), "deleted": r.get("DeleteDate"),
                    "cert_id": r.get("RegisterPositionId")})
    # pomijamy najświeższe (Wayback jeszcze ich nie ma), reszta w losowej kolejności
    cutoff = time.strftime("%Y-%m-%d", time.gmtime(time.time() - 14 * 86400))
    out = [x for x in out if (x["insert"] or "") < cutoff]
    random.Random(42).shuffle(out)
    # najpierw domeny z polskimi słowami / TLD – reszta to głównie kampanie na inne kraje
    out.sort(key=lambda x: 0 if PL_RE.search(x["domain"]) else 1)
    return out


_local = threading.local()


def client() -> httpx.Client:
    c = getattr(_local, "c", None)
    if c is None:
        c = httpx.Client(timeout=45, follow_redirects=True,
                         headers={"User-Agent": "investwatch-research/0.1 (academic hackathon)"})
        _local.c = c
    return c


def get(url: str, params: dict | None = None) -> httpx.Response | None:
    for attempt in range(4):
        try:
            r = client().get(url, params=params)
            if r.status_code in (429, 503):
                time.sleep(15 * (attempt + 1))
                continue
            return r
        except httpx.HTTPError:
            time.sleep(5 * (attempt + 1))
    return None


def snapshots(domain: str, insert_date: str | None) -> list[tuple[str, str]]:
    """Najbliższa kopia z Wayback względem daty wpisu na listę CERT (później strona bywa już wyłączona)."""
    params = {"url": domain}
    if insert_date:
        params["timestamp"] = insert_date[:10].replace("-", "")
    r = get(WB_AVAIL, params)
    if r is None or r.status_code != 200:
        return []
    try:
        snap = r.json().get("archived_snapshots", {}).get("closest")
    except ValueError:
        return []
    if not snap or str(snap.get("status")) != "200":
        return []
    return [(snap["timestamp"], f"http://{domain}/")]


def html_to_doc(html: str, page_url: str, meta: dict) -> tuple[str, str, list[str]]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "iframe", "template"]):
        tag.decompose()
    title = normalize(soup.title.get_text(" ")) if soup.title else ""
    text = normalize(soup.get_text("\n"))
    links = set()
    host = urlparse(page_url).netloc
    for a in soup.find_all("a", href=True):
        href = urljoin(page_url, a["href"])
        if href.startswith("http") and "web.archive.org" not in href and urlparse(href).netloc != host:
            links.add(href)
    return title, text, sorted(links)[:30]


def process(c: dict, args) -> list[Doc]:
    docs = []
    for ts, url in snapshots(c["domain"], c["insert"]):
        r = get(WB_RAW.format(ts=ts, url=url))
        if r is None or r.status_code != 200 or "html" not in r.headers.get("content-type", "html"):
            continue
        title, text, links = html_to_doc(r.text, url, c)
        if len(text) < args.min_chars:
            continue
        try:
            lang = detect(text[:2000])
        except Exception:
            lang = "?"
        if lang != "pl":
            continue
        docs.append(Doc(
            id=f"cert:{c['domain']}:{ts}", source="cert_wayback", platform="web", kind="page", url=url,
            author=c["domain"], title=title[:300], text=text[: args.max_chars],
            published_at=f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}", outbound_links=links,
            meta={"domain": c["domain"], "cert_insert": c["insert"], "cert_deleted": c["deleted"],
                  "cert_id": c["cert_id"], "wayback_ts": ts, "weak_label": "cert_listed"},
        ))
        time.sleep(args.delay)
    return docs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/pool/cert_wayback.jsonl")
    ap.add_argument("--max-domains", type=int, default=1500)
    ap.add_argument("--snapshots-per-domain", type=int, default=2)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--min-chars", type=int, default=200)
    ap.add_argument("--max-chars", type=int, default=9000)
    args = ap.parse_args()

    out = ML_DIR / args.out
    checked_path = out.with_name("cert_wayback_checked.jsonl")
    checked = existing_ids(checked_path, key="domain")
    rows = load_cert(ML_DIR / "data/raw/cert_domains.json")
    cands = candidate_domains(rows)
    log(f"[cert] domen na liście: {len(rows)}, inwestycyjnych (heurystyka): {len(cands)}, sprawdzonych wcześniej: {len(checked)}")
    todo = [c for c in cands if c["domain"] not in checked][: args.max_domains]
    log(f"[cert] sprawdzam {len(todo)} domen w Wayback Machine")
    n_docs = n_hit = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(process, c, args): c for c in todo}
        for i, fut in enumerate(as_completed(futs), start=1):
            c = futs[fut]
            try:
                docs = fut.result()
            except Exception as e:
                docs = []
                log(f"[cert] {c['domain']}: {type(e).__name__}")
            if docs:
                n_hit += 1
                n_docs += len(docs)
                append_jsonl(out, [d.model_dump() for d in docs])
            append_jsonl(checked_path, [{"domain": c["domain"], "docs": len(docs)}])
            if i % 25 == 0 or i == len(futs):
                log(f"[cert] {i}/{len(futs)} domen | z archiwum PL: {n_hit} | stron: {n_docs} | "
                    f"{i / (time.time() - t0) * 60:.0f} domen/min")
    log(f"[cert] koniec: +{n_docs} stron z {n_hit} domen -> {out}")


if __name__ == "__main__":
    main()
