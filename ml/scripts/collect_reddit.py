"""Zbieranie postów i komentarzy z polskich subredditów (publiczne archiwum Arctic Shift) do puli danych.

Wynik: data/pool/reddit.jsonl (format Doc). Wznawialne (pomija znane id).

  uv run python scripts/collect_reddit.py
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import httpx

from investwatch_ml.schema import Doc, append_jsonl, existing_ids
from investwatch_ml.text import normalize

ML_DIR = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
API = "https://arctic-shift.photon-reddit.com/api"
URL_RE = re.compile(r"https?://[^\s)\]>\"']+")

# subreddit -> (limit postów, limit komentarzy)
SUBS: dict[str, tuple[int, int]] = {
    "inwestowanie": (2500, 1500),
    "gielda": (800, 400),
    "PolskaGielda": (400, 0),
    "bitcoinpl": (600, 200),
    "kryptowaluty": (600, 200),
    "Polska": (600, 300),  # głównie negatywy (treści niefinansowe)
}


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def fetch(client: httpx.Client, kind: str, sub: str, before: int | None) -> list[dict]:
    params = {"subreddit": sub, "limit": 100, "sort": "desc"}
    if before:
        params["before"] = before
    for attempt in range(5):
        try:
            r = client.get(f"{API}/{kind}/search", params=params)
            if r.status_code == 200:
                return r.json().get("data") or []
            log(f"[reddit] {sub} {kind}: HTTP {r.status_code} {r.text[:120]}")
        except Exception as ex:
            log(f"[reddit] {sub} {kind}: {type(ex).__name__}")
        time.sleep(3 * (attempt + 1))
    return []


def post_doc(p: dict) -> Doc | None:
    body = p.get("selftext") or ""
    if body in ("[removed]", "[deleted]") or p.get("author") in ("AutoModerator", "[deleted]"):
        body = ""
    title = normalize(p.get("title") or "")
    body = normalize(body)
    if len(title) + len(body) < 40:
        return None
    links = set(URL_RE.findall(body))
    url = p.get("url") or ""
    if url and "reddit.com" not in url and "redd.it" not in url:
        links.add(url)
    return Doc(
        id=f"rd:t3_{p['id']}", source="reddit", platform="reddit", kind="post",
        url=f"https://www.reddit.com{p.get('permalink', '')}", author=f"u/{p.get('author')}",
        title=title, text=body,
        published_at=time.strftime("%Y-%m-%d", time.gmtime(p.get("created_utc", 0))),
        outbound_links=sorted(links)[:30],
        meta={"subreddit": p.get("subreddit"), "score": p.get("score"), "flair": p.get("link_flair_text"),
              "num_comments": p.get("num_comments")},
    )


def comment_doc(c: dict) -> Doc | None:
    body = normalize(c.get("body") or "")
    if body in ("[removed]", "[deleted]") or len(body) < 80 or c.get("author") in ("AutoModerator", "[deleted]"):
        return None
    return Doc(
        id=f"rd:t1_{c['id']}", source="reddit", platform="reddit", kind="comment",
        url=f"https://www.reddit.com{c.get('permalink', '')}" if c.get("permalink") else None,
        author=f"u/{c.get('author')}", text=body,
        published_at=time.strftime("%Y-%m-%d", time.gmtime(c.get("created_utc", 0))),
        outbound_links=sorted(set(URL_RE.findall(body)))[:30],
        meta={"subreddit": c.get("subreddit"), "score": c.get("score"), "link_id": c.get("link_id")},
    )


def collect(client, out: Path, done: set[str], sub: str, kind: str, limit: int) -> int:
    if limit <= 0:
        return 0
    have = sum(1 for d in done if d.startswith("rd:t3_" if kind == "posts" else "rd:t1_"))  # przybliżenie
    n, before, empty_pages = 0, None, 0
    while n < limit:
        rows = fetch(client, kind, sub, before)
        if not rows:
            break
        before = min(int(r.get("created_utc", 0)) for r in rows)
        docs = []
        for r in rows:
            d = post_doc(r) if kind == "posts" else comment_doc(r)
            if d and d.id not in done:
                done.add(d.id)
                docs.append(d.model_dump())
        if docs:
            append_jsonl(out, docs)
            n += len(docs)
            empty_pages = 0
        else:
            empty_pages += 1
            if empty_pages >= 5:
                break
        time.sleep(1.0)
    log(f"[reddit] r/{sub} {kind}: +{n} (w puli wcześniej ok. {have})")
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/pool/reddit.jsonl")
    ap.add_argument("--scale", type=float, default=1.0, help="mnożnik limitów")
    args = ap.parse_args()
    out = ML_DIR / args.out
    done = existing_ids(out)
    client = httpx.Client(timeout=60, headers={"User-Agent": "investwatch-research/0.1"})
    total = 0
    for sub, (lp, lc) in SUBS.items():
        total += collect(client, out, done, sub, "posts", int(lp * args.scale))
        total += collect(client, out, done, sub, "comments", int(lc * args.scale))
    log(f"[reddit] koniec: +{total} dokumentów -> {out}")


if __name__ == "__main__":
    main()
