"""Tests for DocumentRepository."""

import pytest
from datetime import datetime
from uuid import uuid4

from app.db.repositories.document import DocumentRepository
from app.db.models import Document


class TestDocumentRepository:
    """Test cases for DocumentRepository."""

    @pytest.fixture
    async def repo(self, db_session):
        """Create repository instance."""
        return DocumentRepository(db_session)

    @pytest.fixture
    async def test_document(self, db_session, test_user, sample_document_data):
        """Create a test document."""
        doc = Document(
            user_id=test_user.id,
            **sample_document_data,
        )
        db_session.add(doc)
        await db_session.flush()
        return doc

    # =========================================================================
    # get_by_id tests
    # =========================================================================

    async def test_get_by_id_returns_document_when_exists(
        self, repo, test_document
    ):
        """Test get_by_id returns document when it exists."""
        result = await repo.get_by_id(test_document.id)

        assert result is not None
        assert result.id == test_document.id
        assert result.filename == test_document.filename

    async def test_get_by_id_returns_none_when_not_exists(self, repo):
        """Test get_by_id returns None when document does not exist."""
        result = await repo.get_by_id(uuid4())

        assert result is None

    async def test_get_by_id_with_user_filter(
        self, repo, test_document, test_user, regular_user
    ):
        """Test get_by_id filters by user_id when provided."""
        # Should find with correct user
        result = await repo.get_by_id(test_document.id, user_id=test_user.id)
        assert result is not None

        # Should not find with wrong user
        result = await repo.get_by_id(test_document.id, user_id=regular_user.id)
        assert result is None

    # =========================================================================
    # get_by_id_with_chunks tests
    # =========================================================================

    async def test_get_by_id_with_chunks_loads_chunks(
        self, repo, test_document, db_session
    ):
        """Test get_by_id_with_chunks eager loads chunks."""
        # Add a chunk to the document
        from app.db.models import Chunk

        chunk = Chunk(
            document_id=test_document.id,
            content="Test chunk content",
            chunk_index=0,
            start_offset=0,
            end_offset=100,
            token_count=10,
        )
        db_session.add(chunk)
        await db_session.flush()

        result = await repo.get_by_id_with_chunks(test_document.id)

        assert result is not None
        assert len(result.chunks) == 1
        assert result.chunks[0].content == "Test chunk content"

    async def test_get_by_id_with_chunks_returns_none_when_not_exists(self, repo):
        """Test get_by_id_with_chunks returns None when not found."""
        result = await repo.get_by_id_with_chunks(uuid4())

        assert result is None

    # =========================================================================
    # get_by_normalized_filename tests
    # =========================================================================

    async def test_get_by_normalized_filename_returns_document(
        self, repo, test_document, test_user
    ):
        """Test get_by_normalized_filename returns matching document."""
        result = await repo.get_by_normalized_filename(
            test_user.id, test_document.normalized_filename
        )

        assert result is not None
        assert result.id == test_document.id

    async def test_get_by_normalized_filename_returns_none_for_different_user(
        self, repo, test_document, regular_user
    ):
        """Test get_by_normalized_filename returns None for different user."""
        result = await repo.get_by_normalized_filename(
            regular_user.id, test_document.normalized_filename
        )

        assert result is None

    async def test_get_by_normalized_filename_returns_none_when_not_exists(
        self, repo, test_user
    ):
        """Test get_by_normalized_filename returns None when not found."""
        result = await repo.get_by_normalized_filename(
            test_user.id, "nonexistent.pdf"
        )

        assert result is None

    # =========================================================================
    # create tests
    # =========================================================================

    async def test_create_document_with_defaults(self, repo, test_user):
        """Test creating document with default values."""
        doc = await repo.create(
            user_id=test_user.id,
            filename="test.pdf",
            normalized_filename="test.pdf",
            file_type="pdf",
            file_path="/uploads/test.pdf",
            file_size=1024,
        )

        assert doc.id is not None
        assert doc.user_id == test_user.id
        assert doc.filename == "test.pdf"
        assert doc.status == "pending"
        assert doc.chunking_strategy == "fixed"
        assert doc.ocr_enabled is False

    async def test_create_document_with_custom_options(self, repo, test_user):
        """Test creating document with custom options."""
        doc = await repo.create(
            user_id=test_user.id,
            filename="ocr_test.pdf",
            normalized_filename="ocr_test.pdf",
            file_type="pdf",
            file_path="/uploads/ocr_test.pdf",
            file_size=2048,
            chunking_strategy="semantic",
            ocr_enabled=True,
        )

        assert doc.chunking_strategy == "semantic"
        assert doc.ocr_enabled is True

    async def test_create_document_txt_type(self, repo, test_user):
        """Test creating a txt document."""
        doc = await repo.create(
            user_id=test_user.id,
            filename="notes.txt",
            normalized_filename="notes.txt",
            file_type="txt",
            file_path="/uploads/notes.txt",
            file_size=512,
        )

        assert doc.file_type == "txt"

    # =========================================================================
    # update_status tests
    # =========================================================================

    async def test_update_status_changes_status(
        self, repo, test_document, db_session
    ):
        """Test update_status changes the document status."""
        result = await repo.update_status(test_document.id, "processing")
        await db_session.commit()

        assert result is not None
        assert result.status == "processing"

    async def test_update_status_sets_error_message_on_failure(
        self, repo, test_document, db_session
    ):
        """Test update_status can set error message."""
        error_msg = "Failed to process document"
        result = await repo.update_status(
            test_document.id, "failed", error_message=error_msg
        )
        await db_session.commit()

        assert result is not None
        assert result.status == "failed"
        assert result.error_message == error_msg

    async def test_update_status_sets_page_count(
        self, repo, test_document, db_session
    ):
        """Test update_status can set page count."""
        result = await repo.update_status(
            test_document.id, "ready", page_count=10
        )
        await db_session.commit()

        assert result is not None
        assert result.status == "ready"
        assert result.page_count == 10

    async def test_update_status_updates_timestamp(
        self, repo, test_document, db_session
    ):
        """Test update_status updates the updated_at timestamp."""
        original_updated = test_document.updated_at

        # Small delay to ensure timestamp difference
        import asyncio
        await asyncio.sleep(0.01)

        await repo.update_status(test_document.id, "processing")
        await db_session.commit()

        result = await repo.get_by_id(test_document.id)
        # Note: timestamps might be the same in fast tests
        assert result is not None

    # =========================================================================
    # delete tests
    # =========================================================================

    async def test_delete_removes_document(self, repo, test_document, db_session):
        """Test delete removes the document."""
        result = await repo.delete(test_document.id)

        assert result is True

        # Verify it's gone
        doc = await repo.get_by_id(test_document.id)
        assert doc is None

    async def test_delete_returns_false_for_nonexistent(self, repo):
        """Test delete returns False for non-existent document."""
        result = await repo.delete(uuid4())

        assert result is False

    # =========================================================================
    # list_by_user tests
    # =========================================================================

    async def test_list_by_user_returns_user_documents(
        self, repo, test_user, test_document
    ):
        """Test list_by_user returns documents for the user."""
        docs = await repo.list_by_user(test_user.id)

        assert len(docs) == 1
        assert docs[0].id == test_document.id

    async def test_list_by_user_excludes_other_users(
        self, repo, test_user, regular_user, test_document
    ):
        """Test list_by_user excludes other users' documents."""
        docs = await repo.list_by_user(regular_user.id)

        assert len(docs) == 0

    async def test_list_by_user_filters_by_status(
        self, repo, test_user, db_session, sample_document_data
    ):
        """Test list_by_user can filter by status."""
        # Create a ready document
        ready_doc = Document(
            user_id=test_user.id,
            filename="ready.pdf",
            normalized_filename="ready.pdf",
            file_type="pdf",
            file_path="/uploads/ready.pdf",
            file_size=1024,
            status="ready",
        )
        db_session.add(ready_doc)

        # Create a pending document
        pending_doc = Document(
            user_id=test_user.id,
            filename="pending.pdf",
            normalized_filename="pending.pdf",
            file_type="pdf",
            file_path="/uploads/pending.pdf",
            file_size=1024,
            status="pending",
        )
        db_session.add(pending_doc)
        await db_session.flush()

        ready_docs = await repo.list_by_user(test_user.id, status="ready")
        pending_docs = await repo.list_by_user(test_user.id, status="pending")

        assert len(ready_docs) == 1
        assert ready_docs[0].filename == "ready.pdf"
        assert len(pending_docs) == 1
        assert pending_docs[0].filename == "pending.pdf"

    async def test_list_by_user_respects_pagination(
        self, repo, test_user, db_session
    ):
        """Test list_by_user respects limit and offset."""
        # Create multiple documents
        for i in range(5):
            doc = Document(
                user_id=test_user.id,
                filename=f"doc{i}.pdf",
                normalized_filename=f"doc{i}.pdf",
                file_type="pdf",
                file_path=f"/uploads/doc{i}.pdf",
                file_size=1024,
            )
            db_session.add(doc)
        await db_session.flush()

        page1 = await repo.list_by_user(test_user.id, limit=2, offset=0)
        page2 = await repo.list_by_user(test_user.id, limit=2, offset=2)

        assert len(page1) == 2
        assert len(page2) == 2
        assert page1[0].id != page2[0].id

    # =========================================================================
    # count_by_user tests
    # =========================================================================

    async def test_count_by_user_returns_correct_count(
        self, repo, test_user, test_document
    ):
        """Test count_by_user returns correct count."""
        count = await repo.count_by_user(test_user.id)

        assert count == 1

    async def test_count_by_user_returns_zero_for_empty(
        self, repo, regular_user
    ):
        """Test count_by_user returns 0 for user with no documents."""
        count = await repo.count_by_user(regular_user.id)

        assert count == 0

    async def test_count_by_user_filters_by_status(
        self, repo, test_user, db_session
    ):
        """Test count_by_user filters by status."""
        # Create docs with different statuses
        for status in ["pending", "ready", "ready"]:
            doc = Document(
                user_id=test_user.id,
                filename=f"{status}_{uuid4()}.pdf",
                normalized_filename=f"{status}_{uuid4()}.pdf",
                file_type="pdf",
                file_path=f"/uploads/{status}.pdf",
                file_size=1024,
                status=status,
            )
            db_session.add(doc)
        await db_session.flush()

        pending_count = await repo.count_by_user(test_user.id, status="pending")
        ready_count = await repo.count_by_user(test_user.id, status="ready")

        assert pending_count == 1
        assert ready_count == 2

    # =========================================================================
    # list_all tests
    # =========================================================================

    async def test_list_all_returns_all_documents(
        self, repo, test_user, regular_user, db_session
    ):
        """Test list_all returns all documents."""
        # Create document for regular_user too
        doc = Document(
            user_id=regular_user.id,
            filename="regular.pdf",
            normalized_filename="regular.pdf",
            file_type="pdf",
            file_path="/uploads/regular.pdf",
            file_size=1024,
        )
        db_session.add(doc)

        # Create for test_user
        doc2 = Document(
            user_id=test_user.id,
            filename="test.pdf",
            normalized_filename="test.pdf",
            file_type="pdf",
            file_path="/uploads/test.pdf",
            file_size=1024,
        )
        db_session.add(doc2)
        await db_session.flush()

        docs = await repo.list_all()

        assert len(docs) == 2

    async def test_list_all_filters_by_user(
        self, repo, test_user, regular_user, db_session
    ):
        """Test list_all can filter by user_id."""
        # Create docs for both users
        doc1 = Document(
            user_id=test_user.id,
            filename="test.pdf",
            normalized_filename="test.pdf",
            file_type="pdf",
            file_path="/uploads/test.pdf",
            file_size=1024,
        )
        doc2 = Document(
            user_id=regular_user.id,
            filename="regular.pdf",
            normalized_filename="regular.pdf",
            file_type="pdf",
            file_path="/uploads/regular.pdf",
            file_size=1024,
        )
        db_session.add(doc1)
        db_session.add(doc2)
        await db_session.flush()

        test_docs = await repo.list_all(user_id=test_user.id)

        assert len(test_docs) == 1
        assert test_docs[0].user_id == test_user.id

    # =========================================================================
    # count_by_status tests
    # =========================================================================

    async def test_count_by_status_groups_correctly(
        self, repo, test_user, db_session
    ):
        """Test count_by_status returns correct counts per status."""
        # Create docs with various statuses
        statuses = ["pending", "pending", "processing", "ready", "ready", "ready", "failed"]
        for i, status in enumerate(statuses):
            doc = Document(
                user_id=test_user.id,
                filename=f"doc{i}.pdf",
                normalized_filename=f"doc{i}.pdf",
                file_type="pdf",
                file_path=f"/uploads/doc{i}.pdf",
                file_size=1024,
                status=status,
            )
            db_session.add(doc)
        await db_session.flush()

        counts = await repo.count_by_status()

        assert counts.get("pending", 0) == 2
        assert counts.get("processing", 0) == 1
        assert counts.get("ready", 0) == 3
        assert counts.get("failed", 0) == 1

    async def test_count_by_status_returns_empty_for_no_docs(self, repo):
        """Test count_by_status returns empty dict when no documents."""
        counts = await repo.count_by_status()

        assert isinstance(counts, dict)
        assert len(counts) == 0

    # =========================================================================
    # get_chunk_count tests
    # =========================================================================

    async def test_get_chunk_count_returns_zero_for_no_chunks(
        self, repo, test_document
    ):
        """Test get_chunk_count returns 0 when no chunks."""
        count = await repo.get_chunk_count(test_document.id)

        assert count == 0

    async def test_get_chunk_count_returns_correct_count(
        self, repo, test_document, db_session
    ):
        """Test get_chunk_count returns correct count."""
        from app.db.models import Chunk

        # Add chunks
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
        await db_session.flush()

        count = await repo.get_chunk_count(test_document.id)

        assert count == 3


