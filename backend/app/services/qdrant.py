"""Qdrant vector store service."""

from typing import Any
from uuid import UUID

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter

from app.config import get_settings

_client: QdrantClient | None = None


def get_qdrant_client() -> QdrantClient:
    """Get or create Qdrant client singleton."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            api_key=settings.qdrant_api_key if settings.qdrant_api_key else None,
            https=settings.qdrant_use_tls,
            timeout=30,
            check_compatibility=False,  # Allow newer client with older server
        )
    return _client


async def check_qdrant_health() -> bool:
    """Check if Qdrant is healthy."""
    try:
        client = get_qdrant_client()
        client.get_collections()
        return True
    except Exception:
        return False


async def ensure_collection_exists(collection_name: str, vector_size: int = 1536) -> None:
    """Ensure a collection exists, creating it if necessary.

    Args:
        collection_name: Name of the collection
        vector_size: Dimension of vectors (default 1536 for text-embedding-3-small)
    """
    client = get_qdrant_client()

    collections = client.get_collections().collections
    collection_names = [c.name for c in collections]

    if collection_name not in collection_names:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE,
            ),
        )


async def upsert_vectors(
    collection_name: str,
    points: list[dict[str, Any]],
) -> None:
    """Upsert vectors into collection.

    Args:
        collection_name: Name of the collection
        points: List of dicts with 'id', 'vector', and 'payload' keys
    """
    client = get_qdrant_client()

    qdrant_points = [
        PointStruct(
            id=str(point["id"]),
            vector=point["vector"],
            payload=point.get("payload", {}),
        )
        for point in points
    ]

    client.upsert(
        collection_name=collection_name,
        points=qdrant_points,
    )


async def search_vectors(
    collection_name: str,
    query_vector: list[float],
    limit: int = 10,
    filter_conditions: dict | None = None,
) -> list[dict]:
    """Search for similar vectors.

    Args:
        collection_name: Name of the collection
        query_vector: Query embedding vector
        limit: Maximum results to return
        filter_conditions: Optional filter conditions

    Returns:
        List of search results with id, score, and payload
    """
    client = get_qdrant_client()

    search_filter = None
    if filter_conditions:
        # Convert to Qdrant filter format
        search_filter = Filter(**filter_conditions)

    # Use query_points (newer API) instead of search
    response = client.query_points(
        collection_name=collection_name,
        query=query_vector,
        limit=limit,
        query_filter=search_filter,
        with_payload=True,
    )

    return [
        {
            "id": point.id,
            "score": point.score,
            "payload": point.payload,
        }
        for point in response.points
    ]


async def delete_vectors(
    collection_name: str,
    ids: list[str],
) -> None:
    """Delete vectors by ID.

    Args:
        collection_name: Name of the collection
        ids: List of vector IDs to delete
    """
    client = get_qdrant_client()
    client.delete(
        collection_name=collection_name,
        points_selector=ids,
    )


async def delete_vectors_by_filter(
    collection_name: str,
    filter_conditions: dict,
) -> None:
    """Delete vectors matching a filter.

    Args:
        collection_name: Name of the collection
        filter_conditions: Filter conditions for deletion
    """
    client = get_qdrant_client()
    client.delete(
        collection_name=collection_name,
        points_selector=Filter(**filter_conditions),
    )
