"""Trening klasyfikatora: embeddingi bge-m3 (lokalnie) + głowy LogisticRegression na etykietach nauczycieli.

  uv run python scripts/train_heads.py                     # Bielik + Gemini (zgodne etykiety mają większą wagę)
  uv run python scripts/train_heads.py --teachers bielik   # tylko jeden nauczyciel

Wyjście (models/):
  heads.joblib       – głowy dla investwatch_ml.classifier.Classifier
  metrics.json       – metryki na teście (podział po autorze) + porównanie z baseline'em słownikowym
  eval_set.json      – prawdopodobieństwa + etykiety testu → panel kalibracji (/calibration/eval-set)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, f1_score, precision_recall_fscore_support
from sklearn.model_selection import GroupShuffleSplit

from investwatch_ml import heuristics
from investwatch_ml.classifier import Embedder, Heads, doc_windows
from investwatch_ml.labels import CONTENT_TYPES, FLAG_KEYS, INSTRUMENTS, TOPICS
from investwatch_ml.schema import Doc, read_jsonl

ML_DIR = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
TEACHER_FILES = {"bielik": "data/silver/teacher.jsonl", "gemini": "data/silver/teacher_gemini.jsonl",
                 "groq": "data/silver/teacher_groq.jsonl",
                 "openrouter": "data/silver/teacher_openrouter.jsonl"}
TEACHER_RANK = {"groq": 0, "gemini": 1, "openrouter": 1, "bielik": 2}  # kto rozstrzyga typ treści przy rozbieżności


def log(m: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {m}", flush=True)


def load_labels(teachers: list[str]) -> dict[str, list[dict]]:
    by_id: dict[str, list[dict]] = defaultdict(list)
    for t in teachers:
        for r in read_jsonl(ML_DIR / TEACHER_FILES[t]):
            if r.get("label"):
                by_id[str(r["id"])].append({**r["label"], "_teacher": t})
    return by_id


def merge(labels: list[dict]) -> tuple[dict, float]:
    """Łączy etykiety nauczycieli: temat/scam większością (remis → najlepszy nauczyciel), typ treści od najlepszego,
    flagi i instrumenty – suma. Waga 1.0 przy pełnej zgodności tematu i scamu, 0.6 przy rozbieżności."""
    if len(labels) == 1:
        return labels[0], float(labels[0].get("_weight", 1.0))
    labels = sorted(labels, key=lambda x: TEACHER_RANK.get(x["_teacher"], 9))
    best = labels[0]
    merged = dict(best)
    for key in ("topic", "is_scam"):
        votes = Counter(x[key] for x in labels)
        top, n = votes.most_common(1)[0]
        merged[key] = top if n > len(labels) / 2 else best[key]
    if merged["topic"] != "INVESTMENT":
        merged["content_type"] = "NONE"
    merged["flags"] = [f for x in labels for f in x["flags"]]
    merged["instruments"] = sorted({i for x in labels for i in x["instruments"]})
    agree = all(x["topic"] == merged["topic"] and x["is_scam"] == merged["is_scam"] for x in labels)
    return merged, 1.0 if agree else 0.6


def fit_binary(X, y, w=None, C=2.0):
    if y.sum() == 0 or y.sum() == len(y):
        return float(y.mean())
    m = LogisticRegression(C=C, max_iter=3000, class_weight="balanced")
    m.fit(X, y, sample_weight=w)
    return m


def fit_multi(X, y, w=None, C=2.0):
    if len(set(y)) < 2:
        return None
    m = LogisticRegression(C=C, max_iter=3000, class_weight="balanced")
    m.fit(X, y, sample_weight=w)
    return m


def proba(m, X):
    if isinstance(m, float):
        return np.full(len(X), m)
    return m.predict_proba(X)[:, 1]


def bin_metrics(y, p, t=0.5) -> dict:
    if y.sum() == 0:
        return {"support": 0}
    pr, rc, f1, _ = precision_recall_fscore_support(y, p >= t, average="binary", zero_division=0)
    return {"support": int(y.sum()), "n": int(len(y)), "ap": round(float(average_precision_score(y, p)), 3),
            "precision@0.5": round(float(pr), 3), "recall@0.5": round(float(rc), 3), "f1@0.5": round(float(f1), 3)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--teachers", default="bielik,gemini,groq,openrouter")
    ap.add_argument("--embedder", default="BAAI/bge-m3")
    ap.add_argument("--out", default="models")
    ap.add_argument("--test-size", type=float, default=0.2)
    ap.add_argument("--curated", default=None, help="etykiety po naprawie, np. data/curated/labels.jsonl")
    ap.add_argument("--no-edge", action="store_true", help="bez przypadków granicznych: zostają do oceny")
    args = ap.parse_args()
    out = ML_DIR / args.out
    out.mkdir(parents=True, exist_ok=True)

    if args.curated:
        labels = {str(r["id"]): [{**r["label"], "_teacher": "curated", "_weight": float(r["weight"])}]
                  for r in read_jsonl(ML_DIR / args.curated)}
    else:
        labels = load_labels(args.teachers.split(","))
    docs: dict[str, Doc] = {}
    for f in (ML_DIR / "data/pool").glob("*.jsonl"):
        if "candidates" in f.name or "skipped" in f.name or "checked" in f.name:
            continue
        for r in read_jsonl(f):
            if str(r.get("id")) in labels:
                docs[str(r["id"])] = Doc(**r)
    edge_rows = [] if args.no_edge else read_jsonl(ML_DIR / "data/gold/edge_cases.jsonl")
    for r in edge_rows:  # ręczne przypadki graniczne: tylko trening, większa waga
        docs[r["doc"]["id"]] = Doc(**r["doc"])
        labels[r["doc"]["id"]] = [{**r["label"], "_teacher": "edge", "_weight": 2.0}]
    ids = sorted(docs)
    log(f"dokumenty z etykietami: {len(ids)} | źródła: {Counter(docs[i].source for i in ids)}")
    if len(ids) < 50:
        log("za mało danych do treningu (min. 50)")
        return

    merged = {i: merge(labels[i]) for i in ids}
    texts = [docs[i].full_text() for i in ids]
    groups = [docs[i].author or docs[i].source for i in ids]
    weights = np.array([merged[i][1] for i in ids])

    # --- embeddingi okien
    log("embeddingi okien (bge-m3, GPU)...")
    emb = Embedder(args.embedder)
    spans = [doc_windows(t) for t in texts]
    flat = [t[s:e] for t, sp in zip(texts, spans) for s, e in sp]
    t0 = time.time()
    E = emb.encode(flat)
    log(f"  {len(flat)} okien w {time.time() - t0:.0f}s")
    W_idx, k = [], 0
    for sp in spans:
        W_idx.append((k, k + len(sp)))
        k += len(sp)
    D = np.stack([E[a:b].mean(0) for a, b in W_idx])
    D /= np.linalg.norm(D, axis=1, keepdims=True) + 1e-9

    # --- podział po autorze / kanale (bez przecieku tego samego autora do testu)
    gss = GroupShuffleSplit(n_splits=1, test_size=args.test_size, random_state=42)
    tr, te = next(gss.split(D, groups=groups))
    synth = np.array([bool(docs[i].meta.get("synthetic")) for i in ids])
    tr = np.array(sorted(set(tr.tolist()) | set(np.where(synth)[0].tolist())))  # syntetyki tylko w treningu
    te = np.array([i for i in te if not synth[i]])
    log(f"train {len(tr)} / test {len(te)} dokumentów")

    lab = [merged[i][0] for i in ids]
    y_topic = np.array([x["topic"] for x in lab])
    y_ct = np.array([x["content_type"] for x in lab])
    y_scam = np.array([int(x["is_scam"]) for x in lab])
    y_instr = {i: np.array([int(i in x["instruments"]) for x in lab]) for i in INSTRUMENTS}
    doc_flag = {f: np.array([int(any(h["flag"] == f for h in x["flags"])) for x in lab]) for f in FLAG_KEYS}

    heads = Heads(embedder_name=args.embedder)
    heads.topic = fit_multi(D[tr], y_topic[tr], weights[tr])
    heads.content_type = fit_multi(D[tr], y_ct[tr], weights[tr])
    heads.scam = fit_binary(D[tr], y_scam[tr], weights[tr])
    heads.instruments = {i: fit_binary(D[tr], y_instr[i][tr], weights[tr]) for i in INSTRUMENTS}

    # --- flagi na poziomie okien: pozytyw = okno nachodzi na dopasowany cytat; negatyw = okna dokumentów bez flagi
    tr_set = set(tr.tolist())
    for f in FLAG_KEYS:
        Xs, ys, ws = [], [], []
        for di in tr_set:
            a, b = W_idx[di]
            hits = [(h["start"], h["end"]) for h in lab[di]["flags"] if h["flag"] == f and h.get("start") is not None]
            if doc_flag[f][di] and not hits:
                continue  # flaga bez dopasowanego cytatu – nie wiemy, które okno
            for wi, (s, e) in enumerate(spans[di]):
                pos = any(s < he and hs < e for hs, he in hits)
                if doc_flag[f][di] and not pos:
                    continue  # inne okna dokumentu z flagą – niepewne, pomijamy
                Xs.append(a + wi)
                ys.append(int(pos))
                ws.append(float(weights[di]))
        y = np.array(ys)
        heads.flags[f] = fit_binary(E[Xs], y, np.array(ws) if args.curated else None) if len(Xs) else 0.0
        log(f"  flaga {f:30s} okna: {len(y)} (poz. {int(y.sum()) if len(y) else 0})")

    # --- ewaluacja na teście (etykiety nauczycieli) + baseline słownikowy
    metrics: dict = {"n_train": int(len(tr)), "n_test": int(len(te)), "teachers": args.teachers, "heads": {}, "baseline": {}}
    topics, ctypes = list(TOPICS), list(CONTENT_TYPES)
    p_topic = heads.topic.predict(D[te])
    p_ct = heads.content_type.predict(D[te])
    metrics["heads"]["topic_macro_f1"] = round(float(f1_score(y_topic[te], p_topic, average="macro")), 3)
    metrics["heads"]["content_type_macro_f1"] = round(float(f1_score(y_ct[te], p_ct, average="macro")), 3)
    base = [heuristics.predict(texts[i]) for i in te]
    b_topic = np.array([max(b["topic"], key=b["topic"].get) for b in base])
    metrics["baseline"]["topic_macro_f1"] = round(float(f1_score(y_topic[te], b_topic, average="macro")), 3)

    eval_probs: dict[str, np.ndarray] = {}
    eval_gold: dict[str, np.ndarray] = {}
    inv_idx = topics.index("INVESTMENT")
    eval_probs["topic.INVESTMENT"] = heads.topic.predict_proba(D[te])[:, list(heads.topic.classes_).index("INVESTMENT")] \
        if "INVESTMENT" in heads.topic.classes_ else np.zeros(len(te))
    eval_gold["topic.INVESTMENT"] = (y_topic[te] == "INVESTMENT").astype(int)
    eval_probs["scam"] = proba(heads.scam, D[te])
    eval_gold["scam"] = y_scam[te]
    metrics["heads"]["scam"] = bin_metrics(y_scam[te], eval_probs["scam"])
    metrics["baseline"]["scam"] = bin_metrics(y_scam[te], np.array([b["scamText"] for b in base]))
    for c in ("FIRM_OWN_MARKETING", "THIRD_PARTY_PROMO", "SERVICE_OFFER", "RECOMMENDATION"):
        if heads.content_type is not None and c in heads.content_type.classes_:
            pc = heads.content_type.predict_proba(D[te])[:, list(heads.content_type.classes_).index(c)]
            eval_probs[f"contentType.{c}"], eval_gold[f"contentType.{c}"] = pc, (y_ct[te] == c).astype(int)
    for f in FLAG_KEYS:
        pf = np.array([proba(heads.flags[f], E[W_idx[i][0]:W_idx[i][1]]).max() for i in te])
        eval_probs[f"flags.{f}"], eval_gold[f"flags.{f}"] = pf, doc_flag[f][te]
        metrics["heads"][f"flags.{f}"] = bin_metrics(doc_flag[f][te], pf)
        metrics["baseline"][f"flags.{f}"] = bin_metrics(doc_flag[f][te], np.array([b["flags"][f]["p"] for b in base]))

    heads.meta = {"version": f"heads-{time.strftime('%Y%m%d-%H%M')}", "teachers": args.teachers,
                  "n_docs": len(ids), "trained_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    heads.save(out / "heads.joblib")
    (out / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    eval_items = [{"id": ids[i], "probs": {k: round(float(v[n]), 4) for k, v in eval_probs.items()},
                   "gold": {k: int(v[n]) for k, v in eval_gold.items()}} for n, i in enumerate(te)]
    (out / "eval_set.json").write_text(json.dumps(eval_items, ensure_ascii=False), encoding="utf-8")

    log(f"topic macro-F1: model {metrics['heads']['topic_macro_f1']} vs baseline {metrics['baseline']['topic_macro_f1']}")
    log(f"content_type macro-F1: {metrics['heads']['content_type_macro_f1']}")
    log(f"scam: model {metrics['heads']['scam']} | baseline {metrics['baseline']['scam']}")
    for f in FLAG_KEYS:
        m, b = metrics["heads"][f"flags.{f}"], metrics["baseline"][f"flags.{f}"]
        if m.get("support"):
            log(f"  {f:30s} AP model {m['ap']:.2f} vs baseline {b.get('ap', 0):.2f} (n+={m['support']})")
    log(f"zapisano {out}/heads.joblib, metrics.json, eval_set.json")


if __name__ == "__main__":
    main()
