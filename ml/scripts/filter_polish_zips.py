"""Usuwa z paczek zip rekordy, które nie są po polsku. Pliki inne niż .jsonl zostają bez zmian.

Język ocenia investwatch_ml.language (porównanie słów polskich i obcych, detektor tylko dla niejasnych).
Decyzja jest per adres: jeśli którakolwiek wersja rekordu jest polska, zostają wszystkie wersje tego adresu.

  python ml/scripts/filter_polish_zips.py A.zip B.zip            # przebieg próbny
  python ml/scripts/filter_polish_zips.py --apply A.zip B.zip    # zapis, oryginał obok jako *.orig.zip
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from investwatch_ml import language  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

def text_of(r: dict) -> str:
    t = r.get("text")
    if isinstance(t, dict):
        return "\n".join(str(v) for v in t.values())
    if isinstance(t, list):
        return "\n".join(str(s.get("text", "")) for s in t if isinstance(s, dict))
    return str(t or "")


def is_polish(r: dict) -> bool:
    return language.is_polish(text_of(r))


def is_records(name: str) -> bool:
    return name.lower().endswith(".jsonl")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("zips", nargs="+")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    for path in map(Path, args.zips):
        polish: dict[str, bool] = defaultdict(bool)
        samples, total = [], Counter()
        with zipfile.ZipFile(path) as a:
            for n in filter(is_records, a.namelist()):
                for line in a.read(n).decode("utf-8").splitlines():
                    if line.strip():
                        r = json.loads(line)
                        u = r.get("source_url") or r.get("url") or line[:200]
                        polish[u] = polish[u] or is_polish(r)
                        samples.append((u, r.get("source"), r.get("author"), " ".join(text_of(r).split())[:90]))
        drop = {u for u, ok in polish.items() if not ok}
        print(f"\n{path}: adresy {len(polish)}, polskie {len(polish) - len(drop)}, do usunięcia {len(drop)}")
        print(" usuwane wg źródła:", dict(Counter(s for u, s, _, _ in {x[0]: x for x in samples if x[0] in drop}.values() for s in [s])))
        pick = [x for x in {x[0]: x for x in samples if x[0] in drop}.values()]
        random.Random(1).shuffle(pick)
        for _, s, au, t in pick[:12]:
            print(f"  - {s} | {str(au)[:20]} | {t}")
        if not args.apply:
            continue
        backup = path.with_name(path.stem + ".orig.zip")
        if not backup.exists():
            shutil.copy2(path, backup)
        tmp = path.with_suffix(".tmp")
        with zipfile.ZipFile(path) as src, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as dst:
            for info in src.infolist():
                data = src.read(info.filename)
                if is_records(info.filename):
                    kept = []
                    for line in data.decode("utf-8").splitlines():
                        if line.strip():
                            r = json.loads(line)
                            if (r.get("source_url") or r.get("url") or line[:200]) not in drop:
                                kept.append(line)
                    data = ("\n".join(kept) + "\n" if kept else "").encode("utf-8")
                dst.writestr(info, data)
        tmp.replace(path)
        print(f" zapisano; oryginał: {backup}")


if __name__ == "__main__":
    main()
