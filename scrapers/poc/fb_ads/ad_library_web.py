"""FB + IG ads, no login: Meta Ad Library web page via Playwright. FEASIBILITY PROBE ONLY:
Meta terms allow automated collection only via Platform APIs; production = fb_ads.ad_library_api."""
import hashlib
import re
from urllib.parse import quote

from playwright.sync_api import sync_playwright

from common import envelope, ua

ID_RE = re.compile(r"Identyfikator biblioteki: (\d+)")
# Per ad card: first media >= 150 px wide; <img> src = creative, <video> poster = video thumbnail. Cards whose creative
# is not a plain image or poster (lazy player, CSS background) are marked `data-iw-ad` for an element screenshot.
JS_MEDIA = r"""() => {
  const out = {};
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = w.nextNode(); n; n = w.nextNode()) {
    const m = /Identyfikator biblioteki: (\d+)/.exec(n.textContent); if (!m || out[m[1]]) continue;
    let card = null, found = null;
    for (let el = n.parentElement, d = 0; el && d < 12; el = el.parentElement, d++) {
      if ((el.innerText.match(/Identyfikator biblioteki/g) || []).length > 1) break;
      card = el;
      const x = [...el.querySelectorAll('img, video')].find(x => x.getBoundingClientRect().width >= 150);
      const src = x ? (x.tagName === 'VIDEO' ? x.poster : x.currentSrc || x.src) : '';
      if (src) { found = { src, kind: x.tagName === 'VIDEO' ? 'thumbnail' : 'creative' }; break; }
    }
    if (found) out[m[1]] = found;
    else if (card && card.getBoundingClientRect().height >= 200) { card.dataset.iwAd = m[1]; out[m[1]] = { src: '', kind: 'screenshot' }; }
  }
  return out;
}"""


def save_media(pg, found, media_dir):
    """Download creative/poster URLs or screenshot the ad card (same browser context) -> {ad_id: (path, kind)};
    failures are skipped."""
    out = {}
    for ad_id, m in found.items():
        try:
            if m["src"]:
                r = pg.request.get(m["src"], timeout=30000)
                body = r.body() if r.ok else None
            else:
                body = pg.locator(f'[data-iw-ad="{ad_id}"]').first.screenshot(timeout=15000)
        except Exception:
            continue
        if not body:
            continue
        path = media_dir / (hashlib.sha1(body).hexdigest()[:20] + (".jpg" if m["src"] else ".png"))
        path.write_bytes(body)
        out[ad_id] = (str(path), m["kind"])
    return out


def collect(query, notes, scrolls=0, media_dir=None):
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
        media = {}
        if media_dir:
            media_dir.mkdir(parents=True, exist_ok=True)
            found = pg.evaluate(JS_MEDIA)
            media = save_media(pg, found, media_dir)
            notes.update(media_found=len(found), media_saved=len(media))
        b.close()
    notes.update(login_wall="Zaloguj się" in body[:3000], body_chars=len(body))
    for ch in re.split(r"(?=Identyfikator biblioteki: \d+)", body)[1:]:
        ad_id = ID_RE.search(ch).group(1)
        lines = [l for l in ch.splitlines() if l.strip()]
        spons = next((lines[i - 1] for i, l in enumerate(lines) if l.strip() in ("Sponsorowane", "Sponsored")), None)
        meta = {"query": query, "ad_id": ad_id, "period": lines[1] if len(lines) > 1 else None}
        if ad_id in media:
            meta.update(image_refs=[media[ad_id][0]], image_source=media[ad_id][1])
        yield envelope(
            url=f"https://www.facebook.com/ads/library/?id={ad_id}", source="meta_ad_library",
            collector="fb_ads.ad_library_web", content_type="ad", text="\n".join(lines[:40]),
            author=spons, sponsor=spons, source_meta=meta,
        )
