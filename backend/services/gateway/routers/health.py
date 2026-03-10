"""Health check endpoints."""
import os
from typing import Any, Dict, List
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from qdrant_client import QdrantClient

from shared.embeddings import embed_text
from shared.retrieval import COLLECTION_NAME
from shared.settings import config

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "service": "vobiz-voice-platform",
        "version": "1.0.0",
    }


@router.get("/ready")
async def ready_check():
    """
    Readiness check - verifies all dependencies are available.
    Returns 200 if all dependencies are healthy, 503 if any are down.
    """
    checks = {}
    
    # Check MongoDB
    try:
        from shared.database.connection import get_database
        db = get_database()
        await db.command("ping")
        checks["mongodb"] = "ok"
    except Exception as e:
        checks["mongodb"] = f"failed: {str(e)}"
    
    # Check Redis (if configured)
    redis_host = os.getenv("REDIS_HOST")
    if redis_host:
        try:
            import redis
            r = redis.Redis(host=redis_host, port=int(os.getenv("REDIS_PORT", 6379)))
            r.ping()
            checks["redis"] = "ok"
        except Exception as e:
            checks["redis"] = f"failed: {str(e)}"
    
    # Determine overall status
    all_ok = all(v == "ok" for v in checks.values())
    status = "ready" if all_ok else "degraded"
    
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={
            "status": status,
            "service": "vobiz-voice-platform",
            "checks": checks,
        }
    )


@router.get("/debug/rag-test")
async def rag_test(q: str, top_k: int = 5):
    """Debug RAG retrieval without running a live call."""
    query = (q or "").strip()
    if not query:
        return {"query": q, "results": [], "count": 0}

    query_vector = embed_text(query)
    client = QdrantClient(url=config.QDRANT_URL)
    response = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=top_k,
        with_payload=True,
    )
    results = list(getattr(response, "points", []) or [])

    chunks: List[Dict[str, Any]] = []
    for hit in results:
        payload = hit.payload or {}
        chunks.append(
            {
                "score": float(hit.score or 0.0),
                "document_id": payload.get("document_id"),
                "assistant_id": payload.get("assistant_id"),
                "user_id": payload.get("user_id"),
                "chunk_id": payload.get("chunk_id"),
                "text": str(payload.get("text", "")),
            }
        )

    return {
        "query": query,
        "collection": COLLECTION_NAME,
        "count": len(chunks),
        "results": chunks,
    }
