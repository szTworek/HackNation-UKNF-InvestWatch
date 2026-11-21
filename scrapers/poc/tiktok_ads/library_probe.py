"""TikTok ads, no login: Commercial Content Library web (robots.txt disallows /ads and /api, so we
only load the landing page) and Creative Center Top Ads (robots allows)."""
from playwright.sync_api import sync_playwright

from common import ua

URLS = {
    "ccl_landing": "https://library.tiktok.com/",
    "creative_center_topads": "https://ads.tiktok.com/business/creativecenter/inspiration/topads/pc/pl?region=PL&period=30&industry=",
}


def collect(query, notes):
    with sync_playwright() as p:
        b = p.chromium.launch()
        for k, u in URLS.items():
            pg = b.new_page(user_agent=ua(), locale="pl-PL")
            api = []
            pg.on("response", lambda r: api.append((r.status, r.url[:120])) if "/api/" in r.url else None)
            pg.goto(u, wait_until="domcontentloaded", timeout=60000)
            pg.wait_for_timeout(7000)
            body = pg.inner_text("body")
            notes[k] = {"final_url": pg.url[:150], "body_chars": len(body), "head": " ".join(body.split())[:300],
                        "api_calls": api[:8]}
            pg.close()
        b.close()
    return []

