"""Klasyfikator docelowy: zamrożony model embeddingowy + lekkie głowy (LogisticRegression).

- głowy dokumentowe: topic (softmax), content_type (softmax), instruments (multi-label), scam (binarna)
  na średniej z embeddingów okien dokumentu,
- głowy flag na poziomie okien (~50 słów, krok 25 – działa też na transkrypcjach bez interpunkcji):
  flaga dokumentu = max po oknach, najlepsze okna = evidence.

Wyjście ma ten sam format co heuristics.predict(), więc API i scoring się nie zmieniają.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from .labels import CONTENT_TYPES, FLAG_KEYS, INSTRUMENTS, TOPICS
from .text import word_windows

DEFAULT_EMBEDDER = "BAAI/bge-m3"
WINDOW_WORDS, WINDOW_STRIDE = 50, 25
MAX_WINDOWS = 120  # ~3000 słów na dokument


class Embedder:
    def __init__(self, name: str = DEFAULT_EMBEDDER, device: str | None = None, batch_size: int = 64,
                 max_seq_length: int = 256):
        from sentence_transformers import SentenceTransformer

        self.name = name
        self.model = SentenceTransformer(name, device=device)
        if self.model.device.type == "cuda":
            self.model.half()
        self.model.max_seq_length = max_seq_length
        self.batch_size = batch_size

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.model.get_sentence_embedding_dimension()), dtype=np.float32)
        return np.asarray(self.model.encode(texts, batch_size=self.batch_size, normalize_embeddings=True,
                                            convert_to_numpy=True, show_progress_bar=False), dtype=np.float32)


def doc_windows(text: str) -> list[tuple[int, int]]:
    spans = word_windows(text, WINDOW_WORDS, WINDOW_STRIDE)
    return spans[:MAX_WINDOWS] if spans else [(0, len(text))]


@dataclass
class Heads:
    embedder_name: str
    topic: Any = None
    content_type: Any = None
    instruments: dict[str, Any] = field(default_factory=dict)
    scam: Any = None
    flags: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)

    @staticmethod
    def load(path: str | Path) -> Heads:
        return joblib.load(path)


def _proba_binary(model: Any, X: np.ndarray) -> np.ndarray:
    if model is None:
        return np.zeros(len(X))
    if isinstance(model, float):  # stała (klasa bez przykładów pozytywnych w treningu)
        return np.full(len(X), model)
    return model.predict_proba(X)[:, 1]


def _proba_multiclass(model: Any, X: np.ndarray, labels: list[str]) -> np.ndarray:
    out = np.zeros((len(X), len(labels)))
    if model is None:
        return out
    p = model.predict_proba(X)
    for j, cls in enumerate(model.classes_):
        out[:, labels.index(cls)] = p[:, j]
    return out


class Classifier:
    def __init__(self, heads_path: str | Path, embedder: Embedder | None = None):
        self.heads = Heads.load(heads_path)
        self.embedder = embedder or Embedder(self.heads.embedder_name)
        self.version = self.heads.meta.get("version", "heads")

    def predict(self, text: str) -> dict[str, Any]:
        return self.predict_many([text])[0]

    def predict_many(self, texts: list[str]) -> list[dict[str, Any]]:
        all_spans = [doc_windows(t) for t in texts]
        flat = [t[s:e] for t, spans in zip(texts, all_spans) for s, e in spans]
        E = self.embedder.encode(flat)
        out, k = [], 0
        h = self.heads
        topics, ctypes = list(TOPICS), list(CONTENT_TYPES)
        for text, spans in zip(texts, all_spans):
            W = E[k: k + len(spans)]
            k += len(spans)
            D = W.mean(axis=0, keepdims=True)
            D /= np.linalg.norm(D) + 1e-9
            topic = dict(zip(topics, _proba_multiclass(h.topic, D, topics)[0].round(3).tolist()))
            ctype = dict(zip(ctypes, _proba_multiclass(h.content_type, D, ctypes)[0].round(3).tolist()))
            instr = {i: round(float(_proba_binary(h.instruments.get(i), D)[0]), 3) for i in INSTRUMENTS}
            flags = {}
            for f in FLAG_KEYS:
                pw = _proba_binary(h.flags.get(f), W)
                best = np.argsort(-pw)[:2]
                p = float(pw.max()) if len(pw) else 0.0
                ev = [{"section": "text", "start": spans[i][0], "end": spans[i][1],
                       "text": text[spans[i][0]: spans[i][1]], "p": round(float(pw[i]), 3)}
                      for i in best if pw[i] >= 0.5]
                flags[f] = {"p": round(p, 3), "evidence": ev}
            scam = round(float(_proba_binary(h.scam, D)[0]), 3)
            out.append({"topic": topic, "contentType": ctype, "instruments": instr, "flags": flags, "scamText": scam})
        return out


def timed(fn):
    def wrap(*a, **kw):
        t = time.time()
        r = fn(*a, **kw)
        print(f"[{fn.__name__}] {time.time() - t:.1f}s", flush=True)
        return r
    return wrap
