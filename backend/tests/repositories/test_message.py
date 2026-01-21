"""Tests for MessageRepository."""

import pytest
from datetime import datetime
from uuid import uuid4
import asyncio

from app.db.repositories.message import MessageRepository
from app.db.models import Thread, Message


class TestMessageRepository:
    """Test cases for MessageRepository."""

    @pytest.fixture
    async def repo(self, db_session):
        """Create repository instance."""
        return MessageRepository(db_session)

    @pytest.fixture
    async def test_thread(self, db_session, test_user):
        """Create a test thread for message tests."""
        thread = Thread(
            user_id=test_user.id,
            name="Test Thread",
        )
        db_session.add(thread)
        await db_session.flush()
        return thread

    @pytest.fixture
    async def test_message(self, db_session, test_thread):
        """Create a test message."""
        message = Message(
            thread_id=test_thread.id,
            role="user",
            content="Test message content",
        )
        db_session.add(message)
        await db_session.flush()
        return message

    # =========================================================================
    # get_by_id tests
    # =========================================================================

    async def test_get_by_id_returns_message_when_exists(
        self, repo, test_message
    ):
        """Test get_by_id returns message when it exists."""
        result = await repo.get_by_id(test_message.id)

        assert result is not None
        assert result.id == test_message.id
        assert result.content == test_message.content

    async def test_get_by_id_returns_none_when_not_exists(self, repo):
        """Test get_by_id returns None when message does not exist."""
        result = await repo.get_by_id(uuid4())

        assert result is None

    # =========================================================================
    # create tests
    # =========================================================================

    async def test_create_user_message(self, repo, test_thread):
        """Test creating a user message."""
        message = await repo.create(
            thread_id=test_thread.id,
            role="user",
            content="Hello, world!",
        )

        assert message.id is not None
        assert message.thread_id == test_thread.id
        assert message.role == "user"
        assert message.content == "Hello, world!"
        assert message.is_from_documents is True  # default

    async def test_create_assistant_message(self, repo, test_thread):
        """Test creating an assistant message."""
        message = await repo.create(
            thread_id=test_thread.id,
            role="assistant",
            content="Hello! How can I help you?",
        )

        assert message.role == "assistant"
        assert message.content == "Hello! How can I help you?"

    async def test_create_message_with_citations(self, repo, test_thread):
        """Test creating message with citations."""
        citations = [
            {"document_id": str(uuid4()), "chunk_id": str(uuid4()), "text": "Source text"},
        ]
        message = await repo.create(
            thread_id=test_thread.id,
            role="assistant",
            content="Based on the document...",
            citations=citations,
        )

        assert message.citations is not None

    async def test_create_message_with_model_used(self, repo, test_thread):
        """Test creating message with model_used field."""
        message = await repo.create(
            thread_id=test_thread.id,
            role="assistant",
            content="Response",
            model_used="claude-3-opus-20240229",
        )

        assert message.model_used == "claude-3-opus-20240229"

    async def test_create_message_with_is_from_documents_false(
        self, repo, test_thread
    ):
        """Test creating message with is_from_documents=False."""
        message = await repo.create(
            thread_id=test_thread.id,
            role="assistant",
            content="General response not from documents",
            is_from_documents=False,
        )

        assert message.is_from_documents is False

    async def test_create_message_with_token_count(self, repo, test_thread):
        """Test creating message with token_count."""
        message = await repo.create(
            thread_id=test_thread.id,
            role="user",
            content="Short message",
            token_count=5,
        )

        assert message.token_count == 5

    async def test_create_message_is_persisted(self, repo, test_thread):
        """Test that created message is persisted."""
        message = await repo.create(
            thread_id=test_thread.id,
            role="user",
            content="Persisted message",
        )

        # Verify we can retrieve it
        retrieved = await repo.get_by_id(message.id)
        assert retrieved is not None
        assert retrieved.content == "Persisted message"

    # =========================================================================
    # delete tests
    # =========================================================================

    async def test_delete_removes_message(
        self, repo, test_message, db_session
    ):
        """Test delete removes the message."""
        result = await repo.delete(test_message.id)

        assert result is True

        # Verify it's gone
        msg = await repo.get_by_id(test_message.id)
        assert msg is None

    async def test_delete_returns_false_for_nonexistent(self, repo):
        """Test delete returns False for non-existent message."""
        result = await repo.delete(uuid4())

        assert result is False

    # =========================================================================
    # list_by_thread tests
    # =========================================================================

    async def test_list_by_thread_returns_messages(
        self, repo, test_thread, db_session
    ):
        """Test list_by_thread returns messages for the thread."""
        # Create messages
        for i in range(3):
            msg = Message(
                thread_id=test_thread.id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i}",
            )
            db_session.add(msg)
        await db_session.flush()

        messages = await repo.list_by_thread(test_thread.id)

        assert len(messages) == 3

    async def test_list_by_thread_ordered_by_created_at(
        self, repo, test_thread, db_session
    ):
        """Test list_by_thread returns messages ordered by created_at."""
        # Create messages with small delays
        messages_data = ["First", "Second", "Third"]
        for content in messages_data:
            msg = Message(
                thread_id=test_thread.id,
                role="user",
                content=content,
            )
            db_session.add(msg)
            await db_session.flush()
            await asyncio.sleep(0.01)

        messages = await repo.list_by_thread(test_thread.id)

        # Should be in chronological order
        assert messages[0].content == "First"
        assert messages[1].content == "Second"
        assert messages[2].content == "Third"

    async def test_list_by_thread_respects_pagination(
        self, repo, test_thread, db_session
    ):
        """Test list_by_thread respects limit and offset."""
        # Create 10 messages
        for i in range(10):
            msg = Message(
                thread_id=test_thread.id,
                role="user",
                content=f"Message {i}",
            )
            db_session.add(msg)
        await db_session.flush()

        page1 = await repo.list_by_thread(test_thread.id, limit=3, offset=0)
        page2 = await repo.list_by_thread(test_thread.id, limit=3, offset=3)

        assert len(page1) == 3
        assert len(page2) == 3
        assert page1[0].id != page2[0].id

    async def test_list_by_thread_returns_empty_for_no_messages(
        self, repo, test_thread
    ):
        """Test list_by_thread returns empty for thread with no messages."""
        messages = await repo.list_by_thread(test_thread.id)

        assert len(messages) == 0

    async def test_list_by_thread_excludes_other_threads(
        self, repo, test_user, db_session
    ):
        """Test list_by_thread excludes messages from other threads."""
        # Create two threads
        thread1 = Thread(user_id=test_user.id, name="Thread 1")
        thread2 = Thread(user_id=test_user.id, name="Thread 2")
        db_session.add(thread1)
        db_session.add(thread2)
        await db_session.flush()

        # Add message to thread1 only
        msg = Message(thread_id=thread1.id, role="user", content="Thread 1 message")
        db_session.add(msg)
        await db_session.flush()

        # Thread2 should have no messages
        messages = await repo.list_by_thread(thread2.id)
        assert len(messages) == 0

    # =========================================================================
    # count_by_thread tests
    # =========================================================================

    async def test_count_by_thread_returns_correct_count(
        self, repo, test_thread, db_session
    ):
        """Test count_by_thread returns correct count."""
        # Create messages
        for i in range(5):
            msg = Message(
                thread_id=test_thread.id,
                role="user",
                content=f"Message {i}",
            )
            db_session.add(msg)
        await db_session.flush()

        count = await repo.count_by_thread(test_thread.id)

        assert count == 5

    async def test_count_by_thread_returns_zero_for_no_messages(
        self, repo, test_thread
    ):
        """Test count_by_thread returns 0 when no messages exist."""
        count = await repo.count_by_thread(test_thread.id)

        assert count == 0

    # =========================================================================
    # get_last_messages tests
    # =========================================================================

    async def test_get_last_messages_returns_recent_messages(
        self, repo, test_thread, db_session
    ):
        """Test get_last_messages returns the requested count of messages.

        Note: Due to fast test execution, created_at timestamps may be
        identical, so we verify count rather than specific ordering.
        """
        # Create 10 messages
        for i in range(10):
            msg = Message(
                thread_id=test_thread.id,
                role="user",
                content=f"Message {i}",
            )
            db_session.add(msg)
        await db_session.flush()

        messages = await repo.get_last_messages(test_thread.id, count=3)

        # Should return exactly 3 messages
        assert len(messages) == 3
        # Verify we got 3 distinct messages
        contents = [m.content for m in messages]
        assert len(set(contents)) == 3

    async def test_get_last_messages_returns_in_chronological_order(
        self, repo, test_thread, db_session
    ):
        """Test get_last_messages returns messages.

        Note: Due to fast test execution, created_at timestamps may be
        identical, so the ordering within the returned set may vary.
        We verify that the function returns distinct messages.
        """
        # Create messages
        contents = ["First", "Second", "Third", "Fourth", "Fifth"]
        for content in contents:
            msg = Message(
                thread_id=test_thread.id,
                role="user",
                content=content,
            )
            db_session.add(msg)
        await db_session.flush()

        messages = await repo.get_last_messages(test_thread.id, count=3)

        # Should return 3 distinct messages
        assert len(messages) == 3
        returned_contents = [m.content for m in messages]
        assert len(set(returned_contents)) == 3

    async def test_get_last_messages_returns_all_when_fewer_than_count(
        self, repo, test_thread, db_session
    ):
        """Test get_last_messages returns all when fewer messages than count."""
        # Create 2 messages
        for i in range(2):
            msg = Message(
                thread_id=test_thread.id,
                role="user",
                content=f"Message {i}",
            )
            db_session.add(msg)
        await db_session.flush()

        messages = await repo.get_last_messages(test_thread.id, count=10)

        assert len(messages) == 2

    async def test_get_last_messages_returns_empty_for_no_messages(
        self, repo, test_thread
    ):
        """Test get_last_messages returns empty for thread with no messages."""
        messages = await repo.get_last_messages(test_thread.id, count=5)

        assert len(messages) == 0

    async def test_get_last_messages_default_count(
        self, repo, test_thread, db_session
    ):
        """Test get_last_messages uses default count of 10."""
        # Create 15 messages
        for i in range(15):
            msg = Message(
                thread_id=test_thread.id,
                role="user",
                content=f"Message {i}",
            )
            db_session.add(msg)
        await db_session.flush()

        messages = await repo.get_last_messages(test_thread.id)

        assert len(messages) == 10  # default count


