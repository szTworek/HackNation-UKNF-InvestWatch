"""Convert fb_ads.ad_library_web PoC docs to the D12-D15 record format (JSONL).

Usage: python convert_fb_ads_web.py INPUT_DOCS_JSON [OUTPUT_JSONL] [YTDLP_DIR]
YTDLP_DIR (optional) holds fb_ads.ytdlp_by_id *-docs.json; their text replaces ad_body.
"""
import glob
import json
import re
import sys
from pathlib import Path

MONTHS = {"sty": 1, "lut": 2, "mar": 3, "kwi": 4, "maj": 5, "cze": 6,
          "lip": 7, "sie": 8, "wrz": 9, "paź": 10, "lis": 11, "gru": 12}
DATE = r"(\d{1,2}) (\w{3}) (\d{4})"
CTAS = {"dowiedz się więcej", "skorzystaj z oferty", "learn more", "zarejestruj się",
        "sign up", "shop now", "zobacz więcej", "kup teraz", "zainstaluj teraz",
        "wyślij wiadomość", "zadzwoń teraz", "pobierz", "download", "get offer"}
NOTICES = ("Ta reklama był wyświetlana", "Te materiały zostały usunięte")
RESTRICTED = "Ta reklama nie jest aktywna dla niektórych odbiorców"
FOOTER = ("Wyświetl więcej", "Stan systemu")
DOMAIN = re.compile(r"^[A-Z0-9][A-Z0-9.-]*\.[A-Z]{2,}(/\S*)?$")
DURATION = re.compile(r"^\d+:\d{2} / \d+:\d{2}$")


def iso(d, m, y):
    return f"{int(y):04d}-{MONTHS[m]:02d}-{int(d):02d}"


def parse_ad(text):
    raw = text.split("\n")
    platform_icons = sum(1 for l in raw if l == "​")
    lines = [l.replace("​", "").strip() for l in raw]
    lines = [l for l in lines if l]
    meta = {}
    m = re.match(r"Identyfikator biblioteki: (\d+)", lines[0])
    meta["library_id"] = m.group(1) if m else None
    sp = lines.index("Sponsorowane")
    head, rest = lines[1:sp - 1], lines[sp + 1:]
    start = end = None
    for l in head:
        r = re.fullmatch(DATE + r" – " + DATE, l)
        if r:
            start, end = iso(*r.group(1, 2, 3)), iso(*r.group(4, 5, 6))
        r = re.fullmatch(r"Rozpoczęcie wyświetlania " + DATE, l)
        if r:
            start = iso(*r.groups())
        r = re.match(r"Liczba reklam wykorzystujących ten materiał reklamowy i tekst: (\d+)", l)
        if r:
            meta["ads_with_same_creative"] = int(r.group(1))
    meta["delivery_end"] = end
    meta["platform_icons"] = platform_icons
    meta["eu_transparency"] = "Transparentność w UE" in head
    meta["multiple_versions"] = "Reklama ma kilka wersji." in head
    meta["has_categories"] = "Kategorie" in head
    meta["restricted_for_some_audiences"] = any(l.startswith(RESTRICTED) for l in head)

    # tail: status, footer, notices
    status = None
    if rest and rest[-1] in ("Aktywna", "Nieaktywna"):
        status = rest.pop()
    for i, l in enumerate(rest):
        if l.startswith(FOOTER):
            rest = rest[:i]
            break
    meta["status"] = status
    notices = [l for l in rest if l.startswith(NOTICES)]
    if any(l.startswith(RESTRICTED) for l in rest):
        meta["restricted_for_some_audiences"] = True
    rest = [l for l in rest if not l.startswith(NOTICES) and not l.startswith(RESTRICTED)]
    if notices:
        meta["notice"] = notices[0]

    meta["has_video"] = any(DURATION.match(l) for l in rest)
    rest = [l for l in rest if not DURATION.match(l)]
    cta = None
    if rest and rest[-1].lower() in CTAS:
        cta = rest.pop()
    domain = title = desc = None
    di = next((i for i, l in enumerate(rest) if DOMAIN.match(l)), None)
    if di is not None:
        domain = rest[di].lower()
        after = rest[di + 1:]
        rest = rest[:di]
        if after:
            title = after[0]
            desc = " ".join(after[1:]) or None
    return start, meta, rest, title, desc, cta, domain


def main():
    src = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parents[1] / "data/samples/meta_ads_sample_v1.jsonl"
    yt_dir = Path(sys.argv[3]) if len(sys.argv) > 3 else src.parents[1] / "fb_ads.ytdlp_by_id"
    yt = {}
    for f in sorted(glob.glob(str(yt_dir / "*-docs.json"))):
        for d in json.load(open(f, encoding="utf8")):
            if d.get("text"):
                yt[d["source_meta"]["ad_id"]] = d["text"].strip()

    docs = json.load(open(src, encoding="utf8"))
    with open(out, "w", encoding="utf8", newline="\n") as fh:
        for d in docs:
            start, meta, body, title, desc, cta, domain = parse_ad(d["text"])
            lib_id = meta["library_id"]
            body_text = "\n".join(body)
            if lib_id in yt:
                body_text = yt[lib_id]
                meta["ad_body_source"] = "ytdlp_by_id"
            else:
                meta["ad_body_source"] = "ad_library_web"
            sections = []
            for typ, val in (("ad_body", body_text), ("title", title),
                             ("link_description", desc), ("cta", cta)):
                if val:
                    sections.append({"type": typ, "text": val})
            rec = {
                "source": "meta_ad_library",
                "source_url": d["url"],
                "author": d["author"],
                "published_at": start,
                "fetched_at": d["fetched_at"],
                "query_keywords": ["forex"],
                "content_keywords": [],
                "text": sections,
                "sponsor": d["author"],
                "links": [domain] if domain else [],
                "content_type": "ad",
                "source_meta": meta,
                "url_key": d["url_key"],
            }
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"wrote {len(docs)} records to {out}")


if __name__ == "__main__":
    main()
