"""Document repository for database operations."""

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from sqlalchemy import func, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Document, Chunk


class DocumentRepository:
    """Repository for Document database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(
        self,
        document_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> Optional[Document]:
        """Get document by ID.

        Args:
            document_id: Document UUID
            user_id: Optional user ID for ownership check

        Returns:
            Document if found, None otherwise
        """
        query = select(Document).where(Document.id == document_id)
        if user_id is not None:
            query = query.where(Document.user_id == user_id)

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_id_with_chunks(
        self,
        document_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> Optional[Document]:
        """Get document by ID with chunks loaded.

        Args:
            document_id: Document UUID
            user_id: Optional user ID for ownership check

        Returns:
            Document with chunks if found
        """
        query = (
            select(Document)
            .options(selectinload(Document.chunks))
            .where(Document.id == document_id)
        )
        if user_id is not None:
            query = query.where(Document.user_id == user_id)

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_normalized_filename(
        self,
        user_id: UUID,
        normalized_filename: str,
    ) -> Optional[Document]:
        """Get document by normalized filename for a user.

        Args:
            user_id: User UUID
            normalized_filename: Normalized filename

        Returns:
            Document if found
        """
        result = await self.session.execute(
            select(Document).where(
                Document.user_id == user_id,
                Document.normalized_filename == normalized_filename,
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        user_id: UUID,
        filename: str,
        normalized_filename: str,
        file_type: Literal["pdf", "txt"],
        file_path: str,
        file_size: int,
        chunking_strategy: str = "fixed",
        ocr_enabled: bool = False,
    ) -> Document:
        """Create a new document.

        Args:
            user_id: Owner user ID
            filename: Original filename
            normalized_filename: Normalized filename
            file_type: File type (pdf or txt)
            file_path: Path to stored file
            file_size: File size in bytes
            chunking_strategy: Chunking strategy to use
            ocr_enabled: Whether OCR is enabled

        Returns:
            Created document
        """
        document = Document(
            user_id=user_id,
            filename=filename,
            normalized_filename=normalized_filename,
            file_type=file_type,
            file_path=file_path,
            file_size=file_size,
            chunking_strategy=chunking_strategy,
            ocr_enabled=ocr_enabled,
        )
        self.session.add(document)
        await self.session.flush()
        return document

    async def update_status(
        self,
        document_id: UUID,
        status: Literal["pending", "processing", "ready", "failed"],
        error_message: Optional[str] = None,
        page_count: Optional[int] = None,
    ) -> Optional[Document]:
        """Update document status.

        Args:
            document_id: Document UUID
            status: New status
            error_message: Error message if failed
            page_count: Page count if known

        Returns:
            Updated document
        """
        values = {"status": status, "updated_at": datetime.utcnow()}
        if error_message is not None:
            values["error_message"] = error_message
        if page_count is not None:
            values["page_count"] = page_count

        await self.session.execute(
            update(Document).where(Document.id == document_id).values(**values)
        )
        return await self.get_by_id(document_id)

    async def claim_for_processing(self, document_id: UUID) -> bool:
        """Atomically claim a document for processing.

        Args:
            document_id: Document UUID

        Returns:
            True if claimed, False if already processing
        """
        result = await self.session.execute(
            update(Document)
            .where(Document.id == document_id, Document.status == "pending")
            .values(status="processing", updated_at=datetime.utcnow())
            .returning(Document.id)
        )
        row = result.scalar_one_or_none()
        await self.session.commit()
        return row is not None

    async def delete(self, document_id: UUID) -> bool:
        """Delete a document.

        Args:
            document_id: Document UUID

        Returns:
            True if deleted
        """
        result = await self.session.execute(
            delete(Document).where(Document.id == document_id).returning(Document.id)
        )
        row = result.scalar_one_or_none()
        await self.session.commit()
        return row is not None

    async def list_by_user(
        self,
        user_id: UUID,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Document]:
        """List documents for a user.

        Args:
            user_id: User UUID
            status: Optional status filter
            limit: Maximum documents to return
            offset: Pagination offset

        Returns:
            List of documents
        """
        query = select(Document).where(Document.user_id == user_id)

        if status is not None:
            query = query.where(Document.status == status)

        query = query.order_by(Document.created_at.desc()).limit(limit).offset(offset)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count_by_user(
        self,
        user_id: UUID,
        status: Optional[str] = None,
    ) -> int:
        """Count documents for a user.

        Args:
            user_id: User UUID
            status: Optional status filter

        Returns:
            Count of documents
        """
        query = select(func.count(Document.id)).where(Document.user_id == user_id)

        if status is not None:
            query = query.where(Document.status == status)

        result = await self.session.execute(query)
        return result.scalar_one()

    async def list_all(
        self,
        user_id: Optional[UUID] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Document]:
        """List all documents (admin).

        Args:
            user_id: Optional user ID filter
            status: Optional status filter
            limit: Maximum documents
            offset: Pagination offset

        Returns:
            List of documents
        """
        query = select(Document)

        if user_id is not None:
            query = query.where(Document.user_id == user_id)
        if status is not None:
            query = query.where(Document.status == status)

        query = query.order_by(Document.created_at.desc()).limit(limit).offset(offset)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count_by_status(self) -> dict[str, int]:
        """Get document count by status.

        Returns:
            Dict mapping status to count
        """
        result = await self.session.execute(
            select(Document.status, func.count(Document.id)).group_by(Document.status)
        )
        return {row[0]: row[1] for row in result.all()}

    async def get_chunk_count(self, document_id: UUID) -> int:
        """Get chunk count for a document.

        Args:
            document_id: Document UUID

        Returns:
            Number of chunks
        """
        result = await self.session.execute(
            select(func.count(Chunk.id)).where(Chunk.document_id == document_id)
        )
        return result.scalar_one()
