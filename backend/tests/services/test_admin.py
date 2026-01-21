"""Tests for the admin service."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.config import Settings
from app.db.models import User, Document, AuditLog
from app.services.admin import AdminService


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
        dev_mode=True,
    )


@pytest.fixture
def mock_session():
    """Create mock database session."""
    return AsyncMock()


@pytest.fixture
def admin_service(test_settings, mock_session):
    """Create admin service with mocked dependencies."""
    return AdminService(settings=test_settings, session=mock_session)


@pytest.fixture
def sample_user_id():
    """Sample user UUID."""
    return UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture
def sample_user(sample_user_id):
    """Create sample user object."""
    user = MagicMock(spec=User)
    user.id = sample_user_id
    user.email = "test@example.com"
    user.role = "user"
    user.created_at = datetime.utcnow()
    user.last_login = datetime.utcnow()
    user.is_active = True
    return user


@pytest.fixture
def sample_admin_user():
    """Create sample admin user object."""
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.email = "admin@example.com"
    user.role = "admin"
    user.created_at = datetime.utcnow()
    user.last_login = datetime.utcnow()
    user.is_active = True
    return user


@pytest.fixture
def sample_document_id():
    """Sample document UUID."""
    return UUID("00000000-0000-0000-0000-000000000002")


@pytest.fixture
def sample_document(sample_document_id, sample_user_id):
    """Create sample document object."""
    doc = MagicMock(spec=Document)
    doc.id = sample_document_id
    doc.user_id = sample_user_id
    doc.filename = "test_document.pdf"
    doc.file_type = "pdf"
    doc.file_size = 1024
    doc.page_count = 10
    doc.status = "ready"
    doc.error_message = None
    doc.created_at = datetime.utcnow()
    doc.updated_at = datetime.utcnow()
    return doc


# =============================================================================
# Test: get_stats
# =============================================================================


class TestGetStats:
    """Tests for get_stats method."""

    @pytest.mark.asyncio
    async def test_get_stats_all_zeros(self, admin_service):
        """Test getting stats when everything is zero."""
        admin_service.user_repo.count = AsyncMock(return_value=0)
        admin_service.audit_repo.count_active_users_today = AsyncMock(return_value=0)
        admin_service.doc_repo.count_by_status = AsyncMock(return_value={})
        admin_service.audit_repo.count_queries_today = AsyncMock(return_value=0)

        stats = await admin_service.get_stats()

        assert stats["total_users"] == 0
        assert stats["active_users_today"] == 0
        assert stats["total_documents"] == 0
        assert stats["total_queries_today"] == 0
        assert stats["documents_by_status"] == {}

    @pytest.mark.asyncio
    async def test_get_stats_with_data(self, admin_service):
        """Test getting stats with actual data."""
        admin_service.user_repo.count = AsyncMock(return_value=100)
        admin_service.audit_repo.count_active_users_today = AsyncMock(return_value=25)
        admin_service.doc_repo.count_by_status = AsyncMock(
            return_value={
                "ready": 50,
                "processing": 5,
                "pending": 10,
                "failed": 2,
            }
        )
        admin_service.audit_repo.count_queries_today = AsyncMock(return_value=150)

        stats = await admin_service.get_stats()

        assert stats["total_users"] == 100
        assert stats["active_users_today"] == 25
        assert stats["total_documents"] == 67  # Sum of all statuses
        assert stats["total_queries_today"] == 150
        assert stats["documents_by_status"]["ready"] == 50

    @pytest.mark.asyncio
    async def test_get_stats_calculates_total_documents(self, admin_service):
        """Test that total_documents is sum of all statuses."""
        admin_service.user_repo.count = AsyncMock(return_value=10)
        admin_service.audit_repo.count_active_users_today = AsyncMock(return_value=5)
        admin_service.doc_repo.count_by_status = AsyncMock(
            return_value={"ready": 10, "pending": 5}
        )
        admin_service.audit_repo.count_queries_today = AsyncMock(return_value=0)

        stats = await admin_service.get_stats()

        assert stats["total_documents"] == 15


# =============================================================================
# Test: list_users
# =============================================================================


class TestListUsers:
    """Tests for list_users method."""

    @pytest.mark.asyncio
    async def test_list_users_empty(self, admin_service):
        """Test listing users when none exist."""
        admin_service.user_repo.list_all = AsyncMock(return_value=[])

        users = await admin_service.list_users()

        assert users == []
        admin_service.user_repo.list_all.assert_awaited_once_with(
            role=None, is_active=None
        )

    @pytest.mark.asyncio
    async def test_list_users_with_results(self, admin_service, sample_user):
        """Test listing users with results."""
        admin_service.user_repo.list_all = AsyncMock(return_value=[sample_user])

        users = await admin_service.list_users()

        assert len(users) == 1
        assert users[0]["email"] == sample_user.email
        assert users[0]["role"] == sample_user.role

    @pytest.mark.asyncio
    async def test_list_users_filter_by_role(self, admin_service, sample_admin_user):
        """Test listing users filtered by role."""
        admin_service.user_repo.list_all = AsyncMock(return_value=[sample_admin_user])

        users = await admin_service.list_users(role="admin")

        admin_service.user_repo.list_all.assert_awaited_once_with(
            role="admin", is_active=None
        )
        assert len(users) == 1
        assert users[0]["role"] == "admin"

    @pytest.mark.asyncio
    async def test_list_users_filter_by_active(self, admin_service, sample_user):
        """Test listing users filtered by active status."""
        admin_service.user_repo.list_all = AsyncMock(return_value=[sample_user])

        users = await admin_service.list_users(is_active=True)

        admin_service.user_repo.list_all.assert_awaited_once_with(
            role=None, is_active=True
        )

    @pytest.mark.asyncio
    async def test_list_users_filter_combined(self, admin_service, sample_admin_user):
        """Test listing users with combined filters."""
        admin_service.user_repo.list_all = AsyncMock(return_value=[sample_admin_user])

        users = await admin_service.list_users(role="admin", is_active=True)

        admin_service.user_repo.list_all.assert_awaited_once_with(
            role="admin", is_active=True
        )

    @pytest.mark.asyncio
    async def test_list_users_formats_dates(self, admin_service, sample_user):
        """Test that dates are properly formatted as ISO strings."""
        admin_service.user_repo.list_all = AsyncMock(return_value=[sample_user])

        users = await admin_service.list_users()

        # Check that dates are ISO formatted strings
        assert isinstance(users[0]["created_at"], str)

    @pytest.mark.asyncio
    async def test_list_users_handles_null_last_login(self, admin_service, sample_user):
        """Test handling of null last_login."""
        sample_user.last_login = None
        admin_service.user_repo.list_all = AsyncMock(return_value=[sample_user])

        users = await admin_service.list_users()

        assert users[0]["last_login"] is None


# =============================================================================
# Test: update_user
# =============================================================================


class TestUpdateUser:
    """Tests for update_user method."""

    @pytest.mark.asyncio
    async def test_update_user_not_found(self, admin_service, sample_user_id):
        """Test updating a non-existent user."""
        admin_service.user_repo.get_by_id = AsyncMock(return_value=None)
        admin_service.user_repo.update_role = AsyncMock()

        result = await admin_service.update_user(sample_user_id, role="admin")

        assert result is None
        admin_service.user_repo.update_role.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_update_user_role(self, admin_service, sample_user_id, sample_user):
        """Test updating user role."""
        sample_user.role = "admin"
        admin_service.user_repo.get_by_id = AsyncMock(return_value=sample_user)
        admin_service.user_repo.update_role = AsyncMock(return_value=sample_user)

        result = await admin_service.update_user(sample_user_id, role="admin")

        assert result is not None
        assert result["role"] == "admin"
        admin_service.user_repo.update_role.assert_awaited_once_with(
            sample_user_id, "admin"
        )

    @pytest.mark.asyncio
    async def test_update_user_active_status(
        self, admin_service, sample_user_id, sample_user
    ):
        """Test updating user active status."""
        sample_user.is_active = False
        admin_service.user_repo.get_by_id = AsyncMock(return_value=sample_user)
        admin_service.user_repo.set_active = AsyncMock(return_value=sample_user)

        result = await admin_service.update_user(sample_user_id, is_active=False)

        assert result is not None
        assert result["is_active"] is False
        admin_service.user_repo.set_active.assert_awaited_once_with(
            sample_user_id, False
        )

    @pytest.mark.asyncio
    async def test_update_user_both_fields(
        self, admin_service, sample_user_id, sample_user
    ):
        """Test updating both role and active status."""
        sample_user.role = "admin"
        sample_user.is_active = False
        admin_service.user_repo.get_by_id = AsyncMock(return_value=sample_user)
        admin_service.user_repo.update_role = AsyncMock(return_value=sample_user)
        admin_service.user_repo.set_active = AsyncMock(return_value=sample_user)

        result = await admin_service.update_user(
            sample_user_id, role="admin", is_active=False
        )

        assert result is not None
        admin_service.user_repo.update_role.assert_awaited_once()
        admin_service.user_repo.set_active.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_user_no_changes(
        self, admin_service, sample_user_id, sample_user
    ):
        """Test calling update_user with no actual changes."""
        admin_service.user_repo.get_by_id = AsyncMock(return_value=sample_user)
        admin_service.user_repo.update_role = AsyncMock()
        admin_service.user_repo.set_active = AsyncMock()

        result = await admin_service.update_user(sample_user_id)

        assert result is not None
        admin_service.user_repo.update_role.assert_not_awaited()
        admin_service.user_repo.set_active.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_update_user_role_update_returns_none(
        self, admin_service, sample_user_id, sample_user
    ):
        """Test handling when update_role returns None."""
        admin_service.user_repo.get_by_id = AsyncMock(return_value=sample_user)
        admin_service.user_repo.update_role = AsyncMock(return_value=None)

        result = await admin_service.update_user(sample_user_id, role="admin")

        assert result is None


# =============================================================================
# Test: list_all_documents
# =============================================================================


class TestListAllDocuments:
    """Tests for list_all_documents method."""

    @pytest.mark.asyncio
    async def test_list_all_documents_empty(self, admin_service):
        """Test listing documents when none exist."""
        admin_service.doc_repo.list_all = AsyncMock(return_value=[])

        documents = await admin_service.list_all_documents()

        assert documents == []
        admin_service.doc_repo.list_all.assert_awaited_once_with(
            user_id=None, status=None
        )

    @pytest.mark.asyncio
    async def test_list_all_documents_with_results(
        self, admin_service, sample_document
    ):
        """Test listing documents with results."""
        admin_service.doc_repo.list_all = AsyncMock(return_value=[sample_document])

        documents = await admin_service.list_all_documents()

        assert len(documents) == 1
        assert documents[0]["filename"] == sample_document.filename
        assert documents[0]["status"] == sample_document.status

    @pytest.mark.asyncio
    async def test_list_all_documents_filter_by_user(
        self, admin_service, sample_user_id, sample_document
    ):
        """Test listing documents filtered by user."""
        admin_service.doc_repo.list_all = AsyncMock(return_value=[sample_document])

        documents = await admin_service.list_all_documents(user_id=sample_user_id)

        admin_service.doc_repo.list_all.assert_awaited_once_with(
            user_id=sample_user_id, status=None
        )

    @pytest.mark.asyncio
    async def test_list_all_documents_filter_by_status(
        self, admin_service, sample_document
    ):
        """Test listing documents filtered by status."""
        admin_service.doc_repo.list_all = AsyncMock(return_value=[sample_document])

        documents = await admin_service.list_all_documents(status="ready")

        admin_service.doc_repo.list_all.assert_awaited_once_with(
            user_id=None, status="ready"
        )

    @pytest.mark.asyncio
    async def test_list_all_documents_combined_filters(
        self, admin_service, sample_user_id, sample_document
    ):
        """Test listing documents with combined filters."""
        admin_service.doc_repo.list_all = AsyncMock(return_value=[sample_document])

        documents = await admin_service.list_all_documents(
            user_id=sample_user_id, status="ready"
        )

        admin_service.doc_repo.list_all.assert_awaited_once_with(
            user_id=sample_user_id, status="ready"
        )

    @pytest.mark.asyncio
    async def test_list_all_documents_formats_ids(
        self, admin_service, sample_document
    ):
        """Test that UUIDs are formatted as strings."""
        admin_service.doc_repo.list_all = AsyncMock(return_value=[sample_document])

        documents = await admin_service.list_all_documents()

        assert isinstance(documents[0]["id"], str)
        assert isinstance(documents[0]["user_id"], str)


# =============================================================================
# Test: delete_document
# =============================================================================


class TestDeleteDocument:
    """Tests for delete_document method."""

    @pytest.mark.asyncio
    async def test_delete_document_success(self, admin_service, sample_document_id):
        """Test successfully deleting a document."""
        admin_service.doc_repo.delete = AsyncMock(return_value=True)

        result = await admin_service.delete_document(sample_document_id)

        assert result is True
        admin_service.doc_repo.delete.assert_awaited_once_with(sample_document_id)

    @pytest.mark.asyncio
    async def test_delete_document_not_found(self, admin_service, sample_document_id):
        """Test deleting a non-existent document."""
        admin_service.doc_repo.delete = AsyncMock(return_value=False)

        result = await admin_service.delete_document(sample_document_id)

        assert result is False


# =============================================================================
# Test: log_action
# =============================================================================


class TestLogAction:
    """Tests for log_action method."""

    @pytest.mark.asyncio
    async def test_log_action_minimal(self, admin_service):
        """Test logging action with minimal parameters."""
        admin_service.audit_repo.create = AsyncMock()

        await admin_service.log_action(
            action="test_action",
            resource_type="test_resource",
        )

        admin_service.audit_repo.create.assert_awaited_once_with(
            action="test_action",
            resource_type="test_resource",
            user_id=None,
            resource_id=None,
            details=None,
            ip_address=None,
        )

    @pytest.mark.asyncio
    async def test_log_action_full_parameters(
        self, admin_service, sample_user_id, sample_document_id
    ):
        """Test logging action with all parameters."""
        admin_service.audit_repo.create = AsyncMock()

        await admin_service.log_action(
            action="document_deleted",
            resource_type="document",
            user_id=sample_user_id,
            resource_id=sample_document_id,
            details={"reason": "Admin request"},
            ip_address="192.168.1.1",
        )

        admin_service.audit_repo.create.assert_awaited_once_with(
            action="document_deleted",
            resource_type="document",
            user_id=sample_user_id,
            resource_id=sample_document_id,
            details={"reason": "Admin request"},
            ip_address="192.168.1.1",
        )

    @pytest.mark.asyncio
    async def test_log_action_with_user_only(
        self, admin_service, sample_user_id
    ):
        """Test logging action with user ID only."""
        admin_service.audit_repo.create = AsyncMock()

        await admin_service.log_action(
            action="user_login",
            resource_type="user",
            user_id=sample_user_id,
        )

        call_kwargs = admin_service.audit_repo.create.call_args.kwargs
        assert call_kwargs["user_id"] == sample_user_id
        assert call_kwargs["resource_id"] is None

    @pytest.mark.asyncio
    async def test_log_action_with_details(self, admin_service):
        """Test logging action with complex details."""
        admin_service.audit_repo.create = AsyncMock()

        details = {
            "old_status": "pending",
            "new_status": "ready",
            "chunk_count": 50,
        }

        await admin_service.log_action(
            action="document_processed",
            resource_type="document",
            details=details,
        )

        call_kwargs = admin_service.audit_repo.create.call_args.kwargs
        assert call_kwargs["details"] == details


# =============================================================================
# Test: _count_all_documents (private method)
# =============================================================================


class TestCountAllDocuments:
    """Tests for _count_all_documents helper method."""

    @pytest.mark.asyncio
    async def test_count_all_documents_empty(self, admin_service):
        """Test counting when no documents exist."""
        admin_service.doc_repo.count_by_status = AsyncMock(return_value={})

        count = await admin_service._count_all_documents()

        assert count == 0

    @pytest.mark.asyncio
    async def test_count_all_documents_single_status(self, admin_service):
        """Test counting with single status."""
        admin_service.doc_repo.count_by_status = AsyncMock(return_value={"ready": 10})

        count = await admin_service._count_all_documents()

        assert count == 10

    @pytest.mark.asyncio
    async def test_count_all_documents_multiple_statuses(self, admin_service):
        """Test counting with multiple statuses."""
        admin_service.doc_repo.count_by_status = AsyncMock(
            return_value={
                "pending": 5,
                "processing": 3,
                "ready": 20,
                "failed": 2,
            }
        )

        count = await admin_service._count_all_documents()

        assert count == 30
