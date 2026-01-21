"""Tests for chat API endpoints."""

from uuid import UUID, uuid4
from unittest.mock import patch, MagicMock

import pytest
from httpx import AsyncClient

from tests.conftest import TEST_USER_ID

# Note: Authentication tests are skipped because dev_mode=True bypasses auth


async def create_test_thread(client: AsyncClient, name: str = "Test Thread") -> dict:
    """Helper to create a test thread via the API."""
    response = await client.post(
        "/api/v1/chat/threads",
        json={"name": name},
    )
    assert response.status_code == 201
    return response.json()


class TestCreateThread:
    """Test create thread endpoint."""

    async def test_create_thread_success(self, client: AsyncClient):
        """Test creating a new thread."""
        response = await client.post(
            "/api/v1/chat/threads",
            json={"name": "Test Thread"},
        )

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["name"] == "Test Thread"
        assert "created_at" in data
        assert "updated_at" in data

    async def test_create_thread_default_name(self, client: AsyncClient):
        """Test creating a thread with default name."""
        response = await client.post(
            "/api/v1/chat/threads",
            json={},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Conversation"

    async def test_create_thread_null_name(self, client: AsyncClient):
        """Test creating a thread with null name uses default."""
        response = await client.post(
            "/api/v1/chat/threads",
            json={"name": None},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Conversation"

    @pytest.mark.skip(reason="Auth is bypassed in dev_mode=True; requires production mode testing")
    async def test_create_thread_requires_auth(self, unauthenticated_client: AsyncClient):
        """Test that creating a thread requires authentication."""
        response = await unauthenticated_client.post(
            "/api/v1/chat/threads",
            json={"name": "Test Thread"},
        )

        assert response.status_code == 401


class TestListThreads:
    """Test list threads endpoint."""

    async def test_list_threads_empty(self, client: AsyncClient):
        """Test listing threads when none exist."""
        response = await client.get("/api/v1/chat/threads")

        assert response.status_code == 200
        data = response.json()
        assert "threads" in data
        assert "total" in data
        assert data["threads"] == []
        assert data["total"] == 0

    async def test_list_threads_with_data(self, client: AsyncClient):
        """Test listing threads when threads exist."""
        # Create thread via API
        await create_test_thread(client, "Existing Thread")

        response = await client.get("/api/v1/chat/threads")

        assert response.status_code == 200
        data = response.json()
        assert len(data["threads"]) >= 1
        thread_names = [t["name"] for t in data["threads"]]
        assert "Existing Thread" in thread_names

    async def test_list_threads_pagination(self, client: AsyncClient):
        """Test pagination for thread list."""
        # Create multiple threads via API
        for i in range(5):
            await create_test_thread(client, f"Thread {i}")

        # Get first 2 threads
        response = await client.get("/api/v1/chat/threads?limit=2&offset=0")

        assert response.status_code == 200
        data = response.json()
        assert len(data["threads"]) == 2
        assert data["total"] >= 5

    @pytest.mark.skip(reason="Auth is bypassed in dev_mode=True; requires production mode testing")
    async def test_list_threads_requires_auth(self, unauthenticated_client: AsyncClient):
        """Test that listing threads requires authentication."""
        response = await unauthenticated_client.get("/api/v1/chat/threads")

        assert response.status_code == 401


class TestGetThread:
    """Test get thread endpoint."""

    async def test_get_thread_success(self, client: AsyncClient):
        """Test getting a thread that exists."""
        thread = await create_test_thread(client, "Get Thread Test")
        thread_id = thread["id"]

        response = await client.get(f"/api/v1/chat/threads/{thread_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == thread_id
        assert data["name"] == "Get Thread Test"
        assert "messages" in data
        assert isinstance(data["messages"], list)

    async def test_get_thread_not_found(self, client: AsyncClient):
        """Test getting a thread that does not exist."""
        fake_id = str(uuid4())
        response = await client.get(f"/api/v1/chat/threads/{fake_id}")

        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["code"] == "NOT_FOUND"

    @pytest.mark.skip(reason="Auth is bypassed in dev_mode=True; requires production mode testing")
    async def test_get_thread_requires_auth(self, unauthenticated_client: AsyncClient):
        """Test that getting a thread requires authentication."""
        fake_id = str(uuid4())
        response = await unauthenticated_client.get(f"/api/v1/chat/threads/{fake_id}")

        assert response.status_code == 401


class TestDeleteThread:
    """Test delete thread endpoint."""

    async def test_delete_thread_success(self, client: AsyncClient):
        """Test deleting a thread successfully."""
        thread = await create_test_thread(client, "To Delete")
        thread_id = thread["id"]

        response = await client.delete(f"/api/v1/chat/threads/{thread_id}")

        assert response.status_code == 204

        # Verify thread was deleted
        get_response = await client.get(f"/api/v1/chat/threads/{thread_id}")
        assert get_response.status_code == 404

    async def test_delete_thread_not_found(self, client: AsyncClient):
        """Test deleting a thread that does not exist."""
        fake_id = str(uuid4())
        response = await client.delete(f"/api/v1/chat/threads/{fake_id}")

        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["code"] == "NOT_FOUND"

    @pytest.mark.skip(reason="Auth is bypassed in dev_mode=True; requires production mode testing")
    async def test_delete_thread_requires_auth(self, unauthenticated_client: AsyncClient):
        """Test that deleting a thread requires authentication."""
        fake_id = str(uuid4())
        response = await unauthenticated_client.delete(f"/api/v1/chat/threads/{fake_id}")

        assert response.status_code == 401


class TestSendMessage:
    """Test send message endpoint."""

    async def test_send_message_returns_stream(self, client: AsyncClient):
        """Test that sending a message returns a streaming response."""
        # Create a thread first via API
        thread = await create_test_thread(client, "Message Test Thread")
        thread_id = thread["id"]

        # Mock the chat service
        async def mock_stream():
            yield {"event": "status", "data": {"stage": "searching"}}
            yield {"event": "status", "data": {"stage": "generating"}}
            yield {"event": "token", "data": {"content": "Hello"}}
            yield {"event": "token", "data": {"content": " World"}}
            yield {"event": "done", "data": {"message_id": str(uuid4()), "is_from_documents": False, "content": "Hello World"}}

        with patch("app.api.chat.ChatService") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            mock_instance.send_message_stream.return_value = mock_stream()

            response = await client.post(
                f"/api/v1/chat/threads/{thread_id}/messages",
                json={"content": "Hello"},
            )

        assert response.status_code == 200
        assert response.headers.get("content-type") == "text/event-stream; charset=utf-8"

    @pytest.mark.skip(reason="Auth is bypassed in dev_mode=True; requires production mode testing")
    async def test_send_message_requires_auth(self, unauthenticated_client: AsyncClient):
        """Test that sending a message requires authentication."""
        fake_id = str(uuid4())
        response = await unauthenticated_client.post(
            f"/api/v1/chat/threads/{fake_id}/messages",
            json={"content": "Hello"},
        )

        assert response.status_code == 401

    async def test_send_message_with_model(self, client: AsyncClient):
        """Test sending a message with a specific model."""
        thread = await create_test_thread(client, "Model Test Thread")
        thread_id = thread["id"]

        async def mock_stream():
            yield {"event": "status", "data": {"stage": "generating"}}
            yield {"event": "done", "data": {"message_id": str(uuid4()), "is_from_documents": False, "content": "Response"}}

        with patch("app.api.chat.ChatService") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            mock_instance.send_message_stream.return_value = mock_stream()

            response = await client.post(
                f"/api/v1/chat/threads/{thread_id}/messages",
                json={"content": "Hello", "model": "gpt-4"},
            )

        assert response.status_code == 200
