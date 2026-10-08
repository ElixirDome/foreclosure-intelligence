"""
Lightweight embeddings for Phase 4 without an external model dependency.

Uses a hashed bag-of-words vector (feature hashing). Good enough for
hybrid retrieval prototypes; swap `embed_text` for a real model later
without changing callers.
"""

from __future__ import annotations

import math
import re
from collections import Counter

VECTOR_DIM = 256
_TOKEN_RE = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?", re.IGNORECASE)


def tokenize(text: str) -> list[str]:
    if not text:
        return []
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def embed_text(text: str, dim: int = VECTOR_DIM) -> list[float]:
    """Return an L2-normalized hashed bag-of-words vector."""
    tokens = tokenize(text)
    if not tokens:
        return [0.0] * dim

    counts = Counter(tokens)
    vec = [0.0] * dim
    for token, count in counts.items():
        # Stable hash into bucket; sign bit reduces collisions.
        h = hash(token)
        idx = h % dim
        sign = 1.0 if (h & 1) == 0 else -1.0
        # Simple TF weighting
        vec[idx] += sign * (1.0 + math.log(count))

    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        return vec
    return [v / norm for v in vec]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))
