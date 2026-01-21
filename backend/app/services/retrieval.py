"""Retrieval service for hybrid search."""

from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.repositories.chunk import ChunkRepository
from app.db.repositories.document import DocumentRepository
from app.services.llm import LLMService
from app.services.qdrant import search_vectors

logger = structlog.get_logger()


class RetrievalResult:
    """A retrieval result."""

    def __init__(
        self,
        chunk_id: UUID,
        document_id: UUID,
        document_name: str,
        content: str,
        score: float,
        page_numbers: Optional[list[int]] = None,
    ):
        self.chunk_id = chunk_id
        self.document_id = document_id
        self.document_name = document_name
        self.content = content
        self.score = score
        self.page_numbers = page_numbers


class RetrievalService:
    """Service for hybrid document retrieval."""

    def __init__(
        self,
        settings: Settings,
        session: AsyncSession,
        llm_service: LLMService,
    ):
        self.settings = settings
        self.session = session
        self.chunk_repo = ChunkRepository(session)
        self.doc_repo = DocumentRepository(session)
        self.llm_service = llm_service

    async def search(
        self,
        query: str,
        user_id: UUID,
        top_k: int = 10,
        document_ids: Optional[list[UUID]] = None,
        use_keyword: bool = True,
        use_vector: bool = True,
    ) -> list[RetrievalResult]:
        """Perform hybrid search across documents.

        Args:
            query: Search query
            user_id: User UUID for filtering
            top_k: Number of results to return
            document_ids: Optional filter to specific documents
            use_keyword: Whether to use keyword/FTS search
            use_vector: Whether to use vector search

        Returns:
            List of RetrievalResult objects
        """
        results = []

        # Get more results than needed for fusion
        fetch_k = top_k * 3

        if use_vector:
            vector_results = await self._vector_search(
                query, user_id, fetch_k, document_ids
            )
            results.append(("vector", vector_results))

        if use_keyword:
            keyword_results = await self._keyword_search(
                query, user_id, fetch_k, document_ids
            )
            results.append(("keyword", keyword_results))

        if not results:
            return []

        # If only one search type, return directly
        if len(results) == 1:
            return results[0][1][:top_k]

        # Apply RRF fusion
        return self._rrf_fusion(results, top_k)

    async def _vector_search(
        self,
        query: str,
        user_id: UUID,
        limit: int,
        document_ids: Optional[list[UUID]] = None,
    ) -> list[RetrievalResult]:
        """Perform vector similarity search.

        Args:
            query: Search query
            user_id: User UUID
            limit: Max results
            document_ids: Optional document filter

        Returns:
            List of results sorted by similarity
        """
        # Generate query embedding
        query_embedding = await self.llm_service.generate_embedding(query)

        # Build filter
        filter_conditions = {
            "must": [{"key": "user_id", "match": {"value": str(user_id)}}]
        }

        if document_ids:
            filter_conditions["must"].append({
                "key": "document_id",
                "match": {"any": [str(did) for did in document_ids]},
            })

        # Search Qdrant
        qdrant_results = await search_vectors(
            self.settings.qdrant_collection_name,
            query_embedding,
            limit=limit,
            filter_conditions=filter_conditions,
        )

        # Get chunk details
        chunk_ids = [UUID(r["id"]) for r in qdrant_results]
        chunks = await self.chunk_repo.get_by_ids(chunk_ids)
        chunk_map = {str(c.id): c for c in chunks}

        # Build results
        results = []
        for qdrant_result in qdrant_results:
            chunk = chunk_map.get(qdrant_result["id"])
            if not chunk:
                continue

            # Get document name
            doc = await self.doc_repo.get_by_id(chunk.document_id)
            doc_name = doc.filename if doc else "Unknown"

            results.append(RetrievalResult(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                document_name=doc_name,
                content=chunk.content,
                score=qdrant_result["score"],
                page_numbers=chunk.page_numbers,
            ))

        return results

    async def _keyword_search(
        self,
        query: str,
        user_id: UUID,
        limit: int,
        document_ids: Optional[list[UUID]] = None,
    ) -> list[RetrievalResult]:
        """Perform full-text keyword search.

        Args:
            query: Search query
            user_id: User UUID
            limit: Max results
            document_ids: Optional document filter

        Returns:
            List of results sorted by relevance
        """
        # Use PostgreSQL FTS
        fts_results = await self.chunk_repo.search_fts(
            query, user_id, document_ids, limit
        )

        results = []
        for chunk, rank in fts_results:
            doc = await self.doc_repo.get_by_id(chunk.document_id)
            doc_name = doc.filename if doc else "Unknown"

            results.append(RetrievalResult(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                document_name=doc_name,
                content=chunk.content,
                score=rank,
                page_numbers=chunk.page_numbers,
            ))

        return results

    def _rrf_fusion(
        self,
        result_lists: list[tuple[str, list[RetrievalResult]]],
        top_k: int,
    ) -> list[RetrievalResult]:
        """Apply Reciprocal Rank Fusion to combine results.

        Args:
            result_lists: List of (source_name, results) tuples
            top_k: Number of final results

        Returns:
            Fused and re-ranked results
        """
        k = self.settings.ruhroh_rrf_k
        scores: dict[str, float] = {}
        result_map: dict[str, RetrievalResult] = {}

        for source, results in result_lists:
            weight = (
                self.settings.ruhroh_vector_weight
                if source == "vector"
                else self.settings.ruhroh_keyword_weight
            )

            for rank, result in enumerate(results, start=1):
                chunk_id = str(result.chunk_id)

                # RRF score
                rrf_score = weight / (k + rank)

                if chunk_id in scores:
                    scores[chunk_id] += rrf_score
                else:
                    scores[chunk_id] = rrf_score
                    result_map[chunk_id] = result

        # Sort by fused score
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

        # Update scores and return top_k
        final_results = []
        for chunk_id in sorted_ids[:top_k]:
            result = result_map[chunk_id]
            result.score = scores[chunk_id]
            final_results.append(result)

        return final_results

    async def get_context_for_chat(
        self,
        query: str,
        user_id: UUID,
        top_k: int = 5,
    ) -> tuple[str, list[RetrievalResult]]:
        """Get context for chat response generation.

        Args:
            query: User query
            user_id: User UUID
            top_k: Number of chunks to retrieve

        Returns:
            Tuple of (formatted_context, results)
        """
        results = await self.search(query, user_id, top_k=top_k)

        if not results:
            return "", []

        # Format context for LLM
        context_parts = []
        for i, result in enumerate(results, start=1):
            page_info = ""
            if result.page_numbers:
                pages = ", ".join(str(p) for p in result.page_numbers)
                page_info = f" (pages: {pages})"

            context_parts.append(
                f"[{i}] From \"{result.document_name}\"{page_info}:\n"
                f"{result.content}"
            )

        context = "\n\n".join(context_parts)
        return context, results
