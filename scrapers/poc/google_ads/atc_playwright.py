"""YouTube/Google ads: Google Ads Transparency Center (no login, no official API).
Playwright opens advertiser search by domain and captures the site's own SearchCreatives RPC response."""
import json
import re

from playwright.sync_api import sync_playwright

from common import envelope, ua



def parse(body: str):
    data = json.loads(body.removeprefix(")]}'"))
    return data.get("1") or []


def collect(query, notes):
    docs = []
    DOMAINS = [x.strip() for x in query.split(',') if x.strip()]
    with sync_playwright() as p:
        b = p.chromium.launch()
        for dom in DOMAINS:
            pg = b.new_page(user_agent=ua(), locale="pl-PL")
            caps = []
            pg.on("response", lambda r: caps.append(r) if "SearchCreatives" in r.url else None)
            pg.goto(f"https://adstransparency.google.com/?region=PL&domain={dom}", wait_until="networkidle", timeout=60000)
            pg.wait_for_timeout(2000)
            total = pg.locator("text=/\d+ (reklam|ads)/").first.inner_text() if pg.locator("text=/\d+ (reklam|ads)/").count() else None
            items = []
            for r in caps:
                try:
                    items += parse(r.text())
                except Exception as e:
                    notes.setdefault("parse_errors", []).append(str(e)[:100])
            notes[dom] = {"rpc_calls": len(caps), "creatives": len(items), "label": total}
            for c in items:
                adv, cr = c.get("1"), c.get("2")
                body = json.dumps(c.get("3") or {}, ensure_ascii=False)
                media = re.findall(r"https?://[^\"\<> ]+", body)
                docs.append(envelope(
                    url=f"https://adstransparency.google.com/advertiser/{adv}/creative/{cr}?region=PL",
                    source="google_ads_transparency", collector="google_ads.atc_playwright", content_type="ad",
                    title=None, text="", query_keywords=[dom], author=c.get("12"), sponsor=c.get("12"), links=media,
                    source_meta={"domain": dom, "advertiser_id": adv, "creative_id": cr,
                                 "format": {1: "text", 2: "image", 3: "video"}.get(c.get("4"), c.get("4")), "first_shown": (c.get("6") or {}).get("1"),
                                 "last_shown": (c.get("7") or {}).get("1"), "raw": c},
                ))
            pg.close()
        b.close()
    return docs

