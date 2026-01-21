"""Evaluation API routes."""

from datetime import datetime
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.database import get_db_session
from app.db.models import User
from app.dependencies import get_current_user, require_role
from app.models import (
    # Single eval
    SingleEvalRequest,
    SingleEvalResponse,
    RetrievedContext,
    EvalMetrics,
    # Batch eval
    BatchEvalRequest,
    BatchEvalResponse,
    BatchEvalStatusResponse,
    BatchEvalSummary,
    TestCaseResult,
    # History
    EvalHistoryItem,
    EvalHistoryResponse,
    # Original models
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


# =============================================================================
# Single Evaluation Endpoints
# =============================================================================


@router.post(
    "/single",
    response_model=SingleEvalResponse,
    status_code=status.HTTP_200_OK,
    responses={400: {"model": ErrorResponse}},
)
async def run_single_evaluation(
    data: SingleEvalRequest,
    user: Annotated[User, Depends(get_current_user)],
    eval_service: Annotated[EvalService, Depends(get_eval_service)],
):
    """Run a single RAG evaluation.

    Evaluates a single question through the RAG pipeline and computes quality metrics:
    - Faithfulness: How well the answer aligns with retrieved context
    - Answer Relevancy: How well the answer addresses the question
    - Context Precision: How relevant the retrieved chunks are
    - Answer Correctness: How correct the answer is (requires expected_answer)
    - Context Recall: Estimated recall of context (requires expected_answer)
    """
    try:
        result = await eval_service.run_single_evaluation(
            user_id=user.id,
            question=data.question,
            expected_answer=data.expected_answer,
            document_ids=data.document_ids,
            top_k=data.top_k,
            model=data.model,
        )

        return SingleEvalResponse(
            eval_id=result["eval_id"],
            question=result["question"],
            generated_answer=result["generated_answer"],
            expected_answer=result["expected_answer"],
            retrieved_contexts=[
                RetrievedContext(**ctx) for ctx in result["retrieved_contexts"]
            ],
            metrics=EvalMetrics(**result["metrics"]),
            model_used=result["model_used"],
            latency_ms=result["latency_ms"],
            created_at=result["created_at"],
        )

    except EvalError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "EVAL_ERROR", "message": str(e)},
        )


# =============================================================================
# Batch Evaluation Endpoints
# =============================================================================


@router.post(
    "/batch",
    response_model=BatchEvalResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={400: {"model": ErrorResponse}},
)
async def run_batch_evaluation(
    data: BatchEvalRequest,
    background_tasks: BackgroundTasks,
    user: Annotated[User, Depends(get_current_user)],
    eval_service: Annotated[EvalService, Depends(get_eval_service)],
):
    """Start a batch evaluation run.

    Evaluates multiple questions through the RAG pipeline. The evaluation runs
    in the background and results can be retrieved using GET /api/v1/eval/batch/{eval_id}.
    """
    try:
        # Convert test cases to dict format
        test_cases = [tc.model_dump() for tc in data.test_cases]

        result = await eval_service.start_batch_evaluation(
            user_id=user.id,
            test_cases=test_cases,
            document_ids=data.document_ids,
            top_k=data.top_k,
            model=data.model,
            name=data.name,
        )

        # Run evaluation in background
        background_tasks.add_task(
            eval_service.run_batch_evaluation,
            str(result["eval_id"]),
        )

        return BatchEvalResponse(
            eval_id=result["eval_id"],
            status="pending",
            total_cases=result["total_cases"],
        )

    except EvalError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "EVAL_ERROR", "message": str(e)},
        )


@router.get(
    "/batch/{eval_id}",
    response_model=BatchEvalStatusResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_batch_evaluation(
    eval_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    eval_service: Annotated[EvalService, Depends(get_eval_service)],
):
    """Get batch evaluation status and results."""
    result = await eval_service.get_evaluation_by_id(str(eval_id), user.id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Evaluation not found"},
        )

    if result["eval_type"] != "batch":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_TYPE", "message": "This is not a batch evaluation"},
        )

    response = BatchEvalStatusResponse(
        eval_id=UUID(result["id"]),
        name=result.get("name"),
        status=result["status"],
        progress=EvalProgress(**result["progress"]) if result.get("progress") else None,
        created_at=datetime.fromisoformat(result["created_at"]),
        completed_at=(
            datetime.fromisoformat(result["completed_at"])
            if result.get("completed_at")
            else None
        ),
        error=result.get("error"),
    )

    if result.get("summary"):
        response.summary = BatchEvalSummary(**result["summary"])

    if result.get("results"):
        response.results = [
            TestCaseResult(
                test_case_index=r["test_case_index"],
                question=r["question"],
                generated_answer=r["generated_answer"],
                expected_answer=r.get("expected_answer"),
                metrics=EvalMetrics(**r["metrics"]),
                retrieved_context_count=r["retrieved_context_count"],
                latency_ms=r["latency_ms"],
                error=r.get("error"),
            )
            for r in result["results"]
        ]

    return response


