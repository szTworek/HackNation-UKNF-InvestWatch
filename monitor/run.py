"""Website change monitor: fetch pages.json, append PageSnapshot/PageChange to data/monitor/*.jsonl.

  python -m monitor.run                      # one full run
  python -m monitor.run --entity xtb         # only one entity
  python -m monitor.run --every 6h           # loop forever (s/m/h/d)
"""
import argparse
import hashlib
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

from monitor.diff import compare
from monitor.extract import normalize, risk_warning, sha256
from monitor.fetch import fetch_page, fetch_robots

DATA = Path(__file__).resolve().parents[1] / "data" / "monitor"
PAGES, SNAPSHOTS, CHANGES, RUNS = (DATA / n for n in ("pages.json", "snapshots.jsonl", "changes.jsonl", "runs.jsonl"))


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def append_jsonl(path, rows):
    with path.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def last_snapshots():
    last = {}
    for s in read_jsonl(SNAPSHOTS):
        if s["page_id"] not in last or s["fetched_at"] >= last[s["page_id"]]["fetched_at"]:
            last[s["page_id"]] = s
    return last


def snapshot(page, res, fetched_at):
    lines = normalize(res.get("lines") or [])
    text = "\n".join(lines)
    return {"id": "snp_" + hashlib.sha1(f"{page['page_id']}|{fetched_at}".encode()).hexdigest()[:12],
            "page_id": page["page_id"], "entity_id": page["entity_id"], "url": page["url"], "fetched_at": fetched_at,
            "text_sha256": sha256(text), "text": text,
            "risk_warning": risk_warning(lines, res.get("warn"), res.get("vh")) if lines else
            {"present": False, "cfd_loss_pct": None, "text": None, "above_fold": None},
            "http_status": res.get("http_status"), "final_url": res.get("final_url"), "mock": False}


def interleave(pages):
    """Round-robin across entities so consecutive requests hit different hosts."""
    by = {}
    for p in pages:
        by.setdefault(p["entity_id"], []).append(p)
    out, queues = [], list(by.values())
    while any(queues):
        for q in queues:
            if q:
                out.append(q.pop(0))
    return out


def run_once(entity=None):
    t0 = time.time()
    pages = [p for p in json.loads(PAGES.read_text(encoding="utf-8")) if not entity or p["entity_id"] == entity]
    last = last_snapshots()
    snaps, changes, skipped, robots = [], [], [], {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for n, page in enumerate(interleave(pages)):
            if n:
                time.sleep(random.uniform(1.5, 3))
            if fetch_robots(browser, page["url"], robots) is False:
                skipped.append({"page_id": page["page_id"], "reason": "robots_disallow"})
                continue
            res = fetch_page(browser, page["url"])
            if res.get("blocked") or res.get("error") or (not res.get("lines") and res.get("http_status") not in (404, 410)):
                skipped.append({"page_id": page["page_id"], "reason": "blocked" if res.get("blocked") else "error",
                                "detail": res.get("blocked") or res.get("error") or "empty page"})
                print(f"  skip {page['page_id']}: {skipped[-1]['reason']}", flush=True)
                continue
            fetched_at = now()
            s = snapshot(page, res, fetched_at)
            snaps.append(s)
            prev = last.get(page["page_id"])
            c = compare(prev, s, fetched_at, mock=bool(prev.get("mock"))) if prev else None
            if c:
                changes.append(c)
            rw = s["risk_warning"]
            print(f"  ok {page['page_id']}: {len(s['text'])} chars, warning={rw['present']} pct={rw['cfd_loss_pct']} "
                  f"fold={rw['above_fold']}{' CHANGE ' + c['summary'] if c else ''}", flush=True)
        browser.close()
    append_jsonl(SNAPSHOTS, snaps)
    append_jsonl(CHANGES, changes)
    summary = {"run_at": now(), "pages": len(pages), "snapshots": len(snaps), "changes": len(changes),
               "skipped": skipped, "duration_s": round(time.time() - t0, 1)}
    append_jsonl(RUNS, [summary])
    print(json.dumps({k: v for k, v in summary.items() if k != "skipped"}), f"skipped={len(skipped)}", flush=True)
    return summary


def parse_every(s):
    return int(s[:-1]) * {"s": 1, "m": 60, "h": 3600, "d": 86400}[s[-1]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--entity")
    ap.add_argument("--every", help="repeat interval, e.g. 6h")
    a = ap.parse_args()
    while True:
        run_once(a.entity)
        if not a.every:
            break
        time.sleep(parse_every(a.every))


if __name__ == "__main__":
    main()
