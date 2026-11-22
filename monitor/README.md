# Website change monitor

Fetches the entity pages in `data/monitor/pages.json` with Playwright (1440x900, pl-PL), normalizes the visible text,
and appends `PageSnapshot` / `PageChange` rows (contract: `contracts/app_api.md`) to `data/monitor/`.

Run from the repo root with the PoC venv (`scrapers/poc/.venv`, Python 3.13 + playwright):

```
scrapers/poc/.venv/Scripts/python -m monitor.run                  # one full run
scrapers/poc/.venv/Scripts/python -m monitor.run --entity xtb     # one entity
scrapers/poc/.venv/Scripts/python -m monitor.run --every 6h       # loop
scrapers/poc/.venv/Scripts/python -m monitor.seed_demo [--reset]  # demo history, rows flagged mock: true
```

Files (`data/monitor/`):

- `pages.json`: `{page_id, entity_id, url, label}`.
- `snapshots.jsonl`: PageSnapshot, plus `http_status`, `final_url`. Order by `fetched_at`; seeded mock rows are older than the real rows.
- `changes.jsonl`: PageChange, written when `text_sha256` differs from the previous snapshot of the page.
- `runs.jsonl`: per-run summary: counts, duration, skipped pages (robots, bot challenge, error).

Behaviour:

- Normalization: cookie/consent containers and lines are dropped, dates/times become `<DATE>`, quotes/prices/daily moves
  outside risk-warning lines become `<NUM>`, duplicate lines are removed.
- `risk_warning`: first visible block matching the CFD / capital-at-risk wording; `cfd_loss_pct` from "79% rachunków…" /
  "82% of retail investor accounts…"; `above_fold` = a warning block starts within the first 900 px.
- Change kinds: `text`, `risk_warning_changed` (added, % or text changed), `risk_warning_removed`, `page_removed` (HTTP 404/410).
- robots.txt is respected, cookies are only rejected, bot challenges (Cloudflare) are logged as skipped, never bypassed.
  `www.trading212.com` serves a Cloudflare challenge and `www.etoro.com` answers 429 after a few requests; trading212 is
  also covered by its help-centre pages, and blocked pages get mock snapshots from `seed_demo.BLOCKED_MOCK` (`mock: true`).
- All plus500 PL URLs redirect to the same English landing page `lp.plus500.com/main/` (identical snapshots).

Scheduling later:

```
# cron
0 */6 * * * cd /path/to/inwestwatch && scrapers/poc/.venv/bin/python -m monitor.run >> data/monitor/cron.log 2>&1
# Celery beat
app.conf.beat_schedule = {"monitor": {"task": "tasks.monitor_run", "schedule": crontab(minute=0, hour="*/6")}}
```
