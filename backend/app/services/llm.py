"""LLM service - Provider abstraction for OpenAI and Anthropic."""

from typing import AsyncGenerator, Literal, Optional

import structlog
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
import tiktoken

from app.config import Settings

logger = structlog.get_logger()


class LLMError(Exception):
    """LLM provider error."""

    pass


class LLMService:
    """Service for LLM interactions with multiple providers."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._openai_client: Optional[AsyncOpenAI] = None
        self._anthropic_client: Optional[AsyncAnthropic] = None
        self._encoding = None

    def _get_openai_client(self) -> AsyncOpenAI:
        """Get or create OpenAI client."""
        if self._openai_client is None:
            self._openai_client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        return self._openai_client

    def _get_anthropic_client(self) -> AsyncAnthropic:
        """Get or create Anthropic client."""
        if self._anthropic_client is None:
            self._anthropic_client = AsyncAnthropic(
                api_key=self.settings.anthropic_api_key
            )
        return self._anthropic_client

    def _get_encoding(self):
        """Get tiktoken encoding for token counting."""
        if self._encoding is None:
            self._encoding = tiktoken.get_encoding("cl100k_base")
        return self._encoding

    def count_tokens(self, text: str) -> int:
        """Count tokens in text.

        Args:
            text: Text to count tokens for

        Returns:
            Number of tokens
        """
        encoding = self._get_encoding()
        return len(encoding.encode(text))

    def _get_provider(self, model: str) -> Literal["openai", "anthropic"]:
        """Determine provider from model name.

        Args:
            model: Model identifier

        Returns:
            Provider name
        """
        if model.startswith("claude"):
            return "anthropic"
        return "openai"

    async def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors

        Raises:
            LLMError: If embedding generation fails
        """
        try:
            client = self._get_openai_client()
            response = await client.embeddings.create(
                model=self.settings.ruhroh_embedding_model,
                input=texts,
            )

            # Sort by index to ensure order matches input
            embeddings = sorted(response.data, key=lambda x: x.index)
            return [e.embedding for e in embeddings]

        except Exception as e:
            logger.error("embedding_generation_failed", error=str(e))
            raise LLMError(f"Failed to generate embeddings: {e}")

    async def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        embeddings = await self.generate_embeddings([text])
        return embeddings[0]

    async def chat_completion(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """Generate a chat completion.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use (default from settings)
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response

        Returns:
            Generated text

        Raises:
            LLMError: If generation fails
        """
        model = model or self.settings.ruhroh_default_model
        provider = self._get_provider(model)

        try:
            if provider == "anthropic":
                return await self._anthropic_completion(
                    messages, model, temperature, max_tokens
                )
            else:
                return await self._openai_completion(
                    messages, model, temperature, max_tokens
                )
        except Exception as e:
            logger.error("chat_completion_failed", error=str(e), model=model)
            raise LLMError(f"Chat completion failed: {e}")

    async def _openai_completion(
        self,
        messages: list[dict],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """OpenAI chat completion."""
        client = self._get_openai_client()
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    async def _anthropic_completion(
        self,
        messages: list[dict],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Anthropic chat completion."""
        client = self._get_anthropic_client()

        # Convert message format for Anthropic
        system_message = None
        anthropic_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                anthropic_messages.append({
                    "role": msg["role"],
                    "content": msg["content"],
                })

        response = await client.messages.create(
            model=model,
            messages=anthropic_messages,
            system=system_message,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.content[0].text

    async def chat_completion_stream(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming chat completion.

        Args:
            messages: List of message dicts
            model: Model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens

        Yields:
            Token strings as they're generated

        Raises:
            LLMError: If generation fails
        """
        model = model or self.settings.ruhroh_default_model
        provider = self._get_provider(model)

        try:
            if provider == "anthropic":
                async for token in self._anthropic_stream(
                    messages, model, temperature, max_tokens
                ):
                    yield token
            else:
                async for token in self._openai_stream(
                    messages, model, temperature, max_tokens
                ):
                    yield token
        except Exception as e:
            logger.error("chat_stream_failed", error=str(e), model=model)
            raise LLMError(f"Chat stream failed: {e}")

    async def _openai_stream(
        self,
        messages: list[dict],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> AsyncGenerator[str, None]:
        """OpenAI streaming completion."""
        client = self._get_openai_client()
        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def _anthropic_stream(
        self,
        messages: list[dict],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> AsyncGenerator[str, None]:
        """Anthropic streaming completion."""
        client = self._get_anthropic_client()

        # Convert message format
        system_message = None
        anthropic_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                anthropic_messages.append({
                    "role": msg["role"],
                    "content": msg["content"],
                })

        async with client.messages.stream(
            model=model,
            messages=anthropic_messages,
            system=system_message,
            temperature=temperature,
            max_tokens=max_tokens,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def close(self) -> None:
        """Close clients."""
        if self._openai_client:
            await self._openai_client.close()
            self._openai_client = None
        if self._anthropic_client:
            await self._anthropic_client.close()
            self._anthropic_client = None
