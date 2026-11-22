"""Lookup w rejestrze firm inwestycyjnych KNF (knf_register.json, budowany przez scripts/build_knf_register.py).

Brak w rejestrze to sygnał do weryfikacji przez analityka, nie stwierdzenie naruszenia.
"""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz, process

REGISTER_PATH = Path(__file__).with_name("knf_register.json")

_LEGAL = {
    "sa", "s", "a", "ag", "se", "nv", "bv", "plc", "ltd", "limited", "llc", "llp", "lp", "gmbh", "kg", "co", "inc", "ab",
    "as", "oy", "oyj", "spa", "srl", "sl", "sas", "sarl", "ood", "eood", "doo", "kft", "sro", "ocp", "cyprus", "europe",
    "sp", "z", "o", "oo", "spolka", "akcyjna", "akcyjny", "oddzial", "w", "polsce", "polska", "the", "and", "i",
}
_GENERIC = {
    "bank", "banku", "dom", "maklerski", "biuro", "maklerskie", "departament", "capital", "invest", "investment",
    "investments", "financial", "finance", "services", "service", "markets", "market", "trading", "trade", "securities",
    "asset", "assets", "management", "group", "global", "international", "holding", "holdings", "partners", "wealth",
    "advisors", "advisory", "fund", "funds", "broker", "brokers", "firma", "fx", "cfd", "online", "digital", "crypto",
    "first", "new", "one", "best", "prime", "direct", "plus", "pro", "money", "solutions", "consulting", "company",
}
# marki używane w reklamach zamiast pełnej nazwy z rejestru (tylko gdy ta nazwa jest w rejestrze)
_BRANDS = {"xtb": "XTB S.A.", "mbank": "mBank S.A.", "bossa": "Dom Maklerski Banku Ochrony Środowiska S.A."}


def _ascii(text: str) -> str:
    text = text.replace("ł", "l").replace("Ł", "L")
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", _ascii(text).casefold().replace(".", ""))


def normalize_name(name: str) -> str:
    """Nazwa bez form prawnych, znaków diakrytycznych i interpunkcji."""
    all_tokens = tokens(name)
    core = [t for t in all_tokens if t not in _LEGAL]
    return " ".join(core or all_tokens)


class Register:
    def __init__(self, data: dict[str, Any]) -> None:
        self.generated_at = data.get("generatedAt")
        self.entities: list[dict[str, Any]] = data.get("entities", [])
        self.by_name: dict[str, dict[str, Any]] = {}
        self.phrases: dict[str, list[tuple[tuple[str, ...], dict[str, Any]]]] = {}
        for entity in self.entities:
            for name in [entity["name"], *entity.get("aliases", [])]:
                key = normalize_name(name)
                if key:
                    self.by_name.setdefault(key, entity)
                    self._add_phrase(key.split(), entity)
        for brand, official in _BRANDS.items():
            entity = self.by_name.get(normalize_name(official))
            if entity:
                self.by_name.setdefault(brand, entity)
                self._add_phrase([brand], entity)
        self.keys = list(self.by_name)

    def _add_phrase(self, words: list[str], entity: dict[str, Any]) -> None:
        # pojedyncze słowo tylko, gdy jest wyróżniające; inaczej „Capital” dopasowałby pół internetu
        if len(words) == 1 and (len(words[0]) < 3 or words[0] in _GENERIC or words[0].isdigit()):
            return
        if all(w in _GENERIC for w in words):
            return
        self.phrases.setdefault(words[0], []).append((tuple(words), entity))

    def lookup(self, name: str | None, min_score: float = 93.0) -> dict[str, Any]:
        """Status podmiotu o znanej nazwie (autor, sponsor)."""
        key = normalize_name(name or "")
        if not key:
            return {"status": "NOT_FOUND"}
        entity = self.by_name.get(key)
        score = 1.0
        if entity is None and len(key) >= 6 and not set(key.split()) <= _GENERIC:
            hit = process.extractOne(key, self.keys, scorer=fuzz.token_sort_ratio, score_cutoff=min_score)
            if hit:
                entity, score = self.by_name[hit[0]], hit[1] / 100
        if entity is None:
            # inna spółka tej samej marki (eToro Group / Etoro (Europe)) to nie jest wpis tego podmiotu: analityk weryfikuje
            related = self._same_brand(key)
            return {"status": "NOT_FOUND", "relatedEntity": related["name"]} if related else {"status": "NOT_FOUND"}
        return {"status": "REGISTERED", "matchedName": entity["name"], "score": round(score, 3), "lists": entity["lists"]}

    def _same_brand(self, key: str) -> dict[str, Any] | None:
        brand = next((w for w in key.split() if w not in _GENERIC and len(w) >= 5), None)
        if brand is None:
            return None
        for known, entity in self.by_name.items():
            first = next((w for w in known.split() if w not in _GENERIC and len(w) >= 5), None)
            if first and (first == brand or first.startswith(brand) or brand.startswith(first)):
                return entity
        return None

    def mentions(self, text: str, limit: int = 8) -> list[dict[str, Any]]:
        """Firmy z rejestru wymienione w tekście, dopasowanie całych słów, najdłuższa fraza wygrywa."""
        words = tokens(text)
        found: dict[str, dict[str, Any]] = {}
        i = 0
        while i < len(words):
            best: tuple[tuple[str, ...], dict[str, Any]] | None = None
            for phrase, entity in self.phrases.get(words[i], []):
                if tuple(words[i:i + len(phrase)]) == phrase and (best is None or len(phrase) > len(best[0])):
                    best = (phrase, entity)
            if best:
                found.setdefault(best[1]["name"], best[1])
                i += len(best[0])
            else:
                i += 1
        return list(found.values())[:limit]


@lru_cache(maxsize=1)
def register() -> Register:
    if not REGISTER_PATH.exists():
        return Register({})
    return Register(json.loads(REGISTER_PATH.read_text(encoding="utf-8")))


def resolve_entities(text: str, publisher: str | None = None) -> list[dict[str, Any]]:
    """Podmioty rekordu w formacie `Entity` frontu. `publisher: true` oznacza autora lub sponsora materiału."""
    reg = register()
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    if publisher and publisher.strip():
        status = reg.lookup(publisher)
        registered = status["status"] == "REGISTERED"
        name = status.get("matchedName", publisher.strip())
        seen.add(name)
        out.append({"name": name, "role": "investment_firm" if registered else "advertiser", "publisher": True,
                    "knfRegister": status})
    for entity in reg.mentions(text):
        if entity["name"] not in seen:
            seen.add(entity["name"])
            out.append({"name": entity["name"], "role": "investment_firm", "knfRegister": {
                "status": "REGISTERED", "matchedName": entity["name"], "score": 1.0, "lists": entity["lists"]}})
    return out[:8]
