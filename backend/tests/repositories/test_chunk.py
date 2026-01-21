"""Tests for ChunkRepository."""

import pytest
from datetime import datetime
from uuid import uuid4

from app.db.repositories.chunk import ChunkRepository
from app.db.models import Chunk, Document


class TestChunkRepository:
    """Test cases for ChunkRepository."""

    @pytest.fixture
    async def repo(self, db_session):
        """Create repository instance."""
        return ChunkRepository(db_session)

    @pytest.fixture
    async def test_document(self, db_session, test_user):
        """Create a test document for chunk tests."""
        doc = Document(
            user_id=test_user.id,
            filename="test.pdf",
            normalized_filename="test.pdf",
            file_type="pdf",
            file_path="/uploads/test.pdf",
            file_size=1024,
            status="ready",
        )
        db_session.add(doc)
        await db_session.flush()
        return doc

    @pytest.fixture
    async def test_chunk(self, db_session, test_document):
        """Create a test chunk."""
        chunk = Chunk(
            document_id=test_document.id,
            content="This is test chunk content.",
            chunk_index=0,
            start_offset=0,
            end_offset=100,
            token_count=10,
        )
        db_session.add(chunk)
        await db_session.flush()
        return chunk

    # =========================================================================
    # get_by_id tests
    # =========================================================================

    async def test_get_by_id_returns_chunk_when_exists(self, repo, test_chunk):
        """Test get_by_id returns chunk when it exists."""
        result = await repo.get_by_id(test_chunk.id)

        assert result is not None
        assert result.id == test_chunk.id
        assert result.content == test_chunk.content

    async def test_get_by_id_returns_none_when_not_exists(self, repo):
        """Test get_by_id returns None when chunk does not exist."""
        result = await repo.get_by_id(uuid4())

        assert result is None

    # =========================================================================
    # get_by_ids tests
    # =========================================================================

    async def test_get_by_ids_returns_matching_chunks(
        self, repo, test_document, db_session
    ):
        """Test get_by_ids returns all matching chunks."""
        # Create multiple chunks
        chunks = []
        for i in range(3):
            chunk = Chunk(
                document_id=test_document.id,
                content=f"Chunk {i} content",
                chunk_index=i,
                start_offset=i * 100,
                end_offset=(i + 1) * 100,
                token_count=10,
            )
            db_session.add(chunk)
            chunks.append(chunk)
        await db_session.flush()

        chunk_ids = [c.id for c in chunks]
        result = await repo.get_by_ids(chunk_ids)

        assert len(result) == 3
        result_ids = {c.id for c in result}
        assert result_ids == set(chunk_ids)

    async def test_get_by_ids_returns_empty_for_no_match(self, repo):
        """Test get_by_ids returns empty list when no chunks match."""
        result = await repo.get_by_ids([uuid4(), uuid4()])

        assert len(result) == 0

    async def test_get_by_ids_returns_partial_match(
        self, repo, test_chunk
    ):
        """Test get_by_ids returns only matching chunks for mixed IDs."""
        result = await repo.get_by_ids([test_chunk.id, uuid4()])

        assert len(result) == 1
        assert result[0].id == test_chunk.id

    async def test_get_by_ids_handles_empty_list(self, repo):
        """Test get_by_ids handles empty list input."""
        result = await repo.get_by_ids([])

        assert len(result) == 0

    # =========================================================================
    # create_many tests
    # =========================================================================

    async def test_create_many_creates_all_chunks(
        self, repo, test_document, db_session
    ):
        """Test create_many creates all provided chunks."""
        chunk_data = [
            {
                "document_id": test_document.id,
                "content": "First chunk content",
                "chunk_index": 0,
                "start_offset": 0,
                "end_offset": 100,
                "token_count": 10,
            },
            {
                "document_id": test_document.id,
                "content": "Second chunk content",
                "chunk_index": 1,
                "start_offset": 100,
                "end_offset": 200,
                "token_count": 15,
            },
            {
                "document_id": test_document.id,
                "content": "Third chunk content",
                "chunk_index": 2,
                "start_offset": 200,
                "end_offset": 300,
                "token_count": 12,
            },
        ]

        result = await repo.create_many(chunk_data)

        assert len(result) == 3
        assert result[0].content == "First chunk content"
        assert result[1].content == "Second chunk content"
        assert result[2].content == "Third chunk content"

    async def test_create_many_without_page_numbers(
        self, repo, test_document, db_session
    ):
        """Test create_many without page_numbers field.

        Note: The page_numbers field uses PostgreSQL's ARRAY type which
        doesn't translate directly to SQLite. In the SQLite test environment,
        we test chunk creation without page_numbers. Page number functionality
        should be tested in integration tests with PostgreSQL.
        """
        chunk_data = [
            {
                "document_id": test_document.id,
                "content": "Content from page 1",
                "chunk_index": 0,
                # Omit page_numbers for SQLite compatibility
                "start_offset": 0,
                "end_offset": 100,
                "token_count": 10,
            },
        ]

        result = await repo.create_many(chunk_data)

        assert len(result) == 1
        # Verify chunk was created with the content
        assert result[0].content == "Content from page 1"

    async def test_create_many_with_metadata(
        self, repo, test_document, db_session
    ):
        """Test create_many with extracted_metadata."""
        chunk_data = [
            {
                "document_id": test_document.id,
                "content": "Content with metadata",
                "chunk_index": 0,
                "start_offset": 0,
                "end_offset": 100,
                "token_count": 10,
                "extracted_metadata": '{"heading": "Introduction"}',
            },
        ]

        result = await repo.create_many(chunk_data)

        assert len(result) == 1

    async def test_create_many_handles_empty_list(self, repo):
        """Test create_many handles empty list."""
        result = await repo.create_many([])

        assert len(result) == 0

    async def test_create_many_persists_chunks(
        self, repo, test_document, db_session
    ):
        """Test create_many actually persists chunks to database."""
        chunk_data = [
            {
                "document_id": test_document.id,
                "content": "Persisted content",
                "chunk_index": 0,
                "start_offset": 0,
                "end_offset": 50,
                "token_count": 5,
            },
        ]

        created = await repo.create_many(chunk_data)

        # Verify we can retrieve it
        retrieved = await repo.get_by_id(created[0].id)
        assert retrieved is not None
        assert retrieved.content == "Persisted content"

    # =========================================================================
    # delete_by_document tests
    # =========================================================================

    async def test_delete_by_document_removes_all_chunks(
        self, repo, test_document, db_session
    ):
        """Test delete_by_document removes all chunks for a document."""
        # Create multiple chunks
        for i in range(5):
            chunk = Chunk(
                document_id=test_document.id,
                content=f"Chunk {i}",
                chunk_index=i,
                start_offset=i * 100,
                end_offset=(i + 1) * 100,
                token_count=10,
            )
            db_session.add(chunk)
        await db_session.flush()

        # Verify chunks exist
        initial_count = await repo.count_by_document(test_document.id)
        assert initial_count == 5

        # Delete all chunks
        deleted_count = await repo.delete_by_document(test_document.id)

        assert deleted_count == 5

        # Verify chunks are gone
        remaining = await repo.list_by_document(test_document.id)
        assert len(remaining) == 0

    async def test_delete_by_document_returns_zero_for_no_chunks(
        self, repo, test_document
    ):
        """Test delete_by_document returns 0 when no chunks exist."""
        count = await repo.delete_by_document(test_document.id)

        assert count == 0

    async def test_delete_by_document_only_affects_target_document(
        self, repo, test_user, db_session
    ):
        """Test delete_by_document only removes chunks from target document."""
        # Create two documents
        doc1 = Document(
            user_id=test_user.id,
            filename="doc1.pdf",
            normalized_filename="doc1.pdf",
            file_type="pdf",
            file_path="/uploads/doc1.pdf",
            file_size=1024,
        )
        doc2 = Document(
            user_id=test_user.id,
            filename="doc2.pdf",
            normalized_filename="doc2.pdf",
            file_type="pdf",
            file_path="/uploads/doc2.pdf",
            file_size=1024,
        )
        db_session.add(doc1)
        db_session.add(doc2)
        await db_session.flush()

        # Add chunks to both
        chunk1 = Chunk(
            document_id=doc1.id,
            content="Doc1 chunk",
            chunk_index=0,
            start_offset=0,
            end_offset=100,
            token_count=10,
        )
        chunk2 = Chunk(
            document_id=doc2.id,
            content="Doc2 chunk",
            chunk_index=0,
            start_offset=0,
            end_offset=100,
            token_count=10,
        )
        db_session.add(chunk1)
        db_session.add(chunk2)
        await db_session.flush()

        # Delete chunks from doc1
        await repo.delete_by_document(doc1.id)

        # Verify doc2 chunks still exist
        doc2_chunks = await repo.list_by_document(doc2.id)
        assert len(doc2_chunks) == 1
        assert doc2_chunks[0].content == "Doc2 chunk"

    # =========================================================================
    # list_by_document tests
    # =========================================================================

    async def test_list_by_document_returns_chunks(
        self, repo, test_document, db_session
    ):
        """Test list_by_document returns chunks for the document."""
        # Create chunks
        for i in range(3):
            chunk = Chunk(
                document_id=test_document.id,
                content=f"Chunk {i}",
                chunk_index=i,
                start_offset=i * 100,
                end_offset=(i + 1) * 100,
                token_count=10,
            )
            db_session.add(chunk)
        await db_session.flush()

        result = await repo.list_by_document(test_document.id)

        assert len(result) == 3

    async def test_list_by_document_ordered_by_chunk_index(
        self, repo, test_document, db_session
    ):
        """Test list_by_document returns chunks ordered by chunk_index."""
        # Create chunks in random order
        for i in [2, 0, 1]:
            chunk = Chunk(
                document_id=test_document.id,
                content=f"Chunk {i}",
                chunk_index=i,
                start_offset=i * 100,
                end_offset=(i + 1) * 100,
                token_count=10,
            )
            db_session.add(chunk)
        await db_session.flush()

        result = await repo.list_by_document(test_document.id)

        assert result[0].chunk_index == 0
        assert result[1].chunk_index == 1
        assert result[2].chunk_index == 2

    async def test_list_by_document_respects_pagination(
        self, repo, test_document, db_session
    ):
        """Test list_by_document respects limit and offset."""
        # Create 10 chunks
        for i in range(10):
            chunk = Chunk(
                document_id=test_document.id,
                content=f"Chunk {i}",
                chunk_index=i,
                start_offset=i * 100,
                end_offset=(i + 1) * 100,
                token_count=10,
            )
            db_session.add(chunk)
        await db_session.flush()

        page1 = await repo.list_by_document(test_document.id, limit=3, offset=0)
        page2 = await repo.list_by_document(test_document.id, limit=3, offset=3)

        assert len(page1) == 3
        assert len(page2) == 3
        assert page1[0].chunk_index == 0
        assert page2[0].chunk_index == 3

    async def test_list_by_document_returns_empty_for_no_chunks(
        self, repo, test_document
    ):
        """Test list_by_document returns empty list for document with no chunks."""
        result = await repo.list_by_document(test_document.id)

        assert len(result) == 0

    # =========================================================================
    # count_by_document tests
    # =========================================================================

    async def test_count_by_document_returns_correct_count(
        self, repo, test_document, db_session
    ):
        """Test count_by_document returns correct count."""
        # Create 5 chunks
        for i in range(5):
            chunk = Chunk(
                document_id=test_document.id,
                content=f"Chunk {i}",
                chunk_index=i,
                start_offset=i * 100,
                end_offset=(i + 1) * 100,
                token_count=10,
            )
            db_session.add(chunk)
        await db_session.flush()

        count = await repo.count_by_document(test_document.id)

        assert count == 5

    async def test_count_by_document_returns_zero_for_no_chunks(
        self, repo, test_document
    ):
        """Test count_by_document returns 0 when no chunks exist."""
        count = await repo.count_by_document(test_document.id)

        assert count == 0

    # =========================================================================
    # get_total_tokens tests
    # =========================================================================

    async def test_get_total_tokens_sums_token_counts(
        self, repo, test_document, db_session
    ):
        """Test get_total_tokens returns sum of all token counts."""
        # Create chunks with different token counts
        token_counts = [10, 20, 30, 40]
        for i, tc in enumerate(token_counts):
            chunk = Chunk(
                document_id=test_document.id,
                content=f"Chunk {i}",
                chunk_index=i,
                start_offset=i * 100,
                end_offset=(i + 1) * 100,
                token_count=tc,
            )
            db_session.add(chunk)
        await db_session.flush()

        total = await repo.get_total_tokens(test_document.id)

        assert total == 100  # 10 + 20 + 30 + 40

    async def test_get_total_tokens_returns_zero_for_no_chunks(
        self, repo, test_document
    ):
        """Test get_total_tokens returns 0 when no chunks exist."""
        total = await repo.get_total_tokens(test_document.id)

        assert total == 0


