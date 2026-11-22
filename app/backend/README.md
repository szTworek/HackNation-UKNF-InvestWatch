# InvestWatch backend

FastAPI + SQLAlchemy, SQLite at `inwestwatch/data/app.db` by default. API contract: `contracts/app_api.md`.

## Run

```powershell
cd app/backend
uv venv --python 3.13 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements.txt
.venv/Scripts/python.exe -m uvicorn inwestwatch_api.main:app --reload --port 8000
```

Docs: http://localhost:8000/docs. Startup creates tables and runs one scan; the scheduler rescans every `SCAN_INTERVAL_MIN` minutes.

Smoke test (throwaway DB, every endpoint):

```powershell
.venv/Scripts/python.exe smoke_test.py
```

## Env

| var | default | |
|---|---|---|
| `DATABASE_URL` | `sqlite:///<repo>/data/app.db` | e.g. `postgresql+psycopg://user:pw@db/inwestwatch` (add `psycopg[binary]`) |
| `SCAN_INTERVAL_MIN` | `60` | `0` disables the scheduler |
| `SCAN_ON_STARTUP` | `1` | |
| `MOCK_HISTORY` | `1` | `0` skips mock items/page changes |
| `KNF_FILE` | `<repo>/../data/knf_entities.json` | KNF registry dump |

## Scan pipeline (`POST /api/scan/run`)

1. Entities: 5 groups in `inwestwatch_api/entities.py`, registry entries matched by exact name in the KNF file.
2. Items: `data/export/*/records.jsonl`, then `data/samples/*_entities_v1.jsonl` and `firm_web_v1.jsonl` (dedup by `source_url`). Linked by author/sponsor, domains, brand name in text; homonyms excluded (e.g. Shimano/KSW "XTB"). Unlinked records are dropped.
3. Pages: `data/monitor/pages.json|snapshots.jsonl|changes.jsonl` (optional) + one snapshot per page from `firm_web_v1.jsonl`.
4. Classifier: `classifier.classify(item) -> list[Finding]`, `mock-v0` keyword rules R01..R18. Routing: author is the entity -> M2; third party with signal/copy-trading hits -> M3; third party promoting the entity -> M1. Swap `classifier.classifier` for an LLM implementation.
5. Alerts: every `high` finding, every page change with `risk_warning_changed|risk_warning_removed|page_removed`. Alert status (`ack`) survives rescans.

`findings_by_day` buckets by the item's `published_at` (fallback: finding `created_at`), so a scan does not pile every real finding onto one day.

Mock data (`mock: true` on items, findings, pages, snapshots, changes, alerts): `inwestwatch_api/mockgen.py` adds ~124 items over the last 30 days and one page change per entity (skipped per entity once the monitor writes real changes).
