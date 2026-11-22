"""Dokleja do findings.real.json fikcyjne przykłady powiązań (id `demo-*`, kampania `C-demo-*`).

Dane są w demo_findings.json. Skrypt działa bez sieci i nie woła ai-service ani LLM.
Marki, osoby i numery są wymyślone, a domeny leżą w zarezerwowanej strefie `.example` (RFC 2606).
Można go uruchamiać wielokrotnie.

  python ml/scripts/add_demo_findings.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_findings import OUT, write_atomic  # noqa: E402

DEMO = Path(__file__).with_name("demo_findings.json")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file", type=Path, default=OUT)
    args = ap.parse_args()
    data = json.loads(args.file.read_text(encoding="utf-8"))
    demo = json.loads(DEMO.read_text(encoding="utf-8"))
    data["findings"] = [f for f in data["findings"] if not f["id"].startswith("demo-")] + demo["findings"]
    data["campaigns"] = [c for c in data.get("campaigns", []) if not str(c.get("id", "")).startswith("C-demo-")] + demo["campaigns"]
    write_atomic(args.file, data)
    print(f"demo: {len(demo['findings'])} rekordów, razem {len(data['findings'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
