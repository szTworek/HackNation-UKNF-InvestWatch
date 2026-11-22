"""Wspólne struktury danych: dokument w puli (format pośredni) i etykieta nauczyciela."""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class Doc(BaseModel):
    """Dokument do etykietowania / klasyfikacji.

    Offsety (evidence) zawsze odnoszą się do `full_text()`, czyli tytuł + treść.
    """

    id: str
    source: str  # youtube | reddit | cert_cc | scraper | smoke ...
    platform: str  # youtube | facebook | instagram | tiktok | x | reddit | web | other
    kind: str  # post | comment | transcript | page
    url: str | None = None
    author: str | None = None
    title: str | None = None
    text: str
    published_at: str | None = None
    outbound_links: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)

    def full_text(self) -> str:
        if self.title and self.title.strip():
            return f"{self.title.strip()}\n\n{self.text}"
        return self.text


class FlagHit(BaseModel):
    flag: str
    quote: str
    start: int | None = None  # offset w Doc.full_text()
    end: int | None = None
    align_score: float | None = None


class Entity(BaseModel):
    name: str
    role: str


class TeacherLabel(BaseModel):
    rationale: str
    topic: str
    content_type: str
    instruments: list[str]
    is_scam: bool
    scam_confidence: str
    flags: list[FlagHit]
    entities: list[Entity]



def read_jsonl(path: str | Path) -> Iterator[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return
    with p.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue  # ucięta ostatnia linia po przerwaniu zapisu


def append_jsonl(path: str | Path, rows: Iterable[dict[str, Any]]) -> int:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with p.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
    return n


def existing_ids(path: str | Path, key: str = "id") -> set[str]:
    return {str(r[key]) for r in read_jsonl(path) if key in r}
