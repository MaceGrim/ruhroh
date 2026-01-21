"""Evaluation Pydantic models."""

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.common import BaseSchema


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
