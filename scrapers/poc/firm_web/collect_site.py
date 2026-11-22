"""Firm websites (M2): Playwright renders each URL at 1440/768/375 px and stores raw visual measurements (D3).

Per page and viewport: full-page screenshot, `text_blocks` (font_px, color, bg, contrast, bbox, visible, occluded,
in_footer, truncated) and a summary of blocks matching the risk-warning regex. Verdicts and thresholds stay in M2.
Cookie banners: only a "reject" / "only necessary" button is clicked; consent is never accepted.
Bot challenges (Cloudflare, captcha) are recorded and the page is skipped, never bypassed.

  python firm_web/collect_site.py [url ...]      # default: URLS below
"""
import json
import random
import re
import sys
import time
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright

from common import RESULTS, now, url_key

OUT = RESULTS / "firm_web"
SHOTS = OUT / "shots"
BLOCKS = OUT / "blocks"
SAMPLE = Path(__file__).resolve().parents[3] / "data" / "samples" / "firm_web_v1.jsonl"
VIEWPORTS = {1440: (1440, 900), 768: (768, 1024), 375: (375, 812)}
UA_DESKTOP = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0 Safari/537.36"
UA_MOBILE = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0 Mobile Safari/537.36"
FIRMS = {  # domain -> entity name as in the KNF register
    "xtb.com": "XTB S.A.",
    "etoro.com": "Etoro (Europe) Ltd",
    "plus500.com": "Plus500CY Ltd",
    "trading212.com": "Trading 212 Markets Ltd",
    "revolut.com": "Revolut Securities Europe UAB",
}
URLS = [
    "https://www.xtb.com/pl", "https://www.xtb.com/pl/indeksy-gieldowe", "https://www.xtb.com/pl/etf",
    "https://www.xtb.com/pl/odsetki",
    "https://www.etoro.com/pl/", "https://www.etoro.com/pl/trading/cfd/",
    "https://www.etoro.com/pl/investing/interest-on-balance/", "https://www.etoro.com/pl/invite/",
    "https://www.plus500.com/pl/",
    "https://www.trading212.com/pl",
    "https://www.revolut.com/pl-PL/", "https://www.revolut.com/pl-PL/stock-trading/", "https://www.revolut.com/pl-PL/etfs/",
]
RISK_RE = (r"rachunk\w* inwestor\w* detaliczn\w*|trac\w* pieniądze|traci\w* pieniądz\w*|może(?:sz)? stracić"
           r"|utrat\w* (?:części|całości|środków|kapitału)|ryzyk\w*|zagrożon\w*|narażon\w* na ryzyko|wzrosnąć lub spaść"
           r"|retail investor accounts lose|lose money|capital (?:is )?at risk")
PROFIT_RE = r"zysk\w*|zarab\w*|0\s?% prowizji|bez prowizji|bonus\w*|darmow\w*|oprocentowan\w*|odsetk\w*|zwrot\w*|\bdo \d+[,.]?\d*\s?%"
REJECT_RE = re.compile(r"^\s*(odrzuć|odrzuc|odrzucam|nie zgadzam się|tylko niezbędne|tylko wymagane|tylko konieczne"
                       r"|zezwól tylko na niezbędne|wyłącz wszystkie|kontynuuj bez akceptacji|reject|reject all|decline|only necessary"
                       r"|necessary only|use necessary cookies only)", re.I)
REJECT_SELECTORS = ["#onetrust-reject-all-handler", "#CybotCookiebotDialogBodyButtonDecline",
                    "button[data-testid='uc-deny-all-button']", "[data-cookiebanner='reject_button']"]
BLOCK_RE = re.compile(r"just a moment|cierpliwości|not a robot|attention required|access denied|verify you are human|captcha|security check", re.I)

