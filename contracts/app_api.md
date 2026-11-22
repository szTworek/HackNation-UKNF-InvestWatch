# InvestWatch app contract v0 (entity-centric)

Main axis: entity (podmiot) from the KNF registry. Everything (website pages, social posts, ads) is attached to an entity and classified per module.
PoC scope: 5 entities — `xtb`, `etoro`, `plus500`, `trading212`, `revolut`. LLM is mocked (`model: "mock-v0"`). Mock data allowed, always flagged `mock: true`.

Owners: backend `inwestwatch/app/backend/`, website monitor `inwestwatch/monitor/`, UI `inwestwatch/frontend/`. A change to this file is proposed to the lead session, not edited silently.

## Modules

- `M1`: entity advertised by third parties / finfluencers (author is not the entity).
- `M2`: risk-information compliance in the entity's own materials (website, own ads); 18 rules, art. 44 of Delegated Regulation 2017/565. Rule ids `R01`..`R18`.
- `M3`: shadow advisory — investment recommendations by authors outside the KNF registry, mentioning the entity.

## Objects (JSON)

```jsonc
// Entity — group of KNF registry entries under one brand
{"id": "xtb", "name": "XTB", "registry_entries": [{"name": "XTB S.A.", "category": "domy_maklerskie", "country": "Polska"}],
 "domains": ["xtb.com"], "monitored_pages": 6, "social_handles": {"youtube": "XTBPolska"},
 "kpis": {"items": 412, "findings_open": 17, "alerts_new": 3, "risk_score": 0.62, "pages_changed_7d": 1}}

// Item — one collected record in the D12–D15 format (data/export/<source>/records.jsonl) plus entity linkage
{"id": "itm_...", "entity_ids": ["xtb"], "channel": "ad|social|website", "platform": "google_ads|meta_ads|bing_ads|youtube|tiktok|website",
 "source_url": "...", "author": "...", "author_is_entity": true, "published_at": "...", "fetched_at": "...",
 "text": {"title": "...", "ad_body": "..."}, "mock": false}

// Finding — output of the classifier (mock now, LLM later); one item can yield many
{"id": "fnd_...", "item_id": "itm_...", "entity_id": "xtb", "module": "M2", "score": 0.81, "severity": "low|medium|high",
 "rule_hits": [{"rule_id": "R04", "label": "Missing CFD loss percentage", "evidence": "…quote…", "section": "ad_body", "span": [12, 48]}],
 "model": "mock-v0", "created_at": "..."}

// PageSnapshot — written by the monitor
{"id": "snp_...", "page_id": "xtb-home", "entity_id": "xtb", "url": "https://www.xtb.com/pl", "fetched_at": "...",
 "text_sha256": "...", "text": "...", "risk_warning": {"present": true, "cfd_loss_pct": 79, "text": "...", "above_fold": true}, "mock": false}

// PageChange — written by the monitor when text_sha256 differs from the previous snapshot of the page
{"id": "chg_...", "page_id": "xtb-home", "entity_id": "xtb", "from_snapshot": "snp_a", "to_snapshot": "snp_b", "detected_at": "...",
 "kinds": ["text", "risk_warning_changed", "risk_warning_removed", "page_removed"],
 "summary": "CFD loss percentage 77% -> 79%", "added_lines": ["..."], "removed_lines": ["..."], "mock": false}

// Alert — created by the backend from findings (severity high) and page changes (risk_warning_*)
{"id": "alr_...", "created_at": "...", "entity_id": "xtb", "kind": "finding|page_change", "severity": "low|medium|high",
 "title": "Risk warning removed on xtb.com/pl/cfd", "ref": {"finding_id": null, "change_id": "chg_..."}, "status": "new|ack|closed"}
```

Amendments v0.1 (accepted): `mock` is on every object (Finding, Alert, page too); Item also returns `source_meta`; `span` is `null` for "missing X" rules; `findings_by_day` buckets by the item's `published_at`.

## Monitor -> backend handoff (files)

- `inwestwatch/data/monitor/pages.json`: list of `{page_id, entity_id, url, label}`.
- `inwestwatch/data/monitor/snapshots.jsonl`, `inwestwatch/data/monitor/changes.jsonl`: PageSnapshot / PageChange, append-only.
- Backend ingests them on startup and on `POST /api/scan/run`.

## API (FastAPI, base `/api`, default `http://localhost:8000`)

| method | path | returns |
|---|---|---|
| GET | `/api/entities` | `Entity[]` |
| GET | `/api/entities/{id}` | `Entity` + `{"modules": {"M1": {"findings": n, "avg_score": x}, ...}, "platforms": {"youtube": n, ...}}` |
| GET | `/api/entities/{id}/items?channel=&platform=&module=&limit=&offset=` | `{"total": n, "items": [Item + {"findings": Finding[]}]}` |
| GET | `/api/items/{id}` | `Item` + `{"findings": Finding[]}` |
| GET | `/api/entities/{id}/pages` | `[{page_id, url, label, last_snapshot: PageSnapshot, changes: PageChange[]}]` |
| GET | `/api/changes/{id}` | `PageChange` + `{"from": PageSnapshot, "to": PageSnapshot}` |
| GET | `/api/alerts?status=&entity_id=&severity=` | `Alert[]` |
| POST | `/api/alerts/{id}/ack` | `Alert` |
| GET | `/api/metrics/overview?days=30` | see below |
| POST | `/api/scan/run` | `{"items_new": n, "findings_new": n, "alerts_new": n}` |

```jsonc
// /api/metrics/overview
{"totals": {"entities": 5, "items": 1200, "findings": 240, "alerts_new": 12, "pages": 30, "page_changes_30d": 4},
 "findings_by_day": [{"date": "2026-11-01", "M1": 3, "M2": 5, "M3": 1}],
 "items_by_platform": {"google_ads": 440, "meta_ads": 341},
 "heatmap": [{"entity_id": "xtb", "M1": 0.4, "M2": 0.7, "M3": 0.1}],
 "top_rules": [{"rule_id": "R04", "label": "...", "count": 31}]}
```
