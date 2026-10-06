"""Hybrid intent classifier: TF-IDF features + sentence embeddings -> logistic regression.

The sentence encoder (all-MiniLM-L6-v2) is not pickled; the backend attaches the retriever's already-loaded
encoder with `set_encoder`. Without an encoder (offline / embeddings disabled) the bundled TF-IDF-only model is
used, so classification always works.
"""
from __future__ import annotations

import numpy as np
from scipy.sparse import csr_matrix, hstack


class HybridIntentClassifier:
    def __init__(self, tfidf_features, hybrid_clf, fallback, embed_model: str, embed_weight: float = 1.0):
        self.tfidf_features = tfidf_features   # fitted FeatureUnion (word + char TF-IDF)
        self.hybrid_clf = hybrid_clf           # LogisticRegression over [TF-IDF | embedding]
        self.fallback = fallback               # TF-IDF-only Pipeline
        self.embed_model = embed_model
        self.embed_weight = embed_weight
        self._encode = None

    def __getstate__(self):
        state = self.__dict__.copy()
        state["_encode"] = None
        return state

    def set_encoder(self, encode) -> None:
        """encode(list[str]) -> np.ndarray of L2-normalised embeddings."""
        self._encode = encode

    @property
    def uses_embeddings(self) -> bool:
        return self._encode is not None

    @property
    def classes_(self):
        return self.hybrid_clf.classes_ if self.uses_embeddings else self.fallback.classes_

    def _features(self, texts: list[str]):
        emb = np.asarray(self._encode(list(texts)), dtype=np.float64) * self.embed_weight
        return hstack([self.tfidf_features.transform(texts), csr_matrix(emb)]).tocsr()

    def predict_proba(self, texts: list[str]) -> np.ndarray:
        if not self.uses_embeddings:
            return self.fallback.predict_proba(texts)
        return self.hybrid_clf.predict_proba(self._features(texts))

    def predict(self, texts: list[str]) -> np.ndarray:
        return self.classes_[np.argmax(self.predict_proba(texts), axis=1)]
