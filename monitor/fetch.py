"""Render a page with Playwright (1440x900, pl-PL), reject cookies, return visible text lines + risk-warning geometry.

Reuses robots/cookie/challenge handling from scrapers/poc/firm_web/collect_site.py. Bot challenges are recorded, never bypassed.
"""
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scrapers" / "poc"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scrapers" / "poc" / "firm_web"))
from collect_site import BLOCK_RE, UA_DESKTOP, reject_cookies, robots_allows  # noqa: E402

from monitor.extract import WARNING_RE  # noqa: E402

VIEWPORT = (1440, 900)

# Visible text per block element (in document order) + y of blocks matching the CFD warning regex.
# Cookie/consent containers and hidden elements are skipped.
JS_TEXT = r"""
(warnSrc) => {
  const warnRe = new RegExp(warnSrc, 'i');
  const skip = el => el.closest('#onetrust-consent-sdk, #CybotCookiebotDialog, #usercentrics-root, [id*=cookie i], [class*=cookie i], [aria-label*=cookie i], script, style, noscript, template, svg');
  const isBlock = el => !/^inline/.test(getComputedStyle(el).display) || el === document.body;
  const blocks = new Map();
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const t = n.textContent.replace(/\s+/g, ' ').trim(); if (!t) continue;
    const p = n.parentElement; if (!p || skip(p)) continue;
    let b = p; while (b.parentElement && !isBlock(b)) b = b.parentElement;
    if (!blocks.has(b)) blocks.set(b, []);
    blocks.get(b).push(t);
  }
  const lines = [], warn = [];
  for (const [el, parts] of blocks) {
    const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    if (!(r.width > 0 && r.height > 0) || cs.visibility === 'hidden') continue;
    const text = parts.join(' ');
    lines.push(text);
    if (warnRe.test(text)) warn.push({ text, top: Math.round(r.top + scrollY) });
  }
  return { lines, warn, vh: innerHeight, title: document.title };
}
"""


def fetch_robots(browser, url, cache):
    host = urlsplit(url).scheme + "://" + urlsplit(url).netloc
    if host not in cache:
        ctx = browser.new_context(user_agent=UA_DESKTOP)
        try:
            r = ctx.request.get(host + "/robots.txt", timeout=30000)
            body = r.text()
            cache[host] = body if "user-agent" in body.lower() else None
        except Exception:
            cache[host] = None
        ctx.close()
    txt = cache[host]
    return robots_allows(txt, url)[0] if txt else None


def fetch_page(browser, url):
    w, h = VIEWPORT
    ctx = browser.new_context(viewport={"width": w, "height": h}, locale="pl-PL", timezone_id="Europe/Warsaw",
                              user_agent=UA_DESKTOP, extra_http_headers={"Accept-Language": "pl-PL,pl;q=0.9"})
    page = ctx.new_page()
    res = {"url": url}
    try:
        resp = page.goto(url, wait_until="domcontentloaded", timeout=60000)
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass
        page.wait_for_timeout(2000)
        res["http_status"] = resp.status if resp else None
        res["final_url"] = page.url
        title = page.title()
        challenge = page.locator("iframe[src*='challenges.cloudflare.com'], iframe[src*='recaptcha'], iframe[src*='hcaptcha']").count()
        if res["http_status"] in (404, 410):
            return res
        same_host = urlsplit(page.url).netloc == urlsplit(url).netloc  # plus500: 403 on a cross-host landing page with content
        if ((res["http_status"] or 0) >= 400 and same_host) or BLOCK_RE.search(title or "") or challenge:
            res["blocked"] = {"status": res["http_status"], "title": title, "challenge_iframe": challenge}
            return res
        reject_cookies(page)
        page.wait_for_timeout(1000)
        for y in range(0, min(page.evaluate("document.documentElement.scrollHeight"), 20 * h), h):  # lazy content
            page.evaluate(f"window.scrollTo(0, {y})")
            page.wait_for_timeout(120)
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(500)
        data = page.evaluate(JS_TEXT, WARNING_RE.pattern)
        res.update(lines=data["lines"], warn=data["warn"], vh=data["vh"], title=data["title"])
    except Exception as e:
        res["error"] = f"{type(e).__name__}: {e}"[:300]
    finally:
        ctx.close()
    return res
