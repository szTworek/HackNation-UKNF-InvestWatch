"""Buduje frontend/mock-server/data/findings.real.json z prawdziwych rekordów scrapera i wyników ai-service.

Wymaga działającego ai-service. Używa tylko biblioteki standardowej:
  python ml/scripts/build_findings.py [--ai-url http://localhost:8000]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Iterable, Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "frontend" / "mock-server" / "data" / "findings.real.json"
CERT_DOMAINS = ROOT / "ml" / "data" / "raw" / "cert_domains.json"
BATCH_SIZE = 32
MIN_SCAM_P = 0.3
TRANSCRIPT_MARKER = "[TRANSKRYPCJA]"
PLATFORMS = {"facebook", "instagram", "tiktok", "youtube", "x", "web", "other"}
KINDS = {"post", "transcript", "comment", "page"}


def read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def m3_record(doc: dict[str, Any]) -> dict[str, Any]:
    """Kandydat M3 w formacie `Doc` jako rekord kolektora."""
    meta = doc.get("meta") if isinstance(doc.get("meta"), dict) else {}
    query = meta.get("query")
    return {
        "source": "youtube",
        "source_url": doc.get("url"),
        "author": doc.get("author"),
        "published_at": doc.get("published_at"),
        "fetched_at": doc.get("fetched_at"),
        "query_keywords": [query] if query else [],
        "content_keywords": [],
        "text": {"title": doc.get("title") or "", "description": doc.get("text") or ""},
        "links": doc.get("outbound_links") or [],
        "content_type": "video",
        "source_meta": meta,
    }


def load_records() -> tuple[list[dict[str, Any]], Counter]:
    stats: Counter = Counter()
    rows: list[tuple[str, dict[str, Any]]] = []
    for pattern in ("data/export/*/records.jsonl", "ml/data/raw/scraper_live/*/records.jsonl"):
        for path in sorted(ROOT.glob(pattern)):
            rows += [(path.parent.name, row) for row in read_jsonl(path)]
    m3 = ROOT / "ml" / "data" / "pool" / "m3_youtube.jsonl"
    if m3.exists():
        rows += [("m3_youtube", m3_record(row)) for row in read_jsonl(m3)]
    seen: set[str] = set()
    records: list[dict[str, Any]] = []
    for origin, row in rows:
        stats["read"] += 1
        url = row.get("source_url")
        if not url:
            stats["missingUrl"] += 1
        elif url in seen:
            stats["duplicateUrl"] += 1
        else:
            seen.add(url)
            records.append(row)
            stats[f"source.{origin}"] += 1
    return records, stats


def request(method: str, url: str, payload: Any = None, timeout: int = 900) -> Any:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as res:  # noqa: S310 - adres ai-service podaje operator
        return json.load(res)


def iso(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def load_cert_domains() -> set[str]:
    if not CERT_DOMAINS.exists():
        return set()
    rows = json.loads(CERT_DOMAINS.read_text(encoding="utf-8"))
    return {r["DomainAddress"].lower() for r in rows if r.get("DomainAddress") and not r.get("DeleteDate")}


def on_cert_list(url: str, domains: set[str]) -> bool:
    host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
    parts = host.split(".")
    return any(".".join(parts[i:]) in domains for i in range(max(len(parts) - 1, 1)))


def clean_evidence(evidence: Iterable[dict[str, Any]], text: str, stats: Counter) -> list[dict[str, Any]]:
    """Zostawia tylko dowody, których offsety wskazują dokładnie cytowany fragment."""
    out = []
    for e in evidence or []:
        start, end = e.get("start"), e.get("end")
        if isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(text) and text[start:end] == e.get("text"):
            out.append({k: e[k] for k in ("section", "start", "end", "text", "t") if k in e})
        else:
            stats["evidenceDropped"] += 1
    return out


def to_finding(item: dict[str, Any], analysis: dict[str, Any], imported_at: str, cert: set[str], stats: Counter) -> dict[str, Any]:
    text = analysis["analyzedText"]
    flags = {k: {"p": v["p"], "evidence": clean_evidence(v.get("evidence"), text, stats)} for k, v in analysis["flags"].items()}
    rules = [{**r, "evidence": clean_evidence(r.get("evidence"), text, stats)} for r in analysis["rules"]]
    fetched = iso(item.get("fetchedAt")) or imported_at
    author = {k: v for k, v in (item.get("author") or {}).items() if v is not None}
    author.setdefault("handle", "nieznany")
    links = item.get("outboundLinks") or []
    finding: dict[str, Any] = {
        "id": item["id"],
        "url": item["url"],
        "platform": item["platform"] if item.get("platform") in PLATFORMS else "other",
        "kind": item["kind"] if item.get("kind") in KINDS else "post",
        "author": author,
        "text": text,
        "fetchedAt": fetched,
        "modules": analysis["modules"],
        "topic": analysis["topic"],
        "contentType": analysis["contentType"],
        "instruments": analysis["instruments"],
        "flags": flags,
        "rules": rules,
        "entities": analysis["entities"],
        "outboundLinks": links,
        "scam": analysis["scam"],
        "landingPages": [],
        "indicators": analysis["indicators"],
        "related": [],
        "riskScore": analysis["riskScore"],
        "riskLevel": analysis["riskLevel"],
        "status": "NEW",
        "history": [{"at": imported_at, "status": "NEW", "user": "system", "comment": "zaimportowano"}],
        "modelVersion": analysis["modelVersion"],
        "blockedUrls": [u for u in [item["url"], *links] if on_cert_list(u, cert)],
    }
    if item.get("title"):
        finding["title"] = item["title"]
    published = iso(item.get("publishedAt"))
    if published:
        finding["publishedAt"] = published
    if TRANSCRIPT_MARKER in text:
        finding["transcript"] = text.split(TRANSCRIPT_MARKER, 1)[1].strip()
    if analysis.get("scoringInput") is not None:
        finding["scoringInput"] = analysis["scoringInput"]
    return finding


def keep(analysis: dict[str, Any], topic_threshold: float) -> bool:
    topic = analysis["topic"]
    investment = topic.get("INVESTMENT", 0) >= topic_threshold or max(topic, key=topic.get) == "INVESTMENT"
    return investment or analysis["scam"]["p"] >= MIN_SCAM_P or bool(analysis["modules"])


def build_campaigns(ai_url: str, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Kampanie z ai-service. Brak endpointu oznacza pustą listę, bez generowania zastępczych danych."""
    payload = {"items": [{
        "id": f["id"], "text": f["text"], "author": f["author"]["handle"], "platform": f["platform"],
        "indicators": f["indicators"], "scamP": f["scam"]["p"], "fetchedAt": f["fetchedAt"],
    } for f in findings]}
    try:
        result = request("POST", f"{ai_url}/campaigns/build", payload)
    except urllib.error.HTTPError as ex:
        if ex.code in (404, 405):
            return []
        raise
    by_id = {f["id"]: f for f in findings}
    for finding_id, campaign_id in result.get("assignments", {}).items():
        if finding_id in by_id:
            by_id[finding_id]["campaignId"] = campaign_id
    for finding_id, related in result.get("related", {}).items():
        if finding_id in by_id:
            by_id[finding_id]["related"] = [r for r in related if r.get("findingId") in by_id][:5]
    return result.get("campaigns", [])


