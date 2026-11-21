"""Save a login session for session-based collectors. A visible Chrome window opens; YOU log in
manually (test account), then press Enter here. Playwright storage_state is written to
UKNF/.secrets/<platform>_state.json (gitignored). Usage: python -m login fb|ig|x"""
import sys

from playwright.sync_api import sync_playwright

from common import SESSIONS

START = {"fb": "https://www.facebook.com/login", "ig": "https://www.instagram.com/accounts/login/",
         "x": "https://x.com/i/flow/login"}


def main(platform: str):
    SESSIONS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=False)
        ctx = b.new_context(locale="pl-PL", viewport={"width": 1280, "height": 900})
        ctx.new_page().goto(START[platform])
        input(f"Log in to {platform} in the Chrome window, then press Enter here... ")
        out = SESSIONS / f"{platform}_state.json"
        ctx.storage_state(path=out)
        print(f"saved {out}")
        b.close()


if __name__ == "__main__":
    main(sys.argv[1])
