from collections import Counter, defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .classifier import RULES
from .config import DATA, MONITOR_DIR, SCAN_INTERVAL_MIN, SCAN_ON_STARTUP
from .db import Alert, Change, Entity, Finding, Item, ItemEntity, Page, SessionLocal, Snapshot, init_db
from .scan import run_scan

scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(_app):
    init_db()
    if SCAN_ON_STARTUP:
        run_scan()
    if SCAN_INTERVAL_MIN > 0:
        scheduler.add_job(run_scan, "interval", minutes=SCAN_INTERVAL_MIN, id="rescan", coalesce=True, max_instances=1)
        scheduler.start()
    yield
    if scheduler.running:
        scheduler.shutdown(wait=False)


app = FastAPI(title="InvestWatch API", version="0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/api/screens", StaticFiles(directory=MONITOR_DIR / "screens", check_dir=False), name="screens")
app.mount("/api/media", StaticFiles(directory=DATA / "media", check_dir=False), name="media")


def db():
    with SessionLocal() as s:
        yield s


def row(obj, drop=()):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns if c.name not in drop}


ITEM_DROP = ("author_entity_id", "query_keywords", "source_meta")


def item_out(it, findings):
    return {**row(it, ITEM_DROP), "source_meta": it.source_meta, "findings": [row(f) for f in findings]}


def utc(days=0):
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def entity_out(s, e):
    items = s.scalar(select(func.count()).select_from(ItemEntity).where(ItemEntity.entity_id == e.id))
    fs = s.execute(select(Finding.module, Finding.score).where(Finding.entity_id == e.id)).all()
    alerts_new = s.scalar(select(func.count()).select_from(Alert).where(Alert.entity_id == e.id, Alert.status == "new"))
    pages = s.scalar(select(func.count()).select_from(Page).where(Page.entity_id == e.id))
    changed = s.scalar(select(func.count(func.distinct(Change.page_id))).where(Change.entity_id == e.id, Change.detected_at >= utc(7)))
    risk = round(sum(sc for _, sc in fs) / len(fs), 2) if fs else 0.0
    return {"id": e.id, "name": e.name, "registry_entries": e.registry_entries, "domains": e.domains,
            "monitored_pages": pages, "social_handles": e.social_handles,
            "kpis": {"items": items, "findings_open": len(fs), "alerts_new": alerts_new, "risk_score": risk, "pages_changed_7d": changed}}


def get_entity(s, eid):
    e = s.get(Entity, eid)
    if not e:
        raise HTTPException(404, f"entity {eid} not found")
    return e


@app.get("/api/entities")
def list_entities(s: Session = Depends(db)):
    return [entity_out(s, e) for e in s.scalars(select(Entity).order_by(Entity.id))]


@app.get("/api/entities/{eid}")
def entity_detail(eid: str, s: Session = Depends(db)):
    e = get_entity(s, eid)
    modules = {m: {"findings": 0, "avg_score": 0.0} for m in ("M1", "M2", "M3")}
    for m, n, avg in s.execute(select(Finding.module, func.count(), func.avg(Finding.score)).where(Finding.entity_id == eid).group_by(Finding.module)):
        modules[m] = {"findings": n, "avg_score": round(avg, 2)}
    platforms = dict(s.execute(select(Item.platform, func.count()).join(ItemEntity, ItemEntity.item_id == Item.id)
                               .where(ItemEntity.entity_id == eid).group_by(Item.platform)).all())
    return {**entity_out(s, e), "modules": modules, "platforms": platforms}


@app.get("/api/entities/{eid}/items")
def entity_items(eid: str, channel: str | None = None, platform: str | None = None, module: str | None = None,
                 limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0), s: Session = Depends(db)):
    get_entity(s, eid)
    q = select(Item).join(ItemEntity, ItemEntity.item_id == Item.id).where(ItemEntity.entity_id == eid)
    if channel:
        q = q.where(Item.channel == channel)
    if platform:
        q = q.where(Item.platform == platform)
    if module:
        q = q.where(Item.id.in_(select(Finding.item_id).where(Finding.entity_id == eid, Finding.module == module)))
    total = s.scalar(select(func.count()).select_from(q.subquery()))
    items = s.scalars(q.order_by(Item.published_at.desc().nulls_last(), Item.id).limit(limit).offset(offset)).all()
    fmap = defaultdict(list)
    for f in s.scalars(select(Finding).where(Finding.entity_id == eid, Finding.item_id.in_([i.id for i in items]))):
        fmap[f.item_id].append(f)
    return {"total": total, "items": [item_out(i, fmap[i.id]) for i in items]}


