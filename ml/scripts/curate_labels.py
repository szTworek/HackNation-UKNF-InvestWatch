"""Warstwa naprawcza etykiet: data/silver zostaje bez zmian, wynik trafia do data/curated/labels.jsonl.

Co robi:
1. łączy nauczycieli głosowaniem zamiast sumowania flag i usuwa cytaty spoza tekstu,
2. stosuje pewne źródła (CERT, znane firmy, metadane zbiorów oszustw),
3. naprawia sprzeczności w etykietach i dodaje precyzyjne reguły dla rzadkich klas M3,
4. usuwa duplikaty i śmieci, zmniejsza wagę danych syntetycznych,
5. szuka prawdopodobnych błędów etykiet przez walidację krzyżową i zmniejsza ich wagę (bez zmiany etykiety).

  uv run python scripts/curate_labels.py
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from langdetect import DetectorFactory, detect_langs
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold

from investwatch_ml.classifier import Embedder
from investwatch_ml.labels import FLAGS_BY_KEY
from investwatch_ml.schema import Doc, read_jsonl

ML_DIR = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
DetectorFactory.seed = 0
TEACHERS = {"groq": "teacher_groq", "openrouter": "teacher_openrouter", "gemini": "teacher_gemini", "bielik": "teacher"}
RANK = {"groq": 0, "openrouter": 1, "gemini": 1, "bielik": 2}
SOURCE_WEIGHT = {"mafb": 0.25, "fraud_r1": 0.5, "videoconviction": 0.5}
KNOWN_FIRMS = re.compile(r"\b(xtb|mbank|bossa|dom maklerski|etoro|swissquote|plus500|tfi)\b", re.I)
WARNING = re.compile(r"\b(uwaga na|ostrzegam|ostrzeżenie|nie daj się|oszuści|to oszustwo|to scam|nie wpłacaj|lista ostrzeżeń)\b", re.I)

LABEL_RULES = {
    "PAID_ADVISORY_SERVICE": re.compile(
        r"grup\w*\s+(vip|premium)|sygnał\w*.{0,40}(abonament|subskrypcj|\d+\s*zł)|konsultacj\w*\s*(1\s*[:na]\s*1|indywidualn)"
        r"|mentoring\w*|zarządzam\s+portfel\w*|audyt\w*\s+portfel\w*|kopiuj\w*\s+(moje|transakcje|pozycje)"
        r"|newsletter\w*\s+premium|handlował\w*\s+za\s+ciebie", re.I),
    "PERSONALIZED_ADVICE": re.compile(
        r"(dobior\w+|ułoż\w+|rozpisz\w+)\s+(ci|tobie|dla ciebie)?.{0,25}portfel\w*|pod\s+twoj\w+\s+(sytuacj|cel|wiek|profil)\w*"
        r"|napisz.{0,25}ile masz|dopasowan\w+\s+do\s+twoj\w+|indywidualn\w+\s+(plan|strategi|rekomendacj)\w*", re.I),
    "SPECIFIC_INSTRUMENT_CALL": re.compile(
        r"\b(kupujcie|sprzedajcie|ładujcie|wchodźcie)\b.{0,40}|\b[A-Z]{3,6}\s+(short|long)\s+z\s+\d", re.I),
}


def log(m: str) -> None:
    print(m, flush=True)


def fingerprint(text: str) -> str:
    return hashlib.sha1(" ".join(re.findall(r"\w+", text.lower())).encode()).hexdigest()


def p_polish(text: str) -> float:
    try:
        return next((x.prob for x in detect_langs(text[:1500]) if x.lang == "pl"), 0.0)
    except Exception:
        return 0.0


def majority(values: list, fallback):
    top = Counter(values).most_common()
    return top[0][0] if len(top) == 1 or top[0][1] > top[1][1] else fallback


def merge(doc: Doc, by_teacher: dict[str, dict], stats: Counter) -> tuple[dict, float, list[str]]:
    order = sorted(by_teacher, key=lambda t: RANK[t])
    best = by_teacher[order[0]]
    labels = [by_teacher[t] for t in order]
    text = doc.full_text()
    meta = doc.meta
    weight, why = SOURCE_WEIGHT.get(doc.source, 1.0), []
    topic = majority([x["topic"] for x in labels], best["topic"])
    scam = majority([x["is_scam"] for x in labels], best["is_scam"])
    if len(labels) > 1 and len({(x["topic"], x["is_scam"]) for x in labels}) > 1:
        weight *= 0.6
        why.append("spór nauczycieli")

    if meta.get("weak_investment") and meta.get("weak_is_scam"):
        topic, scam = "INVESTMENT", True
    elif meta.get("weak_is_scam") and not meta.get("weak_investment"):
        scam = False
    if doc.source == "cert_wayback" and any(x["topic"] == "INVESTMENT" for x in labels):
        if not scam:
            stats["CERT: poprawiono na scam"] += 1
        topic, scam = "INVESTMENT", True
    if doc.source == "scraper" and meta.get("is_paid_ad") and KNOWN_FIRMS.search(doc.author or ""):
        if scam:
            stats["znana firma: usunięto scam"] += 1
        scam = False
    if scam and WARNING.search(text[:600]) and doc.meta.get("synthetic") is not True:
        scam = False
        stats["ostrzeżenie przed oszustwem: usunięto scam"] += 1

    if topic != "INVESTMENT":
        stats["poza inwestycjami: wyczyszczono flagi"] += any(x["flags"] for x in labels)
        stats["poza inwestycjami: usunięto scam"] += bool(scam)
        return {**best, "topic": topic, "content_type": "NONE", "is_scam": False, "instruments": [], "flags": []}, weight, why

    ctype = next((x["content_type"] for x in labels if x["content_type"] != "NONE"), "NONE")
    if ctype == "NONE":
        ctype = "OPINION_DISCUSSION"
        weight *= 0.5
        why.append("brak typu treści")

    votes: dict[str, list[dict]] = defaultdict(list)
    seen: dict[str, set] = defaultdict(set)
    for t in order:
        for h in by_teacher[t]["flags"]:
            if h.get("start") is None:
                stats["flagi: usunięto cytat spoza tekstu"] += 1
                continue
            if t not in seen[h["flag"]]:
                seen[h["flag"]].add(t)
            votes[h["flag"]].append({**h, "_t": t})
    flags = []
    for name, hits in votes.items():
        teachers = seen[name]
        if len(by_teacher) > 1 and len(teachers) < 2 and not any(RANK[t] < 2 for t in teachers):
            stats["flagi: odrzucono bez potwierdzenia"] += 1
            continue
        spans = set()
        for h in hits:
            if (h["start"], h["end"]) not in spans:
                spans.add((h["start"], h["end"]))
                flags.append({k: v for k, v in h.items() if k != "_t"})

    if ctype not in ("NEWS_EDU", "OPINION_DISCUSSION") and not WARNING.search(text[:600]):
        have = {h["flag"] for h in flags}
        for name, rx in LABEL_RULES.items():
            m = rx.search(text)
            if m and name not in have:
                flags.append({"flag": name, "quote": m.group(0), "start": m.start(), "end": m.end(), "align_score": 1.0})
                stats[f"reguła dodała: {name}"] += 1
    names = {h["flag"] for h in flags}
    if ctype == "RECOMMENDATION" and "SPECIFIC_INSTRUMENT_CALL" not in names:
        weight *= 0.7
        why.append("rekomendacja bez wezwania")
    if ctype == "SERVICE_OFFER" and not names & {"PAID_ADVISORY_SERVICE", "PERSONALIZED_ADVICE"} and not scam:
        weight *= 0.7
        why.append("oferta bez flagi usługi")
    if scam and not any(FLAGS_BY_KEY[n].group == "scam" for n in names) and not meta.get("weak_is_scam") \
            and doc.source != "cert_wayback":
        weight *= 0.6
        why.append("scam bez sygnałów")
    instruments = sorted({i for x in labels for i in x["instruments"]})
    return {**best, "topic": topic, "content_type": ctype, "is_scam": bool(scam), "instruments": instruments, "flags": flags}, weight, why


def suspicious(X: np.ndarray, y: np.ndarray, groups: np.ndarray) -> np.ndarray:
    """Prawdopodobny błąd: model z innych autorów daje podanej etykiecie < 8%, a innej klasie > 80%."""
    out = np.zeros(len(y), dtype=bool)
    classes = sorted(set(y.tolist()))
    if len(classes) < 2:
        return out
    for tr, te in GroupKFold(n_splits=5).split(X, y, groups):
        if len(set(y[tr].tolist())) < len(classes):
            continue
        m = LogisticRegression(C=2.0, max_iter=1500, class_weight="balanced").fit(X[tr], y[tr])
        p = m.predict_proba(X[te])
        index = {c: k for k, c in enumerate(m.classes_)}
        given = p[np.arange(len(te)), [index[v] for v in y[te]]]
        out[te] = (given < 0.08) & (p.max(1) > 0.8)
    return out


def main() -> None:
    docs: dict[str, Doc] = {}
    for f in (ML_DIR / "data/pool").glob("*.jsonl"):
        if any(x in f.name for x in ("candidates", "skipped", "checked", ".bak")):
            continue
        for r in read_jsonl(f):
            try:
                docs[str(r["id"])] = Doc(**r)
            except Exception:
                pass
    labels: dict[str, dict[str, dict]] = defaultdict(dict)
    for t, f in TEACHERS.items():
        for r in read_jsonl(ML_DIR / f"data/silver/{f}.jsonl"):
            if r.get("label") and str(r["id"]) in docs:
                labels[str(r["id"])][t] = r["label"]

    stats: Counter = Counter()
    rows, seen = [], set()
    for i in sorted(labels, key=lambda x: (-len(labels[x]), x)):
        d = docs[i]
        text = d.full_text()
        words = re.findall(r"\w+", text.lower())
        fp = fingerprint(text)
        if fp in seen:
            stats["usunięto: duplikat"] += 1
            continue
        if len(words) < 5:
            stats["usunięto: za krótkie"] += 1
            continue
        if len(words) >= 30 and len(set(words)) / len(words) < 0.25:
            stats["usunięto: powtarzalny tekst"] += 1
            continue
        if not d.meta.get("synthetic") and p_polish(text) < 0.5:
            stats["usunięto: nie po polsku"] += 1
            continue
        seen.add(fp)
        label, weight, why = merge(d, labels[i], stats)
        rows.append({"id": i, "label": label, "weight": weight, "why": why, "n_teachers": len(labels[i])})

    log(f"dokumenty po czyszczeniu: {len(rows)}; liczę embeddingi do wykrywania błędów...")
    texts = [docs[r["id"]].full_text()[:1800] for r in rows]
    X = Embedder("BAAI/bge-m3").encode(texts)
    groups = np.array([docs[r["id"]].author or docs[r["id"]].source for r in rows])
    for field, values in (("topic", [r["label"]["topic"] for r in rows]),
                          ("content_type", [r["label"]["content_type"] for r in rows]),
                          ("is_scam", [str(r["label"]["is_scam"]) for r in rows])):
        bad = suspicious(X, np.array(values), groups)
        for k in np.where(bad)[0]:
            r = rows[k]
            hard = docs[r["id"]].source == "cert_wayback" or docs[r["id"]].meta.get("weak_is_scam")
            if r["n_teachers"] == 1 and not hard and f"cv:{field}" not in r["why"]:
                r["weight"] *= 0.3
                r["why"].append(f"cv:{field}")
                stats[f"prawdopodobny błąd etykiety: {field}"] += 1

    out = ML_DIR / "data/curated/labels.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    log(f"zapisano {len(rows)} -> {out}")
    for k, v in sorted(stats.items()):
        log(f"  {k}: {v}")
    log(f"  scam po naprawie: realne {sum(r['label']['is_scam'] and not docs[r['id']].meta.get('synthetic') for r in rows)}, "
        f"syntetyczne {sum(r['label']['is_scam'] and bool(docs[r['id']].meta.get('synthetic')) for r in rows)}")
    log("  typy realne: " + str(dict(Counter(r["label"]["content_type"] for r in rows if not docs[r["id"]].meta.get("synthetic")))))
    log("  flagi M3 realne: " + str(dict(Counter(h["flag"] for r in rows if not docs[r["id"]].meta.get("synthetic") for h in {x["flag"]: x for x in r["label"]["flags"]}.values() if FLAGS_BY_KEY[h["flag"]].group == "advisory"))))


if __name__ == "__main__":
    main()
