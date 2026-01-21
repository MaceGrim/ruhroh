"""Pydantic models for API requests and responses."""

from app.models.common import (
    BaseSchema,
    ErrorDetail,
    ErrorResponse,
    PaginatedResponse,
    HealthStatus,
    TimestampMixin,
)
from app.models.user import (
    UserBase,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
    AuthTokenResponse,
    RefreshTokenRequest,
    TokenRefreshResponse,
    UserRegisterResponse,
)
from app.models.document import (
    DocumentUpload,
    DocumentResponse,
    DocumentDetailResponse,
    DocumentStatusResponse,
    DocumentUploadResponse,
    DocumentReprocess,
    DocumentListResponse,
    DocumentListParams,
)
from app.models.chunk import (
    ChunkResponse,
    ChunkCreate,
    SearchResult,
    SearchRequest,
    SearchResponse,
)
from app.models.thread import (
    ThreadCreate,
    ThreadResponse,
    ThreadDetailResponse,
    ThreadListResponse,
    ThreadListParams,
)
from app.models.message import (
    Citation,
    MessageCreate,
    MessageResponse,
    StreamEvent,
    StatusEvent,
    TokenEvent,
    CitationEvent,
    DoneEvent,
    ErrorEvent,
)
from app.models.schema import (
    EntityDefinition,
    CustomFieldDefinition,
    SchemaDefinition,
    ExtractionSchemaCreate,
    ExtractionSchemaUpdate,
    ExtractionSchemaResponse,
    ExtractionSchemaListResponse,
)
from app.models.eval import (
    # Single eval
    SingleEvalRequest,
    SingleEvalResponse,
    RetrievedContext,
    EvalMetrics,
    # Batch eval
    TestCase,
    BatchEvalRequest,
    TestCaseResult,
    BatchEvalSummary,
    BatchEvalResponse,
    BatchEvalStatusResponse,
    # History
    EvalHistoryItem,
    EvalHistoryResponse,
    # Original models
    EvalRunRequest,
    EvalRunResponse,
    EvalProgress,
    StrategyComparison,
    EvalResults,
    EvalStatusResponse,
)
from app.models.admin import (
    AdminStats,
    AdminUserListParams,
    AdminUserListResponse,
    AdminDocumentListParams,
    AdminDocumentListResponse,
    AdminHealthResponse,
)

__all__ = [
    # Common
    "BaseSchema",
    "ErrorDetail",
    "ErrorResponse",
    "PaginatedResponse",
    "HealthStatus",
    "TimestampMixin",
    # User
    "UserBase",
    "UserCreate",
    "UserLogin",
    "UserResponse",
    "UserUpdate",
    "AuthTokenResponse",
    "RefreshTokenRequest",
    "TokenRefreshResponse",
    "UserRegisterResponse",
    # Document
    "DocumentUpload",
    "DocumentResponse",
    "DocumentDetailResponse",
    "DocumentStatusResponse",
    "DocumentUploadResponse",
    "DocumentReprocess",
    "DocumentListResponse",
    "DocumentListParams",
    # Chunk
    "ChunkResponse",
    "ChunkCreate",
    "SearchResult",
    "SearchRequest",
    "SearchResponse",
    # Thread
    "ThreadCreate",
    "ThreadResponse",
    "ThreadDetailResponse",
    "ThreadListResponse",
    "ThreadListParams",
    # Message
    "Citation",
    "MessageCreate",
    "MessageResponse",
    "StreamEvent",
    "StatusEvent",
    "TokenEvent",
    "CitationEvent",
    "DoneEvent",
    "ErrorEvent",
    # Schema
    "EntityDefinition",
    "CustomFieldDefinition",
    "SchemaDefinition",
    "ExtractionSchemaCreate",
    "ExtractionSchemaUpdate",
    "ExtractionSchemaResponse",
    "ExtractionSchemaListResponse",
    # Eval - Single
    "SingleEvalRequest",
    "SingleEvalResponse",
    "RetrievedContext",
    "EvalMetrics",
    # Eval - Batch
    "TestCase",
    "BatchEvalRequest",
    "TestCaseResult",
    "BatchEvalSummary",
    "BatchEvalResponse",
    "BatchEvalStatusResponse",
    # Eval - History
    "EvalHistoryItem",
    "EvalHistoryResponse",
    # Eval - Original
    "EvalRunRequest",
    "EvalRunResponse",
    "EvalProgress",
    "StrategyComparison",
    "EvalResults",
    "EvalStatusResponse",
    # Admin
    "AdminStats",
    "AdminUserListParams",
    "AdminUserListResponse",
    "AdminDocumentListParams",
    "AdminDocumentListResponse",
    "AdminHealthResponse",
]
