"""Preprocessing tekstu: normalizacja, dzielenie na fragmenty, dopasowanie cytatów (evidence) do offsetów."""

from __future__ import annotations

import re
import unicodedata

from rapidfuzz import fuzz

_ZERO_WIDTH = re.compile(r"[​-‏⁠﻿]")
_SPACES = re.compile(r"[ \t ]+")
_MANY_NL = re.compile(r"\n{3,}")


def normalize(text: str) -> str:
    """NFC, bez znaków zerowej szerokości, zredukowane białe znaki. Emoji i hashtagi zostają (to sygnały)."""
    text = unicodedata.normalize("NFC", text or "")
    text = _ZERO_WIDTH.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _SPACES.sub(" ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    text = _MANY_NL.sub("\n\n", text)
    return text.strip()


def chunk_spans(text: str, max_chars: int, overlap: int = 0) -> list[tuple[int, int]]:
    """Dzieli tekst na fragmenty <= max_chars, cięcie na granicy zdania / linii / spacji. Zwraca (start, end)."""
    n = len(text)
    if n <= max_chars:
        return [(0, n)]
    spans: list[tuple[int, int]] = []
    start = 0
    while start < n:
        end = min(start + max_chars, n)
        if end < n:
            window = text[start:end]
            cut = -1
            for sep in ("\n", ". ", "! ", "? ", " "):
                idx = window.rfind(sep, int(max_chars * 0.6))
                if idx > cut:
                    cut = idx
                    break
            if cut > 0:
                end = start + cut + 1
        spans.append((start, end))
        if end >= n:
            break
        start = max(end - overlap, start + 1)
        # nie zaczynaj w środku słowa
        while start < n and start > 0 and not text[start - 1].isspace() and start < end:
            start += 1
    return spans


def word_windows(text: str, size: int = 50, stride: int = 25) -> list[tuple[int, int]]:
    """Okna po `size` słów z krokiem `stride` (transkrypcje ASR nie mają interpunkcji). Zwraca (start, end)."""
    words = [(m.start(), m.end()) for m in re.finditer(r"\S+", text)]
    if not words:
        return []
    spans = []
    i = 0
    while True:
        j = min(i + size, len(words))
        spans.append((words[i][0], words[j - 1][1]))
        if j >= len(words):
            break
        i += stride
    return spans


def _strip_quote(q: str) -> str:
    return q.strip().strip("\"'„”“«»…").strip().rstrip(".").strip()


def align_quote(text: str, quote: str, min_score: float = 80.0) -> tuple[int, int, float] | None:
    """Znajduje cytat (podany przez LLM, czasem lekko zmieniony) w tekście. Zwraca (start, end, score)."""
    q = _strip_quote(quote)
    if len(q) < 4:
        return None
    i = text.find(q)
    if i >= 0:
        return i, i + len(q), 100.0
    low, ql = text.lower(), q.lower()
    i = low.find(ql)
    if i >= 0:
        return i, i + len(q), 99.0
    # tolerancja na różnice w białych znakach
    pattern = r"\s+".join(re.escape(w) for w in ql.split())
    m = re.search(pattern, low)
    if m:
        return m.start(), m.end(), 98.0
    al = fuzz.partial_ratio_alignment(ql, low, score_cutoff=min_score)
    if al is None:
        return None
    return al.dest_start, al.dest_end, round(al.score, 1)
