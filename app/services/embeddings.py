"""Embedding adapter: optional Ollama & Gemini semantic vectors with a stable local fallback."""

from __future__ import annotations

import hashlib
import logging
import math
import os
import re
from collections import Counter

import requests

VECTOR_DIM = 256
EMBEDDING_VERSION = 3
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_EMBEDDING_MODEL = os.getenv("OLLAMA_EMBEDDING_MODEL", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001").strip()

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?", re.IGNORECASE)
logger = logging.getLogger(__name__)
_OLLAMA_UNAVAILABLE = False
_GEMINI_UNAVAILABLE = False


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
    if GEMINI_API_KEY and not _GEMINI_UNAVAILABLE:
        return f"gemini:{GEMINI_EMBEDDING_MODEL}"
    return "stable-hash-v3"


def _hashed_embedding(text: str, dim: int = VECTOR_DIM) -> list[float]:
    tokens = tokenize(text)
    if not tokens:
        return [0.0] * dim

    counts = Counter(tokens)
    vector = [0.0] * dim
    for token, count in counts.items():
        # Stable hashing is essential: Python's built-in hash changes by process.
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        hashed = int.from_bytes(digest, byteorder="big", signed=False)
        index = hashed % dim
        sign = 1.0 if (hashed & 1) == 0 else -1.0
        vector[index] += sign * (1.0 + math.log(count))

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def _format_nomic_input(text: str, task: str = "document") -> str:
    """Format input text with task-specific prefix for nomic-embed-text models."""
    clean = text.strip()
    if clean.startswith("search_query:") or clean.startswith("search_document:"):
        return clean
    if task in ("query", "search_query"):
        return f"search_query: {clean}"
    return f"search_document: {clean}"


def _ollama_embedding(text: str, task: str = "document") -> list[float]:
    input_text = text
    if "nomic" in OLLAMA_EMBEDDING_MODEL.lower():
        input_text = _format_nomic_input(text, task=task)

    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/embed",
        json={"model": OLLAMA_EMBEDDING_MODEL, "input": input_text},
        timeout=(3.0, 15.0),
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


def _gemini_embedding(text: str, dim: int = VECTOR_DIM) -> list[float]:
    """Obtain embeddings from Gemini API with matching dimensionality."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_EMBEDDING_MODEL}:embedContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY,
    }
    payload = {
        "model": f"models/{GEMINI_EMBEDDING_MODEL}",
        "content": {"parts": [{"text": text.strip()}]},
        "outputDimensionality": dim,
    }
    response = requests.post(url, headers=headers, json=payload, timeout=(3.0, 10.0))
    response.raise_for_status()
    payload_json = response.json()
    values = (payload_json.get("embedding") or {}).get("values")
    if not values:
        raise ValueError("Gemini returned no embedding vector")

    vector = [float(value) for value in values]
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        raise ValueError("Gemini returned a zero-length embedding")
    return [value / norm for value in vector]


def embed_text(text: str, dim: int = VECTOR_DIM, task: str = "document") -> list[float]:
    """Embed text semantically when configured; otherwise use stable feature hashing.

    Supports Ollama (/api/embed), Gemini (/models/{model}:embedContent), and stable
    feature hashing. If a provider fails or is unreachable, the system falls back
    gracefully to the next tier rather than failing ingestion or retrieval.
    """
    global _OLLAMA_UNAVAILABLE, _GEMINI_UNAVAILABLE

    if not text or not text.strip():
        return _hashed_embedding(text, dim)

    # 1. Try Ollama if configured and available
    if OLLAMA_EMBEDDING_MODEL and not _OLLAMA_UNAVAILABLE:
        try:
            return _ollama_embedding(text, task=task)
        except Exception as exc:
            _OLLAMA_UNAVAILABLE = True
            logger.warning(
                "Ollama embedding backend unavailable (%s); attempting fallback",
                exc,
            )

    # 2. Try Gemini if configured and available
    if GEMINI_API_KEY and not _GEMINI_UNAVAILABLE:
        try:
            return _gemini_embedding(text, dim=dim)
        except Exception as exc:
            _GEMINI_UNAVAILABLE = True
            logger.warning(
                "Gemini embedding backend unavailable (%s); using stable hash fallback",
                exc,
            )

    # 3. Deterministic local feature-hash fallback
    return _hashed_embedding(text, dim)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(left * right for left, right in zip(a, b))
