"""Instagram posts with a saved login session (python -m login ig). Playwright opens a hashtag
page ("#inwestowanie"), profile ("@handle") or keyword search, and captures the site's own JSON
responses; any object with a shortcode + caption becomes a post. Violates IG terms: PoC only."""
import json
from datetime import datetime, timezone
from urllib.parse import quote

from playwright.sync_api import sync_playwright

from common import envelope, session_file


def page_url(query):
    if query.startswith("#"):
        return f"https://www.instagram.com/explore/tags/{quote(query[1:])}/"
    if query.startswith("@"):
        return f"https://www.instagram.com/{query[1:]}/"
    return f"https://www.instagram.com/explore/search/keyword/?q={quote(query)}"


def walk(o):
    if isinstance(o, dict):
        if "code" in o and isinstance(o.get("caption"), (dict, type(None))) and ("taken_at" in o or "user" in o):
            yield o
        for v in o.values():
            yield from walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from walk(v)


def collect(query, notes, scrolls=3):
    bodies = []
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        ctx = b.new_context(storage_state=session_file("ig"), locale="pl-PL")
        pg = ctx.new_page()
        pg.on("response", lambda r: bodies.append(r) if ("/api/" in r.url or "graphql" in r.url)
              and "json" in (r.headers.get("content-type") or "") else None)
        pg.goto(page_url(query), wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(6000)
        for _ in range(scrolls):
            pg.mouse.wheel(0, 4000)
            pg.wait_for_timeout(2500)
        notes.update(final_url=pg.url[:120], json_responses=len(bodies),
                     checkpoint="challenge" in pg.url or "login" in pg.url)
        posts = {}
        for r in bodies:
            try:
                for m in walk(r.json()):
                    posts[m["code"]] = m
            except Exception:
                pass
        b.close()
    for code, m in posts.items():
        user = (m.get("user") or m.get("owner") or {}).get("username")
        ts = m.get("taken_at")
        yield envelope(
            url=f"https://www.instagram.com/p/{code}/", source="instagram", collector="ig_posts.session",
            content_type={1: "image", 2: "video", 8: "carousel"}.get(m.get("media_type"), "post"),
            text=(m.get("caption") or {}).get("text", ""), author=user,
            published_at=datetime.fromtimestamp(ts, timezone.utc).isoformat() if ts else None,
            sponsor=", ".join(u.get("sponsor", {}).get("username", "") for u in m.get("sponsor_tags") or []) or None,
            source_meta={"query": query, "shortcode": code, "likes": m.get("like_count"),
                         "comments": m.get("comment_count"), "is_paid_partnership": m.get("is_paid_partnership")},
        )
