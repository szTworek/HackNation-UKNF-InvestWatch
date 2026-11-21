"""X ads, no login: X Ads Repository (DSA) web UI. Playwright picks advertiser via typeahead,
country Poland, range 'This year', clicks Create report and saves the CSV export."""
import csv
import io

from playwright.sync_api import sync_playwright

from common import RESULTS, envelope, ua



def collect(query, notes):
    docs = []
    ADVERTISERS = [x.strip() for x in query.split(',') if x.strip()]
    with sync_playwright() as p:
        b = p.chromium.launch()
        for adv in ADVERTISERS:
            pg = b.new_page(user_agent=ua(), accept_downloads=True)
            pg.goto("https://ads.x.com/ads-repository", wait_until="networkidle", timeout=60000)
            pg.locator("input").first.fill(adv)
            pg.wait_for_timeout(3000)
            opts = pg.locator("[role=option], li")
            handle = opts.first.inner_text().split()[-1] if opts.count() else None
            if not handle:
                notes[adv] = "no advertiser suggestion"
                continue
            opts.first.click()
            pg.get_by_text("France").first.click()
            pg.get_by_text("France").last.click()
            pg.get_by_text("Poland").last.click()
            pg.keyboard.press("Escape")
            pg.get_by_text("Today").first.click()
            pg.get_by_text("This year", exact=True).first.click()
            pg.get_by_role("button", name="Create report").click()
            pg.wait_for_timeout(4000)
            body = " ".join(pg.inner_text("body").split())
            if "No ads found" in body or "No promoted" in body:
                notes[adv] = {"handle": handle, "rows": 0, "msg": "No ads found (PL, this year)"}
                pg.close()
                continue
            try:
                with pg.expect_download(timeout=240000) as d:
                    pg.get_by_role("button", name="Download").click(timeout=240000)
                path = RESULTS / "x_ads.ads_repository_probe" / f"{handle.strip('@')}.csv"
                path.parent.mkdir(parents=True, exist_ok=True)
                d.value.save_as(path)
                rows = list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig", errors="replace"))))
                notes[adv] = {"handle": handle, "rows": len(rows), "columns": list(rows[0].keys()) if rows else []}
                for r in rows:
                    tid = r.get("Tweet ID") or r.get("tweet_id") or next(iter(r.values()))
                    docs.append(envelope(
                        url=f"https://x.com/{handle.strip('@')}/status/{tid}", source="x_ads_repository",
                        collector="x_ads.ads_repository_probe", content_type="ad",
                        text=r.get("Tweet Text") or r.get("Text") or "", author=handle,
                        sponsor=r.get("Paid By") or r.get("Advertiser Name") or handle,
                        source_meta={"advertiser_query": adv, "row": r},
                    ))
            except Exception as e:
                notes[adv] = {"handle": handle, "error": f"{type(e).__name__}", "page": body[300:600]}
            pg.close()
        b.close()
    return docs

