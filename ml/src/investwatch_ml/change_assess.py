"""Ocena LLM zmian na stronach firm (PageChange z monitora): czy zmiana ma znaczenie prawne.

Prompt: change_prompt.md. Silnik i limit partii jak w llm.py (LLM_BACKEND, LLM_BATCH).
Bez LLM albo przy błędzie zwraca None: wywołujący zostawia zmianę jako oczekującą, bez zmyślonego werdyktu.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from . import llm

PROMPT = (Path(__file__).parent / "change_prompt.md").read_text(encoding="utf-8")
PROMPT_VERSION = hashlib.sha1(PROMPT.encode()).hexdigest()[:8]
CATEGORIES = ("risk_info", "ad_marking", "sponsorship", "pricing", "other")
RULES = {f"R{n:02d}" for n in range(1, 19) if n != 12} | {"R12a", "R12b"}
MAX_LINES = 20
MAX_LINE_CHARS = 400
MAX_STYLES = 30
_CACHE: dict[str, dict] = {}


def build_input(change: dict[str, Any]) -> dict[str, Any]:
    """Skrócony rekord dla LLM; zmiany stylu bez powtórzeń między viewportami."""
    styles, seen = [], set()
    for s in change.get("style_changes") or []:
        sig = (s.get("text"), s.get("field"), str(s.get("before")), str(s.get("after")))
        if sig in seen:
            continue
        seen.add(sig)
        styles.append({k: v for k, v in s.items() if v is not None})
    return {"id": str(change["id"]), "entity_id": change.get("entity_id"), "url": change.get("url"),
            **{k: [str(x)[:MAX_LINE_CHARS] for x in (change.get(k) or [])[:MAX_LINES]] for k in ("added_lines", "removed_lines")},
            "style_changes": styles[:MAX_STYLES]}


def _rule(r: Any) -> str | None:
    m = re.fullmatch(r"R?0*(\d{1,2})([ab]?)", str(r).strip(), re.I)
    rid = f"R{int(m[1]):02d}{m[2].lower()}" if m else None
    return rid if rid in RULES else None


def normalize(res: dict) -> dict | None:
    """Odpowiedź LLM -> assessment z kontraktu albo None, gdy brak rozstrzygnięcia."""
    rel = res.get("relevant")
    if isinstance(rel, str) and rel.lower() in ("true", "false"):
        rel = rel.lower() == "true"
    reason = str(res.get("reason") or "").strip()
    if not isinstance(rel, bool) or not reason:
        return None
    cat = str(res.get("category") or "").strip().lower()
    rules = [] if not rel else list(dict.fromkeys(x for x in map(_rule, res.get("rules") or []) if x))
    return {"relevant": rel, "category": cat if cat in CATEGORIES else "other", "reason": reason,
            "rules": rules, "model": llm.MODEL}


def _key(inp: dict) -> str:
    body = json.dumps({k: v for k, v in inp.items() if k != "id"}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(f"{PROMPT_VERSION}|{llm.MODEL}|{body}".encode()).hexdigest()


def _call(items: list[dict]) -> dict[str, dict]:
    return {str(x.get("id")): x for x in llm._call(items, PROMPT, "relevant")}


def assess(changes: list[dict[str, Any]]) -> dict[str, dict | None]:
    """id -> assessment albo None (LLM wyłączony, błąd, limit, brak poprawnej odpowiedzi)."""
    inputs = [build_input(c) for c in changes]
    out: dict[str, dict | None] = {inp["id"]: None for inp in inputs}
    if not llm.enabled():
        return out
    todo = []
    for inp in inputs:
        key = _key(inp)
        if key in _CACHE:
            out[inp["id"]] = _CACHE[key]
        else:
            todo.append((key, inp))
    for i in range(0, len(todo), llm.BATCH):
        chunk = todo[i:i + llm.BATCH]
        try:
            got = _call([inp for _, inp in chunk])
        except Exception:  # noqa: BLE001 - awaria LLM zostawia zmiany jako oczekujące
            got = {}
        for key, inp in chunk:
            res = normalize(got[inp["id"]]) if inp["id"] in got else None
            if res is None and len(chunk) > 1:  # ponowienie pojedynczo
                try:
                    single = llm._call([inp], PROMPT, "relevant")
                    res = normalize(single[0]) if single else None
                except Exception:  # noqa: BLE001
                    res = None
            if res is not None:
                _CACHE[key] = res
                out[inp["id"]] = res
    return out