# Each text node is assigned to its nearest non-inline ancestor ("block"); font_px = char-weighted mode in the block.
JS_BLOCKS = r"""
([riskSrc, profitSrc]) => {
  const riskRe = new RegExp(riskSrc, 'i'), profitRe = new RegExp(profitSrc, 'i');
  const lum = c => { const v = c / 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
  const rgba = s => { const m = (s || '').match(/[\d.]+/g); if (!m) return null;
    return [ +m[0], +m[1], +m[2], m.length > 3 ? +m[3] : 1 ]; };
  const L = c => 0.2126 * lum(c[0]) + 0.7152 * lum(c[1]) + 0.0722 * lum(c[2]);
  const contrast = (a, b) => { const x = L(a), y = L(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const bgOf = el => { let bgImage = false;
    for (let e = el; e && e.nodeType === 1; e = e.parentElement) { const cs = getComputedStyle(e);
      if (cs.backgroundImage && cs.backgroundImage !== 'none') bgImage = true;
      const c = rgba(cs.backgroundColor); if (c && c[3] > 0.5) return [c, bgImage]; }
    return [[255, 255, 255, 1], bgImage]; };
  const opacityOf = el => { let o = 1; for (let e = el; e && e.nodeType === 1; e = e.parentElement) o *= +getComputedStyle(e).opacity; return o; };
  const isBlock = el => !/^inline/.test(getComputedStyle(el).display) || el === document.body;
  const desc = e => e ? (e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') +
      (typeof e.className === 'string' && e.className.trim() ? '.' + e.className.trim().split(/\s+/).slice(0, 3).join('.') : '')) : null;
  const vw = innerWidth, vh = innerHeight, sy = scrollY;
  const blocks = new Map();
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const t = n.textContent.replace(/\s+/g, ' ').trim(); if (!t) continue;
    const p = n.parentElement; if (!p || /^(SCRIPT|STYLE|NOSCRIPT|TEMPLATE|SVG)$/i.test(p.tagName)) continue;
    let b = p; while (b.parentElement && !isBlock(b)) b = b.parentElement;
    if (!blocks.has(b)) blocks.set(b, { parts: [], fonts: {} });
    const rec = blocks.get(b), fs = parseFloat(getComputedStyle(p).fontSize);
    rec.parts.push(t); rec.fonts[fs] = (rec.fonts[fs] || 0) + t.length;
  }
  const out = [];
  for (const [el, rec] of blocks) {
    const text = rec.parts.join(' ');
    const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    const fonts = Object.entries(rec.fonts).sort((a, b) => b[1] - a[1]);
    const color = rgba(cs.color) || [0, 0, 0, 1], [bg, bgImage] = bgOf(el), op = opacityOf(el);
    const visible = r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && op > 0.05;
    const overflowHidden = /hidden|clip/.test(cs.overflow + cs.overflowX);
    out.push({
      i: out.length, text: text.slice(0, 2000), chars: text.length, tag: el.tagName.toLowerCase(), el: desc(el),
      font_px: +fonts[0][0], font_px_min: Math.min(...fonts.map(f => +f[0])), font_weight: cs.fontWeight,
      color: cs.color, bg: `rgba(${bg.join(', ')})`, bg_image: bgImage, opacity: +op.toFixed(2),
      contrast: +contrast(color, bg).toFixed(2),
      bbox: [Math.round(r.left), Math.round(r.top + sy), Math.round(r.width), Math.round(r.height)],
      visible, above_fold: visible && r.top + sy < vh,
      offscreen_x: visible && (r.right > vw + 1 || r.left < -1),
      truncated: visible && overflowHidden && (el.scrollWidth > el.clientWidth + 1 || el.scrollHeight > el.clientHeight + 1),
      position: cs.position,
      fixed: (() => { for (let e = el; e && e.nodeType === 1; e = e.parentElement) {
        const p = getComputedStyle(e).position; if (p === 'fixed' || p === 'sticky') return p; } return null; })(),
      in_footer: !!el.closest('footer, [role=contentinfo]'),
      legal_hint: !!el.closest('[class*=legal i], [id*=legal i], [class*=disclaimer i], [id*=disclaimer i], [class*=footnote i], [class*=risk i], [id*=risk i]'),
      risk: riskRe.test(text), profit: profitRe.test(text),
    });
    out[out.length - 1]._el = el;
  }
  window.__iw_blocks = out.map(o => o._el);
  out.forEach(o => delete o._el);
  return { blocks: out, page_h: document.documentElement.scrollHeight, vw, vh,
           scroll_w: document.documentElement.scrollWidth, title: document.title, lang: document.documentElement.lang };
}
"""

