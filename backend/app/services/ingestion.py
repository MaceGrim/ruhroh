"""Document ingestion service."""

import os
import unicodedata
from pathlib import Path
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.database import get_session_factory
from app.db.repositories.document import DocumentRepository
from app.db.repositories.chunk import ChunkRepository
from app.services.llm import LLMService
from app.services.qdrant import (
    ensure_collection_exists,
    upsert_vectors,
    delete_vectors_by_filter,
)
from app.utils.chunking import get_chunker, ChunkInfo
from app.utils.pdf import extract_text_from_pdf, extract_text_from_txt

logger = structlog.get_logger()


class IngestionError(Exception):
    """Document ingestion error."""

    pass


class IngestionService:
    """Service for document ingestion pipeline."""

    def __init__(
        self,
        settings: Settings,
        session: Optional[AsyncSession] = None,
        llm_service: Optional[LLMService] = None,
    ):
        self.settings = settings
        self.session = session
        self.llm_service = llm_service or LLMService(settings)
        if session:
            self.doc_repo = DocumentRepository(session)
            self.chunk_repo = ChunkRepository(session)
        else:
            self.doc_repo = None
            self.chunk_repo = None

    def normalize_filename(self, filename: str) -> str:
        """Normalize a filename for duplicate detection.

        Args:
            filename: Original filename

        Returns:
            Normalized lowercase filename
        """
        # Normalize unicode
        normalized = unicodedata.normalize("NFKC", filename)
        # Lowercase
        normalized = normalized.lower()
        # Remove extra whitespace
        normalized = " ".join(normalized.split())
        return normalized

    async def process_document(self, document_id: UUID) -> None:
        """Process a document through the ingestion pipeline.

        This is the main pipeline that:
        1. Claims the document for processing
        2. Extracts text
        3. Chunks the text
        4. Generates embeddings
        5. Stores chunks and vectors

        Args:
            document_id: Document UUID to process

        Raises:
            IngestionError: If processing fails
        """
        # Create own session for background task processing
        session_factory = get_session_factory()
        async with session_factory() as session:
            doc_repo = DocumentRepository(session)
            chunk_repo = ChunkRepository(session)

            # Claim document for processing
            claimed = await doc_repo.claim_for_processing(document_id)
            if not claimed:
                logger.info(
                    "document_already_processing",
                    document_id=str(document_id),
                )
                return

            try:
                # Get document
                document = await doc_repo.get_by_id(document_id)
                if not document:
                    raise IngestionError(f"Document not found: {document_id}")

                logger.info(
                    "processing_document",
                    document_id=str(document_id),
                    filename=document.filename,
                )

                # Extract text
                text, page_boundaries, page_count = await self._extract_text(document)

                # Update page count
                if page_count:
                    await doc_repo.update_status(
                        document_id,
                        "processing",
                        page_count=page_count,
                    )

                # Chunk text
                chunks = await self._chunk_text(
                    text,
                    document.chunking_strategy,
                    page_boundaries,
                )

                if not chunks:
                    raise IngestionError("No chunks generated from document")

                # Store chunks in database
                chunk_records = await self._store_chunks_with_repo(document_id, chunks, chunk_repo)

                # Generate embeddings and store in Qdrant
                await self._generate_and_store_vectors(
                    document_id,
                    document.user_id,
                    chunk_records,
                )

                # Mark as ready
                await doc_repo.update_status(document_id, "ready")
                await session.commit()

                logger.info(
                    "document_processed",
                    document_id=str(document_id),
                    chunk_count=len(chunks),
                )

            except Exception as e:
                logger.error(
                    "document_processing_failed",
                    document_id=str(document_id),
                    error=str(e),
                )
                await doc_repo.update_status(
                    document_id,
                    "failed",
                    error_message=str(e),
                )
                await session.commit()
                raise IngestionError(f"Processing failed: {e}")

    async def _extract_text(
        self,
        document,
    ) -> tuple[str, Optional[list[tuple[int, int]]], Optional[int]]:
        """Extract text from document.

        Args:
            document: Document model

        Returns:
            Tuple of (text, page_boundaries, page_count)
        """
        file_path = Path(document.file_path)

        if document.file_type == "pdf":
            pdf_content = extract_text_from_pdf(file_path)
            return (
                pdf_content.text,
                pdf_content.page_boundaries,
                pdf_content.page_count,
            )
        else:
            text = extract_text_from_txt(file_path)
            return text, None, None

    async def _chunk_text(
        self,
        text: str,
        strategy: str,
        page_boundaries: Optional[list[tuple[int, int]]],
    ) -> list[ChunkInfo]:
        """Chunk text using specified strategy.

        Args:
            text: Text to chunk
            strategy: Chunking strategy
            page_boundaries: Optional page boundary info

        Returns:
            List of ChunkInfo objects
        """
        chunker = get_chunker(
            strategy,
            self.settings.ruhroh_chunk_size,
            self.settings.ruhroh_chunk_overlap,
        )
        return chunker.chunk_text(text, page_boundaries)

    async def _store_chunks(
        self,
        document_id: UUID,
        chunks: list[ChunkInfo],
    ) -> list[dict]:
        """Store chunks in database using instance repo."""
        return await self._store_chunks_with_repo(document_id, chunks, self.chunk_repo)

    async def _store_chunks_with_repo(
        self,
        document_id: UUID,
        chunks: list[ChunkInfo],
        chunk_repo: ChunkRepository,
    ) -> list[dict]:
        """Store chunks in database.

        Args:
            document_id: Document UUID
            chunks: List of ChunkInfo
            chunk_repo: ChunkRepository instance

        Returns:
            List of created chunk records as dicts
        """
        chunk_data = [
            {
                "document_id": document_id,
                "content": chunk.content,
                "chunk_index": chunk.chunk_index,
                "page_numbers": chunk.page_numbers,
                "start_offset": chunk.start_offset,
                "end_offset": chunk.end_offset,
                "token_count": chunk.token_count,
                "extracted_metadata": {},
            }
            for chunk in chunks
        ]

        chunk_records = await chunk_repo.create_many(chunk_data)

        return [
            {
                "id": str(c.id),
                "content": c.content,
                "document_id": str(c.document_id),
                "chunk_index": c.chunk_index,
                "page_numbers": c.page_numbers,
            }
            for c in chunk_records
        ]

    async def _generate_and_store_vectors(
        self,
        document_id: UUID,
        user_id: UUID,
        chunk_records: list[dict],
    ) -> None:
        """Generate embeddings and store in Qdrant.

        Args:
            document_id: Document UUID
            user_id: User UUID for filtering
            chunk_records: List of chunk dicts with id and content
        """
        # Ensure collection exists
        await ensure_collection_exists(self.settings.qdrant_collection_name)

        # Generate embeddings in batches
        batch_size = 100
        all_points = []

        for i in range(0, len(chunk_records), batch_size):
            batch = chunk_records[i : i + batch_size]
            texts = [c["content"] for c in batch]

            embeddings = await self.llm_service.generate_embeddings(texts)

            for chunk, embedding in zip(batch, embeddings):
                all_points.append({
                    "id": chunk["id"],
                    "vector": embedding,
                    "payload": {
                        "document_id": str(document_id),
                        "user_id": str(user_id),
                        "chunk_index": chunk["chunk_index"],
                        "page_numbers": chunk["page_numbers"],
                    },
                })

        # Upsert all vectors
        await upsert_vectors(self.settings.qdrant_collection_name, all_points)

    async def reprocess_document(
        self,
        document_id: UUID,
        chunking_strategy: Optional[str] = None,
        ocr_enabled: Optional[bool] = None,
    ) -> None:
        """Reprocess a document with new settings.

        Args:
            document_id: Document UUID
            chunking_strategy: New chunking strategy
            ocr_enabled: Whether to enable OCR
        """
        # Create own session for background task
        session_factory = get_session_factory()
        async with session_factory() as session:
            doc_repo = DocumentRepository(session)
            chunk_repo = ChunkRepository(session)

            document = await doc_repo.get_by_id(document_id)
            if not document:
                raise IngestionError(f"Document not found: {document_id}")

            # Delete existing chunks from database
            await chunk_repo.delete_by_document(document_id)

            # Delete vectors from Qdrant
            await delete_vectors_by_filter(
                self.settings.qdrant_collection_name,
                {"must": [{"key": "document_id", "match": {"value": str(document_id)}}]},
            )

            # Update document settings and reset status
            await doc_repo.update_status(document_id, "pending")
            await session.commit()

        # Process again (creates its own session)
        await self.process_document(document_id)

    async def delete_document(self, document_id: UUID, session: Optional[AsyncSession] = None) -> bool:
        """Delete a document and all associated data.

        Args:
            document_id: Document UUID
            session: Optional session to use (creates own if not provided)

        Returns:
            True if deleted
        """
        # Use provided session or create a new one
        if session:
            return await self._delete_document_with_session(document_id, session)

        session_factory = get_session_factory()
        async with session_factory() as new_session:
            result = await self._delete_document_with_session(document_id, new_session)
            await new_session.commit()
            return result

    async def _delete_document_with_session(self, document_id: UUID, session: AsyncSession) -> bool:
        """Delete document using provided session."""
        doc_repo = DocumentRepository(session)
        document = await doc_repo.get_by_id(document_id)
        if not document:
            return False

        # Delete vectors from Qdrant
        try:
            await delete_vectors_by_filter(
                self.settings.qdrant_collection_name,
                {"must": [{"key": "document_id", "match": {"value": str(document_id)}}]},
            )
        except Exception as e:
            logger.warning(
                "qdrant_delete_failed",
                document_id=str(document_id),
                error=str(e),
            )

        # Delete file from storage
        try:
            file_path = Path(document.file_path)
            if file_path.exists():
                file_path.unlink()
        except Exception as e:
            logger.warning(
                "file_delete_failed",
                document_id=str(document_id),
                error=str(e),
            )

        # Delete from database (cascades to chunks)
        return await doc_repo.delete(document_id)
