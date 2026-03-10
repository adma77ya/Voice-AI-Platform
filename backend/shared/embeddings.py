"""Embedding client utilities backed by embedding-service over HTTP."""
import logging
import os
from typing import List

import httpx

EMBEDDING_DIMENSION = 384
VECTOR_SIZE = EMBEDDING_DIMENSION
EMBEDDING_ENDPOINT = os.getenv("EMBEDDING_SERVICE_URL", "http://embedding-service:8004/embed")
REQUEST_TIMEOUT_SECONDS = 15.0

logger = logging.getLogger("embeddings.client")
rag_logger = logging.getLogger("rag")


def _placeholder_vector() -> List[float]:
    return [0.0] * VECTOR_SIZE


def embed_text(text: str) -> List[float]:
    """Get one embedding from embedding-service using Docker service DNS."""
    rag_logger.info("Embedding query: %s", str(text or "")[:200])
    rag_logger.info("Embedding endpoint: %s", EMBEDDING_ENDPOINT)
    embeddings = embed_batch([text])
    if not embeddings:
        vector = _placeholder_vector()
        logger.info("Embedding vector dimension: %d", len(vector))
        return vector

    vector = embeddings[0]
    logger.info("Embedding vector dimension: %d", len(vector))
    return vector


def embed_batch(texts: List[str]) -> List[List[float]]:
    """Get embeddings from embedding-service, fallback to placeholders on errors."""
    if not texts:
        return []

    rag_logger.info("Embedding batch size: %d", len(texts))
    rag_logger.info("Embedding endpoint: %s", EMBEDDING_ENDPOINT)

    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            response = client.post(EMBEDDING_ENDPOINT, json={"text": texts})
            response.raise_for_status()
            payload = response.json()

        embeddings = payload.get("embeddings")
        if not isinstance(embeddings, list):
            raise ValueError("Invalid embedding-service response: 'embeddings' must be a list")

        if len(embeddings) != len(texts):
            raise ValueError("Embedding count mismatch from embedding-service")

        if embeddings and isinstance(embeddings[0], list):
            rag_logger.info("Embedding vector dimension: %d", len(embeddings[0]))

        return embeddings
    except Exception as exc:
        logger.warning("embedding-service request failed, using placeholders: %s", str(exc))
        return [_placeholder_vector() for _ in texts]
