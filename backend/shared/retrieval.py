"""Qdrant-backed retrieval helpers for Knowledge Base RAG."""
import logging
import os
from typing import List

from qdrant_client import QdrantClient
from qdrant_client.http import models

from shared.embeddings import embed_text
from shared.settings import config

logger = logging.getLogger("kb.retrieval")
rag_logger = logging.getLogger("rag")

QDRANT_URL = config.QDRANT_URL
COLLECTION_NAME = "knowledge"
VECTOR_SIZE = 384
SIMILARITY_THRESHOLD = 0.7
MAX_CONTEXT_DOCS = 3
MAX_CONTEXT_CHARS = 2000

_qdrant_client: QdrantClient | None = None
_collection_ready = False


def _get_qdrant_client() -> QdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(url=QDRANT_URL)
    return _qdrant_client


def _ensure_collection() -> None:
    global _collection_ready
    if _collection_ready:
        return

    client = _get_qdrant_client()
    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=VECTOR_SIZE,
                distance=models.Distance.COSINE,
            ),
        )

    _collection_ready = True


def delete_document_vectors(document_id: str) -> None:
    _ensure_collection()
    client = _get_qdrant_client()
    client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=models.FilterSelector(
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(value=document_id),
                    )
                ]
            )
        ),
        wait=True,
    )


def upsert_points(points: List[models.PointStruct]) -> None:
    if not points:
        return

    _ensure_collection()
    client = _get_qdrant_client()
    client.upsert(
        collection_name=COLLECTION_NAME,
        points=points,
        wait=True,
    )


def retrieve_context(
    assistant_id: str,
    workspace_id: str,
    query: str,
    top_k: int = 5,
) -> str:
    rag_logger.info("RAG QUERY RECEIVED: %s", query)
    if not query.strip() or not assistant_id:
        return ""

    _ensure_collection()
    client = _get_qdrant_client()

    rag_logger.info("Embedding query using embedding service")
    query_vector = embed_text(query)
    rag_logger.info("Embedding dimension: %d", len(query_vector))
    rag_logger.info("Searching Qdrant collection 'knowledge'")
    rag_logger.info("Collection searched: %s", COLLECTION_NAME)
    rag_logger.info("Top K: %d", top_k)

    must_filters = [
        models.FieldCondition(
            key="assistant_id",
            match=models.MatchValue(value=assistant_id),
        )
    ]
    if workspace_id:
        must_filters.append(
            models.FieldCondition(
                key="user_id",
                match=models.MatchValue(value=workspace_id),
            )
        )

    search_filter = models.Filter(must=must_filters)

    rag_logger.info(
        "Search filters: assistant_id=%s user_id=%s",
        assistant_id,
        workspace_id or "<none>",
    )

    results_response = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        query_filter=search_filter,
        limit=top_k,
        with_payload=True,
    )
    results = list(getattr(results_response, "points", []) or [])

    rag_logger.info("Qdrant returned %d results", len(results))
    rag_logger.info("Scores: %s", [round(float(hit.score or 0.0), 4) for hit in results])
    for hit in results:
        payload = hit.payload or {}
        rag_logger.info(
            "Retrieved chunk score=%f document_id=%s",
            float(hit.score or 0.0),
            payload.get("document_id"),
        )

    if not results:
        rag_logger.info("No filtered results. Running fallback search without payload filter")
        fallback_response = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=top_k,
            with_payload=True,
        )
        results = list(getattr(fallback_response, "points", []) or [])
        rag_logger.info("Fallback search returned %d results", len(results))
        rag_logger.info("Fallback scores: %s", [round(float(hit.score or 0.0), 4) for hit in results])

    min_score = float(os.getenv("RAG_MIN_SCORE", "0.0"))
    filtered = [hit for hit in results if float(hit.score or 0.0) >= min_score]
    logger.info("RAG retrieved %d docs for query", len(filtered))

    chunks: List[str] = []
    total_chars = 0
    for hit in filtered:
        if len(chunks) >= MAX_CONTEXT_DOCS:
            break

        payload = hit.payload or {}
        text = str(payload.get("text") or "").strip()
        if not text:
            continue

        projected_chars = total_chars + len(text)
        if projected_chars > MAX_CONTEXT_CHARS:
            remaining = MAX_CONTEXT_CHARS - total_chars
            if remaining <= 0:
                break
            text = text[:remaining].rstrip()
            if not text:
                break

        chunks.append(text)
        total_chars += len(text)

    context = "\n\n".join(chunks)
    rag_logger.info("Final RAG context length: %d characters", len(context))

    debug_query = os.getenv("RAG_DEBUG_TEST_QUERY", "").strip()
    if debug_query:
        rag_logger.info("Running hardcoded debug search query: %s", debug_query)
        debug_embedding = embed_text(debug_query)
        debug_response = client.query_points(
            collection_name=COLLECTION_NAME,
            query=debug_embedding,
            limit=3,
            with_payload=True,
        )
        debug_results = list(getattr(debug_response, "points", []) or [])
        rag_logger.info("Hardcoded debug search returned %d results", len(debug_results))

    return context
