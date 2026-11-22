"""Wstawia klasyfikację LLM (moduły 1–3) do danych frontu: frontend/mock-server/data/findings.real.json.

- moduł, poziom i wynik ryzyka z LLM zastępują wynik heurystyk/klasyfikatora,
- naruszenia reguł z LLM (z dosłownym cytatem) zastępują reguły tekstowe o tym samym id; reguły 4–8 zostają z pomiarów,
- uzasadnienie LLM trafia do historii rekordu (widoczne w UI),
- rekordy oznaczone przez LLM, których brakuje we froncie, są pobierane z eksportu i analizowane przez ai-service.

  python ml/scripts/merge_llm.py --llm ml/data/skill/zip_groq120b.jsonl --export "ml/data/raw/scraper_live/zip1122_*"
"""

from __future__ import annotations

import argparse
import glob
import json
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "ml/src"))
import build_findings as bf  # noqa: E402
from investwatch_ml import llm as llm_core  # noqa: E402

FINDINGS = ROOT / "frontend/mock-server/data/findings.real.json"
VISUAL = {"4", "5", "6", "7", "8"}


def evidence_for(text: str, quote: str) -> list[dict]:
    q = (quote or "").strip()
    if not q:
        return []
    start = text.find(q)
    if start < 0:
        start = text.lower().find(q.lower())
    return [{"section": "text", "start": start, "end": start + len(q), "text": text[start:start + len(q)]}] if start >= 0 else []


def apply(f: dict, res: dict, model: str, now: str) -> None:
    paid = bool(((f.get("scoringInput") or {}).get("context") or {}).get("is_paid_ad"))
    res = llm_core.enforce(res, paid)
    f["adDisclosure"] = llm_core.ad_disclosure(res["rules"], paid, f.get("text", ""))
    module = res.get("module", "NONE")
    scores = res.get("scores", {})
    conf = round(float(scores.get(module, 0.0)), 3)
    f["llm"] = {"model": model, "module": module, "confidence": conf, "scores": scores, "reason": res.get("reason", ""),
                "riskLevel": res.get("risk_level"), "riskSignals": res.get("risk_signals", []), "needsHuman": res.get("needs_human")}
    author = f.get("author") or {}
    inp = llm_core.build_input(f["id"], f["text"], author.get("displayName") or author.get("handle"), None, f.get("platform"),
                               f.get("kind"), f.get("url"))
    f["llm"]["decision"] = llm_core.decision(inp, res, f.get("outboundLinks"))
    f["llm"]["decision"]["trace"].update({"backend": "groq", "model": model})
    f["modules"] = [int(module[1])] if module in ("M1", "M2", "M3") else []
    level = res.get("risk_level") if res.get("risk_level") in ("LOW", "MEDIUM", "HIGH", "CRITICAL") else "LOW"
    if not f["modules"]:
        level = "LOW"
    f["riskLevel"] = level
    f["riskScore"] = round(float(scores.get(module, 0.0)), 3) if f["modules"] else round(1 - float(scores.get("NONE", 1.0)), 3)
    llm_rules = {}
    for r in res.get("rules") or []:
        rid = str(r.get("id"))
        if rid in VISUAL or r.get("status") not in ("VIOLATION", "OK"):
            continue
        llm_rules[rid] = {"ruleId": rid, "status": r["status"], "score": 0.8 if r["status"] == "VIOLATION" else 0.0,
                          "evidence": evidence_for(f["text"], r.get("quote", ""))}
    # reguły tekstowe wyłącznie z LLM; stary klasyfikator nie może zostawiać własnych naruszeń; 4–8 z pomiarów
    rules = [r if r["ruleId"] in VISUAL else llm_rules.pop(r["ruleId"], {**r, "status": "NOT_APPLICABLE", "score": 0.0, "evidence": []})
             for r in f.get("rules", [])]
    f["rules"] = rules + list(llm_rules.values())
    f["flags"] = {k: {"p": 0.0, "evidence": []} for k in f.get("flags", {})}
    if not f["modules"]:
        f["scam"] = {"p": 0.0, "signals": []}
    hist = [h for h in f.get("history", []) if h.get("user") != "model"]
    label = {"M1": "Moduł 1", "M2": "Moduł 2", "M3": "Moduł 3"}.get(module, "Poza modułami")
    hist.append({"at": now, "status": f.get("status", "NEW"), "user": "model",
                 "comment": f"{label}, pewność {conf:.0%} ({model}): {res.get('reason', '')}"})
    f["history"] = hist
    f["modelVersion"] = model


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", required=True)
    ap.add_argument("--export", required=True, help="wzorzec katalogów z records.jsonl (rekordy do dociągnięcia)")
    ap.add_argument("--ai-url", default="http://localhost:8000")
    args = ap.parse_args()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    data = json.loads(FINDINGS.read_text(encoding="utf-8"))
    backup = FINDINGS.with_suffix(".before_llm.json")
    if not backup.exists():
        shutil.copyfile(FINDINGS, backup)
    llm = {}
    model = "llm"
    for line in open(args.llm, encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            llm[r["url"]] = r["result"]
            model = r.get("model", model)
    by_url = {f["url"]: f for f in data["findings"]}
    stats = Counter()

    missing = {u for u, res in llm.items() if u not in by_url and res.get("module") in ("M1", "M2", "M3")}
    if missing:
        records = []
        for d in glob.glob(args.export):
            for line in open(Path(d) / "records.jsonl", encoding="utf-8"):
                if line.strip():
                    rec = json.loads(line)
                    if rec.get("source_url") in missing:
                        records.append(rec)
        cert = bf.load_cert_domains()
        for i in range(0, len(records), 32):
            out = bf.request("POST", f"{args.ai_url}/ingest", {"records": records[i:i + 32]})
            for x in out["results"]:
                f = bf.to_finding(x["item"], x["analysis"], now, cert, stats)
                data["findings"].append(f)
                by_url[f["url"]] = f
                stats["dodane"] += 1

    for url, res in llm.items():
        f = by_url.get(url)
        if f:
            apply(f, res, model, now)
            stats[f"moduł {res.get('module')}"] += 1
    # klasyfikator pomija powtórzone treści: ten sam autor i tekst dostają tę samą ocenę
    same = lambda f: ((f.get("author") or {}).get("handle"), " ".join((f.get("text") or "").split()))
    judged = {same(by_url[u]): res for u, res in llm.items() if u in by_url}
    for f in data["findings"]:
        weaker = "120b" in model and (f.get("llm") or {}).get("model") != model  # duplikat dostaje ocenę lepszego modelu
        if ("llm" not in f or weaker) and same(f) in judged:
            apply(f, judged[same(f)], model, now)
            stats["powtórzone treści"] += 1
    for f in data["findings"]:  # duplikaty ocenione we wcześniejszym przebiegu
        if "llm" in f and "adDisclosure" not in f:
            paid = bool(((f.get("scoringInput") or {}).get("context") or {}).get("is_paid_ad"))
            f["adDisclosure"] = llm_core.ad_disclosure(f.get("rules", []), paid, f.get("text", ""))
    if "(moduły)" not in str(data.get("modelVersion")):
        data["modelVersion"] = f"{model} (moduły) + {data.get('modelVersion', '')}"
    data["generatedAt"] = now
    data.setdefault("stats", {})["llm"] = dict(stats)
    bf.write_atomic(FINDINGS, data)
    print(dict(stats), "->", FINDINGS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