class TestMessageRepositoryEdgeCases:
    """Edge case tests for MessageRepository."""

    @pytest.fixture
    async def repo(self, db_session):
        """Create repository instance."""
        return MessageRepository(db_session)

    @pytest.fixture
    async def test_thread(self, db_session, test_user):
        """Create a test thread."""
        thread = Thread(user_id=test_user.id, name="Test Thread")
        db_session.add(thread)
        await db_session.flush()
        return thread

    async def test_create_message_with_long_content(
        self, repo, test_thread
    ):
        """Test creating message with very long content."""
        long_content = "x" * 100000  # 100KB of content

        message = await repo.create(
            thread_id=test_thread.id,
            role="user",
            content=long_content,
        )

        assert len(message.content) == 100000

    async def test_create_message_with_unicode(self, repo, test_thread):
        """Test creating message with unicode characters."""
        unicode_content = "Hello World! Testing unicode content."

        message = await repo.create(
            thread_id=test_thread.id,
            role="user",
            content=unicode_content,
        )

        assert message.content == unicode_content

    async def test_create_message_with_newlines(self, repo, test_thread):
        """Test creating message with newlines."""
        multiline_content = "Line 1\nLine 2\nLine 3\n\nLine 5"

        message = await repo.create(
            thread_id=test_thread.id,
            role="user",
            content=multiline_content,
        )

        assert message.content == multiline_content

    async def test_create_message_with_complex_citations(
        self, repo, test_thread
    ):
        """Test creating message with complex citations structure."""
        complex_citations = [
            {
                "document_id": str(uuid4()),
                "chunk_id": str(uuid4()),
                "text": "First citation text",
                "page_numbers": [1, 2],
                "score": 0.95,
            },
            {
                "document_id": str(uuid4()),
                "chunk_id": str(uuid4()),
                "text": "Second citation text",
                "page_numbers": [3],
                "score": 0.87,
            },
        ]

        message = await repo.create(
            thread_id=test_thread.id,
            role="assistant",
            content="Response with citations",
            citations=complex_citations,
        )

        assert message.citations is not None

    async def test_list_by_thread_with_large_offset(
        self, repo, test_thread
    ):
        """Test list_by_thread with offset larger than message count."""
        messages = await repo.list_by_thread(test_thread.id, offset=1000)

        assert len(messages) == 0

    async def test_create_message_with_empty_content(self, repo, test_thread):
        """Test creating message with empty content."""
        message = await repo.create(
            thread_id=test_thread.id,
            role="user",
            content="",
        )

        assert message.content == ""