# Occlusion: scroll block into view, hit-test 5 points of its on-screen part; anything not inside the block covers it.
JS_OCCLUDED = r"""
(idx) => idx.map(i => {
  const el = window.__iw_blocks[i]; if (!el) return null;
  el.scrollIntoView({ block: 'center' });
  const r = el.getBoundingClientRect();
  const x0 = Math.max(0, r.left), x1 = Math.min(innerWidth - 1, r.right), y0 = Math.max(0, r.top), y1 = Math.min(innerHeight - 1, r.bottom);
  if (x1 <= x0 || y1 <= y0) return { i, occluded: null, occluded_frac: null, occluded_by: null };
  const d = e => e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + (typeof e.className === 'string' && e.className.trim() ? '.' + e.className.trim().split(/\s+/)[0] : '');
  const pts = [[.5, .5], [.1, .15], [.9, .15], [.1, .85], [.9, .85]];
  const by = [];
  for (const [fx, fy] of pts) {
    const hit = document.elementFromPoint(x0 + (x1 - x0) * fx, y0 + (y1 - y0) * fy);
    if (hit && hit !== el && !el.contains(hit) && !hit.contains(el)) {
      let f = null; for (let e = hit; e && e.nodeType === 1; e = e.parentElement) { const p = getComputedStyle(e).position; if (p === 'fixed' || p === 'sticky') { f = p; break; } }
      by.push(d(hit) + (f ? ' [' + f + ']' : ''));
    }
  }
  return { i, occluded: by.length > 0, occluded_frac: by.length / pts.length, occluded_by: by[0] || null };
})
"""


def firm_of(url):
    host = urlsplit(url).netloc.lower().removeprefix("www.")
    return next((v for k, v in FIRMS.items() if host.endswith(k)), host)


def slug(url):
    p = urlsplit(url)
    return re.sub(r"[^a-z0-9]+", "_", (p.netloc.removeprefix("www.") + p.path).lower()).strip("_")


def robots_allows(robots_txt, url):
    """`User-agent: *` group, longest-match Allow/Disallow with `*` and `$` wildcards (Google semantics)."""
    rules, active, path = [], False, urlsplit(url).path or "/"
    if urlsplit(url).query:
        path += "?" + urlsplit(url).query
    for line in robots_txt.splitlines():
        line = line.split("#")[0].strip()
        if ":" not in line:
            continue
        k, v = (s.strip() for s in line.split(":", 1))
        if k.lower() == "user-agent":
            active = v == "*"
        elif active and k.lower() in ("allow", "disallow") and v:
            rx = "^" + re.escape(v).replace(r"\*", ".*").replace(r"\$", "$")
            if not v.startswith(("/", "*")):
                rx = "^/" + rx[1:]
            rules.append((len(v), k.lower() == "allow", rx))
    hits = sorted((r for r in rules if re.match(r[2], path)), key=lambda r: (r[0], r[1]))
    return (hits[-1][1], hits[-1]) if hits else (True, None)


def _click(loc):
    try:
        loc.click(timeout=5000)
        return {}
    except Exception:
        try:
            loc.click(timeout=5000, force=True)
            return {"forced": True}
        except Exception as e:
            return {"click_error": str(e)[:120]}


def reject_cookies(page, tries=3):
    for _ in range(tries):  # consent banners often render a few seconds after load
        found = _reject_once(page)
        if found:
            return found
        page.wait_for_timeout(1500)
    banner = page.evaluate("""() => [...document.querySelectorAll('body *')].some(e => {
        const cs = getComputedStyle(e); return (cs.position === 'fixed' || cs.position === 'sticky') &&
        e.offsetHeight > 40 && /cookie|ciasteczk|pliki cookie/i.test(e.innerText || ''); })""")
    return {"clicked": None, "banner_without_reject": banner}


