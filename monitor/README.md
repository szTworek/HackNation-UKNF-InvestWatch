# Website change monitor

Fetches the entity pages in `data/monitor/pages.json` with Playwright (1366x768, pl-PL), normalizes the visible text, captures styled text blocks and a full-page screenshot,
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
- `snapshots.jsonl`: PageSnapshot, plus `http_status`, `final_url`.
- `screens/<snapshot_id>_<viewport>.png`: full-page screenshot (git-ignored), path in the snapshot as `screenshots`. Order by `fetched_at`; seeded mock rows are older than the real rows.
- `changes.jsonl`: PageChange, written when `text_sha256` or `style_sha256` differs from the previous snapshot of the page.
- `runs.jsonl`: per-run summary: counts, duration, skipped pages (robots, bot challenge, error).

Behaviour:

- Normalization: cookie/consent containers and lines are dropped, dates/times become `<DATE>`, quotes/prices/daily moves
  outside risk-warning lines become `<NUM>`, duplicate lines are removed.
- `risk_warning`: first visible block matching the CFD / capital-at-risk wording; `cfd_loss_pct` from "79% rachunków…" /
  "82% of retail investor accounts…"; `above_fold` = a warning block starts within the first 768 px.
- `blocks`: per viewport, visible text blocks (max 400) with computed `font_size_px`, `font_weight`, `color`, `background_color`
  (hex; ancestor backgrounds composited up to the first opaque one), `opacity` (product of ancestors), `x/y/w/h`.
  `style_sha256` = hash of block text + style fields + above/below the fold. Snapshots without `blocks` (older ones) never
  produce style changes.
- Legibility per block (thresholds and regexes in `preprocessing/legibility.py`): `rel_font_size` against the prevailing
  font size of the page, `contrast_ratio` (WCAG) from the CSS colours, or sampled from the screenshot when a background
  image lies under the text (`contrast_source`, `background_image`), and `is_disclosure`. Per snapshot: `legibility`
  (dominant font size + disclosure blocks per viewport) and `legibility_check` (`status` + missed thresholds).
  Only the desktop viewport is captured, so the phone threshold (11 px) is unused for now.
- Change: `text_sha256` or `style_sha256` difference; `style_changes` = per matched block (same normalized text) and field
  (style fields + `above_fold`) `{text, viewport, field, before, after}` plus `contrast_before/after` and
  `rel_size_before/after` when those measurements changed; `summary` = "N lines added, M removed, K style changes";
  `assessment` = `null` (reserved for a later LLM assessment).
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