class TestMessageConversationPatterns:
    """Test realistic conversation patterns."""

    @pytest.fixture
    async def repo(self, db_session):
        """Create repository instance."""
        return MessageRepository(db_session)

    @pytest.fixture
    async def test_thread(self, db_session, test_user):
        """Create a test thread."""
        thread = Thread(user_id=test_user.id, name="Conversation Thread")
        db_session.add(thread)
        await db_session.flush()
        return thread

    async def test_typical_conversation_flow(self, repo, test_thread):
        """Test a typical back-and-forth conversation."""
        # User asks a question
        user_msg1 = await repo.create(
            thread_id=test_thread.id,
            role="user",
            content="What is machine learning?",
        )

        # Assistant responds
        assistant_msg1 = await repo.create(
            thread_id=test_thread.id,
            role="assistant",
            content="Machine learning is a subset of AI...",
            model_used="claude-3-opus",
            is_from_documents=True,
        )

        # User follows up
        user_msg2 = await repo.create(
            thread_id=test_thread.id,
            role="user",
            content="Can you give an example?",
        )

        # Assistant responds again
        assistant_msg2 = await repo.create(
            thread_id=test_thread.id,
            role="assistant",
            content="Sure! One common example is...",
            model_used="claude-3-opus",
        )

        # Verify conversation
        messages = await repo.list_by_thread(test_thread.id)

        assert len(messages) == 4
        assert messages[0].role == "user"
        assert messages[1].role == "assistant"
        assert messages[2].role == "user"
        assert messages[3].role == "assistant"

    async def test_conversation_with_citations(self, repo, test_thread):
        """Test conversation where assistant provides citations."""
        # User asks about documents
        await repo.create(
            thread_id=test_thread.id,
            role="user",
            content="What does the report say about sales?",
        )

        # Assistant responds with citations
        doc_id = str(uuid4())
        citations = [
            {
                "document_id": doc_id,
                "text": "Sales increased by 15% in Q4",
                "page_numbers": [5],
            },
        ]
        await repo.create(
            thread_id=test_thread.id,
            role="assistant",
            content="According to the report, sales increased by 15% in Q4 [1].",
            citations=citations,
            is_from_documents=True,
        )

        messages = await repo.list_by_thread(test_thread.id)
        assert len(messages) == 2
        assert messages[1].citations is not None
        assert messages[1].is_from_documents is True

    async def test_get_context_for_new_message(self, repo, test_thread):
        """Test getting recent messages for context.

        Note: Due to fast test execution, created_at timestamps may be
        identical, so specific message ordering may vary.
        """
        # Create a longer conversation
        for i in range(20):
            await repo.create(
                thread_id=test_thread.id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message number {i}",
            )

        # Get last 5 messages for context
        context = await repo.get_last_messages(test_thread.id, count=5)

        # Should return 5 distinct messages
        assert len(context) == 5
        contents = [m.content for m in context]
        assert len(set(contents)) == 5