def _reject_once(page):
    for fr in page.frames:
        for sel in REJECT_SELECTORS:
            loc = fr.locator(sel)
            if loc.count() and loc.first.is_visible():
                return {"clicked": sel, **_click(loc.first)}
        loc = fr.get_by_role("button", name=REJECT_RE)
        for j in range(loc.count()):
            if loc.nth(j).is_visible():
                label = loc.nth(j).inner_text().strip()
                return {"clicked": label, **_click(loc.nth(j))}
    return None


def measure(browser, url, vw):
    w, h = VIEWPORTS[vw]
    mobile = vw == 375
    ctx = browser.new_context(viewport={"width": w, "height": h}, locale="pl-PL", timezone_id="Europe/Warsaw",
                              user_agent=UA_MOBILE if mobile else UA_DESKTOP, is_mobile=mobile, has_touch=mobile,
                              extra_http_headers={"Accept-Language": "pl-PL,pl;q=0.9"})
    page = ctx.new_page()
    res = {"viewport": vw}
    try:
        resp = page.goto(url, wait_until="domcontentloaded", timeout=60000)
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            res["networkidle_timeout"] = True
        page.wait_for_timeout(2500)
        res["status"], res["final_url"], res["title"] = (resp.status if resp else None), page.url, page.title()
        challenge = page.locator("iframe[src*='challenges.cloudflare.com'], iframe[src*='recaptcha'], iframe[src*='hcaptcha'], iframe[src*='captcha-delivery.com'], iframe[id^='ddChallenge']").count()
        same_host = urlsplit(page.url).netloc == urlsplit(url).netloc
        if page.url.rstrip("/") != (resp.url if resp else url).rstrip("/"):
            res["redirected_to"] = page.url
        if ((res["status"] or 0) >= 400 and same_host) or BLOCK_RE.search(res["title"] or "") or challenge:
            res["blocked"] = {"status": res["status"], "title": res["title"], "challenge_iframe": challenge}
            page.screenshot(path=str(SHOTS / f"{slug(url)}_{vw}_blocked.png"))
            return res
        res["cookies"] = reject_cookies(page)
        page.wait_for_timeout(1500)
        for y in range(0, page.evaluate("document.documentElement.scrollHeight"), h):  # trigger lazy content
            page.evaluate(f"window.scrollTo(0, {y})")
            page.wait_for_timeout(150)
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(800)
        shot = SHOTS / f"{slug(url)}_{vw}.png"
        page.screenshot(path=str(shot), full_page=True)
        res["screenshot_ref"] = str(shot.relative_to(RESULTS.parent))
        data = page.evaluate(JS_BLOCKS, [RISK_RE, PROFIT_RE])
        blocks = data.pop("blocks")
        risk_idx = [b["i"] for b in blocks if b["risk"]][:60]
        for o in page.evaluate(JS_OCCLUDED, risk_idx) or []:
            if o:
                blocks[o["i"]].update(occluded=o["occluded"], occluded_frac=o["occluded_frac"], occluded_by=o["occluded_by"])
        pixel_contrast(shot, [b for b in blocks if b["risk"] and b["visible"]])
        res.update(data)
        res["text_blocks"] = blocks
    except Exception as e:
        res["error"] = f"{type(e).__name__}: {e}"[:300]
    finally:
        ctx.close()
    return res


def _lum(rgb):
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(rgb[0] / 255) + 0.7152 * f(rgb[1] / 255) + 0.0722 * f(rgb[2] / 255)


def _contrast(a, b):
    x, y = _lum(a), _lum(b)
    return (max(x, y) + 0.05) / (min(x, y) + 0.05)