def write_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ai-url", default=os.environ.get("AI_URL", "http://localhost:8000"))
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    ai_url = args.ai_url.rstrip("/")
    imported_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    try:
        health = request("GET", f"{ai_url}/health", timeout=10)
        thresholds = request("GET", f"{ai_url}/thresholds/default", timeout=10)
    except (urllib.error.URLError, TimeoutError) as ex:
        print(f"Brak połączenia z ai-service ({ai_url}): {ex}", file=sys.stderr)
        return 1

    records, stats = load_records()
    cert = load_cert_domains()
    topic_threshold = thresholds["values"].get("topic.INVESTMENT", 0.5)
    findings: list[dict[str, Any]] = []
    for i in range(0, len(records), BATCH_SIZE):
        response = request("POST", f"{ai_url}/ingest", {"records": records[i:i + BATCH_SIZE]})
        for key in ("rejected", "duplicates"):
            stats[f"ingest.{key}"] += response.get("stats", {}).get(key, 0)
        for result in response["results"]:
            stats["analyzed"] += 1
            if keep(result["analysis"], topic_threshold):
                findings.append(to_finding(result["item"], result["analysis"], imported_at, cert, stats))
            else:
                stats["outOfScope"] += 1
        print(f"{min(i + BATCH_SIZE, len(records))}/{len(records)}", file=sys.stderr, flush=True)
    if not findings:
        print("Brak rekordów do zapisania; poprzedni plik pozostaje bez zmian.", file=sys.stderr)
        return 1

    campaigns = build_campaigns(ai_url, findings)
    stats["kept"] = len(findings)
    stats["campaigns"] = len(campaigns)
    stats["blockedLinks"] = sum(len(f["blockedUrls"]) for f in findings)
    for f in findings:
        stats[f"risk.{f['riskLevel']}"] += 1
        for module in f["modules"]:
            stats[f"module.{module}"] += 1
    write_atomic(args.out, {
        "generatedAt": imported_at,
        "modelVersion": health["modelVersion"],
        "thresholds": thresholds,
        "findings": findings,
        "campaigns": campaigns,
        "stats": dict(sorted(stats.items())),
    })
    print(json.dumps({"out": str(args.out), "modelVersion": health["modelVersion"], "stats": dict(sorted(stats.items()))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
