"""Google/YouTube ads, no login, no browser: Google Ads Transparency Center internal RPC (the calls the
site itself makes). query = domain(s) ("xtb.com,bossa.pl") or advertiser name ("XTB" -> SearchSuggestions).
Region PL = 2616. RPC shapes follow the fejker repo (ftf/sources.py _gatc).

Text: creatives that render via content.js (preview service) -> embedded ad HTML -> `text`.
Image creatives: image saved to results/google_ads.atc_rpc/images/, path in source_meta.image_refs
(target: MinIO), `text` left empty for the OCR preprocessing step."""
import hashlib
import json
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from curl_cffi import requests
from selectolax.lexbor import LexborHTMLParser

from common import RESULTS, envelope

BASE = "https://adstransparency.google.com/anji/_/rpc/SearchService/"
PL = 2616
FORMAT = {1: "text", 2: "image", 3: "video"}
IMG_DIR = RESULTS / "google_ads.atc_rpc" / "images"
HTML_ARG = re.compile(r"insertPreviewHtmlContent\('[^']*',\s*'[^']*',\s*'((?:\\.|[^'\\])*)'")
IMG_ARG = re.compile(r"insertPreviewImageContent\('[^']*',\s*'[^']*',\s*'([^']+)'")
BIDI = re.compile("[⁦-⁩‎‏]")
URL = re.compile(r"https?://[^\"\\<> ]+")


def rpc(name, req):
    r = requests.post(BASE + name + "?authuser=", impersonate="chrome", timeout=40,
                      headers={"origin": "https://adstransparency.google.com",
                               "referer": "https://adstransparency.google.com/?region=PL"},
                      data={"f.req": json.dumps(req, separators=(",", ":"))})
    r.raise_for_status()
    return r.json()


def day(v):
    s = str(v or "")
    return f"{s[:4]}-{s[4:6]}-{s[6:]}" if len(s) == 8 else None


def creative_regions(adv, cr):
    """Countries where the creative was shown (GetCreativeById field 17; region id = 2000 + ISO 3166 numeric)
    and the PL impressions band and dates. SearchCreatives with region PL also returns multi-country creatives."""
    r = requests.post("https://adstransparency.google.com/anji/_/rpc/LookupService/GetCreativeById?authuser=",
                      impersonate="chrome", timeout=40,
                      headers={"origin": "https://adstransparency.google.com",
                               "referer": "https://adstransparency.google.com/?region=PL"},
                      data={"f.req": json.dumps({"1": adv, "2": cr, "5": {"1": 1, "2": 0, "3": PL}}, separators=(",", ":"))})
    r.raise_for_status()
    stats = (r.json().get("1") or {}).get("17") or []
    pl = next((s for s in stats if s.get("1") == PL), {})
    return {"regions_iso_numeric": sorted(s["1"] - 2000 for s in stats if s.get("1")),
            "pl_only": [s.get("1") for s in stats] == [PL],
            "pl_impressions_min": pl.get("3"), "pl_first_shown": day(pl.get("4") or pl.get("7")),
            "pl_last_shown": day(pl.get("5"))}


def epoch(v):
    return datetime.fromtimestamp(int(v), timezone.utc).isoformat() if v else None


def unjs(s):
    s = re.sub(r"\\x([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), s)
    s = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), s)
    return re.sub(r"\\(.)", r"\1", s)


def html_text(html):
    doc = LexborHTMLParser(html)
    for n in doc.css("script,style,noscript,head"):
        n.decompose()
    return " ".join(doc.body.text(separator=" ").split()) if doc.body else ""


def content_js(url):
    """-> (texts from embedded HTML previews, image urls) of one preview-service content.js."""
    t = requests.get(url, impersonate="chrome", timeout=40).text
    texts = [x for x in (html_text(unjs(m.group(1))) for m in HTML_ARG.finditer(t)) if x]
    return list(dict.fromkeys(texts)), IMG_ARG.findall(t)


