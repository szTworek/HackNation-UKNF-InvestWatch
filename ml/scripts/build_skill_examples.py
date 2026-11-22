"""Wybiera prawdziwe przykłady ze scrapera do ręcznej weryfikacji i wklejenia do skilla (few-shot).

Wejście: frontend/mock-server/data/findings.real.json (rekordy ze scrapera ocenione przez ai-service).
Wyjście (poza gitem, bo zawiera nazwy autorów):
  ml/data/skill/examples_for_review.md     – do czytania i poprawiania
  ml/data/skill/examples_for_review.jsonl  – te same przykłady do skryptów

  python ml/scripts/build_skill_examples.py --per-category 10
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8")

CATEGORIES = {
    "SCAM": "Oszustwo inwestycyjne",
    "M1": "Moduł 1: reklama firmy przez osobę trzecią / finfluencera",
    "M2_BAD": "Moduł 2: materiał firmy z możliwymi brakami",
    "M2_OK": "Moduł 2: materiał firmy bez wykrytych braków",
    "M3_ADVISORY": "Moduł 3: oferta doradztwa / zarządzania / sygnałów",
    "RECOMMENDATION": "Rekomendacja instrumentu dla ogółu („kup X”)",
    "BORDERLINE": "Przypadki graniczne (model niepewny)",
    "NEUTRAL": "Neutralne: edukacja, news, opinia o inwestowaniu",
    "NON_INVESTMENT": "Poza inwestycjami (finanse ogólne lub inne)",
}
PL_HINT = re.compile(r"[ąćęłńóśźż]|\b(i|w|na|nie|się|jest|do|z)\b", re.I)


def rule(f: dict, rid: str) -> str | None:
    return next((r["status"] for r in f["rules"] if r["ruleId"] == rid), None)


def top(d: dict) -> str:
    return max(d, key=d.get) if d else ""


def category(f: dict) -> str | None:
    scam = f["scam"]["p"]
    inv = f["topic"].get("INVESTMENT", 0)
    if 0.4 <= scam < 0.6 or 0.4 <= inv < 0.6:
        return "BORDERLINE"
    if f["scam"]["signals"]:
        return "SCAM"
    if rule(f, "M3_ADVISORY") == "VIOLATION":
        return "M3_ADVISORY"
    if rule(f, "M3_RECOMMENDATION") == "NOT_CHECKED":
        return "RECOMMENDATION"
    if 1 in f["modules"]:
        return "M1"
    if 2 in f["modules"]:
        return "M2_BAD" if any(r["status"] == "VIOLATION" for r in f["rules"]) else "M2_OK"
    if inv < 0.4:
        return "NON_INVESTMENT"
    if top(f["contentType"]) in ("NEWS_EDU", "OPINION_DISCUSSION") and f["riskLevel"] == "LOW":
        return "NEUTRAL"
    return None


def evidence(f: dict) -> list[str]:
    out = []
    for r in f["rules"]:
        if r["status"] in ("VIOLATION", "NOT_CHECKED") and r["evidence"]:
            out.append(f"reguła {r['ruleId']} ({r['status']}): „{r['evidence'][0]['text'][:120]}”")
    for k, v in sorted(f["flags"].items(), key=lambda x: -x[1]["p"]):
        if v["p"] >= 0.5 and v["evidence"]:
            out.append(f"flaga {k} ({v['p']:.2f}): „{v['evidence'][0]['text'][:120]}”")
    return list(dict.fromkeys(out))[:5]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-category", type=int, default=10)
    ap.add_argument("--max-chars", type=int, default=900)
    args = ap.parse_args()
    data = json.loads((ROOT / "frontend/mock-server/data/findings.real.json").read_text(encoding="utf-8"))
    buckets: dict[str, list[dict]] = defaultdict(list)
    for f in data["findings"]:
        text = " ".join((f.get("text") or "").split())
        if not 60 <= len(text) <= 6000 or len(PL_HINT.findall(text)) < 5:
            continue
        c = category(f)
        if c:
            buckets[c].append(f)

    picked, out_md = [], [f"# Prawdziwe przykłady do skilla – do ręcznej weryfikacji\n",
                          f"Źródło: rekordy ze scrapera ocenione przez `{data['modelVersion']}` ({data['generatedAt']}). "
                          "Kategoria to **propozycja modelu**, nie prawda. Przy każdym przykładzie wpisz werdykt; "
                          "do skilla trafiają tylko przykłady z potwierdzoną lub poprawioną kategorią.\n",
                          "Werdykt: `OK` albo nazwa poprawnej kategorii: " + ", ".join(f"`{c}`" for c in CATEGORIES) + ", `SKIP`.\n",
                          "Dane zawierają nazwy autorów i reklamodawców: nie publikuj tego pliku.\n"]
    for c, name in CATEGORIES.items():
        rows = sorted(buckets[c], key=lambda f: (-f["scam"]["p"] if c == "SCAM" else -f["riskScore"], f["id"]))
        seen_auth, chosen = set(), []
        for f in rows:  # różni autorzy i platformy
            a = (f["author"].get("handle") or "").lower()
            if a in seen_auth:
                continue
            seen_auth.add(a)
            chosen.append(f)
            if len(chosen) >= args.per_category:
                break
        out_md.append(f"\n## {c}: {name} ({len(chosen)} z {len(buckets[c])})\n")
        for n, f in enumerate(chosen, 1):
            text = " ".join(f["text"].split())
            ex = {"id": f["id"], "proposed": c, "platform": f["platform"], "author": f["author"].get("handle"),
                  "url": f["url"], "scam_p": f["scam"]["p"], "riskLevel": f["riskLevel"], "modules": f["modules"],
                  "contentType": top(f["contentType"]), "evidence": evidence(f), "text": text[: args.max_chars],
                  "verdict": None, "note": ""}
            picked.append(ex)
            out_md += [f"\n### {c}-{n:02d} · {ex['platform']} · {ex['author']}\n",
                       f"- id: `{ex['id']}`, ryzyko {ex['riskLevel']}, scam {ex['scam_p']:.2f}, typ {ex['contentType']}, moduły {ex['modules']}",
                       f"- źródło (nie otwieraj podejrzanych domen): {ex['url']}"]
            out_md += [f"- {e}" for e in ex["evidence"]]
            out_md += ["", "> " + ex["text"] + ("…" if len(text) > args.max_chars else ""), "",
                       "**Werdykt:** ____  **Uwagi:** ____", ""]
    out = ROOT / "ml/data/skill"
    out.mkdir(parents=True, exist_ok=True)
    (out / "examples_for_review.md").write_text("\n".join(out_md), encoding="utf-8")
    (out / "examples_for_review.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in picked), encoding="utf-8")
    print({c: f"{sum(x['proposed'] == c for x in picked)}/{len(buckets[c])}" for c in CATEGORIES})
    print(out / "examples_for_review.md")


if __name__ == "__main__":
    main()
