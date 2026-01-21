"""Chat service for conversation management."""

import re
from typing import AsyncGenerator, Optional
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.repositories.thread import ThreadRepository
from app.db.repositories.message import MessageRepository
from app.services.llm import LLMService
from app.services.retrieval import RetrievalService, RetrievalResult

logger = structlog.get_logger()


SYSTEM_PROMPT = """You are a helpful document assistant. You help users with their uploaded documents while maintaining natural conversation flow.

CRITICAL: Before using the CONTEXT section below, first check if the user's message refers to something said earlier in the conversation. The conversation history (previous user/assistant messages) takes priority over document context for conversational references.

RULES:
1. If the user refers to something from earlier in the conversation (e.g., "what did I say", "the answer", "remember when"), respond based on the conversation history, NOT the documents
2. For questions specifically about documents, use the CONTEXT section and cite sources using [1], [2], etc.
3. If the user makes a statement not related to documents (e.g., "The answer is 5"), acknowledge it naturally - don't search for it in documents
4. Be concise and direct
5. Never make up document information
6. Only say "I couldn't find this" if the information is in neither the conversation NOR the documents

CONTEXT:
{context}"""

TITLE_GENERATION_PROMPT = """Generate a very short title (2-4 words max) for a conversation that starts with this message.
Return ONLY the title, no quotes, no punctuation at the end, no explanation.

Message: {message}"""


