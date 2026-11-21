"""Buduje lokalny rejestr firm inwestycyjnych z czterech list KNF wskazanych w załącznikach do zadania.

  uv run python scripts/build_knf_register.py

Wynik: src/investwatch_ml/knf_register.json (trafia do obrazu ai-service, lookup działa offline).
Skrypt przerywa pracę, gdy którakolwiek lista jest niepełna, żeby nie nadpisać rejestru częścią danych.
"""

from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

BASE = "https://www.knf.gov.pl/podmioty/Podmioty_rynku_kapitalowego/Firmy_inwestycyjne_i_Agenci_firm_inwestycyjnych"
LISTS = {
    "BANK": "Banki_prowadzace_dzialalnosc_maklerska",
    "BROKERAGE_HOUSE": "domy_maklerskie",
    "FOREIGN_BRANCH": "notyfikowane_firmy_inwestycyjne_oddzialy",
    "CROSS_BORDER": "notyfikowane_zagraniczne_firmy_inwestycyjne",
}
OUT = Path(__file__).resolve().parents[1] / "src" / "investwatch_ml" / "knf_register.json"
NAME_LABELS = ("Nazwa", "Nazwa podmiotu")


def lines(cell) -> list[str]:
    return [x.strip() for x in cell.get_text("\n").split("\n") if x.strip() and x.strip() != "-"]


def parse_page(html: str, list_type: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for table in soup.find_all("table"):
        row: dict[str, list[str]] = {}
        for tr in table.find_all("tr"):
            cells = tr.find_all(["th", "td"])
            if len(cells) >= 2:
                row[cells[0].get_text(" ", strip=True)] = lines(cells[1])
        names = next((row[k] for k in NAME_LABELS if row.get(k)), None)
        if not names:
            continue
        date = next((v[0] for k, v in row.items() if k.startswith("Data") and v), None)
        out.append({
            "name": names[0],
            "aliases": list(dict.fromkeys(names[1:])),
            "lists": [list_type],
            "country": (row.get("Państwo macierzyste") or ["Polska"])[0],
            "supervisor": (row.get("Organ nadzoru") or ["KNF"])[0],
            "registeredAt": date,
        })
    return out


def fetch_list(client: httpx.Client, list_type: str, slug: str) -> list[dict]:
    url = f"{BASE}/{slug}"
    first = client.get(url).raise_for_status().text
    match = re.search(r'\\?"totalPages\\?":\s*(\d+)', first)
    if not match:
        raise RuntimeError(f"{list_type}: brak informacji o liczbie stron")
    total = int(match.group(1))
    rows = parse_page(first, list_type)
    for page in range(2, total + 1):
        time.sleep(0.4)
        html = client.get(url, params={"page": page}).raise_for_status().text
        page_rows = parse_page(html, list_type)
        if not page_rows:
            raise RuntimeError(f"{list_type}: pusta strona {page}/{total}")
        rows += page_rows
    print(f"{list_type}: {len(rows)} podmiotów, {total} stron")
    return rows


def main() -> None:
    from investwatch_ml.knf import normalize_name

    merged: dict[str, dict] = {}
    with httpx.Client(timeout=40, follow_redirects=True, headers={"User-Agent": "InvestWatch-register-builder/0.1"}) as client:
        for list_type, slug in LISTS.items():
            for entity in fetch_list(client, list_type, slug):
                key = normalize_name(entity["name"])
                if key in merged:
                    known = merged[key]
                    known["lists"] = sorted({*known["lists"], *entity["lists"]})
                    known["aliases"] = list(dict.fromkeys(known["aliases"] + entity["aliases"]))
                else:
                    merged[key] = entity
    entities = sorted(merged.values(), key=lambda e: e["name"].casefold())
    OUT.write_text(json.dumps({
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": BASE,
        "entities": entities,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Zapisano {len(entities)} podmiotów do {OUT}")


if __name__ == "__main__":
    main()
