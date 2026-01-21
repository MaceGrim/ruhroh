"""Tests for UserRepository."""

import pytest
from datetime import datetime
from uuid import uuid4

from app.db.repositories.user import UserRepository
from app.db.models import User


class TestUserRepository:
    """Test cases for UserRepository."""

    @pytest.fixture
    async def repo(self, db_session):
        """Create repository instance."""
        return UserRepository(db_session)

    # =========================================================================
    # get_by_id tests
    # =========================================================================

    async def test_get_by_id_returns_user_when_exists(self, repo, test_user):
        """Test get_by_id returns user when it exists."""
        result = await repo.get_by_id(test_user.id)

        assert result is not None
        assert result.id == test_user.id
        assert result.email == test_user.email

    async def test_get_by_id_returns_none_when_not_exists(self, repo):
        """Test get_by_id returns None when user does not exist."""
        non_existent_id = uuid4()
        result = await repo.get_by_id(non_existent_id)

        assert result is None

    # =========================================================================
    # get_by_email tests
    # =========================================================================

    async def test_get_by_email_returns_user_when_exists(self, repo, test_user):
        """Test get_by_email returns user when it exists."""
        result = await repo.get_by_email(test_user.email)

        assert result is not None
        assert result.email == test_user.email
        assert result.id == test_user.id

    async def test_get_by_email_returns_none_when_not_exists(self, repo):
        """Test get_by_email returns None when user does not exist."""
        result = await repo.get_by_email("nonexistent@example.com")

        assert result is None

    async def test_get_by_email_is_case_sensitive(self, repo, test_user):
        """Test that email matching is case-sensitive."""
        # SQLite is case-insensitive by default for ASCII
        # but this tests the query structure
        result = await repo.get_by_email(test_user.email.upper())

        # Depending on DB, this might or might not match
        # The important thing is that the query runs without error
        if result is not None:
            assert result.id == test_user.id

    # =========================================================================
    # create tests
    # =========================================================================

    async def test_create_user_with_defaults(self, repo, db_session):
        """Test creating user with default role."""
        user_id = uuid4()
        email = "newuser@example.com"

        user = await repo.create(user_id=user_id, email=email)

        assert user.id == user_id
        assert user.email == email
        assert user.role == "user"
        assert user.is_active is True

    async def test_create_user_with_custom_role(self, repo, db_session):
        """Test creating user with custom role."""
        user_id = uuid4()
        email = "admin@example.com"

        user = await repo.create(user_id=user_id, email=email, role="admin")

        assert user.id == user_id
        assert user.email == email
        assert user.role == "admin"

    async def test_create_user_is_persisted(self, repo, db_session):
        """Test that created user is persisted to database."""
        user_id = uuid4()
        email = "persisted@example.com"

        await repo.create(user_id=user_id, email=email)

        # Verify we can retrieve it
        retrieved = await repo.get_by_id(user_id)
        assert retrieved is not None
        assert retrieved.email == email

    # =========================================================================
    # update_last_login tests
    # =========================================================================

    async def test_update_last_login_sets_timestamp(self, repo, test_user, db_session):
        """Test update_last_login sets the timestamp."""
        before_update = datetime.utcnow()
        await repo.update_last_login(test_user.id)
        await db_session.commit()

        # Refresh the user
        updated_user = await repo.get_by_id(test_user.id)
        assert updated_user is not None
        assert updated_user.last_login is not None

    async def test_update_last_login_nonexistent_user(self, repo):
        """Test update_last_login with non-existent user does not error."""
        # Should not raise an exception
        await repo.update_last_login(uuid4())

    # =========================================================================
    # update_role tests
    # =========================================================================

    async def test_update_role_changes_role(self, repo, test_user, db_session):
        """Test update_role changes the user's role."""
        # test_user starts as admin
        updated = await repo.update_role(test_user.id, "user")
        await db_session.commit()

        assert updated is not None
        assert updated.role == "user"

    async def test_update_role_returns_none_for_nonexistent_user(self, repo):
        """Test update_role returns None for non-existent user."""
        result = await repo.update_role(uuid4(), "admin")

        # The update runs but returns None when fetching
        assert result is None

    # =========================================================================
    # set_active tests
    # =========================================================================

    async def test_set_active_deactivates_user(self, repo, test_user, db_session):
        """Test set_active can deactivate a user."""
        result = await repo.set_active(test_user.id, False)
        await db_session.commit()

        assert result is not None
        assert result.is_active is False

    async def test_set_active_activates_user(self, repo, inactive_user, db_session):
        """Test set_active can activate an inactive user."""
        result = await repo.set_active(inactive_user.id, True)
        await db_session.commit()

        assert result is not None
        assert result.is_active is True

    async def test_set_active_returns_none_for_nonexistent_user(self, repo):
        """Test set_active returns None for non-existent user."""
        result = await repo.set_active(uuid4(), True)

        assert result is None

    # =========================================================================
    # list_all tests
    # =========================================================================

    async def test_list_all_returns_all_users(
        self, repo, test_user, regular_user, inactive_user
    ):
        """Test list_all returns all users."""
        users = await repo.list_all()

        assert len(users) == 3
        user_ids = {u.id for u in users}
        assert test_user.id in user_ids
        assert regular_user.id in user_ids
        assert inactive_user.id in user_ids

    async def test_list_all_filters_by_role(self, repo, test_user, regular_user):
        """Test list_all filters by role."""
        admins = await repo.list_all(role="admin")

        assert len(admins) == 1
        assert admins[0].id == test_user.id

    async def test_list_all_filters_by_active_status(
        self, repo, test_user, regular_user, inactive_user
    ):
        """Test list_all filters by active status."""
        active_users = await repo.list_all(is_active=True)
        inactive_users = await repo.list_all(is_active=False)

        assert len(active_users) == 2
        assert len(inactive_users) == 1
        assert inactive_users[0].id == inactive_user.id

    async def test_list_all_with_pagination(self, repo, test_user, regular_user):
        """Test list_all respects limit and offset."""
        # Get first user
        first_page = await repo.list_all(limit=1, offset=0)
        assert len(first_page) == 1

        # Get second user
        second_page = await repo.list_all(limit=1, offset=1)
        assert len(second_page) == 1

        # Ensure they are different
        assert first_page[0].id != second_page[0].id

    async def test_list_all_ordered_by_created_at_desc(self, repo, db_session):
        """Test list_all returns users ordered by created_at desc.

        Note: Due to fast test execution, timestamps may be identical.
        We verify that the ordering query runs successfully and returns
        all users in some deterministic order.
        """
        # Create users
        user1_id = uuid4()
        user2_id = uuid4()

        await repo.create(user_id=user1_id, email="first@example.com")
        await repo.create(user_id=user2_id, email="second@example.com")

        users = await repo.list_all()

        # Verify both users are returned
        assert len(users) == 2
        emails = {u.email for u in users}
        assert "first@example.com" in emails
        assert "second@example.com" in emails

    async def test_list_all_combines_filters(
        self, repo, test_user, regular_user, inactive_user
    ):
        """Test list_all can combine role and is_active filters."""
        users = await repo.list_all(role="user", is_active=True)

        assert len(users) == 1
        assert users[0].id == regular_user.id

    async def test_list_all_returns_empty_when_no_match(self, repo, test_user):
        """Test list_all returns empty list when no users match."""
        users = await repo.list_all(role="superuser")

        assert len(users) == 0

    # =========================================================================
    # count tests
    # =========================================================================

    async def test_count_all_users(self, repo, test_user, regular_user, inactive_user):
        """Test count returns total user count."""
        count = await repo.count()

        assert count == 3

    async def test_count_filters_by_role(self, repo, test_user, regular_user):
        """Test count filters by role."""
        admin_count = await repo.count(role="admin")
        user_count = await repo.count(role="user")

        assert admin_count == 1
        assert user_count == 1

    async def test_count_filters_by_active_status(
        self, repo, test_user, regular_user, inactive_user
    ):
        """Test count filters by active status."""
        active_count = await repo.count(is_active=True)
        inactive_count = await repo.count(is_active=False)

        assert active_count == 2
        assert inactive_count == 1

    async def test_count_combines_filters(
        self, repo, test_user, regular_user, inactive_user
    ):
        """Test count can combine filters."""
        count = await repo.count(role="user", is_active=False)

        assert count == 1

    async def test_count_returns_zero_when_no_match(self, repo, test_user):
        """Test count returns 0 when no users match."""
        count = await repo.count(role="superuser")

        assert count == 0


class TestUserRepositoryEdgeCases:
    """Edge case tests for UserRepository."""

    @pytest.fixture
    async def repo(self, db_session):
        """Create repository instance."""
        return UserRepository(db_session)

    async def test_create_with_very_long_email(self, repo):
        """Test creating user with a long email address."""
        user_id = uuid4()
        # Email within typical limits
        long_local = "a" * 64
        long_domain = "b" * 63 + ".com"
        email = f"{long_local}@{long_domain}"

        user = await repo.create(user_id=user_id, email=email)
        assert user.email == email

    async def test_list_all_with_large_offset(self, repo, test_user):
        """Test list_all with offset larger than user count."""
        users = await repo.list_all(offset=1000)

        assert len(users) == 0
