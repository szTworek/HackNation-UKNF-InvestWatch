"""Graf kampanii: łączy rekordy po wspólnych wskaźnikach i podobnym tekście, lokalnie i bez bazy.

Krawędzie mocne to wspólna domena, telefon, komunikator, e-mail, portfel lub IBAN. Krawędzie słabsze to bardzo podobny
tekst rekordów podejrzanych. Wskaźniki popularne są pomijane, żeby nie skleić wszystkiego w jedną kampanię.
Wynik jest wskazówką dla analityka, a nie stwierdzeniem, że rekordy mają wspólnego autora.
"""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from typing import Any

import networkx as nx
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from .indicators import COMMON_DOMAINS

STRONG_TYPES = ("wallet", "iban", "phone", "whatsapp", "telegram", "email", "domain")
TYPE_NAMES = {"wallet": "portfel", "iban": "konto", "phone": "telefon", "whatsapp": "WhatsApp", "telegram": "Telegram",
              "email": "e-mail", "domain": "domena"}
SUSPICIOUS_P = 0.3
EMBED_SIMILARITY = 0.92
TFIDF_SIMILARITY = 0.75  # bez modelu podobieństwo liczone jest na TF-IDF, które ma inną skalę
MAX_NEIGHBOURS = 10
MIN_MEMBERS = 3
MIN_SUSPICIOUS_SHARE = 0.5
MIN_PEAK_SCAM = 0.6
MIN_WORDS_FOR_SIMILARITY = 8  # krótkie teksty są podobne przypadkiem


def _key(indicator: dict[str, Any]) -> tuple[str, str]:
    return str(indicator.get("type")), str(indicator.get("value", "")).strip().lower()


def _usable(key: tuple[str, str]) -> bool:
    kind, value = key
    return kind in STRONG_TYPES and bool(value) and not (kind == "domain" and value in COMMON_DOMAINS)


def _vectors(texts: list[str], embed: Callable[[list[str]], np.ndarray] | None) -> tuple[np.ndarray, float]:
    if embed is not None:
        return np.asarray(embed([t[:2000] for t in texts])), EMBED_SIMILARITY
    matrix = TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True).fit_transform(texts)
    return matrix.toarray().astype(np.float32), TFIDF_SIMILARITY  # TfidfVectorizer normalizuje L2


def build(items: Sequence[dict[str, Any]], embed: Callable[[list[str]], np.ndarray] | None = None) -> dict[str, Any]:
    items = sorted({str(x["id"]): x for x in items}.values(), key=lambda x: str(x["id"]))
    n = len(items)
    empty = {"campaigns": [], "assignments": {}, "related": {}}
    if n < MIN_MEMBERS:
        return empty

    originals: dict[tuple[str, str], dict[str, str]] = {}
    holders: dict[tuple[str, str], list[int]] = defaultdict(list)
    for i, item in enumerate(items):
        for ind in item.get("indicators") or []:
            key = _key(ind)
            if _usable(key) and i not in holders[key]:
                holders[key].append(i)
                originals.setdefault(key, {"type": key[0], "value": str(ind.get("value")).strip()})
    limit = max(10, int(0.05 * n))
    shared = {k: v for k, v in holders.items() if 2 <= len(v) <= limit}

    edges: dict[tuple[int, int], dict[str, Any]] = {}

    def edge(a: int, b: int) -> dict[str, Any]:
        return edges.setdefault((min(a, b), max(a, b)), {"weight": 0.0, "indicators": [], "similarity": 0.0})

    for key, members in shared.items():
        for x, a in enumerate(members):
            for b in members[x + 1:]:
                e = edge(a, b)
                e["weight"] += 1.0
                e["indicators"].append(key)

    suspicious = [i for i, x in enumerate(items) if float(x.get("scamP") or 0) >= SUSPICIOUS_P
                  and len((x.get("text") or "").split()) >= MIN_WORDS_FOR_SIMILARITY]
    if len(suspicious) >= 2:
        vectors, threshold = _vectors([items[i]["text"] for i in suspicious], embed)
        for row in range(len(suspicious)):
            sims = vectors[row + 1:] @ vectors[row]
            hits = np.where(sims >= threshold)[0]
            for offset in hits[np.argsort(-sims[hits])][:MAX_NEIGHBOURS]:
                e = edge(suspicious[row], suspicious[row + 1 + int(offset)])
                sim = float(sims[offset])
                e["similarity"] = max(e["similarity"], sim)
                e["weight"] += 0.6 * sim
    if not edges:
        return empty

    graph = nx.Graph()
    for (a, b), e in sorted(edges.items()):
        graph.add_edge(a, b, weight=e["weight"])
    communities = nx.community.louvain_communities(graph, weight="weight", seed=42)

    campaigns, assignments, used_ids = [], {}, set()
    for community in sorted((sorted(c) for c in communities), key=lambda c: (-len(c), c)):
        if len(community) < MIN_MEMBERS:
            continue
        members = set(community)
        counts = Counter(k for k, v in shared.items() for i in v if i in members)
        common = [k for k, c in counts.items() if c >= 2]
        authors = {str(items[i].get("author") or "").strip().lower() for i in community} - {""}
        if len(authors) < 2 and not common:
            continue
        share = sum(float(items[i].get("scamP") or 0) >= SUSPICIOUS_P for i in community) / len(community)
        peak = max(float(items[i].get("scamP") or 0) for i in community)
        if share < MIN_SUSPICIOUS_SHARE or peak < MIN_PEAK_SCAM:  # np. wiele legalnych reklam jednej firmy z tą samą domeną
            continue
        common.sort(key=lambda k: (-counts[k], STRONG_TYPES.index(k[0]), k[1]))
        top = common[:5]
        member_ids = [str(items[i]["id"]) for i in community]
        seed = "|".join(f"{t}:{v}" for t, v in sorted(top[:3])) or "|".join(member_ids)
        cid = "C-" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:8]
        if cid in used_ids:
            cid = "C-" + hashlib.sha1("|".join(member_ids).encode("utf-8")).hexdigest()[:8]
        used_ids.add(cid)
        if top:
            name = f"Kampania: {TYPE_NAMES[top[0][0]]} {originals[top[0]]['value']}"
        else:
            name = f"Kampania: podobne treści ({len(community)} rekordów)"
        campaigns.append({"id": cid, "name": name, "memberIds": member_ids, "topIndicators": [originals[k] for k in top]})
        assignments.update({m: cid for m in member_ids})

    links: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for (a, b), e in edges.items():
        if e["indicators"]:
            k = sorted(e["indicators"], key=lambda x: STRONG_TYPES.index(x[0]))[0]
            reason, detail, score = "SHARES_INDICATOR", f"wspólny wskaźnik: {TYPE_NAMES[k[0]]} {originals[k]['value']}", min(0.8 + 0.1 * len(e["indicators"]), 1.0)
        else:
            reason, detail, score = "SIMILAR_TEXT", f"podobieństwo tekstu {e['similarity']:.2f}", e["similarity"]
        for x, y in ((a, b), (b, a)):
            links[x].append({"findingId": str(items[y]["id"]), "reason": reason, "detail": detail, "score": round(score, 3)})
    related = {str(items[i]["id"]): sorted(v, key=lambda r: (-r["score"], r["findingId"]))[:5] for i, v in sorted(links.items())}
    return {"campaigns": campaigns, "assignments": assignments, "related": related}
