"""Business logic services."""

from app.services.auth import AuthService, AuthError
from app.services.llm import LLMService, LLMError
from app.services.config_service import ConfigService
from app.services.qdrant import (
    get_qdrant_client,
    check_qdrant_health,
    ensure_collection_exists,
    upsert_vectors,
    search_vectors,
    delete_vectors,
    delete_vectors_by_filter,
)
from app.services.ocr import OCRService, OCRError
from app.services.ingestion import IngestionService, IngestionError
from app.services.retrieval import RetrievalService, RetrievalResult
from app.services.chat import ChatService
from app.services.admin import AdminService
from app.services.extraction import ExtractionService, ExtractionError
from app.services.eval import EvalService, EvalError

__all__ = [
    # Auth
    "AuthService",
    "AuthError",
    # LLM
    "LLMService",
    "LLMError",
    # Config
    "ConfigService",
    # Qdrant
    "get_qdrant_client",
    "check_qdrant_health",
    "ensure_collection_exists",
    "upsert_vectors",
    "search_vectors",
    "delete_vectors",
    "delete_vectors_by_filter",
    # OCR
    "OCRService",
    "OCRError",
    # Ingestion
    "IngestionService",
    "IngestionError",
    # Retrieval
    "RetrievalService",
    "RetrievalResult",
    # Chat
    "ChatService",
    # Admin
    "AdminService",
    # Extraction
    "ExtractionService",
    "ExtractionError",
    # Eval
    "EvalService",
    "EvalError",
]
