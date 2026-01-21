"""Tests for the retrieval service."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.config import Settings
from app.db.models import Chunk, Document
from app.services.retrieval import RetrievalService, RetrievalResult


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def test_settings():
    """Create test settings."""
    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        qdrant_host="localhost",
        qdrant_port=6333,
        qdrant_collection_name="test_documents",
        supabase_url="http://localhost:54321",
        supabase_anon_key="test-anon-key",
        supabase_service_role_key="test-service-key",
        openai_api_key="test-openai-key",
        anthropic_api_key="test-anthropic-key",
        ruhroh_vector_weight=0.6,
        ruhroh_keyword_weight=0.4,
        ruhroh_rrf_k=60,
        dev_mode=True,
    )


@pytest.fixture
def mock_session():
    """Create mock database session."""
    return AsyncMock()


@pytest.fixture
def mock_llm_service():
    """Create mock LLM service."""
    mock = AsyncMock()
    mock.generate_embedding.return_value = [0.1] * 1536
    return mock


@pytest.fixture
def retrieval_service(test_settings, mock_session, mock_llm_service):
    """Create retrieval service with mocked dependencies."""
    return RetrievalService(
        settings=test_settings,
        session=mock_session,
        llm_service=mock_llm_service,
    )


@pytest.fixture
def sample_user_id():
    """Sample user UUID."""
    return UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture
def sample_document_id():
    """Sample document UUID."""
    return UUID("00000000-0000-0000-0000-000000000002")


@pytest.fixture
def sample_chunk_id():
    """Sample chunk UUID."""
    return UUID("00000000-0000-0000-0000-000000000003")


@pytest.fixture
def sample_chunk(sample_chunk_id, sample_document_id):
    """Create sample chunk object."""
    chunk = MagicMock(spec=Chunk)
    chunk.id = sample_chunk_id
    chunk.document_id = sample_document_id
    chunk.content = "This is the chunk content for testing."
    chunk.chunk_index = 0
    chunk.page_numbers = [1, 2]
    chunk.start_offset = 0
    chunk.end_offset = 100
    chunk.token_count = 10
    chunk.created_at = datetime.utcnow()
    return chunk


@pytest.fixture
def sample_document(sample_document_id, sample_user_id):
    """Create sample document object."""
    doc = MagicMock(spec=Document)
    doc.id = sample_document_id
    doc.user_id = sample_user_id
    doc.filename = "test_document.pdf"
    doc.normalized_filename = "test_document.pdf"
    doc.file_type = "pdf"
    doc.status = "ready"
    return doc


# =============================================================================
# Test: _vector_search
# =============================================================================


class TestVectorSearch:
    """Tests for vector search functionality."""

    @pytest.mark.asyncio
    async def test_vector_search_empty_results(
        self, retrieval_service, sample_user_id
    ):
        """Test vector search with no results."""
        with patch("app.services.retrieval.search_vectors", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = []
            retrieval_service.chunk_repo.get_by_ids = AsyncMock(return_value=[])

            results = await retrieval_service._vector_search(
                "test query", sample_user_id, limit=10
            )

            assert results == []
            mock_search.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_vector_search_with_results(
        self, retrieval_service, sample_user_id, sample_chunk, sample_document
    ):
        """Test vector search with results."""
        qdrant_result = {
            "id": str(sample_chunk.id),
            "score": 0.95,
            "payload": {},
        }

        with patch("app.services.retrieval.search_vectors", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [qdrant_result]
            retrieval_service.chunk_repo.get_by_ids = AsyncMock(
                return_value=[sample_chunk]
            )
            retrieval_service.doc_repo.get_by_id = AsyncMock(return_value=sample_document)

            results = await retrieval_service._vector_search(
                "test query", sample_user_id, limit=10
            )

            assert len(results) == 1
            assert results[0].chunk_id == sample_chunk.id
            assert results[0].document_id == sample_chunk.document_id
            assert results[0].score == 0.95

    @pytest.mark.asyncio
    async def test_vector_search_with_document_filter(
        self, retrieval_service, sample_user_id, sample_document_id
    ):
        """Test vector search with document ID filter."""
        with patch("app.services.retrieval.search_vectors", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = []
            retrieval_service.chunk_repo.get_by_ids = AsyncMock(return_value=[])

            await retrieval_service._vector_search(
                "test query",
                sample_user_id,
                limit=10,
                document_ids=[sample_document_id],
            )

            # Verify the filter was included in the call
            call_args = mock_search.call_args
            filter_conditions = call_args.kwargs.get("filter_conditions")
            assert filter_conditions is not None
            assert "must" in filter_conditions

    @pytest.mark.asyncio
    async def test_vector_search_chunk_not_found(
        self, retrieval_service, sample_user_id
    ):
        """Test handling when chunk is not found in database."""
        qdrant_result = {
            "id": str(uuid4()),
            "score": 0.95,
            "payload": {},
        }

        with patch("app.services.retrieval.search_vectors", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [qdrant_result]
            retrieval_service.chunk_repo.get_by_ids = AsyncMock(return_value=[])

            results = await retrieval_service._vector_search(
                "test query", sample_user_id, limit=10
            )

            # Should return empty if chunk not in database
            assert results == []


# =============================================================================
# Test: _keyword_search
# =============================================================================


class TestKeywordSearch:
    """Tests for keyword search functionality."""

    @pytest.mark.asyncio
    async def test_keyword_search_empty_results(
        self, retrieval_service, sample_user_id
    ):
        """Test keyword search with no results."""
        retrieval_service.chunk_repo.search_fts = AsyncMock(return_value=[])

        results = await retrieval_service._keyword_search(
            "test query", sample_user_id, limit=10
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_keyword_search_with_results(
        self, retrieval_service, sample_user_id, sample_chunk, sample_document
    ):
        """Test keyword search with results."""
        retrieval_service.chunk_repo.search_fts = AsyncMock(
            return_value=[(sample_chunk, 0.8)]
        )
        retrieval_service.doc_repo.get_by_id = AsyncMock(return_value=sample_document)

        results = await retrieval_service._keyword_search(
            "test query", sample_user_id, limit=10
        )

        assert len(results) == 1
        assert results[0].chunk_id == sample_chunk.id
        assert results[0].score == 0.8
        assert results[0].document_name == sample_document.filename

    @pytest.mark.asyncio
    async def test_keyword_search_with_document_filter(
        self, retrieval_service, sample_user_id, sample_document_id
    ):
        """Test keyword search with document filter."""
        retrieval_service.chunk_repo.search_fts = AsyncMock(return_value=[])

        await retrieval_service._keyword_search(
            "test query",
            sample_user_id,
            limit=10,
            document_ids=[sample_document_id],
        )

        retrieval_service.chunk_repo.search_fts.assert_awaited_once_with(
            "test query", sample_user_id, [sample_document_id], 10
        )

    @pytest.mark.asyncio
    async def test_keyword_search_document_not_found(
        self, retrieval_service, sample_user_id, sample_chunk
    ):
        """Test keyword search when document is deleted."""
        retrieval_service.chunk_repo.search_fts = AsyncMock(
            return_value=[(sample_chunk, 0.8)]
        )
        retrieval_service.doc_repo.get_by_id = AsyncMock(return_value=None)

        results = await retrieval_service._keyword_search(
            "test query", sample_user_id, limit=10
        )

        assert len(results) == 1
        assert results[0].document_name == "Unknown"


# =============================================================================
# Test: _rrf_fusion
# =============================================================================


class TestRRFFusion:
    """Tests for RRF (Reciprocal Rank Fusion) algorithm."""

    def test_rrf_fusion_empty_results(self, retrieval_service):
        """Test RRF fusion with empty results."""
        results = retrieval_service._rrf_fusion([], top_k=5)
        assert results == []

    def test_rrf_fusion_single_source(self, retrieval_service):
        """Test RRF fusion with single source."""
        result1 = RetrievalResult(
            chunk_id=uuid4(),
            document_id=uuid4(),
            document_name="doc1.pdf",
            content="Content 1",
            score=0.9,
            page_numbers=[1],
        )
        result2 = RetrievalResult(
            chunk_id=uuid4(),
            document_id=uuid4(),
            document_name="doc2.pdf",
            content="Content 2",
            score=0.8,
            page_numbers=[2],
        )

        result_lists = [("vector", [result1, result2])]

        fused = retrieval_service._rrf_fusion(result_lists, top_k=5)

        assert len(fused) == 2
        # First result should have higher score
        assert fused[0].chunk_id == result1.chunk_id

    def test_rrf_fusion_two_sources_same_results(self, retrieval_service):
        """Test RRF fusion when both sources have same result."""
        chunk_id = uuid4()
        document_id = uuid4()

        result_vector = RetrievalResult(
            chunk_id=chunk_id,
            document_id=document_id,
            document_name="doc.pdf",
            content="Content",
            score=0.9,
            page_numbers=[1],
        )
        result_keyword = RetrievalResult(
            chunk_id=chunk_id,
            document_id=document_id,
            document_name="doc.pdf",
            content="Content",
            score=0.8,
            page_numbers=[1],
        )

        result_lists = [
            ("vector", [result_vector]),
            ("keyword", [result_keyword]),
        ]

        fused = retrieval_service._rrf_fusion(result_lists, top_k=5)

        # Should be deduplicated to single result with combined score
        assert len(fused) == 1
        assert fused[0].chunk_id == chunk_id

    def test_rrf_fusion_respects_top_k(self, retrieval_service):
        """Test that RRF fusion respects top_k limit."""
        results = []
        for i in range(10):
            results.append(
                RetrievalResult(
                    chunk_id=uuid4(),
                    document_id=uuid4(),
                    document_name=f"doc{i}.pdf",
                    content=f"Content {i}",
                    score=0.9 - i * 0.05,
                    page_numbers=[i],
                )
            )

        result_lists = [("vector", results)]

        fused = retrieval_service._rrf_fusion(result_lists, top_k=3)

        assert len(fused) == 3

    def test_rrf_fusion_weights_applied(self, retrieval_service):
        """Test that vector and keyword weights are applied."""
        chunk_id_1 = uuid4()
        chunk_id_2 = uuid4()

        # Vector search has chunk_1 first
        vector_results = [
            RetrievalResult(
                chunk_id=chunk_id_1,
                document_id=uuid4(),
                document_name="doc1.pdf",
                content="Content 1",
                score=0.9,
            ),
            RetrievalResult(
                chunk_id=chunk_id_2,
                document_id=uuid4(),
                document_name="doc2.pdf",
                content="Content 2",
                score=0.8,
            ),
        ]

        # Keyword search has chunk_2 first
        keyword_results = [
            RetrievalResult(
                chunk_id=chunk_id_2,
                document_id=uuid4(),
                document_name="doc2.pdf",
                content="Content 2",
                score=0.9,
            ),
            RetrievalResult(
                chunk_id=chunk_id_1,
                document_id=uuid4(),
                document_name="doc1.pdf",
                content="Content 1",
                score=0.7,
            ),
        ]

        result_lists = [
            ("vector", vector_results),
            ("keyword", keyword_results),
        ]

        fused = retrieval_service._rrf_fusion(result_lists, top_k=2)

        # Both should be present
        assert len(fused) == 2
        fused_ids = {r.chunk_id for r in fused}
        assert chunk_id_1 in fused_ids
        assert chunk_id_2 in fused_ids


# =============================================================================
# Test: search (hybrid)
# =============================================================================


class TestHybridSearch:
    """Tests for hybrid search combining vector and keyword."""

    @pytest.mark.asyncio
    async def test_hybrid_search_both_enabled(
        self, retrieval_service, sample_user_id
    ):
        """Test hybrid search with both vector and keyword enabled."""
        with patch.object(
            retrieval_service, "_vector_search", new_callable=AsyncMock
        ) as mock_vector, patch.object(
            retrieval_service, "_keyword_search", new_callable=AsyncMock
        ) as mock_keyword:
            mock_vector.return_value = []
            mock_keyword.return_value = []

            await retrieval_service.search(
                "test query",
                sample_user_id,
                top_k=10,
                use_keyword=True,
                use_vector=True,
            )

            mock_vector.assert_awaited_once()
            mock_keyword.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_hybrid_search_vector_only(
        self, retrieval_service, sample_user_id
    ):
        """Test search with only vector search enabled."""
        with patch.object(
            retrieval_service, "_vector_search", new_callable=AsyncMock
        ) as mock_vector, patch.object(
            retrieval_service, "_keyword_search", new_callable=AsyncMock
        ) as mock_keyword:
            result = RetrievalResult(
                chunk_id=uuid4(),
                document_id=uuid4(),
                document_name="doc.pdf",
                content="Content",
                score=0.9,
            )
            mock_vector.return_value = [result]

            results = await retrieval_service.search(
                "test query",
                sample_user_id,
                top_k=10,
                use_keyword=False,
                use_vector=True,
            )

            mock_vector.assert_awaited_once()
            mock_keyword.assert_not_awaited()
            assert len(results) == 1

    @pytest.mark.asyncio
    async def test_hybrid_search_keyword_only(
        self, retrieval_service, sample_user_id
    ):
        """Test search with only keyword search enabled."""
        with patch.object(
            retrieval_service, "_vector_search", new_callable=AsyncMock
        ) as mock_vector, patch.object(
            retrieval_service, "_keyword_search", new_callable=AsyncMock
        ) as mock_keyword:
            result = RetrievalResult(
                chunk_id=uuid4(),
                document_id=uuid4(),
                document_name="doc.pdf",
                content="Content",
                score=0.8,
            )
            mock_keyword.return_value = [result]

            results = await retrieval_service.search(
                "test query",
                sample_user_id,
                top_k=10,
                use_keyword=True,
                use_vector=False,
            )

            mock_vector.assert_not_awaited()
            mock_keyword.assert_awaited_once()
            assert len(results) == 1

    @pytest.mark.asyncio
    async def test_hybrid_search_neither_enabled(
        self, retrieval_service, sample_user_id
    ):
        """Test search with neither method enabled."""
        results = await retrieval_service.search(
            "test query",
            sample_user_id,
            top_k=10,
            use_keyword=False,
            use_vector=False,
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_hybrid_search_respects_top_k(
        self, retrieval_service, sample_user_id
    ):
        """Test that hybrid search respects top_k limit."""
        with patch.object(
            retrieval_service, "_vector_search", new_callable=AsyncMock
        ) as mock_vector, patch.object(
            retrieval_service, "_keyword_search", new_callable=AsyncMock
        ) as mock_keyword:
            # Return more results than top_k
            vector_results = [
                RetrievalResult(
                    chunk_id=uuid4(),
                    document_id=uuid4(),
                    document_name=f"doc{i}.pdf",
                    content=f"Content {i}",
                    score=0.9 - i * 0.05,
                )
                for i in range(10)
            ]
            keyword_results = [
                RetrievalResult(
                    chunk_id=uuid4(),
                    document_id=uuid4(),
                    document_name=f"doc{i}.pdf",
                    content=f"Content {i}",
                    score=0.8 - i * 0.05,
                )
                for i in range(10)
            ]
            mock_vector.return_value = vector_results
            mock_keyword.return_value = keyword_results

            results = await retrieval_service.search(
                "test query",
                sample_user_id,
                top_k=5,
            )

            assert len(results) <= 5


# =============================================================================
# Test: get_context_for_chat
# =============================================================================


class TestGetContextForChat:
    """Tests for context generation for chat."""

    @pytest.mark.asyncio
    async def test_get_context_no_results(self, retrieval_service, sample_user_id):
        """Test context generation with no search results."""
        with patch.object(
            retrieval_service, "search", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = []

            context, results = await retrieval_service.get_context_for_chat(
                "test query", sample_user_id
            )

            assert context == ""
            assert results == []

    @pytest.mark.asyncio
    async def test_get_context_with_results(self, retrieval_service, sample_user_id):
        """Test context generation with search results."""
        result = RetrievalResult(
            chunk_id=uuid4(),
            document_id=uuid4(),
            document_name="test.pdf",
            content="This is the document content.",
            score=0.9,
            page_numbers=[1, 2],
        )

        with patch.object(
            retrieval_service, "search", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = [result]

            context, results = await retrieval_service.get_context_for_chat(
                "test query", sample_user_id
            )

            assert "[1]" in context
            assert "test.pdf" in context
            assert "pages: 1, 2" in context
            assert "This is the document content." in context
            assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_context_multiple_results(
        self, retrieval_service, sample_user_id
    ):
        """Test context generation with multiple results."""
        results = [
            RetrievalResult(
                chunk_id=uuid4(),
                document_id=uuid4(),
                document_name=f"doc{i}.pdf",
                content=f"Content from document {i}.",
                score=0.9 - i * 0.1,
                page_numbers=[i],
            )
            for i in range(3)
        ]

        with patch.object(
            retrieval_service, "search", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = results

            context, returned_results = await retrieval_service.get_context_for_chat(
                "test query", sample_user_id
            )

            assert "[1]" in context
            assert "[2]" in context
            assert "[3]" in context
            assert "doc0.pdf" in context
            assert "doc1.pdf" in context
            assert "doc2.pdf" in context
            assert len(returned_results) == 3

    @pytest.mark.asyncio
    async def test_get_context_without_page_numbers(
        self, retrieval_service, sample_user_id
    ):
        """Test context generation when page numbers are missing."""
        result = RetrievalResult(
            chunk_id=uuid4(),
            document_id=uuid4(),
            document_name="test.pdf",
            content="Content without page info.",
            score=0.9,
            page_numbers=None,
        )

        with patch.object(
            retrieval_service, "search", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = [result]

            context, _ = await retrieval_service.get_context_for_chat(
                "test query", sample_user_id
            )

            assert "pages:" not in context
            assert "test.pdf" in context

    @pytest.mark.asyncio
    async def test_get_context_uses_correct_top_k(
        self, retrieval_service, sample_user_id
    ):
        """Test that get_context_for_chat uses the correct top_k."""
        with patch.object(
            retrieval_service, "search", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = []

            await retrieval_service.get_context_for_chat(
                "test query", sample_user_id, top_k=3
            )

            mock_search.assert_awaited_once_with("test query", sample_user_id, top_k=3)
