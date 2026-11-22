"""Loader: repo data -> Postgres (compose service `loader`, one-shot, idempotent).

1. migrations db/migrations/*.sql,
2. KNF registry -> knf_entities,
3. PoC entity groups (db/linking.py) -> entities; collector records (ml/scripts/build_findings.py:
   data/export/*/records.jsonl) -> items + item_entities; website monitor data/monitor/* -> monitored_pages,
   page_snapshots, page_changes. Only collected data: rows flagged `mock` (monitor/seed_demo.py) are skipped,
4. records not yet analysed go
   to ai-service /ingest in batches and in-scope results -> findings (statuses and history are kept).
   With an LLM backend at most LOADER_LLM_LIMIT records per run (the rest waits for the next run); records the LLM
   did not score (e.g. 429) stay pending instead of being stored with the keyword baseline,
5. media_objects from data/media and data/monitor/screens (files are copied to MinIO by the `minio-init` service).

Run: python db/load.py [--ai-url http://ai-service:8000]
"""
import argparse
import json
import os
import sys
import time
import urllib.error
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from psycopg.types.json import Jsonb

APP = Path(__file__).resolve().parents[1]
for extra in (APP / "ml/scripts",):
    sys.path.insert(0, str(extra))

import build_findings as bf  # noqa: E402
import store  # noqa: E402

DATA = APP / "data"
KNF_ML = APP / "ml/src/investwatch_ml/knf_register.json"
LLM_LIMIT = int(os.environ.get("LOADER_LLM_LIMIT", "100"))
LLM_BATCH = int(os.environ.get("LOADER_LLM_BATCH", "8"))
KNF_FULL = Path(os.environ.get("KNF_FILE", APP.parent / "data" / "knf_entities.json"))
LIST_CATEGORY = {"BROKERAGE_HOUSE": "domy_maklerskie", "BANK": "banki_maklerskie", "FOREIGN_BRANCH": "zagraniczne_oddzialy",
                 "CROSS_BORDER": "zagraniczne_bez_oddzialu"}


def log(msg: str) -> None:
    print(f"[loader] {msg}", flush=True)


def registry() -> list[dict]:
    """Same merge as before in frontend/mock-server/build-entities.ts: full KNF list when present, else the ml register."""
    ml = json.loads(KNF_ML.read_text(encoding="utf-8"))["entities"]
    if KNF_FULL.exists():
        by_name = {r["name"]: r for r in ml}
        out = []
        for r in json.loads(KNF_FULL.read_text(encoding="utf-8")):
            m = by_name.get(r["name"], {})
            out.append({"name": r["name"], "aliases": r.get("aliases") or m.get("aliases") or [], "category": r.get("category"),
                        "country": r.get("country"), "supervisor": m.get("supervisor"),
                        "registered_at": (r.get("details") or {}).get("Data zezwolenia") or m.get("registeredAt"),
                        "address": r.get("address"), "source_url": r.get("source_url")})
        return out
    return [{"name": r["name"], "aliases": r.get("aliases") or [],
             "category": LIST_CATEGORY.get(next((x for x in r.get("lists") or [] if x != "CROSS_BORDER"), "CROSS_BORDER"),
                                           "zagraniczne_bez_oddzialu"),
             "country": r.get("country"), "supervisor": r.get("supervisor"), "registered_at": r.get("registeredAt"),
             "address": None, "source_url": None} for r in ml]


def load_registry(conn) -> int:
    rows = registry()
    with conn.cursor() as cur:
        cur.execute("delete from knf_entities")
        cur.executemany("insert into knf_entities values (%(name)s, %(aliases)s, %(category)s, %(country)s, %(supervisor)s, "
                        "%(registered_at)s, %(address)s, %(source_url)s) on conflict (name) do nothing", rows)
    return len(rows)


def screen_key(path: str) -> str:
    return path.replace("\\", "/").rsplit("/", 1)[-1]


def jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def load_entities(conn, records: list[dict]) -> tuple[dict[str, str], Counter]:
    """Entities, items with their entity links and monitor data. Returns {source_url: item id}."""
    from linking import GROUPS, HANDLES

    n: Counter = Counter()
    mon = DATA / "monitor"
    pages = json.loads((mon / "pages.json").read_text(encoding="utf-8")) if (mon / "pages.json").exists() else []
    all_snapshots, all_changes = jsonl(mon / "snapshots.jsonl"), jsonl(mon / "changes.jsonl")
    snapshots = [x for x in all_snapshots if not x.get("mock")]
    changes = [x for x in all_changes if not x.get("mock")]
    with conn.cursor() as cur:
        for table in ("item_entities", "page_changes", "page_snapshots", "monitored_pages", "entities"):
            cur.execute(f"delete from {table}")  # noqa: S608 - fixed table names
        for eid, g in GROUPS.items():
            cur.execute("insert into entities values (%s, %s, %s, %s, %s)",
                        (eid, g["name"], g["registry"], g["domains"], Jsonb(HANDLES.get(eid, {}))))
        ids = {}
        for rec in records:
            ids[rec["source_url"]] = iid = store.upsert_item(cur, rec, "export")
            n["itemLinks"] += store.link_item(cur, iid, rec)
        for p in pages:
            cur.execute("insert into monitored_pages values (%s, %s, %s, %s) on conflict do nothing",
                        (p["page_id"], p["entity_id"], p["url"], p.get("label")))
        page_ids = {p["page_id"] for p in pages}
        for x in snapshots:
            if x["page_id"] not in page_ids:
                continue
            shots = {vp: screen_key(path) for vp, path in (x.get("screenshots") or {}).items()}
            cur.execute("insert into page_snapshots values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) on conflict do nothing",
                        (x["id"], x["page_id"], x.get("entity_id"), x.get("url"), store.ts(x.get("fetched_at")), x.get("text_sha256"),
                         x.get("text"), Jsonb(x.get("risk_warning")), Jsonb(shots) if shots else None,
                         Jsonb(x["legibility"]) if x.get("legibility") else None,
                         Jsonb(x["legibility_check"]) if x.get("legibility_check") else None, False))
            n["snapshots"] += 1
        known = {x["id"] for x in snapshots}
        for c in changes:
            if c["page_id"] not in page_ids or c.get("to_snapshot") not in known:
                continue
            cur.execute("insert into page_changes values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) on conflict do nothing",
                        (c["id"], c["page_id"], c.get("entity_id"), c.get("from_snapshot"), c.get("to_snapshot"),
                         store.ts(c.get("detected_at")), c.get("summary"), Jsonb(c.get("added_lines") or []),
                         Jsonb(c.get("removed_lines") or []), Jsonb(c.get("style_changes") or []),
                         Jsonb(c["assessment"]) if c.get("assessment") else None, False))
            n["changes"] += 1
    n.update(entities=len(GROUPS), items=len(ids), pages=len(pages),
             skippedMock=len(all_snapshots) - len(snapshots) + len(all_changes) - len(changes))
    return ids, n


def wait_for_ai(ai_url: str, tries: int = 60) -> dict:
    for i in range(tries):
        try:
            return bf.request("GET", f"{ai_url}/health", timeout=10)
        except (urllib.error.URLError, TimeoutError, OSError) as ex:
            if i == tries - 1:
                raise
            log(f"czekam na ai-service: {ex}")
            time.sleep(5)
    raise RuntimeError("unreachable")


