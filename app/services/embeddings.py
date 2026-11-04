"""Embedding adapter: optional Ollama semantic vectors with a stable local fallback."""

from __future__ import annotations

import hashlib
<<<<<<< HEAD
=======
import logging
>>>>>>> 92c77001379e6b91b43212cb314e441bf427457a
import math
import os
import re
from collections import Counter

import requests

VECTOR_DIM = 256
EMBEDDING_VERSION = 3
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_EMBEDDING_MODEL = os.getenv("OLLAMA_EMBEDDING_MODEL", "").strip()
_TOKEN_RE = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?", re.IGNORECASE)
logger = logging.getLogger(__name__)
_OLLAMA_UNAVAILABLE = False


def _stable_token_hash(token: str) -> int:
    """Deterministic token hash across processes, ignoring PYTHONHASHSEED."""
    return int.from_bytes(
        hashlib.md5(token.encode("utf-8")).digest()[:8],
        "little",
        signed=True,
    )


def tokenize(text: str) -> list[str]:
    if not text:
        return []
    return [token.lower() for token in _TOKEN_RE.findall(text)]


def embedding_model_id() -> str:
    """Identify the active vector backend for safe persisted-vector reuse."""
    if OLLAMA_EMBEDDING_MODEL and not _OLLAMA_UNAVAILABLE:
        return f"ollama:{OLLAMA_EMBEDDING_MODEL}"
    return "stable-hash-v3"


def _hashed_embedding(text: str, dim: int = VECTOR_DIM) -> list[float]:
    tokens = tokenize(text)
    if not tokens:
        return [0.0] * dim

    counts = Counter(tokens)
    vector = [0.0] * dim
    for token, count in counts.items():
<<<<<<< HEAD
        # Deterministic hash into bucket; sign bit reduces collisions.
        h = _stable_token_hash(token)
        idx = abs(h) % dim
        sign = 1.0 if (h & 1) == 0 else -1.0
        # Simple TF weighting
        vec[idx] += sign * (1.0 + math.log(count))
=======
        # Stable hashing is essential: Python's built-in hash changes by process.
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        hashed = int.from_bytes(digest, byteorder="big", signed=False)
        index = hashed % dim
        sign = 1.0 if (hashed & 1) == 0 else -1.0
        vector[index] += sign * (1.0 + math.log(count))
>>>>>>> 92c77001379e6b91b43212cb314e441bf427457a

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def _ollama_embedding(text: str) -> list[float]:
    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/embed",
        json={"model": OLLAMA_EMBEDDING_MODEL, "input": text},
        timeout=(1.0, 5.0),
    )
    response.raise_for_status()
    payload = response.json()
    embeddings = payload.get("embeddings") or []
    if not embeddings or not embeddings[0]:
        raise ValueError("Ollama returned no embedding vector")

    vector = [float(value) for value in embeddings[0]]
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        raise ValueError("Ollama returned a zero-length embedding")
    return [value / norm for value in vector]


def embed_text(text: str, dim: int = VECTOR_DIM) -> list[float]:
    """Embed text semantically when configured; otherwise use stable feature hashing.

    Configure OLLAMA_EMBEDDING_MODEL (for example, nomic-embed-text) to use
    Ollama's /api/embed endpoint. If the model/server is unavailable, the
    process falls back to stable hashing rather than failing ingestion.
    """
    global _OLLAMA_UNAVAILABLE

    if not text or not text.strip():
        return _hashed_embedding(text, dim)

    if OLLAMA_EMBEDDING_MODEL and not _OLLAMA_UNAVAILABLE:
        try:
            return _ollama_embedding(text)
        except Exception as exc:
            _OLLAMA_UNAVAILABLE = True
            logger.warning(
                "Ollama embedding backend unavailable; using stable hash fallback: %s",
                exc,
            )

    return _hashed_embedding(text, dim)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(left * right for left, right in zip(a, b))
