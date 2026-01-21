"""Tests for search API endpoints."""

from uuid import UUID, uuid4
from unittest.mock import patch, MagicMock, AsyncMock
from dataclasses import dataclass

import pytest
from httpx import AsyncClient

from tests.conftest import TEST_USER_ID

# Note: Authentication tests are skipped because dev_mode=True bypasses auth


@dataclass
class MockRetrievalResult:
    """Mock retrieval result for testing."""
    chunk_id: UUID
    document_id: UUID
    document_name: str
    content: str
    page_numbers: list[int]
    score: float


class TestSearchEndpoint:
    """Test search endpoint."""

    async def test_search_basic(self, client: AsyncClient):
        """Test basic search request."""
        mock_results = [
            MockRetrievalResult(
                chunk_id=uuid4(),
                document_id=uuid4(),
                document_name="test.pdf",
                content="This is test content about Python programming.",
                page_numbers=[1, 2],
                score=0.95,
            )
        ]

        with patch("app.api.search.RetrievalService") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            mock_instance.search = AsyncMock(return_value=mock_results)

            response = await client.post(
                "/api/v1/search",
                json={"query": "Python programming"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 1
        assert data["results"][0]["document_name"] == "test.pdf"
        assert data["results"][0]["score"] == 0.95

    async def test_search_empty_results(self, client: AsyncClient):
        """Test search with no results."""
        with patch("app.api.search.RetrievalService") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            mock_instance.search = AsyncMock(return_value=[])

            response = await client.post(
                "/api/v1/search",
                json={"query": "nonexistent topic xyz123"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["results"] == []

    async def test_search_with_top_k(self, client: AsyncClient):
        """Test search with custom top_k parameter."""
        mock_results = [
            MockRetrievalResult(
                chunk_id=uuid4(),
                document_id=uuid4(),
                document_name=f"doc{i}.pdf",
                content=f"Content {i}",
                page_numbers=[i],
                score=0.9 - (i * 0.1),
            )
            for i in range(3)
        ]

        with patch("app.api.search.RetrievalService") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            mock_instance.search = AsyncMock(return_value=mock_results)

            response = await client.post(
                "/api/v1/search",
                json={"query": "test", "top_k": 3},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 3

    async def test_search_with_document_filter(self, client: AsyncClient):
        """Test search with document_ids filter."""
        doc_id = uuid4()
        mock_results = [
            MockRetrievalResult(
                chunk_id=uuid4(),
                document_id=doc_id,
                document_name="filtered.pdf",
                content="Filtered content",
                page_numbers=[1],
                score=0.9,
            )
        ]

        with patch("app.api.search.RetrievalService") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            mock_instance.search = AsyncMock(return_value=mock_results)

            response = await client.post(
                "/api/v1/search",
                json={"query": "test", "document_ids": [str(doc_id)]},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["document_id"] == str(doc_id)

    async def test_search_keyword_only(self, client: AsyncClient):
        """Test search with only keyword search enabled."""
        mock_results = [
            MockRetrievalResult(
                chunk_id=uuid4(),
                document_id=uuid4(),
                document_name="keyword.pdf",
                content="Keyword search content",
                page_numbers=[1],
                score=0.8,
            )
        ]

        with patch("app.api.search.RetrievalService") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            mock_instance.search = AsyncMock(return_value=mock_results)

            response = await client.post(
                "/api/v1/search",
                json={
                    "query": "keyword",
                    "use_keyword": True,
                    "use_vector": False,
                },
            )

        assert response.status_code == 200

    async def test_search_vector_only(self, client: AsyncClient):
        """Test search with only vector search enabled."""
        mock_results = [
            MockRetrievalResult(
                chunk_id=uuid4(),
                document_id=uuid4(),
                document_name="vector.pdf",
                content="Vector search content",
                page_numbers=[1],
                score=0.85,
            )
        ]

        with patch("app.api.search.RetrievalService") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            mock_instance.search = AsyncMock(return_value=mock_results)

            response = await client.post(
                "/api/v1/search",
                json={
                    "query": "semantic meaning",
                    "use_keyword": False,
                    "use_vector": True,
                },
            )

        assert response.status_code == 200

    async def test_search_empty_query_rejected(self, client: AsyncClient):
        """Test that empty query is rejected."""
        response = await client.post(
            "/api/v1/search",
            json={"query": ""},
        )

        assert response.status_code == 422

    async def test_search_top_k_validation(self, client: AsyncClient):
        """Test that top_k validation works."""
        # top_k too large
        response = await client.post(
            "/api/v1/search",
            json={"query": "test", "top_k": 200},
        )

        assert response.status_code == 422

    @pytest.mark.skip(reason="Auth is bypassed in dev_mode=True; requires production mode testing")
    async def test_search_requires_auth(self, unauthenticated_client: AsyncClient):
        """Test that search requires authentication."""
        response = await unauthenticated_client.post(
            "/api/v1/search",
            json={"query": "test"},
        )

        assert response.status_code == 401


class TestSearchResponseSchema:
    """Test search response schema validation."""

    async def test_search_result_has_required_fields(self, client: AsyncClient):
        """Test that search results have all required fields."""
        mock_results = [
            MockRetrievalResult(
                chunk_id=uuid4(),
                document_id=uuid4(),
                document_name="schema_test.pdf",
                content="Schema validation content",
                page_numbers=[1, 2, 3],
                score=0.92,
            )
        ]

        with patch("app.api.search.RetrievalService") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            mock_instance.search = AsyncMock(return_value=mock_results)

            response = await client.post(
                "/api/v1/search",
                json={"query": "test"},
            )

        assert response.status_code == 200
        data = response.json()
        result = data["results"][0]

        # Check all required fields
        assert "chunk_id" in result
        assert "document_id" in result
        assert "document_name" in result
        assert "content" in result
        assert "page_numbers" in result
        assert "score" in result

    async def test_search_result_types(self, client: AsyncClient):
        """Test that search result fields have correct types."""
        chunk_id = uuid4()
        doc_id = uuid4()
        mock_results = [
            MockRetrievalResult(
                chunk_id=chunk_id,
                document_id=doc_id,
                document_name="types.pdf",
                content="Type testing",
                page_numbers=[1],
                score=0.5,
            )
        ]

        with patch("app.api.search.RetrievalService") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            mock_instance.search = AsyncMock(return_value=mock_results)

            response = await client.post(
                "/api/v1/search",
                json={"query": "test"},
            )

        assert response.status_code == 200
        result = response.json()["results"][0]

        # Verify types
        assert isinstance(result["chunk_id"], str)
        assert isinstance(result["document_id"], str)
        assert isinstance(result["document_name"], str)
        assert isinstance(result["content"], str)
        assert isinstance(result["page_numbers"], list)
        assert isinstance(result["score"], float)

    async def test_search_result_null_page_numbers(self, client: AsyncClient):
        """Test that null page_numbers is handled correctly."""
        mock_results = [
            MockRetrievalResult(
                chunk_id=uuid4(),
                document_id=uuid4(),
                document_name="null_pages.pdf",
                content="Content without page numbers",
                page_numbers=None,
                score=0.7,
            )
        ]

        with patch("app.api.search.RetrievalService") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            mock_instance.search = AsyncMock(return_value=mock_results)

            response = await client.post(
                "/api/v1/search",
                json={"query": "test"},
            )

        assert response.status_code == 200
        result = response.json()["results"][0]
        assert result["page_numbers"] is None