def save_image(url):
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):  # image CDN drops connections on weak networks (hotspot)
        try:
            r = requests.get(url, impersonate="chrome", timeout=40)
            r.raise_for_status()
            break
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))
    ext = {"image/png": ".png", "image/gif": ".gif", "image/webp": ".webp"}.get(r.headers.get("content-type", ""), ".jpg")
    p = IMG_DIR / (hashlib.sha256(r.content).hexdigest()[:20] + ext)
    p.write_bytes(r.content)
    return str(p)


def filters(query, notes):
    out = []
    for q in (x.strip() for x in query.split(",") if x.strip()):
        if "." in q:
            out.append(("domain", q, {"12": {"1": q, "2": True}, "8": [PL]}))
            continue
        sug = rpc("SearchSuggestions", {"1": q, "2": 10, "3": 10}).get("1", [])
        advs = [s["1"] for s in sug if "1" in s]
        notes.setdefault("advertisers", []).extend({"name": a.get("1"), "id": a.get("2"), "country": a.get("3")} for a in advs)
        out += [("advertiser", a.get("1"), {"12": {"1": "", "2": True}, "13": {"1": [a["2"]]}, "8": [PL]}) for a in advs[:2]]
    return out


def creative_doc(c, kind, label, notes, fetch_text, fetch_images, fetch_regions=False):
    body = json.dumps(c.get("3") or {}, ensure_ascii=False)
    urls = URL.findall(body)
    cjs = next((u for u in urls if "content.js" in u), None)
    imgs = [u for u in urls if "content.js" not in u]
    texts, image_refs, render = [], [], "image" if imgs else None
    if fetch_text and cjs:
        render = "content.js"
        try:
            texts, more = content_js(cjs)
            imgs += more
        except Exception:
            notes["content_js_errors"] += 1
    if fetch_images and not texts:
        for u in imgs[:1]:
            try:
                image_refs.append(save_image(u))
            except Exception:
                notes["image_errors"] += 1
    adv, cr = c.get("1"), c.get("2")
    regions = {}
    if fetch_regions:  # one GetCreativeById per creative; in parallel it triggers HTTP 429
        try:
            regions = creative_regions(adv, cr)
        except Exception:
            notes["region_errors"] = notes.get("region_errors", 0) + 1
    return envelope(
        url=f"https://adstransparency.google.com/advertiser/{adv}/creative/{cr}?region=PL",
        source="google_ads_transparency", collector="google_ads.atc_rpc", content_type="ad",
        text=BIDI.sub("", "\n".join(texts)),
        published_at=epoch((c.get("6") or {}).get("1") if isinstance(c.get("6"), dict) else None),
        author=c.get("12"), sponsor=c.get("12"), links=imgs[:3],
        source_meta={"query": label, "match": kind, "advertiser_id": adv, "creative_id": cr,
                     "domain": c.get("14"), "format": FORMAT.get(c.get("4"), c.get("4")), **regions,
                     "render": render, "text_source": "content.js" if texts else None, "image_refs": image_refs,
                     "last_shown": epoch((c.get("7") or {}).get("1") if isinstance(c.get("7"), dict) else None)},
    )


def collect(query, notes, pages=2, fetch_text=True, fetch_images=True, workers=8, fetch_regions=False, pause=(3, 7)):
    notes.update(pages={}, content_js_errors=0, image_errors=0)
    with ThreadPoolExecutor(workers) as pool:
        for kind, label, flt in filters(query, notes):
            token, n = None, 0
            for _ in range(pages):
                req = {"2": 40, "3": flt, "7": {"1": 1, "2": 0, "3": PL}}
                if token:
                    req["4"] = token
                time.sleep(random.uniform(*pause))
                js = rpc("SearchCreatives", req)
                cs = js.get("1", [])
                n += len(cs)
                yield from pool.map(lambda c: creative_doc(c, kind, label, notes, fetch_text, fetch_images,
                                                           fetch_regions), cs)
                token = js.get("2")
                if not token:
                    break
            notes["pages"][label] = n
