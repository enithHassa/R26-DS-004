"""TF-IDF + per-label centroid intent classifier (same baseline as scripts/phase2_intent_tfidf.py)."""

from __future__ import annotations

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import normalize


class TfidfIntentCentroidClassifier:
    """Predict intent by argmax cosine similarity to per-label mean TF-IDF vectors."""

    def __init__(
        self,
        *,
        max_features: int = 30_000,
        ngram_range: tuple[int, int] = (1, 2),
    ) -> None:
        self._vectorizer = TfidfVectorizer(
            max_features=max_features,
            ngram_range=ngram_range,
            min_df=1,
            sublinear_tf=True,
        )
        self._labels: list[str] = []
        self._centroids: np.ndarray | None = None

    def fit(self, utterances: list[str], labels: list[str]) -> None:
        if len(utterances) != len(labels):
            raise ValueError("utterances and labels length mismatch")
        if not utterances:
            raise ValueError("no training examples")

        X = self._vectorizer.fit_transform(utterances)
        Xn = normalize(X)

        ordered_labels: list[str] = []
        centroid_rows: list[np.ndarray] = []

        for lab in sorted({str(y) for y in labels}):
            idx = [i for i, y in enumerate(labels) if str(y) == lab]
            if not idx:
                continue
            block = Xn[idx]
            dense = block.toarray() if hasattr(block, "toarray") else np.asarray(block)
            c = np.asarray(dense.mean(axis=0)).ravel()
            ordered_labels.append(lab)
            centroid_rows.append(c)

        self._labels = ordered_labels
        if not self._labels:
            raise ValueError("no labels in training set")

        stacked = np.vstack(centroid_rows)
        self._centroids = normalize(stacked)

    def predict(self, utterances: list[str]) -> list[str]:
        if self._centroids is None:
            raise RuntimeError("fit first")
        X = self._vectorizer.transform(utterances)
        Xn = normalize(X)
        q = Xn.toarray() if hasattr(Xn, "toarray") else np.asarray(Xn)
        sims = cosine_similarity(q, self._centroids)
        best = np.argmax(sims, axis=1)
        return [self._labels[int(i)] for i in best]
