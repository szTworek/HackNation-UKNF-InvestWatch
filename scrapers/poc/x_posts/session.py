"""X posts with a saved login session (python -m login x). Playwright opens x.com live search and
captures the site's own SearchTimeline GraphQL responses. Violates X terms: PoC only, test account."""
import json
from urllib.parse import quote

from playwright.sync_api import sync_playwright

from common import envelope, session_file


def walk(o):
    if isinstance(o, dict):
        if o.get("__typename") == "Tweet" and "legacy" in o:
            yield o
        for v in o.values():
            yield from walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from walk(v)


def collect(query, notes, scrolls=4):
    bodies = []
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        ctx = b.new_context(storage_state=session_file("x"), locale="pl-PL")
        pg = ctx.new_page()
        pg.on("response", lambda r: bodies.append(r) if "SearchTimeline" in r.url else None)
        pg.goto(f"https://x.com/search?q={quote(query)}&f=live", wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(5000)
        for _ in range(scrolls):
            pg.mouse.wheel(0, 4000)
            pg.wait_for_timeout(2500)
        notes.update(final_url=pg.url[:120], graphql_responses=len(bodies))
        tweets = {}
        for r in bodies:
            try:
                for t in walk(r.json()):
                    tweets[t["rest_id"]] = t
            except Exception as e:
                notes.setdefault("parse_errors", []).append(str(e)[:100])
        b.close()
    for tid, t in tweets.items():
        lg, user = t["legacy"], t.get("core", {}).get("user_results", {}).get("result", {})
        handle = user.get("core", {}).get("screen_name") or user.get("legacy", {}).get("screen_name")
        yield envelope(
            url=f"https://x.com/{handle}/status/{tid}", source="x", collector="x_posts.session", content_type="post",
            text=lg.get("full_text", ""), published_at=lg.get("created_at"), author=handle,
            links=[u.get("expanded_url") for u in lg.get("entities", {}).get("urls", [])],
            source_meta={"query": query, "tweet_id": tid, "lang": lg.get("lang"), "favorites": lg.get("favorite_count"),
                         "retweets": lg.get("retweet_count"), "views": t.get("views", {}).get("count")},
        )