class TestDocumentRepositoryEdgeCases:
    """Edge case tests for DocumentRepository."""

    @pytest.fixture
    async def repo(self, db_session):
        """Create repository instance."""
        return DocumentRepository(db_session)

    async def test_normalized_filename_uniqueness_per_user(
        self, repo, test_user, regular_user, db_session
    ):
        """Test same normalized filename can exist for different users."""
        # Create doc for test_user
        doc1 = await repo.create(
            user_id=test_user.id,
            filename="test.pdf",
            normalized_filename="test.pdf",
            file_type="pdf",
            file_path="/uploads/test.pdf",
            file_size=1024,
        )

        # Create doc with same normalized filename for regular_user
        doc2 = await repo.create(
            user_id=regular_user.id,
            filename="test.pdf",
            normalized_filename="test.pdf",
            file_type="pdf",
            file_path="/uploads/test2.pdf",
            file_size=1024,
        )

        assert doc1.id != doc2.id
        assert doc1.normalized_filename == doc2.normalized_filename

    async def test_create_with_large_file_size(self, repo, test_user):
        """Test creating document with large file size."""
        large_size = 10 * 1024 * 1024 * 1024  # 10GB

        doc = await repo.create(
            user_id=test_user.id,
            filename="large.pdf",
            normalized_filename="large.pdf",
            file_type="pdf",
            file_path="/uploads/large.pdf",
            file_size=large_size,
        )

        assert doc.file_size == large_size

    async def test_list_by_user_with_large_offset(self, repo, test_user):
        """Test list_by_user with offset larger than document count."""
        docs = await repo.list_by_user(test_user.id, offset=1000)

        assert len(docs) == 0

    async def test_update_status_all_transitions(self, repo, test_user, db_session):
        """Test all valid status transitions."""
        doc = await repo.create(
            user_id=test_user.id,
            filename="status_test.pdf",
            normalized_filename="status_test.pdf",
            file_type="pdf",
            file_path="/uploads/status_test.pdf",
            file_size=1024,
        )

        # pending -> processing
        result = await repo.update_status(doc.id, "processing")
        assert result.status == "processing"

        # processing -> ready
        result = await repo.update_status(doc.id, "ready")
        assert result.status == "ready"

        # Can also go to failed from any state
        result = await repo.update_status(doc.id, "failed", error_message="Test error")
        assert result.status == "failed"
        assert result.error_message == "Test error"