class TestChunkRepositoryEdgeCases:
    """Edge case tests for ChunkRepository."""

    @pytest.fixture
    async def repo(self, db_session):
        """Create repository instance."""
        return ChunkRepository(db_session)

    @pytest.fixture
    async def test_document(self, db_session, test_user):
        """Create a test document."""
        doc = Document(
            user_id=test_user.id,
            filename="test.pdf",
            normalized_filename="test.pdf",
            file_type="pdf",
            file_path="/uploads/test.pdf",
            file_size=1024,
        )
        db_session.add(doc)
        await db_session.flush()
        return doc

    async def test_create_many_with_large_content(
        self, repo, test_document, db_session
    ):
        """Test create_many handles chunks with large content."""
        large_content = "x" * 100000  # 100KB of content

        chunk_data = [
            {
                "document_id": test_document.id,
                "content": large_content,
                "chunk_index": 0,
                "start_offset": 0,
                "end_offset": 100000,
                "token_count": 25000,
            },
        ]

        result = await repo.create_many(chunk_data)

        assert len(result) == 1
        assert len(result[0].content) == 100000

    async def test_create_many_with_many_chunks(
        self, repo, test_document, db_session
    ):
        """Test create_many handles creating many chunks at once."""
        chunk_data = [
            {
                "document_id": test_document.id,
                "content": f"Chunk {i} content for testing batch creation",
                "chunk_index": i,
                "start_offset": i * 50,
                "end_offset": (i + 1) * 50,
                "token_count": 10,
            }
            for i in range(100)
        ]

        result = await repo.create_many(chunk_data)

        assert len(result) == 100

    async def test_list_by_document_large_offset(
        self, repo, test_document
    ):
        """Test list_by_document with offset larger than chunk count."""
        result = await repo.list_by_document(test_document.id, offset=1000)

        assert len(result) == 0

    async def test_get_by_ids_with_duplicate_ids(
        self, repo, test_document, db_session
    ):
        """Test get_by_ids handles duplicate IDs in input."""
        chunk = Chunk(
            document_id=test_document.id,
            content="Test content",
            chunk_index=0,
            start_offset=0,
            end_offset=100,
            token_count=10,
        )
        db_session.add(chunk)
        await db_session.flush()

        # Query with duplicate IDs
        result = await repo.get_by_ids([chunk.id, chunk.id, chunk.id])

        # Should return only unique chunks
        assert len(result) == 1
        assert result[0].id == chunk.id


