"""One-off: collect records about 5 KNF-registered firms (XTB, eToro, Plus500, Trading 212, Revolut) from
Meta Ad Library (web), Microsoft Ad Library, YouTube Data API and TikTok -> data/samples/<source>_entities_v1.jsonl.

  python build_entities_sample.py meta|bing|youtube|tiktok [extra]
Adds source_meta: firm (query firm), firms_mentioned, advertiser_is_firm, lang_hint_pl."""
import json
import random
import re
import sys
import time

from common import POC_DIR, pl_score, plain_text

FIRMS = {  # firm -> name patterns (lowercase) matched in text, author, links
    "XTB": [r"\bxtb\b", r"x-trade brokers"],
    "eToro": [r"etoro"],
    "Plus500": [r"plus500", r"plus 500"],
    "Trading 212": [r"trading ?212"],
    "Revolut": [r"revolut"],
}
DOMAINS = {"XTB": "xtb.com", "eToro": "etoro.com", "Plus500": "plus500.com", "Trading 212": "trading212.com",
           "Revolut": "revolut.com"}
SAMPLES = POC_DIR.parents[1] / "data" / "samples"


def mentions(s):
    low = (s or "").lower()
    return [f for f, pats in FIRMS.items() if any(re.search(p, low) for p in pats)]


# official channels / accounts (verified badge or channel name checked 2026-11-21); ads use advertiser name match
OFFICIAL = {"meta_ads": {"xtb online investing", "xtb online trading", "etoro", "revolut"},
            "youtube": {"xtb polska", "etoro", "etoro eu"},
            "tiktok": {"xtbpl", "plus500official", "trading212", "revolut", "etoro_official"}}


def tag(doc, firm, official=None):
    blob = " ".join([plain_text(doc), doc.get("title") or "", " ".join(doc.get("links") or []),
                     str((doc.get("source_meta") or {}).get("display_url") or "")])
    m = doc["source_meta"]
    m["firm"] = firm
    m["firms_mentioned"] = sorted(set(mentions(blob)) | set(mentions(doc.get("author"))))
    m["advertiser_is_firm"] = (bool(mentions(doc.get("author"))) if official is None
                               else (doc.get("author") or "").lower() in official)
    m["lang_hint_pl"] = pl_score(plain_text(doc)) >= 2
    return doc


def pause(a=2, b=5):
    time.sleep(random.uniform(a, b))


def retry(fn, tries=4):
    """Retry on network errors (flaky local link); platform refusals (403/429) are raised at once."""
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            if i == tries - 1 or any(c in str(e) for c in ("403", "429")):
                raise
            time.sleep(10 * (i + 1))


def existing(name, key):
    out = SAMPLES / f"{name}_entities_v1.jsonl"
    docs = [json.loads(l) for l in out.open(encoding="utf-8") if l.strip()] if out.exists() else []
    return {key(d): d for d in docs}


