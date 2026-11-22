"""Audyt jakości danych treningowych. Tylko odczyt.

  uv run python scripts/audit_data.py
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from langdetect import DetectorFactory, detect_langs

from investwatch_ml.labels import FLAGS_BY_KEY
from investwatch_ml.schema import Doc, read_jsonl

ML_DIR = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8")
DetectorFactory.seed = 0
TEACHERS = {"bielik": "teacher", "gemini": "teacher_gemini", "groq": "teacher_groq", "openrouter": "teacher_openrouter"}
NEG_QUOTE = re.compile(r"oszust|scam|uwaga|ostrzeg|fałszyw|nie daj|nie wpłacaj|piramid|naciąg", re.I)


def fp(text: str) -> str:
    return hashlib.sha1(" ".join(re.findall(r"\w+", text.lower())).encode()).hexdigest()


def pct(a: int, b: int) -> str:
    return f"{a}/{b} ({100 * a / max(b, 1):.0f}%)"


def p_pl(text: str) -> float:
    try:
        return next((x.prob for x in detect_langs(text[:1500]) if x.lang == "pl"), 0.0)
    except Exception:
        return 0.0


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
    ids = sorted(labels)
    real = [i for i in ids if not docs[i].meta.get("synthetic")]
    print(f"1. SKALA: pula {len(docs)}, oznaczone {len(ids)}, realne {len(real)}, syntetyczne {len(ids) - len(real)}")
    print("   źródła:", dict(Counter(docs[i].source for i in ids)))
    print("   liczba nauczycieli na dokument:", dict(sorted(Counter(len(labels[i]) for i in ids).items())))

    groups = defaultdict(list)
    for i in ids:
        groups[fp(docs[i].full_text())].append(i)
    dup = [v for v in groups.values() if len(v) > 1]
    cross = sum(len({docs[i].author or docs[i].source for i in v}) > 1 for v in dup)
    print(f"\n2. DUPLIKATY: grup {len(dup)}, nadmiarowych dok. {sum(len(v) - 1 for v in dup)}, grup u różnych autorów (przeciek do testu): {cross}")
    no_author = sum(not docs[i].author for i in ids)
    top_auth = Counter(docs[i].author or f"<brak:{docs[i].source}>" for i in real).most_common(4)
    print(f"   bez autora: {pct(no_author, len(ids))}; najwięksi autorzy realni: {top_auth}")

    print("\n3. ZGODNOŚĆ NAUCZYCIELI (dokumenty z co najmniej 2):")
    multi = [i for i in ids if len(labels[i]) > 1]
    for field in ("topic", "content_type", "is_scam"):
        print(f"   {field}: {pct(sum(len({v[field] for v in labels[i].values()}) == 1 for i in multi), len(multi))}")
    agree, total = Counter(), Counter()
    for i in multi:
        sets = [{h["flag"] for h in v["flags"]} for v in labels[i].values()]
        for f in set().union(*sets):
            total[f] += 1
            agree[f] += all(f in s for s in sets)
    print("   flagi, wskazane przez wszystkich:", pct(sum(agree.values()), sum(total.values())))
    print("   najmniej zgodne:", [(f, pct(agree[f], total[f])) for f, n in sorted(total.items(), key=lambda x: agree[x[0]] / x[1]) if n >= 8][:6])

    print("\n4. JAKOŚĆ CYTATÓW:")
    hits = none = fake = 0
    for i in ids:
        text = docs[i].full_text().lower()
        for v in labels[i].values():
            for h in v["flags"]:
                hits += 1
                none += h.get("start") is None
                q = (h.get("quote") or "").lower().strip()
                fake += bool(q) and h.get("start") is None and q[:30] not in text
    print(f"   flagi bez dopasowania: {pct(none, hits)}, z cytatem spoza tekstu (halucynacja): {pct(fake, hits)}")

    print("\n5. SPRZECZNOŚCI Z PEWNYM ŹRÓDŁEM:")
    def scam_votes(i: str) -> bool:
        return sum(v["is_scam"] for v in labels[i].values()) > len(labels[i]) / 2
    cert = [i for i in ids if docs[i].source == "cert_wayback"]
    print("   strony CERT oznaczone jako scam:", pct(sum(scam_votes(i) for i in cert), len(cert)))
    weak = [i for i in ids if docs[i].meta.get("weak_is_scam") and docs[i].meta.get("weak_investment")]
    print("   syntetyczne oszustwa inwestycyjne oznaczone jako scam:", pct(sum(scam_votes(i) for i in weak), len(weak)))
    print("   syntetyczne oszustwa z tematem INVESTMENT:", pct(sum(any(v["topic"] == "INVESTMENT" for v in labels[i].values()) for i in weak), len(weak)))
    firms = re.compile(r"\b(xtb|mbank|bossa|dom maklerski|etoro|swissquote|plus500|tfi)\b", re.I)
    ads = [i for i in ids if docs[i].source == "scraper" and docs[i].meta.get("is_paid_ad") and firms.search(docs[i].author or "")]
    print("   reklamy znanych firm oznaczone jako scam:", pct(sum(scam_votes(i) for i in ads), len(ads)))
    warn = [i for i in real if scam_votes(i) and NEG_QUOTE.search(docs[i].full_text()[:500])]
    print("   realne 'scamy' ze słownictwem ostrzeżeń (możliwe ostrzeżenia przed oszustwem):", pct(len(warn), sum(scam_votes(i) for i in real)))

    print("\n6. LOGIKA ETYKIET:")
    bad = Counter()
    for i in ids:
        for v in labels[i].values():
            names = {h["flag"] for h in v["flags"]}
            bad["scam poza INVESTMENT"] += v["is_scam"] and v["topic"] != "INVESTMENT"
            bad["flagi inwestycyjne przy NON_FINANCIAL"] += v["topic"] == "NON_FINANCIAL" and bool(names)
            bad["SERVICE_OFFER bez flagi usługi"] += v["content_type"] == "SERVICE_OFFER" and not names & {"PAID_ADVISORY_SERVICE", "PERSONALIZED_ADVICE"}
            bad["RECOMMENDATION bez wezwania"] += v["content_type"] == "RECOMMENDATION" and "SPECIFIC_INSTRUMENT_CALL" not in names
            bad["scam bez żadnej flagi scam"] += v["is_scam"] and not any(FLAGS_BY_KEY[n].group == "scam" for n in names)
    print("  ", {k: int(n) for k, n in bad.items()})

    print("\n7. SZUM W TEKSTACH (realne):")
    noise = Counter()
    for i in real:
        d, t = docs[i], docs[i].full_text()
        words = re.findall(r"\w+", t.lower())
        noise["krótkie (<12 słów)"] += len(words) < 12
        noise["powtarzalne (halucynacje ASR)"] += len(words) >= 30 and len(set(words)) / len(words) < 0.25
        noise["OCR"] += bool(d.meta.get("has_ocr"))
        noise["mało polskie (p<0.7)"] += p_pl(t) < 0.7
    print("  ", {k: pct(n, len(real)) for k, n in noise.items()})

    print("\n8. ROZKŁAD KLAS I PRZECIEK ŹRÓDŁA (etykieta najlepszego nauczyciela):")
    def best(i: str) -> dict:
        return next(labels[i][t] for t in ("groq", "openrouter", "gemini", "bielik") if t in labels[i])
    table = defaultdict(Counter)
    for i in ids:
        table[docs[i].source][best(i)["content_type"]] += 1
        table[docs[i].source]["_scam"] += best(i)["is_scam"]
    for s, c in table.items():
        print(f"   {s:16s} n={sum(v for k, v in c.items() if k != '_scam'):4d} scam={c['_scam']:4d} " + ", ".join(f"{k[:9]}:{v}" for k, v in c.most_common(4) if k != "_scam"))
    print("   realne pozytywy:", dict(Counter(h for i in real for h in {x["flag"] for x in best(i)["flags"]}).most_common(23)))


if __name__ == "__main__":
    main()
