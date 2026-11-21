"""Facebook posts, no login: probe a public Page ("@XTBPL") via httpx and Playwright (expect login wall)."""
import re

import httpx
from playwright.sync_api import sync_playwright

from common import envelope, ua


def collect(query, notes):
    page = query.lstrip("@")
    notes["httpx"] = {}
    for host in ("www", "m", "mbasic"):
        try:
            r = httpx.get(f"https://{host}.facebook.com/{page}", headers={"User-Agent": ua()}, timeout=20, follow_redirects=True)
            notes["httpx"][host] = r.status_code
        except Exception as e:
            notes["httpx"][host] = type(e).__name__
    url = f"https://www.facebook.com/{page}"
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(user_agent=ua(), locale="pl-PL")
        pg.goto(url, wait_until="domcontentloaded", timeout=45000)
        pg.wait_for_timeout(4000)
        body = pg.inner_text("body")
        posts = [t for t in pg.locator('[role="article"]').all_inner_texts() if t.strip()]
        b.close()
    notes["playwright"] = {"articles_with_text": len(posts), "login_wall": bool(re.search(r"Zaloguj|Log in", body))}
    for t in posts:
        yield envelope(url=url, source="facebook", collector="fb_posts.no_login_probe", content_type="post", text=t, author=page, query_keywords=[query])
