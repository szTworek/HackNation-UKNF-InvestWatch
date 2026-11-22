"""Scan pipeline: entities -> items (ingest + link) -> pages/snapshots/changes -> classify -> alerts. Idempotent (stable ids)."""
import hashlib
import threading
from urllib.parse import urlparse

from sqlalchemy import select

from . import entities as ent
from . import ingest, mockgen
from .classifier import classifier
from .config import MOCK_HISTORY
from .db import Alert, Change, Entity, Finding, Item, ItemEntity, Page, SessionLocal, Snapshot

_lock = threading.Lock()
COLS = {c.name for c in Item.__table__.columns}


def _entity_of_url(url):
    host = urlparse(url).netloc.lower()
    for eid, g in ent.GROUPS.items():
        if any(host == d or host.endswith("." + d) for d in g["domains"]):
            return eid
    return None


def _upsert_entities(s):
    reg = ent.registry_entries()
    for eid, g in ent.GROUPS.items():
        e = s.get(Entity, eid) or Entity(id=eid)
        e.name, e.registry_entries, e.domains = g["name"], reg[eid], g["domains"]
        s.merge(e)


def _social_handles(s):
    """Most frequent official author per social/ads platform, derived from ingested items."""
    rows = s.execute(select(Item.author_entity_id, Item.platform, Item.author)
                     .where(Item.author_is_entity.is_(True), Item.mock.is_(False))).all()
    counts = {}
    for eid, platform, author in rows:
        if platform == "website" or not author:
            continue
        counts.setdefault(eid, {}).setdefault(platform, {}).setdefault(author, 0)
        counts[eid][platform][author] += 1
    for eid, per in counts.items():
        e = s.get(Entity, eid)
        e.social_handles = {p: max(a, key=a.get) for p, a in sorted(per.items())}


def _save_item(s, rec):
    existing = s.get(Item, rec["id"])
    data = {k: v for k, v in rec.items() if k in COLS}
    data["author_is_entity"] = bool(rec.get("author_entity_id"))
    if existing:
        for k, v in data.items():
            setattr(existing, k, v)
    else:
        s.add(Item(**data))
    s.flush()
    have = set(s.scalars(select(ItemEntity.entity_id).where(ItemEntity.item_id == rec["id"])))
    for eid in have - set(rec["entity_ids"]):
        s.delete(s.get(ItemEntity, (rec["id"], eid)))
    for eid in rec["entity_ids"]:
        if eid not in have:
            s.add(ItemEntity(item_id=rec["id"], entity_id=eid))
    return existing is None


def _add_if_missing(s, model, row, key="id"):
    if s.get(model, row[key]) is None:
        s.add(model(**{k: v for k, v in row.items() if k in model.__table__.columns}))
        return True
    return False


def _latest_snapshot(s, page_id):
    snap = s.scalars(select(Snapshot).where(Snapshot.page_id == page_id).order_by(Snapshot.fetched_at.desc())).first()
    return None if snap is None else {c.name: getattr(snap, c.name) for c in Snapshot.__table__.columns}


def _alerts_from(s, findings, names):
    new = 0
    for f in findings:
        if f["severity"] != "high":
            continue
        item = s.get(Item, f["item_id"])
        top = f["rule_hits"][0]["label"] if f["rule_hits"] else "flagged content"
        new += _add_if_missing(s, Alert, {
            "id": "alr_" + hashlib.sha1(f["id"].encode()).hexdigest()[:12], "created_at": f["created_at"],
            "entity_id": f["entity_id"], "kind": "finding", "severity": "high",
            "title": f"{names[f['entity_id']]} {f['module']}: {top} ({item.platform}, {item.author or 'unknown author'})",
            "ref": {"finding_id": f["id"], "change_id": None}, "status": "new", "mock": f["mock"]})
    return new


def run_scan():
    with _lock, SessionLocal() as s:
        _upsert_entities(s)
        names = {eid: g["name"] for eid, g in ent.GROUPS.items()}

        items_new, records = 0, []
        for rec in ingest.load_records():
            ids, author_eid = ent.link(rec)
            if rec["platform"] == "website" and _entity_of_url(rec["source_url"]):
                author_eid = _entity_of_url(rec["source_url"])
                ids = sorted(set(ids) | {author_eid})
            if not ids:
                continue
            rec.update(entity_ids=ids, author_entity_id=author_eid)
            records.append(rec)
        if MOCK_HISTORY:
            records += mockgen.mock_items()
        for rec in records:
            items_new += _save_item(s, rec)
        s.flush()

        m_pages, m_snaps, m_changes = ingest.monitor_files()
        f_pages, f_snaps = ingest.firm_pages(_entity_of_url)
        monitor_id = {p["url"].rstrip("/"): p["page_id"] for p in m_pages}
        pages = [p for p in m_pages if p.get("entity_id") in names] + [p for p in f_pages if p["url"].rstrip("/") not in monitor_id]
        for sn in f_snaps:
            sn["page_id"] = monitor_id.get(sn["url"].rstrip("/"), sn["page_id"])
        for p in pages:
            _add_if_missing(s, Page, {**p, "mock": bool(p.get("mock"))}, key="page_id")
        for sn in m_snaps + f_snaps:
            _add_if_missing(s, Snapshot, sn)
        s.flush()
        changes = list(m_changes)
        if MOCK_HISTORY:
            real_change_entities = {c.get("entity_id") for c in m_changes}
            for old in s.scalars(select(Change).where(Change.id.like("chg_mock_%"), Change.entity_id.in_(real_change_entities))):
                s.delete(old)
            mp, ms, mc = mockgen.mock_pages(pages, lambda pid: _latest_snapshot(s, pid))
            keep = {c["page_id"] for c in mc if c["entity_id"] not in real_change_entities}
            for p in mp:
                if p["page_id"] in keep:
                    _add_if_missing(s, Page, p, key="page_id")
            s.flush()
            for sn in ms:
                if sn["page_id"] in keep:
                    _add_if_missing(s, Snapshot, sn)
            changes += [c for c in mc if c["page_id"] in keep]
        for c in changes:
            if c.get("entity_id") in names:
                _add_if_missing(s, Change, c)
        s.flush()

        findings_new, all_findings = 0, []
        for rec in records:
            for f in classifier.classify(rec):
                all_findings.append(f)
                row = s.get(Finding, f["id"])
                if row is None:
                    s.add(Finding(**f))
                    findings_new += 1
                else:
                    row.score, row.severity, row.rule_hits = f["score"], f["severity"], f["rule_hits"]
                    if f["mock"]:
                        row.created_at = f["created_at"]
        s.flush()
        produced = {f["id"] for f in all_findings}
        for row in s.scalars(select(Finding).where(Finding.model == classifier.model)):
            if row.id not in produced:
                s.delete(row)
        s.flush()
        kept = {r["id"] for r in records}
        for it in s.scalars(select(Item).where(Item.id.not_in(kept))):
            for ie in s.scalars(select(ItemEntity).where(ItemEntity.item_id == it.id)):
                s.delete(ie)
            s.delete(it)
        for a in s.scalars(select(Alert).where(Alert.kind == "finding")):
            if s.get(Finding, a.ref.get("finding_id")) is None:
                s.delete(a)
        alerts_new = _alerts_from(s, all_findings, names)
        _social_handles(s)
        s.commit()
        return {"items_new": items_new, "findings_new": findings_new, "alerts_new": alerts_new}