class TestChunkCascadeDelete:
    """Test cascade delete behavior for chunks."""

    @pytest.fixture
    async def repo(self, db_session):
        """Create repository instance."""
        return ChunkRepository(db_session)

    async def test_chunks_deleted_when_document_deleted(
        self, repo, test_user, db_session
    ):
        """Test that chunks are deleted when parent document is deleted."""
        from app.db.repositories.document import DocumentRepository
        from sqlalchemy import text

        doc_repo = DocumentRepository(db_session)

        # Create a document
        doc = await doc_repo.create(
            user_id=test_user.id,
            filename="cascade_test.pdf",
            normalized_filename="cascade_test.pdf",
            file_type="pdf",
            file_path="/uploads/cascade_test.pdf",
            file_size=1024,
        )

        # Add chunks
        chunk_data = [
            {
                "document_id": doc.id,
                "content": f"Chunk {i}",
                "chunk_index": i,
                "start_offset": i * 100,
                "end_offset": (i + 1) * 100,
                "token_count": 10,
            }
            for i in range(3)
        ]
        created_chunks = await repo.create_many(chunk_data)
        chunk_ids = [c.id for c in created_chunks]

        # Verify chunks exist
        count = await repo.count_by_document(doc.id)
        assert count == 3

        # Delete the document
        await doc_repo.delete(doc.id)

        # Verify chunks are deleted (cascade)
        # Note: SQLite foreign key cascade must be enabled
        remaining = await repo.get_by_ids(chunk_ids)
        assert len(remaining) == 0
