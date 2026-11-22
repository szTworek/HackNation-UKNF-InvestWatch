"""Hits every contract endpoint on a throwaway SQLite DB. Run: .venv/Scripts/python.exe smoke_test.py"""
import os
import sys
import tempfile

os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "smoke.db").replace("\\", "/")
os.environ["SCAN_INTERVAL_MIN"] = "0"

from fastapi.testclient import TestClient  # noqa: E402

from inwestwatch_api.main import app  # noqa: E402

IDS = ["xtb", "etoro", "plus500", "trading212", "revolut"]


def check(cond, msg):
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        check.failed = True


check.failed = False

with TestClient(app) as c:
    ents = c.get("/api/entities").json()
    check([e["id"] for e in ents] == sorted(IDS), f"GET /api/entities -> {[e['id'] for e in ents]}")
    for eid in IDS:
        d = c.get(f"/api/entities/{eid}").json()
        check(d["kpis"]["items"] > 0 and set(d["modules"]) == {"M1", "M2", "M3"} and d["registry_entries"],
              f"GET /api/entities/{eid} items={d['kpis']['items']} modules={ {m: v['findings'] for m, v in d['modules'].items()} } platforms={d['platforms']}")
        r = c.get(f"/api/entities/{eid}/items", params={"limit": 5}).json()
        check(r["total"] > 0 and len(r["items"]) <= 5, f"GET /api/entities/{eid}/items total={r['total']}")
        r2 = c.get(f"/api/entities/{eid}/items", params={"module": "M2", "channel": "ad", "limit": 3}).json()
        check(all(i["channel"] == "ad" for i in r2["items"]), f"  filter module=M2 channel=ad total={r2['total']}")
        pages = c.get(f"/api/entities/{eid}/pages").json()
        check(len(pages) > 0, f"GET /api/entities/{eid}/pages n={len(pages)} with_snapshot={sum(1 for p in pages if p['last_snapshot'])}")
    item = c.get("/api/entities/xtb/items", params={"module": "M3", "limit": 1}).json()["items"][0]
    d = c.get(f"/api/items/{item['id']}").json()
    check(d["findings"] and d["findings"][0]["model"] == "mock-v0", f"GET /api/items/{item['id']} findings={len(d['findings'])}")
    check(c.get("/api/items/itm_missing").status_code == 404, "GET /api/items/missing -> 404")
    chg = next(ch for p in c.get("/api/entities/xtb/pages").json() for ch in p["changes"])
    d = c.get(f"/api/changes/{chg['id']}").json()
    check(d["from"] and d["to"], f"GET /api/changes/{chg['id']} summary={d['summary']!r}")
    alerts = c.get("/api/alerts", params={"status": "new"}).json()
    check(len(alerts) > 0, f"GET /api/alerts?status=new n={len(alerts)}")
    check(all(a["entity_id"] == "etoro" for a in c.get("/api/alerts", params={"entity_id": "etoro", "severity": "high"}).json()),
          "GET /api/alerts?entity_id=etoro&severity=high")
    a = c.post(f"/api/alerts/{alerts[0]['id']}/ack").json()
    check(a["status"] == "ack", f"POST /api/alerts/{alerts[0]['id']}/ack -> {a['status']}")
    m = c.get("/api/metrics/overview", params={"days": 30}).json()
    check(len(m["findings_by_day"]) == 30 and m["totals"]["entities"] == 5 and m["heatmap"] and m["top_rules"],
          f"GET /api/metrics/overview totals={m['totals']} platforms={m['items_by_platform']}")
    s = c.post("/api/scan/run").json()
    check(set(s) == {"items_new", "findings_new", "alerts_new"}, f"POST /api/scan/run -> {s}")
    check(c.get("/api/alerts", params={"status": "ack"}).json()[0]["id"] == alerts[0]["id"], "ack survives rescan")

sys.exit(1 if check.failed else 0)
