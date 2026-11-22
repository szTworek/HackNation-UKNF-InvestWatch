"""Postgres writes shared by the loader (db/load.py) and scrape-worker: collector records -> items, Finding -> findings."""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from linking import link
from psycopg.types.json import Jsonb

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://investwatch:investwatch@localhost:5432/investwatch")
MIGRATIONS = Path(__file__).resolve().parent / "migrations"

PLATFORM = {"google_ads_transparency": "google_ads", "meta_ad_library": "meta_ads", "microsoft_ad_library": "bing_ads",
            "youtube": "youtube", "tiktok": "tiktok", "firm_website": "website"}
CHANNEL = {"google_ads": "ad", "meta_ads": "ad", "bing_ads": "ad", "youtube": "social", "tiktok": "social", "website": "website"}


def connect() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL)


def migrate(conn: psycopg.Connection) -> None:
    for path in sorted(MIGRATIONS.glob("*.sql")):
        conn.execute(path.read_text(encoding="utf-8"))
    conn.commit()


def sections(text) -> dict:
    if isinstance(text, dict):
        return {k: v for k, v in text.items() if isinstance(v, str)}
    out: dict = {}
    for part in text or []:
        if isinstance(part, dict) and isinstance(part.get("text"), str):
            key = part.get("type") or "text"
            out[key] = f"{out[key]}\n{part['text']}" if key in out else part["text"]
    return out if out else ({"text": text} if isinstance(text, str) else {})


def ts(value) -> str | None:
    """ISO timestamp or None (collectors sometimes leave free text or empty strings)."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        d = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).isoformat()


def item_id(rec: dict) -> str:
    """Same id as app/backend/scripts/build_fixtures.py, so entity links and findings point at one row."""
    return "itm_" + hashlib.sha1((rec["source_url"] + json.dumps(rec["text"], ensure_ascii=False)[:200]).encode("utf-8")).hexdigest()[:10]


def upsert_item(cur: psycopg.Cursor, rec: dict, origin: str, iid: str | None = None) -> str:
    """Collector record (D12) by source_url. Returns the stored id (an existing row keeps its id)."""
    platform = PLATFORM.get(rec.get("source"), rec.get("source"))
    text = sections(rec.get("text"))
    cur.execute(
        """insert into items (id, url, source, origin, platform, channel, author, sponsor, title, text, links, media, source_meta,
                              query_keywords, published_at, fetched_at)
           values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
           on conflict (url) do update set text = excluded.text, media = excluded.media, source_meta = excluded.source_meta,
             fetched_at = excluded.fetched_at
           returning id""",
        (iid or item_id(rec), rec["source_url"], rec.get("source"), origin, platform, CHANNEL.get(platform),
         rec.get("author") if isinstance(rec.get("author"), str) else None,
         rec.get("sponsor") if isinstance(rec.get("sponsor"), str) else None,
         text.get("title") or rec.get("title"), Jsonb(text), [str(x) for x in rec.get("links") or []],
         Jsonb(rec.get("media") or []), Jsonb(rec.get("source_meta") or {}), rec.get("query_keywords") or [],
         ts(rec.get("published_at")), ts(rec.get("fetched_at"))),
    )
    return cur.fetchone()[0]


def save_finding(cur: psycopg.Cursor, iid: str, finding: dict) -> None:
    """Upsert of the model result; the analyst status and finding_history stay untouched."""
    result = {k: v for k, v in finding.items() if k != "scoringInput"}
    cur.execute(
        """insert into findings (id, item_id, model_version, analyzed_at, result, scoring_input, modules, risk_score, risk_level)
           values (%s, %s, %s, now(), %s, %s, %s, %s, %s)
           on conflict (id) do update set result = excluded.result, scoring_input = excluded.scoring_input,
             model_version = excluded.model_version, analyzed_at = excluded.analyzed_at, modules = excluded.modules,
             risk_score = excluded.risk_score, risk_level = excluded.risk_level, updated_at = now()""",
        (finding["id"], iid, finding.get("modelVersion"), Jsonb(result), Jsonb(finding.get("scoringInput")),
         finding.get("modules") or [], finding.get("riskScore"), finding.get("riskLevel")),
    )
    cur.execute("update items set analyzed_at = now() where id = %s", (iid,))


def link_item(cur: psycopg.Cursor, iid: str, rec: dict) -> tuple[list[str], str | None]:
    """Item -> PoC entity links (db/linking.py). Returns (entity ids, entity id when the author is the firm itself)."""
    entity_ids, author_eid = link({**rec, "text": sections(rec.get("text"))})
    for eid in entity_ids:
        cur.execute("insert into item_entities values (%s, %s, %s) on conflict (item_id, entity_id) do nothing",
                    (iid, eid, author_eid is not None))
    return entity_ids, author_eid
