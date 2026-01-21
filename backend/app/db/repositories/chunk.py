"""Chunk repository for database operations."""

from typing import Any, Optional
from uuid import UUID

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk, Document


class ChunkRepository:
    """Repository for Chunk database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, chunk_id: UUID) -> Optional[Chunk]:
        """Get chunk by ID.

        Args:
            chunk_id: Chunk UUID

        Returns:
            Chunk if found
        """
        result = await self.session.execute(select(Chunk).where(Chunk.id == chunk_id))
        return result.scalar_one_or_none()

    async def get_by_ids(self, chunk_ids: list[UUID]) -> list[Chunk]:
        """Get multiple chunks by ID.

        Args:
            chunk_ids: List of chunk UUIDs

        Returns:
            List of chunks
        """
        result = await self.session.execute(
            select(Chunk).where(Chunk.id.in_(chunk_ids))
        )
        return list(result.scalars().all())

    async def create_many(self, chunks: list[dict[str, Any]]) -> list[Chunk]:
        """Create multiple chunks.

        Args:
            chunks: List of chunk data dicts

        Returns:
            Created chunks
        """
        chunk_objects = [Chunk(**chunk_data) for chunk_data in chunks]
        self.session.add_all(chunk_objects)
        await self.session.flush()
        return chunk_objects

    async def delete_by_document(self, document_id: UUID) -> int:
        """Delete all chunks for a document.

        Args:
            document_id: Document UUID

        Returns:
            Number of deleted chunks
        """
        result = await self.session.execute(
            delete(Chunk).where(Chunk.document_id == document_id)
        )
        return result.rowcount

    async def list_by_document(
        self,
        document_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Chunk]:
        """List chunks for a document.

        Args:
            document_id: Document UUID
            limit: Maximum chunks
            offset: Pagination offset

        Returns:
            List of chunks ordered by index
        """
        result = await self.session.execute(
            select(Chunk)
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.chunk_index)
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def search_fts(
        self,
        query: str,
        user_id: UUID,
        document_ids: Optional[list[UUID]] = None,
        limit: int = 10,
    ) -> list[tuple[Chunk, float]]:
        """Full-text search across chunks.

        Args:
            query: Search query
            user_id: User ID for document filtering
            document_ids: Optional document ID filter
            limit: Maximum results

        Returns:
            List of (chunk, rank) tuples
        """
        # Build the query with full-text search
        sql = """
            SELECT c.*, ts_rank(c.content_tsv, plainto_tsquery('english', :query)) as rank
            FROM chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE d.user_id = :user_id
            AND d.status = 'ready'
            AND c.content_tsv @@ plainto_tsquery('english', :query)
        """

        params = {"query": query, "user_id": str(user_id)}

        if document_ids:
            sql += " AND c.document_id = ANY(:doc_ids)"
            params["doc_ids"] = [str(did) for did in document_ids]

        sql += " ORDER BY rank DESC LIMIT :limit"
        params["limit"] = limit

        result = await self.session.execute(text(sql), params)
        rows = result.fetchall()

        # Convert to Chunk objects and ranks
        chunks_with_ranks = []
        for row in rows:
            chunk = Chunk(
                id=row.id,
                document_id=row.document_id,
                content=row.content,
                chunk_index=row.chunk_index,
                page_numbers=row.page_numbers,
                start_offset=row.start_offset,
                end_offset=row.end_offset,
                token_count=row.token_count,
                extracted_metadata=row.extracted_metadata,
                created_at=row.created_at,
            )
            chunks_with_ranks.append((chunk, row.rank))

        return chunks_with_ranks

    async def count_by_document(self, document_id: UUID) -> int:
        """Count chunks for a document.

        Args:
            document_id: Document UUID

        Returns:
            Number of chunks
        """
        result = await self.session.execute(
            select(func.count(Chunk.id)).where(Chunk.document_id == document_id)
        )
        return result.scalar_one()

    async def get_total_tokens(self, document_id: UUID) -> int:
        """Get total token count for a document.

        Args:
            document_id: Document UUID

        Returns:
            Total tokens
        """
        result = await self.session.execute(
            select(func.sum(Chunk.token_count)).where(Chunk.document_id == document_id)
        )
        return result.scalar_one() or 0
