"""Tests for health check endpoint and basic infrastructure."""

import pytest
from httpx import AsyncClient


class TestHealthCheck:
    """Test health check endpoint."""

    async def test_health_endpoint_returns_ok(self, client: AsyncClient):
        """Test that health endpoint returns 200 with status info."""
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()

        # Should have status field
        assert "status" in data
        # With mocked services, status should be ok or degraded
        assert data["status"] in ["ok", "degraded"]


class TestDatabaseFixtures:
    """Test that database fixtures work correctly."""

    async def test_db_session_fixture(self, db_session):
        """Test that db_session fixture provides a working session."""
        from sqlalchemy import text

        result = await db_session.execute(text("SELECT 1"))
        value = result.scalar()
        assert value == 1

    async def test_test_user_fixture(self, test_user):
        """Test that test_user fixture creates a user."""
        from tests.conftest import TEST_USER_ID, TEST_USER_EMAIL

        assert test_user.id == TEST_USER_ID
        assert test_user.email == TEST_USER_EMAIL
        assert test_user.role == "admin"
        assert test_user.is_active is True

    async def test_regular_user_fixture(self, regular_user):
        """Test that regular_user fixture creates a non-admin user."""
        assert regular_user.role == "user"
        assert regular_user.is_active is True

    async def test_inactive_user_fixture(self, inactive_user):
        """Test that inactive_user fixture creates an inactive user."""
        assert inactive_user.is_active is False


class TestMockServices:
    """Test that mock service fixtures work correctly."""

    async def test_mock_llm_service(self, mock_llm_service):
        """Test that mock LLM service returns expected values."""
        # Test embeddings
        embeddings = await mock_llm_service.generate_embeddings(["test"])
        assert len(embeddings) == 1
        assert len(embeddings[0]) == 1536

        # Test chat completion
        response = await mock_llm_service.chat_completion([{"role": "user", "content": "test"}])
        assert isinstance(response, str)

    async def test_mock_auth_service(self, mock_auth_service):
        """Test that mock auth service returns expected values."""
        from tests.conftest import TEST_USER_ID

        user_id = await mock_auth_service.verify_token("test-token")
        assert user_id == TEST_USER_ID

    async def test_mock_qdrant_client(self, mock_qdrant_client):
        """Test that mock Qdrant client has expected methods."""
        # Should have collection methods
        assert hasattr(mock_qdrant_client, "get_collections")
        assert hasattr(mock_qdrant_client, "create_collection")
        assert hasattr(mock_qdrant_client, "upsert")
        assert hasattr(mock_qdrant_client, "query_points")
        assert hasattr(mock_qdrant_client, "delete")


class TestClientFixtures:
    """Test that HTTP client fixtures work correctly."""

    async def test_authenticated_client(self, client: AsyncClient):
        """Test that client fixture has auth headers."""
        # The client should have Authorization header set
        assert "Authorization" in client.headers

    async def test_client_can_make_requests(self, client: AsyncClient):
        """Test that client can make HTTP requests to the app."""
        response = await client.get("/health")
        assert response.status_code in [200, 503]  # Health check should respond


class TestSettingsFixture:
    """Test that settings fixture works correctly."""

    def test_test_settings_values(self, test_settings):
        """Test that test_settings has expected values."""
        assert test_settings.dev_mode is True
        assert test_settings.debug is True
        assert "sqlite" in test_settings.database_url
        assert test_settings.qdrant_collection_name == "test_documents"
