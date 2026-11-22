"""Loader: repo data -> Postgres, in two one-shot, idempotent stages.

--stage init (compose service `db-init`, seconds; the app starts after it): steps 1-3 and 5.
--stage score (compose service `loader`, in the background while the app runs): step 4, progress in load_runs.

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

When data/findings.seed.json exists (findings.real.json of the earlier pipeline, already scored), step 4 imports
those results by URL instead of sending records to ai-service, so `up` does not re-run the LLM. Records without a
result are then removed from items (db-init adds them again on the next run); LOADER_SCORE_NEW=1 scores them instead.

Run: python db/load.py --stage init|score [--ai-url http://ai-service:8000]
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
SEED = Path(os.environ.get("LOADER_SEED", DATA / "findings.seed.json"))
SCORE_NEW = os.environ.get("LOADER_SCORE_NEW") == "1"
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


def load_entities(conn, records: list[dict]) -> tuple[dict[str, str], dict[str, tuple], Counter]:
    """Entities, items with their entity links and monitor data. Returns {source_url: item id}, {source_url: links}."""
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
        ids, links = {}, {}
        for rec in records:
            ids[rec["source_url"]] = iid = store.upsert_item(cur, rec, "export")
            links[rec["source_url"]] = store.link_item(cur, iid, rec)
            n["itemLinks"] += len(links[rec["source_url"]][0])
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
    return ids, links, n


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


def for_ai(rec: dict, links: tuple) -> dict:
    """Own material of a PoC firm goes to ai-service with the KNF registry entry as publisher (module 2)."""
    from linking import GROUPS

    author_eid = links[1] if links else None
    return {**rec, "sponsor": GROUPS[author_eid]["registry"][0]} if author_eid and not rec.get("sponsor") else rec


def db_links(conn) -> tuple[dict[str, str], dict[str, tuple]]:
    """Item ids and entity links written by the init stage: {source_url: id}, {source_url: (entity ids, author entity)}."""
    with conn.cursor() as cur:
        cur.execute("""select i.url, i.id, coalesce(array_agg(ie.entity_id order by ie.entity_id) filter (where ie.entity_id is not null), '{}'),
                              coalesce(bool_or(ie.author_is_entity), false)
                         from items i left join item_entities ie on ie.item_id = i.id group by i.id""")
        rows = cur.fetchall()
    return {url: iid for url, iid, _, _ in rows}, {url: (eids, eids[0] if own and eids else None) for url, _, eids, own in rows}


def load_findings(conn, ai_url: str, records: list[dict], ids: dict[str, str], links: dict[str, tuple], imported_at: str,
                  run_id: int) -> Counter:
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
    # rekordy powiązane z podmiotami najpierw: z nich powstaje oś podmiotu
    linked = [r for r in pending if links.get(r["source_url"], ([], None))[0]]
    ordered = interleave(linked) + interleave([r for r in pending if not links.get(r["source_url"], ([], None))[0]])
    todo = ordered[:LLM_LIMIT] if use_llm else ordered
    batch = LLM_BATCH if use_llm else bf.BATCH_SIZE
    log(f"rekordy: {len(records)}, czeka na analizę: {len(pending)}, w tym przebiegu: {len(todo)} (LLM: {use_llm})")
    with conn.cursor() as cur:
        cur.execute("update load_runs set total = %s, done = 0, model_version = %s where id = %s", (len(todo), health["modelVersion"], run_id))
    conn.commit()
    cert = bf.load_cert_domains()
    topic_threshold = thresholds["values"].get("topic.INVESTMENT", 0.5)
    for i in range(0, len(todo), batch):
        chunk = todo[i:i + batch]
        response = bf.request("POST", f"{ai_url}/ingest", {"records": [for_ai(r, links.get(r["source_url"])) for r in chunk]})
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
            cur.execute("update load_runs set done = %s where id = %s", (min(i + batch, len(todo)), run_id))
        conn.commit()
        log(f"{min(i + batch, len(todo))}/{len(todo)}")
        if retry and any("429" in str((x["analysis"].get("llm") or {}).get("error")) for x in response["results"]):
            log("limit LLM (429): pozostałe rekordy czekają na kolejny przebieg loadera")
            break
    stats["pending"] = len(pending) - stats["analyzed"] - stats["rejected"]
    stats["modelVersion"] = health["modelVersion"]
    return stats


def seed_item(f: dict) -> dict:
    """Collector-style record rebuilt from a seed finding whose URL is not among the collected records
    (the fictional `demo-*` examples of docs/demo.md, records dropped from the export)."""
    author = f.get("author") or {}
    return {"source_url": f["url"], "source": f.get("platform"), "title": f.get("title"), "text": f.get("text") or "",
            "author": author.get("displayName") or author.get("handle") if isinstance(author, dict) else author,
            "links": f.get("outboundLinks") or [], "published_at": f.get("publishedAt"), "fetched_at": f.get("fetchedAt")}


def load_seed(conn, ids: dict[str, str]) -> Counter:
    """Already scored findings from SEED, matched to items by URL. A finding already in the table is left as it is;
    another finding of the same collected item (different id from a later scoring run) is replaced, so an item has
    one result. A finding without a collected item gets an item of its own (origin `seed`); versions of one post
    (demo-ig-kasia-v1/v2) share that item."""
    n: Counter = Counter()
    findings = json.loads(SEED.read_text(encoding="utf-8"))["findings"]
    with conn.cursor() as cur:
        cur.execute("select id from findings")
        present = {r[0] for r in cur.fetchall()}
        for f in findings:
            if f["id"] in present:
                n["seedPresent"] += 1
                continue
            iid = ids.get(f["url"])
            if iid:
                cur.execute("delete from findings where item_id = %s and id <> %s", (iid, f["id"]))
            else:
                iid = store.upsert_item(cur, seed_item(f), "seed")
                n["seedItems"] += 1
            store.save_finding(cur, iid, f)
            # status zapisany w pliku pasuje do jego historii (findings.result.history); później zmienia go tylko analityk
            cur.execute("update findings set status = %s where id = %s", (f.get("status") or "NEW", f["id"]))
            n["seeded"] += 1
    conn.commit()
    return n


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
    ap.add_argument("--stage", choices=("init", "score"), required=True)
    ap.add_argument("--ai-url", default=os.environ.get("AI_URL", "http://localhost:8000"))
    args = ap.parse_args()
    started = datetime.now(timezone.utc)
    imported_at = started.isoformat(timespec="seconds").replace("+00:00", "Z")
    stats: Counter = Counter()
    with store.connect() as conn:
        store.migrate(conn)
        records, read_stats = bf.load_records()
        with conn.cursor() as cur:
            cur.execute("insert into load_runs (stage, started_at) values (%s, %s) returning id", (args.stage, started))
            run_id = cur.fetchone()[0]
        conn.commit()
        if args.stage == "init":
            stats["registry"] = load_registry(conn)
            _, _, linked = load_entities(conn, records)
            stats.update(linked)
            stats.update(load_media(conn))
            stats.update({f"read.{k}": v for k, v in read_stats.items()})
        else:
            ids, links = db_links(conn)
            if SEED.is_file():
                stats.update(load_seed(conn, ids))
                log(f"wyniki z {SEED.name}: {stats['seeded']} nowych (w tym {stats['seedItems']} z własnym rekordem), "
                    f"{stats['seedPresent']} już w bazie")
            if SCORE_NEW or not SEED.is_file():
                found = load_findings(conn, args.ai_url.rstrip("/"), records, ids, links, imported_at, run_id)
                found.pop("modelVersion")
                stats.update(found)
            else:
                # bez oceny LLM aplikacja pokazuje tylko ocenione rekordy; db-init doda resztę przy kolejnym up
                with conn.cursor() as cur:
                    cur.execute("delete from items where analyzed_at is null")
                    stats["unscoredRemoved"] = cur.rowcount
                conn.commit()
                log(f"bez oceny LLM: usunięto {stats['unscoredRemoved']} rekordów bez oceny (LOADER_SCORE_NEW=1 je ocenia)")
        with conn.cursor() as cur:
            cur.execute("update load_runs set finished_at = now(), stats = %s where id = %s", (Jsonb(dict(stats)), run_id))
            cur.execute("select count(*) from findings")
            total = cur.fetchone()[0]
        conn.commit()
    log(json.dumps({"stage": args.stage, "findings": total, **dict(sorted(stats.items()))}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