def write(name, docs, notes):
    out = SAMPLES / f"{name}_entities_v1.jsonl"
    with out.open("w", encoding="utf-8", newline="\n") as f:
        for d in docs:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    sp = SAMPLES / f"{name}_entities_v1.summary.json"
    old = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else {}
    sp.write_text(json.dumps({**old, **notes}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(out, len(docs), flush=True)


def bing(only=None):
    from bing_ads.ms_adlib import collect
    seen = existing("bing_ads", lambda d: d["source_meta"]["ad_id"])
    docs, notes = list(seen.values()), {}
    for firm, dom in DOMAINS.items():
        for q in (firm, dom):
            if only and q not in only.split(","):
                continue
            for skip in range(0, 120, 24):
                n = {}
                try:
                    page = retry(lambda: list(collect(q, n, top=24, skip=skip)))
                except Exception as e:
                    notes[f"{q}@{skip}"] = {"error": str(e)[:200]}
                    if "429" in str(e):
                        write("bing_ads", docs, notes)
                        return
                    break
                hits = [tag(d, firm) for d in page if d["source_meta"]["ad_id"] not in seen]
                hits = [d for d in hits if d["source_meta"]["firms_mentioned"]]
                for d in hits:
                    seen[d["source_meta"]["ad_id"]] = 1
                    d["source_meta"]["skip"] = skip
                docs += hits
                notes[f"{q}@{skip}"] = {"returned": len(page), "kept": len(hits)}
                print(q, skip, notes[f"{q}@{skip}"], flush=True)
                pause(3, 5)
                if len(page) < 24:
                    break
    write("bing_ads", docs, notes)


YT_QUERIES = {
    "XTB": ["kod polecający XTB", "XTB opinie", "XTB jak zacząć", "XTB konto maklerskie"],
    "Trading 212": ["Trading 212 kod", "Trading 212 opinie", "Trading 212 jak zacząć"],
    "eToro": ["eToro opinie", "eToro jak zacząć", "eToro kod polecający"],
    "Plus500": ["Plus500 jak zacząć", "Plus500 opinie"],
    "Revolut": ["Revolut inwestowanie", "Revolut akcje opinie", "Revolut kod polecający"],
}


def youtube():
    from youtube_posts.data_api import collect
    seen = existing("youtube", lambda d: d["source_meta"]["video_id"])
    done = {q for d in seen.values() for q in d["query_keywords"]}
    docs, notes = list(seen.values()), {}
    for firm, qs in YT_QUERIES.items():
        for q in qs:
            if q in done:
                continue
            n = {}
            try:
                page = retry(lambda: list(collect(q, n, max_results=25)))
            except Exception as e:
                notes[q] = {"error": str(e)[:200]}
                if "403" in str(e):
                    break
                continue
            hits = [tag(d, firm, OFFICIAL["youtube"]) for d in page if d["source_meta"]["video_id"] not in seen]
            for d in hits:
                seen[d["source_meta"]["video_id"]] = d
            docs += hits
            notes[q] = {"returned": len(page), "new": len(hits), "firm_mentioned": sum(bool(d["source_meta"]["firms_mentioned"]) for d in hits)}
            print(q, notes[q], flush=True)
            write("youtube", docs, notes)
            pause(2, 4)
    write("youtube", docs, notes)


# firm accounts + Polish finfluencers linked from YouTube descriptions in youtube_entities_v1 (tiktok.com/@...)
TT_ACCOUNTS = {"@xtbpl": "XTB", "@plus500official": "Plus500", "@trading212": "Trading 212", "@revolut": "Revolut",
               "@etoro_official": "eToro", "@mr_pankracy": None, "@kacper_snela": None, "@profit_investing": None,
               "@wladcamonet": None}


def tiktok():
    from tiktok_posts.embed_ytdlp import collect
    seen = existing("tiktok", lambda d: d["source_meta"]["video_id"])
    docs, notes = list(seen.values()), {}
    for h, firm in TT_ACCOUNTS.items():
        if any(d["query_keywords"] == [h] for d in docs):
            continue
        n = {}
        try:
            page = retry(lambda: list(collect(h, n, per_user=6)))
        except Exception as e:
            notes[h] = {"error": str(e)[:200]}
            continue
        hits = [tag(d, firm, OFFICIAL["tiktok"]) for d in page if d["source_meta"]["video_id"] not in seen]
        docs += hits
        notes[h] = {**n, "new": len(hits)}
        print(h, notes[h], flush=True)
        write("tiktok", docs, notes)
        pause(3, 5)
    write("tiktok", docs, notes)


META_QUERIES = {
    "XTB": ["XTB", "XTB kod", "XTB polecenie"],
    "eToro": ["eToro", "eToro kod"],
    "Plus500": ["Plus500"],
    "Trading 212": ["Trading 212", "Trading 212 polecenie", "Trading 212 kod"],
    "Revolut": ["Revolut inwestowanie", "Revolut akcje"],
}


def meta(scrolls="6"):
    """Ad Library web (scrolled) -> parsed card (scripts/convert_fb_ads_web.parse_ad); removed ads keep notice, no text."""
    sys.path.insert(0, str(POC_DIR.parents[1] / "scripts"))
    from convert_fb_ads_web import parse_ad
    from fb_ads.ad_library_web import collect
    seen = existing("meta_ads", lambda d: d["source_meta"]["library_id"])
    done = {q for d in seen.values() for q in d["query_keywords"]}
    docs, notes = list(seen.values()), {}
    for firm, qs in META_QUERIES.items():
        for q in qs:
            if q in done:
                continue
            n = {}
            try:
                page = retry(lambda: list(collect(q, n, scrolls=int(scrolls))))
            except Exception as e:
                notes[q] = {"error": str(e)[:200]}
                continue
            if n.get("body_chars", 0) < 500:  # 815 chars = page with 0 results
                notes[q] = {**n, "error": "empty page (block?)"}
                print(q, notes[q], flush=True)
                continue
            new = 0
            for d in page:
                try:
                    start, pm, body, title, desc, cta, domain = parse_ad(d["text"][0]["text"])
                except Exception as e:
                    pm, start, body, title, desc, cta, domain = {"parse_error": str(e)[:100]}, None, [], None, None, None, None
                lib_id = d["source_meta"]["ad_id"]
                if lib_id in seen:
                    continue
                d["text"] = [{"type": t, "text": v} for t, v in (("ad_body", "\n".join(body)), ("title", title),
                             ("link_description", desc), ("cta", cta)) if v]
                d["published_at"] = start
                d["links"] = [domain] if domain else []
                d["source_meta"] = {**pm, "library_id": lib_id, "query": q, "ad_body_source": "ad_library_web"}
                tag(d, firm, OFFICIAL["meta_ads"])
                if not d["source_meta"]["firms_mentioned"] and not pm.get("notice"):
                    continue  # keyword search also matches page text we do not see; keep only visible mentions
                seen[lib_id] = d
                docs.append(d)
                new += 1
            notes[q] = {**n, "returned": len(page), "kept": new}
            print(q, notes[q], flush=True)
            write("meta_ads", docs, notes)
            pause(4, 6)
    write("meta_ads", docs, notes)


def meta_video(limit="40"):
    """Full ad text for video ads via fb_ads.ytdlp_by_id (replaces ad_body)."""
    from fb_ads.ytdlp_by_id import collect
    out = SAMPLES / "meta_ads_entities_v1.jsonl"
    docs = [json.loads(l) for l in out.open(encoding="utf-8") if l.strip()]
    todo = [d for d in docs if d["source_meta"].get("has_video") and d["source_meta"]["ad_body_source"] != "ytdlp_by_id"
            and not d["source_meta"].get("notice")][:int(limit)]
    notes = {"ytdlp_errors": []}
    for d in todo:
        n = {}
        got = retry(lambda: list(collect(d["source_meta"]["library_id"], n)))
        notes["ytdlp_errors"] += n.get("errors", [])
        if got and got[0]["text"]:
            body = got[0]["text"][0]["text"] if isinstance(got[0]["text"], list) else got[0]["text"]
            d["text"] = [{"type": "ad_body", "text": body}] + [s for s in d["text"] if s["type"] != "ad_body"]
            d["source_meta"].update(ad_body_source="ytdlp_by_id", page_id=got[0]["source_meta"].get("page_id"))
            tag(d, d["source_meta"]["firm"], OFFICIAL["meta_ads"])
        pause(2, 4)
    write("meta_ads", docs, notes)
    print(len(todo), "tried,", sum(d["source_meta"]["ad_body_source"] == "ytdlp_by_id" for d in docs), "with full text")


if __name__ == "__main__":
    {"meta": meta, "meta_video": meta_video, "bing": bing, "youtube": youtube, "tiktok": tiktok}[sys.argv[1]](*sys.argv[2:])
