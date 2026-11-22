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
 "text": {"title": "...", "ad_body": "..."}, "media": [], "mock": false}

// Finding — output of the classifier (mock now, LLM later); one item can yield many
{"id": "fnd_...", "item_id": "itm_...", "entity_id": "xtb", "module": "M2", "score": 0.81, "severity": "low|medium|high",
 "rule_hits": [{"rule_id": "R04", "label": "Missing CFD loss percentage", "evidence": "…quote…", "section": "ad_body", "span": [12, 48]}],
 "model": "mock-v0", "created_at": "..."}

// PageSnapshot — written by the monitor
{"id": "snp_...", "page_id": "xtb-home", "entity_id": "xtb", "url": "https://www.xtb.com/pl", "fetched_at": "...",
 "text_sha256": "...", "text": "...", "risk_warning": {"present": true, "cfd_loss_pct": 79, "text": "...", "above_fold": true},
 "blocks": {"1366x768": [{"text": "...", "font_size_px": 14, "font_weight": 400, "color": "#1a1a1a", "background_color": "#ffffff",
                          "opacity": 1, "x": 120, "y": 640, "w": 900, "h": 40}]},
 "style_sha256": "...", "screenshots": {"1366x768": "data/monitor/screens/snp_..._1366x768.png"}, "mock": false}
// blocks / style_sha256 / screenshots are null on snapshots taken before style capture (style changes against them are not reported)

// PageChange — written by the monitor when text_sha256 or style_sha256 differs from the previous snapshot of the page
{"id": "chg_...", "page_id": "xtb-home", "entity_id": "xtb", "from_snapshot": "snp_a", "to_snapshot": "snp_b", "detected_at": "...",
 "summary": "2 lines added, 2 removed, 1 style changes", "added_lines": ["..."], "removed_lines": ["..."],
 "style_changes": [{"text": "Kontrakty CFD są złożonymi instrumentami…", "viewport": "1366x768", "field": "font_size_px", "before": 14, "after": 9}],
 "assessment": null, "mock": false}
// style_changes.field: font_size_px | font_weight | color | background_color | opacity | above_fold

// Alert — created by the backend from findings (severity high); page changes create no alerts until they have an assessment
{"id": "alr_...", "created_at": "...", "entity_id": "xtb", "kind": "finding", "severity": "low|medium|high",
 "title": "XTB M2: Missing CFD loss percentage (youtube, XTB)", "ref": {"finding_id": "fnd_...", "change_id": null}, "status": "new|ack|closed"}
```

Amendments v0.2 (media + legibility of disclosures). Measurements and thresholds are deterministic
(`inwestwatch/preprocessing/legibility.py`, no LLM); an LLM later fills `assessment` / `Finding`, never these numbers.

```jsonc
// Item (and export record): images; key = file in data/media/ (webp, longest side <= 600 px), served by GET /api/media/{key}
"media": [{"type": "image", "key": "0022ab30aa44b5c54d66.webp", "width": 600, "height": 314, "ocr": true,
           "source": "creative|thumbnail|screenshot"}]
// Item: per OCR line of the image (record: source_meta.ocr_lines); box in original image px
"ocr_lines": [{"text": "Kapitał zagrożony…", "box": [x, y, w, h], "box_height_px": 12, "rel_font_size": 0.45,
               "contrast_ratio": 1.9, "is_disclosure": true}]
// Item (record: source_meta.legibility); only on records with at least one image
"legibility": {"disclosure_in_text": false, "disclosure_on_image": true, "image_width": 1200, "image_height": 628,
               "dominant_line_px": 26, "lines": 30, "disclosure_lines": 2}
// rel_font_size = box height / dominant line height (text-length weighted median) of the same image;
// contrast_ratio = WCAG ratio between the text and background pixel classes of the box (Otsu split, class medians);
// is_disclosure = regex: advertising label (sponsorowane, reklama, materiał promocyjny, współpraca, #ad) or risk
//   information (ryzyko, kapitał zagrożony, % rachunków, EN equivalents; "CFD" alone only in a sentence >= 25 chars);
// disclosure_in_text = same regex over text sections except `ocr` (title, ad_body, description, transcript…)

// PageSnapshot.blocks[vp][]: + "rel_font_size" (vs dominant block font size of the page, text-length weighted),
//   "contrast_ratio", "contrast_source": "css|screenshot", "background_image": bool, "is_disclosure": bool.
//   Background colours are composited through ancestors up to the first opaque one; when a background image is in
//   that chain the CSS colour says nothing, so the full-page screenshot is sampled instead (contrast_source).
// PageSnapshot: + "legibility": {"1366x768": {"dominant_font_px": 16, "disclosure_blocks": [{"text", "font_size_px",
//   "rel_font_size", "contrast_ratio", "contrast_source", "y", "above_fold"}]}}
// PageChange.style_changes[]: + "contrast_before", "contrast_after", "rel_size_before", "rel_size_after"
//   (only present when the measurement itself changed)

// Item and PageSnapshot: verdict against fixed thresholds, one entry per threshold missed by a disclosure
"legibility_check": {"status": "ok|problem|no_disclosure",
                     "failures": [{"rule": "R05", "metric": "contrast_ratio", "value": 1.9, "threshold": 4.5, "text": "…"}]}
// metric: contrast_ratio < 4.5 (R05, WCAG 2.x AA) | rel_font_size < 0.7 (R04) | font_px < 12 desktop, 11 phone (R04+R08;
//   image line heights scaled to 1080 px width). status "problem" = the disclosure is only on the image (not in the
//   record text) and misses a threshold (R02 + R06); a disclosure repeated in the text keeps the status "ok".
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
| GET | `/api/entities/{id}/pages` | `[{page_id, url, label, last_snapshot: PageSnapshot (without blocks), changes: PageChange[]}]` |
| GET | `/api/changes/{id}` | `PageChange` + `{"from": PageSnapshot, "to": PageSnapshot}` |
| GET | `/api/screens/{file}` | screenshot PNG from `data/monitor/screens/` |
| GET | `/api/media/{key}` | ad image thumbnail (webp) from `data/media/` |
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
