"""Document management API routes."""

import os
import shutil
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
import magic

from app.config import Settings, get_settings
from app.db.database import get_db_session
from app.db.models import User
from app.db.repositories.document import DocumentRepository
from app.dependencies import get_current_user
from app.models import (
    DocumentUploadResponse,
    DocumentResponse,
    DocumentDetailResponse,
    DocumentStatusResponse,
    DocumentListResponse,
    DocumentReprocess,
    ErrorResponse,
)
from app.services.llm import LLMService
from app.services.ingestion import IngestionService

router = APIRouter()

ALLOWED_MIME_TYPES = {
    "application/pdf": "pdf",
    "text/plain": "txt",
}

MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB


async def get_llm_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> LLMService:
    """Get LLM service."""
    return LLMService(settings)


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={409: {"model": ErrorResponse}, 413: {"model": ErrorResponse}, 415: {"model": ErrorResponse}},
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: Annotated[UploadFile, File()],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    llm_service: Annotated[LLMService, Depends(get_llm_service)],
    chunking_strategy: Annotated[str, Form()] = "fixed",
    ocr_enabled: Annotated[bool, Form()] = False,
    force_replace: Annotated[bool, Form()] = False,
):
    """Upload a new document for processing.

    Accepts PDF and TXT files up to 500MB. Processing happens in the background.
    """
    # Read file content
    content = await file.read()

    # Check file size
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"code": "FILE_TOO_LARGE", "message": "File exceeds 500MB limit"},
        )

    # Validate MIME type
    detected_mime = magic.from_buffer(content[:2048], mime=True)
    if detected_mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={"code": "UNSUPPORTED_FILE_TYPE", "message": f"Unsupported file type: {detected_mime}"},
        )

    file_type = ALLOWED_MIME_TYPES[detected_mime]

    # Initialize repository and service
    doc_repo = DocumentRepository(db)
    ingestion_service = IngestionService(settings)

    # Normalize filename
    filename = file.filename or "document"
    normalized_filename = ingestion_service.normalize_filename(filename)

    # Check for existing document
    existing = await doc_repo.get_by_normalized_filename(user.id, normalized_filename)

    if existing and not force_replace:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "DOCUMENT_EXISTS",
                "message": f"Document '{filename}' already exists. Use force_replace=true to overwrite.",
            },
        )

    if existing and force_replace:
        # Delete existing document
        await ingestion_service.delete_document(existing.id, session=db)

    # Save file
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_path = upload_dir / f"{user.id}_{normalized_filename}"
    with open(file_path, "wb") as f:
        f.write(content)

    # Create document record
    document = await doc_repo.create(
        user_id=user.id,
        filename=filename,
        normalized_filename=normalized_filename,
        file_type=file_type,
        file_path=str(file_path),
        file_size=len(content),
        chunking_strategy=chunking_strategy,
        ocr_enabled=ocr_enabled,
    )

    # Commit so background task can see the document
    await db.commit()

    # Process in background
    background_tasks.add_task(
        ingestion_service.process_document,
        document.id,
    )

    return DocumentUploadResponse(document_id=document.id)


@router.get(
    "",
    response_model=DocumentListResponse,
)
async def list_documents(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """List user's documents with optional status filter."""
    doc_repo = DocumentRepository(db)

    documents = await doc_repo.list_by_user(
        user.id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    total = await doc_repo.count_by_user(user.id, status=status_filter)

    return DocumentListResponse(
        documents=[
            DocumentResponse(
                id=d.id,
                filename=d.filename,
                normalized_filename=d.normalized_filename,
                file_type=d.file_type,
                file_size=d.file_size,
                page_count=d.page_count,
                status=d.status,
                chunking_strategy=d.chunking_strategy,
                ocr_enabled=d.ocr_enabled,
                error_message=d.error_message,
                created_at=d.created_at,
                updated_at=d.updated_at,
            )
            for d in documents
        ],
        total=total,
    )


@router.get(
    "/{document_id}",
    response_model=DocumentDetailResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_document(
    document_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Get detailed information about a document."""
    doc_repo = DocumentRepository(db)

    document = await doc_repo.get_by_id(document_id, user.id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Document not found"},
        )

    chunk_count = await doc_repo.get_chunk_count(document_id)

    return DocumentDetailResponse(
        id=document.id,
        user_id=document.user_id,
        filename=document.filename,
        normalized_filename=document.normalized_filename,
        file_type=document.file_type,
        file_size=document.file_size,
        page_count=document.page_count,
        status=document.status,
        chunking_strategy=document.chunking_strategy,
        ocr_enabled=document.ocr_enabled,
        error_message=document.error_message,
        created_at=document.created_at,
        updated_at=document.updated_at,
        chunk_count=chunk_count,
    )


@router.get(
    "/{document_id}/status",
    response_model=DocumentStatusResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_document_status(
    document_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Get document processing status."""
    doc_repo = DocumentRepository(db)

    document = await doc_repo.get_by_id(document_id, user.id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Document not found"},
        )

    progress = None
    if document.status == "processing":
        progress = "Processing document..."
    elif document.status == "pending":
        progress = "Queued for processing"

    return DocumentStatusResponse(
        status=document.status,
        progress=progress,
        error_message=document.error_message,
    )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
)
async def delete_document(
    document_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    llm_service: Annotated[LLMService, Depends(get_llm_service)],
):
    """Delete a document and all associated data."""
    doc_repo = DocumentRepository(db)

    document = await doc_repo.get_by_id(document_id, user.id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Document not found"},
        )

    ingestion_service = IngestionService(settings)
    await ingestion_service.delete_document(document_id, session=db)

    return None


@router.post(
    "/{document_id}/reprocess",
    response_model=DocumentStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={404: {"model": ErrorResponse}},
)
async def reprocess_document(
    document_id: UUID,
    data: DocumentReprocess,
    background_tasks: BackgroundTasks,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    llm_service: Annotated[LLMService, Depends(get_llm_service)],
):
    """Reprocess a document with new settings."""
    doc_repo = DocumentRepository(db)

    document = await doc_repo.get_by_id(document_id, user.id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Document not found"},
        )

    ingestion_service = IngestionService(settings)

    # Reprocess in background
    background_tasks.add_task(
        ingestion_service.reprocess_document,
        document_id,
        data.chunking_strategy,
        data.ocr_enabled,
    )

    return DocumentStatusResponse(status="pending", progress="Queued for reprocessing")
