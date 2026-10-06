"""Semantic retrieval over the FitBot knowledge base.

Uses Sentence Transformers (all-MiniLM-L6-v2, 22M params, Apache-2.0) when available
and falls back to TF-IDF cosine similarity (scikit-learn) when the embedding model
cannot be loaded (e.g. offline). Both the dataset builder and the backend use this
class so training-time context matches inference-time context.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)
DEFAULT_EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class KnowledgeRetriever:
    def __init__(self, kb_path: str | Path, model_name: str | None = None, use_embeddings: bool = True):
        data = json.loads(Path(kb_path).read_text())
        self.passages: list[dict] = data["passages"]
        self.texts = [f"{p['title']}. {p['text']}" for p in self.passages]
        self.backend = "tfidf"
        self._model = None
        model_name = model_name or os.getenv("FITBOT_EMBED_MODEL", DEFAULT_EMBED_MODEL)
        if use_embeddings:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(model_name, device="cpu")
                self._emb = self._model.encode(self.texts, normalize_embeddings=True, show_progress_bar=False)
                self.backend = "sentence-transformers"
            except Exception as exc:  # pragma: no cover - depends on environment
                log.warning("Embedding model unavailable (%s); using TF-IDF retrieval", exc)
        if self._model is None:
            from sklearn.feature_extraction.text import TfidfVectorizer
            self._vec = TfidfVectorizer(ngram_range=(1, 2), stop_words="english", sublinear_tf=True)
            self._tfidf = self._vec.fit_transform(self.texts)

    def encode(self, texts: list[str]) -> np.ndarray:
        """Normalised sentence embeddings (shared with the intent classifier)."""
        return self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)

    def scores(self, query: str) -> np.ndarray:
        if self._model is not None:
            q = self._model.encode([query], normalize_embeddings=True, show_progress_bar=False)[0]
            return self._emb @ q
        q = self._vec.transform([query])
        return (self._tfidf @ q.T).toarray().ravel()

    def search(self, query: str, k: int = 2, topic: str | None = None, min_score: float | None = None) -> list[dict]:
        """Top-k passages. A small bonus is given to passages whose topic matches the intent."""
        s = self.scores(query).astype(float)
        if topic:
            s = s + np.array([0.05 if p["topic"] == topic else 0.0 for p in self.passages])
        threshold = min_score if min_score is not None else (0.30 if self.backend != "tfidf" else 0.08)
        order = np.argsort(-s)[:k]
        return [{**self.passages[i], "score": round(float(s[i]), 3)} for i in order if s[i] >= threshold]
