"""Porównuje modele na ręcznych przypadkach granicznych, które były wyłączone z ich treningu.

  uv run python scripts/eval_edge.py models_candidate/base_noedge models_candidate/curated_noedge
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import accuracy_score, average_precision_score, f1_score

from investwatch_ml.classifier import Classifier, Embedder
from investwatch_ml.labels import FLAG_KEYS
from investwatch_ml.schema import read_jsonl

ML_DIR = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
M3 = ("PERSONALIZED_ADVICE", "PAID_ADVISORY_SERVICE", "SPECIFIC_INSTRUMENT_CALL")


def evaluate(path: str, rows: list[dict], embedder: Embedder) -> dict:
    preds = Classifier(ML_DIR / path / "heads.joblib", embedder=embedder).predict_many([r["doc"]["text"] for r in rows])
    gold = [r["label"] for r in rows]
    y_topic = [x["topic"] for x in gold]
    p_topic = [max(p["topic"], key=p["topic"].get) for p in preds]
    inv = [i for i, x in enumerate(gold) if x["topic"] == "INVESTMENT"]
    y_type = [gold[i]["content_type"] for i in inv]
    p_type = [max({k: v for k, v in preds[i]["contentType"].items() if k != "NONE"},
                  key=lambda k: preds[i]["contentType"][k]) for i in inv]
    y_scam = np.array([int(x["is_scam"]) for x in gold])
    p_scam = np.array([p["scamText"] for p in preds])
    out = {"temat acc": accuracy_score(y_topic, p_topic), "typ treści acc": accuracy_score(y_type, p_type),
           "typ treści macro-F1": f1_score(y_type, p_type, average="macro", zero_division=0),
           "scam AP": average_precision_score(y_scam, p_scam), "scam F1@0.5": f1_score(y_scam, p_scam >= 0.5, zero_division=0)}
    aps = {}
    for f in FLAG_KEYS:
        y = np.array([int(any(h["flag"] == f for h in x["flags"])) for x in gold])
        if y.sum() >= 3:
            aps[f] = average_precision_score(y, np.array([p["flags"][f]["p"] for p in preds]))
    out["flagi średnie AP"] = float(np.mean(list(aps.values())))
    out["flagi M3 AP"] = float(np.mean([aps[f] for f in M3 if f in aps]))
    for f in M3:
        if f in aps:
            out[f"  {f}"] = aps[f]
    return out


def main() -> None:
    rows = list(read_jsonl(ML_DIR / "data/gold/edge_cases.jsonl"))
    embedder = Embedder("BAAI/bge-m3")
    results = {p: evaluate(p, rows, embedder) for p in sys.argv[1:]}
    print(f"przypadki graniczne poza treningiem: {len(rows)}")
    print(f"{'metryka':32s}" + "".join(f"{Path(p).name:>18s}" for p in results))
    for k in next(iter(results.values())):
        print(f"{k:32s}" + "".join(f"{r.get(k, float('nan')):18.3f}" for r in results.values()))
    (ML_DIR / "models_candidate/edge_comparison.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
