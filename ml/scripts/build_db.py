"""Buduje bazę SQLite z wyników: rekordy, decyzje, czynniki, źródła i graf powiązań.

  python ml/scripts/build_db.py [--out data/db/investwatch.sqlite]

Graf: węzły finding, publisher, firm, rule, indicator (domena, telefon, Telegram...), keyword_signal.
Przykład: wszystkie rekordy połączone z tym samym kanałem Telegram:
  SELECT e.src FROM edges e WHERE e.dst = 'indicator:telegram:nazwa' AND e.type = 'HAS_INDICATOR';
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = """
CREATE TABLE findings(id TEXT PRIMARY KEY, url TEXT, platform TEXT, kind TEXT, author TEXT, title TEXT, text TEXT,
  published_at TEXT, fetched_at TEXT, status TEXT, module TEXT, confidence REAL, risk_level TEXT, risk_score REAL,
  reason TEXT, needs_human INTEGER, model TEXT, prompt_version TEXT, decided_at TEXT, publisher_knf TEXT, campaign_id TEXT);
CREATE TABLE module_scores(finding_id TEXT, module TEXT, score REAL, PRIMARY KEY(finding_id, module));
CREATE TABLE decision_factors(finding_id TEXT, kind TEXT, name TEXT, value TEXT);
CREATE TABLE rule_results(finding_id TEXT, rule_id TEXT, status TEXT, score REAL, quote TEXT);
CREATE TABLE sources(finding_id TEXT, url TEXT, kind TEXT);
CREATE TABLE nodes(id TEXT PRIMARY KEY, type TEXT, label TEXT);
CREATE TABLE edges(src TEXT, dst TEXT, type TEXT, detail TEXT, PRIMARY KEY(src, dst, type));
CREATE INDEX idx_findings_module ON findings(module, risk_level);
CREATE INDEX idx_factors ON decision_factors(finding_id);
CREATE INDEX idx_edges_dst ON edges(dst, type);
CREATE VIEW flagged AS SELECT id, module, confidence, risk_level, author, reason, url FROM findings
  WHERE module IN ('M1', 'M2', 'M3') ORDER BY confidence DESC;
CREATE VIEW shared_indicators AS SELECT e.dst AS indicator, COUNT(*) AS findings FROM edges e
  WHERE e.type = 'HAS_INDICATOR' GROUP BY e.dst HAVING COUNT(*) > 1 ORDER BY findings DESC;
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, default=ROOT / "frontend/mock-server/data/findings.real.json")
    ap.add_argument("--out", type=Path, default=ROOT / "data/db/investwatch.sqlite")
    args = ap.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.out.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript(SCHEMA)

    def node(nid: str, kind: str, label: str) -> str:
        db.execute("INSERT OR IGNORE INTO nodes VALUES (?,?,?)", (nid, kind, label))
        return nid

    def edge(src: str, dst: str, kind: str, detail: str = "") -> None:
        db.execute("INSERT OR IGNORE INTO edges VALUES (?,?,?,?)", (src, dst, kind, detail))

    for f in data["findings"]:
        fid, llm = f["id"], f.get("llm") or {}
        dec, trace = llm.get("decision") or {}, (llm.get("decision") or {}).get("trace") or {}
        author = (f.get("author") or {}).get("displayName") or (f.get("author") or {}).get("handle")
        publisher = dec.get("publisher") or {}
        module = llm.get("module") or (f"M{f['modules'][0]}" if f.get("modules") else "NONE")
        db.execute("INSERT INTO findings VALUES (" + ",".join("?" * 21) + ")", (
            fid, f.get("url"), f.get("platform"), f.get("kind"), author, f.get("title"), f.get("text"), f.get("publishedAt"),
            f.get("fetchedAt"), f.get("status"), module, llm.get("confidence"), f.get("riskLevel"), f.get("riskScore"),
            llm.get("reason"), int(bool(llm.get("needsHuman"))), llm.get("model") or f.get("modelVersion"),
            trace.get("promptVersion"), trace.get("decidedAt"), publisher.get("knfStatus"), f.get("campaignId")))
        for m, s in (llm.get("scores") or {}).items():
            db.execute("INSERT INTO module_scores VALUES (?,?,?)", (fid, m, s))
        n = node(f"finding:{fid}", "finding", (f.get("title") or f.get("text") or "")[:80])
        if author:
            edge(n, node(f"publisher:{author.lower()}", "publisher", author), "PUBLISHED_BY", str(publisher.get("knfStatus") or ""))
        firms = list(dict.fromkeys([x for x in [dec.get("firm"), *(dec.get("mentionedFirms") or [])] if x]))
        for firm in firms:
            edge(n, node(f"firm:{firm.lower()}", "firm", firm), "CONCERNS_FIRM")
            db.execute("INSERT INTO decision_factors VALUES (?,?,?,?)", (fid, "firm", firm, ""))
        if publisher.get("impersonates"):
            edge(n, node(f"firm:{str(publisher['impersonates']).lower()}", "firm", str(publisher["impersonates"])), "IMPERSONATES")
            db.execute("INSERT INTO decision_factors VALUES (?,?,?,?)", (fid, "impersonation", str(publisher["impersonates"]), ""))
        db.execute("INSERT INTO decision_factors VALUES (?,?,?,?)", (fid, "publisher_knf", str(author), str(publisher.get("knfStatus"))))
        for group, words in (dec.get("keywordSignals") or {}).items():
            db.execute("INSERT INTO decision_factors VALUES (?,?,?,?)", (fid, "keyword", group, ", ".join(words)))
            edge(n, node(f"signal:{group}", "keyword_signal", group), "HAS_SIGNAL", ", ".join(words))
        for s in dec.get("riskSignals") or []:
            db.execute("INSERT INTO decision_factors VALUES (?,?,?,?)", (fid, "risk_signal", str(s.get("type")), str(s.get("quote", ""))))
        for r in dec.get("ruleFindings") or []:
            db.execute("INSERT INTO rule_results VALUES (?,?,?,?,?)", (fid, r["ruleId"], r.get("status"), None, r.get("quote")))
            if r.get("status") == "VIOLATION":
                edge(n, node(f"rule:{r['ruleId']}", "rule", f"Reguła {r['ruleId']}"), "VIOLATES", str(r.get("quote", ""))[:200])
        db.execute("INSERT INTO sources VALUES (?,?,?)", (fid, f.get("url"), "source"))
        for u in f.get("outboundLinks") or []:
            db.execute("INSERT INTO sources VALUES (?,?,?)", (fid, u, "outbound"))
        for ind in f.get("indicators") or []:
            value = str(ind.get("value", "")).lower()
            edge(n, node(f"indicator:{ind.get('type')}:{value}", "indicator", f"{ind.get('type')}: {ind.get('value')}"), "HAS_INDICATOR")
        if f.get("campaignId"):
            edge(n, node(f"campaign:{f['campaignId']}", "campaign", f["campaignId"]), "IN_CAMPAIGN")
    db.commit()
    counts = {t: db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("findings", "decision_factors", "rule_results", "sources", "nodes", "edges")}
    db.close()
    tmp.replace(args.out)
    print(counts, "->", args.out)


if __name__ == "__main__":
    main()
