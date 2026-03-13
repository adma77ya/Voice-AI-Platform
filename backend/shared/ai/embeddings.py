"""Embedding helpers with placeholder vectors while embeddings are externalized."""
from typing import List

VECTOR_SIZE = 384


def _placeholder_vector() -> List[float]:
    return [0.0] * VECTOR_SIZE


async def embed_texts(texts: List[str]) -> List[List[float]]:
    if not texts:
        return []
    return [_placeholder_vector() for _ in texts]
