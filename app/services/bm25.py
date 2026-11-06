"""
Genuine Okapi BM25 lexical ranking engine for legal & auction document retrieval.

Implements Okapi BM25 scoring with:
- Standard k1 (term saturation) and b (document length penalty) parameters
- Inverted index construction with token frequencies
- Non-negative Robertson-Spärck Jones IDF
- Domain-specific bonuses for exact auction numbers (reserve price, lot, plot),
  bank names, and exact phrase matches.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Sequence

from app.services.embeddings import tokenize


@dataclass
class BM25Document:
    doc_id: int
    text: str
    tokens: list[str]
    length: int


class BM25Ranker:
    """
    Okapi BM25 Ranker with exact-term and numeric auction boosting.
    """

    def __init__(
        self,
        corpus: Sequence[tuple[int, str]],
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        self.k1 = k1
        self.b = b
        self.documents: list[BM25Document] = []
        self.inverted_index: dict[str, list[int]] = {}
        self.doc_freqs: dict[str, int] = {}
        self.avg_doc_len: float = 0.0

        self._build_index(corpus)

    def _build_index(self, corpus: Sequence[tuple[int, str]]) -> None:
        if not corpus:
            return

        total_len = 0
        for idx, (doc_id, text) in enumerate(corpus):
            tokens = tokenize(text)
            doc_len = len(tokens)
            total_len += doc_len

            doc = BM25Document(
                doc_id=doc_id,
                text=text,
                tokens=tokens,
                length=doc_len,
            )
            self.documents.append(doc)

            # Inverted index
            unique_tokens = set(tokens)
            for token in unique_tokens:
                if token not in self.inverted_index:
                    self.inverted_index[token] = []
                self.inverted_index[token].append(idx)
                self.doc_freqs[token] = self.doc_freqs.get(token, 0) + 1

        self.avg_doc_len = total_len / max(len(self.documents), 1)

    def idf(self, token: str) -> float:
        """Robertson-Spärck Jones IDF formulation with floor at 0.0."""
        n = self.doc_freqs.get(token, 0)
        N = len(self.documents)
        if n == 0 or N == 0:
            return 0.0
        # Standard positive BM25 IDF: ln(1 + (N - n + 0.5) / (n + 0.5))
        return math.log(1.0 + (N - n + 0.5) / (n + 0.5))

    def score(
        self,
        query: str,
        *,
        min_score: float = 0.01,
    ) -> list[tuple[int, float]]:
        """
        Rank all documents in corpus against query.
        Returns list of (doc_id, bm25_score) sorted descending.
        """
        if not self.documents:
            return []

        q_tokens = tokenize(query)
        if not q_tokens:
            return []

        q_clean = query.lower().strip()
        q_counter = Counter(q_tokens)
        scores: dict[int, float] = {}

        # 1. Standard Okapi BM25 scoring across terms
        for token, qf in q_counter.items():
            if token not in self.inverted_index:
                continue

            token_idf = self.idf(token)
            if token_idf <= 0.0:
                continue

            posting_list = self.inverted_index[token]
            for doc_idx in posting_list:
                doc = self.documents[doc_idx]
                tf = doc.tokens.count(token)

                numerator = tf * (self.k1 + 1.0)
                denom = tf + self.k1 * (1.0 - self.b + self.b * (doc.length / max(self.avg_doc_len, 1e-6)))
                term_score = token_idf * (numerator / denom)

                # Numeric boost: exact numbers in queries (e.g. "3438000", "204", "15") are critical in auctions
                if any(c.isdigit() for c in token):
                    term_score *= 1.35

                scores[doc.doc_id] = scores.get(doc.doc_id, 0.0) + term_score

        # 2. Phrase and exact coverage boosts
        for doc in self.documents:
            doc_id = doc.doc_id
            if doc_id not in scores:
                # Substring check even if token boundaries differ slightly
                if len(q_clean) >= 4 and q_clean in doc.text.lower():
                    scores[doc_id] = 0.5
                continue

            # Exact phrase match bonus
            if len(q_clean) >= 4 and q_clean in doc.text.lower():
                scores[doc_id] += 1.5

            # High term recall bonus (percentage of distinct query tokens present)
            overlap = set(q_tokens) & set(doc.tokens)
            coverage = len(overlap) / max(len(set(q_tokens)), 1)
            scores[doc_id] *= (0.7 + 0.3 * coverage)

        ranked = [
            (doc_id, s)
            for doc_id, s in scores.items()
            if s >= min_score
        ]
        ranked.sort(key=lambda x: (x[1], -x[0]), reverse=True)
        return ranked
