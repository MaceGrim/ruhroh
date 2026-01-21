"""Evaluation Pydantic models."""

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.common import BaseSchema


# ============================================================================
# Single Evaluation Models
# ============================================================================


class SingleEvalRequest(BaseModel):
    """Schema for running a single RAG evaluation."""

    question: str = Field(..., description="The question to evaluate")
    expected_answer: Optional[str] = Field(
        None,
        description="Expected answer for comparison (optional)",
    )
    document_ids: Optional[list[UUID]] = Field(
        None,
        description="Specific documents to search (defaults to all user docs)",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of context chunks to retrieve",
    )
    model: Optional[str] = Field(
        None,
        description="Model to use for answer generation",
    )


class RetrievedContext(BaseModel):
    """Schema for a retrieved context chunk."""

    chunk_id: UUID
    document_id: UUID
    document_name: str
    content: str
    score: float
    page_numbers: Optional[list[int]] = None


class EvalMetrics(BaseModel):
    """Schema for evaluation metrics."""

    faithfulness: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="How faithful the answer is to the retrieved context (0-1)",
    )
    answer_relevancy: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="How relevant the answer is to the question (0-1)",
    )
    context_precision: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Precision of retrieved context chunks (0-1)",
    )
    context_recall: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Recall of retrieved context (requires expected answer)",
    )
    answer_correctness: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Correctness compared to expected answer (requires expected answer)",
    )


class SingleEvalResponse(BaseModel):
    """Schema for single evaluation result."""

    eval_id: UUID
    question: str
    generated_answer: str
    expected_answer: Optional[str] = None
    retrieved_contexts: list[RetrievedContext]
    metrics: EvalMetrics
    model_used: str
    latency_ms: float = Field(..., description="Total evaluation latency in milliseconds")
    created_at: datetime


# ============================================================================
# Batch Evaluation Models
# ============================================================================


class TestCase(BaseModel):
    """Schema for a single test case in batch evaluation."""

    question: str = Field(..., description="The question to evaluate")
    expected_answer: Optional[str] = Field(
        None,
        description="Expected answer for comparison",
    )
    context_ground_truth: Optional[list[str]] = Field(
        None,
        description="Ground truth context (chunk IDs or content snippets)",
    )
    metadata: Optional[dict[str, Any]] = Field(
        None,
        description="Additional metadata for this test case",
    )


class BatchEvalRequest(BaseModel):
    """Schema for running batch evaluation."""

    test_cases: list[TestCase] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of test cases to evaluate",
    )
    document_ids: Optional[list[UUID]] = Field(
        None,
        description="Documents to evaluate against",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of context chunks to retrieve per question",
    )
    model: Optional[str] = Field(
        None,
        description="Model to use for answer generation",
    )
    name: Optional[str] = Field(
        None,
        description="Name for this evaluation run",
    )


class TestCaseResult(BaseModel):
    """Schema for a single test case result in batch evaluation."""

    test_case_index: int
    question: str
    generated_answer: str
    expected_answer: Optional[str] = None
    metrics: EvalMetrics
    retrieved_context_count: int
    latency_ms: float
    error: Optional[str] = None


class BatchEvalSummary(BaseModel):
    """Schema for batch evaluation summary statistics."""

    total_cases: int
    successful_cases: int
    failed_cases: int
    avg_faithfulness: float
    avg_answer_relevancy: float
    avg_context_precision: float
    avg_context_recall: Optional[float] = None
    avg_answer_correctness: Optional[float] = None
    avg_latency_ms: float
    total_duration_seconds: float


class BatchEvalResponse(BaseModel):
    """Schema for batch evaluation response (started)."""

    eval_id: UUID
    status: Literal["pending", "running"] = "pending"
    total_cases: int


class BatchEvalStatusResponse(BaseModel):
    """Schema for batch evaluation status and results."""

    eval_id: UUID
    name: Optional[str] = None
    status: Literal["pending", "running", "completed", "failed"]
    progress: Optional["EvalProgress"] = None
    summary: Optional[BatchEvalSummary] = None
    results: Optional[list[TestCaseResult]] = None
    error: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


# ============================================================================
# Evaluation History Models
# ============================================================================


class EvalHistoryItem(BaseModel):
    """Schema for an evaluation in the history list."""

    eval_id: UUID
    eval_type: Literal["single", "batch", "auto"]
    name: Optional[str] = None
    status: Literal["pending", "running", "completed", "failed"]
    summary_metrics: Optional[dict[str, float]] = None
    total_cases: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class EvalHistoryResponse(BaseModel):
    """Schema for evaluation history list."""

    evaluations: list[EvalHistoryItem]
    total: int
    limit: int
    offset: int


# ============================================================================
# Original Bulk Evaluation Models (kept for backward compatibility)
# ============================================================================


class EvalRunRequest(BaseModel):
    """Schema for starting an evaluation run."""

    document_ids: Optional[list[UUID]] = Field(
        None,
        description="Documents to evaluate (defaults to user's docs)",
    )
    question_count: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Number of questions to generate",
    )
    chunking_strategies: Optional[list[str]] = Field(
        None,
        description="Strategies to compare",
    )
    use_holdout: bool = Field(
        default=False,
        description="Use holdout set for evaluation",
    )


class EvalRunResponse(BaseModel):
    """Schema for eval run creation response."""

    eval_id: UUID
    status: Literal["pending"] = "pending"


class EvalProgress(BaseModel):
    """Schema for evaluation progress."""

    current: int
    total: int


class StrategyComparison(BaseModel):
    """Schema for strategy comparison results."""

    strategy: str
    hit_rate: float
    mrr: float
    context_precision: float
    answer_relevancy: float


class EvalResults(BaseModel):
    """Schema for evaluation results."""

    hit_rate: float = Field(..., description="Percentage of relevant docs retrieved")
    mrr: float = Field(..., description="Mean Reciprocal Rank")
    context_precision: float = Field(..., description="Precision of retrieved context")
    answer_relevancy: float = Field(..., description="Relevance of generated answers")
    strategy_comparison: Optional[list[StrategyComparison]] = Field(
        None,
        description="Comparison of different strategies",
    )
    questions_generated: int
    completed_at: datetime


class EvalStatusResponse(BaseModel):
    """Schema for evaluation status response."""

    eval_id: UUID
    status: Literal["pending", "running", "completed", "failed"]
    progress: Optional[EvalProgress] = None
    results: Optional[EvalResults] = None
