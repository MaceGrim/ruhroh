"""Evaluation API routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.database import get_db_session
from app.db.models import User
from app.dependencies import require_role
from app.models import (
    EvalRunRequest,
    EvalRunResponse,
    EvalStatusResponse,
    EvalProgress,
    EvalResults,
    ErrorResponse,
)
from app.services.llm import LLMService
from app.services.retrieval import RetrievalService
from app.services.eval import EvalService, EvalError

router = APIRouter()


async def get_eval_service(
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> EvalService:
    """Get eval service."""
    llm_service = LLMService(settings)
    retrieval_service = RetrievalService(settings, db, llm_service)
    return EvalService(settings, db, llm_service, retrieval_service)


require_superuser_role = require_role(["superuser", "admin"])


@router.post(
    "/run",
    response_model=EvalRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_superuser_role)],
    responses={400: {"model": ErrorResponse}},
)
async def run_evaluation(
    data: EvalRunRequest,
    background_tasks: BackgroundTasks,
    user: Annotated[User, Depends(require_superuser_role)],
    eval_service: Annotated[EvalService, Depends(get_eval_service)],
):
    """Start an evaluation run (superuser or admin).

    Evaluates RAG pipeline quality by:
    1. Generating questions from document content
    2. Running retrieval for each question
    3. Calculating metrics (hit rate, MRR, context precision, answer relevancy)
    """
    try:
        result = await eval_service.start_evaluation(
            user_id=user.id,
            document_ids=data.document_ids,
            question_count=data.question_count,
            chunking_strategies=data.chunking_strategies,
            use_holdout=data.use_holdout,
        )

        # Run evaluation in background
        background_tasks.add_task(
            eval_service.run_evaluation,
            str(result["eval_id"]),
        )

        return EvalRunResponse(
            eval_id=result["eval_id"],
            status="pending",
        )

    except EvalError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "EVAL_ERROR", "message": str(e)},
        )


@router.get(
    "/{eval_id}",
    response_model=EvalStatusResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_evaluation(
    eval_id: UUID,
    eval_service: Annotated[EvalService, Depends(get_eval_service)],
):
    """Get evaluation status and results."""
    result = await eval_service.get_evaluation(str(eval_id))

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Evaluation not found"},
        )

    response = EvalStatusResponse(
        eval_id=result["eval_id"],
        status=result["status"],
        progress=EvalProgress(**result["progress"]) if result.get("progress") else None,
    )

    if result.get("results"):
        response.results = EvalResults(**result["results"])

    return response
