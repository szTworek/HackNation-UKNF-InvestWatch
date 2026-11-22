"""FB + IG ads, no login: Meta Ad Library web page via Playwright. FEASIBILITY PROBE ONLY:
Meta terms allow automated collection only via Platform APIs; production = fb_ads.ad_library_api."""
import re
from urllib.parse import quote

from playwright.sync_api import sync_playwright

from common import envelope, ua

ID_RE = re.compile(r"Identyfikator biblioteki: (\d+)")


def collect(query, notes, scrolls=0):
    url = (f"https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country=PL"
           f"&q={quote(query)}&search_type=keyword_unordered&media_type=all")
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(user_agent=ua(), locale="pl-PL", viewport={"width": 1440, "height": 2000})
        pg.goto(url, wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(8000)
        body = pg.inner_text("body")
        for i in range(scrolls):  # infinite scroll: stop when a scroll adds no new ads
            pg.mouse.wheel(0, 20000)
            pg.wait_for_timeout(3000 + 1000 * (i % 3))
            nxt = pg.inner_text("body")
            if nxt.count("Identyfikator biblioteki:") <= body.count("Identyfikator biblioteki:"):
                body = nxt
                break
            body = nxt
        notes["scrolls_done"] = i + 1 if scrolls else 0
        b.close()
    notes.update(login_wall="Zaloguj się" in body[:3000], body_chars=len(body))
    for ch in re.split(r"(?=Identyfikator biblioteki: \d+)", body)[1:]:
        ad_id = ID_RE.search(ch).group(1)
        lines = [l for l in ch.splitlines() if l.strip()]
        spons = next((lines[i - 1] for i, l in enumerate(lines) if l.strip() in ("Sponsorowane", "Sponsored")), None)
        yield envelope(
            url=f"https://www.facebook.com/ads/library/?id={ad_id}", source="meta_ad_library",
            collector="fb_ads.ad_library_web", content_type="ad", text="\n".join(lines[:40]),
            author=spons, sponsor=spons, source_meta={"query": query, "ad_id": ad_id, "period": lines[1] if len(lines) > 1 else None},
        )
