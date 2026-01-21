"""Chat API routes."""

import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.database import get_db_session
from app.db.models import User
from app.dependencies import get_current_user
from app.models import (
    ThreadCreate,
    ThreadResponse,
    ThreadDetailResponse,
    ThreadListResponse,
    MessageCreate,
    ErrorResponse,
)
from app.services.llm import LLMService
from app.services.retrieval import RetrievalService
from app.services.chat import ChatService

router = APIRouter()


async def get_chat_service(
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ChatService:
    """Get chat service with dependencies."""
    llm_service = LLMService(settings)
    retrieval_service = RetrievalService(settings, db, llm_service)
    return ChatService(settings, db, llm_service, retrieval_service)


@router.get(
    "/threads",
    response_model=ThreadListResponse,
)
async def list_threads(
    user: Annotated[User, Depends(get_current_user)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    limit: int = 20,
    offset: int = 0,
):
    """List user's chat threads."""
    result = await chat_service.list_threads(user.id, limit, offset)

    return ThreadListResponse(
        threads=[
            ThreadResponse(
                id=UUID(t["id"]),
                name=t["name"],
                created_at=t["created_at"],
                updated_at=t["updated_at"],
            )
            for t in result["threads"]
        ],
        total=result["total"],
    )


@router.post(
    "/threads",
    response_model=ThreadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_thread(
    data: ThreadCreate,
    user: Annotated[User, Depends(get_current_user)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
):
    """Create a new chat thread."""
    result = await chat_service.create_thread(user.id, data.name)

    return ThreadResponse(
        id=UUID(result["id"]),
        name=result["name"],
        created_at=result["created_at"],
        updated_at=result["updated_at"],
    )


@router.get(
    "/threads/{thread_id}",
    response_model=ThreadDetailResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_thread(
    thread_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
):
    """Get a thread with its messages."""
    result = await chat_service.get_thread(thread_id, user.id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Thread not found"},
        )

    return ThreadDetailResponse(
        id=UUID(result["id"]),
        name=result["name"],
        created_at=result["created_at"],
        updated_at=result["updated_at"],
        messages=result["messages"],
    )


@router.delete(
    "/threads/{thread_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
)
async def delete_thread(
    thread_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
):
    """Delete a chat thread and all its messages."""
    deleted = await chat_service.delete_thread(thread_id, user.id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Thread not found"},
        )

    return None


@router.post(
    "/threads/{thread_id}/messages",
    responses={404: {"model": ErrorResponse}},
)
async def send_message(
    thread_id: UUID,
    data: MessageCreate,
    user: Annotated[User, Depends(get_current_user)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
):
    """Send a message and receive streaming response.

    Returns Server-Sent Events with the following event types:
    - status: Processing stage updates (searching, thinking, generating)
    - token: Individual response tokens
    - citation: Citation information
    - done: Completion with message ID
    - error: Error information
    """

    async def event_generator():
        """Generate SSE events."""
        async for event in chat_service.send_message_stream(
            thread_id,
            user.id,
            data.content,
            data.model,
        ):
            event_type = event["event"]
            event_data = json.dumps(event["data"])
            yield f"event: {event_type}\ndata: {event_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
