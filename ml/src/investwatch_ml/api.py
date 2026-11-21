"""ai-service (FastAPI) – kontrakt z docs/backend-integration.md §4.

Na razie predykcje pochodzą z baseline'u słownikowego (heuristics.py); po treningu podmieniamy `predict_text`
na klasyfikator embeddingowy – kontrakt i scoring (scoring.py) się nie zmieniają.

  uv run uvicorn investwatch_ml.api:app --port 8000
"""

from __future__ import annotations

import random
import re
import time
import zlib
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field

from . import heuristics, indicators, scoring
from .labels import FLAG_KEYS
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

# stan w pamięci (stub): ostatnie predykcje dla /rescore, aktualne progi
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


class ItemsRequest(BaseModel):
    items: list[Item]


class RescoreRequest(BaseModel):
    thresholds: dict[str, Any]
    itemIds: list[str] | None = None


class MediaRequest(BaseModel):
    itemId: str
    objectKey: str


class ExplainRequest(BaseModel):
    itemId: str


FIRM_RE = re.compile(r"\b([A-ZŁŚŻŹĆ][\w&.-]+(?:\s[A-ZŁŚŻŹĆ][\w&.-]+){0,3}\s(?:S\.A\.|SA|DM|TFI|Markets|Invest|Capital|Brokers?))\b")


def _full_text(it: Item) -> str:
    t = normalize(it.text)
    return f"{normalize(it.title)}\n\n{t}" if it.title else t


def _entities(text: str) -> list[dict[str, Any]]:
    ents, seen = [], set()
    for m in FIRM_RE.finditer(text):
        name = m.group(1)
        if name.lower() not in seen:
            seen.add(name.lower())
            # TODO: prawdziwy lookup w rejestrze KNF (knf_entities) + listy ostrzeżeń
            ents.append({"name": name, "role": "investment_firm", "knfRegister": {"status": "NOT_FOUND"}})
    return ents[:8]


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
    ents = _entities(text)
    inds = indicators.extract(text, it.outboundLinks)
    _PRED[it.id] = {"pred": pred, "entities": ents}
    sc = scoring.compute(pred, ents, _THRESHOLDS)
    return {
        "itemId": it.id,
        "topic": pred["topic"],
        "contentType": pred["contentType"],
        "instruments": pred["instruments"],
        "flags": pred["flags"],
        "entities": ents,
        "indicators": inds,
        "campaignId": None,  # TODO: graf kampanii
        "related": [],
        "modelVersion": MODEL_VERSION,
        **sc,
    }


@app.get("/health")
def health() -> dict[str, Any]:
    try:
        import torch

        gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    except Exception:
        gpu = None
    return {"status": "ok", "modelVersion": MODEL_VERSION, "gpu": gpu}


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


@app.post("/rescore")
def rescore(req: RescoreRequest) -> dict[str, Any]:
    th = req.thresholds.get("values", req.thresholds)  # przyjmujemy Thresholds albo samą mapę values
    _THRESHOLDS.update({k: float(v) for k, v in th.items()})
    ids = req.itemIds or list(_PRED)
    out = []
    for i in ids:
        if i in _PRED:
            sc = scoring.compute(_PRED[i]["pred"], _PRED[i]["entities"], _THRESHOLDS)
            out.append({"itemId": i, **{k: sc[k] for k in ("rules", "modules", "riskScore", "riskLevel", "scam")}})
    return {"results": out}


@app.get("/thresholds/default")
def thresholds_default() -> dict[str, Any]:
    return {"version": MODEL_VERSION, "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "values": scoring.DEFAULT_THRESHOLDS}


@app.get("/calibration/eval-set")
def eval_set(n: int = 200) -> list[dict[str, Any]]:
    """Zbiór walidacyjny z treningu (models/eval_set.json); bez modelu – syntetyczny stub."""
    if (MODELS_DIR / "eval_set.json").exists():
        return json.loads((MODELS_DIR / "eval_set.json").read_text(encoding="utf-8"))[:n * 10]
    rng = random.Random(7)
    keys = [f"flags.{k}" for k in FLAG_KEYS] + ["topic.INVESTMENT", "scam", "contentType.THIRD_PARTY_PROMO",
                                                 "contentType.FIRM_OWN_MARKETING", "contentType.SERVICE_OFFER"]
    items = []
    for i in range(n):
        probs, gold = {}, {}
        for k in keys:
            base_rate = 0.5 if k in ("topic.INVESTMENT",) else 0.2
            g = 1 if rng.random() < base_rate else 0
            p = min(max(rng.gauss(0.72 if g else 0.25, 0.18), 0.0), 1.0)
            probs[k], gold[k] = round(p, 3), g
        items.append({"id": f"eval-{i:03d}", "probs": probs, "gold": gold})
    return items


@app.post("/enrich/media")
def enrich_media(req: MediaRequest) -> dict[str, Any]:
    """STUB: ASR / OCR / syntetyczny głos – implementacja w kolejnym etapie."""
    seed = zlib.crc32(req.objectKey.encode())
    return {"asr": {"used": False, "text": "", "segments": []}, "keyframes": [],
            "syntheticVoice": {"score": round((seed % 100) / 100, 2), "model": "stub", "segments": [],
                               "experimental": True}}


@app.post("/explain")
def explain(req: ExplainRequest) -> dict[str, Any]:
    st = _PRED.get(req.itemId)
    if not st:
        return {"explanation": "Brak analizy dla tego rekordu."}
    sc = scoring.compute(st["pred"], st["entities"], _THRESHOLDS)
    names = [scoring.RULES[r["ruleId"]][0] for r in sc["rules"] if r["status"] == "VIOLATION"]
    txt = ("Wykryto możliwe naruszenia: " + ", ".join(names) + ".") if names else "Nie wykryto naruszeń."
    return {"explanation": txt + " (stub – docelowo opis generowany przez Bielika)"}
