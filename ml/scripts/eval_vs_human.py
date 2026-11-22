"""Trafność modeli względem ręcznych ocen (eval_decisions.json): ogółem, per moduł, macierz pomyłek."""
import collections, json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
H = {d["id"]: d["verdict"] for d in json.load(open(sys.argv[1], encoding="utf-8")) if d.get("verdict")}
for f in sys.argv[2:]:
    P = {json.loads(l)["id"]: json.loads(l)["result"].get("module") for l in open(f, encoding="utf-8") if l.strip()}
    ids = [i for i in H if i in P]
    ok = sum(P[i] == H[i] for i in ids)
    per = {}
    for c in ("M1", "M2", "M3", "NONE"):
        tp = sum(P[i] == c and H[i] == c for i in ids)
        per[c] = f"P {tp}/{sum(P[i] == c for i in ids)} R {tp}/{sum(H[i] == c for i in ids)}"
    conf = collections.Counter(f"{H[i]}->{P[i]}" for i in ids if P[i] != H[i])
    print(f"{Path(f).stem}: {ok}/{len(ids)} ({ok / max(len(ids), 1):.0%}) | {per}\n   pomyłki: {dict(conf.most_common())}")
