"""ai-service (FastAPI) – kontrakt z docs/backend-integration.md §4.

Predykcje pochodzą z klasyfikatora embeddingowego, gdy model przejdzie bramkę jakości, a inaczej z baseline'u
słownikowego (heuristics.py). Serwis działa lokalnie i nie woła zewnętrznych API.

  uv run uvicorn investwatch_ml.api:app --port 8000
"""

from __future__ import annotations

import re
import time
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field

from . import campaigns, heuristics, indicators, ingest, knf, scoring
from .text import normalize

import json
import os
from pathlib import Path

MODELS_DIR = Path(os.environ.get("INVESTWATCH_MODELS", Path(__file__).resolve().parents[2] / "models"))
_CLF = None
def _model_ready() -> bool:
    """Bramka jakości: model dopiero po treningu na >= 500 dok. z przykładami scamu (albo INVESTWATCH_USE_MODEL=1)."""
    if os.environ.get("INVESTWATCH_USE_MODEL") == "1":
        return True
    try:
        m = json.loads((MODELS_DIR / "metrics.json").read_text(encoding="utf-8"))
        return m["n_train"] >= 500 and m["heads"]["scam"].get("support", 0) > 0
    except Exception:
        return False


if (MODELS_DIR / "heads.joblib").exists() and os.environ.get("INVESTWATCH_BASELINE") != "1" and _model_ready():
    from .classifier import Classifier

    _CLF = Classifier(MODELS_DIR / "heads.joblib")
MODEL_VERSION = _CLF.version if _CLF else "baseline-heuristics-0.1"
app = FastAPI(title="InvestWatch ai-service", version="0.1")

# stan w pamięci: ostatnie predykcje dla /rescore i /explain, aktualne progi
_PRED: dict[str, dict[str, Any]] = {}
_THRESHOLDS: dict[str, float] = dict(scoring.DEFAULT_THRESHOLDS)


class Item(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    platform: str = "other"
    kind: str = "post"
    url: str | None = None
    title: str | None = None
    text: str = ""
    outboundLinks: list[str] = Field(default_factory=list)
    landingPages: list[dict[str, Any]] | None = None
    mediaAnalysis: dict[str, Any] | None = None
    publisher: str | None = None  # autor lub sponsor materiału, sprawdzany w rejestrze KNF
    isSponsored: bool = False
    isPolish: bool = True  # reklama spoza polskiego rynku nie trafia do modułów


class ItemsRequest(BaseModel):
    items: list[Item]


class RecordsRequest(BaseModel):
    records: list[dict[str, Any]]


class ScoringInput(BaseModel):
    pred: dict[str, Any]
    entities: list[dict[str, Any]] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)


class RescoreItem(BaseModel):
    itemId: str
    scoringInput: ScoringInput


class RescoreRequest(BaseModel):
    thresholds: dict[str, Any]
    itemIds: list[str] | None = None
    persist: bool = True  # false: podgląd w panelu kalibracji, bez zmiany aktywnych progów
    items: list[RescoreItem] | None = None  # zapisane wejście scoringu: działa także po restarcie serwisu