def pixel_contrast(shot, blocks):
    """Background read from screenshot pixels (DOM misses text over images/overlays): pixels far from the text
    colour inside the bbox = background; contrast_px vs their median, contrast_px_p10 vs the worst 10%."""
    from PIL import Image
    img = Image.open(shot).convert("RGB")
    for b in blocks:
        x, y, w, h = b["bbox"]
        box = (max(0, x), max(0, y), min(img.width, x + w), min(img.height, y + h))
        if box[2] - box[0] < 2 or box[3] - box[1] < 2:
            continue
        crop = img.crop(box)
        crop.thumbnail((400, 120))
        fg = [int(v) for v in re.findall(r"\d+", b["color"])[:3]]
        bg = [px for px in crop.getdata() if max(abs(px[i] - fg[i]) for i in range(3)) > 60]
        if len(bg) < 20:
            continue
        med = [sorted(c)[len(c) // 2] for c in zip(*bg)]
        cs = sorted(_contrast(fg, px) for px in bg)
        b["bg_px"] = "rgb({}, {}, {})".format(*med)
        b["contrast_px"] = round(_contrast(fg, med), 2)
        b["contrast_px_p10"] = round(cs[len(cs) // 10], 2)


def dominant_font(blocks):
    c = Counter()
    for b in blocks:
        if b["visible"]:
            c[b["font_px"]] += b["chars"]
    return c.most_common(1)[0][0] if c else None


def risk_summary(res):
    blocks = res.get("text_blocks") or []
    dom = dominant_font(blocks)
    risk = [b for b in blocks if b["risk"]]
    strong = [b for b in risk if re.search(r"rachunk\w* inwestor|trac\w* pieniądz|lose money", b["text"], re.I)]
    pick = [b for b in strong if b["visible"]] or strong or [b for b in risk if b["visible"]]
    best = min(pick, key=lambda b: b["bbox"][1]) if pick else None
    profit = [b for b in blocks if b["profit"] and b["visible"]]
    first = min((b for b in risk if b["visible"]), key=lambda b: b["bbox"][1], default=None)
    s = {"viewport": res["viewport"], "dominant_font_px": dom, "page_h": res.get("page_h"),
         "dominant_font_px_main": dominant_font([b for b in blocks if not (b["in_footer"] or b["legal_hint"] or b["risk"])]),
         "risk_blocks": len(risk), "cfd_warning_blocks": len(strong), "profit_blocks": len(profit),
         "first_profit_y": min((b["bbox"][1] for b in profit), default=None),
         "horizontal_overflow": (res.get("scroll_w") or 0) > (res.get("vw") or 0) + 1}
    if best:
        s["disclaimer"] = {
            "text": best["text"][:600], "block": best["i"], "el": best["el"], "font_px": best["font_px"],
            "font_ratio": round(best["font_px"] / dom, 2) if dom else None, "contrast": best["contrast"],
            "contrast_px": best.get("contrast_px"), "contrast_px_p10": best.get("contrast_px_p10"),
            "bg_image": best["bg_image"], "y": best["bbox"][1],
            "y_ratio": round(best["bbox"][1] / res["page_h"], 3) if res.get("page_h") else None,
            "visible": best["visible"], "above_fold": best["above_fold"], "fixed": best["fixed"],
            "occluded": best.get("occluded"), "occluded_frac": best.get("occluded_frac"), "occluded_by": best.get("occluded_by"),
            "in_footer": best["in_footer"], "legal_hint": best["legal_hint"],
            "truncated": best["truncated"], "offscreen_x": best["offscreen_x"]}
    if first:
        s["first_risk"] = {"text": first["text"][:300], "block": first["i"], "font_px": first["font_px"],
                           "font_ratio": round(first["font_px"] / dom, 2) if dom else None, "y": first["bbox"][1],
                           "contrast_px": first.get("contrast_px"), "in_footer": first["in_footer"], "fixed": first["fixed"]}
    return s


def page_text(blocks):
    return "\n".join(b["text"] for b in blocks if b["visible"])


def collect(query, notes):
    urls = [u.strip() for u in (query.split(",") if isinstance(query, str) else query) if u.strip()]
    SHOTS.mkdir(parents=True, exist_ok=True)
    BLOCKS.mkdir(parents=True, exist_ok=True)
    docs, robots_cache = [], {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for n, url in enumerate(urls):
            if n:
                time.sleep(random.uniform(2, 5))
            host = urlsplit(url).scheme + "://" + urlsplit(url).netloc
            nt = notes.setdefault(url, {})
            if host not in robots_cache:
                ctx = browser.new_context(user_agent=UA_DESKTOP)
                try:
                    r = ctx.new_page().goto(host + "/robots.txt", timeout=30000)
                    body = r.text() if r else ""
                    robots_cache[host] = {"status": r.status if r else None,
                                          "txt": body if "user-agent" in body.lower() else None}
                except Exception as e:
                    robots_cache[host] = {"status": None, "txt": None, "error": str(e)[:200]}
                ctx.close()
            rb = robots_cache[host]
            allowed, rule = robots_allows(rb["txt"], url) if rb["txt"] else (None, None)
            nt["robots"] = {"status": rb["status"], "parsed": bool(rb["txt"]), "allowed": allowed,
                            "rule": rule[2] if rule else None}
            if allowed is False:
                continue
            per_vp = {}
            for vw in VIEWPORTS:
                per_vp[vw] = measure(browser, url, vw)
                time.sleep(random.uniform(1, 2))
            summaries = {vw: risk_summary(r) for vw, r in per_vp.items() if r.get("text_blocks")}
            nt["viewports"] = {vw: {k: r.get(k) for k in ("status", "title", "redirected_to", "blocked", "cookies", "error", "networkidle_timeout")
                                    if r.get(k) is not None} for vw, r in per_vp.items()}
            nt["risk"] = summaries
            blocks_file = BLOCKS / f"{slug(url)}.json"
            blocks_file.write_text(json.dumps({"url": url, "fetched_at": now(), "viewports": per_vp},
                                              ensure_ascii=False), encoding="utf-8")
            main = per_vp[1440] if per_vp[1440].get("text_blocks") else next((r for r in per_vp.values() if r.get("text_blocks")), None)
            if not main:
                continue
            disc = (summaries.get(1440) or next(iter(summaries.values()))).get("disclaimer") or {}
            docs.append({
                "schema_version": "rawdocument.v1-poc",
                "source": "firm_website",
                "source_url": main.get("final_url") or url,
                "author": firm_of(url),
                "published_at": None,
                "fetched_at": now(),
                "query_keywords": [url],
                "content_keywords": [],
                "text": {"page": page_text(main["text_blocks"]), "risk_disclaimer": disc.get("text", "")},
                "url_key": url_key(main.get("final_url") or url),
                "collector": "firm_web.collect_site",
                "content_type": "web_page",
                "title": main.get("title"),
                "lang": None,
                "source_meta": {
                    "html_lang": main.get("lang"), "robots": nt["robots"],
                    "cookies": {vw: r.get("cookies") for vw, r in per_vp.items()},
                    "screenshot_refs": {vw: r.get("screenshot_ref") for vw, r in per_vp.items() if r.get("screenshot_ref")},
                    "text_blocks_ref": str(blocks_file.relative_to(RESULTS.parent)),
                    "risk_by_viewport": summaries,
                },
            })
        browser.close()
    return docs


if __name__ == "__main__":
    notes = {}
    t0 = time.perf_counter()
    docs = collect(sys.argv[1:] or URLS, notes)
    SAMPLE.parent.mkdir(parents=True, exist_ok=True)
    with SAMPLE.open("w", encoding="utf-8") as f:
        for d in docs:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    (OUT / "summary.json").write_text(json.dumps({"run_at": now(), "seconds": round(time.perf_counter() - t0, 1),
                                                  "records": len(docs), "notes": notes}, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
    print(json.dumps({"records": len(docs), "seconds": round(time.perf_counter() - t0, 1)}))
