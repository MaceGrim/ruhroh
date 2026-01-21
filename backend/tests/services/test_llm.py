"""Tests for the LLM service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Settings
from app.services.llm import LLMService, LLMError


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
        ruhroh_embedding_model="text-embedding-3-small",
        dev_mode=True,
    )


@pytest.fixture
def llm_service(test_settings):
    """Create LLM service instance."""
    return LLMService(settings=test_settings)


@pytest.fixture
def mock_openai_client():
    """Create mock OpenAI client."""
    mock = AsyncMock()
    return mock


@pytest.fixture
def mock_anthropic_client():
    """Create mock Anthropic client."""
    mock = AsyncMock()
    return mock


# =============================================================================
# Test: Provider Detection
# =============================================================================


class TestProviderDetection:
    """Tests for LLM provider detection."""

    def test_get_provider_openai_gpt4(self, llm_service):
        """Test that gpt-4 models use OpenAI."""
        provider = llm_service._get_provider("gpt-4")
        assert provider == "openai"

    def test_get_provider_openai_gpt35(self, llm_service):
        """Test that gpt-3.5 models use OpenAI."""
        provider = llm_service._get_provider("gpt-3.5-turbo")
        assert provider == "openai"

    def test_get_provider_openai_gpt4_turbo(self, llm_service):
        """Test that gpt-4-turbo models use OpenAI."""
        provider = llm_service._get_provider("gpt-4-turbo")
        assert provider == "openai"

    def test_get_provider_anthropic_claude3(self, llm_service):
        """Test that claude-3 models use Anthropic."""
        provider = llm_service._get_provider("claude-3-opus-20240229")
        assert provider == "anthropic"

    def test_get_provider_anthropic_claude2(self, llm_service):
        """Test that claude-2 models use Anthropic."""
        provider = llm_service._get_provider("claude-2.1")
        assert provider == "anthropic"

    def test_get_provider_anthropic_claude_sonnet(self, llm_service):
        """Test that claude-3-sonnet uses Anthropic."""
        provider = llm_service._get_provider("claude-3-sonnet-20240229")
        assert provider == "anthropic"

    def test_get_provider_unknown_defaults_openai(self, llm_service):
        """Test that unknown models default to OpenAI."""
        provider = llm_service._get_provider("unknown-model")
        assert provider == "openai"


# =============================================================================
# Test: Token Counting
# =============================================================================


class TestTokenCounting:
    """Tests for token counting functionality."""

    def test_count_tokens_empty_string(self, llm_service):
        """Test counting tokens in empty string."""
        count = llm_service.count_tokens("")
        assert count == 0

    def test_count_tokens_simple_text(self, llm_service):
        """Test counting tokens in simple text."""
        count = llm_service.count_tokens("Hello world")
        assert count > 0

    def test_count_tokens_longer_text(self, llm_service):
        """Test counting tokens in longer text."""
        short_count = llm_service.count_tokens("Hello")
        long_count = llm_service.count_tokens("Hello world, this is a longer sentence.")
        assert long_count > short_count

    def test_count_tokens_special_characters(self, llm_service):
        """Test counting tokens with special characters."""
        count = llm_service.count_tokens("Hello! @#$%^&*() World?")
        assert count > 0

    def test_count_tokens_unicode(self, llm_service):
        """Test counting tokens with unicode characters."""
        count = llm_service.count_tokens("Hello")
        assert count > 0


# =============================================================================
# Test: Generate Embeddings
# =============================================================================


class TestGenerateEmbeddings:
    """Tests for embedding generation."""

    @pytest.mark.asyncio
    async def test_generate_embeddings_single_text(self, llm_service):
        """Test generating embeddings for single text."""
        mock_response = MagicMock()
        mock_embedding = MagicMock()
        mock_embedding.index = 0
        mock_embedding.embedding = [0.1] * 1536
        mock_response.data = [mock_embedding]

        with patch.object(llm_service, "_get_openai_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.embeddings.create.return_value = mock_response
            mock_get_client.return_value = mock_client

            embeddings = await llm_service.generate_embeddings(["test text"])

            assert len(embeddings) == 1
            assert len(embeddings[0]) == 1536
            mock_client.embeddings.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_generate_embeddings_multiple_texts(self, llm_service):
        """Test generating embeddings for multiple texts."""
        mock_response = MagicMock()
        mock_embeddings = []
        for i in range(3):
            emb = MagicMock()
            emb.index = i
            emb.embedding = [0.1 * (i + 1)] * 1536
            mock_embeddings.append(emb)
        mock_response.data = mock_embeddings

        with patch.object(llm_service, "_get_openai_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.embeddings.create.return_value = mock_response
            mock_get_client.return_value = mock_client

            embeddings = await llm_service.generate_embeddings(
                ["text1", "text2", "text3"]
            )

            assert len(embeddings) == 3

    @pytest.mark.asyncio
    async def test_generate_embeddings_error_handling(self, llm_service):
        """Test error handling in embedding generation."""
        with patch.object(llm_service, "_get_openai_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.embeddings.create.side_effect = Exception("API error")
            mock_get_client.return_value = mock_client

            with pytest.raises(LLMError) as exc_info:
                await llm_service.generate_embeddings(["test text"])

            assert "Failed to generate embeddings" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_embedding_single(self, llm_service):
        """Test generating single embedding."""
        mock_response = MagicMock()
        mock_embedding = MagicMock()
        mock_embedding.index = 0
        mock_embedding.embedding = [0.5] * 1536
        mock_response.data = [mock_embedding]

        with patch.object(llm_service, "_get_openai_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.embeddings.create.return_value = mock_response
            mock_get_client.return_value = mock_client

            embedding = await llm_service.generate_embedding("test text")

            assert len(embedding) == 1536
            assert embedding[0] == 0.5


# =============================================================================
# Test: Chat Completion
# =============================================================================


class TestChatCompletion:
    """Tests for chat completion functionality."""

    @pytest.mark.asyncio
    async def test_chat_completion_openai(self, llm_service):
        """Test chat completion with OpenAI."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello! I'm an AI assistant."

        with patch.object(llm_service, "_get_openai_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_get_client.return_value = mock_client

            messages = [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Hello!"},
            ]

            response = await llm_service.chat_completion(messages, model="gpt-4")

            assert response == "Hello! I'm an AI assistant."
            mock_client.chat.completions.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_chat_completion_anthropic(self, llm_service):
        """Test chat completion with Anthropic."""
        mock_response = MagicMock()
        mock_content = MagicMock()
        mock_content.text = "Hello from Claude!"
        mock_response.content = [mock_content]

        with patch.object(llm_service, "_get_anthropic_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.messages.create.return_value = mock_response
            mock_get_client.return_value = mock_client

            messages = [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Hello!"},
            ]

            response = await llm_service.chat_completion(
                messages, model="claude-3-opus-20240229"
            )

            assert response == "Hello from Claude!"
            mock_client.messages.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_chat_completion_anthropic_message_format(self, llm_service):
        """Test that Anthropic messages are formatted correctly."""
        mock_response = MagicMock()
        mock_content = MagicMock()
        mock_content.text = "Response"
        mock_response.content = [mock_content]

        with patch.object(llm_service, "_get_anthropic_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.messages.create.return_value = mock_response
            mock_get_client.return_value = mock_client

            messages = [
                {"role": "system", "content": "System prompt"},
                {"role": "user", "content": "User message"},
                {"role": "assistant", "content": "Assistant response"},
                {"role": "user", "content": "Follow up"},
            ]

            await llm_service.chat_completion(messages, model="claude-3-opus-20240229")

            call_kwargs = mock_client.messages.create.call_args.kwargs
            # System should be passed separately
            assert call_kwargs["system"] == "System prompt"
            # Messages should not include system message
            assert len(call_kwargs["messages"]) == 3

    @pytest.mark.asyncio
    async def test_chat_completion_default_model(self, llm_service):
        """Test chat completion uses default model when not specified."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"

        with patch.object(llm_service, "_get_openai_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_get_client.return_value = mock_client

            messages = [{"role": "user", "content": "Hello"}]

            await llm_service.chat_completion(messages)

            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            assert call_kwargs["model"] == "gpt-4"  # Default from settings

    @pytest.mark.asyncio
    async def test_chat_completion_custom_parameters(self, llm_service):
        """Test chat completion with custom temperature and max_tokens."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"

        with patch.object(llm_service, "_get_openai_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_get_client.return_value = mock_client

            messages = [{"role": "user", "content": "Hello"}]

            await llm_service.chat_completion(
                messages, temperature=0.5, max_tokens=1000
            )

            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            assert call_kwargs["temperature"] == 0.5
            assert call_kwargs["max_tokens"] == 1000

    @pytest.mark.asyncio
    async def test_chat_completion_error_handling(self, llm_service):
        """Test error handling in chat completion."""
        with patch.object(llm_service, "_get_openai_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.chat.completions.create.side_effect = Exception("API error")
            mock_get_client.return_value = mock_client

            messages = [{"role": "user", "content": "Hello"}]

            with pytest.raises(LLMError) as exc_info:
                await llm_service.chat_completion(messages)

            assert "Chat completion failed" in str(exc_info.value)


# =============================================================================
# Test: Streaming Chat Completion
# =============================================================================


class TestStreamingChatCompletion:
    """Tests for streaming chat completion."""

    @pytest.mark.asyncio
    async def test_chat_completion_stream_openai(self, llm_service):
        """Test streaming chat completion with OpenAI."""

        async def mock_stream():
            for content in ["Hello", " ", "world", "!"]:
                chunk = MagicMock()
                chunk.choices = [MagicMock()]
                chunk.choices[0].delta.content = content
                yield chunk

        with patch.object(llm_service, "_get_openai_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.chat.completions.create.return_value = mock_stream()
            mock_get_client.return_value = mock_client

            messages = [{"role": "user", "content": "Hello"}]

            tokens = []
            async for token in llm_service.chat_completion_stream(messages, model="gpt-4"):
                tokens.append(token)

            assert tokens == ["Hello", " ", "world", "!"]

    @pytest.mark.asyncio
    async def test_chat_completion_stream_openai_empty_chunks(self, llm_service):
        """Test streaming handles empty content chunks."""

        async def mock_stream():
            # First chunk might have empty content
            chunk1 = MagicMock()
            chunk1.choices = [MagicMock()]
            chunk1.choices[0].delta.content = None
            yield chunk1

            # Second chunk has content
            chunk2 = MagicMock()
            chunk2.choices = [MagicMock()]
            chunk2.choices[0].delta.content = "Hello"
            yield chunk2

        with patch.object(llm_service, "_get_openai_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.chat.completions.create.return_value = mock_stream()
            mock_get_client.return_value = mock_client

            messages = [{"role": "user", "content": "Hello"}]

            tokens = []
            async for token in llm_service.chat_completion_stream(messages, model="gpt-4"):
                tokens.append(token)

            # Should only include non-empty content
            assert tokens == ["Hello"]

    @pytest.mark.asyncio
    async def test_chat_completion_stream_anthropic(self, llm_service):
        """Test streaming chat completion with Anthropic."""

        async def mock_text_stream():
            for text in ["Hello", " ", "from", " ", "Claude"]:
                yield text

        # Create a proper async context manager class
        class MockStreamContext:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

            @property
            def text_stream(self):
                return mock_text_stream()

        with patch.object(llm_service, "_get_anthropic_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.messages.stream.return_value = MockStreamContext()

            mock_get_client.return_value = mock_client

            messages = [{"role": "user", "content": "Hello"}]

            tokens = []
            async for token in llm_service.chat_completion_stream(
                messages, model="claude-3-opus-20240229"
            ):
                tokens.append(token)

            assert tokens == ["Hello", " ", "from", " ", "Claude"]

    @pytest.mark.asyncio
    async def test_chat_completion_stream_error(self, llm_service):
        """Test error handling in streaming chat completion."""
        with patch.object(llm_service, "_get_openai_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.chat.completions.create.side_effect = Exception("Stream error")
            mock_get_client.return_value = mock_client

            messages = [{"role": "user", "content": "Hello"}]

            with pytest.raises(LLMError) as exc_info:
                async for _ in llm_service.chat_completion_stream(messages, model="gpt-4"):
                    pass

            assert "Chat stream failed" in str(exc_info.value)


# =============================================================================
# Test: Client Management
# =============================================================================


class TestClientManagement:
    """Tests for client lifecycle management."""

    def test_openai_client_lazy_initialization(self, llm_service):
        """Test that OpenAI client is lazily initialized."""
        assert llm_service._openai_client is None
        client = llm_service._get_openai_client()
        assert client is not None
        assert llm_service._openai_client is client

    def test_anthropic_client_lazy_initialization(self, llm_service):
        """Test that Anthropic client is lazily initialized."""
        assert llm_service._anthropic_client is None
        client = llm_service._get_anthropic_client()
        assert client is not None
        assert llm_service._anthropic_client is client

    def test_clients_reused(self, llm_service):
        """Test that clients are reused on subsequent calls."""
        client1 = llm_service._get_openai_client()
        client2 = llm_service._get_openai_client()
        assert client1 is client2

    @pytest.mark.asyncio
    async def test_close_clients(self, llm_service):
        """Test closing clients."""
        # Initialize mock clients
        mock_openai = AsyncMock()
        mock_anthropic = AsyncMock()
        llm_service._openai_client = mock_openai
        llm_service._anthropic_client = mock_anthropic

        await llm_service.close()

        # Verify close was called on the original mocks
        mock_openai.close.assert_awaited_once()
        mock_anthropic.close.assert_awaited_once()
        # Verify clients are set to None after close
        assert llm_service._openai_client is None
        assert llm_service._anthropic_client is None

    @pytest.mark.asyncio
    async def test_close_clients_when_not_initialized(self, llm_service):
        """Test closing when clients were never initialized."""
        # Should not raise
        await llm_service.close()

    def test_encoding_lazy_initialization(self, llm_service):
        """Test that tiktoken encoding is lazily initialized."""
        assert llm_service._encoding is None
        encoding = llm_service._get_encoding()
        assert encoding is not None
        assert llm_service._encoding is encoding

    def test_encoding_reused(self, llm_service):
        """Test that encoding is reused."""
        enc1 = llm_service._get_encoding()
        enc2 = llm_service._get_encoding()
        assert enc1 is enc2
