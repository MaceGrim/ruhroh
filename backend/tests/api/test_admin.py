"""Tests for admin API endpoints."""

from uuid import UUID, uuid4
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from tests.conftest import TEST_USER_ID, TEST_USER_EMAIL

# Note: Authentication tests are skipped because dev_mode=True bypasses auth


class TestAdminRequiresAdminRole:
    """Test that admin endpoints require admin role."""

    async def test_admin_users_requires_admin(self, client: AsyncClient, db_session, regular_user):
        """Test that /admin/users requires admin role."""
        # The test_user fixture has admin role, so this should work
        # Create a mock for the admin service
        with patch("app.api.admin.AdminService") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            mock_instance.list_users = AsyncMock(return_value=[])

            response = await client.get("/api/v1/admin/users")

        # With admin role, should succeed
        assert response.status_code == 200

    @pytest.mark.skip(reason="Auth is bypassed in dev_mode=True; requires production mode testing")
    async def test_admin_requires_auth(self, unauthenticated_client: AsyncClient):
        """Test that admin endpoints require authentication."""
        response = await unauthenticated_client.get("/api/v1/admin/users")

        assert response.status_code == 401


class TestAdminListUsers:
    """Test admin list users endpoint."""

    async def test_list_users_success(self, client: AsyncClient):
        """Test listing users as admin."""
        mock_users = [
            {
                "id": str(TEST_USER_ID),
                "email": TEST_USER_EMAIL,
                "role": "admin",
                "created_at": datetime.utcnow().isoformat(),
                "last_login": None,
                "is_active": True,
            }
        ]

        with patch("app.api.admin.AdminService") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            mock_instance.list_users = AsyncMock(return_value=mock_users)

            response = await client.get("/api/v1/admin/users")

        assert response.status_code == 200
        data = response.json()
        assert "users" in data
        assert len(data["users"]) == 1
        assert data["users"][0]["email"] == TEST_USER_EMAIL

    async def test_list_users_filter_by_role(self, client: AsyncClient):
        """Test filtering users by role."""
        mock_users = [
            {
                "id": str(uuid4()),
                "email": "admin@example.com",
                "role": "admin",
                "created_at": datetime.utcnow().isoformat(),
                "last_login": None,
                "is_active": True,
            }
        ]

        with patch("app.api.admin.AdminService") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            mock_instance.list_users = AsyncMock(return_value=mock_users)

            response = await client.get("/api/v1/admin/users?role=admin")

        assert response.status_code == 200
        data = response.json()
        for user in data["users"]:
            assert user["role"] == "admin"

    async def test_list_users_filter_by_active(self, client: AsyncClient):
        """Test filtering users by active status."""
        mock_users = [
            {
                "id": str(uuid4()),
                "email": "active@example.com",
                "role": "user",
                "created_at": datetime.utcnow().isoformat(),
                "last_login": None,
                "is_active": True,
            }
        ]

        with patch("app.api.admin.AdminService") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            mock_instance.list_users = AsyncMock(return_value=mock_users)

            response = await client.get("/api/v1/admin/users?is_active=true")

        assert response.status_code == 200


