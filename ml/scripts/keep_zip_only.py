"""Zostawia w danych frontu tylko rekordy obecne w paczkach zip i przelicza kampanie na tym zbiorze.

Surowe dane nie są zmieniane. Poprzedni stan zapisuje jako findings.real.before_zip_only.json.

  python ml/scripts/keep_zip_only.py data/paczka1.zip ../inne/paczka2.zip
"""

from __future__ import annotations

import json
import shutil
import sys
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_findings as bf  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
FINDINGS = ROOT / "frontend/mock-server/data/findings.real.json"


def zip_urls(path: str) -> set[str]:
    urls: set[str] = set()
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if name.replace(chr(92), "/").rsplit("/", 1)[-1] != "records.jsonl":
                continue
            for line in archive.read(name).decode("utf-8").splitlines():
                if line.strip():
                    urls.add(json.loads(line).get("source_url"))
    print(f"{path}: {len(urls)} adresów")
    return urls


def main() -> None:
    urls = set().union(*(zip_urls(p) for p in sys.argv[1:]))
    data = json.loads(FINDINGS.read_text(encoding="utf-8"))
    before = data["findings"]
    backup = FINDINGS.with_name("findings.real.before_zip_only.json")
    if not backup.exists():
        shutil.copyfile(FINDINGS, backup)
    kept = [f for f in before if f["url"] in urls]
    for f in kept:  # powiązania i kampanie mogły wskazywać usunięte rekordy
        f.pop("campaignId", None)
        f["related"] = []
    data["findings"] = kept
    data["campaigns"] = bf.build_campaigns("http://localhost:8000", kept)
    data.setdefault("stats", {})["zipOnly"] = {"before": len(before), "kept": len(kept)}
    bf.write_atomic(FINDINGS, data)
    removed = [f for f in before if f["url"] not in urls]
    print(f"zostało {len(kept)}, usunięto {len(removed)} (demo: {sum(f['id'].startswith('demo-') for f in removed)})")
    print("z LLM:", sum("llm" in f for f in kept), "| bez LLM, ale w module:", sum("llm" not in f and bool(f["modules"]) for f in kept))
    print("moduły:", dict(Counter((f"M{f['modules'][0]}" if f["modules"] else "NONE") for f in kept)),
          "| ryzyko:", dict(Counter(f["riskLevel"] for f in kept)), "| kampanie:", len(data["campaigns"]))


if __name__ == "__main__":
    main()
