"""Search API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.database import get_db_session
from app.db.models import User
from app.dependencies import get_current_user
from app.models import SearchRequest, SearchResponse, SearchResult
from app.services.llm import LLMService
from app.services.retrieval import RetrievalService

router = APIRouter()


async def get_retrieval_service(
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> RetrievalService:
    """Get retrieval service."""
    llm_service = LLMService(settings)
    return RetrievalService(settings, db, llm_service)


@router.post(
    "",
    response_model=SearchResponse,
)
async def search(
    data: SearchRequest,
    user: Annotated[User, Depends(get_current_user)],
    retrieval_service: Annotated[RetrievalService, Depends(get_retrieval_service)],
):
    """Search across user's documents.

    Performs hybrid search combining vector similarity and keyword matching.
    Results are fused using Reciprocal Rank Fusion (RRF).
    """
    results = await retrieval_service.search(
        query=data.query,
        user_id=user.id,
        top_k=data.top_k,
        document_ids=data.document_ids,
        use_keyword=data.use_keyword,
        use_vector=data.use_vector,
    )

    return SearchResponse(
        results=[
            SearchResult(
                chunk_id=r.chunk_id,
                document_id=r.document_id,
                document_name=r.document_name,
                content=r.content,
                page_numbers=r.page_numbers,
                score=r.score,
            )
            for r in results
        ]
    )
