"""Łączy propozycje Claude, wybiera ~150 rekordów z różnych źródeł i buduje stronę zip_review.html z propozycjami."""
import json, runpy, sys
from collections import Counter, defaultdict
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
SK = Path(__file__).resolve().parents[1] / "data/skill"
L = {}
for i in range(1, 5):
    L.update(runpy.run_path(str(SK / f"claude_labels_{i}.py"))["L"])
import re
def rules(lab):
    r, t, x = set(), lab["reason"].lower(), set(lab["extra"])
    if lab["verdict"] in ("M1", "M2_BAD", "M2_OK"):
        if "no_risk" in x: r.add("3")
        if "no_ad" in x: r.add("2")
        if "knf" in x: r.update({"17", "18"})
        if re.search(r"najlepsz|ranking|porówna|lepiej niż", t): r.add("11")
        if re.search(r"podat", t) and lab["verdict"] != "M2_OK": r.add("16")
        if re.search(r"historyczn|wzrost .*%|12a|wynik", t) and lab["verdict"] != "M2_OK": r.update({"12a", "12b", "13", "14"})
        if re.search(r"prognoz", t): r.add("15")
        r.update(re.findall(r"(1[0-8][ab]?|[1-9])(?=[,)])", lab["reason"]) if "reguł" in t else [])
    return sorted(r, key=lambda v: (int(re.match(r"\d+", v).group()), v))
for _lab in []: pass
rows = [json.loads(l) for l in (SK / "zip_clean.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
missing = [r["id"] for r in rows if r["id"] not in L]
print("bez etykiety:", missing)
CAP = {"eBilet Polska Sp. z o. o.": 2, "Revolut": 3, "Revolut Ltd": 2, "mBank S.A.": 8, "PLUS500 Ltd": 2, "XTB S.A.": 6,
       "Dom Maklerski Banku Ochrony Środowiska SA": 16, "XTB Online Investing": 14, "MMA.pl": 1, "MMA.pl Extra": 1,
       "济南沃晋跨境电子商务有限公司": 1, "厦门通誉网络科技有限公司": 1, "Jobrapido Srl": 1, "Revolut Securities Europe UAB": 2}
used, picked = Counter(), []
seen_reason = Counter()
for r in rows:
    a = r["author"] or "?"
    lab = L.get(r["id"])
    if not lab: continue
    if used[a] >= CAP.get(a, 6): continue
    key = (a, lab["reason"])
    if seen_reason[key] >= (2 if lab["verdict"] in ("NF", "M2_OK") else 4): continue
    used[a] += 1; seen_reason[key] += 1
    picked.append({**r, "claude": {**lab, "rules": rules(lab)}})
print("wybrane:", len(picked), "| źródła:", dict(Counter(p["folder"] for p in picked)), "| werdykty:", dict(Counter(p["claude"]["verdict"] for p in picked)))
(SK / "zip_claude_labels.jsonl").write_text("".join(json.dumps({"id": r["id"], **L[r["id"]]}, ensure_ascii=False) + "\n" for r in rows if r["id"] in L), encoding="utf-8")
(SK / "zip_review_set.jsonl").write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in picked), encoding="utf-8")