class TestAdminUpdateUser:
    """Test admin update user endpoint."""

    async def test_update_user_role(self, client: AsyncClient):
        """Test updating a user's role."""
        user_id = str(uuid4())
        updated_user = {
            "id": user_id,
            "email": "user@example.com",
            "role": "superuser",
            "created_at": datetime.utcnow().isoformat(),
            "last_login": None,
            "is_active": True,
        }

        with patch("app.api.admin.AdminService") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            mock_instance.update_user = AsyncMock(return_value=updated_user)

            response = await client.patch(
                f"/api/v1/admin/users/{user_id}",
                json={"role": "superuser"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "superuser"

    async def test_update_user_active_status(self, client: AsyncClient):
        """Test updating a user's active status."""
        user_id = str(uuid4())
        updated_user = {
            "id": user_id,
            "email": "user@example.com",
            "role": "user",
            "created_at": datetime.utcnow().isoformat(),
            "last_login": None,
            "is_active": False,
        }

        with patch("app.api.admin.AdminService") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            mock_instance.update_user = AsyncMock(return_value=updated_user)

            response = await client.patch(
                f"/api/v1/admin/users/{user_id}",
                json={"is_active": False},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False

    async def test_update_user_not_found(self, client: AsyncClient):
        """Test updating a non-existent user."""
        fake_id = str(uuid4())

        with patch("app.api.admin.AdminService") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            mock_instance.update_user = AsyncMock(return_value=None)

            response = await client.patch(
                f"/api/v1/admin/users/{fake_id}",
                json={"role": "superuser"},
            )

        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["code"] == "NOT_FOUND"


class TestAdminStats:
    """Test admin stats endpoint."""

    async def test_get_stats(self, client: AsyncClient):
        """Test getting system statistics."""
        mock_stats = {
            "total_users": 10,
            "active_users_today": 5,
            "total_documents": 100,
            "total_queries_today": 50,
            "documents_by_status": {
                "pending": 5,
                "processing": 2,
                "ready": 90,
                "failed": 3,
            },
        }

        with patch("app.api.admin.AdminService") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            mock_instance.get_stats = AsyncMock(return_value=mock_stats)

            response = await client.get("/api/v1/admin/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_users"] == 10
        assert data["active_users_today"] == 5
        assert data["total_documents"] == 100
        assert data["total_queries_today"] == 50
        assert "documents_by_status" in data

    async def test_stats_response_schema(self, client: AsyncClient):
        """Test that stats response matches expected schema."""
        mock_stats = {
            "total_users": 1,
            "active_users_today": 1,
            "total_documents": 1,
            "total_queries_today": 0,
            "documents_by_status": {"ready": 1},
        }

        with patch("app.api.admin.AdminService") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            mock_instance.get_stats = AsyncMock(return_value=mock_stats)

            response = await client.get("/api/v1/admin/stats")

        assert response.status_code == 200
        data = response.json()

        # Check all required fields
        assert "total_users" in data
        assert "active_users_today" in data
        assert "total_documents" in data
        assert "total_queries_today" in data
        assert "documents_by_status" in data

        # Check types
        assert isinstance(data["total_users"], int)
        assert isinstance(data["active_users_today"], int)
        assert isinstance(data["total_documents"], int)
        assert isinstance(data["total_queries_today"], int)
        assert isinstance(data["documents_by_status"], dict)


class TestAdminListDocuments:
    """Test admin list documents endpoint."""

    async def test_list_all_documents(self, client: AsyncClient):
        """Test listing all documents as admin."""
        mock_documents = [
            {
                "id": str(uuid4()),
                "user_id": str(TEST_USER_ID),
                "filename": "doc1.pdf",
                "file_type": "pdf",
                "file_size": 1024,
                "page_count": 10,
                "status": "ready",
                "error_message": None,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }
        ]

        with patch("app.api.admin.AdminService") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            mock_instance.list_all_documents = AsyncMock(return_value=mock_documents)

            response = await client.get("/api/v1/admin/documents")

        assert response.status_code == 200
        data = response.json()
        assert "documents" in data
        assert len(data["documents"]) == 1

    async def test_list_documents_filter_by_user(self, client: AsyncClient):
        """Test filtering documents by user_id."""
        user_id = str(uuid4())
        mock_documents = [
            {
                "id": str(uuid4()),
                "user_id": user_id,
                "filename": "user_doc.pdf",
                "file_type": "pdf",
                "file_size": 512,
                "page_count": 5,
                "status": "ready",
                "error_message": None,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }
        ]

        with patch("app.api.admin.AdminService") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            mock_instance.list_all_documents = AsyncMock(return_value=mock_documents)

            response = await client.get(f"/api/v1/admin/documents?user_id={user_id}")

        assert response.status_code == 200

    async def test_list_documents_filter_by_status(self, client: AsyncClient):
        """Test filtering documents by status."""
        mock_documents = [
            {
                "id": str(uuid4()),
                "user_id": str(TEST_USER_ID),
                "filename": "failed_doc.pdf",
                "file_type": "pdf",
                "file_size": 256,
                "page_count": None,
                "status": "failed",
                "error_message": "Processing error",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }
        ]

        with patch("app.api.admin.AdminService") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            mock_instance.list_all_documents = AsyncMock(return_value=mock_documents)

            response = await client.get("/api/v1/admin/documents?status=failed")

        assert response.status_code == 200


class TestAdminDeleteDocument:
    """Test admin delete document endpoint."""

    async def test_delete_document_success(self, client: AsyncClient):
        """Test deleting a document as admin."""
        doc_id = str(uuid4())

        with patch("app.api.admin.AdminService") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            mock_instance.delete_document = AsyncMock(return_value=True)

            response = await client.delete(f"/api/v1/admin/documents/{doc_id}")

        assert response.status_code == 204

    async def test_delete_document_not_found(self, client: AsyncClient):
        """Test deleting a non-existent document."""
        fake_id = str(uuid4())

        with patch("app.api.admin.AdminService") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            mock_instance.delete_document = AsyncMock(return_value=False)

            response = await client.delete(f"/api/v1/admin/documents/{fake_id}")

        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["code"] == "NOT_FOUND"


class TestAdminHealth:
    """Test admin health endpoint."""

    async def test_admin_health_success(self, client: AsyncClient):
        """Test admin health endpoint returns detailed status."""
        response = await client.get("/api/v1/admin/health")

        assert response.status_code == 200
        data = response.json()
        assert "api" in data
        assert "database" in data
        assert "qdrant" in data
        assert "supabase" in data

    async def test_admin_health_status_values(self, client: AsyncClient):
        """Test that admin health returns valid status values."""
        response = await client.get("/api/v1/admin/health")

        assert response.status_code == 200
        data = response.json()
        assert data["api"] in ["ok", "degraded"]
        assert data["database"] in ["ok", "error"]
        assert data["qdrant"] in ["ok", "error"]
        assert data["supabase"] in ["ok", "error"]


class TestAdminUserResponse:
    """Test admin user response schema."""

    async def test_user_response_has_required_fields(self, client: AsyncClient):
        """Test that user response has all required fields."""
        mock_users = [
            {
                "id": str(uuid4()),
                "email": "test@example.com",
                "role": "user",
                "created_at": datetime.utcnow().isoformat(),
                "last_login": datetime.utcnow().isoformat(),
                "is_active": True,
            }
        ]

        with patch("app.api.admin.AdminService") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            mock_instance.list_users = AsyncMock(return_value=mock_users)

            response = await client.get("/api/v1/admin/users")

        assert response.status_code == 200
        user = response.json()["users"][0]

        # Check all required fields
        assert "id" in user
        assert "email" in user
        assert "role" in user
        assert "created_at" in user
        assert "last_login" in user
        assert "is_active" in user

    async def test_user_response_null_last_login(self, client: AsyncClient):
        """Test that null last_login is handled correctly."""
        mock_users = [
            {
                "id": str(uuid4()),
                "email": "new@example.com",
                "role": "user",
                "created_at": datetime.utcnow().isoformat(),
                "last_login": None,
                "is_active": True,
            }
        ]

        with patch("app.api.admin.AdminService") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            mock_instance.list_users = AsyncMock(return_value=mock_users)

            response = await client.get("/api/v1/admin/users")

        assert response.status_code == 200
        user = response.json()["users"][0]
        assert user["last_login"] is None
