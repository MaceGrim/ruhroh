"""Tests for the chat service."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.config import Settings
from app.db.models import Thread, Message
from app.services.chat import ChatService
from app.services.retrieval import RetrievalResult


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
        ruhroh_default_model="gpt-4",
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
    mock.count_tokens.return_value = 10

    async def mock_stream(*args, **kwargs):
        for token in ["Hello", " ", "world", "!"]:
            yield token

    mock.chat_completion_stream = mock_stream
    return mock


@pytest.fixture
def mock_retrieval_service():
    """Create mock retrieval service."""
    mock = AsyncMock()
    mock.get_context_for_chat.return_value = ("", [])
    return mock


@pytest.fixture
def chat_service(test_settings, mock_session, mock_llm_service, mock_retrieval_service):
    """Create chat service with mocked dependencies."""
    return ChatService(
        settings=test_settings,
        session=mock_session,
        llm_service=mock_llm_service,
        retrieval_service=mock_retrieval_service,
    )


@pytest.fixture
def sample_user_id():
    """Sample user UUID."""
    return UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture
def sample_thread_id():
    """Sample thread UUID."""
    return UUID("00000000-0000-0000-0000-000000000002")


@pytest.fixture
def sample_thread(sample_user_id, sample_thread_id):
    """Create sample thread object."""
    thread = MagicMock(spec=Thread)
    thread.id = sample_thread_id
    thread.user_id = sample_user_id
    thread.name = "Test Conversation"
    thread.created_at = datetime.utcnow()
    thread.updated_at = datetime.utcnow()
    thread.messages = []
    return thread


@pytest.fixture
def sample_message(sample_thread_id):
    """Create sample message object."""
    message = MagicMock(spec=Message)
    message.id = uuid4()
    message.thread_id = sample_thread_id
    message.role = "user"
    message.content = "Hello, how are you?"
    message.citations = None
    message.model_used = None
    message.is_from_documents = True
    message.created_at = datetime.utcnow()
    return message


# =============================================================================
# Test: create_thread
# =============================================================================


class TestCreateThread:
    """Tests for create_thread method."""

    @pytest.mark.asyncio
    async def test_create_thread_with_default_name(
        self, chat_service, sample_user_id, sample_thread
    ):
        """Test creating a thread with default name."""
        chat_service.thread_repo.create = AsyncMock(return_value=sample_thread)

        result = await chat_service.create_thread(sample_user_id)

        assert "id" in result
        assert "name" in result
        assert "created_at" in result
        assert "updated_at" in result
        chat_service.thread_repo.create.assert_awaited_once_with(
            user_id=sample_user_id,
            name="New Conversation",
        )

    @pytest.mark.asyncio
    async def test_create_thread_with_custom_name(
        self, chat_service, sample_user_id, sample_thread
    ):
        """Test creating a thread with custom name."""
        sample_thread.name = "Custom Name"
        chat_service.thread_repo.create = AsyncMock(return_value=sample_thread)

        result = await chat_service.create_thread(sample_user_id, name="Custom Name")

        assert result["name"] == "Custom Name"
        chat_service.thread_repo.create.assert_awaited_once_with(
            user_id=sample_user_id,
            name="Custom Name",
        )


# =============================================================================
# Test: get_thread
# =============================================================================


class TestGetThread:
    """Tests for get_thread method."""

    @pytest.mark.asyncio
    async def test_get_thread_success(
        self, chat_service, sample_user_id, sample_thread_id, sample_thread
    ):
        """Test getting an existing thread."""
        chat_service.thread_repo.get_by_id_with_messages = AsyncMock(
            return_value=sample_thread
        )

        result = await chat_service.get_thread(sample_thread_id, sample_user_id)

        assert result is not None
        assert result["id"] == str(sample_thread_id)
        assert result["name"] == sample_thread.name
        assert "messages" in result
        chat_service.thread_repo.get_by_id_with_messages.assert_awaited_once_with(
            sample_thread_id, sample_user_id
        )

    @pytest.mark.asyncio
    async def test_get_thread_not_found(
        self, chat_service, sample_user_id, sample_thread_id
    ):
        """Test getting a non-existent thread."""
        chat_service.thread_repo.get_by_id_with_messages = AsyncMock(return_value=None)

        result = await chat_service.get_thread(sample_thread_id, sample_user_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_thread_with_messages(
        self, chat_service, sample_user_id, sample_thread_id, sample_thread, sample_message
    ):
        """Test getting a thread with messages."""
        sample_thread.messages = [sample_message]
        chat_service.thread_repo.get_by_id_with_messages = AsyncMock(
            return_value=sample_thread
        )

        result = await chat_service.get_thread(sample_thread_id, sample_user_id)

        assert result is not None
        assert len(result["messages"]) == 1
        assert result["messages"][0]["content"] == sample_message.content


# =============================================================================
# Test: list_threads
# =============================================================================


class TestListThreads:
    """Tests for list_threads method."""

    @pytest.mark.asyncio
    async def test_list_threads_empty(self, chat_service, sample_user_id):
        """Test listing threads when none exist."""
        chat_service.thread_repo.list_by_user = AsyncMock(return_value=[])
        chat_service.thread_repo.count_by_user = AsyncMock(return_value=0)

        result = await chat_service.list_threads(sample_user_id)

        assert result["threads"] == []
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_list_threads_with_results(
        self, chat_service, sample_user_id, sample_thread
    ):
        """Test listing threads with results."""
        chat_service.thread_repo.list_by_user = AsyncMock(return_value=[sample_thread])
        chat_service.thread_repo.count_by_user = AsyncMock(return_value=1)

        result = await chat_service.list_threads(sample_user_id)

        assert len(result["threads"]) == 1
        assert result["total"] == 1
        assert result["threads"][0]["name"] == sample_thread.name

    @pytest.mark.asyncio
    async def test_list_threads_with_pagination(
        self, chat_service, sample_user_id, sample_thread
    ):
        """Test listing threads with pagination."""
        chat_service.thread_repo.list_by_user = AsyncMock(return_value=[sample_thread])
        chat_service.thread_repo.count_by_user = AsyncMock(return_value=50)

        result = await chat_service.list_threads(sample_user_id, limit=10, offset=20)

        chat_service.thread_repo.list_by_user.assert_awaited_once_with(
            sample_user_id, 10, 20
        )
        assert result["total"] == 50


# =============================================================================
# Test: delete_thread
# =============================================================================


class TestDeleteThread:
    """Tests for delete_thread method."""

    @pytest.mark.asyncio
    async def test_delete_thread_success(
        self, chat_service, sample_user_id, sample_thread_id, sample_thread
    ):
        """Test deleting an existing thread."""
        chat_service.thread_repo.get_by_id = AsyncMock(return_value=sample_thread)
        chat_service.thread_repo.delete = AsyncMock(return_value=True)

        result = await chat_service.delete_thread(sample_thread_id, sample_user_id)

        assert result is True
        chat_service.thread_repo.delete.assert_awaited_once_with(sample_thread_id)

    @pytest.mark.asyncio
    async def test_delete_thread_not_found(
        self, chat_service, sample_user_id, sample_thread_id
    ):
        """Test deleting a non-existent thread."""
        chat_service.thread_repo.get_by_id = AsyncMock(return_value=None)
        chat_service.thread_repo.delete = AsyncMock()

        result = await chat_service.delete_thread(sample_thread_id, sample_user_id)

        assert result is False
        chat_service.thread_repo.delete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_delete_thread_wrong_user(
        self, chat_service, sample_thread_id, sample_thread
    ):
        """Test deleting thread owned by different user."""
        different_user_id = uuid4()
        chat_service.thread_repo.get_by_id = AsyncMock(return_value=None)

        result = await chat_service.delete_thread(sample_thread_id, different_user_id)

        assert result is False


# =============================================================================
# Test: send_message_stream
# =============================================================================


class TestSendMessageStream:
    """Tests for send_message_stream method."""

    @pytest.mark.asyncio
    async def test_send_message_stream_thread_not_found(
        self, chat_service, sample_user_id, sample_thread_id
    ):
        """Test sending message to non-existent thread."""
        chat_service.thread_repo.get_by_id = AsyncMock(return_value=None)

        events = []
        async for event in chat_service.send_message_stream(
            sample_thread_id, sample_user_id, "Hello"
        ):
            events.append(event)

        assert len(events) == 1
        assert events[0]["event"] == "error"
        assert events[0]["data"]["code"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_send_message_stream_success(
        self, chat_service, sample_user_id, sample_thread_id, sample_thread, sample_message
    ):
        """Test successful message streaming."""
        chat_service.thread_repo.get_by_id = AsyncMock(return_value=sample_thread)
        chat_service.thread_repo.touch = AsyncMock()
        chat_service.message_repo.create = AsyncMock(return_value=sample_message)
        chat_service.message_repo.get_last_messages = AsyncMock(return_value=[])
        chat_service.retrieval_service.get_context_for_chat = AsyncMock(
            return_value=("", [])
        )

        events = []
        async for event in chat_service.send_message_stream(
            sample_thread_id, sample_user_id, "Hello"
        ):
            events.append(event)

        # Should have status events (searching, thinking, generating), tokens, and done
        event_types = [e["event"] for e in events]
        assert "status" in event_types
        assert "token" in event_types
        assert "done" in event_types

    @pytest.mark.asyncio
    async def test_send_message_stream_with_context(
        self, chat_service, sample_user_id, sample_thread_id, sample_thread, sample_message
    ):
        """Test message streaming with document context."""
        chat_service.thread_repo.get_by_id = AsyncMock(return_value=sample_thread)
        chat_service.thread_repo.touch = AsyncMock()
        chat_service.message_repo.create = AsyncMock(return_value=sample_message)
        chat_service.message_repo.get_last_messages = AsyncMock(return_value=[])

        # Set up retrieval results
        retrieval_result = RetrievalResult(
            chunk_id=uuid4(),
            document_id=uuid4(),
            document_name="test.pdf",
            content="Some document content",
            score=0.9,
            page_numbers=[1, 2],
        )
        chat_service.retrieval_service.get_context_for_chat = AsyncMock(
            return_value=("Context from documents", [retrieval_result])
        )

        events = []
        async for event in chat_service.send_message_stream(
            sample_thread_id, sample_user_id, "What does the document say?"
        ):
            events.append(event)

        # Verify done event indicates is_from_documents
        done_events = [e for e in events if e["event"] == "done"]
        assert len(done_events) == 1
        assert done_events[0]["data"]["is_from_documents"] is True


# =============================================================================
# Test: _extract_and_renumber_citations
# =============================================================================


class TestExtractAndRenumberCitations:
    """Tests for citation extraction and renumbering."""

    def test_extract_citations_no_citations(self, chat_service):
        """Test extraction when no citations present."""
        response = "This is a simple response without citations."
        results = []

        renumbered, citations = chat_service._extract_and_renumber_citations(
            response, results
        )

        assert renumbered == response
        assert citations == []

    def test_extract_citations_single_citation(self, chat_service):
        """Test extraction with single citation."""
        response = "According to the document [1], this is the answer."
        results = [
            RetrievalResult(
                chunk_id=uuid4(),
                document_id=uuid4(),
                document_name="doc.pdf",
                content="Source content here",
                score=0.9,
                page_numbers=[1],
            )
        ]

        renumbered, citations = chat_service._extract_and_renumber_citations(
            response, results
        )

        assert "[1]" in renumbered
        assert len(citations) == 1
        assert citations[0]["index"] == 1
        assert citations[0]["document_name"] == "doc.pdf"

    def test_extract_citations_multiple_sequential(self, chat_service):
        """Test extraction with multiple sequential citations."""
        response = "First [1] and second [2] and third [3]."
        results = [
            RetrievalResult(
                chunk_id=uuid4(),
                document_id=uuid4(),
                document_name=f"doc{i}.pdf",
                content=f"Content {i}",
                score=0.9 - i * 0.1,
                page_numbers=[i],
            )
            for i in range(1, 4)
        ]

        renumbered, citations = chat_service._extract_and_renumber_citations(
            response, results
        )

        assert "[1]" in renumbered
        assert "[2]" in renumbered
        assert "[3]" in renumbered
        assert len(citations) == 3

    def test_extract_citations_with_gaps(self, chat_service):
        """Test renumbering when citations have gaps."""
        response = "First [1] and third [3]."  # Skipped [2]
        results = [
            RetrievalResult(
                chunk_id=uuid4(),
                document_id=uuid4(),
                document_name=f"doc{i}.pdf",
                content=f"Content {i}",
                score=0.9 - i * 0.1,
                page_numbers=[i],
            )
            for i in range(1, 4)
        ]

        renumbered, citations = chat_service._extract_and_renumber_citations(
            response, results
        )

        # Should renumber to sequential [1], [2]
        assert "[1]" in renumbered
        assert "[2]" in renumbered
        assert "[3]" not in renumbered
        assert len(citations) == 2
        assert citations[0]["index"] == 1
        assert citations[1]["index"] == 2

    def test_extract_citations_out_of_order(self, chat_service):
        """Test renumbering when citations are out of order."""
        response = "Third [3] and first [1]."
        results = [
            RetrievalResult(
                chunk_id=uuid4(),
                document_id=uuid4(),
                document_name=f"doc{i}.pdf",
                content=f"Content {i}",
                score=0.9 - i * 0.1,
                page_numbers=[i],
            )
            for i in range(1, 4)
        ]

        renumbered, citations = chat_service._extract_and_renumber_citations(
            response, results
        )

        # Should maintain order of appearance
        assert len(citations) == 2

    def test_extract_citations_long_content_truncated(self, chat_service):
        """Test that long content is truncated in excerpt."""
        response = "According to [1]."
        long_content = "x" * 500
        results = [
            RetrievalResult(
                chunk_id=uuid4(),
                document_id=uuid4(),
                document_name="doc.pdf",
                content=long_content,
                score=0.9,
                page_numbers=[1],
            )
        ]

        _, citations = chat_service._extract_and_renumber_citations(response, results)

        assert len(citations[0]["excerpt"]) <= 203  # 200 chars + "..."
        assert citations[0]["excerpt"].endswith("...")

    def test_extract_citations_invalid_index(self, chat_service):
        """Test handling of citation index beyond results."""
        response = "According to [10]."  # No result at index 10
        results = [
            RetrievalResult(
                chunk_id=uuid4(),
                document_id=uuid4(),
                document_name="doc.pdf",
                content="Content",
                score=0.9,
                page_numbers=[1],
            )
        ]

        _, citations = chat_service._extract_and_renumber_citations(response, results)

        # Invalid citation should not be included
        assert len(citations) == 0


# =============================================================================
# Test: _build_chat_messages
# =============================================================================


class TestBuildChatMessages:
    """Tests for building chat messages."""

    def test_build_messages_with_context(self, chat_service):
        """Test building messages with document context."""
        messages = chat_service._build_chat_messages(
            "Context from documents",
            [],  # No history
            "What does it say?",
        )

        assert len(messages) == 2  # system + user
        assert messages[0]["role"] == "system"
        assert "Context from documents" in messages[0]["content"]
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == "What does it say?"

    def test_build_messages_without_context(self, chat_service):
        """Test building messages without document context."""
        messages = chat_service._build_chat_messages(
            "",  # No context
            [],  # No history
            "Hello!",
        )

        assert len(messages) == 2
        assert "hasn't uploaded any documents" in messages[0]["content"]

    def test_build_messages_with_history(self, chat_service):
        """Test building messages with conversation history."""
        history_message = MagicMock()
        history_message.role = "user"
        history_message.content = "Previous question"

        messages = chat_service._build_chat_messages(
            "Context",
            [history_message],  # Pre-fetched history
            "Current question",
        )

        # Should include: system, history message, current query
        assert len(messages) == 3
        assert messages[1]["content"] == "Previous question"
        assert messages[2]["content"] == "Current question"

    def test_build_messages_preserves_all_history(self, chat_service):
        """Test that all history messages are preserved (no content-based filtering)."""
        # Create history with repeated content - should all be preserved
        msg1 = MagicMock()
        msg1.role = "user"
        msg1.content = "The answer is 5"

        msg2 = MagicMock()
        msg2.role = "assistant"
        msg2.content = "I understand, the answer is 5."

        messages = chat_service._build_chat_messages(
            "Context",
            [msg1, msg2],
            "What is the answer?",
        )

        # Should include: system + 2 history messages + current query = 4
        assert len(messages) == 4
        assert messages[1]["content"] == "The answer is 5"
        assert messages[2]["content"] == "I understand, the answer is 5."
        assert messages[3]["content"] == "What is the answer?"