class CampaignItem(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    text: str = ""
    author: str | None = None
    platform: str | None = None
    indicators: list[dict[str, Any]] = Field(default_factory=list)
    scamP: float = 0.0
    fetchedAt: str | None = None


class CampaignsRequest(BaseModel):
    items: list[CampaignItem]


class MediaRequest(BaseModel):
    itemId: str
    objectKey: str


class ExplainRequest(BaseModel):
    itemId: str
    scoringInput: ScoringInput | None = None


def _full_text(it: Item) -> str:
    t = normalize(it.text)
    return f"{normalize(it.title)}\n\n{t}" if it.title else t


def _publisher(it: Item) -> str | None:
    if it.publisher:
        return it.publisher
    extra = it.model_extra or {}
    author = extra.get("author")
    if isinstance(author, dict):
        author = author.get("displayName") or author.get("handle")
    return extra.get("sponsor") or (author if isinstance(author, str) else None)


def predict_text(text: str) -> dict[str, Any]:
    if _CLF is None:
        return heuristics.predict(text)
    pred = _CLF.predict(text)
    # cechy słownikowe wzmacniają rzadkie flagi scamowe, dopóki model ma mało przykładów
    base = heuristics.predict(text)
    for k in heuristics.SCAM_FLAGS:
        if base["flags"][k]["evidence"] and base["flags"][k]["p"] > pred["flags"][k]["p"]:
            pred["flags"][k] = base["flags"][k]
    return pred


def _analyze(it: Item) -> dict[str, Any]:
    text = _full_text(it)
    pred = predict_text(text)
    ents = knf.resolve_entities(text, _publisher(it))
    inds = indicators.extract(text, it.outboundLinks)
    context = {"is_paid_ad": it.isSponsored, "is_polish": it.isPolish, "tax_disclaimer": scoring.has_tax_disclaimer(text)}
    _PRED[it.id] = {"pred": pred, "entities": ents, "context": context}
    sc = scoring.compute(pred, ents, _THRESHOLDS, **context)
    return {
        "itemId": it.id,
        "analyzedText": text,  # evidence ma offsety w tym tekście; backend zapisuje go jako Finding.text
        "topic": pred["topic"],
        "contentType": {k: v for k, v in pred["contentType"].items() if k != "NONE"},  # NONE jest wewnętrzne
        "instruments": pred["instruments"],
        "flags": pred["flags"],
        "entities": ents,
        "indicators": inds,
        "campaignId": None,  # uzupełnia POST /campaigns/build na całym zbiorze
        "related": [],
        "modelVersion": MODEL_VERSION,
        "scoringInput": {"pred": pred, "entities": ents, "context": context},
        **sc,
    }


@app.get("/health")
def health() -> dict[str, Any]:
    try:
        import torch

        gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    except Exception:
        gpu = None
    reg = knf.register()
    return {"status": "ok", "modelVersion": MODEL_VERSION, "gpu": gpu,
            "knfRegister": {"entities": len(reg.entities), "generatedAt": reg.generated_at}}


@app.post("/triage")
def triage(req: ItemsRequest) -> dict[str, Any]:
    res = []
    for it in req.items:
        p = predict_text(_full_text(it))
        p_inv = p["topic"]["INVESTMENT"]
        res.append({"itemId": it.id, "pInvestment": p_inv, "pScam": p["scamText"],
                    "enrich": p_inv >= 0.3 and bool(it.outboundLinks or it.kind == "transcript")})
    return {"results": res}


@app.post("/analyze")
def analyze(req: ItemsRequest) -> dict[str, Any]:
    return {"results": [_analyze(it) for it in req.items]}


@app.post("/ingest")
def ingest_records(req: RecordsRequest) -> dict[str, Any]:
    """Rekordy prosto z kolektora: adapter, rejestr KNF i analiza. Zwraca znormalizowany item razem z wynikiem."""
    items, stats = ingest.to_items(req.records)
    return {"stats": dict(stats), "results": [{"item": item, "analysis": _analyze(Item(**item))} for item in items]}


@app.post("/rescore")
def rescore(req: RescoreRequest) -> dict[str, Any]:
    th = req.thresholds.get("values", req.thresholds)  # przyjmujemy Thresholds albo samą mapę values
    values = {**_THRESHOLDS, **{k: float(v) for k, v in scoring.normalize_thresholds(th).items()}}
    if req.persist:
        _THRESHOLDS.update(values)
    if req.items is not None:
        for it in req.items:
            _PRED[it.itemId] = it.scoringInput.model_dump()
    ids = [it.itemId for it in req.items] if req.items is not None else (req.itemIds or list(_PRED))
    out = []
    for i in ids:
        if i in _PRED:
            sc = scoring.compute(_PRED[i]["pred"], _PRED[i]["entities"], values, **_PRED[i].get("context", {}))
            out.append({"itemId": i, **{k: sc[k] for k in ("rules", "modules", "riskScore", "riskLevel", "scam")}})
    return {"results": out}


@app.get("/thresholds/default")
def thresholds_default() -> dict[str, Any]:
    return {"version": MODEL_VERSION, "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "values": scoring.DEFAULT_THRESHOLDS}


@app.get("/calibration/eval-set")
def eval_set(n: int = 200) -> list[dict[str, Any]]:
    """Zbiór walidacyjny z treningu (models/eval_set.json). Bez modelu lista jest pusta."""
    if not (MODELS_DIR / "eval_set.json").exists():
        return []
    rows = json.loads((MODELS_DIR / "eval_set.json").read_text(encoding="utf-8"))[:n * 10]
    for row in rows:  # trening zapisuje klucz `scam`, kontrakt używa `scam.p`
        for part in ("probs", "gold"):
            if "scam" in row[part]:
                row[part]["scam.p"] = row[part].pop("scam")
    return rows


@app.post("/campaigns/build")
def campaigns_build(req: CampaignsRequest) -> dict[str, Any]:
    """Grupuje cały zbiór w kampanie. Z modelem używa embeddingów, bez modelu TF-IDF."""
    embed = _CLF.embedder.encode if _CLF is not None else None
    return campaigns.build([x.model_dump() for x in req.items], embed)


@app.post("/enrich/media")
def enrich_media(req: MediaRequest) -> dict[str, Any]:
    """Analiza mediów nie jest jeszcze aktywna, więc serwis nie zwraca żadnego wyniku głosu."""
    return {"active": False, "reason": "Analiza mediów nie jest aktywna.",
            "asr": {"used": False, "text": "", "segments": []}, "keyframes": [], "syntheticVoice": None}


def _quote(evidence: list[dict[str, Any]]) -> str:
    text = " ".join(re.sub(r"https?://\S+", "", str(evidence[0].get("text") or "")).split()) if evidence else ""
    return f" (np. „{text[:140]}”)" if text else ""


@app.post("/explain")
def explain(req: ExplainRequest) -> dict[str, Any]:
    st = req.scoringInput.model_dump() if req.scoringInput else _PRED.get(req.itemId)
    if not st:
        return {"explanation": "Brak analizy dla tego rekordu."}
    sc = scoring.compute(st["pred"], st["entities"], _THRESHOLDS, **st.get("context", {}))
    parts = []
    if sc["scam"]["signals"]:
        parts.append(f"Treść przypomina oszustwo inwestycyjne (prawdopodobieństwo {sc['scam']['p']:.0%}).")
    violations = [r for r in sc["rules"] if r["status"] == "VIOLATION"]
    if violations:
        parts.append("Możliwe naruszenia: "
                     + "; ".join(scoring.RULES[r["ruleId"]][0] + _quote(r["evidence"]) for r in violations[:5]) + ".")
    review = [r for r in sc["rules"] if r["ruleId"] == "M3_RECOMMENDATION" and r["status"] == "NOT_CHECKED"]
    if review:
        parts.append("Treść zawiera rekomendację instrumentu dla ogółu odbiorców" + _quote(review[0]["evidence"])
                     + " i wymaga weryfikacji.")
    missing = [e["name"] for e in st["entities"] if e.get("knfRegister", {}).get("status") == "NOT_FOUND"]
    if missing and (violations or review or sc["scam"]["signals"]):
        parts.append("Nie znaleziono w rejestrze KNF: " + ", ".join(missing[:3])
                     + ". To sygnał do sprawdzenia, nie stwierdzenie naruszenia.")
    if not parts:
        parts.append("Przy obecnych progach nie wykryto sygnałów wymagających reakcji.")
    parts.append(f"Poziom ryzyka: {sc['riskLevel']}. Wynik wymaga weryfikacji przez analityka.")
    return {"explanation": " ".join(parts)}