class ChatService:
    """Service for chat interactions."""

    def __init__(
        self,
        settings: Settings,
        session: AsyncSession,
        llm_service: LLMService,
        retrieval_service: RetrievalService,
    ):
        self.settings = settings
        self.session = session
        self.thread_repo = ThreadRepository(session)
        self.message_repo = MessageRepository(session)
        self.llm_service = llm_service
        self.retrieval_service = retrieval_service

    async def create_thread(
        self,
        user_id: UUID,
        name: Optional[str] = None,
    ) -> dict:
        """Create a new chat thread.

        Args:
            user_id: User UUID
            name: Optional thread name

        Returns:
            Thread dict
        """
        thread = await self.thread_repo.create(
            user_id=user_id,
            name=name or "New Conversation",
        )

        return {
            "id": str(thread.id),
            "name": thread.name,
            "created_at": thread.created_at.isoformat(),
            "updated_at": thread.updated_at.isoformat(),
        }

    async def get_thread(
        self,
        thread_id: UUID,
        user_id: UUID,
    ) -> Optional[dict]:
        """Get thread with messages.

        Args:
            thread_id: Thread UUID
            user_id: User UUID for ownership check

        Returns:
            Thread dict with messages or None
        """
        thread = await self.thread_repo.get_by_id_with_messages(thread_id, user_id)
        if not thread:
            return None

        return {
            "id": str(thread.id),
            "name": thread.name,
            "created_at": thread.created_at.isoformat(),
            "updated_at": thread.updated_at.isoformat(),
            "messages": [
                {
                    "id": str(m.id),
                    "thread_id": str(m.thread_id),
                    "role": m.role,
                    "content": m.content,
                    "citations": m.citations,
                    "model_used": m.model_used,
                    "is_from_documents": m.is_from_documents,
                    "token_count": m.token_count,
                    "created_at": m.created_at.isoformat(),
                }
                for m in sorted(thread.messages, key=lambda x: x.created_at)
            ],
        }

    async def list_threads(
        self,
        user_id: UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> dict:
        """List user's threads.

        Args:
            user_id: User UUID
            limit: Max threads
            offset: Pagination offset

        Returns:
            Dict with threads list and total
        """
        threads = await self.thread_repo.list_by_user(user_id, limit, offset)
        total = await self.thread_repo.count_by_user(user_id)

        return {
            "threads": [
                {
                    "id": str(t.id),
                    "name": t.name,
                    "created_at": t.created_at.isoformat(),
                    "updated_at": t.updated_at.isoformat(),
                }
                for t in threads
            ],
            "total": total,
        }

    async def delete_thread(
        self,
        thread_id: UUID,
        user_id: UUID,
    ) -> bool:
        """Delete a thread.

        Args:
            thread_id: Thread UUID
            user_id: User UUID for ownership check

        Returns:
            True if deleted
        """
        thread = await self.thread_repo.get_by_id(thread_id, user_id)
        if not thread:
            return False

        return await self.thread_repo.delete(thread_id)

    async def _generate_thread_title(self, first_message: str) -> str:
        """Generate a short title from the first message.

        Args:
            first_message: The first user message in the thread

        Returns:
            A 2-4 word title
        """
        try:
            messages = [
                {"role": "user", "content": TITLE_GENERATION_PROMPT.format(message=first_message[:500])}
            ]
            title = await self.llm_service.chat_completion(messages, max_tokens=20)
            # Clean up the title - remove quotes and trailing punctuation
            title = title.strip().strip('"\'').rstrip('.!?')
            # Limit length
            if len(title) > 50:
                title = title[:47] + "..."
            return title or "New Conversation"
        except Exception as e:
            logger.warning("Failed to generate thread title", error=str(e))
            return "New Conversation"

    async def update_thread_name(
        self,
        thread_id: UUID,
        name: str,
    ) -> Optional[dict]:
        """Update thread name.

        Args:
            thread_id: Thread UUID
            name: New name

        Returns:
            Updated thread dict or None
        """
        thread = await self.thread_repo.update_name(thread_id, name)
        if not thread:
            return None
        return {
            "id": str(thread.id),
            "name": thread.name,
            "created_at": thread.created_at.isoformat(),
            "updated_at": thread.updated_at.isoformat(),
        }

    async def send_message_stream(
        self,
        thread_id: UUID,
        user_id: UUID,
        content: str,
        model: Optional[str] = None,
    ) -> AsyncGenerator[dict, None]:
        """Send a message and stream the response.

        Args:
            thread_id: Thread UUID
            user_id: User UUID
            content: Message content
            model: Optional model to use

        Yields:
            SSE event dicts
        """
        # Verify thread ownership
        thread = await self.thread_repo.get_by_id(thread_id, user_id)
        if not thread:
            yield {"event": "error", "data": {"code": "NOT_FOUND", "message": "Thread not found"}}
            return

        # Check if this is the first message (for auto-title generation)
        message_count = await self.message_repo.count_by_thread(thread_id)
        is_first_message = message_count == 0
        logger.info("Message count check", thread_id=str(thread_id), message_count=message_count, is_first_message=is_first_message)

        # Fetch conversation history BEFORE saving the new message
        # This avoids the need for content-based deduplication which can drop legitimate history
        conversation_history = await self.message_repo.get_last_messages(thread_id, count=10)

        # Save user message
        user_message = await self.message_repo.create(
            thread_id=thread_id,
            role="user",
            content=content,
        )

        # Update thread timestamp
        await self.thread_repo.touch(thread_id)

        # Yield searching status
        yield {"event": "status", "data": {"stage": "searching"}}

        # Retrieve context
        context, retrieval_results = await self.retrieval_service.get_context_for_chat(
            content, user_id
        )

        is_from_documents = len(retrieval_results) > 0

        # Yield thinking status
        yield {"event": "status", "data": {"stage": "thinking"}}

        # Build messages for LLM (pass pre-fetched history and current query)
        messages = self._build_chat_messages(
            context, conversation_history, content
        )

        # Yield generating status
        yield {"event": "status", "data": {"stage": "generating"}}

        # Stream response
        full_response = ""
        model_used = model or self.settings.ruhroh_default_model

        async for token in self.llm_service.chat_completion_stream(
            messages, model=model_used
        ):
            full_response += token
            yield {"event": "token", "data": {"content": token}}

        # Extract citations and renumber them sequentially
        renumbered_response, citations = self._extract_and_renumber_citations(
            full_response, retrieval_results
        )
        for citation in citations:
            yield {"event": "citation", "data": citation}

        # Save assistant message with renumbered content
        assistant_message = await self.message_repo.create(
            thread_id=thread_id,
            role="assistant",
            content=renumbered_response,
            citations=citations if citations else None,
            model_used=model_used,
            is_from_documents=is_from_documents,
            token_count=self.llm_service.count_tokens(renumbered_response),
        )

        # Generate title for new threads (after first message)
        new_title = None
        if is_first_message:
            logger.info("Generating title for new thread", thread_id=str(thread_id))
            new_title = await self._generate_thread_title(content)
            logger.info("Generated title", title=new_title, thread_id=str(thread_id))
            await self.thread_repo.update_name(thread_id, new_title)
            yield {"event": "title", "data": {"title": new_title}}

        # Yield done with renumbered content for clients to update their display
        yield {
            "event": "done",
            "data": {
                "message_id": str(assistant_message.id),
                "is_from_documents": is_from_documents,
                "content": renumbered_response,
            },
        }

    def _build_chat_messages(
        self,
        context: str,
        conversation_history: list,
        current_query: str,
    ) -> list[dict]:
        """Build messages list for LLM.

        Args:
            context: Retrieved context
            conversation_history: Pre-fetched conversation history (excludes current message)
            current_query: Current user query

        Returns:
            List of message dicts
        """
        messages = []

        # System message with context
        if context:
            system_content = SYSTEM_PROMPT.format(context=context)
        else:
            system_content = (
                "You are a helpful assistant. You can have natural conversations and help with "
                "general questions. If the user asks about specific documents and none have been "
                "uploaded or no relevant context was found, let them know they can upload documents "
                "to get document-based answers. For general conversation or follow-up questions, "
                "respond helpfully using the conversation history."
            )

        messages.append({"role": "system", "content": system_content})

        # Add conversation history (fetched BEFORE saving current message, so no dedup needed)
        for msg in conversation_history:
            messages.append({"role": msg.role, "content": msg.content})

        # Add current query
        messages.append({"role": "user", "content": current_query})

        logger.info(
            "Built chat messages",
            message_count=len(messages),
            history_count=len(conversation_history),
        )

        return messages

    def _extract_and_renumber_citations(
        self,
        response: str,
        retrieval_results: list[RetrievalResult],
    ) -> tuple[str, list[dict]]:
        """Extract citations from response and renumber them sequentially.

        Args:
            response: LLM response text
            retrieval_results: Retrieved chunks

        Returns:
            Tuple of (renumbered_response, citations)
        """
        citations = []

        # Find citation markers like [1], [2], etc.
        pattern = r"\[(\d+)\]"
        matches = re.findall(pattern, response)
        used_indices = sorted(set(int(m) for m in matches))

        # Create mapping from old index to new sequential index
        old_to_new = {old_idx: new_idx for new_idx, old_idx in enumerate(used_indices, start=1)}

        # Renumber citations in response text using temporary placeholders to avoid cascading replacements
        # First pass: replace [N] with temporary placeholder <<N>>
        renumbered_response = response
        for old_idx in used_indices:
            renumbered_response = renumbered_response.replace(f"[{old_idx}]", f"<<{old_idx}>>")

        # Second pass: replace <<N>> with new sequential number [M]
        for old_idx, new_idx in old_to_new.items():
            renumbered_response = renumbered_response.replace(f"<<{old_idx}>>", f"[{new_idx}]")

        # Build citation list with new indices
        for old_idx in used_indices:
            # Citation indices are 1-based
            result_idx = old_idx - 1
            if 0 <= result_idx < len(retrieval_results):
                result = retrieval_results[result_idx]

                # Create excerpt (first 200 chars)
                excerpt = result.content[:200]
                if len(result.content) > 200:
                    excerpt += "..."

                citations.append({
                    "index": old_to_new[old_idx],
                    "chunk_id": str(result.chunk_id),
                    "document_id": str(result.document_id),
                    "document_name": result.document_name,
                    "pages": result.page_numbers or [],
                    "excerpt": excerpt,
                })

        return renumbered_response, citations