@app.get("/api/items/{iid}")
def item_detail(iid: str, s: Session = Depends(db)):
    it = s.get(Item, iid)
    if not it:
        raise HTTPException(404, f"item {iid} not found")
    return item_out(it, s.scalars(select(Finding).where(Finding.item_id == iid)).all())


@app.get("/api/entities/{eid}/pages")
def entity_pages(eid: str, s: Session = Depends(db)):
    get_entity(s, eid)
    out = []
    for p in s.scalars(select(Page).where(Page.entity_id == eid).order_by(Page.url)):
        snap = s.scalars(select(Snapshot).where(Snapshot.page_id == p.page_id).order_by(Snapshot.fetched_at.desc())).first()
        changes = s.scalars(select(Change).where(Change.page_id == p.page_id).order_by(Change.detected_at.desc())).all()
        out.append({"page_id": p.page_id, "url": p.url, "label": p.label, "mock": p.mock,
                    "last_snapshot": row(snap, ("blocks",)) if snap else None, "changes": [row(c) for c in changes]})
    return out


@app.get("/api/changes/{cid}")
def change_detail(cid: str, s: Session = Depends(db)):
    c = s.get(Change, cid)
    if not c:
        raise HTTPException(404, f"change {cid} not found")
    frm = s.get(Snapshot, c.from_snapshot) if c.from_snapshot else None
    to = s.get(Snapshot, c.to_snapshot) if c.to_snapshot else None
    return {**row(c), "from": row(frm) if frm else None, "to": row(to) if to else None}


@app.get("/api/alerts")
def list_alerts(status: str | None = None, entity_id: str | None = None, severity: str | None = None, s: Session = Depends(db)):
    q = select(Alert)
    if status:
        q = q.where(Alert.status == status)
    if entity_id:
        q = q.where(Alert.entity_id == entity_id)
    if severity:
        q = q.where(Alert.severity == severity)
    return [row(a) for a in s.scalars(q.order_by(Alert.created_at.desc()))]


@app.post("/api/alerts/{aid}/ack")
def ack_alert(aid: str, s: Session = Depends(db)):
    a = s.get(Alert, aid)
    if not a:
        raise HTTPException(404, f"alert {aid} not found")
    a.status = "ack"
    s.commit()
    return row(a)


@app.get("/api/metrics/overview")
def metrics(days: int = Query(30, ge=1, le=365), s: Session = Depends(db)):
    since = utc(days)
    by_day = {(datetime.now(timezone.utc) - timedelta(days=d)).strftime("%Y-%m-%d"): {"M1": 0, "M2": 0, "M3": 0}
              for d in range(days - 1, -1, -1)}
    when = func.coalesce(Item.published_at, Finding.created_at)
    for created, module in s.execute(select(when, Finding.module).join(Item, Item.id == Finding.item_id).where(when >= since)):
        day = by_day.get(created[:10])
        if day is not None:
            day[module] += 1
    heat = defaultdict(lambda: {"M1": 0.0, "M2": 0.0, "M3": 0.0})
    for eid, m, avg in s.execute(select(Finding.entity_id, Finding.module, func.avg(Finding.score)).group_by(Finding.entity_id, Finding.module)):
        heat[eid][m] = round(avg, 2)
    rules = Counter(h["rule_id"] for (hits,) in s.execute(select(Finding.rule_hits)) for h in hits)
    return {
        "totals": {
            "entities": s.scalar(select(func.count()).select_from(Entity)),
            "items": s.scalar(select(func.count(func.distinct(ItemEntity.item_id)))),
            "findings": s.scalar(select(func.count()).select_from(Finding)),
            "alerts_new": s.scalar(select(func.count()).select_from(Alert).where(Alert.status == "new")),
            "pages": s.scalar(select(func.count()).select_from(Page)),
            "page_changes_30d": s.scalar(select(func.count()).select_from(Change).where(Change.detected_at >= utc(30))),
        },
        "findings_by_day": [{"date": d, **v} for d, v in by_day.items()],
        "items_by_platform": dict(s.execute(select(Item.platform, func.count()).where(Item.id.in_(select(ItemEntity.item_id)))
                                            .group_by(Item.platform)).all()),
        "heatmap": [{"entity_id": e, **heat[e]} for e in s.scalars(select(Entity.id).order_by(Entity.id))],
        "top_rules": [{"rule_id": r, "label": RULES[r], "count": n} for r, n in rules.most_common(10)],
    }


@app.post("/api/scan/run")
def scan_run():
    return run_scan()
