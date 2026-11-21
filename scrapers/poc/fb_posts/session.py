"""Facebook posts with a saved login session (python -m login fb). Playwright opens post search
(keyword) or a Page ("@XTBPL"), scrolls, and reads [role=article] blocks from the DOM.
Violates Meta terms: PoC only, test account."""
import re
from urllib.parse import quote

from playwright.sync_api import sync_playwright

from common import envelope, session_file

POST_LINK = re.compile(r"/(posts|permalink|videos|reel|photo|story\.php)|story_fbid|pfbid")


def collect(query, notes, scrolls=5):
    url = (f"https://www.facebook.com/{query[1:]}" if query.startswith("@")
           else f"https://www.facebook.com/search/posts?q={quote(query)}")
    items = []
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        ctx = b.new_context(storage_state=session_file("fb"), locale="pl-PL", viewport={"width": 1280, "height": 2000})
        pg = ctx.new_page()
        pg.goto(url, wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(6000)
        for _ in range(scrolls):
            pg.mouse.wheel(0, 3000)
            pg.wait_for_timeout(2500)
        for a in pg.locator('[role="article"]').all():
            try:
                text = a.inner_text(timeout=2000)
                links = [h for h in a.locator("a").evaluate_all("els => els.map(e => e.href)") if h]
            except Exception:
                continue
            if text.strip():
                items.append((text, links))
        notes.update(final_url=pg.url[:120], articles=len(items),
                     checkpoint="checkpoint" in pg.url or "login" in pg.url)
        b.close()
    seen = set()
    for text, links in items:
        post = next((h.split("?")[0] for h in links if POST_LINK.search(h)), None)
        key = post or text[:80]
        if key in seen:
            continue
        seen.add(key)
        lines = [l for l in text.splitlines() if l.strip()]
        yield envelope(
            url=post or url, source="facebook", collector="fb_posts.session", content_type="post",
            text=text, author=lines[0] if lines else None,
            links=[h for h in links if "facebook.com" not in h][:20],
            source_meta={"query": query, "has_permalink": bool(post)},
        )