# =============================================================================
# Evaluation History Endpoints
# =============================================================================


@router.get(
    "/results",
    response_model=EvalHistoryResponse,
)
async def list_evaluation_results(
    user: Annotated[User, Depends(get_current_user)],
    eval_service: Annotated[EvalService, Depends(get_eval_service)],
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    eval_type: Optional[str] = Query(
        default=None,
        description="Filter by evaluation type: single, batch, or auto",
    ),
):
    """List past evaluation results.

    Returns a paginated list of all evaluation runs for the current user.
    """
    result = await eval_service.list_evaluations(
        user_id=user.id,
        limit=limit,
        offset=offset,
        eval_type=eval_type,
    )

    return EvalHistoryResponse(
        evaluations=[
            EvalHistoryItem(
                eval_id=e["eval_id"],
                eval_type=e["eval_type"],
                name=e.get("name"),
                status=e["status"],
                summary_metrics=e.get("summary_metrics"),
                total_cases=e.get("total_cases"),
                created_at=e["created_at"],
                completed_at=e.get("completed_at"),
            )
            for e in result["evaluations"]
        ],
        total=result["total"],
        limit=result["limit"],
        offset=result["offset"],
    )


@router.get(
    "/results/{eval_id}",
    responses={404: {"model": ErrorResponse}},
)
async def get_evaluation_result(
    eval_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    eval_service: Annotated[EvalService, Depends(get_eval_service)],
):
    """Get a specific evaluation result by ID.

    Returns the full evaluation data including all metrics and results.
    The response format varies based on the evaluation type (single, batch, or auto).
    """
    result = await eval_service.get_evaluation_by_id(str(eval_id), user.id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Evaluation not found"},
        )

    # Return appropriate response based on eval type
    if result["eval_type"] == "single":
        return SingleEvalResponse(
            eval_id=UUID(result["id"]),
            question=result["question"],
            generated_answer=result["generated_answer"],
            expected_answer=result.get("expected_answer"),
            retrieved_contexts=[
                RetrievedContext(**ctx) for ctx in result["retrieved_contexts"]
            ],
            metrics=EvalMetrics(**result["metrics"]),
            model_used=result["model_used"],
            latency_ms=result["latency_ms"],
            created_at=datetime.fromisoformat(result["created_at"]),
        )

    elif result["eval_type"] == "batch":
        response = BatchEvalStatusResponse(
            eval_id=UUID(result["id"]),
            name=result.get("name"),
            status=result["status"],
            progress=EvalProgress(**result["progress"]) if result.get("progress") else None,
            created_at=datetime.fromisoformat(result["created_at"]),
            completed_at=(
                datetime.fromisoformat(result["completed_at"])
                if result.get("completed_at")
                else None
            ),
            error=result.get("error"),
        )

        if result.get("summary"):
            response.summary = BatchEvalSummary(**result["summary"])

        if result.get("results"):
            response.results = [
                TestCaseResult(
                    test_case_index=r["test_case_index"],
                    question=r["question"],
                    generated_answer=r["generated_answer"],
                    expected_answer=r.get("expected_answer"),
                    metrics=EvalMetrics(**r["metrics"]),
                    retrieved_context_count=r["retrieved_context_count"],
                    latency_ms=r["latency_ms"],
                    error=r.get("error"),
                )
                for r in result["results"]
            ]

        return response

    else:
        # Return the original auto eval format
        response = EvalStatusResponse(
            eval_id=UUID(result["id"]),
            status=result["status"],
            progress=EvalProgress(**result["progress"]) if result.get("progress") else None,
        )

        if result.get("results"):
            response.results = EvalResults(**result["results"])

        return response


# =============================================================================
# Original Auto-Evaluation Endpoints (backward compatibility)
# =============================================================================


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