def load_findings(conn, ai_url: str, records: list[dict], ids: dict[str, str], imported_at: str) -> Counter:
    stats: Counter = Counter()
    health = wait_for_ai(ai_url)
    thresholds = bf.request("GET", f"{ai_url}/thresholds/default", timeout=10)
    with conn.cursor() as cur:
        cur.execute("select count(*) from thresholds")
        if not cur.fetchone()[0]:
            cur.execute("insert into thresholds (version, values, updated_at, active) values ('v1', %s, %s, true)",
                        (Jsonb(thresholds["values"]), imported_at))
        cur.execute("select url from items where analyzed_at is not null")
        done = {r[0] for r in cur.fetchall()}
    conn.commit()
    pending = [r for r in records if r["source_url"] not in done]
    use_llm = bool((health.get("llm") or {}).get("model"))
    todo = interleave(pending)[:LLM_LIMIT] if use_llm else pending
    batch = LLM_BATCH if use_llm else bf.BATCH_SIZE
    log(f"rekordy: {len(records)}, czeka na analizę: {len(pending)}, w tym przebiegu: {len(todo)} (LLM: {use_llm})")
    cert = bf.load_cert_domains()
    topic_threshold = thresholds["values"].get("topic.INVESTMENT", 0.5)
    for i in range(0, len(todo), batch):
        chunk = todo[i:i + batch]
        response = bf.request("POST", f"{ai_url}/ingest", {"records": chunk})
        returned = {x["item"]["url"] for x in response["results"]}
        retry: set[str] = set()
        stats["rejected"] += len(chunk) - len(returned)
        with conn.cursor() as cur:
            for result in response["results"]:
                llm = result["analysis"].get("llm") or {}
                if use_llm and "module" not in llm:
                    stats["llmPending"] += 1
                    retry.add(result["item"]["url"])
                    continue
                stats["analyzed"] += 1
                if bf.keep(result["analysis"], topic_threshold):
                    finding = bf.to_finding(result["item"], result["analysis"], imported_at, cert, stats)
                    store.save_finding(cur, ids[result["item"]["url"]], finding)
                    stats["kept"] += 1
                else:
                    stats["outOfScope"] += 1
            # odrzucone przez /ingest (za krótkie, duplikat treści) też są przeanalizowane; czekają tylko te bez oceny LLM
            cur.executemany("update items set analyzed_at = now() where id = %s",
                            [(ids[r["source_url"]],) for r in chunk if r["source_url"] not in retry])
        conn.commit()
        log(f"{min(i + batch, len(todo))}/{len(todo)}")
        if retry and any("429" in str((x["analysis"].get("llm") or {}).get("error")) for x in response["results"]):
            log("limit LLM (429): pozostałe rekordy czekają na kolejny przebieg loadera")
            break
    stats["pending"] = len(pending) - stats["analyzed"] - stats["rejected"]
    stats["modelVersion"] = health["modelVersion"]
    return stats


def interleave(records: list[dict]) -> list[dict]:
    """Round-robin by source, so a limited run still covers every platform."""
    groups: dict[str, list[dict]] = {}
    for r in records:
        groups.setdefault(str(r.get("source")), []).append(r)
    out: list[dict] = []
    while any(groups.values()):
        for g in groups.values():
            if g:
                out.append(g.pop(0))
    return out


def load_media(conn) -> Counter:
    n: Counter = Counter()
    index_path = DATA / "media" / "index.json"
    index = {v["key"]: v for v in json.loads(index_path.read_text(encoding="utf-8")).values()} if index_path.exists() else {}
    rows = [("media", p.name, "image/webp", p.stat().st_size, Jsonb({k: index[p.name].get(k) for k in ("width", "height")}
             if p.name in index else None)) for p in sorted((DATA / "media").glob("*.webp"))]
    rows += [("screens", p.name, "image/png", p.stat().st_size, None) for p in sorted((DATA / "monitor" / "screens").glob("*.png"))]
    with conn.cursor() as cur:
        cur.execute("delete from media_objects")
        cur.executemany("insert into media_objects values (%s, %s, %s, %s, %s)", rows)
    conn.commit()
    for bucket, *_ in rows:
        n[bucket] += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ai-url", default=os.environ.get("AI_URL", "http://localhost:8000"))
    args = ap.parse_args()
    started = datetime.now(timezone.utc)
    imported_at = started.isoformat(timespec="seconds").replace("+00:00", "Z")
    with store.connect() as conn:
        store.migrate(conn)
        stats: Counter = Counter(registry=load_registry(conn))
        conn.commit()
        records, read_stats = bf.load_records()
        ids, linked = load_entities(conn, records)
        stats.update(linked)
        conn.commit()
        found = load_findings(conn, args.ai_url.rstrip("/"), records, ids, imported_at)
        model_version = found.pop("modelVersion")
        stats.update(found)
        stats.update(load_media(conn))
        stats.update({f"read.{k}": v for k, v in read_stats.items()})
        with conn.cursor() as cur:
            cur.execute("insert into load_runs (started_at, finished_at, model_version, stats) values (%s, now(), %s, %s)",
                        (started, model_version, Jsonb(dict(stats))))
            cur.execute("select count(*) from findings")
            total = cur.fetchone()[0]
        conn.commit()
    log(json.dumps({"findings": total, **dict(sorted(stats.items()))}, ensure_ascii=False))
    return 0 if total else 1


if __name__ == "__main__":
    raise SystemExit(main())
