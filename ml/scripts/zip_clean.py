"""Czyste rekordy z paczki scrapera (zip), bez etykiet i bez wyników modelu.

  python ml/scripts/zip_clean.py data/investwatch_samples_20261121.zip
Wyjście (poza gitem): ml/data/skill/zip_clean.jsonl (pełny tekst) i zip_clean.md (do czytania).
Zostają rekordy po polsku, bez duplikatów treści i z co najmniej 8 słowami.
"""
import hashlib, json, re, sys, zipfile
from collections import Counter
from pathlib import Path
from langdetect import DetectorFactory, detect_langs

sys.stdout.reconfigure(encoding="utf-8")
DetectorFactory.seed = 0
ROOT = Path(__file__).resolve().parents[2]
FOLDERS = ("youtube", "tiktok", "meta_ads", "google_ads", "bing_ads", "firm_web")  # bez raw/: starsze wersje tych samych danych
ORDER = ("title", "post", "ad_body", "description", "link_description", "cta", "transcript", "ocr", "page", "risk_disclaimer")

def pl(t):
    try: return next((x.prob for x in detect_langs(t[:2000]) if x.lang == "pl"), 0.0)
    except Exception: return 0.0

z = zipfile.ZipFile(sys.argv[1])
rows, seen, st = [], set(), Counter()
for name in sorted(z.namelist()):
    parts = name.replace("\\", "/").split("/")
    if len(parts) < 2 or parts[-1] != "records.jsonl" or parts[-2] not in FOLDERS:
        continue
    for line in z.read(name).decode("utf-8").splitlines():
        if not line.strip(): continue
        r = json.loads(line); folder = parts[-2]; st[f"{folder} wczytane"] += 1
        t = r.get("text") if isinstance(r.get("text"), dict) else {"post": str(r.get("text") or "")}
        sections = {k: " ".join(str(t[k]).split()) for k in sorted(t, key=lambda k: ORDER.index(k) if k in ORDER else 99) if str(t[k]).strip()}
        full = "\n".join(sections.values())
        if len(re.findall(r"\w+", full)) < 8: st[f"{folder} za krótkie"] += 1; continue
        if pl(full) < 0.7: st[f"{folder} nie po polsku"] += 1; continue
        fp = hashlib.sha1(" ".join(re.findall(r"\w+", full.lower())).encode()).hexdigest()
        if fp in seen: st[f"{folder} duplikat"] += 1; continue
        seen.add(fp); st[f"{folder} zostało"] += 1
        rows.append({"id": f"z{len(rows)+1:04d}", "folder": folder, "source": r.get("source"), "author": r.get("author"),
                     "sponsor": r.get("sponsor"), "url": r.get("source_url"), "published_at": r.get("published_at"),
                     "content_type": r.get("content_type"), "query": r.get("query_keywords"), "links": r.get("links") or [],
                     "sections": sections, "label": None})
out = ROOT / "ml/data/skill"; out.mkdir(parents=True, exist_ok=True)
(out / "zip_clean.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows), encoding="utf-8")
md = [f"# Czyste rekordy z {Path(sys.argv[1]).name}\n", f"{len(rows)} rekordów po polsku, bez etykiet. Nie publikuj: zawiera nazwy autorów.\n"]
for x in rows:
    md += [f"\n## {x['id']} · {x['folder']} · {x['author'] or '?'}\n", f"{x['url']}  ", f"zapytanie: {', '.join(x['query'] or [])}\n"]
    for k, v in x["sections"].items():
        md.append(f"**{k}:** {v[:1500]}{'…' if len(v) > 1500 else ''}\n")
(out / "zip_clean.md").write_text("\n".join(md), encoding="utf-8")
for k in sorted(st): print(f"{k}: {st[k]}")
print(len(rows), "->", out / "zip_clean.md")
